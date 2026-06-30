"""Tests for dormant Tessera native-auth adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import custom_components.tessera as tessera_init
import pytest
from custom_components.tessera.auth_adapter import (
    AllowOnlyPolicyViolation,
    AuthPolicyStoreAdapter,
    AuthRecoverySnapshot,
    IncompleteSuperset,
    LockoutRisk,
    PermissionProbeAdapter,
    RecoveryController,
    UnsafeAuthTarget,
    UnsupportedAuthVersion,
    UserBindingAdapter,
    UserGroupSnapshot,
)
from custom_components.tessera.const import DOMAIN


@dataclass
class FakeGroup:
    """Mutable auth group test double."""

    id: str
    name: str
    policy: dict[str, Any]
    system_generated: bool = False


class FakeInnerStore:
    """Private HA storage helper test double."""

    def __init__(self) -> None:
        """Initialize save calls."""
        self.saved_payloads: list[dict[str, Any]] = []

    async def async_save(self, data: dict[str, Any]) -> None:
        """Record one auth-store save."""
        self.saved_payloads.append(data)


class FakeAuthStore:
    """Private auth store test double with mutable groups."""

    def __init__(self) -> None:
        """Initialize fake group storage."""
        self._groups: dict[str, FakeGroup] = {}
        self._store = FakeInnerStore()
        self.get_groups_calls = 0

    async def async_get_groups(self) -> list[FakeGroup]:
        """Return all fake groups."""
        self.get_groups_calls += 1
        return list(self._groups.values())

    def _data_to_save(self) -> dict[str, Any]:
        """Return a secret-free fake auth-store payload."""
        return {"groups": sorted(self._groups)}


class FakeAuth:
    """Home Assistant auth test double."""

    def __init__(self) -> None:
        """Initialize fake auth state."""
        self._store = FakeAuthStore()
        self.update_calls: list[tuple[FakeUser, list[str]]] = []
        self.users: list[FakeUser] = []

    async def async_update_user(self, user: FakeUser, **kwargs: Any) -> None:
        """Record a public HA user update."""
        group_ids = list(kwargs["group_ids"])
        self.update_calls.append((user, group_ids))
        user.group_ids = group_ids

    async def async_get_users(self) -> list[FakeUser]:
        """Return fake users."""
        return self.users


class FakeHass:
    """Home Assistant test double carrying fake auth and domain data."""

    def __init__(self) -> None:
        """Initialize fake HA state."""
        self.auth = FakeAuth()
        self.data: dict[str, Any] = {}
        self.services = FakeServices()


class AuthTrapHass:
    """HA test double that records and fails on native auth access."""

    def __init__(self) -> None:
        """Initialize trap state."""
        self.data: dict[str, Any] = {}
        self.services = FakeServices()
        self.auth_access_count = 0

    @property
    def auth(self) -> object:
        """Record and fail if setup touches native auth."""
        self.auth_access_count += 1
        raise AssertionError("hass.auth must not be touched while adapters are dormant")


class FakeServices:
    """Minimal service registry fake."""

    def __init__(self) -> None:
        """Initialize service calls."""
        self.handlers: dict[tuple[str, str], Any] = {}

    def async_register(self, domain: str, service: str, handler: Any) -> None:
        """Register one fake service handler."""
        self.handlers[(domain, service)] = handler

    def async_remove(self, domain: str, service: str) -> None:
        """Remove one fake service handler."""
        self.handlers.pop((domain, service), None)


class FakePermissions:
    """Permission checker fake."""

    def __init__(self, allowed: dict[tuple[str, str], bool]) -> None:
        """Initialize check results."""
        self._allowed = allowed

    def check_entity(self, entity_id: str, permission: str) -> bool:
        """Return configured permission result."""
        return self._allowed.get((entity_id, permission), False)


@dataclass
class FakeUser:
    """HA user test double."""

    id: str
    group_ids: list[str]
    is_owner: bool = False
    system_generated: bool = False
    is_active: bool = True
    permissions: FakePermissions = field(default_factory=lambda: FakePermissions({}))
    invalidate_calls: int = 0

    def invalidate_cache(self) -> None:
        """Record cache invalidation."""
        self.invalidate_calls += 1


class FakeConfigStore:
    """Tessera config store fake used by fail-safe-to-off."""

    def __init__(self, mode: str) -> None:
        """Initialize stored config."""
        self.saved: list[dict[str, Any]] = []
        self.config = {
            "version": 1,
            "mode": mode,
            "roles": {},
            "membership": {"by_user": {}, "by_group": {}},
        }

    async def async_load_config(self) -> dict[str, Any]:
        """Return current config."""
        return dict(self.config)

    async def async_save_config(self, data: dict[str, Any]) -> None:
        """Record saved config."""
        self.saved.append(data)
        self.config = dict(data)


@dataclass(frozen=True)
class FakeEntry:
    """Minimal config entry test double."""

    entry_id: str


class ModeStore:
    """Tessera store fake returning one configured mode."""

    def __init__(self, mode: str) -> None:
        """Initialize mode."""
        self._mode = mode

    async def async_load_config(self) -> dict[str, Any]:
        """Return config in the requested mode."""
        return {
            "version": 1,
            "mode": self._mode,
            "roles": {},
            "membership": {"by_user": {}, "by_group": {}},
        }

    async def async_load_policy(self) -> dict[str, Any]:
        """Return an empty policy for monitor-preview tests."""
        return {}


def fake_group_factory(group_id: str, name: str, policy: dict[str, Any]) -> FakeGroup:
    """Create a fake auth group."""
    return FakeGroup(group_id, name, policy)


@pytest.mark.asyncio
async def test_policy_store_version_guard_blocks_native_group_write() -> None:
    """Unsupported HA versions refuse group writes before touching storage."""
    hass = FakeHass()
    adapter = AuthPolicyStoreAdapter(
        hass, ha_version="9999.0.0", group_factory=fake_group_factory
    )

    with pytest.raises(UnsupportedAuthVersion):
        await adapter.async_set_group_policy(
            "tessera:viewer", "Viewer", {"entities": {"entity_ids": {}}}
        )

    assert hass.auth._store._groups == {}
    assert hass.auth._store._store.saved_payloads == []


@pytest.mark.asyncio
async def test_policy_store_writes_only_tessera_namespaced_groups() -> None:
    """Policy writes are persisted only for Tessera-managed group ids."""
    hass = FakeHass()
    adapter = AuthPolicyStoreAdapter(
        hass, ha_version="2026.6.4", group_factory=fake_group_factory
    )

    await adapter.async_set_group_policy(
        "tessera:viewer", "Viewer", {"entities": {"entity_ids": {"light.a": {}}}}
    )

    group = hass.auth._store._groups["tessera:viewer"]
    assert group.name == "Viewer"
    assert await adapter.async_get_group_policy("tessera:viewer") == {
        "entities": {"entity_ids": {"light.a": {}}}
    }
    assert hass.auth._store._store.saved_payloads == [{"groups": ["tessera:viewer"]}]

    with pytest.raises(UnsafeAuthTarget):
        await adapter.async_remove_group("system-users")


@pytest.mark.asyncio
async def test_policy_store_lists_only_tessera_groups_for_restore() -> None:
    """Restore group enumeration exposes only Tessera-managed groups."""
    hass = FakeHass()
    hass.auth._store._groups = {
        "system-admin": FakeGroup(
            "system-admin", "Admin", {"entities": {"entity_ids": {}}}
        ),
        "tessera:admin": FakeGroup(
            "tessera:admin", "Admin", {"entities": {"entity_ids": {}}}
        ),
        "tessera:viewer": FakeGroup(
            "tessera:viewer", "Viewer", {"entities": {"entity_ids": {}}}
        ),
    }
    adapter = AuthPolicyStoreAdapter(
        hass, ha_version="2026.6.4", group_factory=fake_group_factory
    )

    assert await adapter.async_list_tessera_group_ids() == [
        "tessera:admin",
        "tessera:viewer",
    ]


@pytest.mark.asyncio
async def test_policy_store_rejects_non_allow_only_policy_shapes() -> None:
    """Native policies are fail-closed to Tessera's entity allow-list shape."""
    hass = FakeHass()
    adapter = AuthPolicyStoreAdapter(
        hass, ha_version="2026.6.4", group_factory=fake_group_factory
    )

    with pytest.raises(AllowOnlyPolicyViolation):
        await adapter.async_set_group_policy(
            "tessera:viewer", "Viewer", {"entities": True}
        )
    with pytest.raises(AllowOnlyPolicyViolation):
        await adapter.async_set_group_policy(
            "tessera:viewer",
            "Viewer",
            {"entities": {"entity_ids": {"light.a": True}}},
        )
    with pytest.raises(AllowOnlyPolicyViolation):
        await adapter.async_set_group_policy(
            "tessera:viewer",
            "Viewer",
            {"entities": {"entity_ids": {}}, "domains": {"light": True}},
        )

    assert hass.auth._store._groups == {}
    assert hass.auth._store._store.saved_payloads == []


