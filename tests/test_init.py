"""Tests for Tessera integration setup and unload lifecycle."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

import custom_components.tessera as tessera_init
import pytest
from custom_components.tessera import (
    DATA_ACK_SERVICES_REGISTERED,
    DATA_MEMBERSHIP_SERVICE_REGISTERED,
    DATA_SERVICE_REGISTERED,
    DOMAIN,
    SERVICE_ACK_COMPONENT,
    SERVICE_RECOMPILE,
    SERVICE_REVOKE_COMPONENT_ACK,
    SERVICE_SET_MEMBERSHIP,
)
from custom_components.tessera.auth_adapter import (
    AuthRecoverySnapshot,
    UserGroupSnapshot,
)
from custom_components.tessera.schema import (
    TesseraSchemaError,
    default_config_data,
    default_policy_data,
)
from custom_components.tessera.state import default_state_data, snapshot_to_state_data
from homeassistant.exceptions import HomeAssistantError, Unauthorized


class FakeServices:
    """Minimal HA service registry double."""

    def __init__(self) -> None:
        """Initialize registered handlers and removal calls."""
        self.handlers: dict[tuple[str, str], Any] = {}
        self.schemas: dict[tuple[str, str], Any] = {}
        self.removed: list[tuple[str, str]] = []

    def async_register(
        self,
        domain: str,
        service: str,
        handler: Any,
        schema: Any = None,
        *_args: Any,
        **_kwargs: Any,
    ) -> None:
        """Register one fake service handler."""
        self.handlers[(domain, service)] = handler
        self.schemas[(domain, service)] = schema

    def async_remove(self, domain: str, service: str) -> None:
        """Record service removal and drop the fake handler."""
        self.removed.append((domain, service))
        self.handlers.pop((domain, service), None)


class FakeHass:
    """Minimal Home Assistant double with auth access trapped."""

    def __init__(self) -> None:
        """Initialize HA-like state."""
        self.data: dict[str, Any] = {}
        self.services = FakeServices()

    @property
    def auth(self) -> object:
        """Fail if setup lifecycle touches native auth."""
        raise AssertionError("hass.auth must not be touched")


class FakeHttp:
    """Minimal HA HTTP double recording static-path registrations."""

    def __init__(self) -> None:
        """Initialize the recorded static-path list."""
        self.static_paths: list[Any] = []

    async def async_register_static_paths(self, configs: list[Any]) -> None:
        """Record registered static paths."""
        self.static_paths.extend(configs)


class PanelHass(FakeHass):
    """FakeHass that also exposes an HTTP server for panel registration."""

    def __init__(self) -> None:
        """Initialize HA-like state with an HTTP double."""
        super().__init__()
        self.http = FakeHttp()


@dataclass
class FakeUser:
    """Minimal native user double for enforce/restore tests."""

    id: str
    group_ids: list[str]
    is_owner: bool = False
    is_active: bool = True
    system_generated: bool = False


class FakeAuth:
    """Small auth double exposing users without native write behavior."""

    def __init__(self, users: list[FakeUser]) -> None:
        """Initialize fake users."""
        self.users = users

    async def async_get_users(self) -> list[FakeUser]:
        """Return configured users."""
        return self.users


class AuthHass(FakeHass):
    """FakeHass variant with readable auth users for enforce tests."""

    def __init__(self, users: list[FakeUser]) -> None:
        """Initialize HA-like state with auth."""
        super().__init__()
        self._auth = FakeAuth(users)

    @property
    def auth(self) -> FakeAuth:
        """Return fake auth."""
        return self._auth


class RaisingStore:
    """Store double whose config load simulates an internal failure."""

    async def async_load_state(self) -> dict[str, Any]:
        """Load an empty recovery state."""
        return default_state_data()

    async def async_load_config(self) -> dict[str, Any]:
        """Raise a schema-like failure without exposing message details."""
        raise TesseraSchemaError("private-ish entity light.private")


class OffStore:
    """Store double that keeps setup in off mode."""

    async def async_load_state(self) -> dict[str, Any]:
        """Load an empty recovery state."""
        return default_state_data()

    async def async_load_config(self) -> dict[str, Any]:
        """Load a minimal off-mode config."""
        return {
            "version": 1,
            "mode": "off",
            "roles": {},
            "membership": {"by_user": {}, "by_group": {}},
        }


class E35Store:
    """Store double with config, policy, and recovery-state calls recorded."""

    def __init__(
        self,
        mode: str,
        state: dict[str, Any] | None = None,
        events: list[str] | None = None,
    ) -> None:
        """Initialize in-memory store payloads."""
        self.config = default_config_data()
        self.config["mode"] = mode
        self.policy = default_policy_data()
        self.state = deepcopy(state or default_state_data())
        self.events = events if events is not None else []

    async def async_load_config(self) -> dict[str, Any]:
        """Load fake config (copy-on-load, mirroring the real store)."""
        return deepcopy(self.config)

    async def async_save_config(self, config: dict[str, Any]) -> None:
        """Persist fake config."""
        self.config = deepcopy(config)

    async def async_load_policy(self) -> dict[str, Any]:
        """Load fake policy."""
        return self.policy

    async def async_load_state(self) -> dict[str, Any]:
        """Load fake recovery state."""
        return deepcopy(self.state)

    async def async_set_pre_install_snapshot(
        self, snapshot: AuthRecoverySnapshot
    ) -> dict[str, Any]:
        """Record immutable snapshot write."""
        self.events.append("set_snapshot")
        self.state["pre_install_snapshot"] = snapshot_to_state_data(snapshot)
        return deepcopy(self.state)

    async def async_mark_apply_in_progress(
        self, snapshot: AuthRecoverySnapshot
    ) -> dict[str, Any]:
        """Record journal open."""
        self.events.append("mark")
        if self.state["pre_install_snapshot"] is None:
            self.state["pre_install_snapshot"] = snapshot_to_state_data(snapshot)
        self.state["apply_in_progress"] = True
        return deepcopy(self.state)

    async def async_clear_apply_in_progress(self) -> dict[str, Any]:
        """Record journal clear."""
        self.events.append("clear")
        self.state["apply_in_progress"] = False
        return deepcopy(self.state)


class AckStore(E35Store):
    """Store double for D9 ack service tests."""

    def __init__(self, *, fail_save: bool = False) -> None:
        """Initialize an off-mode config store with optional save failure."""
        super().__init__("off")
        self.fail_save = fail_save
        self.save_calls = 0

    async def async_save_config(self, config: dict[str, Any]) -> None:
        """Persist fake config or inject a write failure."""
        self.save_calls += 1
        if self.fail_save:
            raise RuntimeError("write failed")
        await super().async_save_config(config)


class MembershipStore(E35Store):
    """Store double for by-user membership service tests."""

    def __init__(
        self,
        mode: str = "monitor",
        *,
        roles: tuple[str, ...] = ("viewer",),
        fail_save: bool = False,
        events: list[str] | None = None,
    ) -> None:
        """Initialize config with known Tessera roles."""
        super().__init__(mode, events=events)
        self.fail_save = fail_save
        self.save_calls = 0
        for role_id in roles:
            self.config["roles"][role_id] = {"name": role_id}

    async def async_save_config(self, config: dict[str, Any]) -> None:
        """Persist fake config or inject a write failure."""
        self.save_calls += 1
        if self.fail_save:
            raise RuntimeError("write failed")
        await super().async_save_config(config)


@dataclass(frozen=True)
class FakeEntry:
    """Minimal config entry double."""

    entry_id: str


@dataclass(frozen=True)
class FakeServiceCall:
    """Minimal service call double carrying service data and admin state."""

    data: dict[str, Any]
    is_admin: bool = True


def _patch_admin_service_registration(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[str, str]]:
    """Replace HA's admin-service helper with an enforcing fake."""
    admin_services: list[tuple[str, str]] = []

    def fake_register_admin_service(
        hass: Any,
        domain: str,
        service: str,
        handler: Any,
        *,
        schema: Any = None,
    ) -> None:
        admin_services.append((domain, service))

        async def admin_wrapped(call: FakeServiceCall) -> None:
            if not call.is_admin:
                raise Unauthorized
            await handler(call)

        hass.services.async_register(domain, service, admin_wrapped, schema=schema)

    monkeypatch.setattr(
        tessera_init, "async_register_admin_service", fake_register_admin_service
    )
    return admin_services


