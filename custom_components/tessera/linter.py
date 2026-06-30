"""Cross-role linting for Tessera's most-permissive HA merge semantics."""

from __future__ import annotations

from typing import Literal, TypedDict

from .compiler import BY_GROUP_PROJECTION_MODE, CompiledPolicies, compile_policies
from .resolver import AreaEntityResolver
from .schema import (
    PermissionLeaf,
    TesseraConfigData,
    TesseraPolicyData,
    validate_config_data,
    validate_policy_data,
)

LintLevel = Literal["read", "control"]
LINT_SEVERITY_ERROR = "error"
# Permission levels in two orders. Read-first is for order-insensitive scans;
# control-first is load-bearing in _conflicts_for_user (see comment there).
LEVELS_READ_FIRST: tuple[LintLevel, ...] = ("read", "control")
LEVELS_CONTROL_FIRST: tuple[LintLevel, ...] = ("control", "read")


class LintConflict(TypedDict):
    """One cross-role conflict for a managed user and entity."""

    user_id: str
    entity_id: str
    exposing_roles: list[str]
    restricting_roles: list[str]
    level: LintLevel
    severity: str


class UserLintReport(TypedDict):
    """Lint result for one managed user."""

    roles: list[str]
    conflicts: list[LintConflict]


class LintReport(TypedDict):
    """Complete cross-role lint report."""

    users: dict[str, UserLintReport]
    conflicts_total: int
    blocking_conflicts: bool
    by_group_projection_mode: str


def lint_cross_role(
    config: TesseraConfigData,
    policy: TesseraPolicyData,
    resolver: AreaEntityResolver,
    *,
    compiled: CompiledPolicies | None = None,
) -> LintReport:
    """Find per-user cross-role restrictions nullified by another role allow.

    Home Assistant merges native group policies most-permissively: any role that
    grants ``read`` or ``control`` exposes that permission. Tessera reports each
    distinct separation-of-duty conflict where a role intentionally restricts an
    entity/level that a different assigned role exposes. Read conflicts are
    hidden only when the same restricting roles are already covered by a control
    conflict on that entity. Unrelated area splits are not conflicts.
    """
    config_data = validate_config_data(config)
    policy_data = validate_policy_data(policy)
    compiled_data = (
        compiled
        if compiled is not None
        else compile_policies(config_data, policy_data, resolver)
    )

    area_levels = _area_levels_by_role(policy_data, resolver)
    compiled_levels = _compiled_levels_by_role(compiled_data)
    restricted = _restricted_levels_by_role(policy_data, area_levels, compiled_levels)

    users: dict[str, UserLintReport] = {}
    conflicts_total = 0
    known_roles = set(config_data["roles"])
    for user_id, role_ids in sorted(config_data["membership"]["by_user"].items()):
        roles = sorted({role_id for role_id in role_ids if role_id in known_roles})
        conflicts = _conflicts_for_user(user_id, roles, compiled_levels, restricted)
        users[user_id] = {"roles": roles, "conflicts": conflicts}
        conflicts_total += len(conflicts)

    return {
        "users": users,
        "conflicts_total": conflicts_total,
        "blocking_conflicts": conflicts_total > 0,
        "by_group_projection_mode": BY_GROUP_PROJECTION_MODE,
    }


def has_blocking_conflicts(report: LintReport) -> bool:
    """Return whether E3 must block enforce apply for this lint report."""
    return report["blocking_conflicts"]


def empty_lint_report() -> LintReport:
    """Return a deterministic empty lint report for preview-only call sites."""
    return {
        "users": {},
        "conflicts_total": 0,
        "blocking_conflicts": False,
        "by_group_projection_mode": BY_GROUP_PROJECTION_MODE,
    }


