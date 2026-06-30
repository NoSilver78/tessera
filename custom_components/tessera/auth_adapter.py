"""Dormant native-auth adapters for Tessera's enforce path (E1).

These adapters encapsulate the *only* code that would mutate Home Assistant's
native auth store. In phase 1 they are dormant: no product code path calls
them (they are imported only by tests). Every write is fail-closed behind a
version guard (``SUPPORTED_HA_AUTH_VERSION``), the ``tessera:`` namespace
guard, and an owner/admin lockout check. They are wired in only at E3, after
the D10 benchmark and a panel review — see docs/spec-e3-enforce.md.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Iterable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Literal, Protocol, cast

from .const import MODE_OFF
from .schema import TesseraConfigData

SUPPORTED_HA_AUTH_VERSION = "2026.6.4"
TESSERA_GROUP_PREFIX = "tessera:"
GROUP_ID_ADMIN = "system-admin"
GROUP_ID_READ_ONLY = "system-read-only"
GROUP_ID_USER = "system-users"
ALLOWED_NATIVE_GROUP_IDS = frozenset({GROUP_ID_ADMIN, GROUP_ID_READ_ONLY})


class AuthAdapterError(RuntimeError):
    """Base class for fail-closed native-auth adapter errors."""


class UnsupportedAuthVersion(AuthAdapterError):
    """Raised before writes when the HA auth-store version is unsupported."""


class UnsafeAuthTarget(AuthAdapterError):
    """Raised when a write target violates Tessera namespace guards."""


class IncompleteSuperset(AuthAdapterError):
    """Raised when a user binding omits expected Tessera role groups."""


class LockoutRisk(AuthAdapterError):
    """Raised when a write could remove owner/admin recovery access."""


class AuthGroupLike(Protocol):
    """Small mutable subset of Home Assistant auth group objects."""

    id: str
    name: str
    policy: dict[str, Any]
    system_generated: bool


class AuthStoreLike(Protocol):
    """Small private HA auth-store subset used by E1 adapters."""

    _groups: dict[str, AuthGroupLike]
    _store: Any

    async def async_get_groups(self) -> list[AuthGroupLike]:
        """Load and return groups from the auth store."""
        ...

    def _data_to_save(self) -> dict[str, Any]:
        """Return HA auth-store payload for persistence."""
        ...


class AuthLike(Protocol):
    """Small Home Assistant auth subset used by E1 adapters."""

    _store: AuthStoreLike

    async def async_update_user(self, user: Any, **kwargs: Any) -> None:
        """Update one user through HA's public REPLACE binding API."""
        ...

    async def async_get_users(self) -> list[Any]:
        """Return Home Assistant users."""
        ...


class HassAuthLike(Protocol):
    """Home Assistant subset needed by the dormant adapters."""

    auth: AuthLike


GroupFactory = Callable[[str, str, dict[str, Any]], AuthGroupLike]


@dataclass(frozen=True)
class UserGroupSnapshot:
    """Secret-free snapshot of one managed user's native group ids."""

    user_id: str
    group_ids: tuple[str, ...]


@dataclass(frozen=True)
class AuthRecoverySnapshot:
    """Namespace-guarded recovery snapshot for managed Tessera users."""

    users: tuple[UserGroupSnapshot, ...]


@dataclass(frozen=True)
class AuthRestoreResult:
    """Result of restoring managed user group bindings."""

    restored_user_ids: tuple[str, ...]


