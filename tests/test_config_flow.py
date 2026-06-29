"""Tests for Tessera config-flow option helpers."""

from __future__ import annotations

from typing import Any

import pytest
from custom_components.tessera.config_flow import (
    _compile_preview,
    add_area_grant,
    add_role,
    remove_area_grant,
    remove_role,
    set_mode,
)
from custom_components.tessera.const import DOMAIN
from custom_components.tessera.schema import (
    TesseraSchemaError,
    default_config_data,
    default_policy_data,
    validate_policy_data,
)


class FakeStore:
    """Store double used by config-flow preview tests."""

    async def async_load_config(self) -> dict[str, Any]:
        """Load unused fake config."""
        return default_config_data()

    async def async_load_policy(self) -> dict[str, Any]:
        """Load unused fake policy."""
        return default_policy_data()


class FakeResolver:
    """Deterministic resolver double."""

    def entity_ids_for_area(self, area_id: str) -> tuple[str, ...]:
        """Resolve one fake area."""
        return ("light.sofa",) if area_id == "living" else ()


class FakeHass:
    """Minimal HA object with auth access trapped."""

    def __init__(self) -> None:
        """Initialize HA-like storage."""
        self.data: dict[str, Any] = {}

    @property
    def auth(self) -> object:
        """Fail if config-flow basics touch native auth."""
        raise AssertionError("config UI must not touch hass.auth")


def test_set_mode_persists_schema_valid_mode() -> None:
    """Mode changes remain schema-validated."""
    config = set_mode(default_config_data(), "monitor")

    assert config["mode"] == "monitor"


def test_add_role_and_remove_role_updates_config_and_grants() -> None:
    """Role management keeps config and policy internally consistent."""
    config = add_role(
        default_config_data(),
        "viewer",
        name="Viewer",
        description="Read-only role",
    )
    config["membership"]["by_user"] = {"user-1": ["viewer"]}
    config["membership"]["by_group"] = {"authentik:tessera-test-eg": ["viewer"]}
    policy = add_area_grant(
        config,
        default_policy_data(),
        area_id="living",
        role_id="viewer",
        read=True,
        control=False,
    )

    next_config, next_policy = remove_role(config, policy, "viewer")

    assert config["roles"]["viewer"] == {
        "name": "Viewer",
        "description": "Read-only role",
    }
    assert next_config["roles"] == {}
    assert next_config["membership"]["by_user"] == {}
    assert next_config["membership"]["by_group"] == {}
    assert next_policy["area_grants"] == {}


def test_add_role_rejects_empty_role_id() -> None:
    """Role ids remain schema-validated."""
    with pytest.raises(TesseraSchemaError):
        add_role(default_config_data(), "")


def test_add_role_rejects_duplicate_role_id() -> None:
    """Adding roles does not silently replace an existing role."""
    config = add_role(default_config_data(), "viewer")

    with pytest.raises(TesseraSchemaError):
        add_role(config, "viewer")


def test_add_area_grant_is_schema_aware_and_never_bare_true() -> None:
    """Area grants store explicit permission leaves only."""
    config = add_role(default_config_data(), "operator")

    policy = add_area_grant(
        config,
        default_policy_data(),
        area_id="living",
        role_id="operator",
        read=False,
        control=True,
    )

    leaf = policy["area_grants"]["living"]["operator"]
    assert leaf == {"read": True, "control": True}
    assert leaf is not True
    assert validate_policy_data(policy) == policy


def test_add_area_grant_rejects_unknown_role_and_empty_leaf() -> None:
    """Invalid UI inputs are rejected before persistence."""
    config = add_role(default_config_data(), "viewer")

    with pytest.raises(TesseraSchemaError):
        add_area_grant(
            config,
            default_policy_data(),
            area_id="living",
            role_id="ghost",
            read=True,
            control=False,
        )

    with pytest.raises(TesseraSchemaError):
        add_area_grant(
            config,
            default_policy_data(),
            area_id="living",
            role_id="viewer",
            read=False,
            control=False,
        )


def test_remove_area_grant_deletes_empty_area_bucket() -> None:
    """Removing the final role grant removes the empty area target."""
    config = add_role(default_config_data(), "viewer")
    policy = add_area_grant(
        config,
        default_policy_data(),
        area_id="living",
        role_id="viewer",
        read=True,
        control=False,
    )

    assert remove_area_grant(policy, "living::viewer")["area_grants"] == {}


@pytest.mark.asyncio
async def test_compile_preview_updates_hass_data_without_native_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Options persistence refreshes monitor preview read-only."""
    config = add_role(set_mode(default_config_data(), "monitor"), "viewer")
    policy = add_area_grant(
        config,
        default_policy_data(),
        area_id="living",
        role_id="viewer",
        read=True,
        control=True,
    )
    hass = FakeHass()

    monkeypatch.setattr(
        "custom_components.tessera.config_flow.AreaEntityResolver.from_hass",
        classmethod(lambda cls, hass: FakeResolver()),
    )

    await _compile_preview(
        hass,
        "entry-1",
        FakeStore(),
        config=config,
        policy=policy,
    )

    assert hass.data[DOMAIN]["entry-1"]["compiled"] == {
        "viewer": {
            "entities": {"entity_ids": {"light.sofa": {"read": True, "control": True}}}
        }
    }
    assert hass.data[DOMAIN]["entry-1"]["preview"]["control_total"] == 1


@pytest.mark.asyncio
async def test_compile_preview_off_clears_stale_preview() -> None:
    """Off mode clears stale monitor projections without native writes."""
    hass = FakeHass()
    hass.data[DOMAIN] = {
        "entry-1": {
            "compiled": {"stale": {}},
            "preview": {"stale": True},
        }
    }

    await _compile_preview(
        hass,
        "entry-1",
        FakeStore(),
        config=default_config_data(),
        policy=default_policy_data(),
    )

    assert "compiled" not in hass.data[DOMAIN]["entry-1"]
    assert "preview" not in hass.data[DOMAIN]["entry-1"]
