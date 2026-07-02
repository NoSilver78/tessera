"""WebSocket API for the Tessera Area x Role matrix panel."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypedDict, cast

import voluptuous as vol
from homeassistant.components.websocket_api import async_register_command
from homeassistant.components.websocket_api import const as websocket_const
from homeassistant.components.websocket_api import decorators as websocket_decorators
from homeassistant.components.websocket_api.connection import ActiveConnection
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import floor_registry as fr
from homeassistant.helpers import label_registry as lr

from .config_flow import (
    add_area_grant,
    encode_grant,
    remove_area_grant,
    set_floor_grant,
    set_label_grant,
)
from .const import DOMAIN, MODE_ENFORCE
from .linter import LintReport
from .monitor import (
    MonitorPreview,
    compile_current,
    lint_current_preview,
    log_monitor_preview,
)
from .resolver import AreaEntityResolver
from .schema import (
    PermissionLeaf,
    TesseraConfigData,
    TesseraPolicyData,
    TesseraSchemaError,
)
from .store import TesseraStore, mutation_lock

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

TYPE_MATRIX_GET = "tessera/matrix/get"
TYPE_MATRIX_SET_GRANT = "tessera/matrix/set_grant"
TYPE_MATRIX_SET_FLOOR_GRANT = "tessera/matrix/set_floor_grant"
TYPE_MATRIX_SET_LABEL_GRANT = "tessera/matrix/set_label_grant"


class MatrixArea(TypedDict):
    """Area row metadata returned to the panel."""

    id: str
    name: str


class MatrixRole(TypedDict):
    """Role column metadata returned to the panel."""

    id: str
    name: str


class MatrixGrant(TypedDict):
    """Panel-facing counterpart of ``schema.PermissionLeaf``.

    Unlike the store leaf, both keys are always present (the panel renders an
    explicit tri-state cell); either value may be ``False``.
    """

    read: bool
    control: bool


class MatrixFloor(TypedDict):
    """Floor metadata for an area — labels, ordering, and floor-sourced grants."""

    id: str
    name: str
    level: int | None
    order: int


class MatrixLabel(TypedDict):
    """Label row metadata returned to the Labels board."""

    id: str
    name: str
    icon: str | None
    color: str | None


class MatrixResponse(TypedDict):
    """Complete matrix payload returned by Tessera WebSocket commands."""

    areas: list[MatrixArea]
    roles: list[MatrixRole]
    grants: dict[str, dict[str, MatrixGrant]]
    floor_grants: dict[str, dict[str, MatrixGrant]]
    area_floor: dict[str, MatrixFloor | None]
    labels: list[MatrixLabel]
    label_grants: dict[str, dict[str, MatrixGrant]]
    entities_by_label: dict[str, list[str]]
    entities_by_area: dict[str, list[str]]
    preview: MonitorPreview
    lint: LintReport


def async_register(hass: HomeAssistant) -> None:
    """Register Tessera matrix WebSocket commands."""
    async_register_command(hass, websocket_matrix_get)
    async_register_command(hass, websocket_matrix_set_grant)
    async_register_command(hass, websocket_matrix_set_floor_grant)
    async_register_command(hass, websocket_matrix_set_label_grant)


@websocket_decorators.require_admin
@websocket_decorators.websocket_command({vol.Required("type"): TYPE_MATRIX_GET})
@websocket_decorators.async_response
async def websocket_matrix_get(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return the current Area x Role grant matrix."""
    try:
        connection.send_result(msg["id"], await async_get_matrix(hass))
    except TesseraSchemaError as err:
        connection.send_error(msg["id"], "invalid_store", str(err))
    except LookupError as err:
        connection.send_error(msg["id"], websocket_const.ERR_NOT_FOUND, str(err))


