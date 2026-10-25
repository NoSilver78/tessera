"""Area-to-entity resolver for Tessera's phase-1 compiler."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, Self, cast

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


class EntityRegistryLike(Protocol):
    """Subset of Home Assistant's entity registry used by Tessera."""

    entities: Mapping[str, Any]


class DeviceRegistryLike(Protocol):
    """Subset of Home Assistant's device registry used by Tessera.

    ``devices`` is declared as a mapping because that is what it is on the older
    validated HA lines and in the test doubles; from HA 2026.9 the real
    attribute is an iterable view whose mapping methods are deprecated, which
    ``AreaEntityResolver._iter_device_entries`` handles. ``child_devices``
    (HA 2026.9+) is deliberately *not* part of this protocol: it is absent on
    2026.7/2026.8, so it is probed with ``getattr`` instead of accessed.
    """

    devices: Mapping[str, Any]


class AreaRegistryLike(Protocol):
    """Subset of Home Assistant's area registry used by Tessera."""

    def async_list_areas(self) -> list[Any]:
        """Return Home Assistant area entries."""


@dataclass(frozen=True)
class AreaEntityResolution:
    """Resolved entity ids for one or more areas."""

    entity_ids: tuple[str, ...]
    by_area: dict[str, tuple[str, ...]]


class AreaEntityResolver:
    """Resolve Home Assistant areas into concrete entity ids.

    Home Assistant's native area permissions primarily expand device-area
    membership. Tessera also needs direct entity ``area_id`` assignments so
    policies do not silently miss registry entries without a device.
    """

    def __init__(
        self,
        entity_registry: EntityRegistryLike,
        device_registry: DeviceRegistryLike,
        area_registry: AreaRegistryLike,
    ) -> None:
        """Initialize the resolver from registry-like objects."""
        self._entity_registry = entity_registry
        self._device_registry = device_registry
        self._area_registry = area_registry

    @classmethod
    def from_hass(cls, hass: HomeAssistant) -> Self:
        """Create a resolver from Home Assistant's live registries."""
        from homeassistant.helpers import area_registry as ar
        from homeassistant.helpers import device_registry as dr
        from homeassistant.helpers import entity_registry as er

        return cls(
            cast(EntityRegistryLike, er.async_get(hass)),
            cast(DeviceRegistryLike, dr.async_get(hass)),
            cast(AreaRegistryLike, ar.async_get(hass)),
        )

    def entity_ids_for_area(self, area_id: str) -> tuple[str, ...]:
        """Resolve one area id to sorted, de-duplicated entity ids."""
        return self.entity_ids_for_areas([area_id]).by_area[area_id]

    def entity_ids_for_floor(self, floor_id: str) -> tuple[str, ...]:
        """Resolve one floor id to sorted, de-duplicated entity ids.

        Fail closed on a falsy floor id: an empty string or ``None`` must never
        collide with floorless areas (which carry ``floor_id=None``) and leak
        every unassigned entity. ``_area_floor_by_id`` additionally drops floorless
        areas so no ``None`` key can structurally match — defense in depth.
        """
        if not floor_id:
            return ()
        area_ids = [
            area_id
            for area_id, area_floor_id in self._area_floor_by_id().items()
            if area_floor_id == floor_id
        ]
        return self.entity_ids_for_areas(area_ids).entity_ids

    def entity_ids_for_label(self, label_id: str) -> tuple[str, ...]:
        """Resolve one label id to sorted, de-duplicated entity ids.

        Scope is the union of the three label sources Home Assistant itself
        expands a label target into (``helpers/service.py``): entities carrying the
        label directly, entities whose device carries it, and entities whose
        effective area carries it. "Device" covers child devices (HA 2026.9+)
        carrying the label themselves — HA never inherits a label from the
        parent, so only the *area* of a child device falls back to its parent.
        Like Tessera's area/floor resolution — and unlike
        HA's *service-target* filtering — it deliberately does NOT drop
        config/diagnostic (``entity_category``) or hidden entities: a scope grant
        covers everything registry-assigned to that scope (mirrors
        ``entity_ids_for_areas``, asserted by ``test_includes_hidden_entities``).
        Disabled entities are excluded.

        Fail closed on a falsy label id: an empty string or ``None`` must never
        match entries that structurally carry no label and leak everything. Device
        keys are likewise guarded so a falsy device id can never collide with
        device-less entities (parity with the floor path's None-key defenses).
        """
        if not label_id:
            return ()
        labeled_devices = {
            device_id
            for device_id, device in self._all_device_entries()
            if device_id and label_id in _entry_labels(device)
        }
        labeled_areas = {
            area_id
            for area_id, area_labels in self._area_labels_by_id().items()
            if label_id in area_labels
        }
        device_areas = self._device_area_by_id()
        matched: set[str] = set()
        for entity_id, entry in self._entity_registry.entities.items():
            if _is_disabled(entry):
                continue
            if (
                label_id in _entry_labels(entry)
                or _entry_value(entry, "device_id") in labeled_devices
                or _effective_area_id(entry, device_areas) in labeled_areas
            ):
                matched.add(str(entity_id))
        return tuple(sorted(matched))

    def entity_ids_for_areas(self, area_ids: Iterable[str]) -> AreaEntityResolution:
        """Resolve multiple area ids to sorted, de-duplicated entity ids."""
        requested = tuple(dict.fromkeys(area_ids))
        device_areas = self._device_area_by_id()
        resolved: dict[str, set[str]] = {area_id: set() for area_id in requested}

        for entity_id, entry in self._entity_registry.entities.items():
            if _is_disabled(entry):
                continue

            area_id = _effective_area_id(entry, device_areas)
            if area_id in resolved:
                resolved[area_id].add(str(entity_id))

        by_area = {
            area_id: tuple(sorted(entity_ids))
            for area_id, entity_ids in resolved.items()
        }
        all_entity_ids = tuple(
            sorted(
                {
                    entity_id
                    for entity_ids in by_area.values()
                    for entity_id in entity_ids
                }
            )
        )
        return AreaEntityResolution(entity_ids=all_entity_ids, by_area=by_area)

    def _device_area_by_id(self) -> dict[Any, str | None]:
        """Map device id to its *effective* area id.

        A child device (HA 2026.9+) without an own area inherits its parent's
        area — the same rule as ``device_registry.async_get_effective_area_id``,
        which Home Assistant itself applies when it expands an area policy.
        Resolving the raw ``area_id`` only would drop those entities out of an
        area, floor or label grant although HA shows them in that area: a grant
        narrower than the matrix promises. An area set on the child itself
        always wins; labels are never inherited (HA rule), so only the area
        falls back.
        """
        areas: dict[Any, str | None] = {
            device_id: _entry_str_value(device, "area_id")
            for device_id, device in self._iter_device_entries()
        }
        for device_id, child in self._iter_child_device_entries():
            area_id = _entry_str_value(child, "area_id")
            if area_id is None:
                parent_id = _entry_value(child, "parent_device_id")
                # A parent is always a main device, so one hop is the whole
                # chain. A falsy or dangling parent reference resolves to no
                # area instead of colliding with device-less entries.
                area_id = areas.get(parent_id) if parent_id else None
            areas[device_id] = area_id
        return areas

    def _iter_device_entries(self) -> list[tuple[Any, Any]]:
        """Return ``(device_id, entry)`` pairs for Home Assistant's main devices.

        HA 2026.9 deprecated *mapping* access to ``DeviceRegistry.devices``:
        every ``items()``/``get()``/``[]`` call is reported via ``report_usage``
        (a log line for custom integrations, removed in 2027.9), while plain
        iteration keeps yielding the entries and stays supported. The older
        validated lines (2026.7/2026.8) and the test doubles hand over a real
        mapping, where the key is the only place the device id lives — so a
        mapping is read as one and everything else is iterated. That makes the
        access path follow the registry's own shape, with no HA version check.
        """
        devices: Any = self._device_registry.devices
        if isinstance(devices, Mapping):
            return list(devices.items())
        return [(_entry_value(entry, "id"), entry) for entry in devices]

    def _iter_child_device_entries(self) -> list[tuple[Any, Any]]:
        """Return ``(device_id, entry)`` pairs for child devices, where HA has them.

        ``DeviceRegistry.child_devices`` exists from HA 2026.9 and is a plain
        collection of entries there; on 2026.7/2026.8 the attribute is absent
        and there is nothing to add.
        """
        children: Any = getattr(self._device_registry, "child_devices", None)
        if children is None:
            return []
        if isinstance(children, Mapping):
            return list(children.items())
        return [(_entry_value(entry, "id"), entry) for entry in children]

    def _all_device_entries(self) -> list[tuple[Any, Any]]:
        """Return main *and* child devices as ``(device_id, entry)`` pairs."""
        return self._iter_device_entries() + self._iter_child_device_entries()

    def _area_floor_by_id(self) -> dict[str, str]:
        """Map area id to floor id, omitting floorless areas.

        Floorless areas carry ``floor_id=None``; excluding them means a ``None``
        or empty floor query can never match, so floor resolution stays fail-closed.
        """
        return {
            area_id: area_floor_id
            for area in self._area_registry.async_list_areas()
            if (area_id := _entry_str_value(area, "id")) is not None
            and (area_floor_id := _entry_str_value(area, "floor_id"))
        }

    def _area_labels_by_id(self) -> dict[str, frozenset[str]]:
        """Map area id to its label-id set, for label→entity area inheritance."""
        return {
            area_id: _entry_labels(area)
            for area in self._area_registry.async_list_areas()
            if (area_id := _entry_str_value(area, "id")) is not None
        }


