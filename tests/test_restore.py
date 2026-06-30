"""Tests for dormant E3.4 restore orchestration."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from custom_components.tessera.auth_adapter import (
    AuthRecoverySnapshot,
    UserGroupSnapshot,
)
from custom_components.tessera.restore import async_restore_to_pre_install


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
