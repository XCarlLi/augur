"""Feishu API CLI wrapper. Each subcommand = one Feishu API operation."""

import argparse
import json
import os
import sys

import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
    ListChatRequest,
    ListMessageRequest,
    ReplyMessageRequest,
    ReplyMessageRequestBody,
)
from lark_oapi.api.docx.v1 import (
    CreateDocumentRequest,
    CreateDocumentRequestBody,
    RawContentDocumentRequest,
    CreateDocumentBlockChildrenRequest,
    CreateDocumentBlockChildrenRequestBody,
    Block,
    Text,
    TextElement,
    TextRun,
)
from lark_oapi.api.calendar.v4 import (
    CalendarEvent,
    ListCalendarEventRequest,
    ListCalendarRequest,
    CreateCalendarEventRequest,
    TimeInfo,
)
from lark_oapi.api.bitable.v1 import (
    AppTableRecord,
    CreateAppRequest,
    CreateAppTableRecordRequest,
    ListAppTableRecordRequest,
    ReqApp,
)
from lark_oapi.api.task.v2 import (
    CreateTaskRequest,
    InputTask,
    ListTaskRequest,
)
from lark_oapi.api.drive.v1 import (
    ListFileRequest,
    UploadAllFileRequest,
    UploadAllFileRequestBody,
)
from lark_oapi.api.wiki.v2 import (
    GetNodeSpaceRequest,
)
from lark_oapi.api.contact.v3 import (
    GetUserRequest,
)


def _build_client() -> lark.Client:
    app_id = os.environ.get("AUGUR_APP_ID", "")
    app_secret = os.environ.get("AUGUR_APP_SECRET", "")
    domain = os.environ.get("AUGUR_FEISHU_DOMAIN", "https://open.feishu.cn")
    if not app_id or not app_secret:
        print("Error: AUGUR_APP_ID and AUGUR_APP_SECRET must be set", file=sys.stderr)
        sys.exit(1)
    return (
        lark.Client.builder()
        .app_id(app_id)
        .app_secret(app_secret)
        .domain(domain)
        .build()
    )


def _out(data: dict) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


# ============================================================================
# Message commands
# ============================================================================


def cmd_send_message(args: argparse.Namespace) -> None:
    client = _build_client()
    # Support both --chat-id (group) and --open-id (DM)
    if args.open_id:
        receive_id = args.open_id
        receive_id_type = "open_id"
    else:
        receive_id = args.chat_id
        receive_id_type = "chat_id"
    body = (
        CreateMessageRequestBody.builder()
        .receive_id(receive_id)
        .msg_type("text")
        .content(json.dumps({"text": args.text}))
        .build()
    )
    req = (
        CreateMessageRequest.builder()
        .receive_id_type(receive_id_type)
        .request_body(body)
        .build()
    )
    resp = client.im.v1.message.create(req)
    if resp.success():
        _out({"ok": True, "message_id": resp.data.message_id})
    else:
        _out({"ok": False, "code": resp.code, "msg": resp.msg})


def cmd_reply_message(args: argparse.Namespace) -> None:
    client = _build_client()
    body = (
        ReplyMessageRequestBody.builder()
        .msg_type("text")
        .content(json.dumps({"text": args.text}))
        .build()
    )
    req = (
        ReplyMessageRequest.builder()
        .message_id(args.message_id)
        .request_body(body)
        .build()
    )
    resp = client.im.v1.message.reply(req)
    if resp.success():
        _out({"ok": True, "message_id": resp.data.message_id})
    else:
        _out({"ok": False, "code": resp.code, "msg": resp.msg})


def cmd_list_chats(args: argparse.Namespace) -> None:
    """List all chats the bot is in. Use --type p2p to filter 1-on-1 chats."""
    client = _build_client()
    req = ListChatRequest.builder().page_size(args.n).build()
    resp = client.im.v1.chat.list(req)
    if resp.success() and resp.data and resp.data.items:
        chats = []
        for item in resp.data.items:
            chats.append({
                "chat_id": item.chat_id,
                "name": item.name,
                "description": getattr(item, 'description', None),
                "owner_id": getattr(item, 'owner_id', None),
                "external": getattr(item, 'external', None),
            })
        _out({"ok": True, "chats": chats, "count": len(chats)})
    else:
        _out({"ok": False, "code": resp.code, "msg": resp.msg})