def _effective_area_id(
    entry: Any, device_areas: Mapping[Any, str | None]
) -> str | None:
    """Return direct entity area, falling back to device area only when absent.

    Fail closed on a falsy device id: a device entry stored under ``None`` or an
    empty string must never collide with device-less entities and hand them its
    area. Unreachable from live HA (device ids are uuid hex), guarded for parity
    with the label path's device-key guard and the floor path's None-key
    defenses.
    """
    direct_area = _entry_str_value(entry, "area_id")
    if direct_area is not None:
        return direct_area

    device_id = _entry_value(entry, "device_id")
    if not device_id:
        return None
    return device_areas.get(device_id)


def _entry_value(entry: Any, key: str) -> Any:
    """Return a registry entry field from object or mapping entries."""
    if isinstance(entry, Mapping):
        return entry.get(key)
    return getattr(entry, key, None)


def _entry_str_value(entry: Any, key: str) -> str | None:
    value = _entry_value(entry, key)
    if isinstance(value, str):
        return value
    return None


def _entry_labels(entry: Any) -> frozenset[str]:
    """Return a registry entry's label ids from object or mapping entries."""
    value = _entry_value(entry, "labels")
    if isinstance(value, (set, frozenset, list, tuple)):
        return frozenset(str(label) for label in value)
    return frozenset()


def _is_disabled(entry: Any) -> bool:
    return _entry_value(entry, "disabled_by") is not None
