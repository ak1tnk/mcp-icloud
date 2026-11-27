"""Interactive commands the owner runs in a terminal: login, status, logout."""

from __future__ import annotations


def login_command(apple_id: str | None) -> int:
    raise NotImplementedError  # implemented in the auth slice


def status_command() -> int:
    raise NotImplementedError  # implemented in the auth slice


def logout_command() -> int:
    raise NotImplementedError  # implemented in the auth slice
