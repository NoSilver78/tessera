"""Tests for Tessera area-to-entity resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from custom_components.tessera.resolver import AreaEntityResolver


@dataclass(frozen=True)
class Registry:
    """Small registry object exposing Home Assistant-like storage maps."""

    entities: dict[str, Any] | None = None
    devices: dict[str, Any] | None = None
    areas: list[Any] | None = None

    def __post_init__(self) -> None:
        """Allow one fake class to stand in for entity and device registries."""
        if self.entities is None and self.devices is None and self.areas is None:
            raise ValueError("fake registry needs entities or devices")

    def async_list_areas(self) -> list[Any]:
        """Return fake Home Assistant areas."""
        return list(self.areas or [])


@dataclass(frozen=True)
class Entry:
    """Object-style registry entry used to mirror HA entries."""

    area_id: str | None = None
    device_id: str | None = None
    disabled_by: str | None = None
    hidden_by: str | None = None
    id: str | None = None
    floor_id: str | None = None
    labels: Any = None


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
        Registry(areas=[]),
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
        Registry(areas=[]),
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
        Registry(areas=[]),
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
        Registry(areas=[]),
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
        Registry(areas=[]),
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
        Registry(areas=[]),
    )

    assert resolver.entity_ids_for_area("living_room") == ("sensor.hidden",)


def test_missing_device_does_not_resolve() -> None:
    """Entity device ids without registry entries do not create area matches."""
    resolver = AreaEntityResolver(
        Registry(entities={"sensor.orphan": Entry(device_id="missing-device")}),
        Registry(devices={}),
        Registry(areas=[]),
    )

    assert resolver.entity_ids_for_area("living_room") == ()


def test_resolves_floor_as_union_of_area_entities() -> None:
    """Floor resolution expands through all areas assigned to that floor."""
    resolver = AreaEntityResolver(
        Registry(
            entities={
                "light.ug": Entry(area_id="ug_room"),
                "sensor.ug_device": Entry(device_id="device-ug"),
                "light.eg": Entry(area_id="eg_room"),
            }
        ),
        Registry(devices={"device-ug": Entry(area_id="ug_hall")}),
        Registry(
            areas=[
                Entry(id="ug_room", floor_id="ug"),
                Entry(id="ug_hall", floor_id="ug"),
                Entry(id="eg_room", floor_id="eg"),
            ]
        ),
    )

    assert resolver.entity_ids_for_floor("ug") == ("light.ug", "sensor.ug_device")


def test_floor_resolution_deduplicates_and_sorts_entities() -> None:
    """A floor entity resolved through direct and device paths is emitted once."""
    resolver = AreaEntityResolver(
        Registry(
            entities={
                "sensor.z": Entry(area_id="living", device_id="device-living"),
                "sensor.a": Entry(area_id="living"),
            }
        ),
        Registry(devices={"device-living": Entry(area_id="living")}),
        Registry(areas=[Entry(id="living", floor_id="eg")]),
    )

    assert resolver.entity_ids_for_floor("eg") == ("sensor.a", "sensor.z")


def test_floor_without_areas_and_unknown_floor_are_empty() -> None:
    """Resolver misses are deny-by-omission, not exceptions."""
    resolver = AreaEntityResolver(
        Registry(entities={"light.a": Entry(area_id="living")}),
        Registry(devices={}),
        Registry(areas=[Entry(id="living", floor_id="eg")]),
    )

    assert resolver.entity_ids_for_floor("ug") == ()
    assert resolver.entity_ids_for_floor("missing") == ()


def test_floorless_areas_never_leak_for_none_or_empty_floor() -> None:
    """A falsy floor query must not collide with floorless areas (fail closed).

    Floorless areas carry ``floor_id=None`` internally; a ``None`` or empty
    floor query must resolve to nothing rather than every unassigned entity.
    """
    resolver = AreaEntityResolver(
        Registry(
            entities={
                "light.orphan": Entry(area_id="no_floor"),
                "light.eg": Entry(area_id="eg_room"),
            }
        ),
        Registry(devices={}),
        Registry(
            areas=[
                Entry(id="no_floor"),
                Entry(id="eg_room", floor_id="eg"),
            ]
        ),
    )

    assert resolver.entity_ids_for_floor(cast(str, None)) == ()
    assert resolver.entity_ids_for_floor("") == ()
    assert resolver.entity_ids_for_floor("eg") == ("light.eg",)


def test_label_resolves_direct_entity_label() -> None:
    """An entity carrying the label directly is in scope."""
    resolver = AreaEntityResolver(
        Registry(entities={"light.a": Entry(labels={"cozy"}), "light.b": Entry()}),
        Registry(devices={}),
        Registry(areas=[]),
    )

    assert resolver.entity_ids_for_label("cozy") == ("light.a",)


def test_label_resolves_via_device_label() -> None:
    """An entity inherits a label carried by its device (HA label semantics)."""
    resolver = AreaEntityResolver(
        Registry(
            entities={
                "light.a": Entry(device_id="d1"),
                "light.b": Entry(device_id="d2"),
            }
        ),
        Registry(devices={"d1": Entry(labels={"media"}), "d2": Entry()}),
        Registry(areas=[]),
    )

    assert resolver.entity_ids_for_label("media") == ("light.a",)


def test_label_resolves_via_area_label_direct_and_device() -> None:
    """An area label reaches entities in the area, whether direct or via device."""
    resolver = AreaEntityResolver(
        Registry(
            entities={
                "light.direct": Entry(area_id="living"),
                "light.dev": Entry(device_id="d1"),
                "light.other": Entry(area_id="kitchen"),
            }
        ),
        Registry(devices={"d1": Entry(area_id="living")}),
        Registry(areas=[Entry(id="living", labels={"guest"}), Entry(id="kitchen")]),
    )

    assert resolver.entity_ids_for_label("guest") == ("light.dev", "light.direct")


def test_label_unions_and_deduplicates_across_paths() -> None:
    """The three label paths union; an entity matched twice is emitted once."""
    resolver = AreaEntityResolver(
        Registry(entities={"light.a": Entry(area_id="living", labels={"cozy"})}),
        Registry(devices={}),
        Registry(areas=[Entry(id="living", labels={"cozy"})]),
    )

    assert resolver.entity_ids_for_label("cozy") == ("light.a",)


def test_label_empty_id_is_fail_closed() -> None:
    """A falsy label id resolves to nothing, never to every entity."""
    resolver = AreaEntityResolver(
        Registry(entities={"light.a": Entry(labels={"cozy"})}),
        Registry(devices={}),
        Registry(areas=[]),
    )

    assert resolver.entity_ids_for_label("") == ()
    assert resolver.entity_ids_for_label(cast(str, None)) == ()


def test_label_skips_disabled_entities() -> None:
    """A disabled entity carrying the label is not a compile target."""
    resolver = AreaEntityResolver(
        Registry(
            entities={
                "light.on": Entry(labels={"cozy"}),
                "light.off": Entry(labels={"cozy"}, disabled_by="user"),
            }
        ),
        Registry(devices={}),
        Registry(areas=[]),
    )

    assert resolver.entity_ids_for_label("cozy") == ("light.on",)


def test_label_unknown_returns_empty() -> None:
    """An unknown label resolves to nothing (deny by omission)."""
    resolver = AreaEntityResolver(
        Registry(entities={"light.a": Entry(labels={"cozy"})}),
        Registry(devices={}),
        Registry(areas=[]),
    )

    assert resolver.entity_ids_for_label("missing") == ()


def test_label_falsy_device_key_does_not_leak_deviceless_entities() -> None:
    """A falsy device key carrying the label must not collide with device-less entities.

    Unreachable from live HA (device ids are always uuid hex), but guarded as
    defense in depth for parity with the floor path's None-key handling.
    """
    resolver = AreaEntityResolver(
        Registry(
            entities={
                "light.orphan": Entry(),
                "light.tagged": Entry(labels={"cozy"}),
            }
        ),
        Registry(devices={None: Entry(labels={"cozy"})}),
        Registry(areas=[]),
    )

    assert resolver.entity_ids_for_label("cozy") == ("light.tagged",)
