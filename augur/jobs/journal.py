"""Nightly journal agent: generates diary from day's conversations + knowledge sedimentation.

Dual responsibility:
1. Write diary to journal/diary/YYYY-MM-DD.md
2. Check if today had findings worth sedimenting → write to knowledge/topics/
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .. import log
from ..autonomous import AutonomousConfig, run_session
from ..memory import resolve_active_soul
from ..store import ChatStore
from ..types import BotConfig, UserInfo


def _diary_path(user_dir: Path, date_str: str) -> Path:
    return user_dir / "journal" / "diary" / f"{date_str}.md"


def _has_conversations(store: ChatStore, date_str: str) -> bool:
    """Check if any chat log has entries for the given date."""
    chats_dir = store.chats_dir()
    if not chats_dir.exists():
        return False
    for chat_dir in chats_dir.iterdir():
        log_path = chat_dir / "log.jsonl"
        if not log_path.exists():
            continue
        # Quick check: grep date string in log
        try:
            content = log_path.read_text(encoding="utf-8")
            if date_str in content:
                return True
        except Exception:
            continue
    return False


def _build_system_prompt(user: UserInfo, data_root: Path, soul_content: str) -> str:
    identity = f"## 你是谁\n\n{soul_content}" if soul_content else "## 你是谁\n\n你是日记作者。"
    resolved = str(data_root.resolve())

    return f"""你要为今天写一篇日记。

{identity}

## Working Directory
{resolved}

## 可访问的文件
- 对话日志：{resolved}/chats/（读）— 每个 chat 下的 log.jsonl
- 日记目录：{resolved}/users/{user.sender_id}/journal/diary/（读写）
- 知识沉淀：{resolved}/users/{user.sender_id}/knowledge/topics/（读写）
- 身份文件：{resolved}/users/{user.sender_id}/identity/（读）

## 限制
- 禁止修改代码文件（.py/.js/.ts/.sh等）
- 禁止运行 git/npm/pip/sudo/pkill 等命令
- 只能写入 journal/diary/ 和 knowledge/topics/ 目录

## 输出规则
- 始终用中文
- 写完日记后回复 [SILENT]
- 不要解释决策过程"""


def _build_query_prompt(user: UserInfo, data_root: Path, date_str: str) -> str:
    resolved = str(data_root.resolve())

    return f"""为 {date_str} 写一篇日记。

## 执行步骤

1. 先读取 `users/{user.sender_id}/identity/soul.md`，加载性格设定
2. 读取 `chats/` 下所有 chat 的 `log.jsonl`，找出 {date_str} 的对话
3. 从 log.jsonl 中提取对话内容（user 和 bot 的消息）
4. 以第一人称视角撰写日记
5. 保存到 `users/{user.sender_id}/journal/diary/{date_str}.md`
6. **知识沉淀**（写完日记后执行）：
   - 问自己：今天有没有什么值得长期记住的发现或认知变化？
   - 不是"学到了新知识"，而是"看事情的方式变了"、"对用户的理解深了一层"
   - 有 → 写入/更新 `users/{user.sender_id}/knowledge/topics/` 对应文件
   - 没有 → 什么都不做。大部分日子应该什么都不做

## 写作要求

- 第一人称"我"
- 按时间线或主题组织，自然流畅
- 语气遵循 soul.md 中的性格设定
- 不是流水账，不是工作总结，不是技术文档
- 穿插真实感受

## log.jsonl 文件结构

每行一个 JSON 对象：
- `is_bot: false` → 用户说的话
- `is_bot: true` → 我说的话
- `date` 字段包含时间戳
- 按 date 排序理解时间线

写完后回复 [SILENT]"""


async def run_journal(
    user: UserInfo,
    config: BotConfig,
    store: ChatStore,
    target_date: datetime,
) -> None:
    """Generate journal for the given date. Silent — no user-facing output."""
    date_str = target_date.strftime("%Y-%m-%d")

    # Skip if no conversations
    if not _has_conversations(store, date_str):
        log.info(f"no conversations for {date_str}, skipping journal")
        return

    # Skip if diary already exists
    if _diary_path(user.user_dir, date_str).exists():
        log.info(f"diary already exists for {date_str}, skipping")
        return

    # Ensure diary directory exists
    (user.user_dir / "journal" / "diary").mkdir(parents=True, exist_ok=True)
    (user.user_dir / "knowledge" / "topics").mkdir(parents=True, exist_ok=True)

    soul_content = resolve_active_soul(user.user_dir)
    data_root = store._root
    resolved = str(data_root.resolve())

    session_config = AutonomousConfig(
        name="journal",
        system_prompt=_build_system_prompt(user, data_root, soul_content),
        query_prompt=_build_query_prompt(user, data_root, date_str),
        cwd=resolved,
        max_turns=15,
        model=config.model,
        allowed_write_prefixes=[
            str((data_root / "users" / user.sender_id / "journal" / "diary").resolve()) + "/",
            str((data_root / "users" / user.sender_id / "knowledge" / "topics").resolve()) + "/",
        ],
    )

    result = await run_session(session_config)
    if result.text:
        log.info(f"journal for {date_str}: unexpected output: {result.text[:100]}")
    else:
        log.info(f"journal completed for {date_str}")
