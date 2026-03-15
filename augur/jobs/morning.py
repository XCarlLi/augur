"""Morning digest: calendar + tasks summary, sent to configured chat.

Uses Feishu CLI to fetch calendar events and tasks, then sends a digest.
Also polls for 30-minute upcoming event alerts.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from .. import log
from ..memory import resolve_active_soul
from ..autonomous import AutonomousConfig, run_session
from ..types import BotConfig, UserInfo


_FEISHU_CLI = [sys.executable, "-m", "augur.cli.feishu_cli"]


def _run_cli(*args: str) -> str | None:
    """Run feishu_cli command and return stdout, or None on failure."""
    try:
        result = subprocess.run(
            [*_FEISHU_CLI, *args],
            capture_output=True, text=True, timeout=30,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception as e:
        log.warning("feishu_cli failed", str(e))
        return None


def _fetch_today_calendar(tz: ZoneInfo) -> str:
    """Fetch today's calendar events via Feishu CLI."""
    today = datetime.now(tz)
    start = today.strftime("%Y-%m-%d")
    end = (today + timedelta(days=1)).strftime("%Y-%m-%d")
    output = _run_cli("list-calendar", "--start", start, "--end", end)
    return output or "(无日历事件)"


def _fetch_tasks() -> str:
    """Fetch pending tasks via Feishu CLI."""
    output = _run_cli("list-tasks")
    return output or "(无待办任务)"


def _build_system_prompt(user: UserInfo, soul_content: str) -> str:
    identity = f"## 你是谁\n\n{soul_content}" if soul_content else "## 你是谁\n\n你是晨间摘要助手。"

    return f"""你要生成一份简洁的晨间摘要。

{identity}

## 输出规则
- 始终用中文
- 输出在飞书上，使用 Markdown 格式
- 简洁明了，不废话
- 包含今日日程和待办任务
- 遵循 soul 中的性格设定来调整语气"""


def _build_query_prompt(calendar: str, tasks: str, now: datetime) -> str:
    weekday_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][now.weekday()]

    return f"""现在是{now.strftime('%Y年%m月%d日')}（{weekday_cn}）早上。

## 今日日程
{calendar}

## 待办任务
{tasks}

根据以上信息，生成一份晨间摘要。语气遵循性格设定。
如果没有任何事项，就简短问个好。"""


async def run_morning(
    user: UserInfo,
    config: BotConfig,
    tz: ZoneInfo,
) -> str | None:
    """Generate morning digest. Returns message text to send."""
    now = datetime.now(tz)
    log.info(f"morning digest starting for {user.sender_id}")

    calendar = _fetch_today_calendar(tz)
    tasks = _fetch_tasks()

    # If nothing at all, skip the agent and return a simple greeting
    if calendar == "(无日历事件)" and tasks == "(无待办任务)":
        soul_content = resolve_active_soul(user.user_dir)
        if not soul_content:
            return None  # No soul, nothing to say
        # Still run agent so soul personality shows through
        pass

    soul_content = resolve_active_soul(user.user_dir)

    session_config = AutonomousConfig(
        name="morning-digest",
        system_prompt=_build_system_prompt(user, soul_content),
        query_prompt=_build_query_prompt(calendar, tasks, now),
        cwd=str(Path(config.working_dir).resolve()),
        max_turns=5,
        model=config.model,
        allowed_write_prefixes=[],  # Read-only session
    )

    result = await run_session(session_config)

    if result.text:
        log.info(f"morning digest generated: {result.text[:100]}")
    else:
        log.info("morning digest: no output")

    return result.text


async def check_upcoming_alerts(
    user: UserInfo,
    config: BotConfig,
    tz: ZoneInfo,
) -> str | None:
    """Check for events starting within 30 minutes. Pure code, no agent.

    Returns alert text or None.
    """
    now = datetime.now(tz)
    start = now.strftime("%Y-%m-%d")
    end = (now + timedelta(days=1)).strftime("%Y-%m-%d")

    output = _run_cli("list-calendar", "--start", start, "--end", end)
    if not output:
        return None

    # Parse calendar output — look for events in the next 30 minutes
    # Calendar output format depends on feishu_cli implementation
    # This is a simplified check — real implementation would parse structured data
    alerts = []
    try:
        events = json.loads(output) if output.startswith("[") else []
    except (json.JSONDecodeError, TypeError):
        return None

    for event in events:
        start_time_str = event.get("start_time", "")
        summary = event.get("summary", "")
        if not start_time_str or not summary:
            continue
        try:
            event_time = datetime.fromisoformat(start_time_str).replace(tzinfo=tz)
            delta = (event_time - now).total_seconds()
            if 0 < delta <= 1800:  # Within 30 minutes
                minutes = max(1, int(delta / 60))
                alerts.append(f"「{summary}」还有 {minutes} 分钟")
        except (ValueError, TypeError):
            continue

    if not alerts:
        return None

    return "提醒：\n" + "\n".join(f"- {a}" for a in alerts)
