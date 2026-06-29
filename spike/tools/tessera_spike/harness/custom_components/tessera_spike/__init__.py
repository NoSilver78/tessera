"""Dev-only Tessera spike harness for HA 2026.6.4."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.auth import models
from homeassistant.auth.models import TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN
from homeassistant.auth.const import GROUP_ID_ADMIN, GROUP_ID_READ_ONLY, GROUP_ID_USER
from homeassistant.auth.permissions.const import (
    CAT_ENTITIES,
    POLICY_CONTROL,
    POLICY_READ,
)
from homeassistant.const import ATTR_ENTITY_ID, __version__ as HA_VERSION
from homeassistant.core import Context, HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.typing import ConfigType

DOMAIN = "tessera_spike"
RESULT_PATH = Path("/config/tessera_spike_result.json")
STATE_PATH = Path("/config/tessera_spike_state.json")
RESCUE_SNAPSHOT_PATH = Path("/config/tessera_spike_rescue_snapshot.json")
RESCUE_TRIGGER_PATH = Path("/config/tessera_spike_rescue_trigger.json")
RESCUE_RESULT_PATH = Path("/config/tessera_spike_rescue_result.json")
CORRUPT_TESSERA_CONFIG_PATH = Path("/config/.storage/tessera.config")
SETUP_EXCEPTION_TRIGGER_PATH = Path("/config/tessera_spike_force_setup_exception.json")
AUTH_STORE_PATH = Path("/config/.storage/auth")

ALLOWED_ENTITY = "input_boolean.tessera_allowed_light"
FORBIDDEN_ENTITY = "input_boolean.tessera_forbidden_light"
STATE_ONLY_ENTITY = "sensor.tessera_state_only"
GROUP_ID = "tessera:test"
GROUP_ID_EXTRA = "tessera:extra"
GROUP_ID_D2 = "tessera:d2"
GROUP_ID_HACS_ROLLBACK = "tessera:hacs_rollback"
GROUP_ID_LIFECYCLE = "tessera:lifecycle"
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
RELEVANT_CUSTOM_COMPONENT_INPUTS = (
    "browser_mod",
    "dreame_vacuum",
    "epex_spot",
    "gruenbeck_cloud",
    "solarman",
    "solcast_solar",
    "unifi_insights",
    "unifi_network_map",
)

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


def _entity_ids_from_body(body: Any) -> set[str]:
    """Collect entity_id strings from already sanitized HA response objects."""
    found: set[str] = set()
    if isinstance(body, dict):
        value = body.get("entity_id")
        if isinstance(value, str):
            found.add(value)
        for child in body.values():
            found.update(_entity_ids_from_body(child))
    elif isinstance(body, list):
        for child in body:
            found.update(_entity_ids_from_body(child))
    return found


def _body_summary(body: Any) -> dict[str, Any]:
    """Summarize response shape without persisting values beyond entity ids."""
    summary: dict[str, Any] = {"body_type": type(body).__name__}
    if isinstance(body, dict):
        summary["keys"] = sorted(str(key) for key in body)
    elif isinstance(body, list):
        summary["items"] = len(body)
    entity_ids = sorted(_entity_ids_from_body(body))
    if entity_ids:
        summary["entity_ids"] = entity_ids[:50]
        summary["entity_ids_truncated"] = len(entity_ids) > 50
    return summary


def _matrix_cell(
    *,
    transport: str,
    vector: str,
    status: int | str | None,
    body: Any = None,
    error: str | None = None,
    tested: bool = True,
    leak_hint: bool = False,
    baseline_present: bool | None = None,
) -> dict[str, Any]:
    """Return one leak/enforcement matrix cell with a conservative verdict."""
    entity_ids = _entity_ids_from_body(body)
    forbidden_seen = FORBIDDEN_ENTITY in entity_ids
    allowed_seen = ALLOWED_ENTITY in entity_ids
    if not tested:
        verdict = "NOT_TESTED"
    elif error:
        verdict = "ERROR"
    elif forbidden_seen or leak_hint:
        verdict = "LEAK"
    elif baseline_present is False:
        verdict = "NOT_VERIFIABLE"
    elif status in (401, 403, 404) or status == "blocked":
        verdict = "BLOCKED"
    else:
        verdict = "ALLOW"
    return {
        "transport": transport,
        "vector": vector,
        "status": status,
        "verdict": verdict,
        "allowed_entity_seen": allowed_seen,
        "forbidden_entity_seen": forbidden_seen,
        "leak_hint": leak_hint,
        "baseline_present": baseline_present,
        "body": _body_summary(body),
        "error": error,
    }


async def _ws_roundtrip(
    hass: HomeAssistant, access_token: str, commands: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Run Home Assistant WebSocket commands and return token-free results."""
    session = aiohttp_client.async_get_clientsession(hass)
    results: list[dict[str, Any]] = []
    async with session.ws_connect("http://127.0.0.1:8123/api/websocket") as ws:
        await ws.receive_json()
        await ws.send_json({"type": "auth", "access_token": access_token})
        auth = await ws.receive_json()
        if auth.get("type") != "auth_ok":
            return [
                {
                    "command_type": command.get("type"),
                    "success": False,
                    "error": "websocket_auth_failed",
                }
                for command in commands
            ]
        for idx, command in enumerate(commands, start=1):
            payload = {"id": idx, **command}
            await ws.send_json(payload)
            while True:
                msg = await ws.receive_json(timeout=20)
                if msg.get("id") == idx:
                    break
            results.append(
                {
                    "command_type": command.get("type"),
                    "success": msg.get("success"),
                    "message_type": msg.get("type"),
                    "error": msg.get("error"),
                    "result": msg.get("result"),
                }
            )
    return results


async def _probe_d3_ws(hass: HomeAssistant, access_token: str) -> dict[str, Any]:
    """Measure read/control consistency through Home Assistant WebSocket."""
    commands = [
        {"type": "get_states"},
        {
            "type": "call_service",
            "domain": "input_boolean",
            "service": "turn_on",
            "target": {"entity_id": ALLOWED_ENTITY},
        },
        {
            "type": "call_service",
            "domain": "input_boolean",
            "service": "turn_on",
            "target": {"entity_id": FORBIDDEN_ENTITY},
        },
    ]
    get_states, allowed_service, forbidden_service = await _ws_roundtrip(
        hass, access_token, commands
    )
    state_entities = _entity_ids_from_body(get_states.get("result"))
    return {
        "tested": True,
        "get_states_success": get_states.get("success"),
        "allowed_in_state_list": ALLOWED_ENTITY in state_entities,
        "forbidden_in_state_list": FORBIDDEN_ENTITY in state_entities,
        "service_allowed_success": allowed_service.get("success"),
        "service_allowed_error": allowed_service.get("error"),
        "service_forbidden_success": forbidden_service.get("success"),
        "service_forbidden_error": forbidden_service.get("error"),
    }


async def _probe_d7_ws_matrix(
    hass: HomeAssistant,
    access_token: str,
    *,
    admin_access_token: str | None = None,
) -> list[dict[str, Any]]:
    """Measure known read/leak vectors reachable through WebSocket."""
    now = "2026-06-29T00:00:00+00:00"
    commands = [
        {"type": "config/entity_registry/list"},
        {"type": "config/device_registry/list"},
        {"type": "config/area_registry/list"},
        {"type": "config/floor_registry/list"},
        {"type": "config/label_registry/list"},
        {"type": "config/category_registry/list", "scope": "entity"},
        {
            "type": "history/history_during_period",
            "start_time": now,
            "entity_ids": [FORBIDDEN_ENTITY],
            "minimal_response": True,
            "no_attributes": True,
        },
        {
            "type": "logbook/get_events",
            "start_time": now,
            "end_time": "2026-06-29T23:59:59+00:00",
            "entity_ids": [FORBIDDEN_ENTITY],
        },
    ]
    admin_responses = (
        await _ws_roundtrip(hass, admin_access_token, commands)
        if admin_access_token is not None
        else []
    )
    responses = await _ws_roundtrip(hass, access_token, commands)
    cells: list[dict[str, Any]] = []
    for index, (command, response) in enumerate(zip(commands, responses, strict=True)):
        admin_result = (
            admin_responses[index].get("result")
            if index < len(admin_responses)
            else None
        )
        vector = str(command["type"])
        baseline_present = None
        leak_hint = False
        if vector.startswith("config/"):
            baseline_present = bool(admin_result)
            leak_hint = bool(response.get("result"))
        elif "history" in vector or "logbook" in vector:
            baseline_present = bool(_entity_ids_from_body(admin_result))
            leak_hint = FORBIDDEN_ENTITY in _entity_ids_from_body(
                response.get("result")
            )
        cells.append(
            _matrix_cell(
                transport="ws",
                vector=vector,
                status="ok" if response.get("success") else "blocked",
                body=response.get("result"),
                error=(
                    str(response.get("error")) if not response.get("success") else None
                ),
                leak_hint=leak_hint,
                baseline_present=baseline_present,
            )
        )
    return cells


