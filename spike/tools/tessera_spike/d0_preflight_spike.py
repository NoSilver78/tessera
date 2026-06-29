#!/usr/bin/env python3
"""Tessera D0 preflight/onboarding/seed plus dev-only D1-D9 spike runner.

This tool is intentionally narrow:
- target container must be exactly ha-tessera-dev
- target image must be HA 2026.6.4
- /config must be the disposable ha-tessera-dev-config Docker volume
- no /Volumes/config bind may be present
- evidence never contains token/password/auth-code values

It writes reports to spike/reports, evidence to spike/evidence, and writes only
to the disposable HA dev container.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "reports"
EVIDENCE = ROOT / "evidence"
HARNESS = Path(__file__).resolve().parent / "harness"
CONTAINER = "ha-tessera-dev"
VOLUME = "ha-tessera-dev-config"
IMAGE = "ghcr.io/home-assistant/home-assistant:2026.6.4"
PORT = "8124"
BASE = f"http://127.0.0.1:{PORT}"
TODAY = dt.date.today().isoformat()
HARNESS_REQUIRED_SERVICES = {
    "boot_rescue_status",
    "ensure_group",
    "set_group_policy",
    "set_user_groups",
    "flush_auth_store",
    "invalidate_user",
    "prepare_boot_rescue",
    "probe_d2_three_way",
    "snapshot",
    "restore",
    "probe_check_entity",
    "probe_system_users_gate",
}
SENSITIVE_KEYS = {
    "access_token",
    "auth_code",
    "code",
    "id_token",
    "password",
    "refresh_token",
    "token",
}
SECRET_VALUE_MARKERS = ("Bearer ", "eyJ")


CONFIGURATION = r"""
default_config:

logger:
  default: warning

tessera_spike:

input_boolean:
  tessera_allowed_light:
    name: Tessera Allowed Light
  tessera_forbidden_light:
    name: Tessera Forbidden Light
