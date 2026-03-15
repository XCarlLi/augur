"""Entry point: wire modules, start the bot."""

import asyncio
import atexit
import signal
import sys
import threading
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from .agent import AgentManager
from .config import load_config
from .feishu import FeishuBot
from .scheduler import JobSpec, Scheduler
from .store import ChatStore
from .types import FeishuEvent, LogEntry
from .user import ensure_initialized, resolve_user
from . import log, settings

# Chat commands: keyword -> (setting_key, on_value)
_COMMANDS = {
    "开启探索": ("exploration_enabled", True),
    "关闭探索": ("exploration_enabled", False),
    "开启日记": ("journal_enabled", True),
    "关闭日记": ("journal_enabled", False),
    "开启晨报": ("morning_enabled", True),
    "关闭晨报": ("morning_enabled", False),
}

_STATUS_LABELS = {
    "exploration_enabled": "自主探索",
    "journal_enabled": "夜间日记",
    "morning_enabled": "晨间摘要",
}


def _handle_command(text: str, user_dir) -> str | None:
    """Try to match a settings command. Returns reply text or None."""
    stripped = text.strip()

    # Toggle command
    if stripped in _COMMANDS:
        key, value = _COMMANDS[stripped]
        new_val = settings.toggle(user_dir, key, value)
        label = _STATUS_LABELS.get(key, key)
        state = "已开启" if new_val else "已关闭"
        return f"{label}: {state}"

    # Status query
    if stripped in ("状态", "设置", "settings"):
        s = settings.load(user_dir)
        lines = []
        for key, label in _STATUS_LABELS.items():
            state = "开启" if s.get(key, True) else "关闭"
            lines.append(f"- {label}: {state}")
        return "当前设置:\n" + "\n".join(lines)

    return None


def main() -> None:
    config = load_config()
    store = ChatStore(config.working_dir)

    # Persistent event loop for all agent tasks
    agent_loop = asyncio.new_event_loop()
    agent_thread = threading.Thread(
        target=agent_loop.run_forever, daemon=True, name="agent-loop"
    )
    agent_thread.start()

    def respond(chat_id: str, text: str, reply_to: str | None = None) -> str | None:
        if reply_to:
            mid = bot.reply_message(reply_to, text)
        else:
            mid = bot.send_message(chat_id, text)

        store.log_message(chat_id, LogEntry(
            date=datetime.now(timezone.utc).isoformat(),
            message_id="",
            sender_id="bot",
            text=text,
            is_bot=True,
        ))
        return mid

    def update(message_id: str, text: str) -> bool:
        return bot.update_message(message_id, text)

    agent_mgr = AgentManager(config, store, respond, update)

    def on_event(event: FeishuEvent) -> None:
        # Resolve and initialize user on first contact
        user = resolve_user(event.sender_id, config, store._root)
        ensure_initialized(user, store.templates_dir())

        store.log_message(event.chat_id, LogEntry(
            date=datetime.now(timezone.utc).isoformat(),
            message_id=event.message_id,
            sender_id=event.sender_id,
            text=event.text,
            is_bot=False,
        ))

        # Check for settings commands first
        reply = _handle_command(event.text, user.user_dir)
        if reply:
            respond(event.chat_id, reply, event.message_id)
            return

        if event.text.lower().strip() == "stop":
            if agent_mgr.is_running(event.chat_id):
                agent_mgr.abort(event.chat_id)
                respond(event.chat_id, "Stopping...", event.message_id)
            else:
                respond(event.chat_id, "Nothing running.", event.message_id)
            return

        if agent_mgr.is_running(event.chat_id):
            respond(event.chat_id, "Already working. Say 'stop' to cancel.", event.message_id)
            return

        asyncio.run_coroutine_threadsafe(agent_mgr.run(event), agent_loop)

    bot = FeishuBot(config, on_event=on_event)

    def send_dm(open_id: str, text: str) -> str | None:
        """Send DM to user via open_id."""
        return bot.send_message(open_id, text, id_type="open_id")

    # Setup scheduler for autonomous agents
    scheduler = _setup_scheduler(config, store, agent_loop, respond, send_dm)

    def _shutdown():
        scheduler.cancel_all()
        future = asyncio.run_coroutine_threadsafe(agent_mgr.shutdown(), agent_loop)
        future.result(timeout=5)
        agent_loop.call_soon_threadsafe(agent_loop.stop)

    atexit.register(_shutdown)
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    log.startup(config)
    bot.start()  # blocking


def _setup_scheduler(config, store, loop, respond, send_dm) -> Scheduler:
    """Create scheduler and register all autonomous jobs."""
    sched_cfg = config.schedule
    scheduler = Scheduler(loop, sched_cfg.timezone)
    tz = ZoneInfo(sched_cfg.timezone)

    if not config.users:
        log.info("no users configured, skipping autonomous jobs")
        return scheduler

    first_sender_id = next(iter(config.users))

    def _get_first_user():
        from .user import resolve_user
        return resolve_user(first_sender_id, config, store._root)

    def _send(text: str) -> None:
        """Send autonomous message: to morning_chat_id if set, else DM the user."""
        if sched_cfg.morning_chat_id:
            respond(sched_cfg.morning_chat_id, text)
        else:
            send_dm(first_sender_id, text)

    def _is_enabled(key: str) -> bool:
        """Check per-user runtime setting (settings.json overrides config.toml)."""
        user = _get_first_user()
        s = settings.load(user.user_dir)
        return s.get(key, True)

    # Morning digest
    async def morning_job():
        if not _is_enabled("morning_enabled"):
            return
        from .jobs.morning import run_morning
        user = _get_first_user()
        text = await run_morning(user, config, tz)
        if text:
            _send(text)

    scheduler.add(JobSpec("morning-digest", sched_cfg.morning_hour, 0, morning_job))

    # Exploration sessions
    for hour in sched_cfg.exploration_hours:
        async def exploration_job(h=hour):
            if not _is_enabled("exploration_enabled"):
                return
            from .jobs.exploration import run_exploration
            user = _get_first_user()
            text = await run_exploration(user, config, store, datetime.now(tz))
            if text:
                _send(text)

        scheduler.add(JobSpec(f"exploration-{hour:02d}", hour, 0, exploration_job))

    # Nightly journal (00:05)
    async def journal_job():
        if not _is_enabled("journal_enabled"):
            return
        from .jobs.journal import run_journal
        user = _get_first_user()
        yesterday = datetime.now(tz) - timedelta(days=1)
        await run_journal(user, config, store, yesterday)

    scheduler.add(JobSpec("journal", 0, 5, journal_job))

    # Monthly summary (1st of month at 03:00)
    async def monthly_summary_job():
        now = datetime.now(tz)
        if now.day != 1:
            return
        last_month = (now.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
        user = _get_first_user()
        from .jobs.summary import run_monthly_summary
        await run_monthly_summary(user, config, store, last_month)

    scheduler.add(JobSpec("monthly-summary", 3, 0, monthly_summary_job))

    # 30-minute upcoming alert check (every 5 minutes)
    async def alert_job():
        if not _is_enabled("morning_enabled"):
            return
        from .jobs.morning import check_upcoming_alerts
        user = _get_first_user()
        text = await check_upcoming_alerts(user, config, tz)
        if text:
            _send(text)

    scheduler.add_repeating("upcoming-alerts", 300, alert_job)

    return scheduler


if __name__ == "__main__":
    main()
