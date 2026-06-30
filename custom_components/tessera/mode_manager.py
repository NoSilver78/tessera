"""Dormant read-only enforce planning for Tessera E3.1."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal, Protocol, TypedDict, cast

from .auth_adapter import (
    GROUP_ID_ADMIN,
    GROUP_ID_READ_ONLY,
    GROUP_ID_USER,
    TESSERA_GROUP_PREFIX,
    UnsupportedAuthVersion,
    _assert_supported_auth_version,
    _homeassistant_version,
)
from .compiler import NativePolicy
from .d9_gate import evaluate_d9_gate
from .linter import LintReport, has_blocking_conflicts, lint_cross_role
from .monitor import compile_current
from .resolver import AreaEntityResolver
from .schema import TesseraConfigData, TesseraPolicyData

BlockReason = Literal["version", "resolver", "store", "compile", "d9", "linter", "auth"]
ApplyStatus = Literal["applied", "blocked", "failed"]
DEFAULT_ROLE_ID = "__default__"
_PRESERVED_SYSTEM_GROUP_IDS = frozenset({GROUP_ID_ADMIN, GROUP_ID_READ_ONLY})


class GroupPlan(TypedDict):
    """Read-only native group policy projection for one Tessera role."""

    group_id: str
    role_id: str
    policy: NativePolicy


class UserBindingPlan(TypedDict):
    """Read-only target native group superset for one managed HA user."""

    user_id: str
    target_group_ids: list[str]


class EnforcePlan(TypedDict):
    """Read-only E3 enforce plan, blocked before any native write surface."""

    groups: list[GroupPlan]
    bindings: list[UserBindingPlan]
    orphan_group_ids: list[str]
    blocked: bool
    block_reason: BlockReason | None
    block_detail: list[str]


class ApplyResult(TypedDict):
    """Dormant E3.3 native-apply result with redacted write accounting."""

    status: ApplyStatus
    groups_written: list[str]
    bindings_written: list[str]
    orphan_group_ids_removed: list[str]
    detail: list[str]


class _StoreLike(Protocol):
    """Small store subset needed by the dormant mode manager."""

    async def async_load_config(self) -> TesseraConfigData:
        """Load Tessera configuration."""
        ...

    async def async_load_policy(self) -> TesseraPolicyData:
        """Load Tessera policy."""
        ...


class _PolicyStoreAdapterLike(Protocol):
    """Writable native group-policy adapter subset used by E3.3."""

    async def async_set_group_policy(
        self, group_id: str, name: str, policy: Mapping[str, Any]
    ) -> None:
        """Create or replace one native group policy."""
        ...

    async def async_remove_group(self, group_id: str) -> None:
        """Remove one native group."""
        ...


class _UserBindingAdapterLike(Protocol):
    """Writable native user-binding adapter subset used by E3.3."""

    async def async_bind_full_superset(
        self,
        user: Any,
        full_group_ids: list[str],
        *,
        expected_tessera_group_ids: list[str],
    ) -> None:
        """Replace one user's native group ids with the complete target set."""
        ...


