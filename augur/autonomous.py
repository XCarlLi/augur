"""Restricted autonomous Claude session runner for scheduled agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
    AssistantMessage,
    ResultMessage,
    TextBlock,
)
from claude_agent_sdk.types import PermissionResultAllow, PermissionResultDeny

from . import log

SILENT_MARKERS = frozenset({"[SILENT]", "[NO_OUTPUT]"})

CODE_EXTENSIONS = frozenset({
    ".py", ".js", ".ts", ".sh", ".bash", ".zsh", ".jsx", ".tsx",
    ".go", ".rs", ".java", ".c", ".cpp", ".h", ".hpp",
})

BLOCKED_COMMANDS = [
    "git commit", "git push", "git reset", "git rebase",
    "npm", "pip", "rm -rf", "sudo", "pkill", "killall",
]


@dataclass
class AutonomousConfig:
    """All configuration for one autonomous session."""

    name: str
    system_prompt: str
    query_prompt: str
    cwd: str
    max_turns: int = 10
    model: str | None = None
    allowed_write_prefixes: list[str] = field(default_factory=list)
    blocked_commands: list[str] = field(default_factory=lambda: list(BLOCKED_COMMANDS))
    blocked_extensions: frozenset[str] = field(default_factory=lambda: CODE_EXTENSIONS)


@dataclass
class SessionResult:
    """Result from an autonomous session."""

    text: str | None = None
    session_id: str | None = None


def _create_restricted_callback(config: AutonomousConfig):
    """Build permission callback that restricts writes and commands."""
    prefixes = config.allowed_write_prefixes
    blocked = config.blocked_commands
    blocked_ext = config.blocked_extensions

    async def can_use_tool(tool_name, input_data, context):
        if tool_name in {"Write", "Edit", "NotebookEdit"}:
            file_path = input_data.get("file_path") or input_data.get("notebook_path", "")
            if file_path:
                resolved = str(Path(file_path).resolve())
                if Path(file_path).suffix in blocked_ext:
                    return PermissionResultDeny(
                        message=f"{config.name} cannot modify code files: {file_path}",
                    )
                if prefixes and not any(resolved.startswith(p) for p in prefixes):
                    return PermissionResultDeny(
                        message=f"{config.name} can only write to allowed paths",
                    )
            return PermissionResultAllow(updated_input=input_data)

        if tool_name == "Bash":
            command = input_data.get("command", "")
            for b in blocked:
                if b in command:
                    return PermissionResultDeny(
                        message=f"{config.name} cannot run: {b}",
                    )
            return PermissionResultAllow(updated_input=input_data)

        return PermissionResultAllow(updated_input=input_data)

    return can_use_tool


async def run_session(config: AutonomousConfig) -> SessionResult:
    """Run one autonomous session. Returns SessionResult with text and session_id."""
    permission_cb = _create_restricted_callback(config)

    options = ClaudeAgentOptions(
        system_prompt=config.system_prompt,
        cwd=config.cwd,
        permission_mode="acceptEdits",
        max_turns=config.max_turns,
        model=config.model,
        can_use_tool=permission_cb,
    )

    try:
        async with ClaudeSDKClient(options) as client:
            await client.connect()
            await client.query(config.query_prompt)

            accumulated = ""
            session_id = None
            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            accumulated += block.text
                elif isinstance(message, ResultMessage):
                    session_id = message.session_id

            if not accumulated:
                log.info(f"[{config.name}] empty response")
                return SessionResult(session_id=session_id)

            text = accumulated.strip()
            if any(marker in text for marker in SILENT_MARKERS):
                log.info(f"[{config.name}] silent")
                return SessionResult(session_id=session_id)

            log.info(f"[{config.name}] output: {text[:200]}")
            return SessionResult(text=text, session_id=session_id)

    except Exception as e:
        log.error(f"[{config.name}] session failed", str(e))
        return SessionResult()
