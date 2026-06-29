"""Tests for Tessera monitor-mode wiring."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import custom_components.tessera as tessera_init
import pytest
from custom_components.tessera import DOMAIN, SERVICE_RECOMPILE
from custom_components.tessera.monitor import compile_current, monitor_preview
from custom_components.tessera.schema import default_config_data, default_policy_data


class FakeResolver:
    """Deterministic area resolver for monitor tests."""

    def __init__(self, areas: dict[str, tuple[str, ...]]) -> None:
        """Initialize area fixtures."""
        self._areas = areas

    def entity_ids_for_area(self, area_id: str) -> tuple[str, ...]:
        """Return entities for one area."""
        return self._areas.get(area_id, ())


class FakeStore:
    """Async in-memory store double."""

    def __init__(self, config: dict[str, Any], policy: dict[str, Any]) -> None:
        """Initialize store payloads."""
        self.config = config
        self.policy = policy
        self.config_loads = 0
        self.policy_loads = 0

    async def async_load_config(self) -> dict[str, Any]:
        """Load fake config."""
        self.config_loads += 1
        return self.config

    async def async_load_policy(self) -> dict[str, Any]:
        """Load fake policy."""
        self.policy_loads += 1
        return self.policy


class FakeServices:
    """Minimal HA services registry double."""

    def __init__(self) -> None:
        """Initialize service handler storage."""
        self.handlers: dict[tuple[str, str], Any] = {}

    def async_register(self, domain: str, service: str, handler: Any) -> None:
        """Register a fake service handler."""
        self.handlers[(domain, service)] = handler


class FakeHass:
    """Minimal Home Assistant double with auth access trapped."""

    def __init__(self) -> None:
        """Initialize HA-like state."""
        self.data: dict[str, Any] = {}
        self.services = FakeServices()

    @property
    def auth(self) -> object:
        """Fail if monitor-mode wiring touches native auth."""
        raise AssertionError("hass.auth must not be touched in monitor wiring")


@dataclass(frozen=True)
class FakeEntry:
    """Minimal config entry double."""

    entry_id: str


def _config(mode: str = "monitor") -> dict[str, Any]:
    config = default_config_data()
    config["mode"] = mode
    config["roles"] = {"viewer": {"name": "Viewer"}}
    return config


def _policy() -> dict[str, Any]:
    policy = default_policy_data()
    policy["area_grants"] = {"living": {"viewer": {"read": True}}}
    policy["entity_overrides"] = {
        "light.sofa": {"viewer": {"read": True, "control": True}}
    }
    return policy


@pytest.mark.asyncio
async def test_compile_current_uses_store_and_resolver_fakes() -> None:
    """Current store payloads compile through the injected resolver."""
    store = FakeStore(_config(), _policy())

    compiled = await compile_current(store, FakeResolver({"living": ("light.sofa",)}))

    assert compiled == {
        "viewer": {
            "entities": {"entity_ids": {"light.sofa": {"read": True, "control": True}}}
        }
    }
    assert store.config_loads == 1
    assert store.policy_loads == 1


def test_monitor_preview_summarizes_counts_without_entity_dump() -> None:
    """Preview returns count-only role summaries."""
    compiled = {
        "operator": {
            "entities": {
                "entity_ids": {
                    "light.sofa": {"read": True, "control": True},
                    "sensor.temp": {"read": True},
                }
            }
        },
        "viewer": {"entities": {"entity_ids": {}}},
    }

    assert monitor_preview(compiled) == {
        "roles": {
            "operator": {"entities": 2, "read": 2, "control": 1},
            "viewer": {"entities": 0, "read": 0, "control": 0},
        },
        "roles_total": 2,
        "entities_total": 2,
        "read_total": 2,
        "control_total": 1,
    }


@pytest.mark.asyncio
async def test_setup_entry_mode_off_does_not_compile_or_log(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Off mode loads only config and does not compile or log a preview."""
    store = FakeStore(_config("off"), _policy())
    hass = FakeHass()

    monkeypatch.setattr(tessera_init, "TesseraStore", lambda hass: store)
    monkeypatch.setattr(
        tessera_init.AreaEntityResolver,
        "from_hass",
        classmethod(lambda cls, hass: FakeResolver({"living": ("light.sofa",)})),
    )
    caplog.set_level(logging.INFO)

    assert await tessera_init.async_setup_entry(hass, FakeEntry("entry-1")) is True

    assert store.config_loads == 1
    assert store.policy_loads == 0
    assert "compiled" not in hass.data[DOMAIN]["entry-1"]
    assert "Tessera monitor preview" not in caplog.text


