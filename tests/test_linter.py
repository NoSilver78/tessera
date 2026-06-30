"""Tests for Tessera cross-role linting."""

from __future__ import annotations

from custom_components.tessera.linter import (
    has_blocking_conflicts,
    lint_cross_role,
)
from custom_components.tessera.schema import default_config_data, default_policy_data


class FakeResolver:
    """Deterministic AreaEntityResolver test double."""

    def __init__(self, areas: dict[str, tuple[str, ...]]) -> None:
        """Initialize area fixtures."""
        self._areas = areas

    def entity_ids_for_area(self, area_id: str) -> tuple[str, ...]:
        """Return entities for one area."""
        return self._areas.get(area_id, ())


def _config(*roles: str) -> dict[str, object]:
    config = default_config_data()
    config["mode"] = "monitor"
    config["roles"] = {role: {"name": role.title()} for role in roles}
    config["membership"]["by_user"] = {"user-1": list(roles)}
    return config


def test_all_false_override_exposed_by_other_role_is_blocking_conflict() -> None:
    """A role carve-out nullified by another assigned role is an error."""
    config = _config("restricted", "operator")
    policy = default_policy_data()
    policy["area_grants"] = {
        "living": {
            "restricted": {"read": True, "control": True},
            "operator": {"read": True, "control": True},
        }
    }
    policy["entity_overrides"] = {
        "light.x": {"restricted": {"read": False, "control": False}}
    }

    report = lint_cross_role(
        config,
        policy,
        FakeResolver({"living": ("light.x", "light.y")}),
    )

    assert has_blocking_conflicts(report) is True
    assert report["conflicts_total"] == 1
    assert report["users"]["user-1"]["conflicts"] == [
        {
            "user_id": "user-1",
            "entity_id": "light.x",
            "exposing_roles": ["operator"],
            "restricting_roles": ["restricted"],
            "level": "control",
            "severity": "error",
        }
    ]


def test_different_area_roles_do_not_create_noise() -> None:
    """Ordinary area partitioning is not a cross-role restriction conflict."""
    config = _config("kitchen", "living")
    policy = default_policy_data()
    policy["area_grants"] = {
        "kitchen": {"kitchen": {"read": True}},
        "living": {"living": {"control": True}},
    }

    report = lint_cross_role(
        config,
        policy,
        FakeResolver({"kitchen": ("sensor.fridge",), "living": ("light.sofa",)}),
    )

    assert report["conflicts_total"] == 0
    assert has_blocking_conflicts(report) is False


def test_read_only_role_conflicts_with_control_role_on_same_entity() -> None:
    """A read-only boundary is nullified when another role grants control."""
    config = _config("viewer", "operator")
    policy = default_policy_data()
    policy["area_grants"] = {
        "living": {
            "viewer": {"read": True},
            "operator": {"control": True},
        }
    }

    report = lint_cross_role(
        config,
        policy,
        FakeResolver({"living": ("light.x",)}),
    )

    assert report["conflicts_total"] == 1
    assert report["users"]["user-1"]["conflicts"][0]["level"] == "control"
    assert report["users"]["user-1"]["conflicts"][0]["exposing_roles"] == ["operator"]
    assert report["users"]["user-1"]["conflicts"][0]["restricting_roles"] == ["viewer"]


def test_read_only_entity_override_implies_control_restriction_conflict() -> None:
    """A read-only entity override carves out control, nullified by a control role.

    The restricting role has no area grant: its only signal is a read-only
    ``entity_override``. The linter must still infer the implied control
    restriction (``read True``/no control => control carved out) so a separate
    control-granting role registers as a separation-of-duties conflict.
    """
    config = _config("read_override", "operator")
    policy = default_policy_data()
    policy["area_grants"] = {"living": {"operator": {"control": True}}}
    policy["entity_overrides"] = {"light.x": {"read_override": {"read": True}}}

    report = lint_cross_role(
        config,
        policy,
        FakeResolver({"living": ("light.x",)}),
    )

    assert has_blocking_conflicts(report) is True
    assert report["conflicts_total"] == 1
    assert report["users"]["user-1"]["conflicts"] == [
        {
            "user_id": "user-1",
            "entity_id": "light.x",
            "exposing_roles": ["operator"],
            "restricting_roles": ["read_override"],
            "level": "control",
            "severity": "error",
        }
    ]


