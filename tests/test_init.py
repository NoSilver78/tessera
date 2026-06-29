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