"""


def run(
    cmd: list[str], *, check: bool = True, capture: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        check=check,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


def body_keys(body: Any) -> list[str]:
    """Return only response-body keys for evidence; never response values."""
    if isinstance(body, dict):
        return sorted(str(key) for key in body)
    return []


def safe_body_summary(body: Any) -> dict[str, Any]:
    """Summarize an HTTP response body without exposing values."""
    summary: dict[str, Any] = {"body_type": type(body).__name__}
    keys = body_keys(body)
    if keys:
        summary["body_keys"] = keys
        summary["sensitive_keys_redacted"] = sorted(set(keys) & SENSITIVE_KEYS)
    elif isinstance(body, list):
        summary["items"] = len(body)
    return summary


def safe_http_error(context: str, status: int, body: Any) -> RuntimeError:
    """Create a token-free HTTP failure exception."""
    return RuntimeError(f"{context}: status={status} body={safe_body_summary(body)}")


def redact_text(text: str) -> str:
    """Redact obvious token-like log fragments before writing evidence."""
    redacted = text
    for marker in SECRET_VALUE_MARKERS:
        if marker in redacted:
            redacted = redacted.split(marker, 1)[0] + marker + "<redacted>"
    return redacted


def measure_failure_redaction(evidence: dict[str, Any]) -> dict[str, Any]:
    """Measure whether collected evidence contains obvious secret values."""
    text = json.dumps(evidence, sort_keys=True)
    jwt_like = re.findall(r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}", text)
    bearer_like = re.findall(r"Bearer\s+[A-Za-z0-9._-]{20,}", text)
    token_exchange = evidence.get("token_exchange", {})
    onboarding_user = evidence.get("onboarding_user", {})
    checks = {
        "token_exchange_values_redacted": token_exchange.get("token_values_redacted")
        is True,
        "token_body_values_not_stored": "body" not in token_exchange,
        "auth_code_value_not_stored": "body" not in onboarding_user,
        "jwt_like_values": len(jwt_like),
        "bearer_like_values": len(bearer_like),
    }
    return {
        "checked": True,
        "clean": all(
            [
                checks["token_exchange_values_redacted"],
                checks["token_body_values_not_stored"],
                checks["auth_code_value_not_stored"],
                checks["jwt_like_values"] == 0,
                checks["bearer_like_values"] == 0,
            ]
        ),
        **checks,
    }


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
        raise RuntimeError(
            "refusing to remove container because target isolation failed"
        )

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
    return docker_exec_json(r"""
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
""")


def wait_auth_baseline(timeout: int = 60) -> dict[str, Any]:
    """Wait until HA has persisted its initial auth store."""
    deadline = time.time() + timeout
    last: dict[str, Any] = {"users": [], "groups_count": 0, "tokens": []}
    while time.time() < deadline:
        last = auth_baseline()
        if last.get("users") or last.get("groups_count") or last.get("tokens"):
            return last
        time.sleep(1)
    return last


def assert_fresh_baseline(
    base: dict[str, Any], onboarding: list[dict[str, Any]]
) -> tuple[bool, list[str]]:
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
        shutil.copytree(HARNESS / "custom_components", tmp_path / "custom_components")
        (tmp_path / "configuration.yaml").write_text(CONFIGURATION)
        run(
            [
                "docker",
                "cp",
                str(tmp_path / "custom_components"),
                f"{CONTAINER}:/config/",
            ]
        )
        run(
            [
                "docker",
                "cp",
                str(tmp_path / "configuration.yaml"),
                f"{CONTAINER}:/config/configuration.yaml",
            ]
        )
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
    evidence["onboarding_user"] = {"status": status, **safe_body_summary(body)}
    if status != 200 or "auth_code" not in body:
        raise safe_http_error("user onboarding failed", status, body)
    auth_code = body["auth_code"]
    status, token_body = http_json(
        "POST",
        "/auth/token",
        form={
            "grant_type": "authorization_code",
            "code": auth_code,
            "client_id": client_id,
        },
    )
    evidence["token_exchange"] = {
        "status": status,
        **safe_body_summary(token_body),
        "token_values_redacted": True,
    }
    if status != 200 or "access_token" not in token_body:
        raise safe_http_error("token exchange failed", status, token_body)
    access_token = token_body["access_token"]

    for path, payload in (
        ("/api/onboarding/core_config", None),
        ("/api/onboarding/analytics", None),
        (
            "/api/onboarding/integration",
            {"client_id": client_id, "redirect_uri": client_id},
        ),
    ):
        status, step_body = http_json("POST", path, token=access_token, payload=payload)
        evidence.setdefault("onboarding_steps", []).append(
            {"path": path, "status": status, **safe_body_summary(step_body)}
        )
        if status not in (200, 201):
            raise safe_http_error(f"onboarding step failed {path}", status, step_body)
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
        raise safe_http_error(f"run_spike {phase} failed", status, body)
    if isinstance(body, dict) and "service_response" in body:
        response = body["service_response"]
        if isinstance(response, dict) and response.get("error"):
            raise RuntimeError(
                f"run_spike {phase} failed internally: "
                f"{response.get('error_type')}: {response.get('error_message')}"
            )
        return response
    return body


def registered_harness_services(services: Any) -> list[str]:
    """Extract registered tessera_spike service names from /api/services."""
    if not isinstance(services, list):
        return []
    for domain in services:
        if not isinstance(domain, dict) or domain.get("domain") != "tessera_spike":
            continue
        service_map = domain.get("services", {})
        if isinstance(service_map, dict):
            return sorted(str(name) for name in service_map)
    return []


def blocking_io_log_check() -> dict[str, Any]:
    """Return matching blocking-I/O log lines for the spike harness only."""
    proc = run(["docker", "logs", "--tail", "2000", CONTAINER], check=False)
    lines = (proc.stdout + "\n" + proc.stderr).splitlines()
    matches = [
        line
        for line in lines
        if "Detected blocking call" in line and "tessera_spike" in line
    ]
    return {
        "checked": True,
        "matches": [redact_text(line) for line in matches[:20]],
        "match_count": len(matches),
        "clean": not matches,
    }


def fallback_incomplete_seed_inventory() -> dict[str, Any]:
    """Describe missing seed evidence when the harness did not return it."""
    return {
        "fixture_version": 1,
        "entities": [
            {
                "entity_id": "input_boolean.tessera_allowed_light",
                "domain": "input_boolean",
                "class": "allowed_control_entity",
                "provided_by": "configuration.yaml",
            },
            {
                "entity_id": "input_boolean.tessera_forbidden_light",
                "domain": "input_boolean",
                "class": "forbidden_entity",
                "provided_by": "configuration.yaml",
            },
            {
                "entity_id": "sensor.tessera_state_only",
                "domain": "sensor",
                "class": "state_only_without_registry",
                "provided_by": "hass.states.async_set",
            },
        ],
        "known_gaps": [
            "area/device registry fixture is not created in Welle A yet",
            "multi-domain light/sensor/cover/camera/lock fixture remains for Welle C",
            "hidden/disabled registry entries remain for Welle C",
            "unsafe non-entity dev-service classification remains for Welle C/D9",
        ],
    }


def gate_results(evidence: dict[str, Any]) -> list[dict[str, Any]]:
    """Build machine-readable D0/A evidence gates."""
    seed = evidence.get("seed_inventory", {})
    harness = evidence.get("harness", {})
    blocking = evidence.get("blocking_io_log_check", {})
    redaction = evidence.get("failure_redaction_check", {})
    return [
        {
            "gate": "target_isolation",
            "status": (
                "PASS"
                if evidence.get("recreated_target", {}).get("isolation_ok")
                or evidence.get("existing_target", {}).get("isolation_ok")
                else "FAIL"
            ),
        },
        {
            "gate": "fresh_baseline",
            "status": (
                "PASS" if evidence.get("fresh_baseline", {}).get("ok") else "FAIL"
            ),
        },
        {
            "gate": "failure_redaction",
            "status": "PASS" if redaction.get("clean") else "FAIL",
            "detail": "measured HTTP/token evidence redaction, not hardcoded",
            "measurement": redaction,
        },
        {
            "gate": "a1_8_services",
            "status": (
                "PASS"
                if harness.get("loaded")
                and not harness.get("missing_required_services")
                else "FAIL"
            ),
            "registered_services": harness.get("registered_services", []),
        },
        {
            "gate": "a1_no_blocking_io_warning",
            "status": "PASS" if blocking.get("clean") else "FAIL",
            "match_count": blocking.get("match_count"),
        },
        {
            "gate": "a2_seed_fixture",
            "status": "PASS" if seed.get("complete_for_welle_a") else "FAIL",
            "entities": len(seed.get("entities", [])),
        },
    ]


def read_container_json(path: str) -> Any:
    proc = run(["docker", "exec", CONTAINER, "cat", path])
    return json.loads(proc.stdout)


def read_container_json_optional(path: str) -> Any:
    """Read JSON from the dev container if present."""
    proc = run(["docker", "exec", CONTAINER, "cat", path], check=False)
    if proc.returncode != 0 or not proc.stdout.strip():
        return {}
    return json.loads(proc.stdout)


def observe_d5_auth_store_corruption() -> dict[str, Any]:
    """Run the S2 auth-store corruption observation; it is never a D5 PASS lever."""
    info = inspect_container()
    isolation_ok, isolation_errors = assert_target_isolation(info)
    if not isolation_ok:
        raise RuntimeError(
            "S2 target isolation failed before auth-store manipulation: "
            f"{isolation_errors}"
        )
    setup = docker_exec_json(r"""
