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
    policy["area_grants"] = {"living_room": {"viewer": {"read": True}}}
    policy["entity_overrides"] = {
        "light.table": {"operator": {"read": True, "control": True}}
    }

    assert validate_policy_data(policy) == policy


@pytest.mark.parametrize(
    "bad_leaf",
    [True, {"entities": True}, {"domains": True}, {"read": "yes"}, {}],
)
def test_policy_schema_rejects_unsafe_leaf_shapes(bad_leaf: object) -> None:
    """Policy schema rejects bare booleans and unsupported HA shortcuts."""
    policy = default_policy_data()
    policy["area_grants"] = {
        "living_room": {"viewer": cast(Any, bad_leaf)}
    }

    with pytest.raises(TesseraSchemaError):
        validate_policy_data(policy)