async def _probe_ws_render_template(
    hass: HomeAssistant, access_token: str, *, admin_access_token: str | None = None
) -> dict[str, Any]:
    """Measure the WebSocket render_template leak vector without storing values."""

    async def _run(token: str) -> dict[str, Any]:
        session = aiohttp_client.async_get_clientsession(hass)
        async with session.ws_connect("http://127.0.0.1:8123/api/websocket") as ws:
            await ws.receive_json()
            await ws.send_json({"type": "auth", "access_token": token})
            auth = await ws.receive_json()
            if auth.get("type") != "auth_ok":
                return {"success": False, "error": "websocket_auth_failed"}
            await ws.send_json(
                {
                    "id": 1,
                    "type": "render_template",
                    "template": "{{ states('input_boolean.tessera_forbidden_light') }}",
                }
            )
            initial = await ws.receive_json(timeout=20)
            event: dict[str, Any] | None = None
            if initial.get("success"):
                event = await ws.receive_json(timeout=20)
                await ws.send_json(
                    {"id": 2, "type": "unsubscribe_events", "subscription": 1}
                )
                await ws.receive_json(timeout=20)
            return {
                "success": initial.get("success"),
                "error": initial.get("error"),
                "event_received": event is not None,
                "event_keys": sorted(event.keys()) if isinstance(event, dict) else [],
                "result_present": (
                    isinstance(event, dict)
                    and isinstance(event.get("event"), dict)
                    and event["event"].get("result") not in (None, "")
                ),
            }

    result = await _run(access_token)
    admin_result = (
        await _run(admin_access_token) if admin_access_token is not None else {}
    )
    return _matrix_cell(
        transport="ws",
        vector="render_template",
        status="ok" if result.get("success") else "blocked",
        body={
            "event_received": result.get("event_received"),
            "event_keys": result.get("event_keys", []),
        },
        error=str(result.get("error")) if not result.get("success") else None,
        leak_hint=result.get("result_present") is True,
        baseline_present=(
            admin_result.get("result_present")
            if admin_access_token is not None
            else None
        ),
    )


async def _probe_d6_system_context(hass: HomeAssistant) -> dict[str, Any]:
    """Measure whether service calls with user_id=None bypass entity checks."""
    await hass.services.async_call(
        "input_boolean",
        "turn_off",
        {ATTR_ENTITY_ID: FORBIDDEN_ENTITY},
        blocking=True,
    )
    before = hass.states.get(FORBIDDEN_ENTITY)
    before_state = before.state if before is not None else None
    try:
        await hass.services.async_call(
            "input_boolean",
            "turn_on",
            {"entity_id": FORBIDDEN_ENTITY},
            blocking=True,
            context=Context(user_id=None),
        )
        error = None
    except Exception as err:  # pragma: no cover - spike evidence path
        error = type(err).__name__
    after = hass.states.get(FORBIDDEN_ENTITY)
    after_state = after.state if after is not None else None
    return {
        "tested": True,
        "context_user_id": None,
        "service": "input_boolean.turn_on",
        "entity_id": FORBIDDEN_ENTITY,
        "before_state": before_state,
        "after_state": after_state,
        "changed": before_state != after_state,
        "error": error,
        "verdict": (
            "ENFORCE_BYPASS"
            if error is None and before_state != after_state
            else "NO_EFFECT" if error is None else "BLOCKED"
        ),
        "not_tested_contexts": ["automation", "script", "assist"],
    }


async def _probe_d7_rest_matrix(
    hass: HomeAssistant,
    access_token: str,
    *,
    admin_access_token: str | None = None,
) -> list[dict[str, Any]]:
    """Measure known read/leak vectors reachable through REST."""
    template = await _http_json(
        hass,
        "POST",
        "/api/template",
        access_token,
        {"template": "{{ states('input_boolean.tessera_forbidden_light') }}"},
    )
    logbook = await _http_json(
        hass,
        "GET",
        f"/api/logbook?entity={FORBIDDEN_ENTITY}",
        access_token,
    )
    history = await _http_json(
        hass,
        "GET",
        f"/api/history/period?filter_entity_id={FORBIDDEN_ENTITY}&minimal_response",
        access_token,
    )
    admin_template = (
        await _http_json(
            hass,
            "POST",
            "/api/template",
            admin_access_token,
            {"template": "{{ states('input_boolean.tessera_forbidden_light') }}"},
        )
        if admin_access_token is not None
        else {"body": None}
    )
    admin_logbook = (
        await _http_json(
            hass,
            "GET",
            f"/api/logbook?entity={FORBIDDEN_ENTITY}",
            admin_access_token,
        )
        if admin_access_token is not None
        else {"body": None}
    )
    admin_history = (
        await _http_json(
            hass,
            "GET",
            f"/api/history/period?filter_entity_id={FORBIDDEN_ENTITY}&minimal_response",
            admin_access_token,
        )
        if admin_access_token is not None
        else {"body": None}
    )
    return [
        _matrix_cell(
            transport="rest",
            vector="/api/template",
            status=template["status"],
            body=template.get("body"),
            leak_hint=template["status"] == 200
            and template.get("body") not in (None, ""),
            baseline_present=admin_template.get("body") not in (None, ""),
        ),
        _matrix_cell(
            transport="rest",
            vector="/api/logbook",
            status=logbook["status"],
            body=logbook.get("body"),
            leak_hint=FORBIDDEN_ENTITY in _entity_ids_from_body(logbook.get("body")),
            baseline_present=FORBIDDEN_ENTITY
            in _entity_ids_from_body(admin_logbook.get("body")),
        ),
        _matrix_cell(
            transport="rest",
            vector="/api/history/period",
            status=history["status"],
            body=history.get("body"),
            leak_hint=FORBIDDEN_ENTITY in _entity_ids_from_body(history.get("body")),
            baseline_present=FORBIDDEN_ENTITY
            in _entity_ids_from_body(admin_history.get("body")),
        ),
    ]


async def _make_llat_access_token(
    hass: HomeAssistant, user: models.User, client_name: str
) -> tuple[str, models.RefreshToken]:
    """Create a real HA long-lived token object and an access token for it."""
    token = await hass.auth.async_create_refresh_token(
        user,
        client_id="http://localhost:8124/",
        client_name=client_name,
        token_type=TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN,
        access_token_expiration=timedelta(days=3650),
    )
    access_token = hass.auth.async_create_access_token(token, "127.0.0.1")
    return access_token, token


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


async def _active_owner_user(hass: HomeAssistant) -> models.User | None:
    users = await hass.auth.async_get_users()
    return next((user for user in users if user.is_owner and user.is_active), None)


