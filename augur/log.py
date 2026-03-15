"""Structured console logging. No noise — only meaningful events."""

import sys
from datetime import datetime, timezone

from .types import BotConfig


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def info(msg: str) -> None:
    print(f"[{_ts()}] {msg}", file=sys.stderr)


def warning(msg: str, detail: str = "") -> None:
    suffix = f": {detail}" if detail else ""
    print(f"[{_ts()}] WARN {msg}{suffix}", file=sys.stderr)


def error(msg: str, detail: str = "") -> None:
    suffix = f": {detail}" if detail else ""
    print(f"[{_ts()}] ERROR {msg}{suffix}", file=sys.stderr)


def startup(config: BotConfig) -> None:
    info(f"augur starting  auth={config.auth_mode.name}  model={config.model}")
    info(f"  data_dir={config.working_dir}")


def connected() -> None:
    info("connected to Feishu WebSocket")


def event_received(chat_id: str, sender: str, text: str) -> None:
    preview = text[:60].replace("\n", " ")
    info(f"[{chat_id}] <{sender}> {preview}")
