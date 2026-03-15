"""Load configuration: config.toml → env vars override → validate."""

import os
import tomllib
from pathlib import Path

from .types import AuthMode, BotConfig, ScheduleConfig

_DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config.toml"


def load_config(config_path: str | None = None) -> BotConfig:
    """Load config from TOML file, then let env vars override. Fail fast."""
    file_cfg = _load_toml(config_path or str(_DEFAULT_CONFIG))

    app_id = _get("AUGUR_APP_ID", file_cfg, ("feishu", "app_id"), required=True)
    app_secret = _get("AUGUR_APP_SECRET", file_cfg, ("feishu", "app_secret"), required=True)
    api_key = _get("ANTHROPIC_API_KEY", file_cfg, ("claude", "api_key"))
    auth_mode = AuthMode.API_KEY if api_key else AuthMode.OAUTH

    working_dir = _get(
        "AUGUR_WORKING_DIR", file_cfg, ("bot", "working_dir"),
        default="~/Desktop/Toys/augur/data",
    )

    schedule = _parse_schedule(file_cfg.get("schedule", {}))
    users = _parse_users(file_cfg.get("users", {}))

    return BotConfig(
        app_id=app_id,
        app_secret=app_secret,
        auth_mode=auth_mode,
        anthropic_api_key=api_key,
        working_dir=os.path.expanduser(working_dir),
        encrypt_key=_get("AUGUR_ENCRYPT_KEY", file_cfg, ("feishu", "encrypt_key"), default=""),
        verification_token=_get("AUGUR_VERIFICATION_TOKEN", file_cfg, ("feishu", "verification_token"), default=""),
        feishu_domain=_get("AUGUR_FEISHU_DOMAIN", file_cfg, ("feishu", "domain"), default="https://open.feishu.cn"),
        model=_get("AUGUR_MODEL", file_cfg, ("claude", "model"), default="claude-sonnet-4-5"),
        schedule=schedule,
        users=users,
    )


def _parse_schedule(cfg: dict) -> ScheduleConfig:
    """Parse [schedule] section from config."""
    if not cfg:
        return ScheduleConfig()

    hours = cfg.get("exploration_hours", [9, 12, 18])
    return ScheduleConfig(
        timezone=cfg.get("timezone", "Asia/Shanghai"),
        morning_hour=cfg.get("morning_hour", 8),
        morning_chat_id=cfg.get("morning_chat_id", ""),
        exploration_hours=tuple(hours),
        journal_enabled=cfg.get("journal_enabled", True),
        exploration_enabled=cfg.get("exploration_enabled", True),
        morning_enabled=cfg.get("morning_enabled", True),
    )


def _parse_users(cfg: dict) -> dict[str, dict]:
    """Parse [users.*] sections. Returns {sender_id: {name, default_soul}}."""
    result = {}
    for sender_id, user_cfg in cfg.items():
        if isinstance(user_cfg, dict):
            result[sender_id] = {
                "name": user_cfg.get("name", sender_id[:8]),
                "default_soul": user_cfg.get("default_soul", "balanced"),
            }
    return result


def _load_toml(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    with open(p, "rb") as f:
        return tomllib.load(f)


def _get(
    env_key: str,
    file_cfg: dict,
    toml_keys: tuple[str, ...],
    default: str | None = None,
    required: bool = False,
) -> str:
    """Resolve value: env var > TOML file > default. Fail if required and missing."""
    val = os.environ.get(env_key)
    if val:
        return val

    node = file_cfg
    for key in toml_keys:
        if isinstance(node, dict):
            node = node.get(key)
        else:
            node = None
            break
    if node and isinstance(node, str) and node.strip():
        return node.strip()

    if default is not None:
        return default

    if required:
        raise SystemExit(
            f"Missing required config: set {env_key} env var or "
            f"{'.'.join(toml_keys)} in config.toml"
        )
    return ""
