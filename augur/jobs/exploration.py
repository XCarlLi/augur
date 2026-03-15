"""Autonomous exploration: three daily sessions for reading, thinking, sharing.

Sessions: 09:00 morning deep-read, 12:00 midday news, 18:00 evening free-form.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from .. import log
from ..autonomous import AutonomousConfig, run_session
from ..memory import resolve_active_soul
from ..store import ChatStore
from ..types import BotConfig, UserInfo

SESSIONS = {
    9: ("晨读", "morning"),
    12: ("午间", "midday"),
    18: ("傍晚", "evening"),
}

_SESSION_GUIDANCE = {
    "morning": "这是晨读时间。适合沉下心读些有深度的东西。\n不求多，一篇足矣，但要真正读进去。读完写下你自己的理解和疑问。",
    "midday": "这是午间时间。看看世上发生了什么值得关注的事。\n不做传声筒——背后的逻辑是什么、哪些是事实哪些是立场、放在更大框架里意味什么，想清楚了再说。",
    "evening": "这是傍晚时间。自由些。\n可以接着之前没想完的问题继续琢磨，可以找些杂学旁收的趣事，可以只是写几句随感。\n像散步一样，走到哪算哪。",
}


def _exploration_dir(user_dir: Path) -> Path:
    d = user_dir / "journal" / "exploration"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load_recent_notes(user_dir: Path, today: str, max_days: int = 3) -> str:
    """Load recent exploration notes for context continuity."""
    exp_dir = _exploration_dir(user_dir)
    notes = []

    today_file = exp_dir / f"{today}.md"
    if today_file.exists():
        content = today_file.read_text(encoding="utf-8").strip()
        if content:
            notes.append(f"【今日已有的探索笔记】\n{content}")

    today_date = datetime.strptime(today, "%Y-%m-%d").date()
    for i in range(1, max_days + 1):
        d = today_date - timedelta(days=i)
        f = exp_dir / f"{d.isoformat()}.md"
        if f.exists():
            content = f.read_text(encoding="utf-8").strip()
            if content:
                lines = content.split("\n")
                hints = [ln for ln in lines if "下次想看" in ln or "方向" in ln]
                if hints:
                    notes.append(f"【{d.isoformat()} 的探索线索】\n" + "\n".join(hints))

    return "\n\n".join(notes) if notes else ""


def _load_recent_diary(user_dir: Path, max_lines: int = 40) -> str:
    """Load the most recent diary entry for context."""
    diary_dir = user_dir / "journal" / "diary"
    if not diary_dir.exists():
        return ""

    diary_files = sorted(diary_dir.glob("*.md"), reverse=True)
    if not diary_files:
        return ""

    content = diary_files[0].read_text(encoding="utf-8").strip()
    lines = content.split("\n")[:max_lines]
    return f"【最近日记 {diary_files[0].stem}】\n" + "\n".join(lines)


def _build_exploration_directions(user_dir: Path) -> str:
    """Build directions from user profile/insights, or use generic defaults."""
    profile = user_dir / "identity" / "profile.md"
    insights = user_dir / "knowledge" / "insights.md"

    has_context = (profile.exists() and profile.stat().st_size > 50) or \
                  (insights.exists() and insights.stat().st_size > 50)

    if has_context:
        return (
            "## 探索方向参考（每次只挑一个）\n"
            "- 读 identity/profile.md 和 knowledge/insights.md 了解用户兴趣\n"
            "- 跟最近对话话题相关的延伸\n"
            "- 任何你自己觉得有意思的东西"
        )
    return (
        "## 探索方向参考（每次只挑一个）\n"
        "- 有深度的技术动态（AI、系统设计、工程哲学）\n"
        "- 文学与诗词、历史中有趣的人和事\n"
        "- 任何你自己觉得有意思的东西"
    )


def _build_system_prompt(user: UserInfo, data_root: Path, soul_content: str) -> str:
    resolved = str(data_root.resolve())

    identity = f"## 你是谁\n\n{soul_content}" if soul_content else "## 你是谁\n\n你是自主探索助手。"

    return f"""这是你的自主探索时间——没有人找你说话，你在自己读书、思考、探索世界。

{identity}

## Working Directory
{resolved}

## 可访问的文件
- 探索笔记：{resolved}/users/{user.sender_id}/journal/exploration/（读写）
- 用户记忆：{resolved}/users/{user.sender_id}/（读）

## 限制
- 禁止修改代码文件
- 禁止运行 git/npm/pip/sudo/pkill 等命令
- 可以使用 WebSearch 和 WebFetch 查信息

## 输出规则
- 始终用中文
- 把笔记追加写入今天的探索文件
- 发现值得分享的 → 输出一条简短消息
- 没什么特别好的 → 回复 [SILENT]
- 不要解释决策过程"""


def _build_query_prompt(
    user: UserInfo,
    now: datetime,
    session_label: str,
    recent_notes: str,
    recent_diary: str,
) -> str:
    weekday_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][now.weekday()]
    today_str = now.strftime("%Y-%m-%d")
    exp_path = f"users/{user.sender_id}/journal/exploration/{today_str}.md"

    guidance = _SESSION_GUIDANCE.get(session_label, "自由探索。")

    context_parts = []
    if recent_notes:
        context_parts.append(recent_notes)
    if recent_diary:
        context_parts.append(recent_diary)
    context_block = "\n\n".join(context_parts) if context_parts else "（还没有探索记录，自由选择一个方向开始。）"

    directions = _build_exploration_directions(user.user_dir)

    return f"""现在是{now.strftime('%Y年%m月%d日')}（{weekday_cn}）{now.strftime('%H:%M')}。

{guidance}

{context_block}

{directions}

用 WebSearch 和 WebFetch 探索，把笔记写入 `{exp_path}`。
发现值得分享的 → 输出整理好的消息。没什么好的 → 回复 [SILENT]。"""


async def run_exploration(
    user: UserInfo,
    config: BotConfig,
    store: ChatStore,
    now: datetime,
) -> str | None:
    """Run exploration session. Returns message text to send, or None if silent."""
    hour = now.hour
    _, session_label = SESSIONS.get(hour, ("自由", "evening"))
    today_str = now.strftime("%Y-%m-%d")

    log.info(f"exploration [{session_label}] starting for {user.sender_id}")

    soul_content = resolve_active_soul(user.user_dir)
    recent_notes = _load_recent_notes(user.user_dir, today_str)
    recent_diary = _load_recent_diary(user.user_dir)

    _exploration_dir(user.user_dir)

    data_root = store._root
    resolved = str(data_root.resolve())

    session_config = AutonomousConfig(
        name=f"exploration-{session_label}",
        system_prompt=_build_system_prompt(user, data_root, soul_content),
        query_prompt=_build_query_prompt(user, now, session_label, recent_notes, recent_diary),
        cwd=resolved,
        max_turns=10,
        model=config.model,
        allowed_write_prefixes=[
            str((data_root / "users" / user.sender_id).resolve()) + "/",
        ],
    )

    result = await run_session(session_config)

    if result.text:
        log.info(f"exploration [{session_label}] output: {result.text[:200]}")
    else:
        log.info(f"exploration [{session_label}] silent")

    return result.text
