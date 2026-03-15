"""Build system prompt: platform-agnostic core + platform-specific capabilities.

Core prompt (all platforms): identity + memory + context + recent log
Platform prompt (replaceable): Feishu CLI docs, message format, etc.
"""

from .memory import load_user_memory
from .store import ChatStore


_FEISHU_CLI = "python -m augur.cli.feishu_cli"

_FEISHU_PLATFORM_PROMPT = f"""## Feishu CLI
Use the Feishu CLI to interact with the platform:
```
{_FEISHU_CLI} <command> [options]
```

Available commands:
  Messages:
    send-message    --chat-id ID --text TEXT
    reply-message   --message-id ID --text TEXT
    list-messages   --chat-id ID [--n N]

  Documents:
    create-doc      --title TITLE [--folder-token TOKEN]
    read-doc        --document-id ID
    write-doc       --document-id ID --content MARKDOWN

  Calendar:
    list-calendar   --start DATE --end DATE
    create-event    --summary TEXT --start DATETIME --end DATETIME [--attendees IDS]
    get-event       --event-id ID

  Bitable:
    create-bitable  --name NAME [--folder-token TOKEN]
    add-record      --app-token TOKEN --table-id ID --fields JSON
    list-records    --app-token TOKEN --table-id ID

  Tasks:
    create-task     --title TEXT [--due DATE] [--assignees IDS]
    list-tasks
    update-task     --task-id ID [--status STATUS]

  Wiki:
    get-wiki        --space-id ID --node-token TOKEN
    create-wiki-node --space-id ID --title TEXT --content MARKDOWN
    search-wiki     --query TEXT

  Drive:
    upload-file     --folder-token TOKEN --file-path PATH
    list-files      --folder-token TOKEN
    download-file   --file-token TOKEN --output PATH

  Users:
    get-user        --user-id ID
    list-users      [--department-id ID]

Use `{_FEISHU_CLI} <command> --help` for details.

## Feishu Message Formatting
Bold: **text**, Italic: *text*, Code: `code`, Code block: ```code```"""


def _build_core_prompt(sender_id: str, chat_id: str, store: ChatStore) -> str:
    """Platform-agnostic core: identity + memory + context + log."""
    user_dir = store.user_dir(sender_id)
    chat_dir = store.chat_dir(chat_id)
    recent = store.get_recent_log(chat_id, n=10)

    # Load user memory (three-layer: identity + knowledge index + journal paths)
    user_memory = load_user_memory(user_dir)

    parts = ["You are Augur, a personal assistant powered by Claude."]

    if user_memory.strip():
        parts.append(user_memory)

    parts.append(f"""## Context
- Chat ID: {chat_id}
- User ID: {sender_id}
- Working directory: {chat_dir}/scratch/
- User memory directory: {user_dir}/

## Local Computer
You have full access to the local computer via bash, file read/write/edit.
The scratch directory for this chat is: {chat_dir}/scratch/

## Recent Conversation
{recent}""")

    return "\n\n".join(parts)


def build_system_prompt(
    sender_id: str,
    chat_id: str,
    store: ChatStore,
    platform_prompt: str = _FEISHU_PLATFORM_PROMPT,
) -> str:
    """Construct the full system prompt: core (platform-agnostic) + platform capabilities."""
    core = _build_core_prompt(sender_id, chat_id, store)
    return core + "\n\n" + platform_prompt
