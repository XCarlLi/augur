"""User read/write isolation. Prevents cross-user data access."""

from __future__ import annotations

import os
import re
from pathlib import Path

from claude_agent_sdk.types import PermissionResultAllow, PermissionResultDeny

_WRITE_TOOLS = {"Write", "Edit", "NotebookEdit"}
_READ_TOOLS = {"Read", "Glob", "Grep"}


def _resolve_path(path_str: str, cwd: str) -> str:
    """Resolve a potentially relative path to absolute."""
    p = Path(path_str)
    if not p.is_absolute():
        p = Path(cwd) / p
    return str(p.resolve())


def _is_other_user_data(resolved: str, data_dir: str, sender_id: str) -> bool:
    """Check if path accesses another user's data under users/{sender_id}/."""
    resolved_p = Path(resolved)
    users_dir = Path(data_dir) / "users"
    users_str = str(users_dir.resolve())

    # Block listing users/ directory itself (enumerates all users)
    if str(resolved_p) == users_str:
        return True

    # Check if path is under users/
    if not str(resolved_p).startswith(users_str + os.sep):
        return False

    # Extract the first component after users/
    rel = str(resolved_p)[len(users_str) + 1:]
    first_component = rel.split(os.sep)[0]

    return first_component != sender_id


def _bash_targets_other_users(command: str, sender_id: str) -> bool:
    """Check if a bash command references other users' data paths."""
    pattern = r'users[/\\](\w+)'
    for m in re.finditer(pattern, command):
        found_id = m.group(1)
        if found_id != sender_id:
            return True
    return False


def create_isolation_callback(sender_id: str, data_dir: str):
    """Create permission callback enforcing user data isolation.

    - Blocks reads of other users' data
    - Restricts writes to user's own memory + current chat scratch
    """
    resolved_data = str(Path(data_dir).resolve())
    user_prefix = str((Path(data_dir) / "users" / sender_id).resolve())

    async def can_use_tool(tool_name: str, input_data: dict, context):
        # Read tools: block cross-user access
        if tool_name in _READ_TOOLS:
            file_path = input_data.get("file_path") or input_data.get("path", "")
            if file_path:
                resolved = _resolve_path(file_path, resolved_data)
                if _is_other_user_data(resolved, resolved_data, sender_id):
                    return PermissionResultDeny(
                        message="Access denied: cannot read other users' data",
                    )
            pattern = input_data.get("pattern", "")
            if pattern and _bash_targets_other_users(pattern, sender_id):
                return PermissionResultDeny(
                    message="Access denied: cannot access other users' data",
                )
            return PermissionResultAllow(updated_input=input_data)

        # Write tools: must be under user's directory or chats/
        if tool_name in _WRITE_TOOLS:
            file_path = input_data.get("file_path") or input_data.get("notebook_path", "")
            if file_path:
                resolved = _resolve_path(file_path, resolved_data)
                chats_prefix = str((Path(data_dir) / "chats").resolve())
                if not (resolved.startswith(user_prefix + os.sep)
                        or resolved.startswith(chats_prefix + os.sep)):
                    return PermissionResultDeny(
                        message=f"Write denied: outside allowed directories",
                    )
            return PermissionResultAllow(updated_input=input_data)

        # Bash: check for cross-user paths
        if tool_name == "Bash":
            command = input_data.get("command", "")
            if _bash_targets_other_users(command, sender_id):
                return PermissionResultDeny(
                    message="Access denied: cannot access other users' data",
                )
            return PermissionResultAllow(updated_input=input_data)

        return PermissionResultAllow(updated_input=input_data)

    return can_use_tool
