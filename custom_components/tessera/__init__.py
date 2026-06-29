"""Tessera — RBAC for Home Assistant.

Store -> Compiler -> native HA ``PolicyPermissions``. The store is the single
source of truth; the compiler projects it into native group policies. See
``docs/spec-phase1-core.md`` for the architecture.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .const import DOMAIN
from .store import TesseraStore

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tessera from a config entry.

    Args:
        hass: The Home Assistant instance.
        entry: The config entry being set up.

    Returns:
        ``True`` once setup succeeds.
    """
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"store": TesseraStore(hass)}
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
