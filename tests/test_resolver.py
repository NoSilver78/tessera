"""Tests for Tessera area-to-entity resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from custom_components.tessera.resolver import (
    AreaEntityResolver,
    resolve_all,
    resolve_area_entities,
)


@dataclass(frozen=True)
class Registry:
    """Small registry object exposing Home Assistant-like storage maps."""

    entities: dict[str, Any] | None = None
    devices: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        """Allow one fake class to stand in for entity and device registries."""
        if self.entities is None and self.devices is None:
            raise ValueError("fake registry needs entities or devices")


@dataclass(frozen=True)
class Entry:
    """Object-style registry entry used to mirror HA entries."""

    area_id: str | None = None
    device_id: str | None = None
    disabled_by: str | None = None
    hidden_by: str | None = None


def test_resolves_device_area_and_direct_entity_area() -> None:
    """Resolver includes both device-area and direct entity-area assignments."""
    resolver = AreaEntityResolver(
        Registry(
            entities={
                "light.sofa": Entry(device_id="device-living"),
                "sensor.living_direct": Entry(area_id="living_room"),
                "switch.kitchen": Entry(device_id="device-kitchen"),
                "sensor.unassigned": Entry(),
            }
        ),
        Registry(
            devices={
                "device-living": Entry(area_id="living_room"),
                "device-kitchen": Entry(area_id="kitchen"),
            }
        ),
    )

    assert resolver.entity_ids_for_area("living_room") == (
        "light.sofa",
        "sensor.living_direct",
    )


def test_deduplicates_entities_matching_direct_and_device_area() -> None:
    """One entity can match the same area through both registry paths."""
    resolver = AreaEntityResolver(
        Registry(
            entities={
                "light.table": {
                    "area_id": "living_room",
                    "device_id": "device-living",
                }
            }
        ),
        Registry(devices={"device-living": {"area_id": "living_room"}}),
    )

    assert resolver.entity_ids_for_area("living_room") == ("light.table",)


def test_direct_entity_area_overrides_device_area() -> None:
    """Direct entity area wins when it differs from the device area."""
    resolver = AreaEntityResolver(
        Registry(
            entities={
                "light.moved": Entry(
                    area_id="kitchen",
                    device_id="device-living",
                )
            }
        ),
        Registry(devices={"device-living": Entry(area_id="living_room")}),
    )

    assert resolver.entity_ids_for_area("living_room") == ()
    assert resolver.entity_ids_for_area("kitchen") == ("light.moved",)


def test_resolves_multiple_areas_with_combined_sorted_result() -> None:
    """Multi-area resolution returns per-area and combined sorted entities."""
    resolver = AreaEntityResolver(
        Registry(
            entities={
                "sensor.office": Entry(area_id="office"),
                "light.living": Entry(device_id="device-living"),
                "cover.living": Entry(area_id="living_room"),
            }
        ),
        Registry(devices={"device-living": Entry(area_id="living_room")}),
    )

    result = resolver.entity_ids_for_areas(["living_room", "office", "living_room"])

    assert result.by_area == {
        "living_room": ("cover.living", "light.living"),
        "office": ("sensor.office",),
    }
    assert result.entity_ids == (
        "cover.living",
        "light.living",
        "sensor.office",
    )


def test_skips_disabled_entities() -> None:
    """Disabled registry entries are not compile targets."""
    resolver = AreaEntityResolver(
        Registry(
            entities={
                "sensor.enabled": Entry(area_id="living_room"),
                "sensor.disabled": Entry(area_id="living_room", disabled_by="user"),
            }
        ),
        Registry(devices={}),
    )

    assert resolver.entity_ids_for_area("living_room") == ("sensor.enabled",)


def test_includes_hidden_entities() -> None:
    """Hidden registry entries remain policy targets unless disabled."""
    resolver = AreaEntityResolver(
        Registry(
            entities={
                "sensor.hidden": Entry(area_id="living_room", hidden_by="user"),
            }
        ),
        Registry(devices={}),
    )

    assert resolver.entity_ids_for_area("living_room") == ("sensor.hidden",)


def test_missing_device_does_not_resolve() -> None:
    """Entity device ids without registry entries do not create area matches."""
    resolver = AreaEntityResolver(
        Registry(entities={"sensor.orphan": Entry(device_id="missing-device")}),
        Registry(devices={}),
    )

    assert resolver.entity_ids_for_area("living_room") == ()


def test_function_contract_returns_sets() -> None:
    """Compiler-facing helpers expose the expected set-based contract."""
    entity_registry = Registry(
        entities={
            "light.sofa": Entry(device_id="device-living"),
            "sensor.office": Entry(area_id="office"),
        }
    )
    device_registry = Registry(devices={"device-living": Entry(area_id="living_room")})

    assert resolve_area_entities("living_room", entity_registry, device_registry) == {
        "light.sofa"
    }
    assert resolve_all(entity_registry, device_registry) == {
        "living_room": {"light.sofa"},
        "office": {"sensor.office"},
    }
