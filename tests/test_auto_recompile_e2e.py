"""End to end: registry and user changes reach the native groups by themselves.

Real HA registries, real AuthStore, real bus and Debouncer, real Tessera store
and enforce path — only the clock is advanced by hand. Before auto-recompile,
both scenarios kept over-granted access until somebody ran tessera.recompile.
"""

from __future__ import annotations

from datetime import timedelta
from functools import partial
from typing import Any

import custom_components.tessera as tessera_init
import pytest
from custom_components.tessera.auto_recompile import (
    RECOMPILE_COOLDOWN,
    async_setup_auto_recompile,
)
from custom_components.tessera.config_flow import (
    add_area_grant,
    add_role,
    set_mode,
    set_user_membership,
)
from custom_components.tessera.const import DOMAIN
from custom_components.tessera.schema import (
    default_config_data,
    default_policy_data,
)
from custom_components.tessera.store import TesseraStore
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

ENTRY_ID = "e2e-entry"


async def _after_cooldown(hass: HomeAssistant) -> None:
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=RECOMPILE_COOLDOWN + 1)
    )
    await hass.async_block_till_done()


def _policy_entity_ids(hass: HomeAssistant, group_id: str) -> set[str]:
    group = hass.auth._store._groups[group_id]
    return set(group.policy["entities"]["entity_ids"])


def _group_ids(user: Any) -> list[str]:
    return sorted(group.id for group in user.groups)


@pytest.fixture
async def enforced(hass: HomeAssistant) -> dict[str, Any]:
    """A live enforce entry: role kid may operate everything in area Kids."""
    owner = await hass.auth.async_create_user("owner", group_ids=["system-admin"])
    owner.is_owner = True
    kid = await hass.auth.async_create_user("kid", group_ids=["system-users"])

    areas = ar.async_get(hass)
    kids_room = areas.async_create("Kids")
    hall = areas.async_create("Hall")
    entities = er.async_get(hass)
    lock = entities.async_get_or_create(
        "lock", "test", "front", suggested_object_id="front_door"
    )
    lamp = entities.async_get_or_create(
        "light", "test", "lamp", suggested_object_id="kids_lamp"
    )
    entities.async_update_entity(lock.entity_id, area_id=kids_room.id)
    entities.async_update_entity(lamp.entity_id, area_id=kids_room.id)

    config = add_role(default_config_data(), "kid", name="Kid")
    config = set_user_membership(config, kid.id, ["kid"])
    config = set_mode(config, "enforce")
    policy = add_area_grant(
        config,
        default_policy_data(),
        area_id=kids_room.id,
        role_id="kid",
        read=True,
        control=True,
    )
    store = TesseraStore(hass)
    await store.async_save_config(config)
    await store.async_save_policy(policy)
    entry_data: dict[str, Any] = {"store": store}
    hass.data.setdefault(DOMAIN, {})[ENTRY_ID] = entry_data

    await tessera_init._compile_for_mode(hass, ENTRY_ID, entry_data)
    assert entry_data["mode"] == "enforce", entry_data.get("last_apply_result")

    unload: list[Any] = []
    async_setup_auto_recompile(
        hass,
        unload.append,
        # exactly what async_setup_entry passes (a lambda here hid a real bug)
        partial(tessera_init._auto_recompile, hass, ENTRY_ID),
    )
    await hass.async_block_till_done()
    yield {
        "kid": kid,
        "lock": lock.entity_id,
        "lamp": lamp.entity_id,
        "hall": hall.id,
        "entities": entities,
        "entry_data": entry_data,
    }
    for func in unload:
        func()


async def test_entity_moved_out_of_a_granted_area_loses_the_grant(
    hass: HomeAssistant, enforced: dict[str, Any]
) -> None:
    """The front-door lock leaves the kids' room; the kid must lose control."""
    assert _policy_entity_ids(hass, "tessera:kid") == {
        enforced["lock"],
        enforced["lamp"],
    }

    enforced["entities"].async_update_entity(enforced["lock"], area_id=enforced["hall"])
    await hass.async_block_till_done()
    await _after_cooldown(hass)

    assert _policy_entity_ids(hass, "tessera:kid") == {enforced["lamp"]}
    assert enforced["entry_data"]["mode"] == "enforce"
    kid_permissions = enforced["kid"].permissions
    assert not kid_permissions.check_entity(enforced["lock"], "control")
    assert kid_permissions.check_entity(enforced["lamp"], "control")


