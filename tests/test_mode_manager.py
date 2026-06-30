"""Tests for Tessera's dormant E3.1 mode manager."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import custom_components.tessera.mode_manager as mode_manager
import pytest
from custom_components.tessera.auth_adapter import SUPPORTED_HA_AUTH_VERSION
from custom_components.tessera.mode_manager import compute_enforce_plan
from custom_components.tessera.schema import (
    TesseraSchemaError,
    default_config_data,
    default_policy_data,
    validate_config_data,
    validate_policy_data,
)


class FakeResolver:
    """Deterministic area resolver for E3.1 tests."""

    def __init__(self, areas: dict[str, tuple[str, ...]]) -> None:
        """Initialize area fixtures."""
        self._areas = areas

    def entity_ids_for_area(self, area_id: str) -> tuple[str, ...]:
        """Return entities for one area."""
        return self._areas.get(area_id, ())


class FakeStore:
    """Async in-memory store double."""

    def __init__(self, config: dict[str, Any], policy: dict[str, Any]) -> None:
        """Initialize store payloads."""
        self.config = config
        self.policy = policy
        self.config_loads = 0
        self.policy_loads = 0

    async def async_load_config(self) -> dict[str, Any]:
        """Load fake config."""
        self.config_loads += 1
        return self.config

    async def async_load_policy(self) -> dict[str, Any]:
        """Load fake policy."""
        self.policy_loads += 1
        return self.policy


class ConfigLoadFailureStore(FakeStore):
    """Store double that simulates a corrupt persisted config payload."""

    async def async_load_config(self) -> dict[str, Any]:
        """Raise as if store validation rejected the persisted config."""
        self.config_loads += 1
        raise TesseraSchemaError("corrupt config")


class AuthTrapHass:
    """HA-like fake that fails if E3.1 touches native auth."""

    @property
    def auth(self) -> object:
        """Raise on any native auth access."""
        raise AssertionError("compute_enforce_plan must not touch hass.auth")


def _config(*roles: str) -> dict[str, Any]:
    config = default_config_data()
    config["mode"] = "enforce"
    config["roles"] = {role: {"name": role.title()} for role in roles}
    config["membership"]["by_user"] = {"user-1": list(roles)}
    return config


def _policy(*roles: str) -> dict[str, Any]:
    policy = default_policy_data()
    policy["area_grants"] = {"living": {}}
    for role in roles:
        policy["area_grants"]["living"][role] = (
            {"control": True} if role == "operator" else {"read": True}
        )
    return policy


@pytest.fixture(autouse=True)
def _mode_manager_fakes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep mode-manager tests HA-free and read-only."""
    monkeypatch.setattr(
        mode_manager,
        "_homeassistant_version",
        lambda: SUPPORTED_HA_AUTH_VERSION,
    )
    monkeypatch.setattr(
        mode_manager.AreaEntityResolver,
        "from_hass",
        classmethod(lambda cls, hass: FakeResolver({"living": ("light.sofa",)})),
    )
    monkeypatch.setattr(
        mode_manager,
        "evaluate_d9_gate",
        AsyncMock(return_value={"enforce_blocked": False, "blocking": []}),
    )


@pytest.mark.asyncio
async def test_clean_store_returns_deterministic_group_plan() -> None:
    """A clean store returns one sorted group plan per compiled role."""
    config = _config("operator", "viewer")
    config["membership"]["by_user"] = {}
    store = FakeStore(config, _policy("operator", "viewer"))

    result = await compute_enforce_plan(AuthTrapHass(), store)

    assert result == {
        "groups": [
            {
                "group_id": "tessera:operator",
                "role_id": "operator",
                "policy": {
                    "entities": {
                        "entity_ids": {"light.sofa": {"read": True, "control": True}}
                    }
                },
            },
            {
                "group_id": "tessera:viewer",
                "role_id": "viewer",
                "policy": {"entities": {"entity_ids": {"light.sofa": {"read": True}}}},
            },
        ],
        "blocked": False,
        "block_reason": None,
        "block_detail": [],
    }
    assert store.config_loads == 1
    assert store.policy_loads == 1


@pytest.mark.asyncio
async def test_d9_block_returns_no_partial_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D9 blocks before linter and drops any compiled partial group plan."""
    store = FakeStore(_config("viewer"), _policy("viewer"))
    monkeypatch.setattr(
        mode_manager,
        "lint_cross_role",
        lambda *args, **kwargs: pytest.fail("linter must not run after D9 block"),
    )
    monkeypatch.setattr(
        mode_manager,
        "evaluate_d9_gate",
        AsyncMock(
            return_value={
                "enforce_blocked": True,
                "blocking": ["unknown_component", "unsafe_component"],
            }
        ),
    )

    result = await compute_enforce_plan(AuthTrapHass(), store)

    assert result == {
        "groups": [],
        "blocked": True,
        "block_reason": "d9",
        "block_detail": ["unknown_component", "unsafe_component"],
    }


@pytest.mark.asyncio
async def test_compile_failure_blocks_before_d9_and_linter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compile errors are hard gates and produce no partial plan."""
    policy = _policy("unknown_role")
    store = FakeStore(_config("viewer"), policy)
    monkeypatch.setattr(
        mode_manager,
        "evaluate_d9_gate",
        AsyncMock(side_effect=AssertionError("D9 must not run after compile block")),
    )
    monkeypatch.setattr(
        mode_manager,
        "lint_cross_role",
        lambda *args, **kwargs: pytest.fail("linter must not run after compile block"),
    )

    result = await compute_enforce_plan(AuthTrapHass(), store)

    assert result["groups"] == []
    assert result["blocked"] is True
    assert result["block_reason"] == "compile"
    assert result["block_detail"][0].startswith("TesseraSchemaError:")