class AuthPolicyStoreAdapter:
    """Version-guarded access to native HA group policy storage.

    The adapter is intentionally dormant in E1. It exposes the private auth-store
    choke point behind a narrow guard so E3 can wire it only after panel review.
    """

    def __init__(
        self,
        hass: HassAuthLike,
        *,
        ha_version: str | None = None,
        group_factory: GroupFactory | None = None,
    ) -> None:
        """Initialize the policy-store adapter.

        Args:
            hass: Home Assistant instance or a test double.
            ha_version: Optional version override for tests.
            group_factory: Optional HA group factory for tests.
        """
        self._hass = hass
        self._ha_version = ha_version or _homeassistant_version()
        self._group_factory = group_factory or _make_group

    async def async_get_group_policy(self, group_id: str) -> dict[str, Any] | None:
        """Return a defensive copy of one Tessera native group policy."""
        _assert_tessera_group_id(group_id)
        store = self._hass.auth._store
        await store.async_get_groups()
        group = store._groups.get(group_id)
        if group is None:
            return None
        return deepcopy(group.policy)

    async def async_set_group_policy(
        self, group_id: str, name: str, policy: Mapping[str, Any]
    ) -> None:
        """Create or update one Tessera native group policy.

        Raises:
            UnsupportedAuthVersion: If HA auth-store version is not allow-listed.
            UnsafeAuthTarget: If ``group_id`` is outside the ``tessera:`` namespace.
        """
        self._assert_supported_version()
        _assert_tessera_group_id(group_id)
        store = self._hass.auth._store
        await store.async_get_groups()
        policy_copy = deepcopy(dict(policy))
        group = store._groups.get(group_id)
        if group is None:
            store._groups[group_id] = self._group_factory(group_id, name, policy_copy)
        else:
            if group.system_generated:
                raise UnsafeAuthTarget(f"{group_id} is system-generated")
            group.name = name
            group.policy = policy_copy
        await _async_persist_auth_store(store)

    async def async_remove_group(self, group_id: str) -> None:
        """Remove a Tessera native group if present."""
        self._assert_supported_version()
        _assert_tessera_group_id(group_id)
        store = self._hass.auth._store
        await store.async_get_groups()
        group = store._groups.get(group_id)
        if group is not None and group.system_generated:
            raise UnsafeAuthTarget(f"{group_id} is system-generated")
        store._groups.pop(group_id, None)
        await _async_persist_auth_store(store)

    def _assert_supported_version(self) -> None:
        """Raise before writes when the current HA version is unsupported."""
        _assert_supported_auth_version(self._ha_version)


class UserBindingAdapter:
    """Version-guarded public ``async_update_user(group_ids=...)`` wrapper."""

    def __init__(self, hass: HassAuthLike, *, ha_version: str | None = None) -> None:
        """Initialize the user-binding adapter."""
        self._hass = hass
        self._ha_version = ha_version or _homeassistant_version()

    async def async_bind_full_superset(
        self,
        user: Any,
        full_group_ids: Collection[str],
        *,
        expected_tessera_group_ids: Collection[str],
    ) -> None:
        """Bind a managed user to the full intended native group superset.

        REPLACE semantics: ``full_group_ids`` wholly replaces the user's native
        ``group_ids``. The no-drop guarantee is *caller-asserted*: this method
        only verifies that every id in ``expected_tessera_group_ids`` is present
        in ``full_group_ids``. It cannot detect a Tessera group the caller
        forgot to list, so the E3 caller MUST compute ``expected`` from the
        user's full current Tessera membership (docs/spec-e3-enforce.md §8).

        Args:
            user: HA user or test double to update.
            full_group_ids: Complete replacement set for ``user.group_ids``.
            expected_tessera_group_ids: Tessera role groups that must be present
                in ``full_group_ids``. Guards against an under-computed set, not
                against over-dropping groups outside this set.
        """
        self._assert_supported_version()
        sorted_group_ids = _validate_full_group_superset(
            user, full_group_ids, expected_tessera_group_ids
        )
        await self._hass.auth.async_update_user(user, group_ids=sorted_group_ids)
        invalidate_cache = getattr(user, "invalidate_cache", None)
        if callable(invalidate_cache):
            invalidate_cache()

    def snapshot_user_groups(self, users: Iterable[Any]) -> AuthRecoverySnapshot:
        """Capture namespace-guarded group bindings for managed Tessera users."""
        snapshots: list[UserGroupSnapshot] = []
        for user in users:
            group_ids = _user_group_ids(user)
            if not any(
                group_id.startswith(TESSERA_GROUP_PREFIX) for group_id in group_ids
            ):
                continue
            snapshots.append(
                UserGroupSnapshot(
                    user_id=_user_id(user),
                    group_ids=tuple(_validate_restore_group_ids(user)),
                )
            )
        return AuthRecoverySnapshot(users=tuple(snapshots))

    def _assert_supported_version(self) -> None:
        """Raise before writes when the current HA version is unsupported."""
        _assert_supported_auth_version(self._ha_version)