@pytest.mark.asyncio
async def test_user_binding_writes_full_superset_and_invalidates_cache() -> None:
    """User binding uses HA's public REPLACE API with the full superset."""
    hass = FakeHass()
    user = FakeUser("user-1", [])
    adapter = UserBindingAdapter(hass, ha_version="2026.6.4")

    await adapter.async_bind_full_superset(
        user,
        ["tessera:viewer", "system-read-only"],
        expected_tessera_group_ids=["tessera:viewer"],
    )

    assert hass.auth.update_calls == [(user, ["system-read-only", "tessera:viewer"])]
    assert user.group_ids == ["system-read-only", "tessera:viewer"]
    assert user.invalidate_calls == 1


@pytest.mark.asyncio
async def test_user_binding_rejects_delta_and_forbidden_groups() -> None:
    """User binding fails closed for deltas and allow-all groups."""
    hass = FakeHass()
    user = FakeUser("user-1", ["tessera:old"])
    adapter = UserBindingAdapter(hass, ha_version="2026.6.4")

    with pytest.raises(TypeError):
        await adapter.async_bind_full_superset(user, ["tessera:viewer"])  # type: ignore[call-arg]
    with pytest.raises(IncompleteSuperset):
        await adapter.async_bind_full_superset(
            user,
            ["tessera:viewer"],
            expected_tessera_group_ids=[],
        )
    with pytest.raises(IncompleteSuperset):
        await adapter.async_bind_full_superset(
            user,
            ["tessera:viewer"],
            expected_tessera_group_ids=["tessera:viewer", "tessera:operator"],
        )
    with pytest.raises(UnsafeAuthTarget):
        await adapter.async_bind_full_superset(
            user,
            ["system-users", "tessera:viewer"],
            expected_tessera_group_ids=["tessera:viewer"],
        )
    with pytest.raises(UnsafeAuthTarget):
        await adapter.async_bind_full_superset(
            user,
            ["custom-group", "tessera:viewer"],
            expected_tessera_group_ids=["tessera:viewer"],
        )

    assert hass.auth.update_calls == []