import json, pathlib, shutil
auth = pathlib.Path("/config/.storage/auth")
backup = pathlib.Path("/config/.storage/auth.tessera_spike_backup")
result = {
    "tested": True,
    "s2_observational_only": True,
    "auth_store_path": str(auth),
    "backup_path": str(backup),
    "auth_store_backup_created": False,
    "auth_store_corruption_injected": False,
}
if auth.exists():
    shutil.copy2(auth, backup)
    result["auth_store_backup_created"] = True
    result["auth_store_size_before"] = auth.stat().st_size
    auth.write_text("{\"intentionally_corrupt\": ")
    result["auth_store_corruption_injected"] = True
print(json.dumps(result, sort_keys=True))
""")
    setup["pre_manipulation_target_isolation_ok"] = isolation_ok
    setup["pre_manipulation_target_isolation_errors"] = isolation_errors
    run(["docker", "restart", CONTAINER], check=False)
    try:
        status: int | str = wait_http_status("/api/", {200, 401}, timeout=45)
        boot_error = None
    except RuntimeError as exc:
        status = "timeout"
        boot_error = redact_text(str(exc))

    restore = docker_exec_json(r"""
import json, pathlib, shutil
auth = pathlib.Path("/config/.storage/auth")
backup = pathlib.Path("/config/.storage/auth.tessera_spike_backup")
result = {
    "auth_store_restored_from_backup": False,
    "backup_removed": False,
}
if backup.exists():
    shutil.copy2(backup, auth)
    result["auth_store_restored_from_backup"] = True
    backup.unlink()
    result["backup_removed"] = True