def _conflicts_for_user(
    user_id: str,
    roles: list[str],
    compiled_levels: dict[str, dict[str, set[LintLevel]]],
    restricted: dict[str, dict[str, set[LintLevel]]],
) -> list[LintConflict]:
    conflicts: list[LintConflict] = []
    entity_ids = sorted(
        {
            entity_id
            for role_id in roles
            for entity_id in (
                set(compiled_levels.get(role_id, {})) | set(restricted.get(role_id, {}))
            )
        }
    )
    for entity_id in entity_ids:
        control_restricting_roles: set[str] = set()
        # Control before read: a read conflict is suppressed when the same
        # roles already raised a control conflict on this entity (control
        # implies read), so control_restricting_roles must be filled first.
        for level in LEVELS_CONTROL_FIRST:
            exposing_roles = [
                role_id
                for role_id in roles
                if level in compiled_levels.get(role_id, {}).get(entity_id, set())
            ]
            restricting_roles = [
                role_id
                for role_id in roles
                if level in restricted.get(role_id, {}).get(entity_id, set())
            ]
            exposing_set = set(exposing_roles)
            restricting_set = set(restricting_roles)
            if (
                exposing_set
                and restricting_set
                and exposing_set - restricting_set
                and restricting_set - exposing_set
                and not (
                    level == "read"
                    and restricting_set.issubset(control_restricting_roles)
                )
            ):
                conflicts.append(
                    {
                        "user_id": user_id,
                        "entity_id": entity_id,
                        "exposing_roles": exposing_roles,
                        "restricting_roles": restricting_roles,
                        "level": level,
                        "severity": LINT_SEVERITY_ERROR,
                    }
                )
                if level == "control":
                    control_restricting_roles = restricting_set
    return conflicts


def _area_levels_by_role(
    policy: TesseraPolicyData, resolver: AreaEntityResolver
) -> dict[str, dict[str, set[LintLevel]]]:
    """Return role/entity levels granted by area rules before overrides."""
    levels: dict[str, dict[str, set[LintLevel]]] = {}
    for area_id, role_map in sorted(policy["area_grants"].items()):
        entity_ids = resolver.entity_ids_for_area(area_id)
        for role_id, leaf in sorted(role_map.items()):
            leaf_levels = _leaf_levels(leaf)
            if not leaf_levels:
                continue
            role_levels = levels.setdefault(role_id, {})
            for entity_id in entity_ids:
                role_levels.setdefault(entity_id, set()).update(leaf_levels)
    return levels


def _compiled_levels_by_role(
    compiled: CompiledPolicies,
) -> dict[str, dict[str, set[LintLevel]]]:
    """Return role/entity levels exposed by the compiled native projection."""
    return {
        role_id: {
            entity_id: _leaf_levels(leaf)
            for entity_id, leaf in role_policy["entities"]["entity_ids"].items()
        }
        for role_id, role_policy in sorted(compiled.items())
    }


def _restricted_levels_by_role(
    policy: TesseraPolicyData,
    area_levels: dict[str, dict[str, set[LintLevel]]],
    compiled_levels: dict[str, dict[str, set[LintLevel]]],
) -> dict[str, dict[str, set[LintLevel]]]:
    """Return role/entity levels intentionally hidden before cross-role merge."""
    restricted: dict[str, dict[str, set[LintLevel]]] = {}
    for role_id, entity_map in area_levels.items():
        for entity_id, levels in entity_map.items():
            missing = levels - compiled_levels.get(role_id, {}).get(entity_id, set())
            _add_levels(restricted, role_id, entity_id, missing)
            if "read" in levels and "control" not in compiled_levels.get(
                role_id, {}
            ).get(entity_id, set()):
                _add_levels(restricted, role_id, entity_id, {"control"})

    for entity_id, role_map in sorted(policy["entity_overrides"].items()):
        for role_id, leaf in sorted(role_map.items()):
            _add_levels(restricted, role_id, entity_id, _explicit_false_levels(leaf))
            if leaf.get("read") is True and leaf.get("control") is not True:
                _add_levels(restricted, role_id, entity_id, {"control"})
    return restricted


def _leaf_levels(leaf: PermissionLeaf) -> set[LintLevel]:
    """Normalize a permission leaf into HA read/control levels."""
    levels: set[LintLevel] = set()
    if leaf.get("read") is True or leaf.get("control") is True:
        levels.add("read")
    if leaf.get("control") is True:
        levels.add("control")
    return levels


def _explicit_false_levels(leaf: PermissionLeaf) -> set[LintLevel]:
    """Return levels explicitly carved out by a policy override leaf."""
    return {
        level
        for level in LEVELS_READ_FIRST
        if level in leaf and leaf.get(level) is False
    }


def _add_levels(
    target: dict[str, dict[str, set[LintLevel]]],
    role_id: str,
    entity_id: str,
    levels: set[LintLevel],
) -> None:
    """Add non-empty restricted levels to a nested role/entity map."""
    if not levels:
        return
    target.setdefault(role_id, {}).setdefault(entity_id, set()).update(levels)