@pytest.mark.asyncio
async def test_user_binding_restore_exact_can_drop_tessera_groups() -> None:
    """Restore exact binding may return a user to pre-install system groups."""
    hass = FakeHass()
    user = FakeUser("user-1", ["system-read-only", "tessera:viewer"])
    adapter = UserBindingAdapter(hass, ha_version="2026.6.4")

    await adapter.async_restore_exact_groups(user, ["system-read-only"])

    assert hass.auth.update_calls == [(user, ["system-read-only"])]
    assert user.group_ids == ["system-read-only"]


@pytest.mark.asyncio
async def test_system_generated_targets_are_rejected() -> None:
    """System-generated groups and users are never managed by Tessera."""
    hass = FakeHass()
    policy = AuthPolicyStoreAdapter(
        hass, ha_version="2026.6.4", group_factory=fake_group_factory
    )
    hass.auth._store._groups["tessera:generated"] = FakeGroup(
        "tessera:generated",
        "Generated",
        {"entities": {"entity_ids": {}}},
        system_generated=True,
    )

    with pytest.raises(UnsafeAuthTarget):
        await policy.async_set_group_policy(
            "tessera:generated", "Generated", {"entities": {"entity_ids": {}}}
        )
    with pytest.raises(UnsafeAuthTarget):
        await policy.async_remove_group("tessera:generated")
    with pytest.raises(UnsafeAuthTarget):
        await UserBindingAdapter(hass, ha_version="2026.6.4").async_bind_full_superset(
            FakeUser("generated-user", ["tessera:viewer"], system_generated=True),
            ["tessera:viewer"],
            expected_tessera_group_ids=["tessera:viewer"],
        )

    assert hass.auth.update_calls == []
    assert hass.auth._store._store.saved_payloads == []