async def _auth_operate_probe(
    hass: HomeAssistant, user: models.User, client_name: str
) -> dict[str, Any]:
    """Create a temporary token, call one safe service, then revoke the token."""
    access_token, refresh_token = await _make_access_token(hass, user, client_name)
    response = await _http_json(
        hass,
        "POST",
        "/api/services/input_boolean/turn_on",
        access_token,
        {"entity_id": ALLOWED_ENTITY},
    )
    hass.auth.async_remove_refresh_token(refresh_token)
    await _persist_auth(hass)
    return {
        "attempted": True,
        "user_name": user.name,
        "is_owner": user.is_owner,
        "is_admin": user.is_admin,
        "status": response["status"],
        "authenticated_and_operated": response["status"] == 200,
        "token_values_redacted": True,
    }


async def _run_boot_rescue_if_requested(hass: HomeAssistant) -> dict[str, Any]:
    """Restore managed user groups during HA boot when the rescue trigger exists."""
    if not RESCUE_TRIGGER_PATH.exists():
        return {"requested": False}

    snapshot = await _read_json(hass, RESCUE_SNAPSHOT_PATH)
    trigger = await _read_json(hass, RESCUE_TRIGGER_PATH)
    snapshot_run_id = snapshot.get("run_id")
    trigger_run_id = trigger.get("run_id")
    setup_exception_requested = SETUP_EXCEPTION_TRIGGER_PATH.exists()
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
        "run_id": snapshot_run_id,
        "trigger_run_id": trigger_run_id,
        "run_id_matches": bool(snapshot_run_id and snapshot_run_id == trigger_run_id),
        "corrupt_tessera_store_path": str(CORRUPT_TESSERA_CONFIG_PATH),
        "corrupt_tessera_store_parse_failed": corrupt_store_parse_failed,
        "corrupt_tessera_store_error": corrupt_store_error,
        "restored_users": [],
        "touched_user_names": [],
        "errors": [],
        "used_public_async_update_user": True,
        "setup_exception_requested": setup_exception_requested,
        "setup_exception_trigger_path": str(SETUP_EXCEPTION_TRIGGER_PATH),
    }
    if not result["run_id_matches"]:
        result["errors"].append("run_id_mismatch")
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
        before_group_ids = sorted(group.id for group in user.groups)
        await hass.auth.async_update_user(user, group_ids=list(validated_group_ids))
        actual_groups = [group.id for group in user.groups]
        exact_match = set(actual_groups) == set(validated_group_ids)
        if not exact_match:
            result["errors"].append(f"group_mismatch:{name}")
        result["restored_users"].append(
            {
                "name": name,
                "expected_group_ids": sorted(validated_group_ids),
                "before_group_ids": before_group_ids,
                "actual_group_ids": sorted(actual_groups),
                "exact_match": exact_match,
            }
        )
        result["touched_user_names"].append(name)

    await _persist_auth(hass)
    expected_names = {
        item.get("name")
        for item in snapshot.get("users", [])
        if isinstance(item.get("name"), str)
    }
    touched_names = set(result["touched_user_names"])
    restored_exact = (
        all(item.get("exact_match") is True for item in result["restored_users"])
        and touched_names == expected_names
    )
    result["reread_state_matches_intended"] = restored_exact
    result["touched_only_snapshot_managed_users"] = touched_names == expected_names
    result["owner_system_unmanaged_never_touched"] = True
    result["ok"] = (
        result["run_id_matches"]
        and corrupt_store_parse_failed
        and restored_exact
        and not result["errors"]
    )
    result["rescue_restore_namespace_guarded"] = True
    result["managed_group_replace_drift_injected"] = (
        snapshot.get("managed_replace_demotion_injected") is True
    )
    result["boot_rescue_corruption_tested"] = bool(
        result["managed_group_replace_drift_injected"] and corrupt_store_parse_failed
    )
    result["no_admin_lockout"] = None
    result["rescue_independent_of_healthy_tessera"] = False
    result["d5_truthfulness"] = (
        "PENDING: startup restore ran; post-boot auth/operate and setup-exception "
        "independence are measured after HA is reachable"
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
    """Prepare measured D5 startup restore against a managed REPLACE demotion."""
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
        hass, TEST_RESCUE_USER_NAME, [GROUP_ID, GROUP_ID_EXTRA]
    )
    expected_groups = sorted(group.id for group in user.groups)
    await hass.auth.async_update_user(user, group_ids=[GROUP_ID_EXTRA])
    drifted_groups = sorted(group.id for group in user.groups)
    owner_before = await _active_owner_user(hass)
    admin_control = await _ensure_test_user(hass, TEST_ADMIN_NAME, [GROUP_ID_ADMIN])
    run_id = uuid.uuid4().hex

    snapshot = {
        "run_id": run_id,
        "users": [{"name": TEST_RESCUE_USER_NAME, "group_ids": expected_groups}],
        "scope": "managed_user_group_ids_only",
        "uses_public_async_update_user_on_boot": True,
        "managed_replace_demotion_injected": GROUP_ID not in drifted_groups,
        "setup_exception_after_rescue_requested": True,
        "owner_control_user_before": (
            _sanitize_user(owner_before) if owner_before is not None else None
        ),
        "admin_control_user_before": _sanitize_user(admin_control),
    }
    await _write_json(hass, RESCUE_SNAPSHOT_PATH, snapshot)
    await _write_json(hass, RESCUE_TRIGGER_PATH, {"requested": True, "run_id": run_id})
    await _write_json(
        hass, SETUP_EXCEPTION_TRIGGER_PATH, {"requested": True, "run_id": run_id}
    )
    await hass.async_add_executor_job(
        CORRUPT_TESSERA_CONFIG_PATH.write_text,
        '{"intentionally_corrupt": ',
    )
    await _persist_auth(hass)

    return {
        "prepared": True,
        "run_id": run_id,
        "user_name": TEST_RESCUE_USER_NAME,
        "expected_groups": expected_groups,
        "drifted_groups_before_restart": drifted_groups,
        "snapshot_path": str(RESCUE_SNAPSHOT_PATH),
        "trigger_path": str(RESCUE_TRIGGER_PATH),
        "setup_exception_trigger_path": str(SETUP_EXCEPTION_TRIGGER_PATH),
        "corrupt_tessera_store_path": str(CORRUPT_TESSERA_CONFIG_PATH),
        "auth_store_path": str(AUTH_STORE_PATH),
        "managed_group_replace_drift_injected": snapshot[
            "managed_replace_demotion_injected"
        ],
        "boot_rescue_corruption_tested": None,
        "no_admin_lockout": None,
        "verdict": "PARTIAL",
        "partial_reason": (
            "D5 requires post-restart rescue, setup-exception independence, "
            "reread, and owner/admin operate probes"
        ),
    }


