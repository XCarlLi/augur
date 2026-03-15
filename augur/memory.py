"""Three-layer memory loader: full, index, path-based directory loading.

Loading strategy is determined by directory name:
  identity/  → full load (small, always injected)
  knowledge/ → index load (first-line summaries, permanent)
  journal/   → path load (recent 14 days, older searchable via Glob/Grep)
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from . import log


def _first_meaningful_line(content: str) -> str:
    """Extract first non-empty, non-heading-marker line as short description."""
    for line in content.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped:
            return stripped[:120]
    return "(no description)"


def load_full(directory: Path, label: str, skip_files: set[str] | None = None) -> str:
    """Read all .md files recursively. Used for identity/ — small, always loaded."""
    if not directory.is_dir():
        return ""

    sections: list[str] = []
    for md_file in sorted(directory.rglob("*.md")):
        if md_file.name.startswith("._"):
            continue
        if skip_files and md_file.name in skip_files:
            continue
        try:
            content = md_file.read_text(encoding="utf-8").strip()
            if content:
                rel = md_file.relative_to(directory)
                sections.append(f"### {rel}\n\n{content}")
        except Exception as e:
            log.warning("failed to read memory file", str(e))

    if not sections:
        return ""
    return f"\n## {label}\n\n" + "\n\n".join(sections) + "\n"


def load_index(directory: Path, label: str) -> str:
    """Read first line of each .md file as index. Used for knowledge/ — permanent."""
    if not directory.is_dir():
        return ""

    index_lines: list[str] = []
    for md_file in sorted(directory.rglob("*.md")):
        if md_file.name.startswith("._"):
            continue
        try:
            content = md_file.read_text(encoding="utf-8").strip()
            if not content:
                continue
            desc = _first_meaningful_line(content)
            rel = md_file.relative_to(directory)
            index_lines.append(f"- `knowledge/{rel}`: {desc}")
        except Exception as e:
            log.warning("failed to index memory file", str(e))

    if not index_lines:
        return ""

    result = f"\n## {label}\n"
    result += "查询：用 Read 工具读取完整内容。跨文件分析：用 Explore subagent。\n\n"
    result += "\n".join(index_lines) + "\n"
    return result


def load_paths(directory: Path, label: str, days: int = 14) -> str:
    """List recent file paths only (no content). Used for journal/ — 14-day window."""
    if not directory.is_dir():
        return ""

    entries: list[str] = []
    today = datetime.now().date()

    for sub in sorted(directory.iterdir()):
        if not sub.is_dir() or sub.name.startswith("."):
            continue
        for days_ago in range(days):
            date = today - timedelta(days=days_ago)
            date_str = date.strftime("%Y-%m-%d")
            for f in sorted(sub.glob(f"{date_str}*")):
                if f.name.startswith("._"):
                    continue
                rel = f.relative_to(directory)
                entries.append(f"- `journal/{rel}`")

    if not entries:
        return ""

    result = f"\n## {label}（用 Read 工具查看内容）\n\n"
    result += "\n".join(entries)
    result += "\n\n> 旧日志在 journal/ 目录，用 Glob/Grep 搜索。\n"
    return result


def resolve_active_soul(user_dir: Path) -> str:
    """Load soul content via souls/active.txt, fallback to identity/soul.md."""
    active_file = user_dir / "souls" / "active.txt"
    soul_path = None
    if active_file.exists():
        relative = active_file.read_text(encoding="utf-8").strip()
        candidate = user_dir / "souls" / relative
        if candidate.exists():
            soul_path = candidate
    if not soul_path:
        soul_path = user_dir / "identity" / "soul.md"
    if not soul_path or not soul_path.exists():
        return ""
    try:
        content = soul_path.read_text(encoding="utf-8").strip()
        return f"### soul.md\n\n{content}" if content else ""
    except Exception as e:
        log.warning("failed to read soul", str(e))
        return ""


def load_user_memory(user_dir: Path) -> str:
    """Compose full user memory prompt from three layers."""
    prompt = ""
    # Identity (full load, skip soul.md — loaded separately via active soul)
    prompt += load_full(
        user_dir / "identity",
        "预加载的记忆（立即据此行动）",
        skip_files={"soul.md"},
    )
    # Active soul
    soul_section = resolve_active_soul(user_dir)
    if soul_section:
        prompt += f"\n{soul_section}\n"
    # Knowledge index (permanent, includes topics/ and summaries/)
    prompt += load_index(user_dir / "knowledge", "知识索引")
    # Recent journal paths (14-day window)
    prompt += load_paths(user_dir / "journal", "近期日志")
    return prompt
