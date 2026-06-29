"""Compile Tessera store data into native Home Assistant policy structures."""

from __future__ import annotations

from copy import deepcopy
from typing import TypedDict

from .resolver import AreaEntityResolver
from .schema import (
    PermissionLeaf,
    TesseraConfigData,
    TesseraPolicyData,
    TesseraSchemaError,
    validate_config_data,
    validate_policy_data,
)


class NativePolicyEntities(TypedDict):
    """Native HA entity policy section."""

    entity_ids: dict[str, PermissionLeaf]


class NativePolicy(TypedDict):
    """Native HA policy structure emitted per Tessera role."""

    entities: NativePolicyEntities


CompiledPolicies = dict[str, NativePolicy]


def compile_policies(
    config: TesseraConfigData,
    policy: TesseraPolicyData,
    resolver: AreaEntityResolver,
) -> CompiledPolicies:
    """Compile Tessera stores into deterministic native HA policies.

    Args:
        config: Valid Tessera configuration store payload.
        policy: Valid Tessera policy store payload.
        resolver: Area resolver used to expand area grants into entity ids.

    Returns:
        A role-id keyed mapping of native HA policy structures. The returned
        structure contains only allow grants and never HA shortcut booleans.
    """
    config_data = validate_config_data(config)
    policy_data = validate_policy_data(policy)
    _validate_referenced_roles(config_data, policy_data)

    compiled: dict[str, dict[str, PermissionLeaf]] = {
        role_id: {} for role_id in sorted(config_data["roles"])
    }

    for area_id, role_map in sorted(policy_data["area_grants"].items()):
        entity_ids = resolver.entity_ids_for_area(area_id)
        for role_id, leaf in sorted(role_map.items()):
            role_entities = compiled[role_id]
            for entity_id in entity_ids:
                if normalized := _normalize_leaf(leaf):
                    role_entities[entity_id] = _merge_leaf(
                        role_entities.get(entity_id), normalized
                    )

    for entity_id, role_map in sorted(policy_data["entity_overrides"].items()):
        for role_id, leaf in sorted(role_map.items()):
            role_entities = compiled[role_id]
            if normalized := _normalize_leaf(leaf):
                role_entities[entity_id] = normalized
            else:
                role_entities.pop(entity_id, None)

    return {
        role_id: {"entities": {"entity_ids": dict(sorted(entity_map.items()))}}
        for role_id, entity_map in sorted(compiled.items())
    }


def _normalize_leaf(leaf: PermissionLeaf) -> PermissionLeaf | None:
    """Return a deterministic copy of an explicit read/control permission leaf."""
    result: PermissionLeaf = {}
    if leaf.get("read") is True or leaf.get("control") is True:
        result["read"] = True
    if leaf.get("control") is True:
        result["control"] = True
    return deepcopy(result) if result else None


def _merge_leaf(
    existing: PermissionLeaf | None, incoming: PermissionLeaf
) -> PermissionLeaf:
    """Union two positive allow leaves without weakening previous grants."""
    control = (
        bool(existing and existing.get("control")) or incoming.get("control") is True
    )
    read = (
        bool(existing and existing.get("read"))
        or incoming.get("read") is True
        or control
    )

    result: PermissionLeaf = {"read": True} if read else {}
    if control:
        result["control"] = True
    return result


def _validate_referenced_roles(
    config: TesseraConfigData, policy: TesseraPolicyData
) -> None:
    """Fail closed when policy data references roles outside config.roles."""
    known_roles = set(config["roles"])
    for path, matrix in (
        ("policy.area_grants", policy["area_grants"]),
        ("policy.entity_overrides", policy["entity_overrides"]),
    ):
        for target_id, role_map in sorted(matrix.items()):
            for role_id in sorted(role_map):
                if role_id not in known_roles:
                    raise TesseraSchemaError(
                        f"{path}.{target_id}.{role_id} references unknown role"
                    )
