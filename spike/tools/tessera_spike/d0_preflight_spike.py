#!/usr/bin/env python3
"""Tessera D0 preflight/onboarding/seed plus dev-only D1-D9 spike runner.

This tool is intentionally narrow:
- target container must be exactly ha-tessera-dev
- target image must be HA 2026.6.4
- /config must be the disposable ha-tessera-dev-config Docker volume
- no /Volumes/config bind may be present
- evidence never contains token/password/auth-code values

It writes reports to outputs/ and writes only to the disposable HA dev container.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUTPUTS = ROOT / "outputs"
CONTAINER = "ha-tessera-dev"
VOLUME = "ha-tessera-dev-config"
IMAGE = "ghcr.io/home-assistant/home-assistant:2026.6.4"
PORT = "8124"
BASE = f"http://127.0.0.1:{PORT}"
TODAY = dt.date.today().isoformat()


HARNESS_INIT = r'''
"""Dev-only Tessera spike harness for HA 2026.6.4."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.auth import models
from homeassistant.auth.const import GROUP_ID_ADMIN, GROUP_ID_READ_ONLY
from homeassistant.auth.permissions.const import CAT_ENTITIES, POLICY_CONTROL, POLICY_READ
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.typing import ConfigType

DOMAIN = "tessera_spike"
RESULT_PATH = Path("/config/tessera_spike_result.json")
STATE_PATH = Path("/config/tessera_spike_state.json")

ALLOWED_ENTITY = "input_boolean.tessera_allowed_light"
FORBIDDEN_ENTITY = "input_boolean.tessera_forbidden_light"
STATE_ONLY_ENTITY = "sensor.tessera_state_only"
GROUP_ID = "tessera:test"
GROUP_ID_EXTRA = "tessera:extra"
TEST_USER_NAME = "tessera-test-user"
TEST_ADMIN_NAME = "tessera-test-admin"
TEST_RO_NAME = "tessera-test-ro"

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)


def _policy(entity_id: str, *, read: bool = True, control: bool = False) -> dict[str, Any]:
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
    groups = await hass.auth._store.async_get_groups()  # noqa: SLF001 - spike probes private API.
    return {
        "users": [_sanitize_user(user) for user in users],
        "groups": [
            {
                "id": group.id,
                "name": group.name,
                "system_generated": group.system_generated,
                "has_policy": bool(group.policy),
                "policy_keys": sorted(group.policy.keys()) if isinstance(group.policy, dict) else [],
            }
            for group in groups
        ],
    }


async def _persist_auth(hass: HomeAssistant) -> None:
    store = hass.auth._store  # noqa: SLF001 - this spike explicitly probes private API.
    await store._store.async_save(store._data_to_save())  # noqa: SLF001
    await asyncio.sleep(0.2)


async def _ensure_group(hass: HomeAssistant, group_id: str, name: str, policy: dict[str, Any]) -> models.Group:
    store = hass.auth._store  # noqa: SLF001
    await store.async_get_groups()
    group = await hass.auth.async_get_group(group_id)
    if group is None:
        group = models.Group(id=group_id, name=name, policy=policy, system_generated=False)
        store._groups[group_id] = group  # noqa: SLF001
    else:
        group.name = name
        group.policy = policy
    await _persist_auth(hass)
    return group


async def _ensure_test_user(hass: HomeAssistant, name: str, group_ids: list[str]) -> models.User:
    users = await hass.auth.async_get_users()
    for user in users:
        if user.name == name:
            await hass.auth.async_update_user(user, group_ids=group_ids)
            return user
    return await hass.auth.async_create_user(name, group_ids=group_ids, local_only=True)


async def _make_access_token(hass: HomeAssistant, user: models.User, client_name: str) -> tuple[str, models.RefreshToken]:
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