async def _probe_d5_post_boot(
    hass: HomeAssistant, rescue_result: dict[str, Any]
) -> dict[str, Any]:
    """Measure D5 post-boot reread and no-admin-lockout conditions."""
    if not rescue_result.get("requested"):
        return rescue_result

    snapshot = await _read_json(hass, RESCUE_SNAPSHOT_PATH)
    reread_results: list[dict[str, Any]] = []
    for item in snapshot.get("users", []):
        name = item.get("name")
        expected = item.get("group_ids")
        if not isinstance(name, str) or not isinstance(expected, list):
            continue
        user = await _find_user(hass, name)
        actual = sorted(group.id for group in user.groups) if user is not None else []
        reread_results.append(
            {
                "name": name,
                "expected_group_ids": sorted(expected),
                "actual_group_ids": actual,
                "exact_match": set(actual) == set(expected),
            }
        )

    owner = await _active_owner_user(hass)
    admin = await _find_user(hass, TEST_ADMIN_NAME)
    owner_probe = (
        await _auth_operate_probe(hass, owner, "tessera-d5-owner-lockout-probe")
        if owner is not None
        else {"attempted": False, "error": "owner_not_found"}
    )
    admin_probe = (
        await _auth_operate_probe(hass, admin, "tessera-d5-admin-lockout-probe")
        if admin is not None
        else {"attempted": False, "error": "admin_not_found"}
    )

    reread_ok = bool(reread_results) and all(
        item["exact_match"] for item in reread_results
    )
    owner_before = snapshot.get("owner_control_user_before") or {}
    admin_before = snapshot.get("admin_control_user_before") or {}
    owner_after = _sanitize_user(owner) if owner is not None else {}
    admin_after = _sanitize_user(admin) if admin is not None else {}
    owner_unchanged = {
        key: owner_after.get(key) == owner_before.get(key)
        for key in ("name", "is_owner", "is_admin", "is_active", "groups")
    }
    admin_unchanged = {
        key: admin_after.get(key) == admin_before.get(key)
        for key in ("name", "is_owner", "is_admin", "is_active", "groups")
    }
    no_admin_lockout = (
        owner_probe.get("authenticated_and_operated") is True
        and admin_probe.get("authenticated_and_operated") is True
    )
    no_forbidden_touch = (
        rescue_result.get("owner_system_unmanaged_never_touched") is True
        and all(owner_unchanged.values())
        and all(admin_unchanged.values())
    )
    passed = (
        rescue_result.get("requested") is True
        and rescue_result.get("snapshot_present") is True
        and rescue_result.get("run_id_matches") is True
        and rescue_result.get("managed_group_replace_drift_injected") is True
        and rescue_result.get("boot_rescue_corruption_tested") is True
        and rescue_result.get("rescue_independent_of_healthy_tessera") is True
        and reread_ok
        and no_admin_lockout
        and no_forbidden_touch
    )

    rescue_result.update(
        {
            "post_boot_measured": True,
            "reread_results": reread_results,
            "reread_state_matches_intended": reread_ok,
            "owner_before_after_unchanged": owner_unchanged,
            "admin_before_after_unchanged": admin_unchanged,
            "owner_operate_probe": owner_probe,
            "admin_operate_probe": admin_probe,
            "no_admin_lockout": no_admin_lockout,
            "owner_system_unmanaged_never_touched": no_forbidden_touch,
            "verdict": "PASS" if passed else "PARTIAL",
            "d5_truthfulness": (
                "PASS: managed REPLACE demotion was rescued before forced setup "
                "exception; reread and owner/admin operate probes passed"
                if passed
                else "PARTIAL: one or more measured D5 rescue conditions failed"
            ),
        }
    )
    await _write_json(hass, RESCUE_RESULT_PATH, rescue_result)
    return rescue_result


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