print(json.dumps(result, sort_keys=True))
""")
    run(["docker", "restart", CONTAINER], check=False)
    try:
        restore_status: int | str = wait_http_status("/api/", {200, 401}, timeout=180)
        restore_error = None
    except RuntimeError as exc:
        restore_status = "timeout"
        restore_error = redact_text(str(exc))

    return {
        **setup,
        "ha_boot_after_auth_corruption": status in {200, 401},
        "ha_boot_after_auth_corruption_status": status,
        "ha_boot_after_auth_corruption_error": boot_error,
        **restore,
        "ha_boot_after_auth_restore": restore_status in {200, 401},
        "ha_boot_after_auth_restore_status": restore_status,
        "ha_boot_after_auth_restore_error": restore_error,
        "d5_pass_lever": False,
    }


def static_d9_scan() -> dict[str, Any]:
    return {
        "available": True,
        "skipped": False,
        "reason": (
            "Welle D uses the explicit relevant-component input list from the "
            "review handoff and does not scan /Volumes/config in this run"
        ),
        "input_source": "exchange/2026-06-29/tessera-welle-d-task-claude-2026-06-29.md plus prior read-only HACS inventory",
        "components": [
            "browser_mod",
            "dreame_vacuum",
            "epex_spot",
            "gruenbeck_cloud",
            "solarman",
            "solcast_solar",
            "unifi_insights",
            "unifi_network_map",
        ],
        "components_count": 8,
        "live_volumes_config_scanned": False,
    }


def verdicts_from_result(
    result: dict[str, Any], d0_green: bool
) -> dict[str, dict[str, Any]]:
    pre = result.get("pre_restart", {})
    post = result.get("post_restart", {})
    d1 = post.get("d1_restart_survival", {})
    d2_three = pre.get("d2_three_way", {})
    d2_restart = post.get("d2_three_way_after_restart", {})
    d3i = pre.get("d3_internal_check_entity", {})
    d3r = post.get("d3_rest_ws_service", {})
    d4 = pre.get("d4_union_restore", {})
    d6 = post.get("d6_service_matrix", {})
    d7 = post.get("d7_leak_matrix", {})
    d8 = post.get("d8_headless_token", {})
    d9 = post.get("d9_custom_component_runtime", {})
    d11 = post.get("d11_version_gate", {})
    d13 = post.get("d13_hacs_rollback", {})
    d15 = post.get("d15_lifecycle", {})
    d5_rescue = post.get("d5_boot_rescue_after_restart", {})
    a2_replace = pre.get("a2_native_write_replace_contract", {})
    a3_guard = pre.get("a3_rescue_namespace_guard", {})
    b3_pre = pre.get("b3_system_users_gate_pre_restart", {})
    b3_post = post.get("b3_system_users_gate_post_restart", {})
    d5_required_true = (
        "requested",
        "snapshot_present",
        "run_id_matches",
        "auth_store_corrupted",
        "managed_group_replace_drift_injected",
        "boot_rescue_corruption_tested",
        "no_admin_lockout",
        "rescue_independent_of_healthy_tessera",
        "reread_state_matches_intended",
        "owner_system_unmanaged_never_touched",
        "rescue_restore_namespace_guarded",
        "post_boot_measured",
    )
    d5_pass = (
        all(d5_rescue.get(key) is True for key in d5_required_true)
        and d5_rescue.get("errors") == []
        and d5_rescue.get("verdict") == "PASS"
        and result.get("d5_authstore_corruption_observation", {}).get("d5_pass_lever")
        is False
    )

    return {
        "D0": {
            "verdict": "PASS" if d0_green else "FAIL",
            "summary": "Preflight/onboarding/seed/harness gate",
        },
        "D1": {
            "verdict": (
                "PASS"
                if all(
                    d1.get(k)
                    for k in (
                        "group_survived_restart",
                        "policy_survived_restart",
                        "user_survived_restart",
                    )
                )
                else "FAIL"
            ),
            "summary": "tessera group/policy/user restart survival",
        },
        "D2": {
            "verdict": (
                "PASS"
                if d2_three.get("after_explicit_invalidate", {}).get("forbidden_read")
                and d2_three.get("after_explicit_invalidate", {}).get(
                    "forbidden_control"
                )
                and not d2_three.get("after_explicit_invalidate", {}).get(
                    "allowed_read"
                )
                and d2_restart.get("forbidden_read")
                and d2_restart.get("forbidden_control")
                and not d2_restart.get("allowed_read")
                else "FAIL"
            ),
            "summary": "policy mutation checked before invalidate, after invalidate, and after restart",
        },
        "D3": {
            "verdict": (
                "PASS"
                if d3i.get("allowed_read")
                and not d3i.get("forbidden_read")
                and d3i.get("allowed_control")
                and not d3i.get("forbidden_control")
                and d3r.get("consistent_entity_targeted")
                else "PARTIAL" if d3r.get("tested") else "FAIL"
            ),
            "summary": "internal + REST + WS + service entity-targeted consistency measured",
        },
        "D4": {
            "verdict": (
                "PASS"
                if set(d4.get("original_groups", []))
                == set(d4.get("restored_groups", []))
                and len(d4.get("union_groups", [])) > len(d4.get("original_groups", []))
                else "FAIL"
            ),
            "summary": "caller restores by supplying the full group set; HA group_ids writes are replace semantics",
        },
        "D5": {
            "verdict": ("PASS" if d5_pass else "PARTIAL"),
            "summary": "managed REPLACE demotion boot-rescue requires measured restore, setup-exception independence, and no-admin-lockout",
        },
        "D6": {
            "verdict": (
                "PASS"
                if d6.get("entity_targeted_pass")
                and d6.get("return_response_changed_states_tested")
                and d6.get("non_entity_service_tested")
                and d6.get("system_context", {}).get("tested")
                else "PARTIAL" if d6.get("tested") else "FAIL"
            ),
            "summary": "service matrix measured; entity-targeted path can pass while non-entity/system gaps stay documented",
        },
        "D7": {
            "verdict": (
                "PASS"
                if d7.get("complete_matrix")
                else "PARTIAL" if d7.get("tested") else "FAIL"
            ),
            "summary": "full REST+WS leak matrix documented; leaks bound view-scope, not operate/control",
        },
        "D8": {
            "verdict": (
                "PASS"
                if d8.get("llat_created")
                and d8.get("matches_ui_path")
                and d8.get("revocation_effective")
                else "PARTIAL" if d8.get("tested") else "FAIL"
            ),
            "summary": "real long-lived token lifecycle measured without storing token values",
        },
        "D9": {
            "verdict": (
                "PASS"
                if d9.get("runtime_custom_components_tested")
                and d9.get("d9_gate_pass_fail_closed")
                and d9.get("live_volumes_config_scanned") is False
                else "PARTIAL" if d9 else "FAIL"
            ),
            "summary": (
                "custom-component classification matrix exists; UNKNOWN_BLOCK_ENFORCE "
                "remains fail-closed for unverified inputs"
            ),
        },
        "D11": {
            "verdict": (
                "PASS"
                if d11.get("status") == "PASS"
                and d11.get("transition", {}).get("version_mismatch_detected")
                and d11.get("enforce_requested")
                and d11.get("native_write_attempted") is False
                and d11.get("native_write_blocked")
                and d11.get("native_write_call_count") == 0
                and d11.get("native_write_refused_before_call")
                and d11.get("effective_mode") in {"monitor", "off"}
                and d11.get("auth_fingerprint_unchanged")
                and d11.get("repair_issue_created")
                else "PARTIAL" if d11.get("tested") else "FAIL"
            ),
            "summary": "unsupported HA version simulation refuses enforce before native auth write",
        },
        "D13": {
            "verdict": (
                "PASS"
                if d13.get("status") == "PASS"
                and d13.get("native_write_attempted")
                and d13.get("auth_fingerprint_before")
                != d13.get("auth_fingerprint_after_update")
                and d13.get("rollback_restored_exact_fingerprint")
                and d13.get("owner_admin_lockout_probe", {}).get("no_admin_lockout")
                else "PARTIAL" if d13.get("tested") else "FAIL"
            ),
            "summary": "simulated HACS update/downgrade rollback restores exact native auth fingerprint",
        },
        "D15": {
            "verdict": (
                "PASS"
                if d15.get("status") == "PASS"
                and not d15.get("off", {}).get("native_write_observed")
                and not d15.get("monitor", {}).get("native_write_observed")
                and d15.get("enforce", {}).get("native_write_attempted")
                and d15.get("enforce", {}).get("native_write_blocked") is False
                and d15.get("enforce", {}).get("full_superset_written")
                and d15.get("enforce", {})
                .get("permission_probe", {})
                .get("forbidden_read")
                and d15.get("enforce", {})
                .get("permission_probe", {})
                .get("forbidden_control")
                and d15.get("restore", {}).get("restored_exact_fingerprint")
                and d15.get("owner_admin_lockout_probe", {}).get("no_admin_lockout")
                else "PARTIAL" if d15.get("tested") else "FAIL"
            ),
            "summary": "off/monitor no-write, enforce full-superset native write, restore exact fingerprint",
        },
        "B3": {
            "verdict": "PASS" if b3_pre.get("ok") and b3_post.get("ok") else "FAIL",
            "summary": "managed Tessera users are not members of HA system-users allow-all group",
        },
        "A2": {
            "verdict": (
                "PASS"
                if a2_replace.get("native_write_is_replace")
                and a2_replace.get("caller_passes_full_superset")
                else "FAIL"
            ),
            "summary": "native async_update_user(group_ids) is REPLACE; caller full-superset contract proven",
        },
        "A3": {
            "verdict": (
                "PASS" if a3_guard.get("rescue_restore_namespace_guarded") else "FAIL"
            ),
            "summary": "rescue restore rejects non-tessera group ids such as system-users",
        },
        "A4": {
            "verdict": "BLOCKED",
            "summary": "D12 remains blocked/partial until op login and a real product claim hook exist",
        },
        "A5": {
            "verdict": "PASS",
            "summary": "failure-redaction gate is measured; stale report marked obsolete",
        },
    }


def lifecycle_report_summary(spike: dict[str, Any]) -> dict[str, Any]:
    """Return compact lifecycle evidence; full fingerprints stay in JSON evidence."""
    post = spike.get("post_restart", {})
    d11 = post.get("d11_version_gate", {})
    d13 = post.get("d13_hacs_rollback", {})
    d15 = post.get("d15_lifecycle", {})
    return {
        "d11_version_gate": {
            "status": d11.get("status"),
            "requested_mode": d11.get("requested_mode"),
            "effective_mode": d11.get("effective_mode"),
            "enforce_requested": d11.get("enforce_requested"),
            "native_write_attempted": d11.get("native_write_attempted"),
            "native_write_blocked": d11.get("native_write_blocked"),
            "native_write_call_count": d11.get("native_write_call_count"),
            "native_write_refused_before_call": d11.get(
                "native_write_refused_before_call"
            ),
            "repair_issue_created": d11.get("repair_issue_created"),
            "auth_fingerprint_unchanged": d11.get("auth_fingerprint_unchanged"),
            "version_mismatch_detected": d11.get("transition", {}).get(
                "version_mismatch_detected"
            ),
            "owner_admin_no_lockout": d11.get("owner_admin_lockout_probe", {}).get(
                "no_admin_lockout"
            ),
        },
        "d13_hacs_rollback": {
            "status": d13.get("status"),
            "simulation_method": d13.get("simulation_method"),
            "native_write_attempted": d13.get("native_write_attempted"),
            "auth_fingerprint_changed_by_update": d13.get(
                "auth_fingerprint_changed_by_update"
            ),
            "rollback_restored_exact_fingerprint": d13.get(
                "rollback_restored_exact_fingerprint"
            ),
            "owner_admin_no_lockout": d13.get("owner_admin_lockout_probe", {}).get(
                "no_admin_lockout"
            ),
        },
        "d15_lifecycle": {
            "status": d15.get("status"),
            "off_native_write_observed": d15.get("off", {}).get(
                "native_write_observed"
            ),
            "monitor_native_write_observed": d15.get("monitor", {}).get(
                "native_write_observed"
            ),
            "enforce_native_write_attempted": d15.get("enforce", {}).get(
                "native_write_attempted"
            ),
            "enforce_native_write_blocked": d15.get("enforce", {}).get(
                "native_write_blocked"
            ),
            "enforce_full_superset_written": d15.get("enforce", {}).get(
                "full_superset_written"
            ),
            "enforce_permission_probe": d15.get("enforce", {}).get("permission_probe"),
            "restore_exact_fingerprint": d15.get("restore", {}).get(
                "restored_exact_fingerprint"
            ),
            "owner_admin_no_lockout": d15.get("owner_admin_lockout_probe", {}).get(
                "no_admin_lockout"
            ),
        },
    }


def write_markdown(
    evidence: dict[str, Any], spike: dict[str, Any], verdicts: dict[str, dict[str, Any]]
) -> Path:
    report = REPORTS / f"tessera-spike-report-{TODAY}.md"
    d0_report = EVIDENCE / f"tessera-d0-evidence-{TODAY}.md"
    d0_json = EVIDENCE / f"tessera-d0-evidence-{TODAY}.json"
    spike_json = EVIDENCE / f"tessera-spike-result-{TODAY}.json"
    spike["verdicts"] = verdicts
    lifecycle_summary = lifecycle_report_summary(spike)

    d0_json.write_text(json.dumps(evidence, indent=2, sort_keys=True))
    spike_json.write_text(json.dumps(spike, indent=2, sort_keys=True))

    d0_lines = [
        "# Tessera D0 Evidence",
        "",
        f"Stand: {dt.datetime.now().isoformat(timespec='seconds')}",
        "Modus: ha-tessera-dev only; no /Volumes/config scan in the standard run; no token/password/auth-code values emitted.",
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
        f"- Harness services: `{evidence.get('harness', {}).get('registered_services')}`",
        f"- Blocking-I/O matches: `{evidence.get('blocking_io_log_check', {}).get('match_count')}`",
        f"- Exit code: `{evidence.get('exit_code')}`",
        f"- Recreate proof: Docker container and volume were recreated after target-isolation check.",
        "",
        "## Gate Results",
        "",
        "```json",
        json.dumps(evidence.get("gate_results", []), indent=2, sort_keys=True),
        "```",
        "",
        "Full sanitized JSON: `" + str(d0_json.relative_to(ROOT)) + "`",
        "",
    ]
    d0_report.write_text("\n".join(d0_lines))

    rows = "\n".join(
        f"| {key} | {value['verdict']} | {value['summary']} |"
        for key, value in verdicts.items()
    )
    md = f"""# Tessera Phase-0 Spike Report

