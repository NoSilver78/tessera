"""Auto-recompile on registry and user changes, against a real HA event bus.

Uses HA's real bus, Debouncer and clock (``async_fire_time_changed``), and HA's
real AuthStore for the loop guard — the wiring is exactly what it is in a live
instance.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from custom_components.tessera import auto_recompile
from custom_components.tessera.auth_adapter import (
    SUPPORTED_HA_AUTH_VERSION,
    AuthPolicyStoreAdapter,
    UserBindingAdapter,
)
from custom_components.tessera.auto_recompile import (
    RECOMPILE_COOLDOWN,
    async_setup_auto_recompile,
    device_change_is_relevant,
    entity_change_is_relevant,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed


class _Recorder:
    """Recompile stand-in plus the unload callbacks setup registered."""

    def __init__(self) -> None:
        self.calls = 0
        self.unload: list[Any] = []

    async def recompile(self) -> None:
        self.calls += 1

    def unload_all(self) -> None:
        for func in self.unload:
            func()


async def _setup(hass: HomeAssistant) -> _Recorder:
    recorder = _Recorder()
    async_setup_auto_recompile(hass, recorder.unload.append, recorder.recompile)
    return recorder


async def _after_cooldown(hass: HomeAssistant) -> None:
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=RECOMPILE_COOLDOWN + 1)
    )
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("data", "relevant"),
    [
        ({"action": "create", "entity_id": "light.a"}, True),
        ({"action": "remove", "entity_id": "light.a"}, True),
        (
            {"action": "update", "entity_id": "light.a", "changes": {"area_id": "x"}},
            True,
        ),
        (
            {"action": "update", "entity_id": "light.a", "changes": {"labels": set()}},
            True,
        ),
        (
            {"action": "update", "entity_id": "light.a", "changes": {"device_id": "d"}},
            True,
        ),
        (
            {
                "action": "update",
                "entity_id": "light.a",
                "changes": {"disabled_by": None},
            },
            True,
        ),
        (
            {
                "action": "update",
                "entity_id": "light.b",
                "old_entity_id": "light.a",
                "changes": {"entity_id": "light.a"},
            },
            True,
        ),
        ({"action": "update", "entity_id": "light.a", "changes": {"name": "x"}}, False),
        ({"action": "update", "entity_id": "light.a", "changes": {"icon": "x"}}, False),
        ({"action": "update", "entity_id": "light.a"}, True),  # unknown shape
    ],
)
def test_entity_change_filter(data: dict[str, Any], relevant: bool) -> None:
    """Only changes the resolver reads trigger a recompile; renames always do."""
    assert entity_change_is_relevant(data) is relevant


@pytest.mark.parametrize(
    ("data", "relevant"),
    [
        ({"action": "create", "device_id": "d"}, True),
        ({"action": "remove", "device_id": "d", "device": {}}, True),
        ({"action": "update", "device_id": "d", "changes": {"area_id": None}}, True),
        ({"action": "update", "device_id": "d", "changes": {"labels": set()}}, True),
        (
            {
                "action": "update",
                "device_id": "d",
                "changes": {"parent_device_id": None},
            },
            True,
        ),
        ({"action": "update", "device_id": "d", "changes": {"sw_version": "1"}}, False),
    ],
)
def test_device_change_filter(data: dict[str, Any], relevant: bool) -> None:
    """Firmware or name churn on a device does not recompile."""
    assert device_change_is_relevant(data) is relevant


@pytest.mark.parametrize(
    "event_type",
    [
        "area_registry_updated",
        "floor_registry_updated",
        "label_registry_updated",
        "user_added",
        "user_removed",
        "user_updated",
    ],
)
async def test_every_listened_event_schedules_a_recompile(
    hass: HomeAssistant, event_type: str
) -> None:
    """Area/floor/label changes and user lifecycle each trigger one recompile."""
    recorder = await _setup(hass)

    hass.bus.async_fire(event_type, {})
    await hass.async_block_till_done()
    assert recorder.calls == 0  # debounced, not immediate
    await _after_cooldown(hass)

    assert recorder.calls == 1
    recorder.unload_all()


async def test_a_burst_collapses_into_one_recompile(hass: HomeAssistant) -> None:
    """A device move fires many entity events; they fold into a single run."""
    recorder = await _setup(hass)

    for index in range(25):
        hass.bus.async_fire(
            "entity_registry_updated",
            {
                "action": "update",
                "entity_id": f"light.l{index}",
                "changes": {"area_id": "old"},
            },
        )
    await hass.async_block_till_done()
    await _after_cooldown(hass)

    assert recorder.calls == 1
    recorder.unload_all()


async def test_irrelevant_changes_do_not_recompile(hass: HomeAssistant) -> None:
    """A rename of an entity's friendly name changes no policy."""
    recorder = await _setup(hass)

    hass.bus.async_fire(
        "entity_registry_updated",
        {"action": "update", "entity_id": "light.a", "changes": {"name": "old"}},
    )
    await hass.async_block_till_done()
    await _after_cooldown(hass)

    assert recorder.calls == 0
    recorder.unload_all()