@pytest.mark.asyncio
async def test_user_binding_version_guard_has_zero_write_calls() -> None:
    """Unsupported versions refuse user binding before async_update_user."""
    hass = FakeHass()
    user = FakeUser("user-1", ["tessera:old"])
    adapter = UserBindingAdapter(hass, ha_version="9999.0.0")

    with pytest.raises(UnsupportedAuthVersion):
        await adapter.async_bind_full_superset(
            user,
            ["tessera:viewer"],
            expected_tessera_group_ids=["tessera:viewer"],
        )

    assert hass.auth.update_calls == []


@pytest.mark.asyncio
async def test_user_binding_refuses_owner_and_admin_demotion() -> None:
    """Owner/admin users are protected from unsafe binding changes."""
    hass = FakeHass()
    adapter = UserBindingAdapter(hass, ha_version="2026.6.4")

    with pytest.raises(LockoutRisk):
        await adapter.async_bind_full_superset(
            FakeUser("owner", ["system-admin"], is_owner=True),
            ["system-admin", "tessera:admin"],
            expected_tessera_group_ids=["tessera:admin"],
        )
    with pytest.raises(LockoutRisk):
        await adapter.async_bind_full_superset(
            FakeUser("admin", ["system-admin", "tessera:admin"]),
            ["tessera:admin"],
            expected_tessera_group_ids=["tessera:admin"],
        )

    assert hass.auth.update_calls == []


def test_permission_probe_uses_user_check_entity() -> None:
    """Permission probes delegate to HA user permission checks."""
    user = FakeUser(
        "user-1",
        ["tessera:viewer"],
        permissions=FakePermissions({("light.sofa", "control"): True}),
    )
    adapter = PermissionProbeAdapter()

    assert adapter.check_entity(user, "light.sofa", "control") is True
    assert adapter.check_entity(user, "light.sofa", "read") is False


@pytest.mark.asyncio
async def test_recovery_snapshot_restore_and_no_admin_lockout() -> None:
    """Recovery snapshots and restores namespace-guarded managed users."""
    hass = FakeHass()
    managed = FakeUser("managed", ["system-read-only", "tessera:viewer"])
    admin = FakeUser("admin", ["system-admin"])
    hass.auth.users = [managed, admin]
    binding = UserBindingAdapter(hass, ha_version="2026.6.4")
    recovery = RecoveryController(hass, binding)

    snapshot = await recovery.async_snapshot()
    pre_install_snapshot = await recovery.async_snapshot(
        [FakeUser("fresh", ["system-read-only"])], include_without_tessera=True
    )
    managed.group_ids = ["system-read-only"]
    result = await recovery.async_restore(snapshot, {"managed": managed})

    assert result.restored_user_ids == ("managed",)
    assert pre_install_snapshot == AuthRecoverySnapshot(
        users=(UserGroupSnapshot("fresh", ("system-read-only",)),)
    )
    assert managed.group_ids == ["system-read-only", "tessera:viewer"]
    assert await recovery.async_has_owner_or_admin() is True
    await recovery.async_assert_no_admin_lockout()


