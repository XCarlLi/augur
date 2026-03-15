"""Per-user runtime settings. Persisted to users/{sender_id}/settings.json.

Mutable at runtime via chat commands, checked by scheduler before running jobs.
"""

from __future__ import annotations

import json
from pathlib import Path

_DEFAULTS = {
    "exploration_enabled": True,
    "journal_enabled": True,
    "morning_enabled": True,
}


def _settings_path(user_dir: Path) -> Path:
    return user_dir / "settings.json"


def load(user_dir: Path) -> dict:
    """Load settings, filling in defaults for missing keys."""
    path = _settings_path(user_dir)
    if not path.exists():
        return dict(_DEFAULTS)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {**_DEFAULTS, **data}
    except (json.JSONDecodeError, OSError):
        return dict(_DEFAULTS)


def save(user_dir: Path, settings: dict) -> None:
    """Persist settings to disk."""
    path = _settings_path(user_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")


def toggle(user_dir: Path, key: str, value: bool | None = None) -> bool:
    """Toggle a setting. Returns the new value. If value is None, flips current."""
    s = load(user_dir)
    if key not in _DEFAULTS:
        raise KeyError(f"Unknown setting: {key}")
    s[key] = (not s[key]) if value is None else value
    save(user_dir, s)
    return s[key]