async def compute_enforce_plan(hass: object, store: _StoreLike) -> EnforcePlan:
    """Compute the read-only E3 enforce plan without native auth writes.

    The gate sequence is fail-closed and intentionally dormant: it is not wired
    into setup, websocket, config-flow, or monitor paths. It performs no native
    auth writes. E3.2 reads native HA users and group ids only after all gates
    pass, so off/monitor paths remain free of ``hass.auth`` access.

    Args:
        hass: Home Assistant instance or test double.
        store: Tessera store adapter or test double.

    Returns:
        A deterministic group-policy plan, or an empty blocked plan when any
        gate or read-only infrastructure step refuses enforce. Compile is a
        deliberately broad fail-closed catch; task cancellation still
        propagates because only ``Exception`` is caught.
    """
    try:
        _assert_supported_auth_version(_homeassistant_version())
    except UnsupportedAuthVersion as error:
        return _blocked("version", [str(error)])

    try:
        resolver = AreaEntityResolver.from_hass(cast(Any, hass))
    except Exception as error:
        return _blocked("resolver", [f"{type(error).__name__}: {error}"])

    try:
        config = await store.async_load_config()
        policy = await store.async_load_policy()
    except Exception as error:
        return _blocked("store", [f"{type(error).__name__}: {error}"])

    try:
        compiled = await compile_current(
            cast(Any, store), resolver, config=config, policy=policy
        )
    except Exception as error:
        return _blocked("compile", [f"{type(error).__name__}: {error}"])

    try:
        d9 = await evaluate_d9_gate(hass, config)  # type: ignore[arg-type]
    except Exception as error:
        return _blocked("d9", [f"{type(error).__name__}: {error}"])
    if d9["enforce_blocked"]:
        return _blocked("d9", list(d9["blocking"]))

    lint_report = lint_cross_role(config, policy, resolver, compiled=compiled)
    if has_blocking_conflicts(lint_report):
        return _blocked("linter", _lint_block_detail(lint_report))

    try:
        binding_plan = await _compute_user_bindings_and_orphans(cast(Any, hass), config)
    except Exception as error:
        return _blocked("auth", [f"{type(error).__name__}: {error}"])

    groups: list[GroupPlan] = [
        {
            "group_id": f"{TESSERA_GROUP_PREFIX}{role_id}",
            "role_id": role_id,
            "policy": compiled[role_id],
        }
        for role_id in sorted(compiled)
    ]
    if binding_plan["needs_default_role"]:
        groups.append(
            {
                "group_id": f"{TESSERA_GROUP_PREFIX}{DEFAULT_ROLE_ID}",
                "role_id": DEFAULT_ROLE_ID,
                "policy": _empty_policy(),
            }
        )
        groups.sort(key=lambda group: group["role_id"])

    return {
        "groups": groups,
        "bindings": binding_plan["bindings"],
        "orphan_group_ids": binding_plan["orphan_group_ids"],
        "blocked": False,
        "block_reason": None,
        "block_detail": [],
    }


async def apply_enforce_plan(
    plan: EnforcePlan,
    policy_store: _PolicyStoreAdapterLike,
    binding_adapter: _UserBindingAdapterLike,
    users_by_id: Mapping[str, Any],
) -> ApplyResult:
    """Apply an already-computed enforce plan through guarded native adapters.

    This is the first native-write E3.3 surface, but remains dormant: no setup,
    websocket, config-flow, or monitor code calls it. It writes only when a
    caller explicitly passes a non-blocked plan and adapter instances.
    """
    if plan["blocked"]:
        return _apply_result(
            "blocked",
            detail=[
                f"{plan['block_reason']}: {detail}" for detail in plan["block_detail"]
            ]
            or [str(plan["block_reason"])],
        )

    try:
        binding_operations = _validated_binding_operations(plan, users_by_id)
    except Exception as error:
        return _apply_result("failed", detail=[f"{type(error).__name__}: {error}"])

    result = _apply_result("applied")
    try:
        for group in plan["groups"]:
            await policy_store.async_set_group_policy(
                group["group_id"],
                group["group_id"],
                group["policy"],
            )
            result["groups_written"].append(group["group_id"])

        for binding, user, expected_group_ids in binding_operations:
            await binding_adapter.async_bind_full_superset(
                user,
                binding["target_group_ids"],
                expected_tessera_group_ids=expected_group_ids,
            )
            result["bindings_written"].append(binding["user_id"])

        for group_id in plan["orphan_group_ids"]:
            await policy_store.async_remove_group(group_id)
            result["orphan_group_ids_removed"].append(group_id)
    except Exception as error:
        result["status"] = "failed"
        result["detail"] = [f"{type(error).__name__}: {error}"]
    return result


class _BindingAndOrphanPlan(TypedDict):
    bindings: list[UserBindingPlan]
    orphan_group_ids: list[str]
    needs_default_role: bool


_BindingOperation = tuple[UserBindingPlan, Any, list[str]]


def _apply_result(
    status: ApplyStatus, *, detail: list[str] | None = None
) -> ApplyResult:
    return {
        "status": status,
        "groups_written": [],
        "bindings_written": [],
        "orphan_group_ids_removed": [],
        "detail": detail or [],
    }


def _validated_binding_operations(
    plan: EnforcePlan, users_by_id: Mapping[str, Any]
) -> list[_BindingOperation]:
    operations: list[_BindingOperation] = []
    for binding in plan["bindings"]:
        user_id = binding["user_id"]
        if user_id not in users_by_id:
            raise ValueError(f"missing native user for binding {user_id}")
        expected_group_ids = [
            group_id
            for group_id in binding["target_group_ids"]
            if group_id.startswith(TESSERA_GROUP_PREFIX)
        ]
        if not expected_group_ids:
            raise ValueError(f"binding {user_id} has no Tessera target group")
        operations.append((binding, users_by_id[user_id], expected_group_ids))
    return operations


