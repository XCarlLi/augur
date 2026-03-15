"""User resolution and initialization. Auto-creates memory structure on first contact."""

from __future__ import annotations

import shutil
from pathlib import Path

from . import log
from .types import BotConfig, UserInfo

DEFAULT_TEMPLATE = "balanced"


def resolve_user(sender_id: str, config: BotConfig, data_root: Path) -> UserInfo:
    """Resolve sender_id to UserInfo. Reads config for known users, falls back to defaults."""
    user_cfg = config.users.get(sender_id, {})
    name = user_cfg.get("name", sender_id[:8])
    default_soul = user_cfg.get("default_soul", DEFAULT_TEMPLATE)

    user_dir = data_root / "users" / sender_id
    active_soul = get_active_soul(user_dir) or f"{default_soul}.md"

    return UserInfo(
        sender_id=sender_id,
        name=name,
        user_dir=user_dir,
        active_soul=active_soul,
    )


def ensure_initialized(user_info: UserInfo, templates_dir: Path) -> None:
    """Initialize user directory structure on first contact. Idempotent."""
    marker = user_info.user_dir / "identity" / "soul.md"
    if marker.exists():
        return

    user_dir = user_info.user_dir
    _create_dirs(user_dir)
    _copy_soul_template(user_info, templates_dir)
    _create_default_profile(user_info)
    _create_empty_insights(user_dir / "knowledge")
    _create_default_proactive_rules(user_dir / "identity" / "rules")
    _setup_souls(user_info, templates_dir)

    log.info(f"initialized user {user_info.sender_id} ({user_info.name})")


def get_active_soul(user_dir: Path) -> str | None:
    """Read souls/active.txt. Returns filename like 'balanced.md', or None."""
    active_file = user_dir / "souls" / "active.txt"
    if not active_file.exists():
        return None
    return active_file.read_text(encoding="utf-8").strip() or None


def set_active_soul(user_dir: Path, soul_name: str) -> None:
    """Write soul filename to souls/active.txt."""
    souls_dir = user_dir / "souls"
    souls_dir.mkdir(parents=True, exist_ok=True)

    # Validate soul file exists
    soul_file = souls_dir / soul_name
    if not soul_file.exists():
        raise FileNotFoundError(f"Soul template not found: {soul_file}")

    active_file = souls_dir / "active.txt"
    active_file.write_text(soul_name, encoding="utf-8")


def _create_dirs(user_dir: Path) -> None:
    """Create the full user directory tree."""
    for subdir in (
        "identity/rules",
        "knowledge/topics",
        "knowledge/summaries",
        "journal/diary",
        "journal/exploration",
        "souls",
        "archive/transcripts",
    ):
        (user_dir / subdir).mkdir(parents=True, exist_ok=True)


def _copy_soul_template(user_info: UserInfo, templates_dir: Path) -> None:
    """Copy default soul template to identity/soul.md."""
    # Derive template name from active_soul (e.g. "balanced.md" -> "balanced")
    template_name = user_info.active_soul.removesuffix(".md")
    template_path = templates_dir / "souls" / f"{template_name}.md"
    if not template_path.exists():
        template_path = templates_dir / "souls" / "balanced.md"

    target = user_info.user_dir / "identity" / "soul.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(template_path, target)


def _create_default_profile(user_info: UserInfo) -> None:
    """Create default profile.md."""
    content = f"""# User Profile

- Name: {user_info.name}
- ID: {user_info.sender_id}
- Soul: {user_info.active_soul}

（初始配置，可由用户自定义）
"""
    path = user_info.user_dir / "identity" / "profile.md"
    path.write_text(content, encoding="utf-8")


def _create_empty_insights(knowledge_dir: Path) -> None:
    """Create initial insights.md."""
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    content = "# 关于用户的认知\n\n（待积累）\n"
    (knowledge_dir / "insights.md").write_text(content, encoding="utf-8")


def _create_default_proactive_rules(rules_dir: Path) -> None:
    """Create default proactive rules."""
    rules_dir.mkdir(parents=True, exist_ok=True)
    content = """# 主动性规则

## 何时主动
- deadline前提醒重要事项
- 任务冲突时提示
- 明确的异常情况

## 何时不主动
- 不主动闲聊
- 不在非必要时打扰
- 不刷存在感
"""
    (rules_dir / "proactive.md").write_text(content, encoding="utf-8")


def _setup_souls(user_info: UserInfo, templates_dir: Path) -> None:
    """Copy all soul templates to user's souls/ dir and set active."""
    souls_src = templates_dir / "souls"
    souls_dst = user_info.user_dir / "souls"
    souls_dst.mkdir(parents=True, exist_ok=True)

    if souls_src.is_dir():
        for template in souls_src.glob("*.md"):
            shutil.copy(template, souls_dst / template.name)

    # Set active soul
    active_file = souls_dst / "active.txt"
    active_file.write_text(user_info.active_soul, encoding="utf-8")
