"""Secret-free persistent recovery state for dormant E3.4 restore."""

from __future__ import annotations

from typing import Any, Literal, TypedDict, cast

from .auth_adapter import AuthRecoverySnapshot, UserGroupSnapshot

StartupRecoveryDecision = Literal["reapply", "rollback", "none"]


class TesseraStateError(ValueError):
    """Raised when persistent recovery state is unsafe or malformed."""


class UserGroupSnapshotData(TypedDict):
    """Persistent representation of one managed user's group ids."""

    user_id: str
    group_ids: list[str]


class PreInstallSnapshotData(TypedDict):
    """Persistent pre-install native-auth binding snapshot."""

    users: list[UserGroupSnapshotData]


class TesseraStateData(TypedDict):
    """Persistent E3 recovery state stored in ``.storage/tessera.state``."""

    pre_install_snapshot: PreInstallSnapshotData | None
    apply_in_progress: bool


def default_state_data() -> TesseraStateData:
    """Return empty recovery state."""
    return {"pre_install_snapshot": None, "apply_in_progress": False}


def validate_state_data(data: dict[str, Any]) -> TesseraStateData:
    """Validate and normalize secret-free recovery state."""
    if set(data) != {"pre_install_snapshot", "apply_in_progress"}:
        raise TesseraStateError("unexpected recovery state keys")
    if not isinstance(data["apply_in_progress"], bool):
        raise TesseraStateError("apply_in_progress must be boolean")
    snapshot = data["pre_install_snapshot"]
    if snapshot is not None:
        snapshot = _validate_snapshot_data(snapshot)
    if data["apply_in_progress"] and snapshot is None:
        raise TesseraStateError("apply_in_progress requires pre_install_snapshot")
    return {
        "pre_install_snapshot": snapshot,
        "apply_in_progress": data["apply_in_progress"],
    }


def snapshot_to_state_data(snapshot: AuthRecoverySnapshot) -> PreInstallSnapshotData:
    """Convert an in-memory recovery snapshot to persistent state data."""
    return {
        "users": [
            {"user_id": user.user_id, "group_ids": list(user.group_ids)}
            for user in snapshot.users
        ]
    }


def snapshot_from_state_data(
    snapshot: PreInstallSnapshotData,
) -> AuthRecoverySnapshot:
    """Convert persistent state data to an in-memory recovery snapshot."""
    return AuthRecoverySnapshot(
        users=tuple(
            UserGroupSnapshot(user["user_id"], tuple(user["group_ids"]))
            for user in snapshot["users"]
        )
    )


def decide_startup_recovery(
    state: TesseraStateData | dict[str, Any],
) -> StartupRecoveryDecision:
    """Return a dormant startup recovery decision.

    E3.4 does not wire startup recovery. If a two-phase apply journal is left
    open, the conservative choice is ``rollback`` to the immutable
    ``pre_install_snapshot`` rather than trying to infer whether a half-apply is
    safe to re-apply.
    """
    validated = validate_state_data(cast(dict[str, Any], state))
    if validated["apply_in_progress"]:
        return "rollback"
    return "none"


def _validate_snapshot_data(data: object) -> PreInstallSnapshotData:
    if not isinstance(data, dict) or set(data) != {"users"}:
        raise TesseraStateError("pre_install_snapshot must contain users")
    users = data["users"]
    if not isinstance(users, list):
        raise TesseraStateError("pre_install_snapshot.users must be a list")
    normalized_users: list[UserGroupSnapshotData] = []
    seen_user_ids: set[str] = set()
    for user in users:
        if not isinstance(user, dict) or set(user) != {"user_id", "group_ids"}:
            raise TesseraStateError("snapshot user must contain user_id and group_ids")
        user_id = user["user_id"]
        group_ids = user["group_ids"]
        if not isinstance(user_id, str) or not user_id:
            raise TesseraStateError("snapshot user_id must be a non-empty string")
        if user_id in seen_user_ids:
            raise TesseraStateError("duplicate snapshot user_id")
        seen_user_ids.add(user_id)
        if not isinstance(group_ids, list) or not all(
            isinstance(group_id, str) and group_id for group_id in group_ids
        ):
            raise TesseraStateError("snapshot group_ids must be strings")
        normalized_users.append(
            {"user_id": user_id, "group_ids": sorted(set(group_ids))}
        )
    return {"users": normalized_users}
