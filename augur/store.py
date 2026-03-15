"""File storage: per-chat logs, per-user memory, directory layout."""

import json
from dataclasses import asdict
from pathlib import Path

from .types import LogEntry


class ChatStore:
    """Manages data directory layout and log persistence."""

    def __init__(self, working_dir: str) -> None:
        self._root = Path(working_dir)
        self._root.mkdir(parents=True, exist_ok=True)

    def chats_dir(self) -> Path:
        d = self._root / "chats"
        d.mkdir(exist_ok=True)
        return d

    def chat_dir(self, chat_id: str) -> Path:
        d = self._root / "chats" / chat_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def scratch_dir(self, chat_id: str) -> Path:
        d = self.chat_dir(chat_id) / "scratch"
        d.mkdir(exist_ok=True)
        return d

    def user_dir(self, sender_id: str) -> Path:
        d = self._root / "users" / sender_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def templates_dir(self) -> Path:
        return self._root / "templates"

    def log_message(self, chat_id: str, entry: LogEntry) -> None:
        log_path = self.chat_dir(chat_id) / "log.jsonl"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")

    def get_recent_log(self, chat_id: str, n: int = 20) -> str:
        """Return last n log entries as text for context."""
        log_path = self.chat_dir(chat_id) / "log.jsonl"
        if not log_path.exists():
            return "(no history)"
        lines = log_path.read_text(encoding="utf-8").strip().split("\n")
        recent = lines[-n:]
        parts = []
        for line in recent:
            try:
                entry = json.loads(line)
                role = "bot" if entry.get("is_bot") else "user"
                parts.append(f"[{role}] {entry.get('text', '')}")
            except json.JSONDecodeError:
                continue
        return "\n".join(parts) if parts else "(no history)"

    def get_all_logs_for_date(self, date_str: str) -> dict[str, list[dict]]:
        """Return {chat_id: [entries]} for all chats with entries on given date."""
        result: dict[str, list[dict]] = {}
        chats = self._root / "chats"
        if not chats.exists():
            return result
        for chat_dir in chats.iterdir():
            log_path = chat_dir / "log.jsonl"
            if not log_path.exists():
                continue
            entries = []
            for line in log_path.read_text(encoding="utf-8").strip().split("\n"):
                try:
                    entry = json.loads(line)
                    if date_str in entry.get("date", ""):
                        entries.append(entry)
                except json.JSONDecodeError:
                    continue
            if entries:
                result[chat_dir.name] = entries
        return result