def test_distinct_read_carve_is_kept_next_to_control_conflict() -> None:
    """Read conflicts survive when a different role causes the control conflict."""
    config = _config("control_hidden", "read_hidden", "operator")
    policy = default_policy_data()
    policy["area_grants"] = {
        "living": {
            "control_hidden": {"read": True},
            "operator": {"read": True, "control": True},
        }
    }
    policy["entity_overrides"] = {"light.x": {"read_hidden": {"read": False}}}

    report = lint_cross_role(
        config,
        policy,
        FakeResolver({"living": ("light.x",)}),
    )

    assert report["users"]["user-1"]["conflicts"] == [
        {
            "user_id": "user-1",
            "entity_id": "light.x",
            "exposing_roles": ["operator"],
            "restricting_roles": ["control_hidden"],
            "level": "control",
            "severity": "error",
        },
        {
            "user_id": "user-1",
            "entity_id": "light.x",
            "exposing_roles": ["control_hidden", "operator"],
            "restricting_roles": ["read_hidden"],
            "level": "read",
            "severity": "error",
        },
    ]


def test_same_role_exposure_and_restriction_is_not_a_cross_role_conflict() -> None:
    """A role must not be counted as exposing its own restriction."""
    config = _config("mixed")
    policy = default_policy_data()
    policy["area_grants"] = {"living": {"mixed": {"read": True}}}
    policy["entity_overrides"] = {"light.x": {"mixed": {"read": False}}}

    report = lint_cross_role(
        config,
        policy,
        FakeResolver({"living": ("light.x",)}),
    )

    assert report["conflicts_total"] == 0


def test_by_group_membership_is_ignored_for_v1_linting() -> None:
    """ADR 0005: external group membership does not create lint subjects."""
    config = _config("restricted", "operator")
    config["membership"]["by_user"] = {}
    config["membership"]["by_group"] = {"authentik:tessera-operators": ["operator"]}
    policy = default_policy_data()
    policy["area_grants"] = {"living": {"operator": {"control": True}}}

    report = lint_cross_role(
        config,
        policy,
        FakeResolver({"living": ("light.x",)}),
    )

    assert report == {
        "users": {},
        "conflicts_total": 0,
        "blocking_conflicts": False,
        "by_group_projection_mode": "v1-inert",
    }


def test_linter_output_is_deterministic() -> None:
    """Reports use stable sorting for reproducible gates and PR evidence."""
    config = _config("operator", "restricted")
    config["membership"]["by_user"] = {
        "user-b": ["restricted", "operator"],
        "user-a": ["operator", "restricted"],
    }
    policy = default_policy_data()
    policy["area_grants"] = {
        "living": {
            "operator": {"control": True},
            "restricted": {"read": True, "control": True},
        }
    }
    policy["entity_overrides"] = {
        "light.x": {"restricted": {"read": False, "control": False}}
    }
    resolver = FakeResolver({"living": ("light.x",)})

    assert lint_cross_role(config, policy, resolver) == lint_cross_role(
        config, policy, resolver
    )


def test_linter_sorts_roles_users_entities_and_conflicts() -> None:
    """Report ordering does not follow input insertion order."""
    config = _config("z_reader", "a_operator", "m_hidden")
    config["membership"]["by_user"] = {
        "user-z": ["z_reader", "a_operator", "m_hidden"],
        "user-a": ["m_hidden", "a_operator", "z_reader"],
    }
    policy = default_policy_data()
    policy["area_grants"] = {
        "living": {
            "z_reader": {"read": True},
            "a_operator": {"control": True},
        }
    }
    policy["entity_overrides"] = {
        "light.b": {"m_hidden": {"read": False}},
        "light.a": {"m_hidden": {"read": False}},
    }

    report = lint_cross_role(
        config,
        policy,
        FakeResolver({"living": ("light.b", "light.a")}),
    )

    assert list(report["users"]) == ["user-a", "user-z"]
    assert report["users"]["user-a"]["roles"] == ["a_operator", "m_hidden", "z_reader"]
    assert [
        conflict["entity_id"] for conflict in report["users"]["user-a"]["conflicts"]
    ] == ["light.a", "light.a", "light.b", "light.b"]
    assert [
        conflict["level"] for conflict in report["users"]["user-a"]["conflicts"]
    ] == ["control", "read", "control", "read"]
