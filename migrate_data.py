"""One-time migration: data/{chat_id}/ → data/chats/{chat_id}/

Run: python migrate_data.py [data_dir]
Default data_dir: ~/Desktop/Toys/augur/data
"""

import shutil
import sys
from pathlib import Path


def migrate(data_dir: Path) -> None:
    chats_dir = data_dir / "chats"
    chats_dir.mkdir(exist_ok=True)

    # Skip known non-chat directories
    skip = {"chats", "users", "templates", "MEMORY.md"}

    moved = 0
    for item in sorted(data_dir.iterdir()):
        if item.name in skip or not item.is_dir():
            continue
        # Heuristic: chat_id directories have log.jsonl or scratch/
        if (item / "log.jsonl").exists() or (item / "scratch").exists():
            dest = chats_dir / item.name
            if dest.exists():
                print(f"  SKIP {item.name} (already exists in chats/)")
                continue
            shutil.move(str(item), str(dest))
            print(f"  MOVED {item.name} → chats/{item.name}")
            moved += 1

    # Remove old MEMORY.md if it exists (superseded by per-user memory)
    old_memory = data_dir / "MEMORY.md"
    if old_memory.exists():
        old_memory.rename(data_dir / "MEMORY.md.bak")
        print(f"  BACKED UP MEMORY.md → MEMORY.md.bak")

    print(f"\nDone. Migrated {moved} chat directories.")


if __name__ == "__main__":
    data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "Desktop/Toys/augur/data"
    if not data_dir.exists():
        print(f"Data directory not found: {data_dir}")
        sys.exit(1)
    print(f"Migrating {data_dir}")
    migrate(data_dir)
