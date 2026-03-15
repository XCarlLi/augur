"""Claude Agent SDK session management. One persistent session per chat."""

import time
from typing import Callable

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
    AssistantMessage,
    ResultMessage,
    SystemMessage,
    TextBlock,
)

from . import log
from .permissions import create_isolation_callback
from .prompt import build_system_prompt
from .store import ChatStore
from .types import BotConfig, ChatState, FeishuEvent


class AgentManager:
    """Manages Claude sessions per chat."""

    def __init__(
        self,
        config: BotConfig,
        store: ChatStore,
        respond: Callable[[str, str, str | None], str | None],
        update: Callable[[str, str], bool],
    ) -> None:
        self._config = config
        self._store = store
        self._respond = respond
        self._update = update
        self._states: dict[str, ChatState] = {}

    def is_running(self, chat_id: str) -> bool:
        state = self._states.get(chat_id)
        return state.running if state else False

    async def run(self, event: FeishuEvent) -> None:
        """Run Claude on the event. Streams response back to Feishu."""
        state = self._get_state(event.chat_id)
        state.running = True
        state.stop_requested = False

        try:
            client = await self._get_or_create_client(state, event)
            await client.query(event.text)

            msg_id: str | None = None
            full_text = ""
            last_update = 0.0

            async for msg in client.receive_response():
                if state.stop_requested:
                    try:
                        await client.interrupt()
                    except Exception:
                        pass
                    break

                if isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        if isinstance(block, TextBlock):
                            full_text += block.text
                            now = time.monotonic()
                            if now - last_update >= 1.0:
                                if msg_id is None:
                                    msg_id = self._respond(
                                        event.chat_id, full_text, event.message_id
                                    )
                                else:
                                    self._update(msg_id, full_text)
                                last_update = now

                elif isinstance(msg, ResultMessage):
                    state.session_id = msg.session_id
                    if msg.is_error and msg.result:
                        full_text += f"\nError: {msg.result}"

                elif isinstance(msg, SystemMessage):
                    log.info(f"system: {msg.subtype}")

            # Final update to ensure complete text is shown
            if msg_id and full_text:
                if not self._update(msg_id, full_text):
                    self._respond(event.chat_id, full_text, None)
            elif full_text.strip():
                self._respond(event.chat_id, full_text, event.message_id)
            else:
                self._respond(event.chat_id, "(no response)", event.message_id)

        except Exception as e:
            log.error("agent run failed", str(e))
            self._respond(event.chat_id, f"Error: {e}", event.message_id)
            await self._reset_client(state)
        finally:
            state.running = False

    def abort(self, chat_id: str) -> None:
        state = self._states.get(chat_id)
        if state:
            state.stop_requested = True

    async def shutdown(self) -> None:
        """Disconnect all sessions. Called on bot shutdown."""
        for state in self._states.values():
            await self._reset_client(state)

    async def _get_or_create_client(
        self, state: ChatState, event: FeishuEvent
    ) -> ClaudeSDKClient:
        if state.client is not None:
            return state.client

        system_prompt = build_system_prompt(
            event.sender_id, event.chat_id, self._store
        )
        permission_cb = create_isolation_callback(
            event.sender_id, self._config.working_dir
        )
        options = ClaudeAgentOptions(
            system_prompt=system_prompt,
            permission_mode="acceptEdits",
            can_use_tool=permission_cb,
            cwd=str(self._store.scratch_dir(event.chat_id)),
            model=self._config.model,
        )
        client = ClaudeSDKClient(options=options)
        await client.connect()
        state.client = client
        return client

    async def _reset_client(self, state: ChatState) -> None:
        if state.client:
            try:
                await state.client.disconnect()
            except Exception:
                pass
            state.client = None
            state.session_id = None

    def _get_state(self, chat_id: str) -> ChatState:
        if chat_id not in self._states:
            self._states[chat_id] = ChatState(chat_id=chat_id)
        return self._states[chat_id]