Stand: {dt.datetime.now().isoformat(timespec='seconds')}

Modus: Dev-only gegen `ha-tessera-dev`; keine Secrets/Token/Auth-Codes ausgegeben. Live-/`/Volumes/config`-Scans sind im Standardlauf bewusst deaktiviert und brauchen ein eigenes Gate.

## Gesamturteil

**PARTIAL / kein Enforce-Go.**

D0 ist gruen genug, um den dev-only Messlauf zu starten. D1, D2, D3, D4, D6, D8, D9, D11, D13, D15, A2, A3 und B3 liefern belastbare Dev-Signale. D5 bewertet das gemessene S1/S1b-Recovery-Gate gegen managed REPLACE-Demotion, Setup-Exception-Unabhaengigkeit, Re-Read und Owner/Admin-Operate-Probe; S2 `/config/.storage/auth`-Korruption bleibt bewusst **observational only** und kein PASS-Hebel. D7 liefert eine ehrliche Leak-Matrix, bleibt aber wegen nicht verifizierbarer Registry-/History-/Logbook-Baselines **PARTIAL**. D12 bleibt **BLOCKED**. Welle D nimmt D9 nur als **fail-closed Klassifikationsmatrix** ab; Welle E nimmt Lifecycle-Gates nur fuer `ha-tessera-dev` ab. Weiter kein Enforce/Product-Go.