def _stable_json(data: Any) -> str:
    """Return deterministic JSON for equality fingerprints."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


async def _auth_fingerprint(hass: HomeAssistant) -> dict[str, Any]:
    """Return a secret-free auth fingerprint for lifecycle probes."""
    users = await hass.auth.async_get_users()
    groups = await hass.auth._store.async_get_groups()  # noqa: SLF001
    store = hass.auth._store  # noqa: SLF001
    raw_store_data = store._data_to_save()  # noqa: SLF001
    store_data = raw_store_data.get("data", raw_store_data)
    managed_group_ids = sorted(
        group.id for group in groups if group.id.startswith(MANAGED_GROUP_PREFIX)
    )
    return {
        "ha_version_actual": HA_VERSION,
        "auth_store_counts": {
            "users": len(store_data.get("users", [])),
            "groups": len(store_data.get("groups", [])),
            "credentials": len(store_data.get("credentials", [])),
            "refresh_tokens": len(store_data.get("refresh_tokens", [])),
        },
        "group_summaries": sorted(
            [
                {
                    "id": group.id,
                    "name": group.name,
                    "system_generated": group.system_generated,
                    "has_policy": bool(group.policy),
                    "policy_json": _stable_json(group.policy) if group.policy else None,
                }
                for group in groups
            ],
            key=lambda item: item["id"],
        ),
        "user_summaries": sorted(
            [
                {
                    "name": user.name,
                    "groups": sorted(group.id for group in user.groups),
                    "is_active": user.is_active,
                    "is_admin": user.is_admin,
                    "is_owner": user.is_owner,
                    "system_generated": user.system_generated,
                    "credentials_count": len(user.credentials),
                    "refresh_token_classes": sorted(
                        {token.token_type for token in user.refresh_tokens.values()}
                    ),
                    "refresh_token_count": len(user.refresh_tokens),
                }
                for user in users
            ],
            key=lambda item: str(item["name"]),
        ),
        "managed_groups": sorted(
            [
                {
                    "id": group.id,
                    "name": group.name,
                    "has_policy": bool(group.policy),
                    "policy_json": _stable_json(group.policy) if group.policy else None,
                }
                for group in groups
                if group.id in managed_group_ids
            ],
            key=lambda item: item["id"],
        ),
        "managed_users": sorted(
            [
                {
                    "name": user.name,
                    "groups": sorted(group.id for group in user.groups),
                    "is_active": user.is_active,
                    "is_admin": user.is_admin,
                    "is_owner": user.is_owner,
                }
                for user in users
                if user.name and user.name.startswith(MANAGED_USER_PREFIX)
            ],
            key=lambda item: str(item["name"]),
        ),
        "owner_admin_users": sorted(
            [
                {
                    "name": user.name,
                    "is_active": user.is_active,
                    "is_admin": user.is_admin,
                    "is_owner": user.is_owner,
                    "groups": sorted(group.id for group in user.groups),
                }
                for user in users
                if user.is_owner or user.is_admin
            ],
            key=lambda item: str(item["name"]),
        ),
    }


async def _owner_admin_lockout_probe(hass: HomeAssistant) -> dict[str, Any]:
    """Verify at least one active owner/admin remains available."""
    users = await hass.auth.async_get_users()
    token_probe: dict[str, Any] = {"attempted": False}
    active_owner_or_admin = sorted(
        [
            {
                "name": user.name,
                "is_owner": user.is_owner,
                "is_admin": user.is_admin,
                "is_active": user.is_active,
                "groups": sorted(group.id for group in user.groups),
            }
            for user in users
            if user.is_active and (user.is_owner or user.is_admin)
        ],
        key=lambda item: str(item["name"]),
    )
    admin_user = next(
        (user for user in users if user.is_active and (user.is_owner or user.is_admin)),
        None,
    )
    if admin_user is not None:
        access_token, refresh_token = await _make_access_token(
            hass, admin_user, "tessera-spike-lockout-probe"
        )
        response = await _http_json(hass, "GET", "/api/config", access_token)
        hass.auth.async_remove_refresh_token(refresh_token)
        await _persist_auth(hass)
        token_probe = {
            "attempted": True,
            "status": response["status"],
            "authenticated": response["status"] == 200,
            "token_values_redacted": True,
        }
    return {
        "checked": True,
        "no_admin_lockout": bool(active_owner_or_admin)
        and token_probe.get("authenticated") is True,
        "active_owner_or_admin_users": active_owner_or_admin,
        "authenticated_admin_request": token_probe,
    }


async def _remove_managed_group_if_absent_before(
    hass: HomeAssistant, group_id: str, before_fingerprint: dict[str, Any]
) -> None:
    """Remove a temporary managed group when the pre-snapshot did not contain it."""
    before_group_ids = {
        group["id"] for group in before_fingerprint.get("managed_groups", [])
    }
    if group_id in before_group_ids:
        return
    store = hass.auth._store  # noqa: SLF001
    await store.async_get_groups()
    store._groups.pop(group_id, None)  # noqa: SLF001
    await _persist_auth(hass)


async def _request_lifecycle_transition(
    hass: HomeAssistant,
    *,
    mode: str,
    user: models.User,
    original_groups: list[str],
    group_id: str,
    entity_id: str,
    simulated_ha_version: str | None = None,
) -> dict[str, Any]:
    """Execute the spike lifecycle transition path used by D11 and D15."""
    before = await _auth_fingerprint(hass)
    actual_version = simulated_ha_version or HA_VERSION
    preview = {
        "group_id": group_id,
        "entity_id": entity_id,
        "read": True,
        "control": True,
    }
    if mode == "off":
        after = await _auth_fingerprint(hass)
        return {
            "requested_mode": mode,
            "effective_mode": "off",
            "ha_version_actual": actual_version,
            "ha_version_supported": HA_VERSION,
            "native_write_attempted": False,
            "native_write_blocked": False,
            "auth_fingerprint_before": before,
            "auth_fingerprint_after": after,
            "native_write_observed": _stable_json(before) != _stable_json(after),
        }
    if mode == "monitor":
        after = await _auth_fingerprint(hass)
        return {
            "requested_mode": mode,
            "effective_mode": "monitor",
            "ha_version_actual": actual_version,
            "ha_version_supported": HA_VERSION,
            "preview": preview,
            "native_write_attempted": False,
            "native_write_blocked": False,
            "auth_fingerprint_before": before,
            "auth_fingerprint_after": after,
            "native_write_observed": _stable_json(before) != _stable_json(after),
        }
    if mode == "enforce" and actual_version != HA_VERSION:
        issue_id = "unsupported_version_enforce_refused"
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            is_persistent=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key=issue_id,
            translation_placeholders={
                "actual": actual_version,
                "supported": HA_VERSION,
            },
        )
        after = await _auth_fingerprint(hass)
        return {
            "requested_mode": mode,
            "effective_mode": "monitor",
            "enforce_requested": True,
            "ha_version_actual": actual_version,
            "ha_version_supported": HA_VERSION,
            "version_mismatch_detected": True,
            "native_write_attempted": False,
            "native_write_blocked": True,
            "native_write_call_count": 0,
            "native_write_refused_before_call": True,
            "repair_issue_created": True,
            "repair_issue_id": issue_id,
            "auth_fingerprint_before": before,
            "auth_fingerprint_after": after,
            "auth_fingerprint_unchanged": _stable_json(before) == _stable_json(after),
        }
    if mode == "enforce":
        await _ensure_group(
            hass,
            group_id,
            "Tessera Lifecycle",
            _policy(entity_id, read=True, control=True),
        )
        full_superset = sorted({*original_groups, group_id})
        await hass.auth.async_update_user(user, group_ids=full_superset)
        user.invalidate_cache()
        await _persist_auth(hass)
        after = await _auth_fingerprint(hass)
        user_groups_after = sorted(group.id for group in user.groups)
        return {
            "requested_mode": mode,
            "effective_mode": "enforce",
            "ha_version_actual": actual_version,
            "ha_version_supported": HA_VERSION,
            "native_write_attempted": True,
            "native_write_blocked": False,
            "full_group_superset": full_superset,
            "original_groups": original_groups,
            "user_groups_after_enforce": user_groups_after,
            "full_superset_written": user_groups_after == full_superset,
            "permission_probe": {
                "forbidden_read": user.permissions.check_entity(entity_id, POLICY_READ),
                "forbidden_control": user.permissions.check_entity(
                    entity_id, POLICY_CONTROL
                ),
            },
            "auth_fingerprint_before": before,
            "auth_fingerprint_after": after,
        }
    return {
        "requested_mode": mode,
        "effective_mode": "off",
        "native_write_attempted": False,
        "native_write_blocked": True,
        "error": "unknown_mode",
    }


async def _probe_d11_version_gate(hass: HomeAssistant) -> dict[str, Any]:
    """Simulate unsupported HA version and prove enforce is refused before writes."""
    user = await _find_user(hass, TEST_USER_NAME)
    if user is None:
        return {
            "tested": True,
            "status": "FAIL",
            "reason": "managed test user missing; cannot measure version gate",
        }
    simulated_unsupported_version = "9999.0.0"
    original_groups = sorted(group.id for group in user.groups)
    transition = await _request_lifecycle_transition(
        hass,
        mode="enforce",
        user=user,
        original_groups=original_groups,
        group_id=GROUP_ID_LIFECYCLE,
        entity_id=FORBIDDEN_ENTITY,
        simulated_ha_version=simulated_unsupported_version,
    )
    unchanged = transition.get("auth_fingerprint_unchanged") is True
    passed = (
        transition.get("version_mismatch_detected") is True
        and transition.get("enforce_requested") is True
        and transition.get("native_write_attempted") is False
        and transition.get("native_write_blocked") is True
        and transition.get("native_write_call_count") == 0
        and transition.get("native_write_refused_before_call") is True
        and transition.get("effective_mode") in {"monitor", "off"}
        and transition.get("repair_issue_created") is True
        and unchanged
    )
    lockout = await _owner_admin_lockout_probe(hass)
    return {
        "tested": True,
        "status": "PASS" if passed and lockout["no_admin_lockout"] else "PARTIAL",
        "reason": "unsupported-version enforce request is routed through lifecycle gate and refused before native auth write",
        "ha_version_actual": HA_VERSION,
        "ha_version_supported": HA_VERSION,
        "ha_version_simulated": simulated_unsupported_version,
        "simulation_method": "in-process lifecycle enforce request with simulated unsupported version",
        "requested_mode": transition.get("requested_mode"),
        "effective_mode": transition.get("effective_mode"),
        "enforce_requested": transition.get("enforce_requested"),
        "native_write_attempted": transition.get("native_write_attempted"),
        "native_write_blocked": transition.get("native_write_blocked"),
        "native_write_call_count": transition.get("native_write_call_count"),
        "native_write_refused_before_call": transition.get(
            "native_write_refused_before_call"
        ),
        "repair_issue_created": transition.get("repair_issue_created"),
        "repair_issue_id": transition.get("repair_issue_id"),
        "auth_fingerprint_before": transition.get("auth_fingerprint_before"),
        "auth_fingerprint_after": transition.get("auth_fingerprint_after"),
        "auth_fingerprint_unchanged": unchanged,
        "owner_admin_lockout_probe": lockout,
        "transition": transition,
        "file_line": "spike/tools/tessera_spike/harness/custom_components/tessera_spike/__init__.py:_probe_d11_version_gate",
    }


async def _probe_d13_hacs_rollback(hass: HomeAssistant) -> dict[str, Any]:
    """Simulate managed-policy update and rollback without leaving native drift."""
    before = await _auth_fingerprint(hass)
    user = await _find_user(hass, TEST_USER_NAME)
    if user is None:
        return {
            "tested": True,
            "status": "FAIL",
            "reason": "managed test user missing; cannot measure rollback",
        }
    original_groups = sorted(group.id for group in user.groups)
    await _ensure_group(
        hass,
        GROUP_ID_HACS_ROLLBACK,
        "Tessera HACS Rollback",
        _policy(FORBIDDEN_ENTITY, read=True, control=True),
    )
    update_groups = sorted({*original_groups, GROUP_ID_HACS_ROLLBACK})
    await hass.auth.async_update_user(user, group_ids=update_groups)
    user.invalidate_cache()
    await _persist_auth(hass)
    after_update = await _auth_fingerprint(hass)

    await hass.auth.async_update_user(user, group_ids=original_groups)
    user.invalidate_cache()
    await _remove_managed_group_if_absent_before(hass, GROUP_ID_HACS_ROLLBACK, before)
    await _persist_auth(hass)
    after_rollback = await _auth_fingerprint(hass)
    updated = _stable_json(before) != _stable_json(after_update)
    restored = _stable_json(before) == _stable_json(after_rollback)
    lockout = await _owner_admin_lockout_probe(hass)
    return {
        "tested": True,
        "status": (
            "PASS"
            if updated and restored and lockout["no_admin_lockout"]
            else "PARTIAL"
        ),
        "reason": "simulated component update writes managed policy, rollback restores exact auth fingerprint",
        "simulation_method": "in-process HACS update/downgrade simulation; no real HACS package install",
        "component_version_before": "welle-e-sim-1",
        "component_version_update": "welle-e-sim-2",
        "component_version_after_rollback": "welle-e-sim-1",
        "native_write_attempted": True,
        "native_write_blocked": False,
        "auth_fingerprint_before": before,
        "auth_fingerprint_after_update": after_update,
        "auth_fingerprint_changed_by_update": updated,
        "auth_fingerprint_after": after_rollback,
        "rollback_restored_exact_fingerprint": restored,
        "managed_groups_before": before.get("managed_groups", []),
        "managed_groups_after": after_rollback.get("managed_groups", []),
        "managed_users_before": before.get("managed_users", []),
        "managed_users_after": after_rollback.get("managed_users", []),
        "owner_admin_lockout_probe": lockout,
        "restore_probe": {
            "user_name": TEST_USER_NAME,
            "original_groups": original_groups,
            "update_groups": update_groups,
            "restored_groups": sorted(group.id for group in user.groups),
        },
        "file_line": "spike/tools/tessera_spike/harness/custom_components/tessera_spike/__init__.py:_probe_d13_hacs_rollback",
    }


async def _probe_d15_lifecycle(hass: HomeAssistant) -> dict[str, Any]:
    """Measure off -> monitor -> enforce -> restore with full-superset writes."""
    before = await _auth_fingerprint(hass)
    user = await _find_user(hass, TEST_USER_NAME)
    if user is None:
        return {
            "tested": True,
            "status": "FAIL",
            "reason": "managed test user missing; cannot measure lifecycle",
        }
    original_groups = sorted(group.id for group in user.groups)
    off_transition = await _request_lifecycle_transition(
        hass,
        mode="off",
        user=user,
        original_groups=original_groups,
        group_id=GROUP_ID_LIFECYCLE,
        entity_id=FORBIDDEN_ENTITY,
    )
    monitor_transition = await _request_lifecycle_transition(
        hass,
        mode="monitor",
        user=user,
        original_groups=original_groups,
        group_id=GROUP_ID_LIFECYCLE,
        entity_id=FORBIDDEN_ENTITY,
    )
    enforce_transition = await _request_lifecycle_transition(
        hass,
        mode="enforce",
        user=user,
        original_groups=original_groups,
        group_id=GROUP_ID_LIFECYCLE,
        entity_id=FORBIDDEN_ENTITY,
    )

    await hass.auth.async_update_user(user, group_ids=original_groups)
    user.invalidate_cache()
    await _remove_managed_group_if_absent_before(hass, GROUP_ID_LIFECYCLE, before)
    await _persist_auth(hass)
    restore_after = await _auth_fingerprint(hass)
    off_wrote = off_transition.get("native_write_observed") is True
    monitor_wrote = monitor_transition.get("native_write_observed") is True
    restored = _stable_json(before) == _stable_json(restore_after)
    lockout = await _owner_admin_lockout_probe(hass)
    enforce_permission_probe = enforce_transition.get("permission_probe", {})
    passed = (
        not off_wrote
        and not monitor_wrote
        and enforce_transition.get("native_write_attempted") is True
        and enforce_transition.get("native_write_blocked") is False
        and enforce_transition.get("full_superset_written") is True
        and enforce_permission_probe.get("forbidden_read") is True
        and enforce_permission_probe.get("forbidden_control") is True
        and restored
        and lockout["no_admin_lockout"]
    )
    return {
        "tested": True,
        "status": "PASS" if passed else "PARTIAL",
        "reason": "measured off and monitor no-write, enforce full-superset native write, restore exact fingerprint",
        "simulation_method": "in-process native auth policy lifecycle",
        "transitions": ["off", "monitor", "enforce", "restore"],
        "off": {
            "transition": off_transition,
            "native_write_observed": off_wrote,
            "effective_mode": "off",
        },
        "monitor": {
            "transition": monitor_transition,
            "native_write_observed": monitor_wrote,
            "effective_mode": "monitor",
            "preview": monitor_transition.get("preview"),
        },
        "enforce": {
            "transition": enforce_transition,
            "native_write_attempted": enforce_transition.get("native_write_attempted"),
            "native_write_blocked": enforce_transition.get("native_write_blocked"),
            "effective_mode": "enforce",
            "full_group_superset": enforce_transition.get("full_group_superset"),
            "original_groups": original_groups,
            "user_groups_after_enforce": enforce_transition.get(
                "user_groups_after_enforce"
            ),
            "full_superset_written": enforce_transition.get("full_superset_written"),
            "permission_probe": enforce_permission_probe,
        },
        "restore": {
            "native_write_attempted": True,
            "effective_mode": "restore",
            "restored_exact_fingerprint": restored,
            "restored_groups": sorted(group.id for group in user.groups),
        },
        "auth_fingerprint_before": before,
        "auth_fingerprint_after_off": off_transition.get("auth_fingerprint_after"),
        "auth_fingerprint_after_monitor": monitor_transition.get(
            "auth_fingerprint_after"
        ),
        "auth_fingerprint_after_enforce": enforce_transition.get(
            "auth_fingerprint_after"
        ),
        "auth_fingerprint_after": restore_after,
        "owner_admin_lockout_probe": lockout,
        "file_line": "spike/tools/tessera_spike/harness/custom_components/tessera_spike/__init__.py:_probe_d15_lifecycle",
    }


def _registered_service_names(hass: HomeAssistant, domain: str) -> list[str]:
    """Return registered service names for a domain."""
    domain_services = hass.services.async_services().get(domain, {})
    return sorted(str(service) for service in domain_services)


def _static_surface_markers(component_path: Path) -> dict[str, Any]:
    """Classify static surface markers for a dev-container component."""
    files = [
        path
        for path in component_path.rglob("*")
        if path.is_file() and path.suffix in {".py", ".yaml", ".json"}
    ]
    services_yaml = component_path / "services.yaml"
    markers = {
        "services_yaml": services_yaml.exists(),
        "python_files": sum(1 for path in files if path.suffix == ".py"),
        "registers_services": False,
        "http_or_panel_marker": False,
        "websocket_marker": False,
    }
    for path in files:
        try:
            text = path.read_text(errors="ignore")
        except OSError:
            continue
        markers["registers_services"] = markers["registers_services"] or (
            "async_register" in text and "services" in text
        )
        markers["http_or_panel_marker"] = markers["http_or_panel_marker"] or any(
            item in text for item in ("HomeAssistantView", "register_view", "panel")
        )
        markers["websocket_marker"] = markers["websocket_marker"] or any(
            item in text for item in ("websocket_command", "async_register_command")
        )
    return markers


def _custom_component_static_inventory(config_path: str) -> dict[str, dict[str, Any]]:
    """Return static dev-container custom-component inventory off the event loop."""
    custom_dir = Path(config_path)
    if not custom_dir.exists():
        return {}
    inventory: dict[str, dict[str, Any]] = {}
    for path in custom_dir.iterdir():
        if path.is_dir() and not path.name.startswith("__"):
            inventory[path.name] = {
                "path": str(path),
                "static_findings": _static_surface_markers(path),
            }
    return inventory


async def _classify_custom_components(hass: HomeAssistant) -> dict[str, Any]:
    """Build the D9 fail-closed custom-component classification matrix."""
    dev_components = await hass.async_add_executor_job(
        _custom_component_static_inventory,
        hass.config.path("custom_components"),
    )
    components: list[dict[str, Any]] = []

    for component in RELEVANT_CUSTOM_COMPONENT_INPUTS:
        installed_component = dev_components.get(component)
        static_findings = (
            installed_component["static_findings"]
            if installed_component is not None
            else {
                "services_yaml": None,
                "registers_services": None,
                "http_or_panel_marker": None,
                "websocket_marker": None,
            }
        )
        runtime_services = _registered_service_names(hass, component)
        runtime_verified = bool(installed_component and runtime_services)
        verdict = "UNKNOWN_BLOCK_ENFORCE"
        reason = (
            "input component is not installed in ha-tessera-dev, so no runtime "
            "ALLOW is possible"
            if installed_component is None
            else "runtime service/user-context behavior is not fully verified"
        )
        components.append(
            {
                "component_id": component,
                "component": component,
                "input_source": "historical read-only custom_components review; no /Volumes/config scan in this run",
                "input_timestamp": "2026-06-29",
                "installed_in_dev": installed_component is not None,
                "runtime_services": runtime_services,
                "runtime_verified": runtime_verified,
                "surfaces": {
                    "services": runtime_services,
                    "services_yaml": static_findings.get("services_yaml"),
                    "http_or_panel": static_findings.get("http_or_panel_marker"),
                    "websocket": static_findings.get("websocket_marker"),
                },
                "service_type": "unknown",
                "actor": "restricted_non_admin/admin/system not runtime-probed for this input",
                "context_user_id": "unknown",
                "permission_path": "unknown",
                "allowed_entity_result": None,
                "forbidden_entity_result": None,
                "response_leak": "unknown",
                "static_findings": static_findings,
                "verdict": verdict,
                "reason": reason,
                "confidence": "high-fail-closed",
                "required_followup": "install same component/version in ha-tessera-dev and run service/http/ws/user-context probes before any ALLOW",
                "file_line": "exchange/2026-06-29/tessera-welle-d-task-claude-2026-06-29.md:10",
            }
        )

    dev_runtime_components: list[dict[str, Any]] = []
    for component, static_inventory in sorted(dev_components.items()):
        services = _registered_service_names(hass, component)
        static_findings = static_inventory["static_findings"]
        if component == DOMAIN:
            verdict = "TIER-2"
            reason = (
                "dev harness exposes non-entity services and is explicitly not "
                "a production allow candidate"
            )
        elif services or any(
            static_findings[key]
            for key in (
                "services_yaml",
                "registers_services",
                "http_or_panel_marker",
                "websocket_marker",
            )
        ):
            verdict = "UNKNOWN_BLOCK_ENFORCE"
            reason = "dev component has enforcement-relevant surfaces without component-specific runtime proof"
        else:
            verdict = "UNKNOWN_BLOCK_ENFORCE"
            reason = (
                "dev component has no observed services/http/ws/panel surface, "
                "but D9 does not emit static ALLOW without component/version "
                "runtime proof"
            )
        dev_runtime_components.append(
            {
                "component_id": component,
                "component": component,
                "input_source": "ha-tessera-dev /config/custom_components runtime inventory",
                "input_timestamp": "2026-06-29",
                "installed_in_dev": True,
                "runtime_services": services,
                "runtime_verified": True,
                "surfaces": {
                    "services": services,
                    "services_yaml": static_findings.get("services_yaml"),
                    "http_or_panel": static_findings.get("http_or_panel_marker"),
                    "websocket": static_findings.get("websocket_marker"),
                },
                "service_type": "non-entity/mixed" if services else "none-observed",
                "actor": "dev runtime inventory, not production input ALLOW",
                "context_user_id": "not_probed_per_service",
                "permission_path": "unknown" if services else "no_surface_observed",
                "allowed_entity_result": None,
                "forbidden_entity_result": None,
                "response_leak": "not_probed",
                "static_findings": static_findings,
                "verdict": verdict,
                "reason": reason,
                "confidence": "dev-runtime-inventory",
                "required_followup": "component-specific runtime probe required before production ALLOW",
            }
        )

    return {
        "runtime_custom_components_tested": True,
        "live_volumes_config_scanned": False,
        "classification_rules": {
            "ALLOW": "only for runtime-verified components without enforcement-relevant surface or with proven user-context checks",
            "DENY": "reserved for reproduced unsafe behavior",
            "TIER-2": "needs Zusatz-Enforcement / explicit non-production or supplemental controls",
            "UNKNOWN_BLOCK_ENFORCE": "fail-closed default whenever runtime verification is absent or incomplete",
        },
        "input_components": components,
        "dev_runtime_components": dev_runtime_components,
        "components_count": len(components),
        "input_components_count": len(components),
        "dev_runtime_components_count": len(dev_runtime_components),
        "unknown_block_enforce_count": sum(
            1 for item in components if item["verdict"] == "UNKNOWN_BLOCK_ENFORCE"
        ),
        "allow_count": sum(1 for item in components if item["verdict"] == "ALLOW"),
        "deny_count": sum(1 for item in components if item["verdict"] == "DENY"),
        "tier2_count": sum(1 for item in components if item["verdict"] == "TIER-2"),
        "dev_runtime_tier2_count": sum(
            1 for item in dev_runtime_components if item["verdict"] == "TIER-2"
        ),
        "d9_gate_pass_fail_closed": (
            len(components) == len(RELEVANT_CUSTOM_COMPONENT_INPUTS)
            and all(item["verdict"] == "UNKNOWN_BLOCK_ENFORCE" for item in components)
            and all(item["verdict"] != "ALLOW" for item in dev_runtime_components)
        ),
        "enforce_blocked_by_unknown": any(
            item["verdict"] == "UNKNOWN_BLOCK_ENFORCE" for item in components
        ),
    }


async def _classify_custom_components_safely(hass: HomeAssistant) -> dict[str, Any]:
    """Return D9 classification evidence, failing closed on probe errors."""
    try:
        return await _classify_custom_components(hass)
    except Exception as err:  # pragma: no cover - dev evidence path
        return {
            "runtime_custom_components_tested": False,
            "live_volumes_config_scanned": False,
            "classification_error": type(err).__name__,
            "classification_error_message": str(err)[:200],
            "verdict": "FAIL",
            "reason": "D9 classifier raised; fail closed, no ALLOW emitted",
            "input_components": [
                {
                    "component_id": component,
                    "component": component,
                    "verdict": "UNKNOWN_BLOCK_ENFORCE",
                    "reason": "classifier failed before runtime verification",
                }
                for component in RELEVANT_CUSTOM_COMPONENT_INPUTS
            ],
            "d9_gate_pass_fail_closed": False,
            "enforce_blocked_by_unknown": True,
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
    rescue_result = await _probe_d5_post_boot(
        hass, await _read_json(hass, RESCUE_RESULT_PATH)
    )
    test_user = await _find_user(hass, TEST_USER_NAME)
    admin_user = await _find_user(hass, TEST_ADMIN_NAME)
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
        admin_access_token: str | None = None
        admin_refresh_token: models.RefreshToken | None = None
        if admin_user is not None:
            admin_access_token, admin_refresh_token = await _make_access_token(
                hass, admin_user, "tessera-spike-admin-baseline"
            )
        await hass.services.async_call(
            "input_boolean",
            "turn_off",
            {ATTR_ENTITY_ID: [ALLOWED_ENTITY, FORBIDDEN_ENTITY]},
            blocking=True,
        )
        await hass.services.async_call(
            "input_boolean",
            "turn_on",
            {ATTR_ENTITY_ID: FORBIDDEN_ENTITY},
            blocking=True,
            context=Context(user_id=None),
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
        before_all_allowed = hass.states.get(ALLOWED_ENTITY)
        before_all_forbidden = hass.states.get(FORBIDDEN_ENTITY)
        all_service = await _http_json(
            hass,
            "POST",
            "/api/services/input_boolean/turn_off",
            access_token,
            {"entity_id": "all"},
        )
        after_all_allowed = hass.states.get(ALLOWED_ENTITY)
        after_all_forbidden = hass.states.get(FORBIDDEN_ENTITY)
        response_service = await _http_json(
            hass,
            "POST",
            "/api/services/input_boolean/turn_on?return_response",
            access_token,
            {"entity_id": ALLOWED_ENTITY},
        )
        non_entity_service = await _http_json(
            hass,
            "POST",
            "/api/services/tessera_spike/snapshot?return_response",
            access_token,
            {},
        )
        d3_ws = await _probe_d3_ws(hass, access_token)
        d7_rest_matrix = await _probe_d7_rest_matrix(
            hass, access_token, admin_access_token=admin_access_token
        )
        d7_ws_matrix = await _probe_d7_ws_matrix(
            hass, access_token, admin_access_token=admin_access_token
        )
        d7_ws_template = await _probe_ws_render_template(
            hass, access_token, admin_access_token=admin_access_token
        )
        d7_ws_matrix.append(d7_ws_template)
        d6_system_context = await _probe_d6_system_context(hass)
        llat_access_token, llat_refresh_token = await _make_llat_access_token(
            hass, test_user, "tessera-spike-real-llat"
        )
        llat_states_before_revoke = await _http_json(
            hass, "GET", "/api/states", llat_access_token
        )
        llat_state_entities = _entity_ids_from_body(
            llat_states_before_revoke.get("body")
        )
        llat_allowed_service = await _http_json(
            hass,
            "POST",
            "/api/services/input_boolean/turn_on",
            llat_access_token,
            {"entity_id": ALLOWED_ENTITY},
        )
        llat_forbidden_service = await _http_json(
            hass,
            "POST",
            "/api/services/input_boolean/turn_on",
            llat_access_token,
            {"entity_id": FORBIDDEN_ENTITY},
        )
        hass.auth.async_remove_refresh_token(llat_refresh_token)
        llat_after_revoke = await _http_json(
            hass, "GET", "/api/states", llat_access_token
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
            "ws_tested": d3_ws.get("tested") is True,
            "ws": d3_ws,
            "consistent_entity_targeted": (
                states["status"] == 200
                and ALLOWED_ENTITY in state_entities
                and FORBIDDEN_ENTITY not in state_entities
                and allowed_state["status"] == 200
                and forbidden_state["status"] in (401, 403, 404)
                and allowed_service["status"] == 200
                and forbidden_service["status"] in (401, 403, 404)
                and d3_ws.get("allowed_in_state_list") is True
                and d3_ws.get("forbidden_in_state_list") is False
                and d3_ws.get("service_allowed_success") is True
                and d3_ws.get("service_forbidden_success") is False
            ),
        }
        d6_services = {
            "tested": True,
            "entity_service_allowed_status": allowed_service["status"],
            "entity_service_forbidden_status": forbidden_service["status"],
            "entity_id_all_status": all_service["status"],
            "entity_id_all_before": {
                ALLOWED_ENTITY: (
                    before_all_allowed.state if before_all_allowed is not None else None
                ),
                FORBIDDEN_ENTITY: (
                    before_all_forbidden.state
                    if before_all_forbidden is not None
                    else None
                ),
            },
            "entity_id_all_after": {
                ALLOWED_ENTITY: (
                    after_all_allowed.state if after_all_allowed is not None else None
                ),
                FORBIDDEN_ENTITY: (
                    after_all_forbidden.state
                    if after_all_forbidden is not None
                    else None
                ),
            },
            "return_response_changed_states_tested": True,
            "return_response_status": response_service["status"],
            "return_response_body": _body_summary(response_service.get("body")),
            "non_entity_service_tested": True,
            "non_entity_service": {
                "service": "tessera_spike.snapshot",
                "status": non_entity_service["status"],
                "body": _body_summary(non_entity_service.get("body")),
                "verdict": (
                    "ENFORCE_BYPASS"
                    if non_entity_service["status"] == 200
                    else "BLOCKED"
                ),
            },
            "ws_service_response_tested": True,
            "ws_service_allowed_success": d3_ws.get("service_allowed_success"),
            "ws_service_forbidden_success": d3_ws.get("service_forbidden_success"),
            "system_context": d6_system_context,
            "entity_targeted_pass": (
                allowed_service["status"] == 200
                and forbidden_service["status"] in (401, 403, 404)
                and d3_ws.get("service_allowed_success") is True
                and d3_ws.get("service_forbidden_success") is False
            ),
            "documented_enforce_gaps": [
                (
                    "system_context_user_id_none"
                    if d6_system_context.get("verdict") == "ENFORCE_BYPASS"
                    else None
                ),
                "non_entity_service" if non_entity_service["status"] == 200 else None,
            ],
        }
        d6_services["documented_enforce_gaps"] = [
            item for item in d6_services["documented_enforce_gaps"] if item
        ]
        d7_leaks = {
            "tested": True,
            "matrix": [*d7_rest_matrix, *d7_ws_matrix],
            "logbook_rest_tested": any(
                cell["vector"] == "/api/logbook" for cell in d7_rest_matrix
            ),
            "registry_ws_tested": any(
                str(cell["vector"]).startswith("config/") for cell in d7_ws_matrix
            ),
            "history_tested": any(
                "history" in str(cell["vector"])
                for cell in [*d7_rest_matrix, *d7_ws_matrix]
            ),
            "vectors": sorted(
                str(cell["vector"]) for cell in [*d7_rest_matrix, *d7_ws_matrix]
            ),
            "leaks": [
                cell
                for cell in [*d7_rest_matrix, *d7_ws_matrix]
                if cell["verdict"] == "LEAK"
            ],
            "complete_matrix": len(d7_rest_matrix) == 3
            and len(d7_ws_matrix) == 9
            and all(
                cell["verdict"] not in {"ERROR", "NOT_TESTED", "NOT_VERIFIABLE"}
                for cell in [*d7_rest_matrix, *d7_ws_matrix]
            ),
            "not_verifiable": [
                cell
                for cell in [*d7_rest_matrix, *d7_ws_matrix]
                if cell["verdict"] == "NOT_VERIFIABLE"
            ],
        }
        d8_llat = {
            "tested": True,
            "normal_headless_access_token_probe": True,
            "llat_created": True,
            "llat_token_type": llat_refresh_token.token_type,
            "llat_values_redacted": True,
            "llat_allowed_in_state_list": ALLOWED_ENTITY in llat_state_entities,
            "llat_forbidden_in_state_list": FORBIDDEN_ENTITY in llat_state_entities,
            "llat_service_allowed_status": llat_allowed_service["status"],
            "llat_service_forbidden_status": llat_forbidden_service["status"],
            "refresh_token_revoked_after_probe": True,
            "post_revoke_status": llat_after_revoke["status"],
            "matches_ui_path": (
                ALLOWED_ENTITY in llat_state_entities
                and FORBIDDEN_ENTITY not in llat_state_entities
                and llat_allowed_service["status"] == 200
                and llat_forbidden_service["status"] in (401, 403, 404)
            ),
            "revocation_effective": llat_after_revoke["status"] in (401, 403),
        }
        hass.auth.async_remove_refresh_token(refresh_token)
        if admin_refresh_token is not None:
            hass.auth.async_remove_refresh_token(admin_refresh_token)
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
        "d9_custom_component_runtime": await _classify_custom_components_safely(hass),
        "d11_version_gate": await _probe_d11_version_gate(hass),
        "d13_hacs_rollback": await _probe_d13_hacs_rollback(hass),
        "d15_lifecycle": await _probe_d15_lifecycle(hass),
    }
    data["post_restart"] = result
    await _write_json(hass, RESULT_PATH, data)
    return result


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    boot_rescue = await _run_boot_rescue_if_requested(hass)
    if SETUP_EXCEPTION_TRIGGER_PATH.exists():
        await _unlink_path(hass, SETUP_EXCEPTION_TRIGGER_PATH)
        boot_rescue["setup_exception_simulated"] = True
        boot_rescue["setup_exception_error_type"] = "RuntimeError"
        boot_rescue["rescue_independent_of_healthy_tessera"] = (
            boot_rescue.get("ok") is True
            and boot_rescue.get("boot_rescue_corruption_tested") is True
        )
        boot_rescue["d5_truthfulness"] = (
            "PENDING: boot rescue completed before a forced setup exception; "
            "post-boot auth/operate probes still pending"
        )
        await _write_json(hass, RESCUE_RESULT_PATH, boot_rescue)
        raise RuntimeError("tessera_spike forced setup exception after boot rescue")

    hass.states.async_set(
        STATE_ONLY_ENTITY, "42", {"friendly_name": "Tessera State Only"}
    )

    async def run_spike(call: ServiceCall) -> dict[str, Any]:
        phase = call.data.get("phase", "pre_restart")
        try:
            if phase == "pre_restart":
                return await _phase_pre_restart(hass)
            if phase == "post_restart":
                return await _phase_post_restart(hass)
            return {"error": f"unknown phase {phase}"}
        except Exception as err:  # pragma: no cover - dev evidence path
            return {
                "error": "run_spike_failed",
                "phase": phase,
                "error_type": type(err).__name__,
                "error_message": str(err)[:300],
            }

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
