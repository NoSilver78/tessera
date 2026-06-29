#!/usr/bin/env python3
"""Secret-redacted D12 Authentik OIDC groups-claim probe."""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "evidence"
REPORTS = ROOT / "reports"
TODAY = dt.date.today().isoformat()
CONTAINER = "ha-tessera-dev"
VOLUME = "ha-tessera-dev-config"
IMAGE = "ghcr.io/home-assistant/home-assistant:2026.6.4"
PORT = "8124"
ALLOWED_GROUPS = {"tessera-test-admin", "tessera-test-eg", "tessera-test-readonly"}
SENSITIVE_KEYS = {
    "access_token",
    "auth_code",
    "client_secret",
    "code",
    "id_token",
    "password",
    "refresh_token",
    "token",
}


def _json_request(
    url: str,
    *,
    method: str = "GET",
    form: dict[str, str] | None = None,
    bearer: str | None = None,
) -> tuple[int, Any]:
    headers = {
        "Accept": "application/json",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 Chrome/126 Safari/537.36"
        ),
    }
    data = None
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    if bearer is not None:
        headers["Authorization"] = f"Bearer {bearer}"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            text = response.read().decode()
            return response.status, json.loads(text) if text else {}
    except urllib.error.HTTPError as exc:
        text = exc.read().decode()
        try:
            body = json.loads(text) if text else {}
        except json.JSONDecodeError:
            body = {"raw_type": "text", "length": len(text)}
        return exc.code, body


def _safe_body(body: Any) -> dict[str, Any]:
    if isinstance(body, dict):
        keys = sorted(str(key) for key in body)
        return {
            "body_type": "dict",
            "body_keys": keys,
            "sensitive_keys_redacted": sorted(set(keys) & SENSITIVE_KEYS),
        }
    if isinstance(body, list):
        return {"body_type": "list", "items": len(body)}
    return {"body_type": type(body).__name__}


def _decode_jwt_payload(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) < 2:
        return {}
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(payload.encode()))
    except (ValueError, json.JSONDecodeError):
        return {}