@pytest.mark.asyncio
async def test_recovery_restore_rejects_unsafe_groups_and_admin_demotion() -> None:
    """Recovery restore keeps namespace and no-lockout guards fail-closed."""
    hass = FakeHass()
    recovery = RecoveryController(hass, UserBindingAdapter(hass, ha_version="2026.6.4"))

    with pytest.raises(UnsafeAuthTarget):
        await recovery.async_restore(
            AuthRecoverySnapshot(
                users=(
                    UserGroupSnapshot("managed", ("system-users", "tessera:viewer")),
                )
            ),
            {"managed": FakeUser("managed", ["tessera:viewer"])},
        )
    with pytest.raises(UnsafeAuthTarget):
        await recovery.async_restore(
            AuthRecoverySnapshot(
                users=(
                    UserGroupSnapshot("managed", ("foreign-group", "tessera:viewer")),
                )
            ),
            {"managed": FakeUser("managed", ["tessera:viewer"])},
        )
    with pytest.raises(LockoutRisk):
        await recovery.async_restore(
            AuthRecoverySnapshot(
                users=(UserGroupSnapshot("admin", ("tessera:admin",)),)
            ),
            {"admin": FakeUser("admin", ["system-admin", "tessera:admin"])},
        )

    assert hass.auth.update_calls == []


@pytest.mark.asyncio
async def test_recovery_detects_lockout_and_can_fail_safe_to_off() -> None:
    """Recovery fails closed on lockout and can persist mode off."""
    hass = FakeHass()
    hass.auth.users = [FakeUser("managed", ["tessera:viewer"])]
    recovery = RecoveryController(hass, UserBindingAdapter(hass, ha_version="2026.6.4"))
    store = FakeConfigStore("enforce")

    with pytest.raises(LockoutRisk):
        await recovery.async_assert_no_admin_lockout()

    assert await recovery.async_fail_safe_to_off(store) == {
        "version": 1,
        "mode": "off",
        "roles": {},
        "membership": {"by_user": {}, "by_group": {}},
    }
    assert store.saved[-1]["mode"] == "off"
    assert hass.auth.update_calls == []


@pytest.mark.asyncio
async def test_recovery_treats_falsey_active_flag_as_inactive() -> None:
    """Falsey non-bool active flags are not owner/admin recovery survivors."""
    hass = FakeHass()
    hass.auth.users = [FakeUser("admin", ["system-admin"], is_active=0)]
    recovery = RecoveryController(hass, UserBindingAdapter(hass, ha_version="2026.6.4"))

    assert await recovery.async_has_owner_or_admin() is False
    with pytest.raises(LockoutRisk):
        await recovery.async_assert_no_admin_lockout()


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["off", "monitor"])
async def test_setup_entry_modes_do_not_touch_native_auth(
    monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    """E1 adapters are dormant: setup in off/monitor never touches hass.auth."""
    hass = AuthTrapHass()

    async def fake_compile_current(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {"viewer": {"entities": {"entity_ids": {}}}}

    monkeypatch.setattr(tessera_init, "TesseraStore", lambda _hass: ModeStore(mode))
    monkeypatch.setattr(
        tessera_init.AreaEntityResolver, "from_hass", lambda _hass: object()
    )
    monkeypatch.setattr(tessera_init, "compile_current", fake_compile_current)
    monkeypatch.setattr(tessera_init, "lint_current_preview", lambda *_args: None)
    monkeypatch.setattr(
        tessera_init,
        "log_monitor_preview",
        lambda compiled, *, mode, lint_report: {
            "compiled": compiled,
            "mode": mode,
            "lint_report": lint_report,
        },
    )

    assert await tessera_init.async_setup_entry(hass, FakeEntry("entry-1")) is True
    assert hass.auth_access_count == 0
    assert DOMAIN in hass.data


@pytest.mark.asyncio
async def test_auth_trap_records_swallowed_auth_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prove the dormant boundary guard catches swallowed hass.auth access."""
    hass = AuthTrapHass()

    monkeypatch.setattr(
        tessera_init.AreaEntityResolver,
        "from_hass",
        lambda leaking_hass: leaking_hass.auth,
    )

    entry_data: dict[str, Any] = {"store": ModeStore("monitor")}
    await tessera_init._compile_for_mode_safely(hass, "entry-1", entry_data)

    assert hass.auth_access_count == 1
    assert "compiled" not in entry_data
    assert "preview" not in entry_data