class PermissionProbeAdapter:
    """Read/control check wrapper used by monitor, verify, and impersonation."""

    def check_entity(
        self, user: Any, entity_id: str, level: Literal["read", "control"]
    ) -> bool:
        """Return whether ``user`` may access ``entity_id`` at ``level``.

        ``level`` is passed straight through to Home Assistant: the Tessera
        levels ``"read"`` and ``"control"`` are exactly HA's native entity
        permission keys (``POLICY_READ`` / ``POLICY_CONTROL``).
        """
        return bool(user.permissions.check_entity(entity_id, level))


class RecoveryController:
    """Dormant recovery helpers for product enforce wiring in E3/E4."""

    def __init__(self, hass: HassAuthLike, binding: UserBindingAdapter) -> None:
        """Initialize recovery helpers with a guarded binding adapter."""
        self._hass = hass
        self._binding = binding

    async def async_snapshot(
        self, users: Iterable[Any] | None = None
    ) -> AuthRecoverySnapshot:
        """Return a namespace-guarded managed-user group snapshot."""
        source_users = (
            list(users)
            if users is not None
            else await self._hass.auth.async_get_users()
        )
        return self._binding.snapshot_user_groups(source_users)

    async def async_restore(
        self, snapshot: AuthRecoverySnapshot, users_by_id: Mapping[str, Any]
    ) -> AuthRestoreResult:
        """Restore managed users to a previously captured full group superset."""
        restored: list[str] = []
        for user_snapshot in snapshot.users:
            user = users_by_id[user_snapshot.user_id]
            tessera_groups = [
                group_id
                for group_id in user_snapshot.group_ids
                if group_id.startswith(TESSERA_GROUP_PREFIX)
            ]
            await self._binding.async_bind_full_superset(
                user,
                user_snapshot.group_ids,
                expected_tessera_group_ids=tessera_groups,
            )
            restored.append(user_snapshot.user_id)
        return AuthRestoreResult(restored_user_ids=tuple(restored))

    async def async_has_owner_or_admin(self) -> bool:
        """Return whether at least one active owner/admin recovery user exists."""
        users = await self._hass.auth.async_get_users()
        return any(_is_active_owner_or_admin(user) for user in users)

    async def async_assert_no_admin_lockout(self) -> None:
        """Fail closed when no active owner/admin recovery path remains."""
        if not await self.async_has_owner_or_admin():
            raise LockoutRisk("no active owner/admin recovery user remains")

    async def async_fail_safe_to_off(self, store: Any) -> TesseraConfigData:
        """Persist Tessera mode ``off`` without touching native HA auth state."""
        config = await store.async_load_config()
        config["mode"] = MODE_OFF
        await store.async_save_config(config)
        return cast(TesseraConfigData, config)


def _homeassistant_version() -> str:
    """Return the running Home Assistant version lazily."""
    from homeassistant.const import __version__ as ha_version

    return str(ha_version)


def _make_group(group_id: str, name: str, policy: dict[str, Any]) -> AuthGroupLike:
    """Create a native HA group object lazily."""
    from homeassistant.auth import models

    return cast(
        AuthGroupLike,
        models.Group(id=group_id, name=name, policy=policy, system_generated=False),
    )


