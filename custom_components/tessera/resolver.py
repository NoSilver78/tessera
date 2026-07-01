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
    """Subset of Home Assistant's device registry used by Tessera."""

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
        return {
            device_id: _entry_str_value(device, "area_id")
            for device_id, device in self._device_registry.devices.items()
        }

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


def _effective_area_id(
    entry: Any, device_areas: Mapping[Any, str | None]
) -> str | None:
    """Return direct entity area, falling back to device area only when absent."""
    direct_area = _entry_str_value(entry, "area_id")
    if direct_area is not None:
        return direct_area

    device_id = _entry_value(entry, "device_id")
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


def _is_disabled(entry: Any) -> bool:
    return _entry_value(entry, "disabled_by") is not None
