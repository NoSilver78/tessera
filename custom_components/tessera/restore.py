"""Dormant E3.4 restore orchestration for Tessera native auth."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from typing import Any, Literal, Protocol, TypedDict

from .auth_adapter import (
    GROUP_ID_ADMIN,
    AuthRecoverySnapshot,
    LockoutRisk,
)

RestoreStatus = Literal["restored", "failed"]
RestoreRefusedReason = Literal["lockout", "write-error"]


class RestoreResult(TypedDict):
    """Dormant restore result with redacted write accounting."""

    status: RestoreStatus
    refused_reason: RestoreRefusedReason | None
    restored_user_ids: list[str]
    group_ids_removed: list[str]
    detail: list[str]


class _PolicyStoreRestoreLike(Protocol):
    """Native group-policy adapter subset needed by restore."""

    async def async_list_tessera_group_ids(self) -> list[str]:
        """Return current Tessera-managed native group ids."""
        ...

    async def async_remove_group(self, group_id: str) -> None:
        """Remove one native group."""
        ...


class _UserBindingRestoreLike(Protocol):
    """Native user-binding adapter subset needed by restore."""

    async def async_restore_exact_groups(
        self, user: Any, group_ids: Collection[str]
    ) -> None:
        """Restore one user to an exact pre-install group set."""
        ...


async def async_restore_to_pre_install(
    snapshot: AuthRecoverySnapshot,
    policy_store: _PolicyStoreRestoreLike,
    binding_adapter: _UserBindingRestoreLike,
    users_by_id: Mapping[str, Any],
) -> RestoreResult:
    """Restore native auth bindings and remove all Tessera groups.

    This E3.4 callable is deliberately dormant: no setup, mode handling, or
    startup path invokes it. When explicitly called, it restores user bindings
    first and removes ``tessera:*`` groups only after no restored user should
    reference them anymore. Restore is not atomic: if a later write fails,
    earlier user/group writes remain applied and are reported in the result.
    """
    result = _restore_result("restored")
    try:
        _assert_restore_owner_or_admin_survives(snapshot, users_by_id)
        tessera_group_ids = await policy_store.async_list_tessera_group_ids()
        for user_snapshot in snapshot.users:
            user = users_by_id[user_snapshot.user_id]
            if _is_unmanaged_user(user):
                continue
            _assert_restore_owner_or_admin_survives(snapshot, users_by_id)
            await binding_adapter.async_restore_exact_groups(
                user, user_snapshot.group_ids
            )
            result["restored_user_ids"].append(user_snapshot.user_id)

        for group_id in tessera_group_ids:
            _assert_restore_owner_or_admin_survives(snapshot, users_by_id)
            await policy_store.async_remove_group(group_id)
            result["group_ids_removed"].append(group_id)
    except LockoutRisk as error:
        result["status"] = "failed"
        result["refused_reason"] = "lockout"
        result["detail"] = _redacted_error_detail(error)
    except Exception as error:
        result["status"] = "failed"
        result["refused_reason"] = "write-error"
        result["detail"] = _redacted_error_detail(error)
    return result


def _restore_result(status: RestoreStatus) -> RestoreResult:
    return {
        "status": status,
        "refused_reason": None,
        "restored_user_ids": [],
        "group_ids_removed": [],
        "detail": [],
    }


def _assert_restore_owner_or_admin_survives(
    snapshot: AuthRecoverySnapshot, users_by_id: Mapping[str, Any]
) -> None:
    target_group_ids_by_user = {
        user_snapshot.user_id: set(user_snapshot.group_ids)
        for user_snapshot in snapshot.users
    }
    for user_id, user in users_by_id.items():
        if not getattr(user, "is_active", True):
            continue
        if getattr(user, "system_generated", False):
            continue
        if getattr(user, "is_owner", False):
            return
        group_ids = target_group_ids_by_user.get(user_id, set(_user_group_ids(user)))
        if GROUP_ID_ADMIN in group_ids:
            return
    raise LockoutRisk("restore would remove the last owner/admin recovery path")


def _is_unmanaged_user(user: Any) -> bool:
    return bool(getattr(user, "is_owner", False)) or bool(
        getattr(user, "system_generated", False)
    )


def _user_group_ids(user: Any) -> list[str]:
    if hasattr(user, "group_ids"):
        return sorted(str(group_id) for group_id in user.group_ids)
    return sorted(str(group.id) for group in user.groups)


def _redacted_error_detail(error: Exception) -> list[str]:
    return [type(error).__name__]
