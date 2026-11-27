"""Interactive commands the owner runs in a terminal: login, status, logout."""

from __future__ import annotations

import getpass
import sys

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
