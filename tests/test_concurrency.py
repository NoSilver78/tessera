"""Concurrency tests: store mutations serialize (no lost updates, no deadlock)."""

from __future__ import annotations

import asyncio
import copy
from typing import Any

import pytest
from custom_components.tessera.const import DOMAIN
from custom_components.tessera.schema import default_config_data, default_policy_data
from custom_components.tessera.store import mutation_lock
from custom_components.tessera.websocket import async_set_matrix_grant


class FakeArea:
    """Minimal AreaEntry-compatible double."""

    def __init__(self, area_id: str, name: str) -> None:
        """Store the area id and name."""
        self.id = area_id
        self.name = name


class FakeAreaRegistry:
    """Area registry double for the matrix API."""

    def __init__(self, areas: list[FakeArea]) -> None:
        """Store the fake areas."""
        self._areas = areas

    def async_list_areas(self) -> list[FakeArea]:
        """Return the fake areas."""
        return self._areas


class FakeResolver:
    """Deterministic resolver double."""

    def entity_ids_for_area(self, area_id: str) -> tuple[str, ...]:
        """Resolve one fake entity per area."""
        return (f"light.{area_id}",)

    def entity_ids_for_floor(self, floor_id: str) -> tuple[str, ...]:
        """No floor entities in these tests."""
        return ()


class SlowLoadStore:
    """Store double whose policy load yields, exposing lost-update races.

    The ``await asyncio.sleep(0)`` makes concurrent callers all load the same
    base policy before any of them saves — so without serialization the last
    save wins and every other grant is silently dropped.
    """

    def __init__(self, config: dict[str, Any], policy: dict[str, Any]) -> None:
        """Initialize in-memory config and policy."""
        self.config = config
        self.policy = policy
        self.load_count = 0

    async def async_load_config(self) -> dict[str, Any]:
        """Load fake config."""
        return self.config

    async def async_load_policy(self) -> dict[str, Any]:
        """Load fake policy, snapshotting the base BEFORE yielding.

        Snapshotting at call time (not after the yield) is what exposes the
        lost-update race: concurrent callers each capture the same base and a
        later save based on a stale snapshot overwrites the earlier one.
        """
        self.load_count += 1
        snapshot = copy.deepcopy(self.policy)
        await asyncio.sleep(0)
        return snapshot

    async def async_save_policy(self, policy: dict[str, Any]) -> None:
        """Persist fake policy."""
        self.policy = policy


class FakeHass:
    """Minimal HA double with one loaded Tessera entry."""

    def __init__(self, store: SlowLoadStore) -> None:
        """Wire the single entry bucket."""
        self.data: dict[str, Any] = {DOMAIN: {"entry-1": {"store": store}}}

    @property
    def auth(self) -> object:
        """Fail if the matrix API touches native auth."""
        raise AssertionError("matrix API must not touch hass.auth")


AREAS = [FakeArea(f"a{i}", f"Area {i}") for i in range(4)]


def _config(mode: str = "monitor") -> dict[str, Any]:
    config = default_config_data()
    config["mode"] = mode
    config["roles"] = {"r": {"name": "R"}}
    return config


def _install(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "custom_components.tessera.websocket.ar.async_get",
        lambda hass: FakeAreaRegistry(AREAS),
    )
    monkeypatch.setattr(
        "custom_components.tessera.websocket.AreaEntityResolver.from_hass",
        classmethod(lambda cls, hass: FakeResolver()),
    )


@pytest.mark.asyncio
async def test_concurrent_matrix_set_grant_persists_all_cells(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Concurrent set_grant on distinct cells must not lose updates.

    Regression for the ha-tessera-dev finding (8 concurrent set_grant persisted
    only 1). Without the mutation lock this fails (last-write-wins); with it all
    four grants survive.
    """
    _install(monkeypatch)
    store = SlowLoadStore(_config(), default_policy_data())
    hass = FakeHass(store)

    await asyncio.gather(
        *[
            async_set_matrix_grant(
                hass, area_id=a.id, role_id="r", read=True, control=False
            )
            for a in AREAS
        ]
    )

    granted = set(store.policy["area_grants"])
    assert granted == {"a0", "a1", "a2", "a3"}, f"lost updates: kept only {granted}"
    # Serialized: each task reloaded after the previous save (not all-at-once).
    assert store.load_count == len(AREAS)


@pytest.mark.asyncio
async def test_enforce_reapply_runs_inside_lock_without_deadlock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The enforce/fail-safe path runs INSIDE the held lock and must not deadlock.

    The compile path (here a spy doing a nested RAW store write, as
    ``_set_mode_monitor``/``async_fail_safe_to_off`` do) runs within the mutation
    lock and must never re-acquire it. ``wait_for`` turns a reentrant deadlock
    into a test failure instead of a hung suite.
    """
    _install(monkeypatch)
    store = SlowLoadStore(_config(mode="enforce"), default_policy_data())
    hass = FakeHass(store)

    observed: dict[str, bool] = {}

    async def _spy_compile(
        spy_hass: Any, entry_id: str, entry_data: dict[str, Any]
    ) -> None:
        observed["locked"] = mutation_lock(spy_hass).locked()
        # Nested raw store write, exactly as the real fail-safe does — must not
        # re-acquire the mutation lock (would self-deadlock).
        await store.async_save_policy(store.policy)

    monkeypatch.setattr(
        "custom_components.tessera._compile_for_mode_safely", _spy_compile
    )

    await asyncio.wait_for(
        async_set_matrix_grant(
            hass, area_id="a0", role_id="r", read=True, control=True
        ),
        timeout=2,
    )

    assert observed["locked"] is True, "compile/fail-safe must run inside the held lock"
