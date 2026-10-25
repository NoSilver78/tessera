"""End-to-end contract: what Tessera grants is what Home Assistant grants.

Every other test checks one link of the chain in isolation — the resolver
against registry doubles, the compiler against a FakeResolver, the auth
adapters against FakeHass. That leaves the one question a permissions product
actually has to answer unasked: does an administrator's grant end up as exactly
that permission inside Home Assistant?

These tests run the real chain against the *installed* HA:

    grant (store) -> AreaEntityResolver -> compile_policies -> PolicyPermissions

and assert the resulting ``check_entity`` answers for granted *and* ungranted
entities. This is the regression net for semantic drift, the class of bug where
every unit test stays green because every double still matches its protocol: HA
2026.9 started inheriting a child device's area from its parent, Tessera's
resolver did not, and area grants silently covered fewer entities than the
matrix showed. A child device is therefore part of the fixture below.

No ``hass`` fixture on purpose, so these run in the bare per-line contract
environments of the CI matrix. See docs/MAINTENANCE.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

import pytest
from custom_components.tessera.compiler import compile_policies
from custom_components.tessera.resolver import AreaEntityResolver
from custom_components.tessera.schema import default_config_data, default_policy_data

pytest.importorskip(
    "homeassistant.auth.permissions",
    reason="contract tests need a real Home Assistant install",
)


@dataclass(frozen=True)
class Registry:
    """Registry double exposing Home Assistant-like storage maps."""

    entities: dict[str, Any] | None = None
    devices: Any = None
    areas: list[Any] | None = None
    child_devices: Any = None

    def async_list_areas(self) -> list[Any]:
        """Return the fake areas."""
        return list(self.areas or [])


@dataclass(frozen=True)
class Entry:
    """Registry entry double mirroring the HA fields Tessera reads."""

    area_id: str | None = None
    device_id: str | None = None
    disabled_by: str | None = None
    id: str | None = None
    floor_id: str | None = None
    labels: Any = None
    parent_device_id: str | None = None


def _resolver() -> AreaEntityResolver:
    """Build a resolver over a living-room area that includes a child device.

    ``light.sofa`` sits on a normal device in the area, ``sensor.child_probe``
    on a child device that inherits the area from its parent, and
    ``switch.garage`` is in a different area so the negative case is real.
    """
    return AreaEntityResolver(
        cast(
            Any,
            Registry(
                entities={
                    "light.sofa": Entry(device_id="device-living"),
                    "sensor.child_probe": Entry(device_id="child-living"),
                    "switch.garage": Entry(device_id="device-garage"),
                }
            ),
        ),
        cast(
            Any,
            Registry(
                devices={
                    "device-living": Entry(area_id="living_room"),
                    "device-garage": Entry(area_id="garage"),
                },
                child_devices={"child-living": Entry(parent_device_id="device-living")},
            ),
        ),
        cast(Any, Registry(areas=[])),
    )


def _compiled_policy(grant: dict[str, Any]) -> dict[str, Any]:
    """Compile one living-room area grant for the ``viewer`` role."""
    config = default_config_data()
    config["roles"] = {"viewer": {"name": "Viewer"}}
    policy = default_policy_data()
    policy["area_grants"] = {"living_room": {"viewer": grant}}

    compiled = compile_policies(config, policy, _resolver())
    return cast(dict[str, Any], compiled["viewer"])


def test_read_grant_reaches_home_assistant_for_every_entity_in_the_area() -> None:
    """A read grant on an area is a read permission on each of its entities.

    Includes the child-device entity: if Tessera's area resolution ever drifts
    from HA's again, this is the assertion that fails.
    """
    from homeassistant.auth.permissions import PolicyPermissions

    permissions = PolicyPermissions(
        _compiled_policy({"read": True}),
        None,  # type: ignore[arg-type]
    )

    assert permissions.check_entity("light.sofa", "read") is True
    assert permissions.check_entity("sensor.child_probe", "read") is True


def test_entities_outside_the_granted_area_stay_denied() -> None:
    """Allow-only means everything not granted is denied by omission."""
    from homeassistant.auth.permissions import PolicyPermissions

    permissions = PolicyPermissions(
        _compiled_policy({"read": True}),
        None,  # type: ignore[arg-type]
    )

    assert permissions.check_entity("switch.garage", "read") is False
    assert permissions.check_entity("light.never_registered", "read") is False


def test_read_grant_does_not_leak_control_or_edit() -> None:
    """The stages stay separate all the way into HA's own check."""
    from homeassistant.auth.permissions import PolicyPermissions

    permissions = PolicyPermissions(
        _compiled_policy({"read": True}),
        None,  # type: ignore[arg-type]
    )

    assert permissions.check_entity("light.sofa", "control") is False
    assert permissions.check_entity("light.sofa", "edit") is False


def test_control_grant_reaches_home_assistant_as_control() -> None:
    """A control grant arrives as control, on the child device's entity too."""
    from homeassistant.auth.permissions import PolicyPermissions

    permissions = PolicyPermissions(
        _compiled_policy({"read": True, "control": True}),
        None,  # type: ignore[arg-type]
    )

    assert permissions.check_entity("light.sofa", "control") is True
    assert permissions.check_entity("sensor.child_probe", "control") is True
    assert permissions.check_entity("switch.garage", "control") is False


def test_role_without_grants_is_granted_nothing() -> None:
    """An ungranted role compiles to a policy HA grants nothing from."""
    from homeassistant.auth.permissions import PolicyPermissions

    config = default_config_data()
    config["roles"] = {"viewer": {"name": "Viewer"}}
    compiled = compile_policies(config, default_policy_data(), _resolver())

    permissions = PolicyPermissions(
        cast(dict[str, Any], compiled["viewer"]),
        None,  # type: ignore[arg-type]
    )

    assert permissions.check_entity("light.sofa", "read") is False
    assert permissions.check_entity("sensor.child_probe", "read") is False
    assert permissions.check_entity("switch.garage", "read") is False