async def test_unload_removes_every_listener(hass: HomeAssistant) -> None:
    """After unload nothing fires into the unloaded integration."""
    recorder = await _setup(hass)
    before = sum(hass.bus.async_listeners().values())

    recorder.unload_all()
    hass.bus.async_fire("user_added", {"user_id": "x"})
    await hass.async_block_till_done()
    await _after_cooldown(hass)

    assert recorder.calls == 0
    assert sum(hass.bus.async_listeners().values()) == before - len(
        auto_recompile._LISTENED
    )


async def test_real_registry_move_triggers_recompile(hass: HomeAssistant) -> None:
    """Moving an entity between areas in HA's real registry recompiles."""
    from homeassistant.helpers import area_registry as ar
    from homeassistant.helpers import entity_registry as er

    area_registry = ar.async_get(hass)
    kids = area_registry.async_create("Kids")
    hall = area_registry.async_create("Hall")
    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get_or_create(
        "lock", "test", "front", suggested_object_id="front_door"
    )
    entity_registry.async_update_entity(entry.entity_id, area_id=kids.id)
    await hass.async_block_till_done()
    recorder = await _setup(hass)

    entity_registry.async_update_entity(entry.entity_id, area_id=hall.id)
    await hass.async_block_till_done()
    await _after_cooldown(hass)

    assert recorder.calls == 1
    recorder.unload_all()


async def test_unchanged_bind_and_policy_write_fire_nothing(
    hass: HomeAssistant,
) -> None:
    """The loop guard: re-applying an unchanged plan fires no ``user_updated``.

    Tessera listens to ``user_updated`` and its own binds fire it. Without the
    no-op skip, every recompile would trigger the next one, forever.
    """
    policy_store = AuthPolicyStoreAdapter(hass, ha_version=SUPPORTED_HA_AUTH_VERSION)
    binding = UserBindingAdapter(hass, ha_version=SUPPORTED_HA_AUTH_VERSION)
    policy = {"entities": {"entity_ids": {"light.a": {"read": True}}}}
    await policy_store.async_set_group_policy("tessera:r1", "tessera:r1", policy)
    await hass.auth.async_create_user("owner", group_ids=["system-admin"])
    user = await hass.auth.async_create_user("u", group_ids=["system-users"])
    await binding.async_bind_full_superset(
        user, ["tessera:r1"], expected_tessera_group_ids=[]
    )
    await hass.async_block_till_done()
    fired: list[str] = []
    remove = hass.bus.async_listen("user_updated", lambda e: fired.append("x"))
    saved: list[int] = []
    original_save = hass.auth._store._store.async_save

    async def _counting_save(*args: Any, **kwargs: Any) -> None:
        saved.append(1)
        await original_save(*args, **kwargs)

    hass.auth._store._store.async_save = _counting_save  # type: ignore[method-assign]

    await policy_store.async_set_group_policy("tessera:r1", "tessera:r1", policy)
    await binding.async_bind_full_superset(
        user, ["tessera:r1"], expected_tessera_group_ids=["tessera:r1"]
    )
    await hass.async_block_till_done()

    assert fired == []
    assert saved == []
    remove()
