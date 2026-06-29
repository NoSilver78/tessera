"""Tessera — RBAC for Home Assistant.

Store -> Compiler -> native HA ``PolicyPermissions``. The store is the single
source of truth; the compiler projects it into native group policies. See
``docs/spec-phase1-core.md`` for the architecture.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from homeassistant.components.frontend import async_remove_panel
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.panel_custom import async_register_panel

from . import websocket as tessera_websocket
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
DATA_WEBSOCKET_REGISTERED = "__websocket_registered"
DATA_PANEL_REGISTERED = "__panel_registered"
PANEL_URL_PATH = "tessera"
PANEL_WEBCOMPONENT = "tessera-matrix-panel"
PANEL_STATIC_URL = "/tessera_static/tessera-panel.js"
PANEL_STATIC_DIR = Path(__file__).parent / "static"


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
    _register_websocket_api(hass)
    await _async_register_matrix_panel(hass)
    await _compile_for_mode_safely(hass, entry.entry_id, domain_data[entry.entry_id])
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
    domain_data = _domain_data(hass)
    domain_data.pop(entry.entry_id, None)
    if not _has_loaded_entries(domain_data):
        if domain_data.pop(DATA_PANEL_REGISTERED, None) is True:
            async_remove_panel(hass, PANEL_URL_PATH, warn_if_unknown=False)
        hass.services.async_remove(DOMAIN, SERVICE_RECOMPILE)
        domain_data.pop(DATA_SERVICE_REGISTERED, None)
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
            await _compile_for_mode_safely(hass, key, entry_data)

    hass.services.async_register(DOMAIN, SERVICE_RECOMPILE, _handle_recompile)
    domain_data[DATA_SERVICE_REGISTERED] = True


def _register_websocket_api(hass: HomeAssistant) -> None:
    """Register Tessera's WebSocket API once per HA instance."""
    domain_data = _domain_data(hass)
    if domain_data.get(DATA_WEBSOCKET_REGISTERED) is True:
        return

    tessera_websocket.async_register(hass)
    domain_data[DATA_WEBSOCKET_REGISTERED] = True


async def _async_register_matrix_panel(hass: HomeAssistant) -> None:
    """Register the Tessera custom panel and its static JS module."""
    domain_data = _domain_data(hass)
    if domain_data.get(DATA_PANEL_REGISTERED) is True:
        return
    if not hasattr(hass, "http"):
        LOGGER.debug("Skipping Tessera panel registration without HA HTTP server")
        return

    await hass.http.async_register_static_paths(
        [StaticPathConfig("/tessera_static", str(PANEL_STATIC_DIR), False)]
    )
    await async_register_panel(
        hass,
        frontend_url_path=PANEL_URL_PATH,
        webcomponent_name=PANEL_WEBCOMPONENT,
        sidebar_title="Tessera",
        sidebar_icon="mdi:shield-account",
        module_url=PANEL_STATIC_URL,
        require_admin=True,
        config_panel_domain=DOMAIN,
    )
    domain_data[DATA_PANEL_REGISTERED] = True


async def _compile_for_mode_safely(
    hass: HomeAssistant, entry_id: str, entry_data: dict[str, Any]
) -> None:
    """Compile monitor previews, falling back to effective off on errors."""
    try:
        await _compile_for_mode(hass, entry_id, entry_data)
    except Exception as err:
        entry_data.pop("compiled", None)
        entry_data.pop("preview", None)
        LOGGER.error(
            "Tessera compile failed for entry %s; falling back to effective off "
            "mode (%s)",
            entry_id,
            err.__class__.__name__,
        )


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


def _has_loaded_entries(domain_data: dict[str, Any]) -> bool:
    """Return whether the domain bucket still contains entry data."""
    return any(
        key != DATA_SERVICE_REGISTERED and isinstance(value, dict)
        for key, value in domain_data.items()
    )
