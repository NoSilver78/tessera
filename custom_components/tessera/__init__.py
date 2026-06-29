"""Tessera — RBAC for Home Assistant.

Store -> Compiler -> native HA ``PolicyPermissions``. The store is the single
source of truth; the compiler projects it into native group policies. See
``docs/spec-phase1-core.md`` for the architecture.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

from .const import DOMAIN, MODE_ENFORCE, MODE_MONITOR, MODE_OFF
from .monitor import compile_current, log_monitor_preview
from .resolver import AreaEntityResolver
from .store import TesseraStore

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

LOGGER = logging.getLogger(__name__)
SERVICE_RECOMPILE = "recompile"
DATA_SERVICE_REGISTERED = "__recompile_service_registered"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tessera from a config entry.

    Args:
        hass: The Home Assistant instance.
        entry: The config entry being set up.

    Returns:
        ``True`` once setup succeeds.
    """
    domain_data = _domain_data(hass)
    domain_data[entry.entry_id] = {"store": TesseraStore(hass)}
    _register_recompile_service(hass)
    await _compile_for_mode(hass, entry.entry_id, domain_data[entry.entry_id])
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry.

    Must restore native policies on unload in a later phase so that removing
    Tessera never leaves users locked out.

    Args:
        hass: The Home Assistant instance.
        entry: The config entry being unloaded.

    Returns:
        ``True`` once unload succeeds.
    """
    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return True


def _register_recompile_service(hass: HomeAssistant) -> None:
    """Register the monitor-mode recompilation service once per HA instance."""
    domain_data = _domain_data(hass)
    if domain_data.get(DATA_SERVICE_REGISTERED) is True:
        return

    async def _handle_recompile(call: object) -> None:
        """Recompile all loaded Tessera entries without native writes."""
        del call
        for key, entry_data in list(_domain_data(hass).items()):
            if key == DATA_SERVICE_REGISTERED or not isinstance(entry_data, dict):
                continue
            await _compile_for_mode(hass, key, entry_data)

    hass.services.async_register(DOMAIN, SERVICE_RECOMPILE, _handle_recompile)
    domain_data[DATA_SERVICE_REGISTERED] = True


async def _compile_for_mode(
    hass: HomeAssistant, entry_id: str, entry_data: dict[str, Any]
) -> None:
    """Compile and log policy previews for monitor-like modes only."""
    store = cast(TesseraStore, entry_data["store"])
    config = await store.async_load_config()

    if config["mode"] == MODE_OFF:
        entry_data.pop("compiled", None)
        entry_data.pop("preview", None)
        return

    if config["mode"] == MODE_ENFORCE:
        LOGGER.warning(
            "Tessera enforce mode requested for entry %s, but enforce is not "
            "implemented yet; running monitor preview only",
            entry_id,
        )

    if config["mode"] in {MODE_MONITOR, MODE_ENFORCE}:
        resolver = AreaEntityResolver.from_hass(hass)
        compiled = await compile_current(store, resolver, config=config)
        entry_data["compiled"] = compiled
        entry_data["preview"] = log_monitor_preview(compiled, mode=config["mode"])


def _domain_data(hass: HomeAssistant) -> dict[str, Any]:
    """Return the mutable Tessera domain data bucket."""
    return cast(dict[str, Any], hass.data.setdefault(DOMAIN, {}))
