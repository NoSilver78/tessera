"""Tests for Tessera policy compilation."""

from __future__ import annotations

import pytest
from custom_components.tessera.compiler import (
    BY_GROUP_PROJECTION_MODE,
    compile_policies,
)
from custom_components.tessera.schema import (
    TesseraSchemaError,
    default_config_data,
    default_policy_data,
)


class FakeResolver:
    """Deterministic AreaEntityResolver test double."""

    def __init__(self, areas: dict[str, tuple[str, ...]]) -> None:
        """Initialize area-to-entity fixtures."""
        self._areas = areas

    def entity_ids_for_area(self, area_id: str) -> tuple[str, ...]:
        """Resolve one area id."""
        return self._areas.get(area_id, ())


def test_area_grant_compiles_to_entity_policy_leafs() -> None:
    """Area grants expand through the resolver into explicit entity leaves."""
    config = default_config_data()
    config["roles"] = {"viewer": {"name": "Viewer"}}
    policy = default_policy_data()
    policy["area_grants"] = {"living": {"viewer": {"read": True}}}

    compiled = compile_policies(
        config, policy, FakeResolver({"living": ("light.sofa", "sensor.temp")})
    )

    assert compiled == {
        "viewer": {
            "entities": {
                "entity_ids": {
                    "light.sofa": {"read": True},
                    "sensor.temp": {"read": True},
                }
            }
        }
    }


def test_entity_override_replaces_area_grant_for_role() -> None:
    """Entity overrides are more specific than area grants."""
    config = default_config_data()
    config["roles"] = {"operator": {"name": "Operator"}}
    policy = default_policy_data()
    policy["area_grants"] = {"living": {"operator": {"read": True, "control": True}}}
    policy["entity_overrides"] = {"light.sofa": {"operator": {"read": True}}}

    compiled = compile_policies(
        config, policy, FakeResolver({"living": ("light.sofa", "light.table")})
    )

    assert compiled["operator"]["entities"]["entity_ids"] == {
        "light.sofa": {"read": True},
        "light.table": {"read": True, "control": True},
    }


def test_all_false_entity_override_removes_area_grant_for_role() -> None:
    """A specific override can remove the allow projection for one entity."""
    config = default_config_data()
    config["roles"] = {"operator": {"name": "Operator"}}
    policy = default_policy_data()
    policy["area_grants"] = {"living": {"operator": {"read": True, "control": True}}}
    policy["entity_overrides"] = {
        "light.sofa": {"operator": {"read": False, "control": False}}
    }

    compiled = compile_policies(
        config, policy, FakeResolver({"living": ("light.sofa", "light.table")})
    )

    assert compiled["operator"]["entities"]["entity_ids"] == {
        "light.table": {"read": True, "control": True}
    }


def test_entity_override_removes_area_grant_only_for_that_role() -> None:
    """An all-false override removes grants only for the referenced role."""
    config = default_config_data()
    config["roles"] = {"a": {"name": "A"}, "b": {"name": "B"}}
    policy = default_policy_data()
    policy["area_grants"] = {
        "living": {
            "a": {"read": True, "control": True},
            "b": {"read": True, "control": True},
        }
    }
    policy["entity_overrides"] = {"light.x": {"a": {"read": False, "control": False}}}

    compiled = compile_policies(config, policy, FakeResolver({"living": ("light.x",)}))

    assert compiled == {
        "a": {"entities": {"entity_ids": {}}},
        "b": {"entities": {"entity_ids": {"light.x": {"read": True, "control": True}}}},
    }


def test_all_false_entity_override_can_empty_role_policy() -> None:
    """Empty role projections stay explicit for later apply/drift logic."""
    config = default_config_data()
    config["roles"] = {"operator": {"name": "Operator"}}
    policy = default_policy_data()
    policy["area_grants"] = {"living": {"operator": {"read": True, "control": True}}}
    policy["entity_overrides"] = {
        "light.sofa": {"operator": {"read": False, "control": False}}
    }

    compiled = compile_policies(
        config, policy, FakeResolver({"living": ("light.sofa",)})
    )

    assert compiled == {"operator": {"entities": {"entity_ids": {}}}}


def test_multiple_area_grants_for_role_are_merged() -> None:
    """Multiple area grants for the same role are unioned."""
    config = default_config_data()
    config["roles"] = {"viewer": {"name": "Viewer"}}
    policy = default_policy_data()
    policy["area_grants"] = {
        "living": {"viewer": {"read": True}},
        "kitchen": {"viewer": {"read": True}},
    }

    compiled = compile_policies(
        config,
        policy,
        FakeResolver({"living": ("light.sofa",), "kitchen": ("sensor.fridge",)}),
    )

    assert compiled["viewer"]["entities"]["entity_ids"] == {
        "light.sofa": {"read": True},
        "sensor.fridge": {"read": True},
    }