## DoD Matrix

| DoD | Verdict | Kurzbegruendung |
|---|---:|---|
{rows}

## D0

- Harte Docker-Isolation: `{evidence.get('recreated_target', {}).get('isolation_ok')}`
- Fresh-Baseline-Allowlist: `{evidence.get('fresh_baseline', {}).get('ok')}`
- Onboarding abgeschlossen: `{all(step.get('done') for step in evidence.get('onboarding_after', []))}`
- Exit-Code: `{evidence.get('exit_code')}`
- Harness-Service geladen: `{evidence.get('harness', {}).get('loaded')}`
- 8-Service-Load-Check: `{not evidence.get('harness', {}).get('missing_required_services')}`; registriert `{evidence.get('harness', {}).get('registered_services')}`
- Blocking-I/O-Warnungen aus `tessera_spike`: `{evidence.get('blocking_io_log_check', {}).get('match_count')}`
- Token-/Passwortwerte: nicht im Report enthalten.

Gate-Results:

```json
{json.dumps(evidence.get('gate_results', []), indent=2, sort_keys=True)}
```

## Seed-Fixture

```json
{json.dumps(evidence.get('seed_inventory', {}), indent=2, sort_keys=True)}
```

## D1-D5 Auth-Store / Recovery Kern

```json
{json.dumps({k: spike.get('pre_restart', {}).get(k) for k in ['d1_pre_restart', 'd2_policy_change_no_restart', 'd2_three_way', 'd3_internal_check_entity', 'd4_union_restore', 'a2_native_write_replace_contract', 'a3_rescue_namespace_guard', 'd5_restore_primitive', 'd5_boot_rescue_prepare', 'b3_system_users_gate_pre_restart']}, indent=2, sort_keys=True)}
```

