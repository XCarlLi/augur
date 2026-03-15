"""Feishu WebSocket event receiver and REST API message sender."""

import json
from typing import Callable

import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
    PatchMessageRequest,
    PatchMessageRequestBody,
    ReplyMessageRequest,
    ReplyMessageRequestBody,
)
from lark_oapi.api.im.v1.model.p2_im_message_receive_v1 import (
    P2ImMessageReceiveV1,
)

from . import log
from .types import BotConfig, EventType, FeishuEvent


def _card_content(text: str) -> str:
    """Wrap text in an interactive card with a markdown element."""
    card = {
        "elements": [
            {"tag": "markdown", "content": text},
        ],
    }
    return json.dumps(card)


# ============================================================================
# Event parsing (pure function, no side effects)
# ============================================================================


def parse_event(data: P2ImMessageReceiveV1) -> FeishuEvent | None:
    """Convert raw Feishu event to FeishuEvent. Returns None if not actionable."""
    event = data.event
    if not event or not event.message or not event.sender:
        return None

    msg = event.message

    # Only handle text messages for now
    if msg.message_type != "text":
        return None

    # Extract sender open_id
    sender_id = ""
    if event.sender.sender_id:
        sender_id = event.sender.sender_id.open_id or ""

    # Skip if no sender (system messages)
    if not sender_id:
        return None

    # Parse content JSON: {"text": "@_user_1 hello"}
    text = _extract_text(msg.content, msg.mentions)

    # Determine event type
    chat_type = msg.chat_type or "p2p"
    if chat_type == "p2p":
        event_type = EventType.DM
    else:
        event_type = EventType.MENTION

    return FeishuEvent(
        event_type=event_type,
        message_id=msg.message_id or "",
        chat_id=msg.chat_id or "",
        chat_type=chat_type,
        sender_id=sender_id,
        text=text,
        create_time=str(msg.create_time or ""),
    )


def _extract_text(content: str | None, mentions: list | None) -> str:
    """Extract plain text from Feishu content JSON, stripping @mentions."""
    if not content:
        return ""
    try:
        text = json.loads(content).get("text", "")
    except (json.JSONDecodeError, AttributeError):
        return ""

    # Strip mention placeholders like @_user_1
    if mentions:
        for m in mentions:
            key = getattr(m, "key", None)
            if key:
                text = text.replace(key, "")

    return text.strip()


# ============================================================================
# FeishuBot
# ============================================================================


class FeishuBot:
    """Receives events from Feishu WebSocket, sends messages via REST."""

    def __init__(
        self,
        config: BotConfig,
        on_event: Callable[[FeishuEvent], None],
    ) -> None:
        self._config = config
        self._on_event = on_event

        # REST client for sending messages
        self._client = (
            lark.Client.builder()
            .app_id(config.app_id)
            .app_secret(config.app_secret)
            .domain(config.feishu_domain)
            .build()
        )

        # Event handler
        handler = (
            lark.EventDispatcherHandler.builder(
                config.encrypt_key, config.verification_token
            )
            .register_p2_im_message_receive_v1(self._handle_message)
            .register_p2_im_message_message_read_v1(lambda _: None)
            .register_p2_im_chat_access_event_bot_p2p_chat_entered_v1(lambda _: None)
            .build()
        )

        # WebSocket client for receiving events
        self._ws_client = lark.ws.Client(
            config.app_id,
            config.app_secret,
            event_handler=handler,
            domain=config.feishu_domain,
        )

    def start(self) -> None:
        """Blocking. Connects WebSocket, receives events forever."""
        log.connected()
        self._ws_client.start()

    # ========================================================================
    # Send messages (REST API) — all replies use interactive cards
    # ========================================================================

    def send_message(
        self, receive_id: str, text: str, id_type: str = "chat_id"
    ) -> str | None:
        """Send an interactive card. id_type: 'chat_id' or 'open_id' (for DM)."""
        body = (
            CreateMessageRequestBody.builder()
            .receive_id(receive_id)
            .msg_type("interactive")
            .content(_card_content(text))
            .build()
        )
        request = (
            CreateMessageRequest.builder()
            .receive_id_type(id_type)
            .request_body(body)
            .build()
        )
        resp = self._client.im.v1.message.create(request)
        if not resp.success():
            log.warning("send_message failed", f"code={resp.code} msg={resp.msg}")
            return None
        return resp.data.message_id if resp.data else None

    def reply_message(self, message_id: str, text: str) -> str | None:
        """Reply to a message with an interactive card. Returns new message_id or None."""
        body = (
            ReplyMessageRequestBody.builder()
            .msg_type("interactive")
            .content(_card_content(text))
            .build()
        )
        request = (
            ReplyMessageRequest.builder()
            .message_id(message_id)
            .request_body(body)
            .build()
        )
        resp = self._client.im.v1.message.reply(request)
        if not resp.success():
            log.warning("reply_message failed", f"code={resp.code} msg={resp.msg}")
            return None
        return resp.data.message_id if resp.data else None

    def update_message(self, message_id: str, text: str) -> bool:
        """Update an existing card message. Returns True on success."""
        body = (
            PatchMessageRequestBody.builder()
            .content(_card_content(text))
            .build()
        )
        request = (
            PatchMessageRequest.builder()
            .message_id(message_id)
            .request_body(body)
            .build()
        )
        resp = self._client.im.v1.message.patch(request)
        if not resp.success():
            log.warning("update_message failed", f"code={resp.code} msg={resp.msg}")
            return False
        return True

    # ========================================================================
    # Event handler (called synchronously by lark_oapi WS client)
    # ========================================================================

    def _handle_message(self, data: P2ImMessageReceiveV1) -> None:
        """Parse incoming event and dispatch to handler."""
        event = parse_event(data)
        if event is None:
            return

        log.event_received(event.chat_id, event.sender_id, event.text)
        self._on_event(event)