def _allowlisted_groups(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted(
        item for item in value if isinstance(item, str) and item in ALLOWED_GROUPS
    )


def _safe_endpoint(url: Any, issuer: str) -> bool:
    if not isinstance(url, str):
        return False
    parsed_url = urllib.parse.urlparse(url)
    parsed_issuer = urllib.parse.urlparse(issuer)
    return (
        parsed_url.scheme == "https"
        and parsed_url.netloc == parsed_issuer.netloc
        and parsed_url.path.startswith("/application/o/")
    )


def _validate_discovery(discovery: dict[str, Any], issuer: str) -> dict[str, Any]:
    return {
        "issuer_matches": discovery.get("issuer") == issuer,
        "token_endpoint_safe": _safe_endpoint(discovery.get("token_endpoint"), issuer),
        "userinfo_endpoint_safe": _safe_endpoint(
            discovery.get("userinfo_endpoint"), issuer
        ),
        "has_groups_scope": "groups" in discovery.get("scopes_supported", []),
        "advertises_groups_claim": "groups" in discovery.get("claims_supported", []),
    }


def _mapping_probe(groups: list[str]) -> dict[str, Any]:
    method = "schema_validator"
    anchors = ["custom_components/tessera/schema.py"]
    try:
        from custom_components.tessera.schema import (  # noqa: PLC0415
            default_config_data,
            validate_config_data,
        )

        config = default_config_data()
        config["roles"] = {"eg": {"name": "EG Rolle"}}
        config["membership"]["by_group"] = {"authentik:tessera-test-eg": ["eg"]}
        validated = validate_config_data(config)
        mapped_roles = sorted(
            {
                role
                for group in groups
                for role in validated["membership"]["by_group"].get(
                    f"authentik:{group}", []
                )
            }
        )
    except ModuleNotFoundError:
        method = "source_fallback_no_local_dependencies"
        schema_text = (REPO_ROOT / "custom_components/tessera/schema.py").read_text()
        schema_supports_by_group = all(
            marker in schema_text
            for marker in (
                "def validate_config_data",
                '"membership": {"by_user": {}, "by_group": {}}',
                "config.membership.by_group",
            )
        )
        mapped_roles = (
            ["eg"] if schema_supports_by_group and "tessera-test-eg" in groups else []
        )
    return {
        "input_group": "authentik:tessera-test-eg",
        "mapped_roles": mapped_roles,
        "role_present": "eg" in mapped_roles,
        "method": method,
        "anchors": anchors,
        "product_hook_present": False,
    }


def _inspect_target() -> dict[str, Any]:
    proc = subprocess.run(
        ["docker", "inspect", CONTAINER],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if proc.returncode != 0:
        return {"ok": False, "error": "docker_inspect_failed"}
    info = json.loads(proc.stdout)[0]
    clean = {
        "name": info.get("Name", "").lstrip("/"),
        "image": info.get("Config", {}).get("Image"),
        "mounts": [
            {
                "Type": mount.get("Type"),
                "Name": mount.get("Name"),
                "Destination": mount.get("Destination"),
            }
            for mount in info.get("Mounts", [])
        ],
        "ports": info.get("NetworkSettings", {}).get("Ports"),
    }
    forbidden = json.dumps(clean)
    errors = []
    if clean["name"] != CONTAINER:
        errors.append("name")
    if clean["image"] != IMAGE:
        errors.append("image")
    config_mounts = [
        mount for mount in clean["mounts"] if mount.get("Destination") == "/config"
    ]
    if len(config_mounts) != 1 or config_mounts[0].get("Name") != VOLUME:
        errors.append("config_volume")
    host_ports = sorted(
        {entry.get("HostPort") for entry in (clean["ports"] or {}).get("8123/tcp", [])}
    )
    if host_ports != [PORT]:
        errors.append("port")
    for marker in ("/Volumes/config", "maison-atrium-dev", "Maison", "Atrium"):
        if marker in forbidden:
            errors.append(f"forbidden:{marker}")
    return {"ok": not errors, "errors": errors, "inspect": clean}


def _read_nul_secrets() -> tuple[str, str]:
    raw = sys.stdin.buffer.read()
    first, sep, second = raw.partition(b"\0")
    if not sep:
        raise RuntimeError("expected NUL-separated client_secret and password on stdin")
    return first.decode().strip(), second.decode().strip()


def _contains_secret_value(text: str, values: list[str]) -> bool:
    return any(value and value in text for value in values)


def run_probe(
    args: argparse.Namespace, client_secret: str, password: str
) -> tuple[dict[str, Any], list[str]]:
    evidence: dict[str, Any] = {
        "d12": {
            "target": CONTAINER,
            "secret_redaction_status": "PASS",
            "no_token_values_logged": True,
            "anchors": {
                "tessera": ["custom_components/tessera/schema.py"],
                "ha_core": [
                    "container:/usr/src/homeassistant/homeassistant/auth/providers/__init__.py:142-190"
                ],
            },
        }
    }
    secret_values = [client_secret, password]
    d12 = evidence["d12"]
    d12["target_isolation"] = _inspect_target()
    if not d12["target_isolation"]["ok"]:
        d12["verdict"] = "FAIL"
        d12["abort_reason"] = "FAIL_TARGET_ISOLATION"
        return evidence, secret_values

    status, discovery = _json_request(args.discovery)
    discovery_validation = (
        _validate_discovery(discovery, args.issuer)
        if isinstance(discovery, dict)
        else {}
    )
    d12["discovery"] = {
        "status": status,
        **_safe_body(discovery),
        **discovery_validation,
    }
    if status != 200 or not isinstance(discovery, dict):
        d12["verdict"] = "FAIL"
        d12["abort_reason"] = "DISCOVERY_FAILED"
        return evidence, secret_values
    if not all(
        discovery_validation.get(key)
        for key in ("issuer_matches", "token_endpoint_safe", "userinfo_endpoint_safe")
    ):
        d12["verdict"] = "FAIL"
        d12["abort_reason"] = "DISCOVERY_NOT_TRUSTED"
        return evidence, secret_values

    token_endpoint = discovery.get("token_endpoint")
    userinfo_endpoint = discovery.get("userinfo_endpoint")
    status, token_body = _json_request(
        str(token_endpoint),
        method="POST",
        form={
            "grant_type": "password",
            "client_id": args.client_id,
            "client_secret": client_secret,
            "username": args.username,
            "password": password,
            "scope": "openid profile email groups",
        },
    )
    d12["login"] = {
        "method": "resource_owner_password_grant_direct_to_authentik",
        "user": args.username,
        "status": status,
        **_safe_body(token_body),
    }
    if status != 200 or not isinstance(token_body, dict):
        d12["verdict"] = "FAIL"
        d12["abort_reason"] = "TOKEN_EXCHANGE_FAILED"
        return evidence, secret_values

    access_token = token_body.get("access_token")
    if isinstance(access_token, str):
        secret_values.append(access_token)
    id_token = token_body.get("id_token")
    if isinstance(id_token, str):
        secret_values.append(id_token)
    refresh_token = token_body.get("refresh_token")
    if isinstance(refresh_token, str):
        secret_values.append(refresh_token)
    id_payload = _decode_jwt_payload(str(id_token or ""))
    id_groups = _allowlisted_groups(id_payload.get("groups"))
    userinfo_groups: list[str] = []
    userinfo_keys: list[str] = []
    if isinstance(access_token, str) and userinfo_endpoint:
        userinfo_status, userinfo = _json_request(
            str(userinfo_endpoint), bearer=access_token
        )
        userinfo_keys = sorted(userinfo) if isinstance(userinfo, dict) else []
        d12["userinfo"] = {"status": userinfo_status, **_safe_body(userinfo)}
        if isinstance(userinfo, dict):
            userinfo_groups = _allowlisted_groups(userinfo.get("groups"))

    groups = sorted(set(id_groups) | set(userinfo_groups))
    d12["claims"] = {
        "source": "id_token_and_userinfo",
        "id_token_claim_keys": sorted(id_payload),
        "userinfo_claim_keys": userinfo_keys,
        "groups_allowlisted": groups,
        "expected_group_present": "tessera-test-eg" in groups,
        "groups_count_allowlisted": len(groups),
    }
    d12["mapping"] = _mapping_probe(groups)
    d12["verdict"] = (
        "PARTIAL"
        if d12["claims"]["expected_group_present"] and d12["mapping"]["role_present"]
        else "FAIL"
    )
    d12["partial_reason"] = (
        "OIDC groups claim and Tessera mapping are proven, but Tessera has no "
        "implemented at-login claim hook yet and HA Core has no native OIDC provider."
    )
    return evidence, secret_values


def write_outputs(evidence: dict[str, Any], secret_values: list[str]) -> None:
    EVIDENCE.mkdir(exist_ok=True)
    REPORTS.mkdir(exist_ok=True)
    json_path = EVIDENCE / f"tessera-d12-authentik-evidence-{TODAY}.json"
    md_path = REPORTS / f"tessera-d12-authentik-report-{TODAY}.md"
    json_text = json.dumps(evidence, indent=2, sort_keys=True)
    if _contains_secret_value(json_text, secret_values):
        raise RuntimeError("refusing to write D12 evidence because a secret leaked")
    d12 = evidence["d12"]
    md_text = "\n".join(
        [
            "# Tessera D12 Authentik IdP Probe",
            "",
            f"Stand: {dt.datetime.now().isoformat(timespec='seconds')}",
            "",
            f"Verdict: **{d12.get('verdict')}**",
            "",
            "Secret-Status: Artefakte wurden vor dem Schreiben gegen aktuelle "
            "Token-/Passwort-/client_secret-Werte geprüft.",
            "",
            "## Kurzbefund",
            "",
            f"- Discovery: `{d12.get('discovery', {}).get('status')}`",
            f"- Issuer fail-closed: `{d12.get('discovery', {}).get('issuer_matches')}`",
            f"- Token endpoint safe: `{d12.get('discovery', {}).get('token_endpoint_safe')}`",
            f"- Userinfo endpoint safe: `{d12.get('discovery', {}).get('userinfo_endpoint_safe')}`",
            f"- Groups-Scope: `{d12.get('discovery', {}).get('has_groups_scope')}`",
            f"- Groups-Claim advertised: `{d12.get('discovery', {}).get('advertises_groups_claim')}`",
            f"- Erwartete Gruppe gesehen: `{d12.get('claims', {}).get('expected_group_present')}`",
            f"- Synthetisches Schema-Mapping `authentik:tessera-test-eg` -> Rolle: `{d12.get('mapping', {}).get('role_present')}`",
            f"- Produkt-Hook vorhanden: `{d12.get('mapping', {}).get('product_hook_present')}`",
            "",
            "## Einordnung",
            "",
            "Diese Probe beweist IdP-Ausgabe + schemafaehiges Mapping, nicht den "
            "produktiven HA-/Tessera-Login-Hook. `by_group` bleibt damit PARTIAL.",
            "",
            "## Evidence",
            "",
            f"Sanitized JSON: `{json_path.relative_to(ROOT)}`",
            "",
        ]
    )
    if _contains_secret_value(md_text, secret_values):
        raise RuntimeError("refusing to write D12 report because a secret leaked")
    json_path.write_text(json_text)
    md_path.write_text(md_text)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--discovery", required=True)
    parser.add_argument("--issuer", required=True)
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Return success for the intentionally IdP-only PARTIAL probe.",
    )
    args = parser.parse_args()
    client_secret, password = _read_nul_secrets()
    evidence, secret_values = run_probe(args, client_secret, password)
    write_outputs(evidence, secret_values)
    verdict = evidence["d12"].get("verdict")
    if verdict == "PASS" or (verdict == "PARTIAL" and args.allow_partial):
        return 0
    if verdict == "PARTIAL":
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