@pytest.mark.asyncio
async def test_setup_entry_falls_back_to_monitor_on_compile_error(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Internal compile failures load the entry in a safe monitor state."""
    hass = FakeHass()

    monkeypatch.setattr(tessera_init, "TesseraStore", lambda _hass: RaisingStore())

    assert await tessera_init.async_setup_entry(hass, FakeEntry("entry-1")) is True

    entry_data = hass.data[DOMAIN]["entry-1"]
    assert "compiled" not in entry_data
    assert "preview" not in entry_data
    assert entry_data["mode"] == "monitor"
    assert hass.data[DOMAIN][DATA_SERVICE_REGISTERED] is True
    assert (DOMAIN, SERVICE_RECOMPILE) in hass.services.handlers
    assert "Tessera mode handling failed for entry entry-1" in caplog.text
    assert "TesseraSchemaError" in caplog.text
    assert "light.private" not in caplog.text


@pytest.mark.asyncio
async def test_unload_entry_keeps_bucket_and_removes_service_after_last_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unload pops entries and removes the service only after the last entry."""
    hass = FakeHass()

    monkeypatch.setattr(tessera_init, "TesseraStore", lambda _hass: OffStore())

    assert await tessera_init.async_setup_entry(hass, FakeEntry("entry-1")) is True
    assert await tessera_init.async_setup_entry(hass, FakeEntry("entry-2")) is True

    assert await tessera_init.async_unload_entry(hass, FakeEntry("entry-1")) is True
    assert DOMAIN in hass.data
    assert "entry-1" not in hass.data[DOMAIN]
    assert "entry-2" in hass.data[DOMAIN]
    assert hass.services.removed == []
    assert hass.data[DOMAIN][DATA_SERVICE_REGISTERED] is True

    assert await tessera_init.async_unload_entry(hass, FakeEntry("entry-2")) is True

    assert DOMAIN in hass.data
    assert "entry-2" not in hass.data[DOMAIN]
    assert DATA_SERVICE_REGISTERED not in hass.data[DOMAIN]
    assert DATA_ACK_SERVICES_REGISTERED not in hass.data[DOMAIN]
    assert DATA_MEMBERSHIP_SERVICE_REGISTERED not in hass.data[DOMAIN]
    assert hass.services.removed == [
        (DOMAIN, SERVICE_RECOMPILE),
        (DOMAIN, SERVICE_ACK_COMPONENT),
        (DOMAIN, SERVICE_REVOKE_COMPONENT_ACK),
        (DOMAIN, SERVICE_SET_MEMBERSHIP),
    ]


@pytest.mark.asyncio
async def test_compile_for_mode_safely_drops_stale_projection(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A later compile failure discards a previously cached projection.

    The bucket is pre-seeded with stale ``compiled``/``preview`` values so the
    test proves they are *removed* (not merely absent), catching a regression
    that left a stale projection behind on the fail-safe-to-monitor path.
    """
    hass = FakeHass()
    entry_data: dict[str, Any] = {
        "store": RaisingStore(),
        "compiled": {"STALE": 1},
        "preview": {"STALE": 1},
    }

    await tessera_init._compile_for_mode_safely(hass, "entry-1", entry_data)

    assert "compiled" not in entry_data
    assert "preview" not in entry_data
    assert "Tessera mode handling failed for entry entry-1" in caplog.text


def _snapshot() -> AuthRecoverySnapshot:
    """Return a stable pre-install recovery snapshot."""
    return AuthRecoverySnapshot(users=(UserGroupSnapshot("admin", ("system-admin",)),))


def _clean_plan() -> dict[str, Any]:
    """Return a minimal non-blocked enforce plan."""
    return {
        "groups": [],
        "bindings": [],
        "orphan_group_ids": [],
        "blocked": False,
        "block_reason": None,
        "block_detail": [],
    }


def _apply_result(status: str, refused_reason: str | None = None) -> dict[str, Any]:
    """Return a minimal apply result."""
    return {
        "status": status,
        "refused_reason": refused_reason,
        "groups_written": [],
        "bindings_written": [],
        "orphan_group_ids_removed": [],
        "detail": [],
    }


def _patch_noop_adapters(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep E3.5 wiring tests HA-free."""
    monkeypatch.setattr(tessera_init, "AuthPolicyStoreAdapter", lambda _hass: object())
    monkeypatch.setattr(tessera_init, "UserBindingAdapter", lambda _hass: object())


def _patch_monitor_preview(monkeypatch: pytest.MonkeyPatch, events: list[str]) -> None:
    """Replace monitor preview with a deterministic HA-free recorder."""

    async def fake_preview(
        _hass: Any, _store: Any, config: dict[str, Any], entry_data: dict[str, Any]
    ) -> None:
        events.append("monitor_preview")
        entry_data["preview"] = {"mode": config["mode"]}

    monkeypatch.setattr(tessera_init, "_compile_monitor_preview", fake_preview)


@pytest.mark.asyncio
async def test_enforce_blocked_plan_fails_safe_to_monitor_without_auth_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A blocked enforce plan persists monitor, previews, and avoids writes."""
    events: list[str] = []
    issues: list[tuple[str, str]] = []
    store = E35Store("enforce", events=events)
    hass = FakeHass()
    entry_data: dict[str, Any] = {"store": store}

    async def fake_compute(_hass: Any, _store: Any) -> dict[str, Any]:
        events.append("compute")
        return {
            "groups": [],
            "bindings": [],
            "orphan_group_ids": [],
            "blocked": True,
            "block_reason": "d9",
            "block_detail": ["custom_component"],
        }

    async def fake_issue(
        _hass: Any, _entry_id: str, issue_id: str, *, reason: str
    ) -> None:
        issues.append((issue_id, reason))

    monkeypatch.setattr(tessera_init, "compute_enforce_plan", fake_compute)
    monkeypatch.setattr(tessera_init, "_record_repair_issue", fake_issue)
    _patch_monitor_preview(monkeypatch, events)

    await tessera_init._compile_for_mode(hass, "entry-1", entry_data)

    assert store.config["mode"] == "monitor"
    assert store.state == default_state_data()
    assert entry_data["mode"] == "monitor"
    assert entry_data["preview"] == {"mode": "monitor"}
    assert events == ["compute", "monitor_preview"]
    assert issues == [(tessera_init.REPAIR_ENFORCE_FAIL_SAFE, "blocked:d9")]


@pytest.mark.asyncio
async def test_enforce_clean_plan_snapshots_journals_applies_and_clears(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Clean enforce runs compute -> snapshot -> journal -> apply -> clear."""
    events: list[str] = []
    store = E35Store("enforce", events=events)
    hass = AuthHass([FakeUser("admin", ["system-admin"], is_owner=True)])
    entry_data: dict[str, Any] = {"store": store}

    async def fake_compute(_hass: Any, _store: Any) -> dict[str, Any]:
        events.append("compute")
        return _clean_plan()

    class FakeRecovery:
        """Recovery double recording snapshot calls."""

        def __init__(self, _hass: Any, _binding: Any) -> None:
            pass

        async def async_snapshot(
            self, _users: Any, *, include_without_tessera: bool
        ) -> AuthRecoverySnapshot:
            assert include_without_tessera is True
            events.append("snapshot")
            return _snapshot()

    async def fake_apply(*_args: Any) -> dict[str, Any]:
        events.append("apply")
        return _apply_result("applied")

    monkeypatch.setattr(tessera_init, "compute_enforce_plan", fake_compute)
    monkeypatch.setattr(tessera_init, "RecoveryController", FakeRecovery)
    monkeypatch.setattr(tessera_init, "apply_enforce_plan", fake_apply)
    _patch_noop_adapters(monkeypatch)

    await tessera_init._compile_for_mode(hass, "entry-1", entry_data)

    assert events == ["compute", "snapshot", "set_snapshot", "mark", "apply", "clear"]
    assert store.state["apply_in_progress"] is False
    assert store.state["pre_install_snapshot"] == snapshot_to_state_data(_snapshot())
    assert entry_data["mode"] == "enforce"


@pytest.mark.asyncio
async def test_recompile_service_runs_enforce_apply_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The recompile service drives the native enforce apply path for an entry."""
    events: list[str] = []
    store = E35Store("enforce", events=events)
    hass = AuthHass([FakeUser("admin", ["system-admin"], is_owner=True)])
    entry_data: dict[str, Any] = {"store": store}

    tessera_init._register_recompile_service(hass)
    hass.data[DOMAIN]["entry-1"] = entry_data

    async def fake_compute(_hass: Any, _store: Any) -> dict[str, Any]:
        events.append("compute")
        return _clean_plan()

    class FakeRecovery:
        """Recovery double recording snapshot calls."""

        def __init__(self, _hass: Any, _binding: Any) -> None:
            pass

        async def async_snapshot(
            self, _users: Any, *, include_without_tessera: bool
        ) -> AuthRecoverySnapshot:
            events.append("snapshot")
            return _snapshot()

    async def fake_apply(*_args: Any) -> dict[str, Any]:
        events.append("apply")
        return _apply_result("applied")

    monkeypatch.setattr(tessera_init, "compute_enforce_plan", fake_compute)
    monkeypatch.setattr(tessera_init, "RecoveryController", FakeRecovery)
    monkeypatch.setattr(tessera_init, "apply_enforce_plan", fake_apply)
    _patch_noop_adapters(monkeypatch)

    handler = hass.services.handlers[(DOMAIN, SERVICE_RECOMPILE)]
    await handler(object())

    assert events == ["compute", "snapshot", "set_snapshot", "mark", "apply", "clear"]
    assert store.state["apply_in_progress"] is False
    assert entry_data["mode"] == "enforce"


@pytest.mark.asyncio
async def test_d9_ack_services_are_admin_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D9 ack services are registered through HA's admin-only service helper."""
    hass = FakeHass()
    admin_services = _patch_admin_service_registration(monkeypatch)
    store = AckStore()
    hass.data[DOMAIN] = {"entry-1": {"store": store}}

    async def fake_target(_hass: Any, domain: str) -> dict[str, str | None]:
        assert domain == "auth_toucher"
        return {"version": "1.0.0", "content_hash": "a" * 64}

    monkeypatch.setattr(tessera_init, "compute_component_ack_target", fake_target)
    tessera_init._register_ack_services(hass)
    handler = hass.services.handlers[(DOMAIN, SERVICE_ACK_COMPONENT)]

    with pytest.raises(Unauthorized):
        await handler(FakeServiceCall({"domain": "auth_toucher"}, is_admin=False))
    await handler(FakeServiceCall({"domain": "auth_toucher"}, is_admin=True))

    assert admin_services == [
        (DOMAIN, SERVICE_ACK_COMPONENT),
        (DOMAIN, SERVICE_REVOKE_COMPONENT_ACK),
    ]
    assert hass.data[DOMAIN][DATA_ACK_SERVICES_REGISTERED] is True
    assert store.config["d9_acks"]["auth_toucher"]["content_hash"] == "a" * 64


@pytest.mark.asyncio
async def test_d9_ack_service_persists_and_recompiles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Acknowledge writes a hash-bound ack and immediately recompiles safely."""
    hass = FakeHass()
    _patch_admin_service_registration(monkeypatch)
    store = AckStore()
    entry_data: dict[str, Any] = {"store": store}
    hass.data[DOMAIN] = {"entry-1": entry_data}
    compile_calls: list[tuple[str, dict[str, Any]]] = []

    async def fake_target(_hass: Any, domain: str) -> dict[str, str | None]:
        assert domain == "auth_toucher"
        return {"version": "1.0.0", "content_hash": "b" * 64}

    async def fake_compile(
        _hass: Any, entry_id: str, compiled_entry_data: dict[str, Any]
    ) -> None:
        compile_calls.append((entry_id, compiled_entry_data))

    monkeypatch.setattr(tessera_init, "compute_component_ack_target", fake_target)
    monkeypatch.setattr(tessera_init, "_compile_for_mode_safely", fake_compile)
    tessera_init._register_ack_services(hass)

    handler = hass.services.handlers[(DOMAIN, SERVICE_ACK_COMPONENT)]
    await handler(FakeServiceCall({"domain": "auth_toucher"}))

    ack = store.config["d9_acks"]["auth_toucher"]
    assert ack["version"] == "1.0.0"
    assert ack["content_hash"] == "b" * 64
    assert isinstance(ack["accepted_at"], str)
    assert ack["accepted_at"]
    assert compile_calls == [("entry-1", entry_data)]


@pytest.mark.asyncio
async def test_d9_ack_service_unknown_domain_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unknown/non-disk domains cannot be acknowledged."""
    hass = FakeHass()
    _patch_admin_service_registration(monkeypatch)
    store = AckStore()
    hass.data[DOMAIN] = {"entry-1": {"store": store}}

    async def fake_target(_hass: Any, _domain: str) -> None:
        return None

    monkeypatch.setattr(tessera_init, "compute_component_ack_target", fake_target)
    tessera_init._register_ack_services(hass)

    handler = hass.services.handlers[(DOMAIN, SERVICE_ACK_COMPONENT)]
    with pytest.raises(HomeAssistantError, match="unknown or non-disk component"):
        await handler(FakeServiceCall({"domain": "missing"}))

    assert store.config["d9_acks"] == {}
    assert store.save_calls == 0


@pytest.mark.asyncio
async def test_d9_ack_service_save_failure_leaves_store_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Save failures bubble and do not mutate the persisted ack state."""
    hass = FakeHass()
    _patch_admin_service_registration(monkeypatch)
    store = AckStore(fail_save=True)
    hass.data[DOMAIN] = {"entry-1": {"store": store}}

    async def fake_target(_hass: Any, _domain: str) -> dict[str, str | None]:
        return {"version": "1.0.0", "content_hash": "c" * 64}

    async def fail_compile(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("compile must not run after save failure")

    monkeypatch.setattr(tessera_init, "compute_component_ack_target", fake_target)
    monkeypatch.setattr(tessera_init, "_compile_for_mode_safely", fail_compile)
    tessera_init._register_ack_services(hass)

    handler = hass.services.handlers[(DOMAIN, SERVICE_ACK_COMPONENT)]
    with pytest.raises(RuntimeError, match="write failed"):
        await handler(FakeServiceCall({"domain": "auth_toucher"}))

    assert store.config["d9_acks"] == {}


@pytest.mark.asyncio
async def test_d9_revoke_ack_is_idempotent_and_recompiles_on_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Revoke removes an existing ack, recompiles, and tolerates missing acks."""
    hass = FakeHass()
    _patch_admin_service_registration(monkeypatch)
    store = AckStore()
    store.config["d9_acks"] = {
        "auth_toucher": {
            "version": "1.0.0",
            "content_hash": "d" * 64,
            "accepted_at": "2026-07-01T00:00:00Z",
        }
    }
    entry_data: dict[str, Any] = {"store": store}
    hass.data[DOMAIN] = {"entry-1": entry_data}
    compile_calls: list[str] = []

    async def fake_compile(
        _hass: Any, entry_id: str, _entry_data: dict[str, Any]
    ) -> None:
        compile_calls.append(entry_id)

    monkeypatch.setattr(tessera_init, "_compile_for_mode_safely", fake_compile)
    tessera_init._register_ack_services(hass)
    handler = hass.services.handlers[(DOMAIN, SERVICE_REVOKE_COMPONENT_ACK)]

    await handler(FakeServiceCall({"domain": "auth_toucher"}))
    await handler(FakeServiceCall({"domain": "auth_toucher"}))

    assert store.config["d9_acks"] == {}
    assert compile_calls == ["entry-1", "entry-1"]


@pytest.mark.asyncio
async def test_set_membership_service_is_admin_only_and_persists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The by-user membership writer is admin-only and recompiles after save."""
    hass = AuthHass([FakeUser("user-1", ["system-users"])])
    admin_services = _patch_admin_service_registration(monkeypatch)
    store = MembershipStore(roles=("viewer", "operator"))
    entry_data: dict[str, Any] = {"store": store}
    hass.data[DOMAIN] = {"entry-1": entry_data}
    compile_calls: list[str] = []

    async def fake_compile(
        _hass: Any, entry_id: str, _entry_data: dict[str, Any]
    ) -> None:
        compile_calls.append(entry_id)

    monkeypatch.setattr(tessera_init, "_compile_for_mode_safely", fake_compile)
    tessera_init._register_membership_service(hass)
    handler = hass.services.handlers[(DOMAIN, SERVICE_SET_MEMBERSHIP)]

    with pytest.raises(Unauthorized):
        await handler(
            FakeServiceCall(
                {"user_id": "user-1", "role_ids": ["viewer"]}, is_admin=False
            )
        )
    await handler(
        FakeServiceCall(
            {"user_id": "user-1", "role_ids": ["operator", "viewer", "operator"]}
        )
    )

    assert admin_services == [(DOMAIN, SERVICE_SET_MEMBERSHIP)]
    assert hass.data[DOMAIN][DATA_MEMBERSHIP_SERVICE_REGISTERED] is True
    assert store.config["membership"]["by_user"] == {"user-1": ["operator", "viewer"]}
    assert compile_calls == ["entry-1"]


@pytest.mark.asyncio
async def test_set_membership_service_unknown_user_fails_closed_without_save_or_compile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unknown Home Assistant user ids are rejected before config writes."""
    hass = AuthHass([FakeUser("other-user", ["system-users"])])
    _patch_admin_service_registration(monkeypatch)
    store = MembershipStore()
    hass.data[DOMAIN] = {"entry-1": {"store": store}}

    async def fail_compile(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("compile must not run for unknown user")

    monkeypatch.setattr(tessera_init, "_compile_for_mode_safely", fail_compile)
    tessera_init._register_membership_service(hass)
    handler = hass.services.handlers[(DOMAIN, SERVICE_SET_MEMBERSHIP)]

    with pytest.raises(HomeAssistantError, match="unknown user"):
        await handler(FakeServiceCall({"user_id": "missing", "role_ids": ["viewer"]}))

    assert store.save_calls == 0
    assert store.config["membership"]["by_user"] == {}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("user", "reason"),
    [
        (FakeUser("user-1", ["system-users"], is_owner=True), "owner"),
        (
            FakeUser("user-1", ["system-users"], system_generated=True),
            "system-generated",
        ),
    ],
)
async def test_set_membership_service_rejects_unmanaged_targets_without_save(
    monkeypatch: pytest.MonkeyPatch, user: FakeUser, reason: str
) -> None:
    """Owner and system-generated users are outside Tessera membership writes."""
    hass = AuthHass([user])
    _patch_admin_service_registration(monkeypatch)
    store = MembershipStore()
    hass.data[DOMAIN] = {"entry-1": {"store": store}}
    tessera_init._register_membership_service(hass)
    handler = hass.services.handlers[(DOMAIN, SERVICE_SET_MEMBERSHIP)]

    with pytest.raises(HomeAssistantError, match=reason):
        await handler(FakeServiceCall({"user_id": "user-1", "role_ids": ["viewer"]}))

    assert store.save_calls == 0


@pytest.mark.asyncio
async def test_set_membership_service_unknown_role_preflights_all_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Role validation happens for every entry before any entry is saved."""
    hass = AuthHass([FakeUser("user-1", ["system-users"])])
    _patch_admin_service_registration(monkeypatch)
    valid_store = MembershipStore(roles=("viewer",))
    invalid_store = MembershipStore(roles=("operator",))
    hass.data[DOMAIN] = {
        "entry-1": {"store": valid_store},
        "entry-2": {"store": invalid_store},
    }

    async def fail_compile(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("compile must not run after preflight failure")

    monkeypatch.setattr(tessera_init, "_compile_for_mode_safely", fail_compile)
    tessera_init._register_membership_service(hass)
    handler = hass.services.handlers[(DOMAIN, SERVICE_SET_MEMBERSHIP)]

    with pytest.raises(TesseraSchemaError):
        await handler(FakeServiceCall({"user_id": "user-1", "role_ids": ["viewer"]}))

    assert valid_store.save_calls == 0
    assert invalid_store.save_calls == 0
    assert valid_store.config["membership"]["by_user"] == {}
    assert invalid_store.config["membership"]["by_user"] == {}


@pytest.mark.asyncio
async def test_set_membership_service_empty_roles_remove_idempotently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty role list removes the by_user mapping and tolerates repeats."""
    hass = AuthHass([FakeUser("user-1", ["system-users"])])
    _patch_admin_service_registration(monkeypatch)
    store = MembershipStore()
    store.config["membership"]["by_user"] = {"user-1": ["viewer"]}
    hass.data[DOMAIN] = {"entry-1": {"store": store}}

    async def fake_compile(*_args: Any, **_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(tessera_init, "_compile_for_mode_safely", fake_compile)
    tessera_init._register_membership_service(hass)
    handler = hass.services.handlers[(DOMAIN, SERVICE_SET_MEMBERSHIP)]

    await handler(FakeServiceCall({"user_id": "user-1", "role_ids": []}))
    await handler(FakeServiceCall({"user_id": "user-1", "role_ids": []}))

    assert store.config["membership"]["by_user"] == {}
    assert store.save_calls == 2


@pytest.mark.asyncio
async def test_set_membership_service_recompile_failure_fails_safe_to_monitor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Enforce-mode membership saves must recompile through the fail-safe guard."""
    issues: list[tuple[str, str]] = []
    store = MembershipStore("enforce")
    hass = AuthHass([FakeUser("user-1", ["system-users"])])
    entry_data: dict[str, Any] = {"store": store}
    hass.data[DOMAIN] = {"entry-1": entry_data}
    _patch_admin_service_registration(monkeypatch)

    async def fail_compile(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("compile failed")

    async def fake_issue(
        _hass: Any, _entry_id: str, issue_id: str, *, reason: str
    ) -> None:
        issues.append((issue_id, reason))

    monkeypatch.setattr(tessera_init, "_compile_for_mode", fail_compile)
    monkeypatch.setattr(tessera_init, "_record_repair_issue", fake_issue)
    tessera_init._register_membership_service(hass)
    handler = hass.services.handlers[(DOMAIN, SERVICE_SET_MEMBERSHIP)]

    await handler(FakeServiceCall({"user_id": "user-1", "role_ids": ["viewer"]}))

    assert store.config["mode"] == "monitor"
    assert entry_data["mode"] == "monitor"
    assert store.config["membership"]["by_user"] == {"user-1": ["viewer"]}
    assert issues == [(tessera_init.REPAIR_ENFORCE_FAIL_SAFE, "compile:RuntimeError")]


@pytest.mark.asyncio
async def test_set_membership_service_blocked_enforce_plan_avoids_native_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Blocked enforce recompiles from the service persist monitor, not auth writes."""
    events: list[str] = []
    store = MembershipStore("enforce", events=events)
    hass = AuthHass([FakeUser("user-1", ["system-users"])])
    entry_data: dict[str, Any] = {"store": store}
    hass.data[DOMAIN] = {"entry-1": entry_data}
    _patch_admin_service_registration(monkeypatch)

    async def fake_compute(_hass: Any, _store: Any) -> dict[str, Any]:
        events.append("compute")
        return {
            "groups": [],
            "bindings": [],
            "orphan_group_ids": [],
            "blocked": True,
            "block_reason": "d9",
            "block_detail": ["custom_component"],
        }

    async def fail_apply(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("native auth apply must not run for blocked plan")

    monkeypatch.setattr(tessera_init, "compute_enforce_plan", fake_compute)
    monkeypatch.setattr(tessera_init, "apply_enforce_plan", fail_apply)
    _patch_monitor_preview(monkeypatch, events)
    tessera_init._register_membership_service(hass)
    handler = hass.services.handlers[(DOMAIN, SERVICE_SET_MEMBERSHIP)]

    await handler(FakeServiceCall({"user_id": "user-1", "role_ids": ["viewer"]}))

    assert store.config["mode"] == "monitor"
    assert store.state == default_state_data()
    assert entry_data["mode"] == "monitor"
    assert entry_data["preview"] == {"mode": "monitor"}
    assert events == ["compute", "monitor_preview"]


@pytest.mark.asyncio
async def test_enforce_apply_failure_rolls_back_and_clears_journal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Apply failure rolls the half-applied auth back immediately + clears journal.

    Invariant: enforce must never leave half-applied native auth behind a monitor
    facade. On apply failure the pre-install snapshot is restored at once (not
    deferred to the next startup recovery), so the journal is cleared and no
    half-enforced window remains. (Codex CXR-01.)
    """
    events: list[str] = []
    issues: list[tuple[str, str]] = []
    store = E35Store("enforce", events=events)
    hass = AuthHass([FakeUser("admin", ["system-admin"], is_owner=True)])
    entry_data: dict[str, Any] = {"store": store}

    async def fake_compute(_hass: Any, _store: Any) -> dict[str, Any]:
        events.append("compute")
        return _clean_plan()

    class FakeRecovery:
        """Recovery double returning a snapshot."""

        def __init__(self, _hass: Any, _binding: Any) -> None:
            pass

        async def async_snapshot(
            self, *_args: Any, **_kwargs: Any
        ) -> AuthRecoverySnapshot:
            events.append("snapshot")
            return _snapshot()

    async def fake_apply(*_args: Any) -> dict[str, Any]:
        events.append("apply")
        return _apply_result("failed", "write-error")

    async def fake_restore_ok(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        events.append("restore")
        return {
            "status": "restored",
            "refused_reason": None,
            "restored_user_ids": [],
            "group_ids_removed": [],
            "detail": [],
        }

    async def fake_issue(
        _hass: Any, _entry_id: str, issue_id: str, *, reason: str
    ) -> None:
        issues.append((issue_id, reason))

    monkeypatch.setattr(tessera_init, "compute_enforce_plan", fake_compute)
    monkeypatch.setattr(tessera_init, "RecoveryController", FakeRecovery)
    monkeypatch.setattr(tessera_init, "apply_enforce_plan", fake_apply)
    monkeypatch.setattr(tessera_init, "async_restore_to_pre_install", fake_restore_ok)
    monkeypatch.setattr(tessera_init, "_record_repair_issue", fake_issue)
    _patch_noop_adapters(monkeypatch)
    _patch_monitor_preview(monkeypatch, events)

    await tessera_init._compile_for_mode(hass, "entry-1", entry_data)

    assert events == [
        "compute",
        "snapshot",
        "set_snapshot",
        "mark",
        "apply",
        "restore",
        "clear",
        "monitor_preview",
    ]
    assert store.config["mode"] == "monitor"
    assert store.state["apply_in_progress"] is False  # rollback cleared the journal
    assert issues == [(tessera_init.REPAIR_ENFORCE_FAIL_SAFE, "apply:write-error")]


@pytest.mark.asyncio
async def test_enforce_apply_failure_rollback_failure_leaves_journal_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the immediate rollback itself fails, leave the journal open + escalate.

    Startup recovery then retries the rollback; the visible mode is still monitor.
    """
    events: list[str] = []
    issues: list[tuple[str, str]] = []
    store = E35Store("enforce", events=events)
    hass = AuthHass([FakeUser("admin", ["system-admin"], is_owner=True)])
    entry_data: dict[str, Any] = {"store": store}

    async def fake_compute(_hass: Any, _store: Any) -> dict[str, Any]:
        events.append("compute")
        return _clean_plan()

    class FakeRecovery:
        """Recovery double returning a snapshot."""

        def __init__(self, _hass: Any, _binding: Any) -> None:
            pass

        async def async_snapshot(
            self, *_args: Any, **_kwargs: Any
        ) -> AuthRecoverySnapshot:
            events.append("snapshot")
            return _snapshot()

    async def fake_apply(*_args: Any) -> dict[str, Any]:
        events.append("apply")
        return _apply_result("failed", "write-error")

    async def fake_restore_fail(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        events.append("restore")
        return {
            "status": "failed",
            "refused_reason": "write-error",
            "restored_user_ids": [],
            "group_ids_removed": [],
            "detail": ["WriteError"],
        }

    async def fake_issue(
        _hass: Any, _entry_id: str, issue_id: str, *, reason: str
    ) -> None:
        issues.append((issue_id, reason))

    monkeypatch.setattr(tessera_init, "compute_enforce_plan", fake_compute)
    monkeypatch.setattr(tessera_init, "RecoveryController", FakeRecovery)
    monkeypatch.setattr(tessera_init, "apply_enforce_plan", fake_apply)
    monkeypatch.setattr(tessera_init, "async_restore_to_pre_install", fake_restore_fail)
    monkeypatch.setattr(tessera_init, "_record_repair_issue", fake_issue)
    _patch_noop_adapters(monkeypatch)
    _patch_monitor_preview(monkeypatch, events)

    await tessera_init._compile_for_mode(hass, "entry-1", entry_data)

    assert store.config["mode"] == "monitor"
    assert store.state["apply_in_progress"] is True  # left open for startup recovery
    issue_ids = [issue_id for issue_id, _ in issues]
    assert tessera_init.REPAIR_RESTORE_FAIL_SAFE in issue_ids
    assert tessera_init.REPAIR_ENFORCE_FAIL_SAFE in issue_ids


@pytest.mark.asyncio
async def test_startup_open_journal_restores_and_clears_before_compile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Startup recovery restores an open journal before mode handling."""
    events: list[str] = []
    state = {
        "pre_install_snapshot": snapshot_to_state_data(_snapshot()),
        "apply_in_progress": True,
    }
    store = E35Store("monitor", state=state, events=events)
    hass = AuthHass([FakeUser("admin", ["system-admin"], is_owner=True)])

    async def fake_restore(*_args: Any) -> dict[str, Any]:
        events.append("restore")
        return {
            "status": "restored",
            "refused_reason": None,
            "restored_user_ids": ["admin"],
            "group_ids_removed": [],
            "detail": [],
        }

    monkeypatch.setattr(tessera_init, "TesseraStore", lambda _hass: store)
    monkeypatch.setattr(tessera_init, "async_restore_to_pre_install", fake_restore)
    _patch_noop_adapters(monkeypatch)
    _patch_monitor_preview(monkeypatch, events)

    assert await tessera_init.async_setup_entry(hass, FakeEntry("entry-1")) is True

    assert events == ["restore", "clear", "monitor_preview"]
    assert store.state["apply_in_progress"] is False


@pytest.mark.asyncio
async def test_startup_recovery_failure_skips_enforce_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Recovery failures persist monitor and do not continue into enforce."""
    issues: list[tuple[str, str]] = []
    state = {
        "pre_install_snapshot": snapshot_to_state_data(_snapshot()),
        "apply_in_progress": True,
    }
    store = E35Store("enforce", state=state)
    hass = AuthHass([FakeUser("admin", ["system-admin"], is_owner=True)])

    async def fake_restore(*_args: Any) -> dict[str, Any]:
        return {
            "status": "failed",
            "refused_reason": "write-error",
            "restored_user_ids": [],
            "group_ids_removed": [],
            "detail": ["RuntimeError"],
        }

    async def fail_compute(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise AssertionError("startup recovery failure must skip enforce")

    async def fake_issue(
        _hass: Any, _entry_id: str, issue_id: str, *, reason: str
    ) -> None:
        issues.append((issue_id, reason))

    monkeypatch.setattr(tessera_init, "TesseraStore", lambda _hass: store)
    monkeypatch.setattr(tessera_init, "async_restore_to_pre_install", fake_restore)
    monkeypatch.setattr(tessera_init, "compute_enforce_plan", fail_compute)
    monkeypatch.setattr(tessera_init, "_record_repair_issue", fake_issue)
    _patch_noop_adapters(monkeypatch)

    assert await tessera_init.async_setup_entry(hass, FakeEntry("entry-1")) is True

    assert store.config["mode"] == "monitor"
    assert hass.data[DOMAIN]["entry-1"]["mode"] == "monitor"
    assert issues == [
        (tessera_init.REPAIR_RESTORE_FAIL_SAFE, "startup_recovery:write-error"),
        (tessera_init.REPAIR_ENFORCE_FAIL_SAFE, "startup_recovery"),
    ]


@pytest.mark.asyncio
async def test_mode_switch_from_enforce_to_off_restores_pre_install_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Leaving enforce restores before entering off mode."""
    events: list[str] = []
    state = {
        "pre_install_snapshot": snapshot_to_state_data(_snapshot()),
        "apply_in_progress": False,
    }
    store = E35Store("off", state=state, events=events)
    hass = AuthHass([FakeUser("admin", ["system-admin"], is_owner=True)])
    entry_data: dict[str, Any] = {"store": store, "mode": "enforce"}

    async def fake_restore(*_args: Any) -> dict[str, Any]:
        events.append("restore")
        return {
            "status": "restored",
            "refused_reason": None,
            "restored_user_ids": ["admin"],
            "group_ids_removed": ["tessera:viewer"],
            "detail": [],
        }

    monkeypatch.setattr(tessera_init, "async_restore_to_pre_install", fake_restore)
    _patch_noop_adapters(monkeypatch)

    await tessera_init._compile_for_mode(hass, "entry-1", entry_data)

    assert events == ["restore", "clear"]
    assert entry_data["mode"] == "off"
    assert "preview" not in entry_data


@pytest.mark.asyncio
async def test_unload_live_enforce_entry_restores_pre_install(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unloading a live enforce entry restores the pre-install snapshot."""
    events: list[str] = []
    state = {
        "pre_install_snapshot": snapshot_to_state_data(_snapshot()),
        "apply_in_progress": False,
    }
    store = E35Store("enforce", state=state, events=events)
    hass = AuthHass([FakeUser("admin", ["system-admin"], is_owner=True)])
    entry_data: dict[str, Any] = {"store": store, "mode": "enforce"}
    hass.data[DOMAIN] = {"entry-1": entry_data}

    async def fake_restore(*_args: Any) -> dict[str, Any]:
        events.append("restore")
        return {
            "status": "restored",
            "refused_reason": None,
            "restored_user_ids": ["admin"],
            "group_ids_removed": ["tessera:viewer"],
            "detail": [],
        }

    monkeypatch.setattr(tessera_init, "async_restore_to_pre_install", fake_restore)
    _patch_noop_adapters(monkeypatch)

    assert await tessera_init.async_unload_entry(hass, FakeEntry("entry-1")) is True

    assert events == ["restore", "clear"]
    assert "entry-1" not in hass.data[DOMAIN]


@pytest.mark.asyncio
async def test_unload_live_enforce_restore_failure_fails_safe_to_monitor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed restore during unload fails safe to monitor (no silent teardown)."""
    issues: list[tuple[str, str]] = []
    state = {
        "pre_install_snapshot": snapshot_to_state_data(_snapshot()),
        "apply_in_progress": False,
    }
    store = E35Store("enforce", state=state)
    hass = AuthHass([FakeUser("admin", ["system-admin"], is_owner=True)])
    entry_data: dict[str, Any] = {"store": store, "mode": "enforce"}
    hass.data[DOMAIN] = {"entry-1": entry_data}

    async def fake_restore(*_args: Any) -> dict[str, Any]:
        return {
            "status": "failed",
            "refused_reason": "write-error",
            "restored_user_ids": [],
            "group_ids_removed": [],
            "detail": ["RuntimeError"],
        }

    async def fake_issue(
        _hass: Any, _entry_id: str, issue_id: str, *, reason: str
    ) -> None:
        issues.append((issue_id, reason))

    monkeypatch.setattr(tessera_init, "async_restore_to_pre_install", fake_restore)
    monkeypatch.setattr(tessera_init, "_record_repair_issue", fake_issue)
    _patch_noop_adapters(monkeypatch)

    assert await tessera_init.async_unload_entry(hass, FakeEntry("entry-1")) is True

    assert entry_data["mode"] == "monitor"
    assert issues == [
        (tessera_init.REPAIR_RESTORE_FAIL_SAFE, "unload:write-error"),
        (tessera_init.REPAIR_ENFORCE_FAIL_SAFE, "unload_restore_failed"),
    ]


@pytest.mark.asyncio
async def test_mode_switch_restore_failure_fails_safe_to_monitor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed restore while leaving enforce fails safe to monitor, not off."""
    issues: list[tuple[str, str]] = []
    state = {
        "pre_install_snapshot": snapshot_to_state_data(_snapshot()),
        "apply_in_progress": False,
    }
    store = E35Store("off", state=state)
    hass = AuthHass([FakeUser("admin", ["system-admin"], is_owner=True)])
    entry_data: dict[str, Any] = {"store": store, "mode": "enforce"}

    async def fake_restore(*_args: Any) -> dict[str, Any]:
        return {
            "status": "failed",
            "refused_reason": "write-error",
            "restored_user_ids": [],
            "group_ids_removed": [],
            "detail": ["RuntimeError"],
        }

    async def fake_issue(
        _hass: Any, _entry_id: str, issue_id: str, *, reason: str
    ) -> None:
        issues.append((issue_id, reason))

    async def fake_preview(*_args: Any, **_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(tessera_init, "async_restore_to_pre_install", fake_restore)
    monkeypatch.setattr(tessera_init, "_record_repair_issue", fake_issue)
    monkeypatch.setattr(tessera_init, "_compile_monitor_preview", fake_preview)
    _patch_noop_adapters(monkeypatch)

    await tessera_init._compile_for_mode(hass, "entry-1", entry_data)

    assert entry_data["mode"] == "monitor"
    assert "off" != entry_data["mode"]
    assert issues == [
        (tessera_init.REPAIR_RESTORE_FAIL_SAFE, "mode_switch:write-error"),
        (tessera_init.REPAIR_ENFORCE_FAIL_SAFE, "mode_switch_restore_failed"),
    ]


@pytest.mark.asyncio
async def test_second_enforce_run_reuses_pre_install_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Existing pre-install snapshots are not overwritten by later enforce runs."""
    events: list[str] = []
    state = {
        "pre_install_snapshot": snapshot_to_state_data(_snapshot()),
        "apply_in_progress": False,
    }
    store = E35Store("enforce", state=state, events=events)
    hass = AuthHass([FakeUser("admin", ["system-admin"], is_owner=True)])
    entry_data: dict[str, Any] = {"store": store}

    async def fake_compute(_hass: Any, _store: Any) -> dict[str, Any]:
        events.append("compute")
        return _clean_plan()

    class FailingRecovery:
        """Recovery double proving snapshot is not called."""

        def __init__(self, _hass: Any, _binding: Any) -> None:
            pass

        async def async_snapshot(
            self, *_args: Any, **_kwargs: Any
        ) -> AuthRecoverySnapshot:
            raise AssertionError("snapshot must not be overwritten")

    async def fake_apply(*_args: Any) -> dict[str, Any]:
        events.append("apply")
        return _apply_result("applied")

    monkeypatch.setattr(tessera_init, "compute_enforce_plan", fake_compute)
    monkeypatch.setattr(tessera_init, "RecoveryController", FailingRecovery)
    monkeypatch.setattr(tessera_init, "apply_enforce_plan", fake_apply)
    _patch_noop_adapters(monkeypatch)

    await tessera_init._compile_for_mode(hass, "entry-1", entry_data)

    assert events == ["compute", "mark", "apply", "clear"]
    assert store.state["pre_install_snapshot"] == state["pre_install_snapshot"]


@pytest.mark.asyncio
async def test_enforce_exception_during_setup_fails_safe_without_bubbling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unexpected enforce errors never make setup fail hard."""
    events: list[str] = []
    issues: list[tuple[str, str]] = []
    store = E35Store("enforce", events=events)
    hass = FakeHass()

    async def fake_compute(_hass: Any, _store: Any) -> dict[str, Any]:
        raise RuntimeError("private-ish native payload")

    async def fake_issue(
        _hass: Any, _entry_id: str, issue_id: str, *, reason: str
    ) -> None:
        issues.append((issue_id, reason))

    monkeypatch.setattr(tessera_init, "TesseraStore", lambda _hass: store)
    monkeypatch.setattr(tessera_init, "compute_enforce_plan", fake_compute)
    monkeypatch.setattr(tessera_init, "_record_repair_issue", fake_issue)

    assert await tessera_init.async_setup_entry(hass, FakeEntry("entry-1")) is True

    assert store.config["mode"] == "monitor"
    assert hass.data[DOMAIN]["entry-1"]["mode"] == "monitor"
    assert issues == [(tessera_init.REPAIR_ENFORCE_FAIL_SAFE, "compile:RuntimeError")]


@pytest.mark.asyncio
async def test_panel_registers_admin_only_and_is_idempotent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The matrix panel registers admin-only (require_admin) and only once."""
    hass = PanelHass()
    panel_calls: list[dict[str, Any]] = []

    async def fake_register_panel(_hass: Any, **kwargs: Any) -> None:
        panel_calls.append(kwargs)

    monkeypatch.setattr(tessera_init, "async_register_panel", fake_register_panel)
    monkeypatch.setattr(tessera_init, "StaticPathConfig", lambda *args: args)

    await tessera_init._async_register_matrix_panel(hass)

    assert len(panel_calls) == 1
    assert panel_calls[0]["require_admin"] is True
    assert panel_calls[0]["frontend_url_path"] == tessera_init.PANEL_URL_PATH
    assert panel_calls[0]["webcomponent_name"] == tessera_init.PANEL_WEBCOMPONENT
    assert len(hass.http.static_paths) == 1
    assert hass.data[DOMAIN][tessera_init.DATA_PANEL_REGISTERED] is True

    await tessera_init._async_register_matrix_panel(hass)
    assert len(panel_calls) == 1
