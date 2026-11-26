"""Recompile on registry and user changes, so native policies cannot drift.

A compiled ``tessera:`` policy is a snapshot of the registries at compile time.
Without these listeners it stayed in force until the next service call, options
edit or restart:

* an entity or device moved **out** of a granted area (or a label removed)
  kept its ``read``/``control`` grant — access the current policy no longer
  grants;
* after an entity rename the old id stayed in the policy, and a *new* entity
  later taking that id inherited the grant;
* a user created under ``enforce`` kept HA's default ``system-users`` (allow
  all) until someone recompiled.

Every relevant change schedules one debounced recompile through the same
guarded path as ``tessera.recompile`` (``mutation_lock`` → mode handling →
fail-safe on error). Bursts collapse into a single run per cooldown.

Feedback loop: Tessera's own native writes fire ``user_updated``. The
adapters skip writes that would not change anything, so the recompile a write
triggers finds nothing to do and fires nothing — the loop ends after one pass.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from homeassistant.core import Event, HomeAssistant, callback

LOGGER = logging.getLogger(__name__)

# Seconds between the first relevant change and the recompile. Short, because
# the window is a window of over-granted access; long enough to fold the burst
# an integration reload or a device move produces into one run.
RECOMPILE_COOLDOWN = 2.0

EVENT_ENTITY_REGISTRY_UPDATED = "entity_registry_updated"
EVENT_DEVICE_REGISTRY_UPDATED = "device_registry_updated"
EVENT_AREA_REGISTRY_UPDATED = "area_registry_updated"
EVENT_FLOOR_REGISTRY_UPDATED = "floor_registry_updated"
EVENT_LABEL_REGISTRY_UPDATED = "label_registry_updated"
EVENT_USER_ADDED = "user_added"
EVENT_USER_REMOVED = "user_removed"
EVENT_USER_UPDATED = "user_updated"

# Registry fields the resolver reads (resolver.py). An ``update`` that changes
# none of them cannot change a compiled policy — name or icon edits, say.
_ENTITY_FIELDS = frozenset({"area_id", "device_id", "labels", "disabled_by"})
_DEVICE_FIELDS = frozenset({"area_id", "labels", "disabled_by", "parent_device_id"})


def entity_change_is_relevant(data: Mapping[str, Any]) -> bool:
    """Return whether an entity-registry event can change a compiled policy."""
    if data.get("action") != "update":
        return True  # create / remove
    if "old_entity_id" in data:
        return True  # rename: the old id must leave the policy
    return _changes_touch(data, _ENTITY_FIELDS)


def device_change_is_relevant(data: Mapping[str, Any]) -> bool:
    """Return whether a device-registry event can change a compiled policy."""
    if data.get("action") != "update":
        return True
    return _changes_touch(data, _DEVICE_FIELDS)


def _changes_touch(data: Mapping[str, Any], fields: frozenset[str]) -> bool:
    changes = data.get("changes")
    if not isinstance(changes, Mapping):
        return True  # unknown shape: recompile rather than miss a change
    return not fields.isdisjoint(changes)


def _always(_data: Mapping[str, Any]) -> bool:
    return True


_LISTENED: tuple[tuple[str, Callable[[Mapping[str, Any]], bool]], ...] = (
    (EVENT_ENTITY_REGISTRY_UPDATED, entity_change_is_relevant),
    (EVENT_DEVICE_REGISTRY_UPDATED, device_change_is_relevant),
    (EVENT_AREA_REGISTRY_UPDATED, _always),
    (EVENT_FLOOR_REGISTRY_UPDATED, _always),
    (EVENT_LABEL_REGISTRY_UPDATED, _always),
    (EVENT_USER_ADDED, _always),
    (EVENT_USER_REMOVED, _always),
    (EVENT_USER_UPDATED, _always),
)


def async_setup_auto_recompile(
    hass: HomeAssistant,
    on_unload: Callable[[Callable[[], None]], None],
    recompile: Callable[[], Awaitable[None]],
) -> None:
    """Listen for relevant changes and schedule one debounced ``recompile``.

    ``on_unload`` is the config entry's ``async_on_unload``: every listener and
    the debouncer are torn down with the entry, so nothing fires into an
    unloaded integration.
    """
    from homeassistant.helpers.debounce import Debouncer

    debouncer: Debouncer[Awaitable[None]] = Debouncer(
        hass,
        LOGGER,
        cooldown=RECOMPILE_COOLDOWN,
        immediate=False,
        function=recompile,
    )
    on_unload(debouncer.async_shutdown)

    for event_type, is_relevant in _LISTENED:
        on_unload(
            hass.bus.async_listen(
                event_type, _listener(debouncer.async_schedule_call, is_relevant)
            )
        )


def _listener(
    schedule: Callable[[], None], is_relevant: Callable[[Mapping[str, Any]], bool]
) -> Callable[[Event[Any]], None]:
    @callback
    def _handle(event: Event[Any]) -> None:
        if is_relevant(event.data):
            schedule()

    return _handle
