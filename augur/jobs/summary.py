"""Monthly summary: generates knowledge/summaries/YYYY-MM.md from journal entries.

Runs on the 1st of each month at 03:00. Reads all diary and exploration files
from the previous month and produces a one-paragraph summary with title on first line.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .. import log
from ..autonomous import AutonomousConfig, run_session
from ..memory import resolve_active_soul
from ..store import ChatStore
from ..types import BotConfig, UserInfo


def _summary_path(user_dir: Path, month: str) -> Path:
    return user_dir / "knowledge" / "summaries" / f"{month}.md"


def _collect_journal_files(user_dir: Path, month: str) -> list[Path]:
    """Collect all diary and exploration files for the given month."""
    files = []
    diary_dir = user_dir / "journal" / "diary"
    exploration_dir = user_dir / "journal" / "exploration"

    for d in (diary_dir, exploration_dir):
        if d.is_dir():
            files.extend(sorted(f for f in d.glob(f"{month}-*.md")))

    return files


def _build_system_prompt(user: UserInfo, data_root: Path) -> str:
    resolved = str(data_root.resolve())

    return f"""你要生成一份月度摘要。

## Working Directory
{resolved}

## 可访问的文件
- 日记：{resolved}/users/{user.sender_id}/journal/diary/（读）
- 探索笔记：{resolved}/users/{user.sender_id}/journal/exploration/（读）
- 摘要目录：{resolved}/users/{user.sender_id}/knowledge/summaries/（写）

## 限制
- 只能写入 knowledge/summaries/ 目录
- 禁止修改代码文件

## 输出规则
- 始终用中文
- 写完摘要后回复 [SILENT]"""


def _build_query_prompt(user: UserInfo, month: str, journal_files: list[Path]) -> str:
    file_list = "\n".join(f"- `{f.name}`" for f in journal_files)

    return f"""为 {month} 生成月度摘要。

## 文件列表
{file_list}

## 执行步骤

1. 读取上述所有文件
2. 提炼本月的主要活动、关键发现、认知变化
3. 生成摘要，格式：
   - 第一行：一句话标题（如"3月：XXX 项目推进 + 探索YYY"）
   - 空行
   - 一段式摘要（200-400字），涵盖：做了什么、发现了什么、想法有什么变化
4. 保存到 `users/{user.sender_id}/knowledge/summaries/{month}.md`

写完后回复 [SILENT]"""


async def run_monthly_summary(
    user: UserInfo,
    config: BotConfig,
    store: ChatStore,
    target_month: str,  # "YYYY-MM"
) -> None:
    """Generate monthly summary. Silent — no user-facing output."""
    # Skip if summary already exists
    if _summary_path(user.user_dir, target_month).exists():
        log.info(f"monthly summary already exists for {target_month}")
        return

    # Collect journal files
    journal_files = _collect_journal_files(user.user_dir, target_month)
    if not journal_files:
        log.info(f"no journal files for {target_month}, skipping summary")
        return

    # Ensure directory
    (user.user_dir / "knowledge" / "summaries").mkdir(parents=True, exist_ok=True)

    data_root = store._root
    resolved = str(data_root.resolve())

    session_config = AutonomousConfig(
        name="monthly-summary",
        system_prompt=_build_system_prompt(user, data_root),
        query_prompt=_build_query_prompt(user, target_month, journal_files),
        cwd=resolved,
        max_turns=10,
        model=config.model,
        allowed_write_prefixes=[
            str((data_root / "users" / user.sender_id / "knowledge" / "summaries").resolve()) + "/",
        ],
    )

    result = await run_session(session_config)
    if result.text:
        log.info(f"monthly summary {target_month}: unexpected output: {result.text[:100]}")
    else:
        log.info(f"monthly summary completed for {target_month}")
