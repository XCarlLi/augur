"""All data structures. Designed first, logic follows."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from claude_agent_sdk import ClaudeSDKClient


class AuthMode(Enum):
    OAUTH = auto()
    API_KEY = auto()


class EventType(Enum):
    MENTION = auto()
    DM = auto()


@dataclass(frozen=True)
class UserInfo:
    """Resolved user identity. sender_id is Feishu open_id."""

    sender_id: str
    name: str
    user_dir: Path
    active_soul: str  # e.g. "balanced.md"


@dataclass(frozen=True)
class ScheduleConfig:
    """Schedule for autonomous agents."""

    timezone: str = "Asia/Shanghai"
    morning_hour: int = 8
    morning_chat_id: str = ""
    exploration_hours: tuple[int, ...] = (9, 12, 18)
    journal_enabled: bool = True
    exploration_enabled: bool = True
    morning_enabled: bool = True


@dataclass(frozen=True)
class BotConfig:
    """Immutable bot configuration. Constructed once at startup."""

    app_id: str
    app_secret: str
    auth_mode: AuthMode
    anthropic_api_key: str | None
    working_dir: str
    encrypt_key: str = ""
    verification_token: str = ""
    feishu_domain: str = "https://open.feishu.cn"
    model: str = "claude-sonnet-4-5"
    schedule: ScheduleConfig = field(default_factory=ScheduleConfig)
    users: dict[str, dict] = field(default_factory=dict)  # sender_id -> {name, default_soul}


@dataclass(frozen=True)
class FeishuEvent:
    """Normalized incoming event. Boundary type between Feishu and internal logic."""

    event_type: EventType
    message_id: str
    chat_id: str
    chat_type: str  # "group" | "p2p"
    sender_id: str
    text: str
    create_time: str


@dataclass
class ChatState:
    """Mutable per-chat runtime state."""

    chat_id: str
    running: bool = False
    session_id: str | None = None
    stop_requested: bool = False
    client: ClaudeSDKClient | None = None


@dataclass(frozen=True)
class LogEntry:
    """A single line in log.jsonl."""

    date: str
    message_id: str
    sender_id: str
    text: str
    is_bot: bool
