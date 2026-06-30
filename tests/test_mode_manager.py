"""Tests for Tessera's E3 mode manager."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock

import custom_components.tessera.mode_manager as mode_manager
import pytest
from custom_components.tessera.auth_adapter import (
    SUPPORTED_HA_AUTH_VERSION,
    IncompleteSuperset,
)
from custom_components.tessera.mode_manager import (
    DEFAULT_ROLE_ID,
    apply_enforce_plan,
    compute_enforce_plan,
)
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


@dataclass
class FakeNativeGroup:
    """Native HA group read double."""

    id: str


@dataclass
class FakeUser:
    """Native HA user read double."""

    id: str
    group_ids: list[str]
    is_owner: bool = False
    system_generated: bool = False


class WriteTrapStore:
    """Auth store double that allows reads and traps native persistence."""

    def __init__(
        self,
        groups: list[FakeNativeGroup] | None = None,
        *,
        fail_get_groups: Exception | None = None,
    ) -> None:
        """Initialize native groups."""
        self._groups = {group.id: group for group in groups or []}
        self.fail_get_groups = fail_get_groups
        self.get_groups_calls = 0
        self.save_calls = 0
        self._store = self

    async def async_get_groups(self) -> list[FakeNativeGroup]:
        """Read native groups without mutating them."""
        self.get_groups_calls += 1
        if self.fail_get_groups is not None:
            raise self.fail_get_groups
        return list(self._groups.values())

    async def async_save(self, data: dict[str, Any]) -> None:
        """Trap any accidental native auth-store persistence."""
        self.save_calls += 1
        raise AssertionError("compute_enforce_plan must not persist auth store")


class FakeAuth:
    """Native HA auth read double with write traps."""

    def __init__(
        self,
        users: list[FakeUser] | None = None,
        groups: list[FakeNativeGroup] | None = None,
        *,
        fail_get_users: Exception | None = None,
        fail_get_groups: Exception | None = None,
    ) -> None:
        """Initialize native users and groups."""
        self.users = users or []
        self.fail_get_users = fail_get_users
        self._store = WriteTrapStore(groups, fail_get_groups=fail_get_groups)
        self.get_users_calls = 0
        self.update_calls = 0

    async def async_get_users(self) -> list[FakeUser]:
        """Read native users without mutating them."""
        self.get_users_calls += 1
        if self.fail_get_users is not None:
            raise self.fail_get_users
        return self.users

    async def async_update_user(self, user: FakeUser, **kwargs: Any) -> None:
        """Trap any accidental native user update."""
        self.update_calls += 1
        raise AssertionError("compute_enforce_plan must not update native users")


class FakeHass:
    """HA-like fake for E3.2 read-only auth planning."""

    def __init__(
        self,
        users: list[FakeUser] | None = None,
        groups: list[FakeNativeGroup] | None = None,
        *,
        fail_get_users: Exception | None = None,
        fail_get_groups: Exception | None = None,
    ) -> None:
        """Initialize fake auth state."""
        self.auth = FakeAuth(
            users,
            groups,
            fail_get_users=fail_get_users,
            fail_get_groups=fail_get_groups,
        )


class SpyPolicyStoreAdapter:
    """Policy-store adapter spy for HA-free E3.3 apply tests."""

    def __init__(self, *, fail_on_set: str | None = None) -> None:
        """Initialize call tracking."""
        self.fail_on_set = fail_on_set
        self.set_calls: list[tuple[str, str, dict[str, Any]]] = []
        self.remove_calls: list[str] = []

    async def async_set_group_policy(
        self, group_id: str, name: str, policy: dict[str, Any]
    ) -> None:
        """Record one native group-policy write."""
        if group_id == self.fail_on_set:
            raise RuntimeError(f"set failed for {group_id}")
        self.set_calls.append((group_id, name, policy))

    async def async_remove_group(self, group_id: str) -> None:
        """Record one native group removal."""
        self.remove_calls.append(group_id)


class SpyBindingAdapter:
    """User-binding adapter spy for HA-free E3.3 apply tests."""

    def __init__(
        self, *, fail_on_user: str | None = None, reject_incomplete: bool = False
    ) -> None:
        """Initialize call tracking."""
        self.fail_on_user = fail_on_user
        self.reject_incomplete = reject_incomplete
        self.bind_calls: list[tuple[Any, list[str], list[str]]] = []

    async def async_bind_full_superset(
        self,
        user: Any,
        full_group_ids: list[str],
        *,
        expected_tessera_group_ids: list[str],
    ) -> None:
        """Record one native user binding write."""
        if user.id == self.fail_on_user:
            raise RuntimeError(f"bind failed for {user.id}")
        if self.reject_incomplete and not set(expected_tessera_group_ids).issubset(
            set(full_group_ids)
        ):
            raise IncompleteSuperset("incomplete superset")
        self.bind_calls.append((user, full_group_ids, expected_tessera_group_ids))


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


def _apply_plan() -> dict[str, Any]:
    return {
        "groups": [
            {
                "group_id": "tessera:admin",
                "role_id": "admin",
                "policy": {"entities": {"entity_ids": {"light.sofa": {"read": True}}}},
            },
            {
                "group_id": "tessera:viewer",
                "role_id": "viewer",
                "policy": {"entities": {"entity_ids": {}}},
            },
        ],
        "bindings": [
            {
                "user_id": "user-1",
                "target_group_ids": [
                    "system-admin",
                    "tessera:admin",
                    "tessera:viewer",
                ],
            }
        ],
        "orphan_group_ids": ["tessera:ghost"],
        "blocked": False,
        "block_reason": None,
        "block_detail": [],
    }


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

    result = await compute_enforce_plan(FakeHass(), store)

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
        "bindings": [],
        "orphan_group_ids": [],
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
        "bindings": [],
        "orphan_group_ids": [],
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
        "bindings": [],
        "orphan_group_ids": [],
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
        "bindings": [],
        "orphan_group_ids": [],
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
        "bindings": [],
        "orphan_group_ids": [],
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
    assert result["bindings"] == []
    assert result["orphan_group_ids"] == []


@pytest.mark.asyncio
async def test_apply_enforce_plan_writes_groups_bindings_then_orphans() -> None:
    """E3.3 apply writes policies, then user bindings, then orphan removals."""
    policy_store = SpyPolicyStoreAdapter()
    binding = SpyBindingAdapter()
    user = FakeUser("user-1", ["tessera:admin", "tessera:viewer"])

    result = await apply_enforce_plan(
        _apply_plan(),
        policy_store,
        binding,
        {"user-1": user},
    )

    assert result == {
        "status": "applied",
        "refused_reason": None,
        "groups_written": ["tessera:admin", "tessera:viewer"],
        "bindings_written": ["user-1"],
        "orphan_group_ids_removed": ["tessera:ghost"],
        "detail": [],
    }
    assert policy_store.set_calls == [
        (
            "tessera:admin",
            "tessera:admin",
            {"entities": {"entity_ids": {"light.sofa": {"read": True}}}},
        ),
        ("tessera:viewer", "tessera:viewer", {"entities": {"entity_ids": {}}}),
    ]
    assert binding.bind_calls == [
        (
            user,
            ["system-admin", "tessera:admin", "tessera:viewer"],
            ["tessera:admin", "tessera:viewer"],
        )
    ]
    assert policy_store.remove_calls == ["tessera:ghost"]


@pytest.mark.asyncio
async def test_apply_enforce_plan_blocked_plan_does_not_write() -> None:
    """A blocked plan is reported without touching native write adapters."""
    plan = _apply_plan()
    plan["blocked"] = True
    plan["block_reason"] = "d9"
    plan["block_detail"] = ["unknown custom component"]
    policy_store = SpyPolicyStoreAdapter()
    binding = SpyBindingAdapter()

    result = await apply_enforce_plan(plan, policy_store, binding, {"user-1": object()})

    assert result == {
        "status": "blocked",
        "refused_reason": "blocked",
        "groups_written": [],
        "bindings_written": [],
        "orphan_group_ids_removed": [],
        "detail": ["d9: unknown custom component"],
    }
    assert policy_store.set_calls == []
    assert binding.bind_calls == []
    assert policy_store.remove_calls == []


@pytest.mark.asyncio
async def test_apply_enforce_plan_missing_user_fails_before_writes() -> None:
    """Apply pre-validates bindings before any native write."""
    policy_store = SpyPolicyStoreAdapter()
    binding = SpyBindingAdapter()

    result = await apply_enforce_plan(_apply_plan(), policy_store, binding, {})

    assert result == {
        "status": "failed",
        "refused_reason": "write-error",
        "groups_written": [],
        "bindings_written": [],
        "orphan_group_ids_removed": [],
        "detail": ["ValueError"],
    }
    assert policy_store.set_calls == []
    assert binding.bind_calls == []
    assert policy_store.remove_calls == []


@pytest.mark.asyncio
async def test_apply_enforce_plan_group_write_failure_stops_before_bindings() -> None:
    """Group-policy write errors stop the apply before user bindings."""
    policy_store = SpyPolicyStoreAdapter(fail_on_set="tessera:viewer")
    binding = SpyBindingAdapter()

    result = await apply_enforce_plan(
        _apply_plan(),
        policy_store,
        binding,
        {"user-1": FakeUser("user-1", [])},
    )

    assert result == {
        "status": "failed",
        "refused_reason": "write-error",
        "groups_written": ["tessera:admin"],
        "bindings_written": [],
        "orphan_group_ids_removed": [],
        "detail": ["RuntimeError"],
    }
    assert binding.bind_calls == []
    assert policy_store.remove_calls == []


@pytest.mark.asyncio
async def test_apply_enforce_plan_binding_failure_stops_before_orphan_removal() -> None:
    """User binding errors stop the apply before orphan group removals."""
    policy_store = SpyPolicyStoreAdapter()
    binding = SpyBindingAdapter(fail_on_user="user-1")

    result = await apply_enforce_plan(
        _apply_plan(),
        policy_store,
        binding,
        {"user-1": FakeUser("user-1", [])},
    )

    assert result == {
        "status": "failed",
        "refused_reason": "write-error",
        "groups_written": ["tessera:admin", "tessera:viewer"],
        "bindings_written": [],
        "orphan_group_ids_removed": [],
        "detail": ["RuntimeError"],
    }
    assert policy_store.remove_calls == []


@pytest.mark.asyncio
async def test_apply_enforce_plan_allow_only_guard_blocks_all_writes() -> None:
    """Invalid native policy shapes are refused before any group write."""
    plan = _apply_plan()
    plan["groups"][1]["policy"] = {"entities": True}
    policy_store = SpyPolicyStoreAdapter()
    binding = SpyBindingAdapter()

    result = await apply_enforce_plan(
        plan,
        policy_store,
        binding,
        {"user-1": FakeUser("user-1", ["system-admin"])},
    )

    assert result == {
        "status": "failed",
        "refused_reason": "allow-only",
        "groups_written": [],
        "bindings_written": [],
        "orphan_group_ids_removed": [],
        "detail": ["AllowOnlyPolicyViolation"],
    }
    assert policy_store.set_calls == []
    assert binding.bind_calls == []
    assert policy_store.remove_calls == []


@pytest.mark.asyncio
async def test_apply_enforce_plan_lockout_guard_blocks_all_writes() -> None:
    """A plan that removes the last active admin survivor is refused upfront."""
    plan = _apply_plan()
    plan["bindings"][0]["target_group_ids"] = ["tessera:viewer"]
    policy_store = SpyPolicyStoreAdapter()
    binding = SpyBindingAdapter()

    result = await apply_enforce_plan(
        plan,
        policy_store,
        binding,
        {"user-1": FakeUser("user-1", ["system-admin"])},
    )

    assert result == {
        "status": "failed",
        "refused_reason": "lockout",
        "groups_written": [],
        "bindings_written": [],
        "orphan_group_ids_removed": [],
        "detail": ["LockoutRisk"],
    }
    assert policy_store.set_calls == []
    assert binding.bind_calls == []
    assert policy_store.remove_calls == []


@pytest.mark.asyncio
async def test_apply_enforce_plan_owner_survivor_allows_demoting_admins() -> None:
    """An owner alone preserves recovery, so demoting every admin still applies.

    The owner carries no ``system-admin`` group and has no plan binding, so the
    only thing keeping this apply off the lockout path is ``is_owner``: if that
    survivor branch broke, the plan (which leaves no admin-bound user) would be
    refused with ``LockoutRisk``.
    """
    plan = _apply_plan()
    # The only managed binding drops the user to viewer-only (no system-admin).
    plan["bindings"][0]["target_group_ids"] = ["tessera:viewer"]
    policy_store = SpyPolicyStoreAdapter()
    binding = SpyBindingAdapter()
    owner = FakeUser("owner", [], is_owner=True)
    user = FakeUser("user-1", ["tessera:viewer"])

    result = await apply_enforce_plan(
        plan,
        policy_store,
        binding,
        {"owner": owner, "user-1": user},
    )

    assert result == {
        "status": "applied",
        "refused_reason": None,
        "groups_written": ["tessera:admin", "tessera:viewer"],
        "bindings_written": ["user-1"],
        "orphan_group_ids_removed": ["tessera:ghost"],
        "detail": [],
    }
    assert binding.bind_calls == [(user, ["tessera:viewer"], ["tessera:viewer"])]


@pytest.mark.asyncio
async def test_apply_enforce_plan_system_generated_admin_is_not_a_survivor() -> None:
    """A system-generated admin must not satisfy the lockout survivor check."""
    plan = _apply_plan()
    plan["bindings"] = [
        {"user_id": "gen", "target_group_ids": ["system-admin", "tessera:viewer"]}
    ]
    policy_store = SpyPolicyStoreAdapter()
    binding = SpyBindingAdapter()

    result = await apply_enforce_plan(
        plan,
        policy_store,
        binding,
        # No owner present; the only system-admin holder is system_generated.
        {"gen": FakeUser("gen", ["system-admin"], system_generated=True)},
    )

    assert result == {
        "status": "failed",
        "refused_reason": "lockout",
        "groups_written": [],
        "bindings_written": [],
        "orphan_group_ids_removed": [],
        "detail": ["LockoutRisk"],
    }
    assert policy_store.set_calls == []
    assert binding.bind_calls == []
    assert policy_store.remove_calls == []


@pytest.mark.asyncio
async def test_apply_enforce_plan_expected_uses_current_tessera_groups() -> None:
    """Expected Tessera groups come from current membership, not target groups."""
    plan = _apply_plan()
    plan["bindings"][0]["target_group_ids"] = ["system-admin", "tessera:admin"]
    policy_store = SpyPolicyStoreAdapter()
    binding = SpyBindingAdapter(reject_incomplete=True)

    result = await apply_enforce_plan(
        plan,
        policy_store,
        binding,
        {"user-1": FakeUser("user-1", ["system-admin", "tessera:viewer"])},
    )

    assert result == {
        "status": "failed",
        "refused_reason": "write-error",
        "groups_written": ["tessera:admin", "tessera:viewer"],
        "bindings_written": [],
        "orphan_group_ids_removed": [],
        "detail": ["IncompleteSuperset"],
    }
    assert policy_store.remove_calls == []


@pytest.mark.asyncio
async def test_binding_plan_uses_full_multi_role_superset_and_admin_role() -> None:
    """Multi-role users get every Tessera role group plus allowed system groups."""
    config = _config("admin", "auditor", "viewer")
    config["roles"]["admin"]["is_admin"] = True
    config["membership"]["by_user"] = {"user-1": ["viewer", "auditor", "admin"]}
    hass = FakeHass(
        users=[
            FakeUser(
                "user-1",
                ["system-read-only", "system-users", "tessera:stale"],
            )
        ],
        groups=[
            FakeNativeGroup("tessera:admin"),
            FakeNativeGroup("tessera:auditor"),
            FakeNativeGroup("tessera:viewer"),
        ],
    )

    result = await compute_enforce_plan(
        hass, FakeStore(config, _policy("admin", "auditor", "viewer"))
    )

    assert result["bindings"] == [
        {
            "user_id": "user-1",
            "target_group_ids": [
                "system-admin",
                "system-read-only",
                "tessera:admin",
                "tessera:auditor",
                "tessera:viewer",
            ],
        }
    ]
    assert "system-users" not in result["bindings"][0]["target_group_ids"]
    assert hass.auth.update_calls == 0
    assert hass.auth._store.save_calls == 0


@pytest.mark.asyncio
async def test_binding_plan_no_drop_keeps_both_role_groups() -> None:
    """A two-role user receives both target Tessera groups, never a delta."""
    config = _config("auditor", "viewer")
    config["membership"]["by_user"] = {"user-1": ["viewer", "auditor"]}

    result = await compute_enforce_plan(
        FakeHass(users=[FakeUser("user-1", [])]),
        FakeStore(config, _policy("auditor", "viewer")),
    )

    assert result["bindings"] == [
        {
            "user_id": "user-1",
            "target_group_ids": ["tessera:auditor", "tessera:viewer"],
        }
    ]


@pytest.mark.asyncio
async def test_binding_plan_empty_union_uses_default_role_not_system_users() -> None:
    """Users without a valid role get the deny-by-omission default group."""
    config = _config("viewer")
    config["membership"]["by_user"] = {"user-1": ["missing-role"]}

    result = await compute_enforce_plan(
        FakeHass(users=[FakeUser("user-1", ["system-users"])]),
        FakeStore(config, _policy("viewer")),
    )

    assert result["bindings"] == [
        {
            "user_id": "user-1",
            "target_group_ids": [f"tessera:{DEFAULT_ROLE_ID}"],
        }
    ]
    assert result["groups"][0] == {
        "group_id": f"tessera:{DEFAULT_ROLE_ID}",
        "role_id": DEFAULT_ROLE_ID,
        "policy": {"entities": {"entity_ids": {}}},
    }
    assert "system-users" not in result["bindings"][0]["target_group_ids"]


@pytest.mark.asyncio
async def test_binding_plan_promotion_guard_and_existing_admin_retention() -> None:
    """Only admin roles promote; existing system-admin membership is preserved."""
    config = _config("viewer")
    config["membership"]["by_user"] = {
        "plain": ["viewer"],
        "existing-admin": ["viewer"],
    }

    result = await compute_enforce_plan(
        FakeHass(
            users=[
                FakeUser("plain", ["system-users"]),
                FakeUser("existing-admin", ["system-admin"]),
            ]
        ),
        FakeStore(config, _policy("viewer")),
    )

    assert result["bindings"] == [
        {
            "user_id": "existing-admin",
            "target_group_ids": ["system-admin", "tessera:viewer"],
        },
        {"user_id": "plain", "target_group_ids": ["tessera:viewer"]},
    ]


@pytest.mark.asyncio
async def test_binding_plan_skips_owner_and_system_generated_users() -> None:
    """Owner and system-generated users are structurally unmanaged."""
    config = _config("viewer")
    config["membership"]["by_user"] = {
        "owner": ["viewer"],
        "generated": ["viewer"],
        "managed": ["viewer"],
    }

    result = await compute_enforce_plan(
        FakeHass(
            users=[
                FakeUser("owner", ["system-admin"], is_owner=True),
                FakeUser("generated", ["tessera:viewer"], system_generated=True),
                FakeUser("managed", []),
            ]
        ),
        FakeStore(config, _policy("viewer")),
    )

    assert result["bindings"] == [
        {"user_id": "managed", "target_group_ids": ["tessera:viewer"]}
    ]


@pytest.mark.asyncio
async def test_binding_plan_reports_orphan_tessera_groups() -> None:
    """Existing unmanaged tessera:* groups are reported as sorted orphans."""
    config = _config("viewer")
    config["membership"]["by_user"] = {}

    result = await compute_enforce_plan(
        FakeHass(
            groups=[
                FakeNativeGroup("system-admin"),
                FakeNativeGroup("tessera:viewer"),
                FakeNativeGroup("tessera:ghost-b"),
                FakeNativeGroup("tessera:ghost-a"),
                FakeNativeGroup(f"tessera:{DEFAULT_ROLE_ID}"),
            ]
        ),
        FakeStore(config, _policy("viewer")),
    )

    assert result["orphan_group_ids"] == ["tessera:ghost-a", "tessera:ghost-b"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("hass", "expected_detail"),
    [
        (
            FakeHass(fail_get_users=RuntimeError("users unavailable")),
            "RuntimeError: users unavailable",
        ),
        (
            FakeHass(
                users=[FakeUser("user-1", [])],
                fail_get_groups=OSError("groups unavailable"),
            ),
            "OSError: groups unavailable",
        ),
    ],
)
async def test_binding_plan_auth_read_errors_fail_closed(
    hass: FakeHass, expected_detail: str
) -> None:
    """Auth user/group read failures block and never propagate."""
    result = await compute_enforce_plan(
        hass, FakeStore(_config("viewer"), _policy("viewer"))
    )

    assert result == {
        "groups": [],
        "bindings": [],
        "orphan_group_ids": [],
        "blocked": True,
        "block_reason": "auth",
        "block_detail": [expected_detail],
    }
    assert hass.auth.update_calls == 0
    assert hass.auth._store.save_calls == 0


@pytest.mark.asyncio
async def test_binding_plan_empty_user_id_fails_closed() -> None:
    """Invalid managed user ids are auth-plan failures, not propagated errors."""
    result = await compute_enforce_plan(
        FakeHass(users=[FakeUser("", [])]),
        FakeStore(_config("viewer"), _policy("viewer")),
    )

    assert result == {
        "groups": [],
        "bindings": [],
        "orphan_group_ids": [],
        "blocked": True,
        "block_reason": "auth",
        "block_detail": ["ValueError: managed users require a stable id"],
    }


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


@pytest.mark.parametrize(
    "role_id", ["tessera:x", "a:b", "TesseraAdmin", "__default__", "__x"]
)
def test_schema_role_id_namespace_guard(role_id: str) -> None:
    """Role ids cannot collide with native ``tessera:<role>`` group ids."""
    config = default_config_data()
    config["roles"] = {role_id: {"name": "bad"}}

    with pytest.raises(TesseraSchemaError, match="reserved"):
        validate_config_data(config)


def test_schema_default_role_sentinel_prevents_duplicate_group_plan() -> None:
    """The internal default-role sentinel cannot be configured as a real role."""
    config = default_config_data()
    config["mode"] = "enforce"
    config["roles"] = {DEFAULT_ROLE_ID: {"name": "Default"}}
    config["membership"]["by_user"] = {"user-1": []}

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
async def test_version_block_never_touches_hass_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pre-auth gate blocks still return empty E3.2 fields without auth access."""
    monkeypatch.setattr(mode_manager, "_homeassistant_version", lambda: "1900.1.1")

    result = await compute_enforce_plan(
        AuthTrapHass(), FakeStore(_config("viewer"), _policy("viewer"))
    )

    assert result["groups"] == []
    assert result["bindings"] == []
    assert result["orphan_group_ids"] == []
    assert result["block_reason"] == "version"