async def test_user_added_under_enforce_is_bound_by_itself(
    hass: HomeAssistant, enforced: dict[str, Any]
) -> None:
    """A new user starts on HA's allow-all default; Tessera narrows it unasked."""
    guest = await hass.auth.async_create_user("guest", group_ids=["system-users"])
    assert _group_ids(guest) == ["system-users"]

    await hass.async_block_till_done()
    await _after_cooldown(hass)

    assert _group_ids(guest) == ["tessera:__default__"]
    assert not guest.permissions.check_entity(enforced["lock"], "read")
    # The bind fired user_updated; the follow-up recompile must find nothing to do.
    await _after_cooldown(hass)
    assert _group_ids(guest) == ["tessera:__default__"]


async def test_revocation_reaches_a_user_whose_permissions_were_cached(
    hass: HomeAssistant, enforced: dict[str, Any]
) -> None:
    """HA caches User.permissions; a moved entity must stop granting anyway.

    The kid has used HA (permissions cached). The lock leaves the kids' room,
    the group policy changes in place and the kid's group ids do not — the bind
    is a no-op, yet the cache has to drop or the grant lives until restart.
    """
    kid = enforced["kid"]
    assert kid.permissions.check_entity(enforced["lock"], "control")

    enforced["entities"].async_update_entity(enforced["lock"], area_id=enforced["hall"])
    await hass.async_block_till_done()
    await _after_cooldown(hass)

    assert _policy_entity_ids(hass, "tessera:kid") == {enforced["lamp"]}
    assert not kid.permissions.check_entity(enforced["lock"], "control")


async def test_a_blocked_auto_recompile_keeps_enforce_and_retries(
    hass: HomeAssistant, enforced: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unattended block must not freeze the drift behind a persisted monitor.

    Before: the block failed safe to monitor, the bindings stayed live, and
    every later recompile only previewed — the moved lock kept its grant and a
    new user kept allow-all. Now enforce stays, and the next change re-applies.
    """
    from custom_components.tessera.mode_manager import _blocked

    real_compute = tessera_init.compute_enforce_plan

    async def blocked(_hass: Any, _store: Any) -> Any:
        return _blocked("linter", ["conflict"])

    monkeypatch.setattr(tessera_init, "compute_enforce_plan", blocked)
    hass.bus.async_fire("label_registry_updated", {"action": "create"})
    await hass.async_block_till_done()
    await _after_cooldown(hass)

    entry_data = enforced["entry_data"]
    assert entry_data["mode"] == "enforce"
    assert (await entry_data["store"].async_load_config())["mode"] == "enforce"
    assert _group_ids(enforced["kid"]) == ["tessera:kid"]  # last state kept

    monkeypatch.setattr(tessera_init, "compute_enforce_plan", real_compute)
    enforced["entities"].async_update_entity(enforced["lock"], area_id=enforced["hall"])
    guest = await hass.auth.async_create_user("guest", group_ids=["system-users"])
    await hass.async_block_till_done()
    await _after_cooldown(hass)

    assert _policy_entity_ids(hass, "tessera:kid") == {enforced["lamp"]}
    assert _group_ids(guest) == ["tessera:__default__"]


async def test_unload_waits_for_a_running_auto_recompile(
    hass: HomeAssistant, enforced: dict[str, Any]
) -> None:
    """A recompile mid-apply must not re-bind users after unload restored them."""
    import asyncio
    from dataclasses import dataclass

    @dataclass
    class Entry:
        entry_id: str

    store = enforced["entry_data"]["store"]
    gate = asyncio.Event()
    entered = asyncio.Event()
    real_mark = store.async_mark_apply_in_progress
    calls = {"n": 0}

    async def held_open(snapshot: Any) -> Any:
        calls["n"] += 1
        if calls["n"] == 1:
            entered.set()
            await gate.wait()
        return await real_mark(snapshot)

    store.async_mark_apply_in_progress = held_open
    enforced["entities"].async_update_entity(enforced["lock"], area_id=enforced["hall"])
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=RECOMPILE_COOLDOWN + 3)
    )
    await asyncio.wait_for(entered.wait(), 2)

    unload = hass.async_create_task(
        tessera_init.async_unload_entry(hass, Entry(ENTRY_ID))  # type: ignore[arg-type]
    )
    for _ in range(20):
        await asyncio.sleep(0)
    assert not unload.done()  # waits for the running recompile
    gate.set()
    await unload
    await hass.async_block_till_done()

    assert "tessera:kid" not in _group_ids(enforced["kid"])
    assert ENTRY_ID not in hass.data.get(DOMAIN, {})