async def _async_persist_auth_store(store: AuthStoreLike) -> None:
    """Persist HA auth-store private group mutations."""
    await store._store.async_save(store._data_to_save())


def _validate_full_group_superset(
    user: Any,
    full_group_ids: Collection[str],
    expected_tessera_group_ids: Collection[str],
) -> list[str]:
    """Validate a complete replacement group set before binding a user."""
    _assert_managed_user(user)
    group_ids = set(full_group_ids)
    if not group_ids:
        raise IncompleteSuperset("full_group_ids must not be empty")
    for group_id in group_ids:
        _assert_allowed_binding_group_id(group_id)
    expected_group_ids = set(expected_tessera_group_ids)
    if not expected_group_ids:
        raise IncompleteSuperset("expected_tessera_group_ids must not be empty")
    for group_id in expected_group_ids:
        _assert_tessera_group_id(group_id)
    missing = expected_group_ids - group_ids
    if missing:
        raise IncompleteSuperset(
            f"full_group_ids missing expected Tessera groups: {sorted(missing)}"
        )
    current_group_ids = set(_user_group_ids(user))
    if GROUP_ID_ADMIN in current_group_ids and GROUP_ID_ADMIN not in group_ids:
        raise LockoutRisk("refusing to remove system-admin from an admin user")
    return sorted(group_ids)


def _validate_restore_group_ids(user: Any) -> list[str]:
    """Validate a recovery snapshot group set for one managed user."""
    _assert_managed_user(user)
    group_ids = _user_group_ids(user)
    for group_id in group_ids:
        _assert_allowed_binding_group_id(group_id)
    return sorted(group_ids)


def _assert_supported_auth_version(ha_version: str) -> None:
    """Raise before writes when the current HA auth version is unsupported."""
    if ha_version != SUPPORTED_HA_AUTH_VERSION:
        raise UnsupportedAuthVersion(
            f"unsupported HA auth version {ha_version}; "
            f"expected {SUPPORTED_HA_AUTH_VERSION}"
        )


def _assert_managed_user(user: Any) -> None:
    """Reject owner/system-generated users from native binding writes."""
    if getattr(user, "is_owner", False):
        raise LockoutRisk("owner users are not managed by Tessera")
    if getattr(user, "system_generated", False):
        raise UnsafeAuthTarget("system-generated users are not managed by Tessera")


def _assert_tessera_group_id(group_id: str) -> None:
    """Require the Tessera-managed group namespace."""
    if not group_id.startswith(TESSERA_GROUP_PREFIX):
        raise UnsafeAuthTarget(f"{group_id} is outside the Tessera namespace")


def _assert_allowed_binding_group_id(group_id: str) -> None:
    """Reject allow-all and non-Tessera groups from managed bindings."""
    if group_id == GROUP_ID_USER:
        raise UnsafeAuthTarget("system-users allow-all group is forbidden")
    if group_id in ALLOWED_NATIVE_GROUP_IDS:
        return
    _assert_tessera_group_id(group_id)


def _user_group_ids(user: Any) -> list[str]:
    """Return sorted group ids from HA user or test double objects."""
    if hasattr(user, "group_ids"):
        return sorted(str(group_id) for group_id in user.group_ids)
    return sorted(str(group.id) for group in user.groups)


def _user_id(user: Any) -> str:
    """Return a stable user id from HA user or test double objects."""
    user_id = getattr(user, "id", None)
    if not isinstance(user_id, str) or not user_id:
        raise UnsafeAuthTarget("managed users require a stable id")
    return user_id


def _is_active_owner_or_admin(user: Any) -> bool:
    """Return whether a user preserves the owner/admin recovery path."""
    if getattr(user, "is_active", True) is False:
        return False
    if getattr(user, "system_generated", False):
        return False
    if getattr(user, "is_owner", False):
        return True
    return GROUP_ID_ADMIN in set(_user_group_ids(user))
