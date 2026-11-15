"""E3.4 restore orchestration for Tessera native auth.

Wired into the enforce-undo paths: crash recovery on startup (open apply
journal) and mode-switch away from enforce.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from typing import Any, Literal, Protocol, TypedDict

from ._user_helpers import _is_unmanaged_user, _user_group_ids
from .auth_adapter import (
    GROUP_ID_USER,
    TESSERA_GROUP_PREFIX,
    AuthRecoverySnapshot,
    LockoutRisk,
    _assert_owner_or_admin_survives_in,
)

RestoreStatus = Literal["restored", "failed"]
RestoreRefusedReason = Literal["lockout", "write-error"]


class RestoreResult(TypedDict):
    """Restore result with redacted write accounting."""

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

    This E3.4 callable is invoked by the enforce-undo paths (crash recovery on
    startup via the apply journal, and mode-switch away from enforce). It
    restores user bindings first and removes ``tessera:*`` groups only after no
    restored user should reference them anymore. Restore is not atomic: if a
    later write fails, earlier user/group writes remain applied and are reported
    in the result.
    """
    result = _restore_result("restored")
    try:
        targets = _restore_targets(snapshot, users_by_id)
        _assert_restore_owner_or_admin_survives(targets, users_by_id)
        tessera_group_ids = await policy_store.async_list_tessera_group_ids()
        for user_id, group_ids in targets.items():
            _assert_restore_owner_or_admin_survives(targets, users_by_id)
            await binding_adapter.async_restore_exact_groups(
                users_by_id[user_id], sorted(group_ids)
            )
            result["restored_user_ids"].append(user_id)

        # Every user that referenced a tessera:* group has been rebound above,
        # so removing the groups cannot leave a dangling group id behind (HA's
        # auth store fails to load on one — no login for anybody).
        for group_id in tessera_group_ids:
            _assert_restore_owner_or_admin_survives(targets, users_by_id)
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


def _restore_targets(
    snapshot: AuthRecoverySnapshot, users_by_id: Mapping[str, Any]
) -> dict[str, set[str]]:
    """Return the exact group set every managed user is restored to.

    * Users in the snapshot get their captured groups back. A user deleted in
      HA since the snapshot is skipped — there is nothing left to restore, and
      indexing it used to abort every restore attempt for good.
    * Managed users *not* in the snapshot (created after the first enforce)
      but holding ``tessera:*`` groups lose those groups and keep everything
      else; with nothing left they get ``system-users``, HA's default for a
      new user. Skipping them would leave dangling group ids once the
      ``tessera:*`` groups are removed.
    * ``tessera:*`` ids never survive a restore, even if a snapshot carries
      them (taken while leftover groups existed).
    """
    targets: dict[str, set[str]] = {}
    for user_snapshot in snapshot.users:
        user = users_by_id.get(user_snapshot.user_id)
        if user is None or _is_unmanaged_user(user):
            continue
        targets[user_snapshot.user_id] = _without_tessera_groups(
            user_snapshot.group_ids
        )
    for user_id in sorted(users_by_id):
        user = users_by_id[user_id]
        if user_id in targets or _is_unmanaged_user(user):
            continue
        current = _user_group_ids(user)
        if any(group_id.startswith(TESSERA_GROUP_PREFIX) for group_id in current):
            targets[user_id] = _without_tessera_groups(current)
    return targets


def _without_tessera_groups(group_ids: Collection[str]) -> set[str]:
    kept = {
        group_id
        for group_id in group_ids
        if not group_id.startswith(TESSERA_GROUP_PREFIX)
    }
    if not kept and len(kept) != len(set(group_ids)):
        return {GROUP_ID_USER}
    return kept


def _assert_restore_owner_or_admin_survives(
    targets: Mapping[str, set[str]], users_by_id: Mapping[str, Any]
) -> None:
    _assert_owner_or_admin_survives_in(
        targets,
        users_by_id,
        message="restore would remove the last owner/admin recovery path",
    )


def _redacted_error_detail(error: Exception) -> list[str]:
    return [type(error).__name__]
