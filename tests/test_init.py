"""Tests for Tessera integration setup and unload lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import custom_components.tessera as tessera_init
import pytest
from custom_components.tessera import (
    DATA_SERVICE_REGISTERED,
    DOMAIN,
    SERVICE_RECOMPILE,
)
from custom_components.tessera.schema import TesseraSchemaError


class FakeServices:
    """Minimal HA service registry double."""

    def __init__(self) -> None:
        """Initialize registered handlers and removal calls."""
        self.handlers: dict[tuple[str, str], Any] = {}
        self.removed: list[tuple[str, str]] = []

    def async_register(self, domain: str, service: str, handler: Any) -> None:
        """Register one fake service handler."""
        self.handlers[(domain, service)] = handler

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


class RaisingStore:
    """Store double whose config load simulates an internal failure."""

    async def async_load_config(self) -> dict[str, Any]:
        """Raise a schema-like failure without exposing message details."""
        raise TesseraSchemaError("secret-ish entity light.private")


class OffStore:
    """Store double that keeps setup in off mode."""

    async def async_load_config(self) -> dict[str, Any]:
        """Load a minimal off-mode config."""
        return {
            "version": 1,
            "mode": "off",
            "roles": {},
            "membership": {"by_user": {}, "by_group": {}},
        }


@dataclass(frozen=True)
class FakeEntry:
    """Minimal config entry double."""

    entry_id: str


@pytest.mark.asyncio
async def test_setup_entry_falls_back_to_effective_off_on_compile_error(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Internal compile failures load the entry in a safe off state."""
    hass = FakeHass()

    monkeypatch.setattr(tessera_init, "TesseraStore", lambda _hass: RaisingStore())

    assert await tessera_init.async_setup_entry(hass, FakeEntry("entry-1")) is True

    entry_data = hass.data[DOMAIN]["entry-1"]
    assert "compiled" not in entry_data
    assert "preview" not in entry_data
    assert hass.data[DOMAIN][DATA_SERVICE_REGISTERED] is True
    assert (DOMAIN, SERVICE_RECOMPILE) in hass.services.handlers
    assert "Tessera compile failed for entry entry-1" in caplog.text
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
    assert hass.services.removed == [(DOMAIN, SERVICE_RECOMPILE)]


@pytest.mark.asyncio
async def test_compile_for_mode_safely_drops_stale_projection(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A later compile failure discards a previously cached projection.

    The bucket is pre-seeded with stale ``compiled``/``preview`` values so the
    test proves they are *removed* (not merely absent), catching a regression
    that left a stale projection behind on the fail-safe-to-off path.
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
    assert "Tessera compile failed for entry entry-1" in caplog.text


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