def test_overlapping_area_grants_union_permissions() -> None:
    """Overlapping area resolution merges permissions without weakening grants."""
    config = default_config_data()
    config["roles"] = {"operator": {"name": "Operator"}}
    policy = default_policy_data()
    policy["area_grants"] = {
        "kitchen": {"operator": {"read": True}},
        "living": {"operator": {"control": True}},
    }

    compiled = compile_policies(
        config,
        policy,
        FakeResolver(
            {
                "kitchen": ("light.shared",),
                "living": ("light.shared", "light.sofa"),
            }
        ),
    )

    assert compiled["operator"]["entities"]["entity_ids"] == {
        "light.shared": {"read": True, "control": True},
        "light.sofa": {"read": True, "control": True},
    }


def test_control_grant_implies_read() -> None:
    """Native control grants also include read permission."""
    config = default_config_data()
    config["roles"] = {"operator": {"name": "Operator"}}
    policy = default_policy_data()
    policy["area_grants"] = {"living": {"operator": {"control": True}}}

    compiled = compile_policies(
        config, policy, FakeResolver({"living": ("light.sofa",)})
    )

    assert compiled["operator"]["entities"]["entity_ids"] == {
        "light.sofa": {"read": True, "control": True}
    }


def test_compile_is_deterministic() -> None:
    """Compiling the same store twice returns an identical structure."""
    config = default_config_data()
    config["roles"] = {"viewer": {"name": "Viewer"}, "operator": {"name": "Operator"}}
    policy = default_policy_data()
    policy["area_grants"] = {
        "kitchen": {"operator": {"control": True, "read": True}},
        "living": {"viewer": {"read": True}},
    }
    policy["entity_overrides"] = {
        "light.sofa": {"operator": {"read": True}},
        "sensor.fridge": {"viewer": {"read": True}},
    }
    resolver = FakeResolver(
        {"living": ("light.sofa", "sensor.temp"), "kitchen": ("sensor.fridge",)}
    )

    assert compile_policies(config, policy, resolver) == compile_policies(
        config, policy, resolver
    )


def test_by_group_membership_is_v1_inert_for_policy_compilation() -> None:
    """ADR 0005: external group membership does not project in v1."""
    config = default_config_data()
    config["roles"] = {"viewer": {"name": "Viewer"}}
    policy = default_policy_data()
    policy["area_grants"] = {"living": {"viewer": {"read": True}}}
    resolver = FakeResolver({"living": ("light.sofa",)})
    baseline = compile_policies(config, policy, resolver)

    config["membership"]["by_group"] = {"authentik:tessera-viewers": ["viewer"]}

    assert BY_GROUP_PROJECTION_MODE == "v1-inert"
    assert compile_policies(config, policy, resolver) == baseline


def test_output_never_contains_bare_true_shortcuts() -> None:
    """Compiler output remains schema-aware and avoids HA shortcut booleans."""
    config = default_config_data()
    config["roles"] = {"viewer": {"name": "Viewer"}}
    policy = default_policy_data()
    policy["area_grants"] = {"living": {"viewer": {"control": True}}}

    compiled = compile_policies(
        config, policy, FakeResolver({"living": ("light.sofa",)})
    )

    role_policy = compiled["viewer"]
    entity_ids = role_policy["entities"]["entity_ids"]
    assert not isinstance(role_policy["entities"], bool)
    assert not isinstance(entity_ids, bool)
    assert entity_ids
    assert all(
        isinstance(leaf, dict) and not isinstance(leaf, bool)
        for leaf in entity_ids.values()
    )
    assert entity_ids == {"light.sofa": {"read": True, "control": True}}


def test_policy_referencing_unknown_role_fails_closed() -> None:
    """The compiler never emits native policy for roles missing in config."""
    config = default_config_data()
    config["roles"] = {"viewer": {"name": "Viewer"}}
    policy = default_policy_data()
    policy["area_grants"] = {"living": {"ghost": {"read": True}}}

    with pytest.raises(TesseraSchemaError, match="unknown role"):
        compile_policies(config, policy, FakeResolver({"living": ("light.sofa",)}))


def test_entity_override_referencing_unknown_role_fails_closed() -> None:
    """Unknown roles fail closed even when referenced only by overrides."""
    config = default_config_data()
    config["roles"] = {"viewer": {"name": "Viewer"}}
    policy = default_policy_data()
    policy["entity_overrides"] = {"light.sofa": {"ghost": {"read": True}}}

    with pytest.raises(TesseraSchemaError, match="unknown role"):
        compile_policies(config, policy, FakeResolver({}))


def test_all_false_area_grant_is_omitted() -> None:
    """All-false area grants remain deny-by-omission."""
    config = default_config_data()
    config["roles"] = {"viewer": {"name": "Viewer"}}
    policy = default_policy_data()
    policy["area_grants"] = {"living": {"viewer": {"read": False, "control": False}}}

    compiled = compile_policies(
        config, policy, FakeResolver({"living": ("light.sofa",)})
    )

    assert compiled == {"viewer": {"entities": {"entity_ids": {}}}}


def test_compile_rejects_invalid_config_mode() -> None:
    """Invalid config modes fail before native policy output is emitted."""
    config = default_config_data()
    config["mode"] = "banana"

    with pytest.raises(TesseraSchemaError, match=r"config\.mode"):
        compile_policies(config, default_policy_data(), FakeResolver({}))
