"""Interactive setup wizard. Guides user through Feishu app configuration."""

import subprocess
import sys
import time
import webbrowser
from pathlib import Path

_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config.toml"

_FEISHU_CONSOLE_URL = "https://open.feishu.cn/app/"
_LARK_CONSOLE_URL = "https://open.larksuite.com/app/"

_REQUIRED_SCOPES = [
    "im:message",
    "im:message:send_as_bot",
    "im:chat:readonly",
    "contact:user.id:readonly",
]

_OPTIONAL_SCOPES = [
    "docx:document",
    "drive:drive",
    "calendar:calendar",
    "bitable:bitable",
    "task:task",
    "wiki:wiki",
]


def main() -> None:
    print("=" * 60)
    print("  Augur Setup Wizard")
    print("  飞书机器人配置向导")
    print("=" * 60)
    print()

    # Step 1: choose platform
    platform = _ask_choice(
        "Which platform? / 选择平台",
        [("feishu", "飞书 (open.feishu.cn)"), ("lark", "Lark (open.larksuite.com)")],
    )
    console_url = _FEISHU_CONSOLE_URL if platform == "feishu" else _LARK_CONSOLE_URL
    domain = "https://open.feishu.cn" if platform == "feishu" else "https://open.larksuite.com"

    # Step 2: create app
    _step("Step 1: Create App / 创建应用")
    print("  Please create an Enterprise Custom App in the developer console.")
    print("  请在开发者后台创建「企业自建应用」。")
    print()
    print(f"  Console URL: {console_url}")
    print()
    print("  Steps / 步骤:")
    print("    1. Click '创建企业自建应用' / 'Create Custom App'")
    print("    2. Fill in app name (e.g., 'Augur Bot') and description")
    print("    3. Click '创建' / 'Create'")
    print()

    if _ask_yn("Open browser? / 打开浏览器？"):
        webbrowser.open(console_url)

    _wait("Press Enter when done... / 完成后按回车...")

    # Step 3: get credentials
    _step("Step 2: Get Credentials / 获取凭证")
    print("  In your app page, go to:")
    print("  '凭证与基础信息' / 'Credentials & Basic Info'")
    print()

    app_id = _ask_input("App ID (starts with cli_)").strip()
    if not app_id.startswith("cli_"):
        print("  Warning: App ID usually starts with 'cli_'", file=sys.stderr)

    app_secret = _ask_input("App Secret").strip()

    # Verify immediately
    print()
    print("  Verifying credentials...", end=" ", flush=True)
    ok, msg = _verify_credentials(app_id, app_secret, domain)
    if ok:
        print("OK")
    else:
        print(f"FAILED: {msg}")
        if not _ask_yn("Continue anyway? / 仍然继续？"):
            sys.exit(1)

    # Step 4: enable bot capability (BEFORE events — required by Feishu)
    _step("Step 3: Enable Bot / 启用机器人能力")
    print("  In your app page, go to:")
    print("  '应用能力 > 机器人' / 'App Features > Bot'")
    print()
    print("  Enable the bot capability.")
    print("  启用机器人能力。")
    _wait("\nPress Enter when done... / 完成后按回车...")

    # Step 5: configure permissions
    _step("Step 4: Configure Permissions / 配置权限")
    print("  In your app page, go to:")
    print("  '权限管理' / 'Permissions & Scopes'")
    print()
    print("  Required / 必须开通:")
    for s in _REQUIRED_SCOPES:
        print(f"    + {s}")
    print()
    print("  Recommended / 推荐开通:")
    for s in _OPTIONAL_SCOPES:
        print(f"    + {s}")
    _wait("\nPress Enter when done... / 完成后按回车...")

    # Step 6: save config FIRST, so we can start the bot
    _step("Step 5: Save Configuration / 保存配置")
    encrypt_key = _ask_input("Encrypt Key (optional, Enter to skip)").strip()
    verification_token = _ask_input("Verification Token (optional, Enter to skip)").strip()

    _write_config(
        app_id=app_id,
        app_secret=app_secret,
        domain=domain,
        encrypt_key=encrypt_key,
        verification_token=verification_token,
    )
    print(f"\n  Config saved to: {_CONFIG_PATH}")

    # Step 7: WebSocket — start bot to establish connection, THEN save in console
    _step("Step 6: Configure Events / 配置事件订阅")
    print("  Feishu requires an active WebSocket connection before")
    print("  you can enable persistent connection mode.")
    print("  飞书要求先建立一次 WebSocket 连接才能保存长连接配置。")
    print()
    print("  We will now start the bot in the background to establish")
    print("  the connection. Keep it running while you configure events.")
    print()

    if _ask_yn("Start bot now? / 现在启动 bot？"):
        bot_proc = _start_bot_background()
        print()
        print("  Bot starting... waiting 5 seconds for connection...")
        time.sleep(5)
        print("  Bot should be connected now.")
    else:
        bot_proc = None
        print("  Please start the bot manually in another terminal:")
        print("    python -m augur")
        _wait("\n  Press Enter when the bot is running... / bot 运行后按回车...")

    print()
    print("  Now go to your app page:")
    print("  '事件与回调' / 'Events & Callbacks'")
    print()
    print("  1. Select 'Receive events through persistent connection'")
    print("     选择「使用长连接接收事件」")
    print("  2. Click Save (should succeed now)")
    print("     点击保存（现在应该能成功了）")
    print("  3. Click 'Add Events' → Messenger → check:")
    print("     点击「添加事件」→ Messenger → 勾选:")
    print("       + im.message.receive_v1 (Receive messages)")
    print("  4. Click 'Add' to confirm")
    _wait("\nPress Enter when done... / 完成后按回车...")

    # Stop background bot if we started it
    if bot_proc:
        bot_proc.terminate()
        bot_proc.wait()
        print("  Background bot stopped.")

    # Step 8: publish
    _step("Step 7: Publish / 发布应用版本")
    print("  Go to '版本管理与发布' / 'Version Management & Release'")
    print("  Create a new version and submit for admin approval.")
    print("  创建版本并提交管理员审批。")
    _wait("\nPress Enter when published... / 发布后按回车...")

    # Done
    print()
    print("=" * 60)
    print("  Setup complete! Run the bot:")
    print()
    print("  python -m augur")
    print("=" * 60)