def cmd_list_messages(args: argparse.Namespace) -> None:
    client = _build_client()
    req = (
        ListMessageRequest.builder()
        .container_id_type("chat")
        .container_id(args.chat_id)
        .page_size(args.n)
        .build()
    )
    resp = client.im.v1.message.list(req)
    if resp.success() and resp.data and resp.data.items:
        messages = []
        for item in resp.data.items:
            messages.append({
                "message_id": item.message_id,
                "sender_id": item.sender.id if item.sender else None,
                "content": item.body.content if item.body else None,
                "create_time": item.create_time,
            })
        _out({"ok": True, "messages": messages})
    else:
        _out({"ok": False, "code": resp.code, "msg": resp.msg})


# ============================================================================
# Document commands
# ============================================================================


def cmd_create_doc(args: argparse.Namespace) -> None:
    client = _build_client()
    builder = CreateDocumentRequestBody.builder().title(args.title)
    if args.folder_token:
        builder = builder.folder_token(args.folder_token)
    req = CreateDocumentRequest.builder().request_body(builder.build()).build()
    resp = client.docx.v1.document.create(req)
    if resp.success() and resp.data:
        doc = resp.data.document
        _out({
            "ok": True,
            "document_id": doc.document_id if doc else None,
            "title": doc.title if doc else None,
        })
    else:
        _out({"ok": False, "code": resp.code, "msg": resp.msg})


def cmd_read_doc(args: argparse.Namespace) -> None:
    client = _build_client()
    req = (
        RawContentDocumentRequest.builder()
        .document_id(args.document_id)
        .build()
    )
    resp = client.docx.v1.document.raw_content(req)
    if resp.success() and resp.data:
        _out({"ok": True, "content": resp.data.content})
    else:
        _out({"ok": False, "code": resp.code, "msg": resp.msg})


