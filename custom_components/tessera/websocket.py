"""WebSocket API for the Tessera Area x Role matrix panel."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypedDict, cast

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.helpers import area_registry as ar

from .config_flow import add_area_grant, remove_area_grant
from .const import DOMAIN
from .monitor import MonitorPreview, compile_current, log_monitor_preview
from .resolver import AreaEntityResolver
from .schema import (
    PermissionLeaf,
    TesseraConfigData,
    TesseraPolicyData,
    TesseraSchemaError,
)
from .store import TesseraStore

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

TYPE_MATRIX_GET = "tessera/matrix/get"
TYPE_MATRIX_SET_GRANT = "tessera/matrix/set_grant"


class MatrixArea(TypedDict):
    """Area row metadata returned to the panel."""

    id: str
    name: str


class MatrixRole(TypedDict):
    """Role column metadata returned to the panel."""

    id: str
    name: str


class MatrixGrant(TypedDict):
    """Normalized permission leaf returned to the panel."""

    read: bool
    control: bool


class MatrixResponse(TypedDict):
    """Complete matrix payload returned by Tessera WebSocket commands."""

    areas: list[MatrixArea]
    roles: list[MatrixRole]
    grants: dict[str, dict[str, MatrixGrant]]
    preview: MonitorPreview


def async_register(hass: HomeAssistant) -> None:
    """Register Tessera matrix WebSocket commands."""
    websocket_api.async_register_command(hass, websocket_matrix_get)
    websocket_api.async_register_command(hass, websocket_matrix_set_grant)


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): TYPE_MATRIX_GET})
@websocket_api.async_response
async def websocket_matrix_get(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return the current Area x Role grant matrix."""
    try:
        connection.send_result(msg["id"], await async_get_matrix(hass))
    except TesseraSchemaError as err:
        connection.send_error(msg["id"], "invalid_store", str(err))
    except LookupError as err:
        connection.send_error(msg["id"], websocket_api.ERR_NOT_FOUND, str(err))


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): TYPE_MATRIX_SET_GRANT,
        vol.Required("area_id"): str,
        vol.Required("role_id"): str,
        vol.Required("read"): bool,
        vol.Required("control"): bool,
    }
)
@websocket_api.async_response
async def websocket_matrix_set_grant(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Persist one Area x Role grant and return the refreshed matrix."""
    try:
        result = await async_set_matrix_grant(
            hass,
            area_id=cast(str, msg["area_id"]),
            role_id=cast(str, msg["role_id"]),
            read=cast(bool, msg["read"]),
            control=cast(bool, msg["control"]),
        )
    except TesseraSchemaError as err:
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, str(err))
        return
    except LookupError as err:
        connection.send_error(msg["id"], websocket_api.ERR_NOT_FOUND, str(err))
        return

    connection.send_result(msg["id"], result)


async def async_get_matrix(hass: HomeAssistant) -> MatrixResponse:
    """Load stores and return a normalized matrix payload."""
    entry_id, entry_data = _get_loaded_entry_data(hass)
    store = cast(TesseraStore, entry_data["store"])
    config = await store.async_load_config()
    policy = await store.async_load_policy()
    preview = await _refresh_preview(hass, entry_id, entry_data, store, config, policy)
    return _matrix_response(hass, config, policy, preview)


async def async_set_matrix_grant(
    hass: HomeAssistant,
    *,
    area_id: str,
    role_id: str,
    read: bool,
    control: bool,
) -> MatrixResponse:
    """Persist one schema-aware grant and return the refreshed matrix payload."""
    entry_id, entry_data = _get_loaded_entry_data(hass)
    store = cast(TesseraStore, entry_data["store"])
    config = await store.async_load_config()
    policy = await store.async_load_policy()

    area_ids = {area["id"] for area in _areas(hass)}
    if area_id not in area_ids:
        raise LookupError(f"Unknown Tessera area: {area_id}")
    if role_id not in config["roles"]:
        raise LookupError(f"Unknown Tessera role: {role_id}")

    if read or control:
        policy = add_area_grant(
            config,
            policy,
            area_id=area_id,
            role_id=role_id,
            read=read,
            control=control,
        )
    else:
        policy = remove_area_grant(policy, f"{area_id}::{role_id}")

    await store.async_save_policy(policy)
    preview = await _refresh_preview(hass, entry_id, entry_data, store, config, policy)
    return _matrix_response(hass, config, policy, preview)


async def _refresh_preview(
    hass: HomeAssistant,
    entry_id: str,
    entry_data: dict[str, Any],
    store: TesseraStore,
    config: TesseraConfigData,
    policy: TesseraPolicyData,
) -> MonitorPreview:
    """Compile and store the read-only monitor preview for the matrix panel."""
    resolver = AreaEntityResolver.from_hass(hass)
    compiled = await compile_current(store, resolver, config=config, policy=policy)
    preview = log_monitor_preview(compiled, mode=config["mode"])
    entry_data["compiled"] = compiled
    entry_data["preview"] = preview
    entry_data["store"] = store
    cast(dict[str, Any], hass.data.setdefault(DOMAIN, {}))[entry_id] = entry_data
    return preview


def _matrix_response(
    hass: HomeAssistant,
    config: TesseraConfigData,
    policy: TesseraPolicyData,
    preview: MonitorPreview,
) -> MatrixResponse:
    """Build the panel payload from schema-valid config and policy."""
    areas = _areas(hass)
    roles = _roles(config)
    return {
        "areas": areas,
        "roles": roles,
        "grants": _grants(policy, areas, roles),
        "preview": preview,
    }


def _areas(hass: HomeAssistant) -> list[MatrixArea]:
    """Return sorted Home Assistant areas for matrix rows."""
    registry = ar.async_get(hass)
    return [
        {"id": area.id, "name": area.name}
        for area in sorted(registry.async_list_areas(), key=lambda item: item.name)
    ]


def _roles(config: TesseraConfigData) -> list[MatrixRole]:
    """Return sorted Tessera roles for matrix columns."""
    return [
        {"id": role_id, "name": role.get("name") or role_id}
        for role_id, role in sorted(config["roles"].items())
    ]


def _grants(
    policy: TesseraPolicyData,
    areas: list[MatrixArea],
    roles: list[MatrixRole],
) -> dict[str, dict[str, MatrixGrant]]:
    """Return explicit bool grants for each visible Area x Role cell."""
    role_ids = [role["id"] for role in roles]
    grants: dict[str, dict[str, MatrixGrant]] = {}
    for area in areas:
        area_id = area["id"]
        role_map = policy["area_grants"].get(area_id, {})
        grants[area_id] = {
            role_id: _grant_leaf(role_map.get(role_id)) for role_id in role_ids
        }
    return grants


def _grant_leaf(leaf: PermissionLeaf | None) -> MatrixGrant:
    """Normalize an optional store leaf into explicit panel booleans."""
    return {
        "read": bool(leaf and leaf.get("read") is True),
        "control": bool(leaf and leaf.get("control") is True),
    }


def _get_loaded_entry_data(hass: HomeAssistant) -> tuple[str, dict[str, Any]]:
    """Return the first loaded Tessera entry data bucket."""
    domain_data = cast(dict[str, Any], hass.data.get(DOMAIN, {}))
    for entry_id, entry_data in sorted(domain_data.items()):
        if isinstance(entry_data, dict) and "store" in entry_data:
            return entry_id, entry_data
    raise LookupError("Tessera is not loaded")