def _blocked(reason: BlockReason, detail: list[str]) -> EnforcePlan:
    return {
        "groups": [],
        "bindings": [],
        "orphan_group_ids": [],
        "blocked": True,
        "block_reason": reason,
        "block_detail": sorted(detail),
    }


def _lint_block_detail(report: LintReport) -> list[str]:
    details: list[str] = []
    for user_id, user_report in sorted(report["users"].items()):
        for conflict in user_report["conflicts"]:
            details.append(
                ":".join(
                    (
                        user_id,
                        conflict["entity_id"],
                        conflict["level"],
                        ",".join(conflict["restricting_roles"]),
                        "blocked-by",
                        ",".join(conflict["exposing_roles"]),
                    )
                )
            )
    return details


async def _compute_user_bindings_and_orphans(
    hass: Any, config: TesseraConfigData
) -> _BindingAndOrphanPlan:
    users = await hass.auth.async_get_users()
    existing_group_ids = await _existing_native_group_ids(hass)
    known_role_ids = set(config["roles"])
    bindings: list[UserBindingPlan] = []
    needs_default_role = False

    for user in sorted(users, key=_user_id):
        if _is_unmanaged_user(user):
            continue
        role_ids = [
            role_id
            for role_id in config["membership"]["by_user"].get(_user_id(user), [])
            if role_id in known_role_ids
        ]
        target_group_ids = _target_group_ids_for_user(user, role_ids, config)
        if not role_ids:
            needs_default_role = True
            target_group_ids.add(f"{TESSERA_GROUP_PREFIX}{DEFAULT_ROLE_ID}")
        bindings.append(
            {
                "user_id": _user_id(user),
                "target_group_ids": sorted(target_group_ids),
            }
        )

    managed_group_ids = {
        f"{TESSERA_GROUP_PREFIX}{role_id}" for role_id in known_role_ids
    } | {f"{TESSERA_GROUP_PREFIX}{DEFAULT_ROLE_ID}"}
    orphan_group_ids = sorted(
        group_id
        for group_id in existing_group_ids
        if group_id.startswith(TESSERA_GROUP_PREFIX)
        and group_id not in managed_group_ids
    )

    return {
        "bindings": bindings,
        "orphan_group_ids": orphan_group_ids,
        "needs_default_role": needs_default_role,
    }


async def _existing_native_group_ids(hass: Any) -> set[str]:
    groups = await hass.auth._store.async_get_groups()
    return {str(group.id) for group in groups}


def _target_group_ids_for_user(
    user: Any, role_ids: list[str], config: TesseraConfigData
) -> set[str]:
    current_group_ids = set(_user_group_ids(user))
    target_group_ids = {f"{TESSERA_GROUP_PREFIX}{role_id}" for role_id in role_ids}
    for group_id in current_group_ids:
        if group_id in _PRESERVED_SYSTEM_GROUP_IDS:
            target_group_ids.add(group_id)
    if GROUP_ID_USER in target_group_ids:
        target_group_ids.remove(GROUP_ID_USER)
    if _has_admin_role(role_ids, config):
        target_group_ids.add(GROUP_ID_ADMIN)
    elif GROUP_ID_ADMIN not in current_group_ids:
        target_group_ids.discard(GROUP_ID_ADMIN)
    return target_group_ids


def _has_admin_role(role_ids: list[str], config: TesseraConfigData) -> bool:
    return any(config["roles"][role_id].get("is_admin") is True for role_id in role_ids)


def _is_unmanaged_user(user: Any) -> bool:
    return bool(getattr(user, "is_owner", False)) or bool(
        getattr(user, "system_generated", False)
    )


def _user_group_ids(user: Any) -> list[str]:
    if hasattr(user, "group_ids"):
        return sorted(str(group_id) for group_id in user.group_ids)
    return sorted(str(group.id) for group in user.groups)


def _user_id(user: Any) -> str:
    user_id = getattr(user, "id", None)
    if not isinstance(user_id, str) or not user_id:
        raise ValueError("managed users require a stable id")
    return user_id


def _empty_policy() -> NativePolicy:
    return {"entities": {"entity_ids": {}}}
