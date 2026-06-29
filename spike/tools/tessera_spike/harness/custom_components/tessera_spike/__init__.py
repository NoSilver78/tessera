"""Dev-only Tessera spike harness for HA 2026.6.4."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.auth import models
from homeassistant.auth.const import GROUP_ID_ADMIN, GROUP_ID_READ_ONLY, GROUP_ID_USER
from homeassistant.auth.permissions.const import (
    CAT_ENTITIES,
    POLICY_CONTROL,
    POLICY_READ,
)
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import ConfigType

DOMAIN = "tessera_spike"
RESULT_PATH = Path("/config/tessera_spike_result.json")
STATE_PATH = Path("/config/tessera_spike_state.json")
RESCUE_SNAPSHOT_PATH = Path("/config/tessera_spike_rescue_snapshot.json")
RESCUE_TRIGGER_PATH = Path("/config/tessera_spike_rescue_trigger.json")
RESCUE_RESULT_PATH = Path("/config/tessera_spike_rescue_result.json")
CORRUPT_TESSERA_CONFIG_PATH = Path("/config/.storage/tessera.config")
AUTH_STORE_PATH = Path("/config/.storage/auth")

ALLOWED_ENTITY = "input_boolean.tessera_allowed_light"
FORBIDDEN_ENTITY = "input_boolean.tessera_forbidden_light"
STATE_ONLY_ENTITY = "sensor.tessera_state_only"
GROUP_ID = "tessera:test"
GROUP_ID_EXTRA = "tessera:extra"
GROUP_ID_D2 = "tessera:d2"
TEST_USER_NAME = "tessera-test-user"
TEST_D2_USER_NAME = "tessera-d2-user"
TEST_RESCUE_USER_NAME = "tessera-rescue-user"
TEST_REPLACE_USER_NAME = "tessera-replace-user"
TEST_ADMIN_NAME = "tessera-test-admin"
TEST_RO_NAME = "tessera-test-ro"
ENFORCE_MANAGED_USER_NAMES = {
    TEST_USER_NAME,
    TEST_D2_USER_NAME,
    TEST_RESCUE_USER_NAME,
    TEST_REPLACE_USER_NAME,
}
MANAGED_USER_PREFIX = "tessera-"
MANAGED_GROUP_PREFIX = "tessera:"

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)


def _policy(
    entity_id: str, *, read: bool = True, control: bool = False
) -> dict[str, Any]:
    leaf: dict[str, bool] = {}
    if read:
        leaf[POLICY_READ] = True
    if control:
        leaf[POLICY_CONTROL] = True
    return {CAT_ENTITIES: {"entity_ids": {entity_id: leaf}}}


def _sanitize_user(user: models.User) -> dict[str, Any]:
    return {
        "name": user.name,
        "is_owner": user.is_owner,
        "is_admin": user.is_admin,
        "is_active": user.is_active,
        "system_generated": user.system_generated,
        "groups": [group.id for group in user.groups],
        "credentials_count": len(user.credentials),
        "refresh_token_classes": sorted(
            {token.token_type for token in user.refresh_tokens.values()}
        ),
        "refresh_token_count": len(user.refresh_tokens),
    }


async def _auth_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    users = await hass.auth.async_get_users()
    groups = (
        await hass.auth._store.async_get_groups()
    )  # noqa: SLF001 - spike probes private API.
    return {
        "users": [_sanitize_user(user) for user in users],
        "groups": [
            {
                "id": group.id,
                "name": group.name,
                "system_generated": group.system_generated,
                "has_policy": bool(group.policy),
                "policy_keys": (
                    sorted(group.policy.keys())
                    if isinstance(group.policy, dict)
                    else []
                ),
            }
            for group in groups
        ],
    }


async def _persist_auth(hass: HomeAssistant) -> None:
    store = hass.auth._store  # noqa: SLF001 - this spike explicitly probes private API.
    await store._store.async_save(store._data_to_save())  # noqa: SLF001
    await asyncio.sleep(0.2)


async def _ensure_group(
    hass: HomeAssistant, group_id: str, name: str, policy: dict[str, Any]
) -> models.Group:
    store = hass.auth._store  # noqa: SLF001
    await store.async_get_groups()
    group = await hass.auth.async_get_group(group_id)
    if group is None:
        group = models.Group(
            id=group_id, name=name, policy=policy, system_generated=False
        )
        store._groups[group_id] = group  # noqa: SLF001
    else:
        group.name = name
        group.policy = policy
    await _persist_auth(hass)
    return group


async def _ensure_test_user(
    hass: HomeAssistant, name: str, group_ids: list[str]
) -> models.User:
    users = await hass.auth.async_get_users()
    for user in users:
        if user.name == name:
            await hass.auth.async_update_user(user, group_ids=group_ids)
            return user
    return await hass.auth.async_create_user(name, group_ids=group_ids, local_only=True)


async def _make_access_token(
    hass: HomeAssistant, user: models.User, client_name: str
) -> tuple[str, models.RefreshToken]:
    token = await hass.auth.async_create_refresh_token(
        user,
        client_id="http://localhost:8124/",
        client_name=client_name,
    )
    access_token = hass.auth.async_create_access_token(token, "127.0.0.1")
    return access_token, token


async def _http_json(
    hass: HomeAssistant,
    method: str,
    path: str,
    access_token: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    session = aiohttp_client.async_get_clientsession(hass)
    headers = {"Authorization": f"Bearer {access_token}"}
    url = f"http://127.0.0.1:8123{path}"
    async with session.request(method, url, headers=headers, json=payload) as resp:
        text = await resp.text()
        try:
            body = json.loads(text) if text else None
        except json.JSONDecodeError:
            body = {"raw": text[:200]}
        return {"status": resp.status, "body_type": type(body).__name__, "body": body}


def _status(verdict: str, evidence: dict[str, Any]) -> dict[str, Any]:
    return {"verdict": verdict, "evidence": evidence}


def _write_json_sync(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True))


def _read_json_sync(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


async def _write_json(hass: HomeAssistant, path: Path, data: dict[str, Any]) -> None:
    await hass.async_add_executor_job(_write_json_sync, path, data)


async def _read_json(hass: HomeAssistant, path: Path) -> dict[str, Any]:
    return await hass.async_add_executor_job(_read_json_sync, path)


async def _unlink_path(hass: HomeAssistant, path: Path) -> None:
    await hass.async_add_executor_job(lambda: path.unlink(missing_ok=True))


async def _find_user(hass: HomeAssistant, name: str) -> models.User | None:
    users = await hass.auth.async_get_users()
    return next((user for user in users if user.name == name), None)


async def _run_boot_rescue_if_requested(hass: HomeAssistant) -> dict[str, Any]:
    """Restore managed user groups during HA boot when the rescue trigger exists."""
    if not RESCUE_TRIGGER_PATH.exists():
        return {"requested": False}

    snapshot = await _read_json(hass, RESCUE_SNAPSHOT_PATH)
    try:
        await _read_json(hass, CORRUPT_TESSERA_CONFIG_PATH)
    except json.JSONDecodeError as err:
        corrupt_store_parse_failed = True
        corrupt_store_error = type(err).__name__
    else:
        corrupt_store_parse_failed = False
        corrupt_store_error = None
    result: dict[str, Any] = {
        "requested": True,
        "snapshot_present": bool(snapshot),
        "corrupt_tessera_store_path": str(CORRUPT_TESSERA_CONFIG_PATH),
        "corrupt_tessera_store_parse_failed": corrupt_store_parse_failed,
        "corrupt_tessera_store_error": corrupt_store_error,
        "restored_users": [],
        "errors": [],
        "used_public_async_update_user": True,
    }
    for item in snapshot.get("users", []):
        name = item.get("name")
        group_ids = item.get("group_ids")
        if not isinstance(name, str) or not isinstance(group_ids, list):
            result["errors"].append("invalid_snapshot_item")
            continue
        try:
            validated_group_ids = [
                _validate_managed_group_id(group_id) for group_id in group_ids
            ]
        except vol.Invalid:
            result["errors"].append(f"invalid_group_namespace:{name}")
            continue
        user = await _find_user(hass, name)
        if user is None:
            result["errors"].append(f"user_not_found:{name}")
            continue
        if violation := _validate_managed_user(user):
            result["errors"].append(violation["error"])
            continue
        await hass.auth.async_update_user(user, group_ids=list(validated_group_ids))
        actual_groups = [group.id for group in user.groups]
        exact_match = set(actual_groups) == set(validated_group_ids)
        if not exact_match:
            result["errors"].append(f"group_mismatch:{name}")
        result["restored_users"].append(
            {
                "name": name,
                "expected_group_ids": sorted(validated_group_ids),
                "actual_group_ids": sorted(actual_groups),
                "exact_match": exact_match,
            }
        )

    await _persist_auth(hass)
    result["ok"] = corrupt_store_parse_failed and not result["errors"]
    result["rescue_restore_namespace_guarded"] = True
    result["auth_store_corrupted"] = False
    result["boot_rescue_corruption_tested"] = False
    result["no_admin_lockout"] = None
    result["d5_truthfulness"] = (
        "PARTIAL: startup restore was exercised against Tessera sidecar corruption, "
        "not real /config/.storage/auth corruption"
    )
    await _write_json(hass, RESCUE_RESULT_PATH, result)
    await _unlink_path(hass, RESCUE_TRIGGER_PATH)
    return result


def _validate_managed_group_id(group_id: str) -> str:
    if not group_id.startswith(MANAGED_GROUP_PREFIX):
        raise vol.Invalid("group_id must use the tessera: dev namespace")
    return group_id


def _validate_managed_user_name(user_name: str) -> str:
    if not user_name.startswith(MANAGED_USER_PREFIX):
        raise vol.Invalid("user_name must use the tessera- dev namespace")
    return user_name


def _validate_managed_user(user: models.User) -> dict[str, Any] | None:
    if (
        user.is_owner
        or user.system_generated
        or not user.name.startswith(MANAGED_USER_PREFIX)
    ):
        return {"ok": False, "error": "refusing_unmanaged_user"}
    return None


def _known_config_entry_id(hass: HomeAssistant) -> str | None:
    for domain in ("sun", "shopping_list", "backup"):
        entries = hass.config_entries.async_entries(domain)
        if entries:
            return entries[0].entry_id
    entries = hass.config_entries.async_entries()
    return entries[0].entry_id if entries else None


def _area_by_name_or_create(area_reg: ar.AreaRegistry, name: str) -> ar.AreaEntry:
    area = area_reg.async_get_area_by_name(name)
    if area is not None:
        return area
    return area_reg.async_create(name)


async def _ensure_seed_fixture(hass: HomeAssistant) -> dict[str, Any]:
    """Create deterministic registry fixture coverage for Welle A."""
    area_reg = ar.async_get(hass)
    device_reg = dr.async_get(hass)
    entity_reg = er.async_get(hass)

    living = _area_by_name_or_create(area_reg, "Tessera Living")
    kitchen = _area_by_name_or_create(area_reg, "Tessera Kitchen")

    config_entry_id = _known_config_entry_id(hass)
    device_id: str | None = None
    if config_entry_id is not None:
        device = device_reg.async_get_or_create(
            config_entry_id=config_entry_id,
            identifiers={(DOMAIN, "seed-device-living")},
            manufacturer="Tessera",
            model="Spike Fixture",
            name="Tessera Seed Device Living",
        )
        device = device_reg.async_update_device(device.id, area_id=living.id) or device
        device_id = device.id

    specs = [
        (
            "device_area_allowed_light",
            "light",
            "seed_allowed_light",
            device_id,
            None,
            None,
            None,
        ),
        (
            "direct_area_forbidden_sensor",
            "sensor",
            "seed_forbidden_sensor",
            None,
            kitchen.id,
            None,
            None,
        ),
        (
            "device_area_allowed_cover",
            "cover",
            "seed_allowed_cover",
            device_id,
            None,
            None,
            None,
        ),
        (
            "hidden_direct_area_camera",
            "camera",
            "seed_hidden_camera",
            None,
            kitchen.id,
            er.RegistryEntryHider.USER,
            None,
        ),
        (
            "disabled_direct_area_lock",
            "lock",
            "seed_disabled_lock",
            None,
            living.id,
            None,
            er.RegistryEntryDisabler.USER,
        ),
    ]

    entities: list[dict[str, Any]] = []
    for (
        class_name,
        domain,
        unique_id,
        entry_device_id,
        area_id,
        hidden_by,
        disabled_by,
    ) in specs:
        object_id = f"tessera_{unique_id}"
        entry = entity_reg.async_get_or_create(
            domain,
            DOMAIN,
            unique_id,
            suggested_object_id=object_id,
            device_id=entry_device_id,
            hidden_by=hidden_by,
            disabled_by=disabled_by,
            original_name=object_id,
        )
        if area_id is not None:
            entry = entity_reg.async_update_entity(entry.entity_id, area_id=area_id)
        entities.append(
            {
                "entity_id": entry.entity_id,
                "domain": domain,
                "class": class_name,
                "area_id": entry.area_id,
                "device_id": entry.device_id,
                "disabled_by": str(entry.disabled_by) if entry.disabled_by else None,
                "hidden_by": str(entry.hidden_by) if entry.hidden_by else None,
            }
        )

    entities.append(
        {
            "entity_id": STATE_ONLY_ENTITY,
            "domain": "sensor",
            "class": "state_only_without_registry",
            "area_id": None,
            "device_id": None,
            "disabled_by": None,
            "hidden_by": None,
        }
    )
    return {
        "fixture_version": 2,
        "areas": [
            {"area_id": living.id, "name": living.name},
            {"area_id": kitchen.id, "name": kitchen.name},
        ],
        "device": {
            "device_id": device_id,
            "area_id": living.id if device_id else None,
            "config_entry_id_present": config_entry_id is not None,
        },
        "entities": entities,
        "non_entity_services": [
            {
                "service": "tessera_spike.snapshot",
                "class": "intentionally_non_entity_dev_service",
                "values_redacted": True,
            }
        ],
        "complete_for_welle_a": device_id is not None,
    }


async def _probe_d2_three_way(hass: HomeAssistant) -> dict[str, Any]:
    """Measure policy mutation before invalidation, after invalidation, and persist."""
    await _ensure_group(
        hass,
        GROUP_ID_D2,
        "Tessera D2",
        _policy(ALLOWED_ENTITY, read=True, control=True),
    )
    test_user = await _ensure_test_user(hass, TEST_D2_USER_NAME, [GROUP_ID_D2])

    before = {
        "allowed_read": test_user.permissions.check_entity(ALLOWED_ENTITY, POLICY_READ),
        "forbidden_read": test_user.permissions.check_entity(
            FORBIDDEN_ENTITY, POLICY_READ
        ),
        "forbidden_control": test_user.permissions.check_entity(
            FORBIDDEN_ENTITY, POLICY_CONTROL
        ),
    }

    group = await hass.auth.async_get_group(GROUP_ID_D2)
    assert group is not None
    group.policy = _policy(FORBIDDEN_ENTITY, read=True, control=True)

    without_invalidate = {
        "allowed_read": test_user.permissions.check_entity(ALLOWED_ENTITY, POLICY_READ),
        "forbidden_read": test_user.permissions.check_entity(
            FORBIDDEN_ENTITY, POLICY_READ
        ),
        "forbidden_control": test_user.permissions.check_entity(
            FORBIDDEN_ENTITY, POLICY_CONTROL
        ),
    }

    test_user.invalidate_cache()
    after_invalidate = {
        "allowed_read": test_user.permissions.check_entity(ALLOWED_ENTITY, POLICY_READ),
        "forbidden_read": test_user.permissions.check_entity(
            FORBIDDEN_ENTITY, POLICY_READ
        ),
        "forbidden_control": test_user.permissions.check_entity(
            FORBIDDEN_ENTITY, POLICY_CONTROL
        ),
    }
    await _persist_auth(hass)

    return {
        "user": _sanitize_user(test_user),
        "group_id": GROUP_ID_D2,
        "before_mutation": before,
        "after_policy_mutation_without_invalidate": without_invalidate,
        "after_explicit_invalidate": after_invalidate,
        "persisted_for_restart_check": True,
        "expected": {
            "without_invalidate_keeps_old_cache": True,
            "after_invalidate_allows_forbidden_entity": True,
        },
    }


async def _probe_native_write_replace_contract(hass: HomeAssistant) -> dict[str, Any]:
    """Prove HA async_update_user(group_ids=...) replaces groups, not unions them."""
    await _ensure_group(
        hass,
        GROUP_ID,
        "Tessera Test",
        _policy(ALLOWED_ENTITY, read=True, control=True),
    )
    await _ensure_group(
        hass,
        GROUP_ID_EXTRA,
        "Tessera Extra",
        _policy(FORBIDDEN_ENTITY, read=True, control=False),
    )
    user = await _ensure_test_user(
        hass, TEST_REPLACE_USER_NAME, [GROUP_ID, GROUP_ID_EXTRA]
    )
    before_groups = [group.id for group in user.groups]

    await hass.auth.async_update_user(user, group_ids=[GROUP_ID])
    after_subset_write = [group.id for group in user.groups]

    full_superset = sorted({GROUP_ID, GROUP_ID_EXTRA})
    await hass.auth.async_update_user(user, group_ids=full_superset)
    after_superset_write = [group.id for group in user.groups]
    await _persist_auth(hass)

    return {
        "native_write_is_replace": GROUP_ID_EXTRA not in after_subset_write,
        "caller_passes_full_superset": set(after_superset_write) == set(full_superset),
        "api": "hass.auth.async_update_user(group_ids=...)",
        "claim_correction": (
            "group_ids is REPLACE; no-lockout depends on caller supplying the "
            "complete intended group set"
        ),
        "before_groups": before_groups,
        "subset_write": [GROUP_ID],
        "after_subset_write": after_subset_write,
        "safe_full_superset": full_superset,
        "after_superset_write": after_superset_write,
    }


async def _probe_rescue_namespace_guard(hass: HomeAssistant) -> dict[str, Any]:
    """Exercise the rescue snapshot group-id validator without writing auth state."""
    malicious_snapshot = {
        "users": [{"name": TEST_RESCUE_USER_NAME, "group_ids": [GROUP_ID_USER]}]
    }
    invalid_groups: list[str] = []
    for item in malicious_snapshot["users"]:
        for group_id in item["group_ids"]:
            try:
                _validate_managed_group_id(group_id)
            except vol.Invalid:
                invalid_groups.append(group_id)
    return {
        "rescue_restore_namespace_guarded": bool(invalid_groups),
        "malicious_group_ids_rejected": invalid_groups,
        "would_restore_system_users": False,
    }


async def _prepare_boot_rescue(hass: HomeAssistant) -> dict[str, Any]:
    """Prepare startup restore against sidecar corruption; not real auth-store rescue."""
    await _ensure_group(
        hass,
        GROUP_ID,
        "Tessera Test",
        _policy(ALLOWED_ENTITY, read=True, control=True),
    )
    await _ensure_group(
        hass,
        GROUP_ID_EXTRA,
        "Tessera Extra",
        _policy(FORBIDDEN_ENTITY, read=True, control=False),
    )
    user = await _ensure_test_user(hass, TEST_RESCUE_USER_NAME, [GROUP_ID])
    expected_groups = [group.id for group in user.groups]
    await hass.auth.async_update_user(user, group_ids=[GROUP_ID_EXTRA])
    drifted_groups = [group.id for group in user.groups]

    snapshot = {
        "users": [{"name": TEST_RESCUE_USER_NAME, "group_ids": expected_groups}],
        "scope": "managed_user_group_ids_only",
        "uses_public_async_update_user_on_boot": True,
    }
    await _write_json(hass, RESCUE_SNAPSHOT_PATH, snapshot)
    await _write_json(hass, RESCUE_TRIGGER_PATH, {"requested": True})
    await hass.async_add_executor_job(
        CORRUPT_TESSERA_CONFIG_PATH.write_text,
        '{"intentionally_corrupt": ',
    )
    await _persist_auth(hass)

    return {
        "prepared": True,
        "user_name": TEST_RESCUE_USER_NAME,
        "expected_groups": expected_groups,
        "drifted_groups_before_restart": drifted_groups,
        "snapshot_path": str(RESCUE_SNAPSHOT_PATH),
        "trigger_path": str(RESCUE_TRIGGER_PATH),
        "corrupt_tessera_store_path": str(CORRUPT_TESSERA_CONFIG_PATH),
        "auth_store_path": str(AUTH_STORE_PATH),
        "auth_store_corrupted": False,
        "boot_rescue_corruption_tested": False,
        "no_admin_lockout": None,
        "verdict": "PARTIAL",
        "partial_reason": (
            "real /config/.storage/auth corruption is not attempted in this run; "
            "D5 must not be reported as PASS"
        ),
    }


async def _probe_system_users_gate(hass: HomeAssistant) -> dict[str, Any]:
    """Verify managed users have no fallback into HA's allow-all users group."""
    users = await hass.auth.async_get_users()
    by_name = {user.name: user for user in users if user.name is not None}
    managed = [
        _sanitize_user(by_name[name])
        for name in sorted(ENFORCE_MANAGED_USER_NAMES)
        if name in by_name and not by_name[name].system_generated
    ]
    missing = sorted(ENFORCE_MANAGED_USER_NAMES - set(user["name"] for user in managed))
    excluded_system_fixture_users = [
        user.name
        for user in users
        if not user.system_generated and user.name in {TEST_ADMIN_NAME, TEST_RO_NAME}
    ]
    offenders = sorted(
        user["name"] for user in managed if GROUP_ID_USER in user["groups"]
    )
    return {
        "ok": not offenders and not missing,
        "system_users_group_id": GROUP_ID_USER,
        "enforce_managed_users": managed,
        "expected_managed_users": sorted(ENFORCE_MANAGED_USER_NAMES),
        "expected_managed_users_present": not missing,
        "missing_expected_managed_users": missing,
        "excluded_system_fixture_users": sorted(excluded_system_fixture_users),
        "offenders": offenders,
        "system_generated_users_ignored": sum(
            1 for user in users if user.system_generated
        ),
    }