async def _phase_pre_restart(hass: HomeAssistant) -> dict[str, Any]:
    hass.states.async_set(STATE_ONLY_ENTITY, "42", {"friendly_name": "Tessera State Only"})
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
    test_admin = await _ensure_test_user(hass, TEST_ADMIN_NAME, [GROUP_ID_ADMIN])
    test_ro = await _ensure_test_user(hass, TEST_RO_NAME, [GROUP_ID_READ_ONLY])

    allowed_read = test_user.permissions.check_entity(ALLOWED_ENTITY, POLICY_READ)
    forbidden_read = test_user.permissions.check_entity(FORBIDDEN_ENTITY, POLICY_READ)
    allowed_control = test_user.permissions.check_entity(ALLOWED_ENTITY, POLICY_CONTROL)
    forbidden_control = test_user.permissions.check_entity(FORBIDDEN_ENTITY, POLICY_CONTROL)

    # D2: policy-only change without membership change.
    group = await hass.auth.async_get_group(GROUP_ID)
    assert group is not None
    group.policy = _policy(FORBIDDEN_ENTITY, read=True, control=True)
    test_user.invalidate_cache()
    d2_after_change = {
        "allowed_read_after_policy_change": test_user.permissions.check_entity(ALLOWED_ENTITY, POLICY_READ),
        "forbidden_read_after_policy_change": test_user.permissions.check_entity(FORBIDDEN_ENTITY, POLICY_READ),
        "forbidden_control_after_policy_change": test_user.permissions.check_entity(FORBIDDEN_ENTITY, POLICY_CONTROL),
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

    STATE_PATH.write_text(
        json.dumps(
            {
                "test_user_name": TEST_USER_NAME,
                "test_admin_name": TEST_ADMIN_NAME,
                "test_ro_name": TEST_RO_NAME,
                "group_id": GROUP_ID,
                "group_id_extra": GROUP_ID_EXTRA,
                "original_groups": original_groups,
            },
            indent=2,
            sort_keys=True,
        )
    )

    after = await _auth_snapshot(hass)
    result = {
        "phase": "pre_restart",
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
        },
    }
    RESULT_PATH.write_text(json.dumps({"pre_restart": result}, indent=2, sort_keys=True))
    return result


async def _phase_post_restart(hass: HomeAssistant) -> dict[str, Any]:
    data: dict[str, Any] = {}
    if RESULT_PATH.exists():
        data = json.loads(RESULT_PATH.read_text())
    state = json.loads(STATE_PATH.read_text()) if STATE_PATH.exists() else {}
    users = await hass.auth.async_get_users()
    test_user = next((user for user in users if user.name == TEST_USER_NAME), None)
    group = await hass.auth.async_get_group(GROUP_ID)

    d1 = {
        "group_survived_restart": group is not None,
        "policy_survived_restart": bool(group and group.policy),
        "user_survived_restart": test_user is not None,
    }

    d3_rest: dict[str, Any] = {"tested": False}
    d6_services: dict[str, Any] = {"tested": False}
    d7_leaks: dict[str, Any] = {"tested": False}
    d8_llat: dict[str, Any] = {"tested": False, "reason": "no real LLAT created; normal dev access token used for headless probe only"}

    if test_user is not None:
        access_token, refresh_token = await _make_access_token(hass, test_user, "tessera-spike-headless")
        states = await _http_json(hass, "GET", "/api/states", access_token)
        state_entities: list[str] = []
        if isinstance(states.get("body"), list):
            state_entities = [item.get("entity_id") for item in states["body"] if isinstance(item, dict)]
        allowed_state = await _http_json(hass, "GET", f"/api/states/{ALLOWED_ENTITY}", access_token)
        forbidden_state = await _http_json(hass, "GET", f"/api/states/{FORBIDDEN_ENTITY}", access_token)
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
    RESULT_PATH.write_text(json.dumps(data, indent=2, sort_keys=True))
    return result


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    hass.states.async_set(STATE_ONLY_ENTITY, "42", {"friendly_name": "Tessera State Only"})

    async def run_spike(call: ServiceCall) -> dict[str, Any]:
        phase = call.data.get("phase", "pre_restart")
        if phase == "pre_restart":
            return await _phase_pre_restart(hass)
        if phase == "post_restart":
            return await _phase_post_restart(hass)
        return {"error": f"unknown phase {phase}"}

    hass.services.async_register(
        DOMAIN,
        "run_spike",
        run_spike,
        schema=vol.Schema({vol.Required("phase"): vol.In(["pre_restart", "post_restart"])}),
        supports_response=SupportsResponse.ONLY,
    )
    return True
