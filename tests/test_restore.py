"""Tests for dormant E3.4 restore orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

import pytest
from custom_components.tessera.auth_adapter import (
    AuthRecoverySnapshot,
    UserGroupSnapshot,
)
from custom_components.tessera.restore import async_restore_to_pre_install
from custom_components.tessera.state import (
    decide_startup_recovery,
    snapshot_from_state_data,
)
from custom_components.tessera.store import TesseraStore


@dataclass
class FakeUser:
    """Native HA user write double."""

    id: str
    group_ids: list[str]
    is_owner: bool = False
    system_generated: bool = False
    is_active: bool = True


class SpyPolicyStore:
    """Policy-store spy for restore tests."""

    def __init__(
        self,
        group_ids: list[str],
        events: list[str],
        *,
        fail_remove: str | None = None,
    ) -> None:
        """Initialize group ids and call tracking."""
        self.group_ids = list(group_ids)
        self.events = events
        self.fail_remove = fail_remove
        self.remove_calls: list[str] = []

    async def async_list_tessera_group_ids(self) -> list[str]:
        """Return all Tessera-managed groups."""
        return sorted(
            group_id for group_id in self.group_ids if group_id.startswith("tessera:")
        )

    async def async_remove_group(self, group_id: str) -> None:
        """Record one group removal."""
        self.events.append(f"remove:{group_id}")
        if group_id == self.fail_remove:
            raise RuntimeError("token-shaped value must not leak")
        self.remove_calls.append(group_id)
        self.group_ids.remove(group_id)


class SpyBindingAdapter:
    """Binding adapter spy for restore tests."""

    def __init__(
        self,
        events: list[str],
        *,
        fail_user_id: str | None = None,
    ) -> None:
        """Initialize call tracking."""
        self.events = events
        self.fail_user_id = fail_user_id
        self.restore_calls: list[tuple[str, list[str]]] = []

    async def async_restore_exact_groups(
        self, user: FakeUser, group_ids: list[str] | tuple[str, ...]
    ) -> None:
        """Record one exact user restore."""
        self.events.append(f"bind:{user.id}")
        if user.id == self.fail_user_id:
            raise RuntimeError("Bearer should-not-appear")
        restored_group_ids = sorted(str(group_id) for group_id in group_ids)
        user.group_ids = restored_group_ids
        self.restore_calls.append((user.id, restored_group_ids))


def _snapshot(*users: tuple[str, tuple[str, ...]]) -> AuthRecoverySnapshot:
    return AuthRecoverySnapshot(
        users=tuple(
            UserGroupSnapshot(user_id, group_ids) for user_id, group_ids in users
        )
    )


class MemoryStore:
    """In-memory HA Store helper replacement for bridge tests."""

    buckets: ClassVar[dict[str, dict[str, object]]] = {}

    def __init__(self, hass: object, version: int, key: str) -> None:
        """Create one memory-backed storage bucket."""
        self.key = key

    async def async_load(self) -> dict[str, object] | None:
        """Load the stored payload."""
        return self.buckets.get(self.key)

    async def async_save(self, data: dict[str, object]) -> None:
        """Save the payload."""
        self.buckets[self.key] = data


@pytest.mark.asyncio
async def test_restore_rebinds_users_before_removing_all_tessera_groups() -> None:
    """Restore applies pre-install bindings, then removes every Tessera group."""
    events: list[str] = []
    users = {
        "user-1": FakeUser("user-1", ["tessera:viewer"]),
        "admin": FakeUser("admin", ["system-admin"]),
    }
    policy_store = SpyPolicyStore(
        ["system-admin", "tessera:admin", "tessera:viewer"], events
    )
    binding = SpyBindingAdapter(events)

    result = await async_restore_to_pre_install(
        _snapshot(("user-1", ("system-read-only",))),
        policy_store,
        binding,
        users,
    )

    assert result == {
        "status": "restored",
        "refused_reason": None,
        "restored_user_ids": ["user-1"],
        "group_ids_removed": ["tessera:admin", "tessera:viewer"],
        "detail": [],
    }
    assert users["user-1"].group_ids == ["system-read-only"]
    assert events == [
        "bind:user-1",
        "remove:tessera:admin",
        "remove:tessera:viewer",
    ]


@pytest.mark.asyncio
async def test_restore_lockout_precheck_blocks_before_writes() -> None:
    """Restore refuses a snapshot that leaves no active owner/admin survivor."""
    events: list[str] = []
    users = {"user-1": FakeUser("user-1", ["tessera:viewer"])}
    policy_store = SpyPolicyStore(["tessera:viewer"], events)
    binding = SpyBindingAdapter(events)

    result = await async_restore_to_pre_install(
        _snapshot(("user-1", ("system-read-only",))),
        policy_store,
        binding,
        users,
    )

    assert result == {
        "status": "failed",
        "refused_reason": "lockout",
        "restored_user_ids": [],
        "group_ids_removed": [],
        "detail": ["LockoutRisk"],
    }
    assert events == []


@pytest.mark.asyncio
async def test_restore_skips_owner_and_system_generated_users() -> None:
    """Owner and system-generated snapshot entries are never rebound."""
    events: list[str] = []
    users = {
        "owner": FakeUser("owner", ["tessera:viewer"], is_owner=True),
        "generated": FakeUser("generated", ["tessera:viewer"], system_generated=True),
    }
    policy_store = SpyPolicyStore(["tessera:viewer"], events)
    binding = SpyBindingAdapter(events)

    result = await async_restore_to_pre_install(
        _snapshot(
            ("owner", ("system-admin",)),
            ("generated", ("system-read-only",)),
        ),
        policy_store,
        binding,
        users,
    )

    assert result["status"] == "restored"
    assert result["restored_user_ids"] == []
    assert binding.restore_calls == []
    assert result["group_ids_removed"] == ["tessera:viewer"]


@pytest.mark.asyncio
async def test_restore_redacts_exception_messages() -> None:
    """Restore details expose exception classes only, never raw messages."""
    events: list[str] = []
    users = {
        "user-1": FakeUser("user-1", ["system-admin", "tessera:viewer"]),
    }
    policy_store = SpyPolicyStore(["tessera:viewer"], events)
    binding = SpyBindingAdapter(events, fail_user_id="user-1")

    result = await async_restore_to_pre_install(
        _snapshot(("user-1", ("system-admin",))),
        policy_store,
        binding,
        users,
    )

    assert result == {
        "status": "failed",
        "refused_reason": "write-error",
        "restored_user_ids": [],
        "group_ids_removed": [],
        "detail": ["RuntimeError"],
    }
    assert "Bearer" not in str(result)


@pytest.mark.asyncio
async def test_journal_rollback_decision_roundtrips_into_restore() -> None:
    """Persisted rollback state can be converted back into an actionable restore."""
    MemoryStore.buckets = {}
    store = TesseraStore(hass=object(), store_factory=MemoryStore)
    snapshot = _snapshot(("user-1", ("system-read-only",)))
    await store.async_mark_apply_in_progress(snapshot)
    state = await store.async_load_state()
    assert decide_startup_recovery(state) == "rollback"
    assert state["pre_install_snapshot"] is not None
    restored_snapshot = snapshot_from_state_data(state["pre_install_snapshot"])
    events: list[str] = []
    users = {
        "user-1": FakeUser("user-1", ["tessera:viewer"]),
        "admin": FakeUser("admin", ["system-admin"]),
    }
    policy_store = SpyPolicyStore(["tessera:viewer"], events)
    binding = SpyBindingAdapter(events)

    result = await async_restore_to_pre_install(
        restored_snapshot, policy_store, binding, users
    )

    assert result["status"] == "restored"
    assert users["user-1"].group_ids == ["system-read-only"]
    assert result["group_ids_removed"] == ["tessera:viewer"]


@pytest.mark.asyncio
async def test_restore_mid_user_failure_reports_prior_writes_without_lockout() -> None:
    """A second-user restore failure reports the first successful rebind only."""
    events: list[str] = []
    users = {
        "user-1": FakeUser("user-1", ["tessera:viewer"]),
        "user-2": FakeUser("user-2", ["tessera:admin"]),
        "admin": FakeUser("admin", ["system-admin"]),
    }
    policy_store = SpyPolicyStore(["tessera:admin", "tessera:viewer"], events)
    binding = SpyBindingAdapter(events, fail_user_id="user-2")

    result = await async_restore_to_pre_install(
        _snapshot(
            ("user-1", ("system-read-only",)),
            ("user-2", ("system-read-only",)),
        ),
        policy_store,
        binding,
        users,
    )

    assert result == {
        "status": "failed",
        "refused_reason": "write-error",
        "restored_user_ids": ["user-1"],
        "group_ids_removed": [],
        "detail": ["RuntimeError"],
    }
    assert users["admin"].group_ids == ["system-admin"]
    assert events == ["bind:user-1", "bind:user-2"]


@pytest.mark.asyncio
async def test_restore_mid_group_failure_reports_prior_removals() -> None:
    """A second group removal failure reports the first removed group only."""
    events: list[str] = []
    users = {
        "user-1": FakeUser("user-1", ["tessera:viewer"]),
        "admin": FakeUser("admin", ["system-admin"]),
    }
    policy_store = SpyPolicyStore(
        ["tessera:admin", "tessera:operator", "tessera:viewer"],
        events,
        fail_remove="tessera:operator",
    )
    binding = SpyBindingAdapter(events)

    result = await async_restore_to_pre_install(
        _snapshot(("user-1", ("system-read-only",))),
        policy_store,
        binding,
        users,
    )

    assert result == {
        "status": "failed",
        "refused_reason": "write-error",
        "restored_user_ids": ["user-1"],
        "group_ids_removed": ["tessera:admin"],
        "detail": ["RuntimeError"],
    }
    assert policy_store.group_ids == ["tessera:operator", "tessera:viewer"]


@pytest.mark.asyncio
async def test_restore_treats_falsey_is_active_as_inactive() -> None:
    """Falsey non-bool active flags do not count as admin survivors."""
    events: list[str] = []
    users = {
        "inactive-admin": FakeUser("inactive-admin", ["system-admin"], is_active=0),
        "user-1": FakeUser("user-1", ["tessera:viewer"]),
    }
    policy_store = SpyPolicyStore(["tessera:viewer"], events)
    binding = SpyBindingAdapter(events)

    result = await async_restore_to_pre_install(
        _snapshot(("user-1", ("system-read-only",))),
        policy_store,
        binding,
        users,
    )

    assert result["status"] == "failed"
    assert result["refused_reason"] == "lockout"
    assert events == []