async def _phase_pre_restart(hass: HomeAssistant) -> dict[str, Any]:
    hass.states.async_set(
        STATE_ONLY_ENTITY, "42", {"friendly_name": "Tessera State Only"}
    )
    seed_fixture = await _ensure_seed_fixture(hass)
    before = await _auth_snapshot(hass)

    await _ensure_group(
        hass,
        GROUP_ID,
        "Tessera Test",
        _policy(ALLOWED_ENTITY, read=True, control=True),
    )
    await _ensure_group(
        hass,
        GROUP_ID_EXTRA,
        "Tessera Extra",
        _policy(FORBIDDEN_ENTITY, read=True, control=False),
    )
    # Managed Tessera users must not remain in system-users while enforcing; HA
    # group policies merge permissively. Keep this probe user only in tessera:test.
    test_user = await _ensure_test_user(hass, TEST_USER_NAME, [GROUP_ID])
    await _ensure_test_user(hass, TEST_ADMIN_NAME, [GROUP_ID_ADMIN])
    await _ensure_test_user(hass, TEST_RO_NAME, [GROUP_ID_READ_ONLY])

    allowed_read = test_user.permissions.check_entity(ALLOWED_ENTITY, POLICY_READ)
    forbidden_read = test_user.permissions.check_entity(FORBIDDEN_ENTITY, POLICY_READ)
    allowed_control = test_user.permissions.check_entity(ALLOWED_ENTITY, POLICY_CONTROL)
    forbidden_control = test_user.permissions.check_entity(
        FORBIDDEN_ENTITY, POLICY_CONTROL
    )

    # D2: policy-only change without membership change.
    group = await hass.auth.async_get_group(GROUP_ID)
    assert group is not None
    group.policy = _policy(FORBIDDEN_ENTITY, read=True, control=True)
    test_user.invalidate_cache()
    d2_after_change = {
        "allowed_read_after_policy_change": test_user.permissions.check_entity(
            ALLOWED_ENTITY, POLICY_READ
        ),
        "forbidden_read_after_policy_change": test_user.permissions.check_entity(
            FORBIDDEN_ENTITY, POLICY_READ
        ),
        "forbidden_control_after_policy_change": test_user.permissions.check_entity(
            FORBIDDEN_ENTITY, POLICY_CONTROL
        ),
    }
    # Restore intended D1/D3 policy.
    group.policy = _policy(ALLOWED_ENTITY, read=True, control=True)
    test_user.invalidate_cache()
    await _persist_auth(hass)

    # D4: full union and restore.
    original_groups = [group.id for group in test_user.groups]
    await hass.auth.async_update_user(test_user, group_ids=[GROUP_ID, GROUP_ID_EXTRA])
    union_groups = [group.id for group in test_user.groups]
    await hass.auth.async_update_user(test_user, group_ids=original_groups)
    restored_groups = [group.id for group in test_user.groups]
    await _persist_auth(hass)

    await _write_json(
        hass,
        STATE_PATH,
        {
            "test_user_name": TEST_USER_NAME,
            "test_admin_name": TEST_ADMIN_NAME,
            "test_ro_name": TEST_RO_NAME,
            "group_id": GROUP_ID,
            "group_id_extra": GROUP_ID_EXTRA,
            "original_groups": original_groups,
        },
    )

    after = await _auth_snapshot(hass)
    result = {
        "phase": "pre_restart",
        "seed_fixture": seed_fixture,
        "before": before,
        "after": after,
        "d1_pre_restart": {
            "group_created": (await hass.auth.async_get_group(GROUP_ID)) is not None,
            "policy_written": bool((await hass.auth.async_get_group(GROUP_ID)).policy),
        },
        "d2_policy_change_no_restart": d2_after_change,
        "d3_internal_check_entity": {
            "allowed_read": allowed_read,
            "forbidden_read": forbidden_read,
            "allowed_control": allowed_control,
            "forbidden_control": forbidden_control,
        },
        "d4_union_restore": {
            "original_groups": original_groups,
            "union_groups": union_groups,
            "restored_groups": restored_groups,
        },
        "d5_restore_primitive": {
            "public_async_update_user_restore_available": True,
            "boot_rescue_corruption_tested": False,
            "native_write_is_replace": True,
            "safe_restore_requires_full_group_set": True,
        },
        "d2_three_way": await _probe_d2_three_way(hass),
        "a2_native_write_replace_contract": await _probe_native_write_replace_contract(
            hass
        ),
        "a3_rescue_namespace_guard": await _probe_rescue_namespace_guard(hass),
        "d5_boot_rescue_prepare": await _prepare_boot_rescue(hass),
        "b3_system_users_gate_pre_restart": await _probe_system_users_gate(hass),
    }
    await _write_json(hass, RESULT_PATH, {"pre_restart": result})
    return result


