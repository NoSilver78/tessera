"""Tests for Tessera schema validation."""

from __future__ import annotations

from typing import Any, cast

import pytest
from custom_components.tessera.schema import (
    TesseraSchemaError,
    default_config_data,
    default_policy_data,
    validate_config_data,
    validate_policy_data,
)


def test_config_schema_accepts_membership_sources() -> None:
    """Config schema accepts by-user and by-group role membership."""
    config = default_config_data()
    config["mode"] = "monitor"
    config["roles"] = {"viewer": {"name": "Viewer"}}
    config["membership"] = {
        "by_user": {"user-1": ["viewer"]},
        "by_group": {"authentik:tessera-viewer": ["viewer"]},
    }

    assert validate_config_data(config) == config


def test_policy_schema_accepts_read_control_leafs() -> None:
    """Policy schema accepts explicit read/control permission leafs."""
    policy = default_policy_data()
    policy["floor_grants"] = {"ground": {"auditor": {"read": True}}}
    policy["area_grants"] = {"living_room": {"viewer": {"read": True}}}
    policy["entity_overrides"] = {
        "light.table": {"operator": {"read": True, "control": True}}
    }
    policy["label_grants"] = {"cozy": {"guest": {"read": True, "control": True}}}

    assert validate_policy_data(policy) == policy


def test_policy_schema_accepts_legitimate_control_and_removal_leafs() -> None:
    """Policy schema keeps valid control-implies-read and all-false leaves."""
    policy = default_policy_data()
    policy["area_grants"] = {
        "living_room": {
            "operator": {"control": True},
            "reader": {"read": True, "control": False},
            "viewer": {"read": True, "control": True},
        }
    }
    policy["floor_grants"] = {
        "ground": {
            "operator": {"control": True},
            "reader": {"read": True, "control": False},
            "viewer": {"read": True, "control": True},
        }
    }
    policy["entity_overrides"] = {
        "light.read_hidden": {"viewer": {"read": False}},
        "light.table": {"operator": {"read": False, "control": False}},
    }

    assert validate_policy_data(policy) == policy


@pytest.mark.parametrize(
    ("section", "target"),
    [
        ("floor_grants", "ground"),
        ("area_grants", "living_room"),
        ("label_grants", "cozy"),
        ("entity_overrides", "light.table"),
    ],
)
def test_policy_schema_rejects_contradictory_control_without_read(
    section: str, target: str
) -> None:
    """Policy schema rejects explicit read denial paired with control allow."""
    policy = default_policy_data()
    policy[section] = {target: {"operator": {"read": False, "control": True}}}

    with pytest.raises(TesseraSchemaError, match="control implies read"):
        validate_policy_data(policy)


@pytest.mark.parametrize(
    ("bad_leaf", "match"),
    [
        (True, "not bare bool"),
        ({"entities": True}, "unsupported permission keys"),
        ({"domains": True}, "unsupported permission keys"),
        ({"read": "yes"}, "must be boolean"),
        ({}, "must not be empty"),
    ],
)
def test_policy_schema_rejects_unsafe_leaf_shapes(bad_leaf: object, match: str) -> None:
    """Policy schema rejects bare booleans and unsupported HA shortcuts.

    Each case asserts the *specific* guard message, so removing one guard
    cannot be masked by another check raising a different error.
    """
    policy = default_policy_data()
    policy["area_grants"] = {"living_room": {"viewer": cast(Any, bad_leaf)}}

    with pytest.raises(TesseraSchemaError, match=match):
        validate_policy_data(policy)


def test_policy_schema_defaults_missing_floor_grants_for_existing_stores() -> None:
    """Existing v1 policy payloads without floor grants remain loadable."""
    policy = default_policy_data()
    policy.pop("floor_grants")

    validated = validate_policy_data(policy)

    assert validated["floor_grants"] == {}


def test_policy_schema_defaults_missing_label_grants_for_existing_stores() -> None:
    """Policy payloads predating the label dimension remain loadable."""
    policy = default_policy_data()
    policy.pop("label_grants")

    validated = validate_policy_data(policy)

    assert validated["label_grants"] == {}