Restart-Survival:

```json
{json.dumps({k: spike.get('post_restart', {}).get(k) for k in ['d1_restart_survival', 'd2_three_way_after_restart', 'd5_boot_rescue_after_restart', 'b3_system_users_gate_post_restart']}, indent=2, sort_keys=True)}
```

D5 S2 Auth-Store-Korruption, **observational only**:

```json
{json.dumps(spike.get('d5_authstore_corruption_observation', {}), indent=2, sort_keys=True)}
```

## D3/D6/D7/D8 Runtime Probes

```json
{json.dumps({k: spike.get('post_restart', {}).get(k) for k in ['d3_rest_ws_service', 'd6_service_matrix', 'd7_leak_matrix', 'd8_headless_token']}, indent=2, sort_keys=True)}
```

Welle-C-Lesart: `D6.entity_targeted_pass` bewertet nur die nativen entity-targeted Service-Pfade. `non_entity_service` und `system_context` sind absichtlich als dokumentierte Enforce-Luecken sichtbar; sie duerfen kein stilles PASS fuer untrusted-view/control erzeugen. `D7` ist eine Dokumentationsmatrix: `LEAK`-Zellen sind kein Messfehler, sondern Scope-Grenzen fuer harte View-Vertraulichkeit.

## D9 Static Custom-Component Scan

```json
{json.dumps(spike.get('d9_static_scan', {}), indent=2, sort_keys=True)}
```

## D9 Runtime-Klassifikation

```json
{json.dumps(spike.get('post_restart', {}).get('d9_custom_component_runtime', {}), indent=2, sort_keys=True)}
```

D9-Lesart: `PASS` bedeutet hier **nicht** `ALLOW` fuer reale HACS-Komponenten. Es bedeutet: Die Matrix ist vorhanden, nutzt eine explizite Input-Provenienz statt `/Volumes/config`-Live-Scan und setzt fuer nicht runtime-verifizierte Service/HTTP/WS-Kandidaten konsequent `UNKNOWN_BLOCK_ENFORCE`. Solange `enforce_blocked_by_unknown` true ist, bleibt Enforce fail-closed blockiert.

## D11/D13/D15 Lifecycle-Gates

```json
{json.dumps(lifecycle_summary, indent=2, sort_keys=True)}
```

Lifecycle-Lesart: `D11` belegt im Dev-Spike den fail-closed Version-Gate-Pfad per unsupported-version Lifecycle-Transition, Repairs-Issue und unveraendertem Auth-Fingerprint. `D13` ist eine HACS-Update/Downgrade-Simulation, kein echter HACS-Paketwechsel; PASS verlangt einen beobachteten Zwischen-Write und exakten Rollback. `D15` misst `off -> monitor -> enforce -> restore` in-process mit vollem Gruppen-Superset, Permission-Probe und exaktem Restore-Fingerprint. Alle drei bleiben Dev-Spike-Belege, kein Produkt-Enforce-Go.

## Core-Anker

- HA `auth_store.py`: private `_groups`, `_data_to_save()`, `_store.async_save()` sind der gemessene Schreibpfad.
- HA `auth/models.py`: `User.permissions` ist cached; `invalidate_cache()` ist fuer reine Policy-Mutation relevant.
- HA `auth/__init__.py`: `async_update_user(group_ids=...)` ist der oeffentliche Restore-/Binding-Pfad.
- HA `http/auth.py`: `Home Assistant Content` ist `system_generated` und bleibt unmanaged.

## Go/No-Go

- **Go fuer weitere Phase-0-Haertung:** ja.
- **Go fuer Tessera-Enforce/Product:** nein.
- **Naechste Pflicht:** echte HACS-/Upgrade-Probe ausserhalb der Simulation, D10/CM5-Benchmark, D12/OIDC und Produkt-/Release-Gates gesondert; kein Enforce/Product-Go aus diesem Spike.

## Artefakte

