"""Hide My Email tools."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

if TYPE_CHECKING:
    from mcp_icloud.server import ApiProvider


def _normalize(raw: dict[str, Any]) -> dict[str, Any]:
    if isinstance(raw.get("hme"), dict):
        raw = raw["hme"]
    timestamp = raw.get("createTimestamp")
    created_at = None
    if type(timestamp) is int:
        created_at = datetime.fromtimestamp(timestamp / 1000, UTC).isoformat()
    return {
        "email": raw.get("hme"),
        "anonymous_id": raw.get("anonymousId"),
        "label": raw.get("label"),
        "note": raw.get("note"),
        "active": raw.get("isActive"),
        "forward_to": raw.get("forwardToEmail"),
        "domain": raw.get("domain"),
        "created_at": created_at,
    }


def _required(value: str, name: str) -> str:
    value = value.strip()
    if not value:
        raise ToolError(f"{name} must not be empty")
    return value


def register(server: MCPServer, provider: ApiProvider) -> None:
    @server.tool()
    def hme_list() -> dict[str, Any]:
        """List all active and inactive Hide My Email addresses."""
        addresses = provider.call(lambda api: [_normalize(raw) for raw in api.hidemyemail])
        return {"count": len(addresses), "addresses": addresses}

    @server.tool()
    def hme_generate() -> dict[str, Any]:
        """Generate a candidate address. It is not saved until hme_reserve."""
        email = provider.call(lambda api: api.hidemyemail.generate())
        if email is None:
            raise ToolError("iCloud did not generate an address")
        return {"email": email}

    @server.tool()
    def hme_reserve(email: str, label: str, note: str = "") -> dict[str, Any]:
        """Save a generated Hide My Email address with a label and optional note."""
        email = _required(email, "email")
        label = _required(label, "label")
        raw = provider.call(lambda api: api.hidemyemail.reserve(email, label, note))
        if not raw:
            raise ToolError("iCloud did not reserve the address")
        return _normalize(raw)

    @server.tool()
    def hme_update(
        anonymous_id: str, label: str | None = None, note: str | None = None
    ) -> dict[str, Any]:
        """Update an address's label or note, preserving fields that are omitted."""
        anonymous_id = _required(anonymous_id, "anonymous_id")
        if label is None and note is None:
            raise ToolError("Provide label or note")
        raw = provider.call(lambda api: api.hidemyemail[anonymous_id])
        if not raw:
            raise ToolError("alias not found")
        current = _normalize(raw)
        new_label = label or current["label"]
        new_note = note if note is not None else current["note"] or ""
        # The update response shape is unverified, so the re-read below decides success.
        provider.call(
            lambda api: api.hidemyemail.update_metadata(anonymous_id, new_label, new_note)
        )
        raw = provider.call(lambda api: api.hidemyemail[anonymous_id])
        if not raw:
            raise ToolError("alias not found")
        alias = _normalize(raw)
        if alias["label"] != new_label or (alias["note"] or "") != new_note:
            raise ToolError("iCloud did not confirm the update")
        return alias

    @server.tool()
    def hme_deactivate(anonymous_id: str) -> dict[str, Any]:
        """Stop forwarding an address. The address can be reactivated later."""
        anonymous_id = _required(anonymous_id, "anonymous_id")
        provider.call(lambda api: api.hidemyemail.deactivate(anonymous_id))
        raw = provider.call(lambda api: api.hidemyemail[anonymous_id])
        if not raw:
            raise ToolError("alias not found")
        alias = _normalize(raw)
        if alias["active"] is not False:
            raise ToolError("iCloud did not confirm the change to inactive")
        return alias

    @server.tool()
    def hme_reactivate(anonymous_id: str) -> dict[str, Any]:
        """Resume forwarding a previously deactivated address."""
        anonymous_id = _required(anonymous_id, "anonymous_id")
        provider.call(lambda api: api.hidemyemail.reactivate(anonymous_id))
        raw = provider.call(lambda api: api.hidemyemail[anonymous_id])
        if not raw:
            raise ToolError("alias not found")
        alias = _normalize(raw)
        if alias["active"] is not True:
            raise ToolError("iCloud did not confirm the change to active")
        return alias
