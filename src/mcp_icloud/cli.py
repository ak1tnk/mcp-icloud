"""`mcp-icloud` command: serve (default), login, status, logout."""

from __future__ import annotations

import argparse


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mcp-icloud", description=__doc__)
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("serve", help="run the MCP server on stdio (default)")
    login = sub.add_parser("login", help="log in interactively (Apple ID, password, 2FA)")
    login.add_argument("--apple-id", help="Apple ID email (prompted if omitted)")
    sub.add_parser("status", help="check whether the stored session is usable")
    sub.add_parser("logout", help="delete the stored session files")
    args = parser.parse_args(argv)

    if args.command == "login":
        from mcp_icloud.login import login_command

        return login_command(args.apple_id)
    if args.command == "status":
        from mcp_icloud.login import status_command

        return status_command()
    if args.command == "logout":
        from mcp_icloud.login import logout_command

        return logout_command()

    from mcp_icloud.server import main as serve

    return serve()
