"""Interactive commands the owner runs in a terminal: login, status, logout."""

from __future__ import annotations

import getpass
import imaplib
import os
import smtplib
import ssl
import sys

from mcp.server.mcpserver.exceptions import ToolError
from pyicloud import PyiCloudService
from pyicloud.exceptions import (
    PyiCloudAPIResponseException,
    PyiCloudConnectionException,
    PyiCloudFailedLoginException,
    PyiCloudNoTrustedNumberAvailable,
    PyiCloudTrustedDevicePromptException,
    PyiCloudTrustedDeviceVerificationException,
)

from mcp_icloud import config
from mcp_icloud.services.mail.backend import selected_backend
from mcp_icloud.services.mail.config import (
    IMAP_HOST,
    IMAP_PORT,
    SMTP_HOST,
    SMTP_PORT,
    USER_ENV,
    configured_mail,
    write_mail_login,
)
from mcp_icloud.session import NotLoggedInError, load_api


def login_command(apple_id: str | None) -> int:
    apple_id = apple_id if apple_id is not None else input("Apple ID: ").strip()
    if not apple_id:
        print("Apple ID must not be empty.", file=sys.stderr)
        return 2
    password = getpass.getpass("Apple ID password: ")
    directory = config.session_dir()
    config.ensure_private_dir(directory)
    try:
        api = PyiCloudService(apple_id, password, cookie_directory=str(directory))
        if api.requires_2fa:
            try:
                needs_security_key = bool(api.fido2_devices) or not api.request_2fa_code()
            except (PyiCloudConnectionException, PyiCloudTrustedDevicePromptException):
                raise
            except PyiCloudAPIResponseException:
                print(
                    "Could not request a 2FA code. If a trusted Apple device already "
                    "shows a code, enter it below."
                )
                api.use_existing_trusted_device_code()
                needs_security_key = False
            if needs_security_key:
                print(
                    "This account needs a security key for 2FA, which mcp-icloud "
                    "does not support yet.",
                    file=sys.stderr,
                )
                return 1
            if api.two_factor_delivery_notice:
                print(api.two_factor_delivery_notice)
            for _ in range(3):
                if api.validate_2fa_code(input("2FA code: ").strip()):
                    break
            else:
                print("The 2FA code was not accepted after 3 attempts.", file=sys.stderr)
                return 1
            if not api.is_trusted_session:
                api.trust_session()
            if not api.is_trusted_session:
                print("Could not establish a trusted session.", file=sys.stderr)
                return 1
        elif api.requires_2sa:
            print(
                "Legacy two-step verification is not supported; enable two-factor "
                "authentication for this Apple ID.",
                file=sys.stderr,
            )
            return 1
    except PyiCloudNoTrustedNumberAvailable:
        print(
            "Two-factor authentication needs a trusted phone number, but Apple returned none.",
            file=sys.stderr,
        )
        return 1
    except (PyiCloudTrustedDevicePromptException, PyiCloudTrustedDeviceVerificationException):
        print(
            "Apple rejected the trusted-device 2FA step. Retry `mcp-icloud login`.",
            file=sys.stderr,
        )
        return 1
    except PyiCloudFailedLoginException as exc:
        print(
            f"Login failed: {type(exc).__name__}. Check the Apple ID and password.",
            file=sys.stderr,
        )
        return 1
    except PyiCloudConnectionException:
        print("Could not reach Apple. Check the network and retry.", file=sys.stderr)
        return 1
    config.write_apple_id(directory, apple_id)
    config.ensure_private_dir(directory)
    print(f"Logged in as {apple_id}. Session stored in {directory}.")
    print(
        "To use it on another machine (e.g. a Linux VM), copy this directory there "
        "and set MCP_ICLOUD_SESSION_DIR if the path differs."
    )
    return 0


def status_command() -> int:
    print(_mail_status_line())
    try:
        api = load_api()
    except NotLoggedInError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except PyiCloudConnectionException:
        print("Could not reach Apple. Check the network and retry.", file=sys.stderr)
        return 1
    print(f"Session OK for {api.account_name} ({config.session_dir()})")
    return 0


def logout_command() -> int:
    remote_logout_confirmed = False
    try:
        api = load_api()
        result = api.logout()
        remote_logout_confirmed = bool(result.get("remote_logout_confirmed"))
        if remote_logout_confirmed:
            print("Signed out of this session at Apple.")
        else:
            print("Apple did not confirm the sign-out.")
    except NotLoggedInError:
        print("No usable session; skipped signing out at Apple.")
    except PyiCloudConnectionException:
        print("Could not reach Apple; skipped signing out at Apple.")
    directory = config.session_dir()
    removed = 0
    if directory.is_dir():
        for child in directory.iterdir():
            if (child.name == "account.json" or child.suffix in {".session", ".cookiejar"}) and (
                child.is_file() or child.is_symlink()
            ):
                child.unlink()
                removed += 1
    print(f"Removed {removed} local session files.")
    if not remote_logout_confirmed:
        print(
            "To revoke it at Apple, change the Apple ID password or review signed-in devices "
            "at https://account.apple.com."
        )
    return 0


def _mail_status_line() -> str:
    mail = configured_mail()
    try:
        backend = selected_backend()
    except ToolError as exc:
        return f"Mail: {exc}"
    if backend == "web":
        return "Mail: web backend (uses the mcp-icloud login session; experimental)"
    if mail:
        return f"Mail: IMAP backend, configured for {mail[0]} ({mail[1]})"
    return "Mail: IMAP backend, not configured (run mcp-icloud mail-login)"


def mail_login_command(user: str | None) -> int:
    if user is None:
        default = os.environ.get(USER_ENV) or config.stored_apple_id(config.session_dir()) or ""
        user = input(f"iCloud Mail address [{default}]: ").strip() or default
    if not user:
        print("iCloud Mail address must not be empty.", file=sys.stderr)
        return 2
    password = getpass.getpass("App-specific password: ")
    try:
        imap = imaplib.IMAP4_SSL(
            IMAP_HOST, IMAP_PORT, ssl_context=ssl.create_default_context(), timeout=30
        )
        imap.login(user, password)
        imap.logout()
        smtp = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30)
        smtp.starttls(context=ssl.create_default_context())
        smtp.login(user, password)
        smtp.quit()
    except (imaplib.IMAP4.error, smtplib.SMTPException, OSError) as exc:
        error = str(exc).replace(password, "***") if password else str(exc)
        print(f"Could not verify the Mail login: {error}", file=sys.stderr)
        return 1
    path = write_mail_login(user, password)
    print(f"Mail configured for {user}. Stored in {path}.")
    return 0


def mail_logout_command() -> int:
    path = config.session_dir() / "mail.json"
    if path.exists():
        path.unlink()
        print("Removed the stored Mail password.")
    else:
        print("No stored Mail password.")
    print("The app-specific password stays valid until you revoke it at https://account.apple.com.")
    return 0