@pytest.mark.asyncio
async def test_store_load_failure_blocks_without_propagating() -> None:
    """Corrupt persisted store data fails closed before compile/D9/linter."""
    store = ConfigLoadFailureStore(_config("viewer"), _policy("viewer"))

    result = await compute_enforce_plan(AuthTrapHass(), store)

    assert result == {
        "groups": [],
        "blocked": True,
        "block_reason": "store",
        "block_detail": ["TesseraSchemaError: corrupt config"],
    }
    assert store.config_loads == 1
    assert store.policy_loads == 0


@pytest.mark.asyncio
async def test_resolver_failure_blocks_without_store_load(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolver construction is an infrastructure gate and fails closed."""
    store = FakeStore(_config("viewer"), _policy("viewer"))
    monkeypatch.setattr(
        mode_manager.AreaEntityResolver,
        "from_hass",
        classmethod(
            lambda cls, hass: (_ for _ in ()).throw(RuntimeError("no registries"))
        ),
    )

    result = await compute_enforce_plan(AuthTrapHass(), store)

    assert result == {
        "groups": [],
        "blocked": True,
        "block_reason": "resolver",
        "block_detail": ["RuntimeError: no registries"],
    }
    assert store.config_loads == 0
    assert store.policy_loads == 0


@pytest.mark.asyncio
async def test_d9_exception_blocks_without_propagating(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D9 infra/read errors fail closed and drop any compiled partial plan."""
    store = FakeStore(_config("viewer"), _policy("viewer"))
    monkeypatch.setattr(
        mode_manager,
        "lint_cross_role",
        lambda *args, **kwargs: pytest.fail("linter must not run after D9 error"),
    )
    monkeypatch.setattr(
        mode_manager,
        "evaluate_d9_gate",
        AsyncMock(side_effect=OSError("permission denied")),
    )

    result = await compute_enforce_plan(AuthTrapHass(), store)

    assert result == {
        "groups": [],
        "blocked": True,
        "block_reason": "d9",
        "block_detail": ["OSError: permission denied"],
    }


@pytest.mark.asyncio
async def test_linter_conflict_blocks_after_d9_passes() -> None:
    """Cross-role conflicts block enforce planning after D9 passes."""
    config = _config("restricted", "operator")
    policy = default_policy_data()
    policy["area_grants"] = {
        "living": {
            "restricted": {"read": True, "control": True},
            "operator": {"control": True},
        }
    }
    policy["entity_overrides"] = {
        "light.sofa": {"restricted": {"read": False, "control": False}}
    }
    store = FakeStore(config, policy)

    result = await compute_enforce_plan(AuthTrapHass(), store)

    assert result["groups"] == []
    assert result["blocked"] is True
    assert result["block_reason"] == "linter"
    assert result["block_detail"] == [
        "user-1:light.sofa:control:restricted:blocked-by:operator"
    ]


@pytest.mark.asyncio
async def test_unsupported_ha_version_blocks_before_store_load(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unsupported HA auth version fails before compile/D9/linter."""
    store = FakeStore(_config("viewer"), _policy("viewer"))
    monkeypatch.setattr(mode_manager, "_homeassistant_version", lambda: "1900.1.1")

    result = await compute_enforce_plan(AuthTrapHass(), store)

    assert result["groups"] == []
    assert result["blocked"] is True
    assert result["block_reason"] == "version"
    assert result["block_detail"]
    assert store.config_loads == 0
    assert store.policy_loads == 0


@pytest.mark.parametrize("role_id", ["tessera:x", "a:b", "TesseraAdmin"])
def test_schema_role_id_namespace_guard(role_id: str) -> None:
    """Role ids cannot collide with native ``tessera:<role>`` group ids."""
    config = default_config_data()
    config["roles"] = {role_id: {"name": "bad"}}

    with pytest.raises(TesseraSchemaError, match="reserved"):
        validate_config_data(config)


@pytest.mark.parametrize("membership_key", ["by_user", "by_group"])
@pytest.mark.parametrize("role_id", ["tessera:x", "a:b", "TesseraAdmin"])
def test_schema_membership_role_id_namespace_guard(
    membership_key: str, role_id: str
) -> None:
    """Membership role values use the same role-id namespace guard."""
    config = default_config_data()
    config["roles"] = {"viewer": {"name": "Viewer"}}
    config["membership"][membership_key] = {"subject-1": [role_id]}

    with pytest.raises(TesseraSchemaError, match="reserved"):
        validate_config_data(config)


@pytest.mark.parametrize("role_id", ["tessera:x", "a:b", "TesseraAdmin"])
def test_schema_grant_matrix_role_id_namespace_guard(role_id: str) -> None:
    """Policy grant role keys use the same role-id namespace guard."""
    policy = default_policy_data()
    policy["area_grants"] = {"living": {role_id: {"read": True}}}

    with pytest.raises(TesseraSchemaError, match="reserved"):
        validate_policy_data(policy)


@pytest.mark.asyncio
async def test_compute_enforce_plan_never_touches_hass_auth() -> None:
    """AuthTrapHass would raise if E3.1 touched native auth."""
    result = await compute_enforce_plan(
        AuthTrapHass(), FakeStore(_config("viewer"), _policy("viewer"))
    )

    assert result["block_reason"] is None
