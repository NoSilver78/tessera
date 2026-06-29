"""Schema validation for Tessera's phase-1 store data."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal, TypedDict, cast

from .const import MODE_OFF, MODES, STORAGE_VERSION

PermissionKey = Literal["read", "control"]


class PermissionLeaf(TypedDict, total=False):
    """Allowed native HA permission leaf shape."""

    read: bool
    control: bool


class RoleData(TypedDict, total=False):
    """Role metadata stored by Tessera."""

    name: str
    description: str


class MembershipData(TypedDict):
    """Role membership mappings from users and external groups."""

    by_user: dict[str, list[str]]
    by_group: dict[str, list[str]]


class TesseraConfigData(TypedDict):
    """Tessera configuration store payload."""

    version: int
    mode: str
    roles: dict[str, RoleData]
    membership: MembershipData


class _TesseraPolicyRequiredData(TypedDict):
    """Required Tessera policy store fields."""

    version: int
    area_grants: dict[str, dict[str, PermissionLeaf]]
    entity_overrides: dict[str, dict[str, PermissionLeaf]]


class TesseraPolicyData(_TesseraPolicyRequiredData, total=False):
    """Tessera policy store payload."""

    staging: dict[str, Any]


class TesseraSchemaError(ValueError):
    """Raised when Tessera store data does not match the phase-1 schema."""


def default_config_data() -> TesseraConfigData:
    """Return the default Tessera configuration payload.

    Returns:
        A new mutable configuration payload using monitor-safe defaults.
    """
    return {
        "version": STORAGE_VERSION,
        "mode": MODE_OFF,
        "roles": {},
        "membership": {"by_user": {}, "by_group": {}},
    }


def default_policy_data() -> TesseraPolicyData:
    """Return the default Tessera policy payload.

    Returns:
        A new mutable policy payload with no grants.
    """
    return {
        "version": STORAGE_VERSION,
        "area_grants": {},
        "entity_overrides": {},
        "staging": {},
    }


def validate_config_data(data: object) -> TesseraConfigData:
    """Validate and normalize Tessera configuration store data.

    Args:
        data: Candidate payload loaded from Home Assistant storage.

    Returns:
        A deep-copied, schema-valid configuration payload.

    Raises:
        TesseraSchemaError: If the payload violates the phase-1 schema.
    """
    payload = _require_mapping(data, "config")
    _require_version(payload, "config")

    mode = payload.get("mode")
    if not isinstance(mode, str) or mode not in MODES:
        raise TesseraSchemaError("config.mode must be one of off, monitor, enforce")

    roles_raw = _require_mapping(payload.get("roles"), "config.roles")
    roles: dict[str, RoleData] = {}
    for role_id, role_data in roles_raw.items():
        role_key = _require_non_empty_string(role_id, "role id")
        role_payload = _require_mapping(role_data, f"config.roles.{role_key}")
        role: RoleData = {}
        if "name" in role_payload:
            role["name"] = _require_non_empty_string(
                role_payload["name"], f"config.roles.{role_key}.name"
            )
        if "description" in role_payload:
            description = role_payload["description"]
            if not isinstance(description, str):
                raise TesseraSchemaError(
                    f"config.roles.{role_key}.description must be a string"
                )
            role["description"] = description
        roles[role_key] = role

    membership_raw = _require_mapping(payload.get("membership"), "config.membership")
    membership: MembershipData = {
        "by_user": _validate_membership_map(
            membership_raw.get("by_user"), "config.membership.by_user"
        ),
        "by_group": _validate_membership_map(
            membership_raw.get("by_group"), "config.membership.by_group"
        ),
    }

    return {
        "version": STORAGE_VERSION,
        "mode": mode,
        "roles": roles,
        "membership": membership,
    }


def validate_policy_data(data: object) -> TesseraPolicyData:
    """Validate and normalize Tessera policy store data.

    Args:
        data: Candidate policy payload loaded from Home Assistant storage.

    Returns:
        A deep-copied, schema-valid policy payload.

    Raises:
        TesseraSchemaError: If grants use an unsafe or unsupported shape.
    """
    payload = _require_mapping(data, "policy")
    _require_version(payload, "policy")

    policy: TesseraPolicyData = {
        "version": STORAGE_VERSION,
        "area_grants": _validate_grant_matrix(
            payload.get("area_grants"), "policy.area_grants"
        ),
        "entity_overrides": _validate_grant_matrix(
            payload.get("entity_overrides"), "policy.entity_overrides"
        ),
        "staging": deepcopy(
            _require_mapping(payload.get("staging", {}), "policy.staging")
        ),
    }
    return policy


def _validate_membership_map(data: object, path: str) -> dict[str, list[str]]:
    mapping = _require_mapping(data, path)
    result: dict[str, list[str]] = {}
    for subject, role_ids in mapping.items():
        subject_id = _require_non_empty_string(subject, f"{path} key")
        if not isinstance(role_ids, list):
            raise TesseraSchemaError(f"{path}.{subject_id} must be a list")
        result[subject_id] = [
            _require_non_empty_string(role_id, f"{path}.{subject_id} role")
            for role_id in role_ids
        ]
    return result


def _validate_grant_matrix(
    data: object, path: str
) -> dict[str, dict[str, PermissionLeaf]]:
    matrix = _require_mapping(data, path)
    result: dict[str, dict[str, PermissionLeaf]] = {}
    for target, role_map in matrix.items():
        target_id = _require_non_empty_string(target, f"{path} key")
        roles = _require_mapping(role_map, f"{path}.{target_id}")
        result[target_id] = {}
        for role_id, leaf in roles.items():
            role_key = _require_non_empty_string(role_id, f"{path}.{target_id} role")
            result[target_id][role_key] = _validate_permission_leaf(
                leaf, f"{path}.{target_id}.{role_key}"
            )
    return result


def _validate_permission_leaf(data: object, path: str) -> PermissionLeaf:
    if isinstance(data, bool):
        raise TesseraSchemaError(f"{path} must be a permission object, not bare bool")

    leaf = _require_mapping(data, path)
    if not leaf:
        raise TesseraSchemaError(f"{path} must not be empty")

    unsupported = set(leaf) - {"read", "control"}
    if unsupported:
        raise TesseraSchemaError(
            f"{path} contains unsupported permission keys: {sorted(unsupported)}"
        )

    result: PermissionLeaf = {}
    for key in ("read", "control"):
        if key in leaf:
            value = leaf[key]
            if not isinstance(value, bool):
                raise TesseraSchemaError(f"{path}.{key} must be boolean")
            result[key] = value
    return result


def _require_mapping(data: object, path: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise TesseraSchemaError(f"{path} must be an object")
    if not all(isinstance(key, str) for key in data):
        raise TesseraSchemaError(f"{path} keys must be strings")
    return deepcopy(cast(dict[str, Any], data))


def _require_version(payload: dict[str, Any], path: str) -> None:
    if payload.get("version") != STORAGE_VERSION:
        raise TesseraSchemaError(f"{path}.version must be {STORAGE_VERSION}")


def _require_non_empty_string(value: object, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise TesseraSchemaError(f"{path} must be a non-empty string")
    return value