async def _phase_post_restart(hass: HomeAssistant) -> dict[str, Any]:
    data = await _read_json(hass, RESULT_PATH)
    state = await _read_json(hass, STATE_PATH)
    rescue_result = await _read_json(hass, RESCUE_RESULT_PATH)
    test_user = await _find_user(hass, TEST_USER_NAME)
    d2_user = await _find_user(hass, TEST_D2_USER_NAME)
    group = await hass.auth.async_get_group(GROUP_ID)

    d1 = {
        "group_survived_restart": group is not None,
        "policy_survived_restart": bool(group and group.policy),
        "user_survived_restart": test_user is not None,
    }

    d3_rest: dict[str, Any] = {"tested": False}
    d6_services: dict[str, Any] = {"tested": False}
    d7_leaks: dict[str, Any] = {"tested": False}
    d8_llat: dict[str, Any] = {
        "tested": False,
        "reason": "no real LLAT created; normal dev access token used for headless probe only",
    }

    if test_user is not None:
        access_token, refresh_token = await _make_access_token(
            hass, test_user, "tessera-spike-headless"
        )
        states = await _http_json(hass, "GET", "/api/states", access_token)
        state_entities: list[str] = []
        if isinstance(states.get("body"), list):
            state_entities = [
                item.get("entity_id")
                for item in states["body"]
                if isinstance(item, dict)
            ]
        allowed_state = await _http_json(
            hass, "GET", f"/api/states/{ALLOWED_ENTITY}", access_token
        )
        forbidden_state = await _http_json(
            hass, "GET", f"/api/states/{FORBIDDEN_ENTITY}", access_token
        )
        allowed_service = await _http_json(
            hass,
            "POST",
            "/api/services/input_boolean/turn_on",
            access_token,
            {"entity_id": ALLOWED_ENTITY},
        )
        forbidden_service = await _http_json(
            hass,
            "POST",
            "/api/services/input_boolean/turn_on",
            access_token,
            {"entity_id": FORBIDDEN_ENTITY},
        )
        all_service = await _http_json(
            hass,
            "POST",
            "/api/services/input_boolean/turn_off",
            access_token,
            {"entity_id": "all"},
        )
        template = await _http_json(
            hass,
            "POST",
            "/api/template",
            access_token,
            {"template": "{{ states('input_boolean.tessera_forbidden_light') }}"},
        )

        d3_rest = {
            "tested": True,
            "state_list_status": states["status"],
            "allowed_in_state_list": ALLOWED_ENTITY in state_entities,
            "forbidden_in_state_list": FORBIDDEN_ENTITY in state_entities,
            "allowed_single_status": allowed_state["status"],
            "forbidden_single_status": forbidden_state["status"],
            "service_allowed_status": allowed_service["status"],
            "service_forbidden_status": forbidden_service["status"],
            "ws_tested": False,
        }
        d6_services = {
            "tested": True,
            "entity_service_allowed_status": allowed_service["status"],
            "entity_service_forbidden_status": forbidden_service["status"],
            "entity_id_all_status": all_service["status"],
            "return_response_changed_states_tested": False,
            "non_entity_service_tested": False,
        }
        d7_leaks = {
            "tested": True,
            "render_template_status": template["status"],
            "render_template_body_type": template["body_type"],
            "logbook_rest_tested": False,
            "registry_ws_tested": False,
            "history_tested": False,
        }
        d8_llat = {
            "tested": True,
            "normal_headless_access_token_probe": True,
            "llat_created": False,
            "refresh_token_revoked_after_probe": True,
        }
        hass.auth.async_remove_refresh_token(refresh_token)
        await _persist_auth(hass)

    result = {
        "phase": "post_restart",
        "state_file": state,
        "auth": await _auth_snapshot(hass),
        "d1_restart_survival": d1,
        "d2_three_way_after_restart": {
            "tested": d2_user is not None,
            "user": _sanitize_user(d2_user) if d2_user is not None else None,
            "allowed_read": (
                d2_user.permissions.check_entity(ALLOWED_ENTITY, POLICY_READ)
                if d2_user is not None
                else None
            ),
            "forbidden_read": (
                d2_user.permissions.check_entity(FORBIDDEN_ENTITY, POLICY_READ)
                if d2_user is not None
                else None
            ),
            "forbidden_control": (
                d2_user.permissions.check_entity(FORBIDDEN_ENTITY, POLICY_CONTROL)
                if d2_user is not None
                else None
            ),
        },
        "d5_boot_rescue_after_restart": rescue_result,
        "b3_system_users_gate_post_restart": await _probe_system_users_gate(hass),
        "d3_rest_ws_service": d3_rest,
        "d6_service_matrix": d6_services,
        "d7_leak_matrix": d7_leaks,
        "d8_headless_token": d8_llat,
        "d9_custom_component_runtime": {
            "runtime_custom_components_tested": False,
            "static_host_scan_expected": True,
        },
    }
    data["post_restart"] = result
    await _write_json(hass, RESULT_PATH, data)
    return result


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    boot_rescue = await _run_boot_rescue_if_requested(hass)
    hass.states.async_set(
        STATE_ONLY_ENTITY, "42", {"friendly_name": "Tessera State Only"}
    )

    async def run_spike(call: ServiceCall) -> dict[str, Any]:
        phase = call.data.get("phase", "pre_restart")
        if phase == "pre_restart":
            return await _phase_pre_restart(hass)
        if phase == "post_restart":
            return await _phase_post_restart(hass)
        return {"error": f"unknown phase {phase}"}

    async def ensure_group(call: ServiceCall) -> dict[str, Any]:
        group = await _ensure_group(
            hass,
            call.data["group_id"],
            call.data["name"],
            _policy(
                call.data["entity_id"],
                read=call.data.get("read", True),
                control=call.data.get("control", False),
            ),
        )
        return {
            "group": {
                "id": group.id,
                "name": group.name,
                "has_policy": bool(group.policy),
            }
        }

    async def set_group_policy(call: ServiceCall) -> dict[str, Any]:
        group = await hass.auth.async_get_group(call.data["group_id"])
        if group is None:
            return {"ok": False, "error": "group_not_found"}
        group.policy = _policy(
            call.data["entity_id"],
            read=call.data.get("read", True),
            control=call.data.get("control", False),
        )
        invalidated = 0
        for user in await hass.auth.async_get_users():
            if any(user_group.id == group.id for user_group in user.groups):
                user.invalidate_cache()
                invalidated += 1
        await _persist_auth(hass)
        return {
            "ok": True,
            "group_id": group.id,
            "has_policy": bool(group.policy),
            "invalidated_users": invalidated,
        }

    async def set_user_groups(call: ServiceCall) -> dict[str, Any]:
        user = await _find_user(hass, call.data["user_name"])
        if user is None:
            user = await hass.auth.async_create_user(
                call.data["user_name"],
                group_ids=list(call.data["group_ids"]),
                local_only=True,
            )
        else:
            if violation := _validate_managed_user(user):
                return violation
            await hass.auth.async_update_user(
                user, group_ids=list(call.data["group_ids"])
            )
        await _persist_auth(hass)
        return {"ok": True, "user": _sanitize_user(user)}

    async def flush_auth_store(call: ServiceCall) -> dict[str, Any]:
        await _persist_auth(hass)
        return {"ok": True}

    async def invalidate_user(call: ServiceCall) -> dict[str, Any]:
        user = await _find_user(hass, call.data["user_name"])
        if user is None:
            return {"ok": False, "error": "user_not_found"}
        if violation := _validate_managed_user(user):
            return violation
        user.invalidate_cache()
        return {"ok": True, "user": _sanitize_user(user)}

    async def snapshot(call: ServiceCall) -> dict[str, Any]:
        return await _auth_snapshot(hass)

    async def probe_d2_three_way(call: ServiceCall) -> dict[str, Any]:
        return await _probe_d2_three_way(hass)

    async def prepare_boot_rescue(call: ServiceCall) -> dict[str, Any]:
        return await _prepare_boot_rescue(hass)

    async def probe_system_users_gate(call: ServiceCall) -> dict[str, Any]:
        return await _probe_system_users_gate(hass)

    async def boot_rescue_status(call: ServiceCall) -> dict[str, Any]:
        return boot_rescue

    async def restore_user_groups(call: ServiceCall) -> dict[str, Any]:
        user = await _find_user(hass, call.data["user_name"])
        if user is None:
            return {"ok": False, "error": "user_not_found"}
        if violation := _validate_managed_user(user):
            return violation
        await hass.auth.async_update_user(user, group_ids=list(call.data["group_ids"]))
        await _persist_auth(hass)
        return {
            "ok": True,
            "scope": "user_group_ids_only",
            "user": _sanitize_user(user),
        }

    async def probe_check_entity(call: ServiceCall) -> dict[str, Any]:
        user = await _find_user(hass, call.data["user_name"])
        if user is None:
            return {"ok": False, "error": "user_not_found"}
        if violation := _validate_managed_user(user):
            return violation
        permission = (
            POLICY_CONTROL
            if call.data.get("permission", "read") == "control"
            else POLICY_READ
        )
        return {
            "ok": True,
            "entity_id": call.data["entity_id"],
            "permission": call.data.get("permission", "read"),
            "allowed": user.permissions.check_entity(
                call.data["entity_id"], permission
            ),
        }

    entity_policy_schema = vol.Schema(
        {
            vol.Required("group_id"): vol.All(str, _validate_managed_group_id),
            vol.Required("entity_id"): str,
            vol.Optional("read", default=True): bool,
            vol.Optional("control", default=False): bool,
        }
    )
    user_groups_schema = vol.Schema(
        {
            vol.Required("user_name"): vol.All(str, _validate_managed_user_name),
            vol.Required("group_ids"): [vol.All(str, _validate_managed_group_id)],
        }
    )

    service_specs = {
        "ensure_group": (
            ensure_group,
            vol.Schema(
                {
                    vol.Required("group_id"): vol.All(str, _validate_managed_group_id),
                    vol.Required("name"): str,
                    vol.Required("entity_id"): str,
                    vol.Optional("read", default=True): bool,
                    vol.Optional("control", default=False): bool,
                }
            ),
        ),
        "set_group_policy": (set_group_policy, entity_policy_schema),
        "set_user_groups": (set_user_groups, user_groups_schema),
        "flush_auth_store": (flush_auth_store, vol.Schema({})),
        "invalidate_user": (
            invalidate_user,
            vol.Schema({vol.Required("user_name"): str}),
        ),
        "snapshot": (snapshot, vol.Schema({})),
        "probe_d2_three_way": (probe_d2_three_way, vol.Schema({})),
        "prepare_boot_rescue": (prepare_boot_rescue, vol.Schema({})),
        "probe_system_users_gate": (probe_system_users_gate, vol.Schema({})),
        "boot_rescue_status": (boot_rescue_status, vol.Schema({})),
        "restore": (restore_user_groups, user_groups_schema),
        "probe_check_entity": (
            probe_check_entity,
            vol.Schema(
                {
                    vol.Required("user_name"): vol.All(
                        str, _validate_managed_user_name
                    ),
                    vol.Required("entity_id"): str,
                    vol.Optional("permission", default="read"): vol.In(
                        ["read", "control"]
                    ),
                }
            ),
        ),
    }

    for service, (handler, schema) in service_specs.items():
        hass.services.async_register(
            DOMAIN,
            service,
            handler,
            schema=schema,
            supports_response=SupportsResponse.ONLY,
        )

    hass.services.async_register(
        DOMAIN,
        "run_spike",
        run_spike,
        schema=vol.Schema(
            {vol.Required("phase"): vol.In(["pre_restart", "post_restart"])}
        ),
        supports_response=SupportsResponse.ONLY,
    )
    return True