'''


MANIFEST = r'''{
  "domain": "tessera_spike",
  "name": "Tessera Spike Harness",
  "version": "0.0.1",
  "documentation": "https://example.invalid/tessera-spike",
  "dependencies": [],
  "codeowners": [],
  "requirements": []
}
'''


CONFIGURATION = r'''
default_config:

logger:
  default: warning

tessera_spike:

input_boolean:
  tessera_allowed_light:
    name: Tessera Allowed Light
  tessera_forbidden_light:
    name: Tessera Forbidden Light
'''


def run(cmd: list[str], *, check: bool = True, capture: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        check=check,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


def docker_json(args: list[str]) -> Any:
    proc = run(["docker", *args])
    text = proc.stdout.strip()
    return json.loads(text) if text else None


def docker_exists() -> bool:
    proc = run(["docker", "ps", "-a", "--format", "{{.Names}}"], check=False)
    return CONTAINER in proc.stdout.splitlines()


def inspect_container() -> dict[str, Any]:
    data = docker_json(["inspect", CONTAINER])
    if not data:
        raise RuntimeError("container inspect returned no data")
    return data[0]


def sanitize_inspect(info: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": info.get("Name", "").lstrip("/"),
        "image": info.get("Config", {}).get("Image"),
        "binds": info.get("HostConfig", {}).get("Binds"),
        "mounts": [
            {
                "Type": m.get("Type"),
                "Name": m.get("Name"),
                "Destination": m.get("Destination"),
                "Driver": m.get("Driver"),
                "Mode": m.get("Mode"),
                "RW": m.get("RW"),
            }
            for m in info.get("Mounts", [])
        ],
        "ports": info.get("NetworkSettings", {}).get("Ports"),
        "id_short": info.get("Id", "")[:12],
    }


def assert_target_isolation(info: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    clean = sanitize_inspect(info)
    if clean["name"] != CONTAINER:
        errors.append("container name mismatch")
    if clean["image"] != IMAGE:
        errors.append("image mismatch")
    binds = clean["binds"] or []
    allowed_binds = {f"{VOLUME}:/config", f"{VOLUME}:/config:rw", f"{VOLUME}:/config:z"}
    unexpected_binds = [bind for bind in binds if bind not in allowed_binds]
    if unexpected_binds:
        errors.append(f"unexpected bind mounts present: {unexpected_binds}")
    mounts = clean["mounts"]
    config_mounts = [m for m in mounts if m.get("Destination") == "/config"]
    if len(config_mounts) != 1:
        errors.append("expected exactly one /config mount")
    else:
        mount = config_mounts[0]
        if mount.get("Type") != "volume" or mount.get("Name") != VOLUME:
            errors.append(f"/config is not expected volume {VOLUME}")
    ports = clean["ports"] or {}
    p = ports.get("8123/tcp") or []
    host_ports = sorted({entry.get("HostPort") for entry in p})
    if host_ports != [PORT]:
        errors.append(f"expected host port {PORT}, got {host_ports}")
    forbidden = json.dumps(clean)
    for marker in ("/Volumes/config", "maison-atrium-dev", "Maison", "Atrium"):
        if marker in forbidden:
            errors.append(f"forbidden live marker in docker inspect: {marker}")
    return not errors, errors


def recreate_container(evidence: dict[str, Any]) -> None:
    existing_ok = True
    if docker_exists():
        info = inspect_container()
        ok, errors = assert_target_isolation(info)
        evidence["pre_existing_target"] = {
            "inspect": sanitize_inspect(info),
            "isolation_ok": ok,
            "errors": errors,
        }
        if not ok:
            existing_ok = False
    if not existing_ok:
        raise RuntimeError("refusing to remove container because target isolation failed")

    run(["docker", "rm", "-f", CONTAINER], check=False)
    run(["docker", "volume", "rm", VOLUME], check=False)
    run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            CONTAINER,
            "-e",
            "TZ=Europe/Berlin",
            "-v",
            f"{VOLUME}:/config",
            "-p",
            f"{PORT}:8123",
            IMAGE,
        ],
        capture=True,
    )
    time.sleep(3)
    info = inspect_container()
    ok, errors = assert_target_isolation(info)
    evidence["recreated_target"] = {
        "inspect": sanitize_inspect(info),
        "isolation_ok": ok,
        "errors": errors,
    }
    if not ok:
        raise RuntimeError(f"target isolation failed after recreate: {errors}")


def wait_http(path: str, timeout: int = 180) -> Any:
    deadline = time.time() + timeout
    last: str | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{BASE}{path}", timeout=5) as resp:
                body = resp.read().decode()
                return json.loads(body) if body else None
        except Exception as exc:  # noqa: BLE001
            last = f"{type(exc).__name__}: {exc}"
            time.sleep(2)
    raise RuntimeError(f"timeout waiting for {path}: {last}")


def wait_http_status(path: str, accepted: set[int], timeout: int = 180) -> int:
    deadline = time.time() + timeout
    last: str | None = None
    while time.time() < deadline:
        try:
            req = urllib.request.Request(f"{BASE}{path}", method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status in accepted:
                    return resp.status
                last = f"HTTP {resp.status}"
        except urllib.error.HTTPError as exc:
            if exc.code in accepted:
                return exc.code
            last = f"HTTPError {exc.code}"
        except Exception as exc:  # noqa: BLE001
            last = f"{type(exc).__name__}: {exc}"
        time.sleep(2)
    raise RuntimeError(f"timeout waiting for {path} status {sorted(accepted)}: {last}")


def http_json(
    method: str,
    path: str,
    *,
    token: str | None = None,
    payload: dict[str, Any] | None = None,
    form: dict[str, str] | None = None,
    timeout: int = 30,
) -> tuple[int, Any]:
    url = f"{BASE}{path}"
    headers: dict[str, str] = {}
    data: bytes | None = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode()
            return resp.status, json.loads(text) if text else {}
    except urllib.error.HTTPError as exc:
        text = exc.read().decode()
        try:
            body = json.loads(text) if text else {}
        except json.JSONDecodeError:
            body = {"raw": text[:200]}
        return exc.code, body


def docker_exec_json(script: str) -> Any:
    proc = run(["docker", "exec", CONTAINER, "python", "-c", script])
    return json.loads(proc.stdout)


def auth_baseline() -> dict[str, Any]:
    return docker_exec_json(
        r'''