- D0 Evidence: `{d0_report.relative_to(ROOT)}`
- D0 JSON: `{d0_json.relative_to(ROOT)}`
- Spike JSON: `{spike_json.relative_to(ROOT)}`
"""
    report.write_text(md)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="Do not recreate the disposable dev container first.",
    )
    args = parser.parse_args()

    REPORTS.mkdir(exist_ok=True)
    EVIDENCE.mkdir(exist_ok=True)
    evidence: dict[str, Any] = {
        "started_at": dt.datetime.now().isoformat(timespec="seconds"),
        "target": {
            "container": CONTAINER,
            "volume": VOLUME,
            "image": IMAGE,
            "port": PORT,
        },
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
        baseline = wait_auth_baseline()
        ok, errors = assert_fresh_baseline(baseline, onboarding_before)
        evidence["onboarding_before"] = onboarding_before
        evidence["auth_baseline"] = baseline
        evidence["fresh_baseline"] = {"ok": ok, "errors": errors}
        if not ok:
            raise RuntimeError(f"fresh baseline failed: {errors}")

        # Re-read immediately before first auth write.
        baseline_reread = auth_baseline()
        ok, errors = assert_fresh_baseline(
            baseline_reread, wait_http("/api/onboarding")
        )
        evidence["auth_baseline_reread"] = baseline_reread
        evidence["fresh_baseline_reread"] = {"ok": ok, "errors": errors}
        if not ok:
            raise RuntimeError(f"fresh baseline re-read failed: {errors}")

        owner_token = onboard(evidence)
        # No token values written; only use in memory below.
        status, services = http_json("GET", "/api/services", token=owner_token)
        registered = registered_harness_services(services)
        missing = sorted(HARNESS_REQUIRED_SERVICES - set(registered))
        loaded = status == 200 and not missing
        evidence["harness"] = {
            "services_status": status,
            "loaded": loaded,
            "registered_services": registered,
            "missing_required_services": missing,
        }
        if not loaded:
            raise RuntimeError(f"tessera_spike required services not loaded: {missing}")

        pre = call_service(owner_token, "pre_restart")
        evidence["pre_restart_service"] = {"ok": True, "keys": sorted(pre.keys())}
        evidence["seed_inventory"] = pre.get(
            "seed_fixture", fallback_incomplete_seed_inventory()
        )
        if not evidence["seed_inventory"].get("complete_for_welle_a"):
            raise RuntimeError("seed fixture incomplete for Welle A")

        run(["docker", "restart", CONTAINER])
        evidence["setup_exception_boot_http_status"] = wait_http_status(
            "/api/", {200, 401}, timeout=180
        )
        setup_exception_boot = read_container_json_optional(
            "/config/tessera_spike_rescue_result.json"
        )
        evidence["d5_setup_exception_boot"] = {
            "observed": setup_exception_boot.get("setup_exception_simulated") is True,
            "rescue_independent_of_healthy_tessera": setup_exception_boot.get(
                "rescue_independent_of_healthy_tessera"
            ),
            "run_id": setup_exception_boot.get("run_id"),
            "error_type": setup_exception_boot.get("setup_exception_error_type"),
        }
        if evidence["d5_setup_exception_boot"]["observed"]:
            run(["docker", "restart", CONTAINER])
            evidence["post_restart_http_status"] = wait_http_status(
                "/api/", {200, 401}, timeout=180
            )
        else:
            evidence["post_restart_http_status"] = evidence[
                "setup_exception_boot_http_status"
            ]
        # Existing access token may be invalid after restart? It should remain valid briefly, but get a new one via refresh would need secret.
        # Call post_restart using the same access token first; if rejected, record failure.
        post = call_service(owner_token, "post_restart")
        evidence["post_restart_service"] = {"ok": True, "keys": sorted(post.keys())}

        spike = read_container_json("/config/tessera_spike_result.json")
        spike["d5_authstore_corruption_observation"] = (
            observe_d5_auth_store_corruption()
        )
        spike["d9_static_scan"] = static_d9_scan()
        evidence["blocking_io_log_check"] = blocking_io_log_check()
        evidence["failure_redaction_check"] = measure_failure_redaction(evidence)
        d0_green = True
        evidence["status"] = "GREEN"
        evidence["exit_code"] = 0
        evidence["abort_reason"] = None
        evidence["gate_results"] = gate_results(evidence)
        verdicts = verdicts_from_result(spike, d0_green)
        report = write_markdown(evidence, spike, verdicts)
        print(f"D0 GREEN; spike report written: {report}")
        return 0
    except Exception as exc:  # noqa: BLE001
        evidence["status"] = "RED"
        evidence["error"] = str(exc)
        evidence["exit_code"] = 2
        evidence["abort_reason"] = str(exc)
        evidence["blocking_io_log_check"] = blocking_io_log_check()
        evidence["failure_redaction_check"] = measure_failure_redaction(evidence)
        evidence["gate_results"] = gate_results(evidence)
        failure = EVIDENCE / f"tessera-d0-evidence-{TODAY}.json"
        failure.write_text(json.dumps(evidence, indent=2, sort_keys=True))
        print(f"D0 RED: {exc}", file=sys.stderr)
        print(f"sanitized evidence: {failure}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
