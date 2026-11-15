"""Regression tests for the native auth write/restore path, against HA's real AuthStore.

Every other test in the suite drives the adapters through ``FakeHass`` doubles,
which match their protocols by construction — none of these defects could
surface there. Each test below reproduces a scenario from the 2026-11-15 code
review and asserts the fixed behaviour on Home Assistant's own auth store.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from custom_components.tessera.auth_adapter import (
    SUPPORTED_HA_AUTH_VERSION,
    AuthPolicyStoreAdapter,
    AuthRecoverySnapshot,
    RecoveryController,
    UnsafeAuthTarget,
    UserBindingAdapter,
    UserGroupSnapshot,
)
from custom_components.tessera.restore import async_restore_to_pre_install
from homeassistant.auth.auth_store import AuthStore
from homeassistant.core import HomeAssistant

POLICY = {"entities": {"entity_ids": {"light.a": {"read": True}}}}


async def _adapters(
    hass: HomeAssistant,
) -> tuple[AuthPolicyStoreAdapter, UserBindingAdapter]:
    # The guard is exercised elsewhere; pin the validated version so these tests
    # run on whatever HA the test harness resolves to.
    policy_store = AuthPolicyStoreAdapter(hass, ha_version=SUPPORTED_HA_AUTH_VERSION)
    binding = UserBindingAdapter(hass, ha_version=SUPPORTED_HA_AUTH_VERSION)
    for role in ("tessera:r1", "tessera:r2"):
        await policy_store.async_set_group_policy(role, role, POLICY)
    await hass.auth.async_create_user("owner", group_ids=["system-admin"])
    return policy_store, binding


async def _users(hass: HomeAssistant) -> dict[str, object]:
    return {user.id: user for user in await hass.auth.async_get_users()}


def _group_ids(user: object) -> list[str]:
    return sorted(group.id for group in user.groups)  # type: ignore[attr-defined]


async def _auth_store_reloads(hass: HomeAssistant) -> None:
    """Load the persisted payload into a fresh AuthStore, as HA does at boot."""
    fresh = AuthStore(hass)
    fresh._store.async_load = AsyncMock(  # type: ignore[method-assign]
        return_value=hass.auth._store._data_to_save()
    )
    await fresh.async_load()


async def test_restore_rebinds_users_created_after_the_snapshot(
    hass: HomeAssistant,
) -> None:
    """A user added during enforce must not keep a removed group's id.

    Before the fix restore rebound only snapshot users and then removed every
    tessera:* group; the late user kept a dangling id and HA's auth store
    raised KeyError on the next boot — nobody could log in.
    """
    policy_store, binding = await _adapters(hass)
    alice = await hass.auth.async_create_user("alice", group_ids=["system-users"])
    snapshot = await RecoveryController(hass, binding).async_snapshot(
        [alice], include_without_tessera=True
    )
    bob = await hass.auth.async_create_user("bob", group_ids=["system-users"])
    for user in (alice, bob):
        await binding.async_bind_full_superset(
            user, ["tessera:r1"], expected_tessera_group_ids=[]
        )

    result = await async_restore_to_pre_install(
        snapshot, policy_store, binding, await _users(hass)
    )

    assert result["status"] == "restored"
    assert _group_ids(alice) == ["system-users"]
    assert _group_ids(bob) == ["system-users"]  # HA's default for a new user
    await _auth_store_reloads(hass)  # must not raise


async def test_remove_group_refuses_while_a_user_still_holds_it(
    hass: HomeAssistant,
) -> None:
    """The adapter never leaves a dangling group id behind, whoever calls it."""
    policy_store, binding = await _adapters(hass)
    user = await hass.auth.async_create_user("c", group_ids=["system-users"])
    await binding.async_bind_full_superset(
        user, ["tessera:r1"], expected_tessera_group_ids=[]
    )

    with pytest.raises(UnsafeAuthTarget):
        await policy_store.async_remove_group("tessera:r1")

    assert "tessera:r1" in await policy_store.async_list_tessera_group_ids()
    await policy_store.async_remove_group("tessera:r2")  # unbound: fine
    await _auth_store_reloads(hass)


async def test_revoking_a_role_under_enforce_is_applied(hass: HomeAssistant) -> None:
    """Dropping an acknowledged Tessera group is how a revocation reaches HA.

    Before the fix every revocation raised IncompleteSuperset, and the failed
    apply rolled all users back to the unrestricted pre-install state.
    """
    _policy_store, binding = await _adapters(hass)
    user = await hass.auth.async_create_user("d", group_ids=["system-users"])
    await binding.async_bind_full_superset(
        user, ["tessera:r1", "tessera:r2"], expected_tessera_group_ids=[]
    )

    await binding.async_bind_full_superset(
        user, ["tessera:r1"], expected_tessera_group_ids=["tessera:r1", "tessera:r2"]
    )

    assert _group_ids(user) == ["tessera:r1"]


async def test_restore_reverts_an_admin_role_promotion(hass: HomeAssistant) -> None:
    """A user promoted through an is_admin role loses it again on restore.

    Before the fix the per-user demotion guard refused this, so every restore
    after such a promotion failed for good and enforce could not be left.
    """
    policy_store, binding = await _adapters(hass)
    user = await hass.auth.async_create_user("e", group_ids=["system-users"])
    snapshot = await RecoveryController(hass, binding).async_snapshot(
        [user], include_without_tessera=True
    )
    await binding.async_bind_full_superset(
        user, ["system-admin", "tessera:r1"], expected_tessera_group_ids=[]
    )

    result = await async_restore_to_pre_install(
        snapshot, policy_store, binding, await _users(hass)
    )

    assert result["status"] == "restored"
    assert _group_ids(user) == ["system-users"]


async def test_restore_skips_a_user_deleted_since_the_snapshot(
    hass: HomeAssistant,
) -> None:
    """A deleted snapshot user must not abort the restore for everybody else."""
    policy_store, binding = await _adapters(hass)
    user = await hass.auth.async_create_user("f", group_ids=["system-users"])
    snapshot = AuthRecoverySnapshot(
        users=(
            UserGroupSnapshot("deleted-user", ("system-users",)),
            UserGroupSnapshot(user.id, ("system-users",)),
        )
    )
    await binding.async_bind_full_superset(
        user, ["tessera:r1"], expected_tessera_group_ids=[]
    )

    result = await async_restore_to_pre_install(
        snapshot, policy_store, binding, await _users(hass)
    )

    assert result["status"] == "restored"
    assert result["restored_user_ids"] == [user.id]
    assert result["group_ids_removed"] == ["tessera:r1", "tessera:r2"]
    await _auth_store_reloads(hass)


async def test_restore_never_puts_tessera_groups_back(hass: HomeAssistant) -> None:
    """A snapshot taken while leftover tessera:* groups existed is sanitised."""
    policy_store, binding = await _adapters(hass)
    user = await hass.auth.async_create_user("g", group_ids=["system-users"])
    await binding.async_bind_full_superset(
        user, ["tessera:r1"], expected_tessera_group_ids=[]
    )
    snapshot = AuthRecoverySnapshot(
        users=(UserGroupSnapshot(user.id, ("tessera:r1",)),)
    )

    result = await async_restore_to_pre_install(
        snapshot, policy_store, binding, await _users(hass)
    )

    assert result["status"] == "restored"
    assert _group_ids(user) == ["system-users"]
    await _auth_store_reloads(hass)