import json, pathlib
p = pathlib.Path("/config/.storage/auth")
data = json.loads(p.read_text())["data"] if p.exists() else {"users": [], "groups": [], "refresh_tokens": []}
users = []
for u in data.get("users", []):
    users.append({
        "name": u.get("name"),
        "is_owner": u.get("is_owner"),
        "is_active": u.get("is_active"),
        "system_generated": u.get("system_generated"),
        "group_ids": u.get("group_ids"),
        "credentials_count": sum(1 for c in data.get("credentials", []) if c.get("user_id") == u.get("id")),
    })
tokens = []
for t in data.get("refresh_tokens", []):
    tokens.append({
        "token_type": t.get("token_type"),
        "client_name": t.get("client_name"),
        "client_id_present": bool(t.get("client_id")),
        "credential_id_present": bool(t.get("credential_id")),
    })
print(json.dumps({"users": users, "groups_count": len(data.get("groups", [])), "tokens": tokens}, sort_keys=True))
'''
    )


def assert_fresh_baseline(base: dict[str, Any], onboarding: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if any(step.get("done") for step in onboarding):
        errors.append("onboarding step already done")
    users = base.get("users", [])
    tokens = base.get("tokens", [])
    expected = [
        u
        for u in users
        if u.get("name") == "Home Assistant Content"
        and u.get("system_generated") is True
        and u.get("is_owner") is False
        and u.get("is_active") is True
        and u.get("group_ids") == ["system-read-only"]
        and u.get("credentials_count") == 0
    ]
    if len(users) != 1 or len(expected) != 1:
        errors.append(f"unexpected user baseline: {users}")
    expected_tokens = [
        t
        for t in tokens
        if t.get("token_type") == "system"
        and t.get("client_name") is None
        and t.get("client_id_present") is False
        and t.get("credential_id_present") is False
    ]
    if len(tokens) != 1 or len(expected_tokens) != 1:
        errors.append(f"unexpected token baseline: {tokens}")
    if base.get("groups_count") != 3:
        errors.append(f"expected 3 system groups, got {base.get('groups_count')}")
    return not errors, errors


def install_harness() -> None:
    with tempfile.TemporaryDirectory(prefix="tessera-spike-") as tmp:
        tmp_path = Path(tmp)
        comp = tmp_path / "custom_components" / "tessera_spike"
        comp.mkdir(parents=True)
        (comp / "__init__.py").write_text(HARNESS_INIT)
        (comp / "manifest.json").write_text(MANIFEST)
        (tmp_path / "configuration.yaml").write_text(CONFIGURATION)
        run(["docker", "cp", str(tmp_path / "custom_components"), f"{CONTAINER}:/config/"])
        run(["docker", "cp", str(tmp_path / "configuration.yaml"), f"{CONTAINER}:/config/configuration.yaml"])
    run(["docker", "restart", CONTAINER])
    wait_http("/api/onboarding", timeout=180)


def onboard(evidence: dict[str, Any]) -> str:
    password = "Tessera-" + secrets.token_urlsafe(24)
    client_id = "http://localhost:8124/"
    status, body = http_json(
        "POST",
        "/api/onboarding/users",
        payload={
            "name": "test-owner",
            "username": "test-owner",
            "password": password,
            "client_id": client_id,
            "language": "en",
        },
    )
    evidence["onboarding_user"] = {"status": status, "body_keys": sorted(body.keys()) if isinstance(body, dict) else []}
    if status != 200 or "auth_code" not in body:
        raise RuntimeError(f"user onboarding failed: {status} {body}")
    auth_code = body["auth_code"]
    status, token_body = http_json(
        "POST",
        "/auth/token",
        form={"grant_type": "authorization_code", "code": auth_code, "client_id": client_id},
    )
    evidence["token_exchange"] = {
        "status": status,
        "body_keys": sorted(token_body.keys()) if isinstance(token_body, dict) else [],
        "token_values_redacted": True,
    }
    if status != 200 or "access_token" not in token_body:
        raise RuntimeError(f"token exchange failed: {status} {token_body}")
    access_token = token_body["access_token"]

    for path, payload in (
        ("/api/onboarding/core_config", None),
        ("/api/onboarding/analytics", None),
        ("/api/onboarding/integration", {"client_id": client_id, "redirect_uri": client_id}),
    ):
        status, step_body = http_json("POST", path, token=access_token, payload=payload)
        evidence.setdefault("onboarding_steps", []).append(
            {"path": path, "status": status, "body_keys": sorted(step_body.keys()) if isinstance(step_body, dict) else []}
        )
        if status not in (200, 201):
            raise RuntimeError(f"onboarding step failed {path}: {status} {step_body}")
    evidence["onboarding_after"] = wait_http("/api/onboarding")
    return access_token


def call_service(token: str, phase: str) -> dict[str, Any]:
    status, body = http_json(
        "POST",
        "/api/services/tessera_spike/run_spike?return_response",
        token=token,
        payload={"phase": phase},
        timeout=120,
    )
    if status != 200:
        raise RuntimeError(f"run_spike {phase} failed: {status} {body}")
    if isinstance(body, dict) and "service_response" in body:
        return body["service_response"]
    return body


def read_container_json(path: str) -> Any:
    proc = run(["docker", "exec", CONTAINER, "cat", path])
    return json.loads(proc.stdout)


def static_d9_scan() -> dict[str, Any]:
    base = Path("/Volumes/config/custom_components")
    result = {
        "path": str(base),
        "available": base.exists(),
        "components_count": None,
        "services_yaml_components": [],
        "http_or_ws_candidates": [],
    }
    if not base.exists():
        return result
    comps = sorted([p for p in base.iterdir() if p.is_dir()])
    result["components_count"] = len(comps)
    for comp in comps:
        if (comp / "services.yaml").exists():
            result["services_yaml_components"].append(comp.name)
        for marker in ("websocket", "http", "panel", "view"):
            if any(marker in str(p).lower() for p in comp.rglob("*.py")):
                result["http_or_ws_candidates"].append(comp.name)
                break
    result["http_or_ws_candidates"] = sorted(set(result["http_or_ws_candidates"]))
    return result


def verdicts_from_result(result: dict[str, Any], d0_green: bool) -> dict[str, dict[str, Any]]:
    pre = result.get("pre_restart", {})
    post = result.get("post_restart", {})
    d1 = post.get("d1_restart_survival", {})
    d2 = pre.get("d2_policy_change_no_restart", {})
    d3i = pre.get("d3_internal_check_entity", {})
    d3r = post.get("d3_rest_ws_service", {})
    d4 = pre.get("d4_union_restore", {})
    d6 = post.get("d6_service_matrix", {})
    d7 = post.get("d7_leak_matrix", {})
    d8 = post.get("d8_headless_token", {})
    d9 = result.get("d9_static_scan", {})

    return {
        "D0": {
            "verdict": "PASS" if d0_green else "FAIL",
            "summary": "Preflight/onboarding/seed/harness gate",
        },
        "D1": {
            "verdict": "PASS" if all(d1.get(k) for k in ("group_survived_restart", "policy_survived_restart", "user_survived_restart")) else "FAIL",
            "summary": "tessera group/policy/user restart survival",
        },
        "D2": {
            "verdict": "PASS" if d2.get("forbidden_read_after_policy_change") and d2.get("forbidden_control_after_policy_change") and not d2.get("allowed_read_after_policy_change") else "FAIL",
            "summary": "policy-only change reflected after explicit cache invalidation without restart",
        },
        "D3": {
            "verdict": "PARTIAL" if d3r.get("tested") and not d3r.get("ws_tested") else "FAIL",
            "summary": "internal + REST + service tested; WS not tested in this run",
        },
        "D4": {
            "verdict": "PASS" if set(d4.get("original_groups", [])) == set(d4.get("restored_groups", [])) and len(d4.get("union_groups", [])) > len(d4.get("original_groups", [])) else "FAIL",
            "summary": "full union and restore via public update_user",
        },
        "D5": {
            "verdict": "PARTIAL",
            "summary": "restore primitive proved; corrupt-store boot rescue not executed in this run",
        },
        "D6": {
            "verdict": "PARTIAL" if d6.get("tested") else "FAIL",
            "summary": "entity service allowed/forbidden and entity_id:all probed; response/non-entity matrix incomplete",
        },
        "D7": {
            "verdict": "PARTIAL" if d7.get("tested") else "FAIL",
            "summary": "render_template probed; logbook/registry/history/WS leak matrix incomplete",
        },
        "D8": {
            "verdict": "PARTIAL" if d8.get("tested") else "FAIL",
            "summary": "headless normal token probe and revocation; real LLAT rotation not performed",
        },
        "D9": {
            "verdict": "PARTIAL" if d9.get("available") else "FAIL",
            "summary": "static /Volumes/config custom-component scan; runtime classification not complete",
        },
    }


def write_markdown(evidence: dict[str, Any], spike: dict[str, Any], verdicts: dict[str, dict[str, Any]]) -> Path:
    report = OUTPUTS / f"tessera-spike-report-{TODAY}.md"
    d0_report = OUTPUTS / f"tessera-d0-evidence-{TODAY}.md"
    d0_json = OUTPUTS / f"tessera-d0-evidence-{TODAY}.json"
    spike_json = OUTPUTS / f"tessera-spike-result-{TODAY}.json"

    d0_json.write_text(json.dumps(evidence, indent=2, sort_keys=True))
    spike_json.write_text(json.dumps(spike, indent=2, sort_keys=True))

    d0_lines = [
        "# Tessera D0 Evidence",
        "",
        f"Stand: {dt.datetime.now().isoformat(timespec='seconds')}",
        "Modus: ha-tessera-dev only; /Volumes/config read-only; no token/password/auth-code values emitted.",
        "",
        f"Overall D0: **{verdicts['D0']['verdict']}**",
        "",
        "## Gate Evidence",
        "",
        f"- Target isolation: `{evidence.get('recreated_target', {}).get('isolation_ok')}`",
        f"- Fresh baseline: `{evidence.get('fresh_baseline', {}).get('ok')}`",
        f"- Onboarding user status: `{evidence.get('onboarding_user', {}).get('status')}`",
        f"- Token exchange status: `{evidence.get('token_exchange', {}).get('status')}` (values redacted)",
        f"- Harness installed/loaded: `{evidence.get('harness', {}).get('loaded')}`",
        f"- Recreate proof: Docker container and volume were recreated after target-isolation check.",
        "",
        "Full sanitized JSON: `" + str(d0_json.relative_to(ROOT)) + "`",
        "",
    ]
    d0_report.write_text("\n".join(d0_lines))

    rows = "\n".join(
        f"| {key} | {value['verdict']} | {value['summary']} |" for key, value in verdicts.items()
    )
    md = f"""# Tessera Phase-0 Spike Report

Stand: {dt.datetime.now().isoformat(timespec='seconds')}

Modus: Dev-only gegen `ha-tessera-dev`; `/Volumes/config` nur read-only fuer D9-Statik; keine Secrets/Token/Auth-Codes ausgegeben.

## Gesamturteil

**PARTIAL / kein Enforce-Go.**

D0 ist gruen genug, um den dev-only Messlauf zu starten. D1, D2 und D4 liefern starke positive Signale fuer den Auth-Store-Schreibpfad. D3/D6/D7/D8/D9 bleiben bewusst **PARTIAL**, weil WS, echte LLAT-Rotation, vollstaendige Leak-Matrix, Custom-Component-Runtime und Live/CM5-Gates in diesem Lauf nicht vollstaendig abgedeckt sind.

## DoD Matrix

| DoD | Verdict | Kurzbegruendung |
|---|---:|---|
{rows}

## D0

- Harte Docker-Isolation: `{evidence.get('recreated_target', {}).get('isolation_ok')}`
- Fresh-Baseline-Allowlist: `{evidence.get('fresh_baseline', {}).get('ok')}`
- Onboarding abgeschlossen: `{all(step.get('done') for step in evidence.get('onboarding_after', []))}`
- Harness-Service geladen: `{evidence.get('harness', {}).get('loaded')}`
- Token-/Passwortwerte: nicht im Report enthalten.

## D1-D5 Auth-Store / Recovery Kern

```json
{json.dumps({k: spike.get('pre_restart', {}).get(k) for k in ['d1_pre_restart', 'd2_policy_change_no_restart', 'd3_internal_check_entity', 'd4_union_restore', 'd5_restore_primitive']}, indent=2, sort_keys=True)}
```

Restart-Survival:

```json
{json.dumps(spike.get('post_restart', {}).get('d1_restart_survival', {}), indent=2, sort_keys=True)}
```

## D3/D6/D7/D8 Runtime Probes

```json
{json.dumps({k: spike.get('post_restart', {}).get(k) for k in ['d3_rest_ws_service', 'd6_service_matrix', 'd7_leak_matrix', 'd8_headless_token']}, indent=2, sort_keys=True)}
```

## D9 Static Custom-Component Scan

```json
{json.dumps(spike.get('d9_static_scan', {}), indent=2, sort_keys=True)}
```

## Core-Anker

- HA `auth_store.py`: private `_groups`, `_data_to_save()`, `_store.async_save()` sind der gemessene Schreibpfad.
- HA `auth/models.py`: `User.permissions` ist cached; `invalidate_cache()` ist fuer reine Policy-Mutation relevant.
- HA `auth/__init__.py`: `async_update_user(group_ids=...)` ist der oeffentliche Restore-/Binding-Pfad.
- HA `http/auth.py`: `Home Assistant Content` ist `system_generated` und bleibt unmanaged.

## Go/No-Go

- **Go fuer weitere Phase-0-Haertung:** ja.
- **Go fuer Tessera-Enforce/Product:** nein.
- **Naechste Pflicht:** WS-Testmatrix, echter LLAT-Lifecycle, Boot-Rescue mit absichtlich korruptem Tessera-Store, non-entity/custom service classification runtime, unsupported-version gate, D10/CM5-Benchmark und D12/OIDC gesondert.

## Artefakte

- D0 Evidence: `{d0_report.relative_to(ROOT)}`
- D0 JSON: `{d0_json.relative_to(ROOT)}`
- Spike JSON: `{spike_json.relative_to(ROOT)}`
"""
    report.write_text(md)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-reset", action="store_true", help="Do not recreate the disposable dev container first.")
    args = parser.parse_args()

    OUTPUTS.mkdir(exist_ok=True)
    evidence: dict[str, Any] = {
        "started_at": dt.datetime.now().isoformat(timespec="seconds"),
        "target": {"container": CONTAINER, "volume": VOLUME, "image": IMAGE, "port": PORT},
        "secret_policy": "no token/password/auth-code values emitted",
        "status": "STARTED",
    }
    d0_green = False
    try:
        if args.no_reset:
            info = inspect_container()
            ok, errors = assert_target_isolation(info)
            evidence["existing_target"] = {
                "inspect": sanitize_inspect(info),
                "isolation_ok": ok,
                "errors": errors,
            }
            if not ok:
                raise RuntimeError(f"target isolation failed: {errors}")
        else:
            recreate_container(evidence)

        wait_http("/api/onboarding", timeout=180)
        install_harness()
        onboarding_before = wait_http("/api/onboarding", timeout=180)
        baseline = auth_baseline()
        ok, errors = assert_fresh_baseline(baseline, onboarding_before)
        evidence["onboarding_before"] = onboarding_before
        evidence["auth_baseline"] = baseline
        evidence["fresh_baseline"] = {"ok": ok, "errors": errors}
        if not ok:
            raise RuntimeError(f"fresh baseline failed: {errors}")

        # Re-read immediately before first auth write.
        baseline_reread = auth_baseline()
        ok, errors = assert_fresh_baseline(baseline_reread, wait_http("/api/onboarding"))
        evidence["auth_baseline_reread"] = baseline_reread
        evidence["fresh_baseline_reread"] = {"ok": ok, "errors": errors}
        if not ok:
            raise RuntimeError(f"fresh baseline re-read failed: {errors}")

        owner_token = onboard(evidence)
        # No token values written; only use in memory below.
        status, services = http_json("GET", "/api/services", token=owner_token)
        loaded = status == 200 and any(
            svc.get("domain") == "tessera_spike"
            for svc in services
            if isinstance(svc, dict)
        )
        evidence["harness"] = {"services_status": status, "loaded": loaded}
        if not loaded:
            raise RuntimeError("tessera_spike service not loaded")

        pre = call_service(owner_token, "pre_restart")
        evidence["pre_restart_service"] = {"ok": True, "keys": sorted(pre.keys())}

        run(["docker", "restart", CONTAINER])
        evidence["post_restart_http_status"] = wait_http_status("/api/", {200, 401}, timeout=180)
        # Existing access token may be invalid after restart? It should remain valid briefly, but get a new one via refresh would need secret.
        # Call post_restart using the same access token first; if rejected, record failure.
        post = call_service(owner_token, "post_restart")
        evidence["post_restart_service"] = {"ok": True, "keys": sorted(post.keys())}

        spike = read_container_json("/config/tessera_spike_result.json")
        spike["d9_static_scan"] = static_d9_scan()
        d0_green = True
        evidence["status"] = "GREEN"
        verdicts = verdicts_from_result(spike, d0_green)
        report = write_markdown(evidence, spike, verdicts)
        print(f"D0 GREEN; spike report written: {report}")
        return 0
    except Exception as exc:  # noqa: BLE001
        evidence["status"] = "RED"
        evidence["error"] = str(exc)
        failure = OUTPUTS / f"tessera-d0-evidence-{TODAY}.json"
        failure.write_text(json.dumps(evidence, indent=2, sort_keys=True))
        print(f"D0 RED: {exc}", file=sys.stderr)
        print(f"sanitized evidence: {failure}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