def cmd_write_doc(args: argparse.Namespace) -> None:
    """Write markdown content to a Feishu document."""
    client = _build_client()

    # Read markdown content
    with open(args.content_file, 'r', encoding='utf-8') as f:
        markdown_content = f.read()

    # Convert markdown to Feishu blocks (simple text blocks for now)
    blocks = []
    for line in markdown_content.split('\n'):
        content = line if line.strip() else " "  # Use space for empty lines
        # Build text element
        text_run = TextRun.builder().content(content).build()
        text_element = TextElement.builder().text_run(text_run).build()
        text = Text.builder().elements([text_element]).build()
        block = Block.builder().block_type(2).text(text).build()  # block_type 2 = text
        blocks.append(block)

    # Add blocks to document in batches of 50
    batch_size = 50
    total_blocks = len(blocks)
    for i in range(0, total_blocks, batch_size):
        batch = blocks[i:i + batch_size]
        body = (
            CreateDocumentBlockChildrenRequestBody.builder()
            .children(batch)
            .build()
        )
        req = (
            CreateDocumentBlockChildrenRequest.builder()
            .document_id(args.document_id)
            .block_id(args.document_id)  # Root block ID is same as document ID
            .request_body(body)
            .build()
        )
        resp = client.docx.v1.document_block_children.create(req)

        if not resp.success():
            _out({"ok": False, "code": resp.code, "msg": resp.msg, "batch": i // batch_size})
            return

    _out({"ok": True, "message": f"Content written successfully ({total_blocks} blocks)"})


# ============================================================================
# Calendar commands
# ============================================================================


def cmd_list_calendar(args: argparse.Namespace) -> None:
    client = _build_client()

    # Get calendar_id: use provided one or auto-detect first available
    calendar_id = args.calendar_id if hasattr(args, 'calendar_id') and args.calendar_id else None

    if not calendar_id:
        # Auto-detect: get first available calendar
        cal_req = ListCalendarRequest.builder().page_size(50).build()
        cal_resp = client.calendar.v4.calendar.list(cal_req)
        if cal_resp.success() and cal_resp.data and hasattr(cal_resp.data, 'calendar_list') and cal_resp.data.calendar_list:
            calendar_id = cal_resp.data.calendar_list[0].calendar_id
        else:
            error_msg = f"List calendar failed: code={getattr(cal_resp, 'code', 'N/A')}, msg={getattr(cal_resp, 'msg', 'N/A')}"
            _out({"ok": False, "code": "NO_CALENDAR", "msg": error_msg})
            return

    # List events in the calendar
    req = (
        ListCalendarEventRequest.builder()
        .calendar_id(calendar_id)
        .start_time(args.start)
        .end_time(args.end)
        .build()
    )
    resp = client.calendar.v4.calendar_event.list(req)
    if resp.success():
        events = []
        if resp.data and hasattr(resp.data, 'items') and resp.data.items:
            for item in resp.data.items:
                events.append({
                    "event_id": item.event_id,
                    "summary": item.summary,
                    "start_time": item.start_time.timestamp if item.start_time else None,
                    "end_time": item.end_time.timestamp if item.end_time else None,
                })
        _out({"ok": True, "events": events, "count": len(events)})
    else:
        _out({"ok": False, "code": resp.code, "msg": resp.msg})


def cmd_create_event(args: argparse.Namespace) -> None:
    client = _build_client()
    event_body = (
        CalendarEvent.builder()
        .summary(args.summary)
        .start_time(TimeInfo.builder().timestamp(args.start).build())
        .end_time(TimeInfo.builder().timestamp(args.end).build())
        .build()
    )
    req = (
        CreateCalendarEventRequest.builder()
        .calendar_id("primary")
        .request_body(event_body)
        .build()
    )
    resp = client.calendar.v4.calendar_event.create(req)
    if resp.success() and resp.data:
        _out({"ok": True, "event_id": resp.data.event.event_id if resp.data.event else None})
    else:
        _out({"ok": False, "code": resp.code, "msg": resp.msg})


# ============================================================================
# Bitable commands
# ============================================================================


def cmd_create_bitable(args: argparse.Namespace) -> None:
    client = _build_client()
    body_builder = ReqApp.builder().name(args.name)
    if args.folder_token:
        body_builder = body_builder.folder_token(args.folder_token)
    req = CreateAppRequest.builder().request_body(body_builder.build()).build()
    resp = client.bitable.v1.app.create(req)
    if resp.success() and resp.data and resp.data.app:
        _out({"ok": True, "app_token": resp.data.app.app_token, "name": resp.data.app.name})
    else:
        _out({"ok": False, "code": resp.code, "msg": resp.msg})


def cmd_add_record(args: argparse.Namespace) -> None:
    client = _build_client()
    fields = json.loads(args.fields)
    body = AppTableRecord.builder().fields(fields).build()
    req = (
        CreateAppTableRecordRequest.builder()
        .app_token(args.app_token)
        .table_id(args.table_id)
        .request_body(body)
        .build()
    )
    resp = client.bitable.v1.app_table_record.create(req)
    if resp.success() and resp.data and resp.data.record:
        _out({"ok": True, "record_id": resp.data.record.record_id})
    else:
        _out({"ok": False, "code": resp.code, "msg": resp.msg})


def cmd_list_records(args: argparse.Namespace) -> None:
    client = _build_client()
    req = (
        ListAppTableRecordRequest.builder()
        .app_token(args.app_token)
        .table_id(args.table_id)
        .page_size(20)
        .build()
    )
    resp = client.bitable.v1.app_table_record.list(req)
    if resp.success() and resp.data and resp.data.items:
        records = [{"record_id": r.record_id, "fields": r.fields} for r in resp.data.items]
        _out({"ok": True, "records": records})
    else:
        _out({"ok": False, "code": resp.code, "msg": resp.msg})


# ============================================================================
# Task commands
# ============================================================================


def cmd_create_task(args: argparse.Namespace) -> None:
    client = _build_client()
    task_builder = InputTask.builder().summary(args.title)
    req = CreateTaskRequest.builder().request_body(task_builder.build()).build()
    resp = client.task.v2.task.create(req)
    if resp.success() and resp.data:
        _out({"ok": True, "task": str(resp.data)})
    else:
        _out({"ok": False, "code": resp.code, "msg": resp.msg})


def cmd_list_tasks(args: argparse.Namespace) -> None:
    client = _build_client()
    req = ListTaskRequest.builder().page_size(50).build()
    resp = client.task.v2.task.list(req)
    if resp.success() and resp.data and resp.data.items:
        tasks = [{"guid": t.guid, "summary": t.summary} for t in resp.data.items]
        _out({"ok": True, "tasks": tasks})
    else:
        _out({"ok": False, "code": resp.code, "msg": resp.msg})


# ============================================================================
# Drive commands
# ============================================================================


def cmd_list_files(args: argparse.Namespace) -> None:
    client = _build_client()
    req = (
        ListFileRequest.builder()
        .folder_token(args.folder_token)
        .page_size(50)
        .build()
    )
    resp = client.drive.v1.file.list(req)
    if resp.success() and resp.data and resp.data.files:
        files = [{"token": f.token, "name": f.name, "type": f.type} for f in resp.data.files]
        _out({"ok": True, "files": files})
    else:
        _out({"ok": False, "code": resp.code, "msg": resp.msg})


# ============================================================================
# User commands
# ============================================================================


def cmd_get_user(args: argparse.Namespace) -> None:
    client = _build_client()
    req = (
        GetUserRequest.builder()
        .user_id(args.user_id)
        .user_id_type("open_id")
        .build()
    )
    resp = client.contact.v3.user.get(req)
    if resp.success() and resp.data and resp.data.user:
        u = resp.data.user
        _out({"ok": True, "name": u.name, "email": u.email, "user_id": u.user_id})
    else:
        _out({"ok": False, "code": resp.code, "msg": resp.msg})


# ============================================================================
# Argument parser
# ============================================================================


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="feishu_cli", description="Feishu API CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    # Messages
    p = sub.add_parser("send-message")
    p.add_argument("--chat-id", default=None, help="Chat ID for group messages")
    p.add_argument("--open-id", default=None, help="Open ID for direct messages (DM)")
    p.add_argument("--text", required=True)

    p = sub.add_parser("reply-message")
    p.add_argument("--message-id", required=True)
    p.add_argument("--text", required=True)

    p = sub.add_parser("list-chats")
    p.add_argument("--n", type=int, default=50, help="Number of chats to list")
    p.add_argument("--type", default=None, help="Filter by type: p2p or group")

    p = sub.add_parser("list-messages")
    p.add_argument("--chat-id", required=True)
    p.add_argument("--n", type=int, default=20)

    # Documents
    p = sub.add_parser("create-doc")
    p.add_argument("--title", required=True)
    p.add_argument("--folder-token", default=None)

    p = sub.add_parser("read-doc")
    p.add_argument("--document-id", required=True)

    p = sub.add_parser("write-doc")
    p.add_argument("--document-id", required=True)
    p.add_argument("--content-file", required=True, help="Path to markdown file")

    # Calendar
    p = sub.add_parser("list-calendar")
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    p.add_argument("--calendar-id", default=None, help="Calendar ID (auto-detect if not provided)")

    p = sub.add_parser("create-event")
    p.add_argument("--summary", required=True)
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)

    # Bitable
    p = sub.add_parser("create-bitable")
    p.add_argument("--name", required=True)
    p.add_argument("--folder-token", default=None)

    p = sub.add_parser("add-record")
    p.add_argument("--app-token", required=True)
    p.add_argument("--table-id", required=True)
    p.add_argument("--fields", required=True, help="JSON string of field values")

    p = sub.add_parser("list-records")
    p.add_argument("--app-token", required=True)
    p.add_argument("--table-id", required=True)

    # Tasks
    p = sub.add_parser("create-task")
    p.add_argument("--title", required=True)
    p.add_argument("--due", default=None)

    p = sub.add_parser("list-tasks")

    # Drive
    p = sub.add_parser("list-files")
    p.add_argument("--folder-token", required=True)

    # Users
    p = sub.add_parser("get-user")
    p.add_argument("--user-id", required=True)

    return parser


_COMMANDS = {
    "send-message": cmd_send_message,
    "reply-message": cmd_reply_message,
    "list-chats": cmd_list_chats,
    "list-messages": cmd_list_messages,
    "create-doc": cmd_create_doc,
    "read-doc": cmd_read_doc,
    "write-doc": cmd_write_doc,
    "list-calendar": cmd_list_calendar,
    "create-event": cmd_create_event,
    "create-bitable": cmd_create_bitable,
    "add-record": cmd_add_record,
    "list-records": cmd_list_records,
    "create-task": cmd_create_task,
    "list-tasks": cmd_list_tasks,
    "list-files": cmd_list_files,
    "get-user": cmd_get_user,
}


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    handler = _COMMANDS.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
