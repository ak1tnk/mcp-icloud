"""Interactive commands the owner runs in a terminal: login, status, logout."""

from __future__ import annotations

import getpass
import sys

from pyicloud import PyiCloudService
from pyicloud.exceptions import PyiCloudConnectionException, PyiCloudFailedLoginException

from mcp_icloud import config
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
            if api.fido2_devices or not api.request_2fa_code():
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
    print(
        "This only deletes local files. To revoke the session at Apple, sign out of the "
        "browser session at https://account.apple.com (Devices) or change the Apple ID password."
    )
    return 0