@pytest.mark.asyncio
async def test_setup_entry_mode_monitor_compiles_preview_and_never_touches_auth(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Monitor mode compiles into hass.data and logs only redacted counts."""
    store = FakeStore(_config("monitor"), _policy())
    hass = FakeHass()

    monkeypatch.setattr(tessera_init, "TesseraStore", lambda hass: store)
    monkeypatch.setattr(
        tessera_init.AreaEntityResolver,
        "from_hass",
        classmethod(lambda cls, hass: FakeResolver({"living": ("light.sofa",)})),
    )
    caplog.set_level(logging.INFO)

    assert await tessera_init.async_setup_entry(hass, FakeEntry("entry-1")) is True

    entry_data = hass.data[DOMAIN]["entry-1"]
    assert entry_data["compiled"] == {
        "viewer": {
            "entities": {"entity_ids": {"light.sofa": {"read": True, "control": True}}}
        }
    }
    assert entry_data["preview"]["entities_total"] == 1
    assert "Tessera monitor preview" in caplog.text
    assert "light.sofa" not in caplog.text


@pytest.mark.asyncio
async def test_setup_entry_mode_enforce_warns_and_runs_monitor_preview_only(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Enforce mode remains gated and uses the monitor preview path only."""
    store = FakeStore(_config("enforce"), _policy())
    hass = FakeHass()

    monkeypatch.setattr(tessera_init, "TesseraStore", lambda hass: store)
    monkeypatch.setattr(
        tessera_init.AreaEntityResolver,
        "from_hass",
        classmethod(lambda cls, hass: FakeResolver({"living": ("light.sofa",)})),
    )
    caplog.set_level(logging.INFO)

    assert await tessera_init.async_setup_entry(hass, FakeEntry("entry-1")) is True

    entry_data = hass.data[DOMAIN]["entry-1"]
    assert entry_data["compiled"] == {
        "viewer": {
            "entities": {"entity_ids": {"light.sofa": {"read": True, "control": True}}}
        }
    }
    assert entry_data["preview"]["control_total"] == 1
    assert "enforce is not implemented yet" in caplog.text
    assert "Tessera enforce preview" in caplog.text
    assert "light.sofa" not in caplog.text


@pytest.mark.asyncio
async def test_recompile_service_refreshes_compiled_preview(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The recompile service rebuilds the in-memory projection only."""
    store = FakeStore(_config("monitor"), _policy())
    hass = FakeHass()
    resolver = FakeResolver({"living": ("light.sofa", "sensor.temp")})

    monkeypatch.setattr(tessera_init, "TesseraStore", lambda hass: store)
    monkeypatch.setattr(
        tessera_init.AreaEntityResolver,
        "from_hass",
        classmethod(lambda cls, hass: resolver),
    )

    assert await tessera_init.async_setup_entry(hass, FakeEntry("entry-1")) is True
    await hass.services.handlers[(DOMAIN, SERVICE_RECOMPILE)](object())

    assert store.policy_loads == 2
    assert hass.data[DOMAIN]["entry-1"]["preview"] == {
        "roles": {"viewer": {"entities": 2, "read": 2, "control": 1}},
        "roles_total": 1,
        "entities_total": 2,
        "read_total": 2,
        "control_total": 1,
    }
