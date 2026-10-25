"""Contract tests for the device-registry shapes Tessera's resolver reads.

``AreaEntityResolver`` resolves areas, floors and labels out of Home Assistant's
device registry. Two of its assumptions are about registry *shape* rather than
about Tessera's own code, and the rest of the suite exercises them against
dict/dataclass doubles that cannot drift:

1. ``DeviceRegistry.devices`` is a real mapping on the older validated lines and
   an iterable-only view from HA 2026.9 (mapping access is deprecated there and
   is removed in 2027.9). ``_iter_device_entries`` branches on exactly that with
   ``isinstance(..., Mapping)``, so the branch has to keep matching reality.
2. Child devices (HA 2026.9+) live in ``DeviceRegistry.child_devices`` and carry
   ``id``, ``area_id`` and ``parent_device_id`` — the three fields
   ``_device_area_by_id`` reads to inherit a parent's area.

These tests assert both against whatever Home Assistant is installed, so a
breaking upstream change surfaces in CI instead of as a silently too-narrow
area grant on a user's instance. Same contract-test idea as
``test_ha_auth_contract.py``; see docs/MAINTENANCE.md for the workflow.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import attr
import pytest

ha_const = pytest.importorskip(
    "homeassistant.const", reason="contract tests need a real Home Assistant install"
)
dr = pytest.importorskip(
    "homeassistant.helpers.device_registry",
    reason="contract tests need a real Home Assistant install",
)

HA_VERSION: str = ha_const.__version__

# Private by nature: this is the shim HA hands out as ``DeviceRegistry.devices``
# once mapping access is deprecated. Absent on 2026.7/2026.8.
_DEPRECATED_VIEW: Any = getattr(dr, "_DeprecatedDeviceRegistryItemsView", None)


def test_installed_registry_items_container_is_still_a_mapping() -> None:
    """The mapping branch of ``_iter_device_entries`` stays reachable.

    On HA 2026.7/2026.8 ``DeviceRegistry.devices`` *is* this container, so the
    resolver reads it as a mapping and takes the device id from the key.
    """
    items = getattr(dr, "DeviceRegistryItems", None)
    assert items is not None, "DeviceRegistryItems is gone from device_registry"
    assert issubclass(items, Mapping), (
        "DeviceRegistryItems is no longer a Mapping — the resolver's mapping "
        "branch would stop matching the older validated HA lines"
    )


@pytest.mark.skipif(
    _DEPRECATED_VIEW is None,
    reason=f"HA {HA_VERSION} still exposes DeviceRegistry.devices as a mapping",
)
def test_deprecated_devices_view_is_not_a_mapping_and_iterates_entries() -> None:
    """From HA 2026.9 the view must land in the resolver's iteration branch.

    Two properties matter and both are asserted here: the view is *not* a
    ``Mapping`` (otherwise ``_iter_device_entries`` would call the deprecated
    ``items()`` and break in HA 2027.9), and iterating it yields the entries
    themselves, which is where the device id then comes from.
    """
    assert not issubclass(_DEPRECATED_VIEW, Mapping)

    view = _DEPRECATED_VIEW({"device-living": "entry-living"})

    assert not isinstance(view, Mapping)
    assert list(iter(view)) == ["entry-living"], (
        "iterating DeviceRegistry.devices no longer yields the entries — "
        "_iter_device_entries would read device ids off the wrong objects"
    )


@pytest.mark.skipif(
    not hasattr(dr, "ChildDeviceEntry"),
    reason=f"HA {HA_VERSION} has no child devices",
)
def test_installed_child_device_entry_carries_the_fields_the_resolver_reads() -> None:
    """``ChildDeviceEntry`` still exposes id, own area and parent reference."""
    fields = {field.name for field in attr.fields(dr.ChildDeviceEntry)}

    assert {
        "id",
        "area_id",
        "parent_device_id",
    } <= fields, (
        f"ChildDeviceEntry lost fields the resolver reads (has: {sorted(fields)})"
    )


@pytest.mark.skipif(
    not hasattr(dr, "ChildDeviceEntry"),
    reason=f"HA {HA_VERSION} has no child devices",
)
def test_installed_device_registry_still_exposes_child_devices() -> None:
    """The registry keeps a ``child_devices`` collection for the resolver to read.

    Checked on the class annotation because the attribute itself only exists on
    an instance, which would need a ``hass`` fixture — and these contract tests
    deliberately run against a bare Home Assistant install.
    """
    annotations = getattr(dr.DeviceRegistry, "__annotations__", {})

    assert "child_devices" in annotations, (
        "DeviceRegistry.child_devices is gone — child devices would silently "
        "drop out of area, floor and label grants again"
    )


@pytest.mark.skipif(
    not hasattr(dr, "async_get_effective_area_id"),
    reason=f"HA {HA_VERSION} has no effective-area helper",
)
def test_effective_area_helper_still_exists_as_the_rule_we_mirror() -> None:
    """HA's own effective-area helper is the rule ``_device_area_by_id`` mirrors.

    Tessera cannot call it (it needs ``hass`` and a device entry, while the
    resolver works off registry-like objects), so it reimplements the one-hop
    parent fallback. If HA's helper changes shape, the mirror needs a look.
    """
    assert callable(dr.async_get_effective_area_id)