# ============================================================================
# Helpers
# ============================================================================


def _verify_credentials(app_id: str, app_secret: str, domain: str) -> tuple[bool, str]:
    """Verify credentials by requesting a tenant_access_token."""
    try:
        import requests
        resp = requests.post(
            f"{domain}/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": app_id, "app_secret": app_secret},
            timeout=10,
        )
        data = resp.json()
        if data.get("code") == 0:
            return True, ""
        return False, data.get("msg", "unknown error")
    except Exception as e:
        return False, str(e)


def _start_bot_background() -> subprocess.Popen:
    """Start the augur bot as a background subprocess."""
    return subprocess.Popen(
        [sys.executable, "-m", "augur"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )


def _write_config(
    app_id: str,
    app_secret: str,
    domain: str,
    encrypt_key: str,
    verification_token: str,
) -> None:
    """Write config.toml with the provided values."""
    lines = [
        "# Augur config — generated by setup wizard",
        "",
        "[feishu]",
        f'app_id = "{app_id}"',
        f'app_secret = "{app_secret}"',
    ]
    if domain != "https://open.feishu.cn":
        lines.append(f'domain = "{domain}"')
    if encrypt_key:
        lines.append(f'encrypt_key = "{encrypt_key}"')
    if verification_token:
        lines.append(f'verification_token = "{verification_token}"')

    lines += [
        "",
        "[claude]",
        '# api_key = ""    # uncomment to use API key mode',
        'model = "claude-sonnet-4-5"',
        "",
        "[bot]",
        '# working_dir = "~/Desktop/Toys/augur/data"',
        "",
    ]

    _CONFIG_PATH.write_text("\n".join(lines), encoding="utf-8")


def _step(title: str) -> None:
    print()
    print("-" * 60)
    print(f"  {title}")
    print("-" * 60)
    print()


def _ask_input(prompt: str) -> str:
    return input(f"  {prompt}: ")


def _ask_yn(prompt: str) -> bool:
    ans = input(f"  {prompt} [Y/n] ").strip().lower()
    return ans in ("", "y", "yes")


def _ask_choice(prompt: str, options: list[tuple[str, str]]) -> str:
    print(f"  {prompt}")
    for i, (key, label) in enumerate(options, 1):
        print(f"    {i}. {label}")
    while True:
        ans = input("  > ").strip()
        if ans.isdigit() and 1 <= int(ans) <= len(options):
            return options[int(ans) - 1][0]
        print("  Invalid choice.")


def _wait(prompt: str) -> None:
    input(f"  {prompt}")


if __name__ == "__main__":
    main()