@websocket_decorators.require_admin
@websocket_decorators.websocket_command(
    {
        vol.Required("type"): TYPE_MATRIX_SET_GRANT,
        vol.Required("area_id"): str,
        vol.Required("role_id"): str,
        vol.Required("read"): bool,
        vol.Required("control"): bool,
    }
)
@websocket_decorators.async_response
async def websocket_matrix_set_grant(
    hass: HomeAssistant,
    connection: ActiveConnection,
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
        connection.send_error(msg["id"], websocket_const.ERR_INVALID_FORMAT, str(err))
        return
    except LookupError as err:
        connection.send_error(msg["id"], websocket_const.ERR_NOT_FOUND, str(err))
        return

    connection.send_result(msg["id"], result)


@websocket_decorators.require_admin
@websocket_decorators.websocket_command(
    {
        vol.Required("type"): TYPE_MATRIX_SET_FLOOR_GRANT,
        vol.Required("floor_id"): str,
        vol.Required("role_id"): str,
        vol.Required("read"): bool,
        vol.Required("control"): bool,
    }
)
@websocket_decorators.async_response
async def websocket_matrix_set_floor_grant(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Persist one Floor x Role grant and return the refreshed matrix."""
    try:
        result = await async_set_matrix_floor_grant(
            hass,
            floor_id=cast(str, msg["floor_id"]),
            role_id=cast(str, msg["role_id"]),
            read=cast(bool, msg["read"]),
            control=cast(bool, msg["control"]),
        )
    except TesseraSchemaError as err:
        connection.send_error(msg["id"], websocket_const.ERR_INVALID_FORMAT, str(err))
        return
    except LookupError as err:
        connection.send_error(msg["id"], websocket_const.ERR_NOT_FOUND, str(err))
        return

    connection.send_result(msg["id"], result)


@websocket_decorators.require_admin
@websocket_decorators.websocket_command(
    {
        vol.Required("type"): TYPE_MATRIX_SET_LABEL_GRANT,
        vol.Required("label_id"): str,
        vol.Required("role_id"): str,
        vol.Required("read"): bool,
        vol.Required("control"): bool,
    }
)
@websocket_decorators.async_response
async def websocket_matrix_set_label_grant(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Persist one Label x Role grant and return the refreshed matrix."""
    try:
        result = await async_set_matrix_label_grant(
            hass,
            label_id=cast(str, msg["label_id"]),
            role_id=cast(str, msg["role_id"]),
            read=cast(bool, msg["read"]),
            control=cast(bool, msg["control"]),
        )
    except TesseraSchemaError as err:
        connection.send_error(msg["id"], websocket_const.ERR_INVALID_FORMAT, str(err))
        return
    except LookupError as err:
        connection.send_error(msg["id"], websocket_const.ERR_NOT_FOUND, str(err))
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
    # Serialize the whole load->mutate->save->compile under the store mutation
    # lock: concurrent set_grant calls (the panel fires one per toggled cell as
    # parallel @async_response tasks) would each reload the same base policy and
    # last-write-wins, silently dropping grants.
    async with mutation_lock(hass):
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
            policy = remove_area_grant(policy, encode_grant(area_id, role_id))

        await store.async_save_policy(policy)
        preview = await _refresh_preview(
            hass, entry_id, entry_data, store, config, policy
        )
        if config["mode"] == MODE_ENFORCE:
            # CXR-02: in enforce a saved grant must re-apply to the native auth
            # store, not merely refresh the read-only preview. Route through the
            # central fail-safe mode handler (the same path the options flow uses)
            # so the change runs the full guarded plan (lockout/D9/allow-only) and
            # falls safe to monitor on error. This runs INSIDE the held lock and
            # uses raw saves (fail-safe) — it must not re-acquire the lock. Late
            # import breaks the cycle (__init__ imports this module, not reverse).
            from . import _compile_for_mode_safely

            await _compile_for_mode_safely(hass, entry_id, entry_data)
        return _matrix_response(hass, config, policy, preview)


async def async_set_matrix_floor_grant(
    hass: HomeAssistant,
    *,
    floor_id: str,
    role_id: str,
    read: bool,
    control: bool,
) -> MatrixResponse:
    """Persist one schema-aware floor grant and return the refreshed matrix.

    A floor grant covers every area on the floor, so the refreshed payload
    updates all of those areas' Floor cells at once. In enforce a saved floor
    grant re-applies natively through the central guarded mode handler (CXR-02),
    like a direct area grant; the write is serialized under the mutation lock.
    """
    async with mutation_lock(hass):
        entry_id, entry_data = _get_loaded_entry_data(hass)
        store = cast(TesseraStore, entry_data["store"])
        config = await store.async_load_config()
        policy = await store.async_load_policy()

        known_floor_ids = {floor["id"] for floor in _area_floor(hass).values() if floor}
        if floor_id not in known_floor_ids:
            raise LookupError(f"Unknown Tessera floor: {floor_id}")
        if role_id not in config["roles"]:
            raise LookupError(f"Unknown Tessera role: {role_id}")

        policy = set_floor_grant(
            config,
            policy,
            floor_id=floor_id,
            role_id=role_id,
            read=read,
            control=control,
        )

        await store.async_save_policy(policy)
        preview = await _refresh_preview(
            hass, entry_id, entry_data, store, config, policy
        )
        if config["mode"] == MODE_ENFORCE:
            # CXR-02: enforce must re-apply the saved floor grant to native auth,
            # not merely refresh the preview. Same guarded path as area grants;
            # runs INSIDE the held lock with raw saves (must not re-acquire).
            from . import _compile_for_mode_safely

            await _compile_for_mode_safely(hass, entry_id, entry_data)
        return _matrix_response(hass, config, policy, preview)


async def async_set_matrix_label_grant(
    hass: HomeAssistant,
    *,
    label_id: str,
    role_id: str,
    read: bool,
    control: bool,
) -> MatrixResponse:
    """Persist one schema-aware label grant and return the refreshed matrix.

    A label grant covers every entity carrying the label — directly, or through
    its device or area (mirroring HA's own label expansion) — so the refreshed
    payload updates that label's row. In enforce a saved label grant re-applies
    natively through the central guarded mode handler (CXR-02), like an area
    grant; the write is serialized under the mutation lock.
    """
    async with mutation_lock(hass):
        entry_id, entry_data = _get_loaded_entry_data(hass)
        store = cast(TesseraStore, entry_data["store"])
        config = await store.async_load_config()
        policy = await store.async_load_policy()

        known_label_ids = {label["id"] for label in _labels(hass)}
        if label_id not in known_label_ids:
            raise LookupError(f"Unknown Tessera label: {label_id}")
        if role_id not in config["roles"]:
            raise LookupError(f"Unknown Tessera role: {role_id}")

        policy = set_label_grant(
            config,
            policy,
            label_id=label_id,
            role_id=role_id,
            read=read,
            control=control,
        )

        await store.async_save_policy(policy)
        preview = await _refresh_preview(
            hass, entry_id, entry_data, store, config, policy
        )
        if config["mode"] == MODE_ENFORCE:
            # CXR-02: enforce must re-apply the saved label grant to native auth,
            # not merely refresh the preview. Same guarded path as area/floor
            # grants; runs INSIDE the held lock with raw saves (must not re-acquire).
            from . import _compile_for_mode_safely

            await _compile_for_mode_safely(hass, entry_id, entry_data)
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
    lint_report = lint_current_preview(config, policy, resolver, compiled)
    preview = log_monitor_preview(
        compiled, mode=config["mode"], lint_report=lint_report
    )
    entry_data["compiled"] = compiled
    entry_data["lint"] = lint_report
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
    area_floor = _area_floor(hass)
    labels = _labels(hass)
    return {
        "areas": areas,
        "roles": roles,
        "grants": _grants(policy, areas, roles),
        "floor_grants": _floor_grants(policy, areas, roles, area_floor),
        "area_floor": area_floor,
        "labels": labels,
        "label_grants": _label_grants(policy, labels, roles),
        "entities_by_label": _entities_by_label(hass, labels),
        "entities_by_area": _entities_by_area(hass, areas),
        "preview": preview,
        "lint": preview["lint"],
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


def _area_floor(hass: HomeAssistant) -> dict[str, MatrixFloor | None]:
    """Return each area's floor (id + name), or None for a floorless area.

    The floor registry is only fetched once an area actually carries a floor,
    so instances (and tests) without floors never touch it.
    """
    floor_reg: Any = None
    floor_order: dict[str, int] = {}
    result: dict[str, MatrixFloor | None] = {}
    for area in ar.async_get(hass).async_list_areas():
        floor_id = area.floor_id
        if not floor_id:
            result[area.id] = None
            continue
        if floor_reg is None:
            floor_reg = fr.async_get(hass)
            # Registry order is the physical-ish fallback the panel uses to sort
            # floors that carry no explicit ``level``.
            floor_order = {
                floor.floor_id: index
                for index, floor in enumerate(floor_reg.async_list_floors())
            }
        floor = floor_reg.async_get_floor(floor_id)
        result[area.id] = {
            "id": floor_id,
            "name": floor.name if floor is not None else floor_id,
            "level": floor.level if floor is not None else None,
            "order": floor_order.get(floor_id, 0),
        }
    return result


def _floor_grants(
    policy: TesseraPolicyData,
    areas: list[MatrixArea],
    roles: list[MatrixRole],
    area_floor: dict[str, MatrixFloor | None],
) -> dict[str, dict[str, MatrixGrant]]:
    """Return the floor-sourced grant for each visible Area x Role cell.

    A cell's floor source is the grant on the area's *floor* (if any) — the
    other half of the provenance split the panel renders next to the direct
    area grant, so an overlap (both set) is visible as a redundant double.
    """
    role_ids = [role["id"] for role in roles]
    floor_grants_policy = policy["floor_grants"]
    result: dict[str, dict[str, MatrixGrant]] = {}
    for area in areas:
        area_id = area["id"]
        floor = area_floor.get(area_id)
        role_map = floor_grants_policy.get(floor["id"], {}) if floor else {}
        result[area_id] = {
            role_id: _grant_leaf(role_map.get(role_id)) for role_id in role_ids
        }
    return result


def _labels(hass: HomeAssistant) -> list[MatrixLabel]:
    """Return sorted Home Assistant labels for the Labels board rows."""
    registry = lr.async_get(hass)
    return [
        {
            "id": label.label_id,
            "name": label.name,
            "icon": label.icon,
            "color": label.color,
        }
        for label in sorted(registry.async_list_labels(), key=lambda item: item.name)
    ]


def _label_grants(
    policy: TesseraPolicyData,
    labels: list[MatrixLabel],
    roles: list[MatrixRole],
) -> dict[str, dict[str, MatrixGrant]]:
    """Return explicit bool grants for each visible Label x Role cell."""
    role_ids = [role["id"] for role in roles]
    result: dict[str, dict[str, MatrixGrant]] = {}
    for label in labels:
        label_id = label["id"]
        role_map = policy["label_grants"].get(label_id, {})
        result[label_id] = {
            role_id: _grant_leaf(role_map.get(role_id)) for role_id in role_ids
        }
    return result


def _entities_by_label(
    hass: HomeAssistant, labels: list[MatrixLabel]
) -> dict[str, list[str]]:
    """Return the entity ids Tessera resolves for each label (for the expand)."""
    resolver = AreaEntityResolver.from_hass(hass)
    return {
        label["id"]: list(resolver.entity_ids_for_label(label["id"]))
        for label in labels
    }


def _entities_by_area(
    hass: HomeAssistant, areas: list[MatrixArea]
) -> dict[str, list[str]]:
    """Return the entity ids Tessera resolves for each area (for the expand)."""
    resolver = AreaEntityResolver.from_hass(hass)
    resolution = resolver.entity_ids_for_areas([area["id"] for area in areas])
    return {area["id"]: list(resolution.by_area.get(area["id"], ())) for area in areas}


def _get_loaded_entry_data(hass: HomeAssistant) -> tuple[str, dict[str, Any]]:
    """Return the single loaded Tessera entry data bucket.

    Tessera is a single-config-entry integration (``unique_id == DOMAIN``), so
    at most one entry bucket exists; the first sorted match is that entry.
    """
    domain_data = cast(dict[str, Any], hass.data.get(DOMAIN, {}))
    for entry_id, entry_data in sorted(domain_data.items()):
        if isinstance(entry_data, dict) and "store" in entry_data:
            return entry_id, entry_data
    raise LookupError("Tessera is not loaded")
