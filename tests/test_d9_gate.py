"""Tests for Tessera's dormant D9 custom-component gate."""

from __future__ import annotations

import builtins
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import custom_components.tessera.d9_gate as d9_gate
import pytest
from custom_components.tessera.d9_classification import (
    D9_VERDICT_ALLOW,
    D9_VERDICT_DENY,
    D9_VERDICT_TIER_2,
    D9_VERDICT_UNKNOWN,
    D9ClassificationEntry,
)
from custom_components.tessera.d9_gate import compute_component_hash, evaluate_d9_gate
from custom_components.tessera.schema import (
    TesseraSchemaError,
    default_config_data,
    validate_config_data,
)


class FakeConfig:
    """Minimal HA config path helper."""

    def __init__(self, root: Path) -> None:
        """Initialize config root."""
        self._root = root

    def path(self, *parts: str) -> str:
        """Return a path under the fake config root."""
        return str(self._root.joinpath(*parts))


class FakeServices:
    """Minimal HA services registry fake."""

    def __init__(self, services: Mapping[str, object] | None = None) -> None:
        """Initialize service registry."""
        self._services = dict(services or {})

    def async_services(self) -> Mapping[str, object]:
        """Return fake registered services by domain."""
        return self._services


class FakeHass:
    """Minimal HA test double for D9."""

    def __init__(
        self, root: Path, services: Mapping[str, object] | None = None
    ) -> None:
        """Initialize fake HA state."""
        self.config = FakeConfig(root)
        self.services = FakeServices(services)
        self.executor_calls = 0

    async def async_add_executor_job(self, target: Any, *args: object) -> object:
        """Run executor jobs synchronously while recording the off-loop path."""
        self.executor_calls += 1
        return target(*args)


def _write_component(
    root: Path,
    domain: str,
    *,
    version: str | None = "1.0.0",
    py_source: str = "",
) -> Path:
    component = root / "custom_components" / domain
    component.mkdir(parents=True)
    manifest: dict[str, Any] = {"domain": domain, "name": domain}
    if version is not None:
        manifest["version"] = version
    (component / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    if py_source:
        (component / "__init__.py").write_text(py_source, encoding="utf-8")
    return component


def _config_with_ack(
    domain: str, *, version: str | None, content_hash: str
) -> dict[str, Any]:
    config = default_config_data()
    config["d9_acks"] = {
        domain: {
            "version": version,
            "content_hash": content_hash,
            "accepted_at": "2026-06-30T00:00:00Z",
        }
    }
    return config


@pytest.fixture(autouse=True)
def _mock_loader(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep D9 tests HA-free by mocking the loader entrypoint."""
    monkeypatch.setattr(
        d9_gate,
        "_async_get_custom_components",
        AsyncMock(return_value={}),
    )


async def test_generic_runtime_service_no_longer_hard_vetoes(tmp_path: Path) -> None:
    """D9 v2: a generic runtime service (no auth mutation) does not block enforce."""
    component = _write_component(tmp_path, "service_only")
    hass = FakeHass(tmp_path, {"service_only": {"do_it": object()}})

    result = await evaluate_d9_gate(hass, default_config_data())

    assert compute_component_hash(component)
    assert result["by_component"]["service_only"]["verdict"] == D9_VERDICT_ALLOW
    assert result["by_component"]["service_only"]["source"] == "default"
    assert result["blocking"] == []
    assert result["enforce_blocked"] is False
    assert hass.executor_calls == 1


async def test_generic_http_ws_surfaces_no_longer_block(tmp_path: Path) -> None:
    """D9 v2: generic View/WS surfaces (no auth mutation) no longer hard-veto."""
    _write_component(
        tmp_path,
        "ui_only",
        py_source=(
            "from homeassistant.components.http import HomeAssistantView\n"
            "async def async_setup(hass, config):\n"
            "    hass.http.register_view(HomeAssistantView())\n"
            "    hass.components.websocket_api.async_register_command(lambda: None)\n"
        ),
    )

    result = await evaluate_d9_gate(FakeHass(tmp_path), default_config_data())

    assert result["by_component"]["ui_only"]["verdict"] == D9_VERDICT_ALLOW
    assert result["blocking"] == []
    assert result["enforce_blocked"] is False


async def test_self_domain_is_excluded_despite_surfaces(tmp_path: Path) -> None:
    """Tessera's own domain is trusted and never D9-vetoes itself.

    Regression: Tessera legitimately registers a panel/service/websocket. Without
    excluding its own domain the surface hard-veto blocked enforce on every real
    install (caught by the ha-tessera-dev E2E).
    """
    _write_component(
        tmp_path,
        "tessera",
        py_source=(
            "from homeassistant.components.http import HomeAssistantView\n"
            "async def async_setup(hass, config):\n"
            "    hass.http.register_view(HomeAssistantView())\n"
            "    hass.components.websocket_api.async_register_command(lambda: None)\n"
        ),
    )

    result = await evaluate_d9_gate(
        FakeHass(tmp_path), default_config_data(), self_domain="tessera"
    )

    assert "tessera" not in result["by_component"]
    assert result["blocking"] == []
    assert result["enforce_blocked"] is False


async def test_ack_expires_when_content_hash_changes(tmp_path: Path) -> None:
    """A stale ack no longer overrides the auth-surface veto after a content change."""
    auth_a = "async def f(hass):\n    await hass.auth.async_update_user(None)\n"
    auth_b = (
        "async def f(hass):\n    await hass.auth.async_update_user(None)  # changed\n"
    )
    component = _write_component(tmp_path, "auth_mutable", py_source=auth_a)
    stale_hash = compute_component_hash(component)
    (component / "__init__.py").write_text(auth_b, encoding="utf-8")

    result = await evaluate_d9_gate(
        FakeHass(tmp_path),
        _config_with_ack("auth_mutable", version="1.0.0", content_hash=stale_hash),
    )

    assert result["by_component"]["auth_mutable"]["verdict"] == D9_VERDICT_UNKNOWN
    assert result["by_component"]["auth_mutable"]["source"] == "surface_veto"
    assert result["enforce_blocked"] is True


async def test_unknown_component_without_surfaces_defaults_to_allow(
    tmp_path: Path,
) -> None:
    """D9 v2: an unknown component without auth-relevant surfaces is trusted."""
    _write_component(tmp_path, "plain_component")

    result = await evaluate_d9_gate(FakeHass(tmp_path), default_config_data())

    assert result["by_component"]["plain_component"]["verdict"] == D9_VERDICT_ALLOW
    assert result["by_component"]["plain_component"]["source"] == "default"
    assert result["enforce_blocked"] is False


async def test_auth_mutating_component_is_vetoed(tmp_path: Path) -> None:
    """D9 v2 (E): a component that mutates the auth store hard-vetoes when un-acked."""
    _write_component(
        tmp_path,
        "auth_toucher",
        py_source=(
            "async def async_setup(hass, config):\n"
            "    await hass.auth.async_update_user(None, group_ids=[])\n"
        ),
    )

    result = await evaluate_d9_gate(FakeHass(tmp_path), default_config_data())

    assert result["by_component"]["auth_toucher"]["verdict"] == D9_VERDICT_UNKNOWN
    assert result["by_component"]["auth_toucher"]["source"] == "surface_veto"
    assert "auth_toucher" in result["blocking"]
    assert result["enforce_blocked"] is True


async def test_admin_ack_overrides_auth_surface_veto(tmp_path: Path) -> None:
    """D9 v2 (A): a content-hash-matched admin ack overrides the auth-surface veto."""
    component = _write_component(
        tmp_path,
        "acked_auth",
        py_source=(
            "async def async_setup(hass, config):\n"
            "    await hass.auth.async_update_user(None, group_ids=[])\n"
        ),
    )
    content_hash = compute_component_hash(component)

    result = await evaluate_d9_gate(
        FakeHass(tmp_path),
        _config_with_ack("acked_auth", version="1.0.0", content_hash=content_hash),
    )

    assert result["by_component"]["acked_auth"]["verdict"] == D9_VERDICT_ALLOW
    assert result["by_component"]["acked_auth"]["source"] == "ack"
    assert result["enforce_blocked"] is False


async def test_compiled_artifact_is_vetoed(tmp_path: Path) -> None:
    """D9 v2: un-analysable compiled code hard-vetoes (could hide auth mutation)."""
    component = _write_component(tmp_path, "compiled_component")
    (component / "ext.so").write_bytes(b"\x7fELF stub")

    result = await evaluate_d9_gate(FakeHass(tmp_path), default_config_data())

    assert result["by_component"]["compiled_component"]["verdict"] == D9_VERDICT_UNKNOWN
    assert result["by_component"]["compiled_component"]["source"] == "surface_veto"
    assert "compiled_component" in result["blocking"]


async def test_clean_component_allows_with_table_hash_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Clean component with pinned table entry and evidence can ALLOW."""
    component = _write_component(tmp_path, "clean_component")
    content_hash = compute_component_hash(component)
    monkeypatch.setattr(
        d9_gate,
        "CLASSIFICATIONS",
        {
            "clean_component": (
                D9ClassificationEntry(
                    version="1.0.0",
                    content_hash=content_hash,
                    verdict=D9_VERDICT_ALLOW,
                    evidence_type="no_surface_verified",
                    reason="fixture verified no surface",
                ),
            )
        },
    )

    result = await evaluate_d9_gate(FakeHass(tmp_path), default_config_data())

    assert result["by_component"]["clean_component"] == {
        "verdict": D9_VERDICT_ALLOW,
        "version": "1.0.0",
        "content_hash": content_hash,
        "source": "classification",
        "reason": "fixture verified no surface",
    }
    assert result["blocking"] == []
    assert result["enforce_blocked"] is False


async def test_table_version_mismatch_is_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Table trust anchor requires the pinned version as well as the hash."""
    component = _write_component(tmp_path, "version_mismatch", version="2.0.0")
    monkeypatch.setattr(
        d9_gate,
        "CLASSIFICATIONS",
        {
            "version_mismatch": (
                D9ClassificationEntry(
                    version="1.0.0",
                    content_hash=compute_component_hash(component),
                    verdict=D9_VERDICT_ALLOW,
                    evidence_type="no_surface_verified",
                    reason="stale version",
                ),
            )
        },
    )

    result = await evaluate_d9_gate(FakeHass(tmp_path), default_config_data())

    component_result = result["by_component"]["version_mismatch"]
    assert component_result["verdict"] == D9_VERDICT_ALLOW
    assert component_result["source"] == "default"


async def test_ack_version_none_vs_string_is_unknown(tmp_path: Path) -> None:
    """Ack version ``None`` must not match a concrete manifest version."""
    component = _write_component(tmp_path, "ack_version_mismatch", version="1.0.0")

    result = await evaluate_d9_gate(
        FakeHass(tmp_path),
        _config_with_ack(
            "ack_version_mismatch",
            version=None,
            content_hash=compute_component_hash(component),
        ),
    )

    component_result = result["by_component"]["ack_version_mismatch"]
    assert component_result["verdict"] == D9_VERDICT_ALLOW
    assert component_result["source"] == "default"


async def test_version_none_can_be_pinned_by_table(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Version-less components are handled explicitly, not stringified."""
    component = _write_component(tmp_path, "versionless", version=None)
    content_hash = compute_component_hash(component)
    monkeypatch.setattr(
        d9_gate,
        "CLASSIFICATIONS",
        {
            "versionless": (
                D9ClassificationEntry(
                    version=None,
                    content_hash=content_hash,
                    verdict=D9_VERDICT_ALLOW,
                    evidence_type="no_surface_verified",
                    reason="fixture allows versionless",
                ),
            )
        },
    )

    result = await evaluate_d9_gate(FakeHass(tmp_path), default_config_data())

    assert result["by_component"]["versionless"]["version"] is None
    assert result["by_component"]["versionless"]["verdict"] == D9_VERDICT_ALLOW


async def test_table_no_surface_anchor_rejects_auth_surface(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Anti-forgery: a no_surface_verified anchor must not trust an auth surface."""
    component = _write_component(
        tmp_path,
        "mutated_allow",
        py_source=(
            "async def async_setup(hass, config):\n"
            "    await hass.auth.async_update_user(None, group_ids=[])\n"
        ),
    )
    monkeypatch.setattr(
        d9_gate,
        "CLASSIFICATIONS",
        {
            "mutated_allow": (
                D9ClassificationEntry(
                    version="1.0.0",
                    content_hash=compute_component_hash(component),
                    verdict=D9_VERDICT_ALLOW,
                    evidence_type="no_surface_verified",
                    reason="stale fixture allow",
                ),
            )
        },
    )

    result = await evaluate_d9_gate(FakeHass(tmp_path), default_config_data())

    assert result["by_component"]["mutated_allow"]["verdict"] == D9_VERDICT_UNKNOWN
    assert result["by_component"]["mutated_allow"]["source"] == "surface_veto"


async def test_ack_does_not_override_deny(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DENY remains blocking even when an ack matches the trust anchor."""
    component = _write_component(tmp_path, "known_bad")
    content_hash = compute_component_hash(component)
    monkeypatch.setattr(
        d9_gate,
        "CLASSIFICATIONS",
        {
            "known_bad": (
                D9ClassificationEntry(
                    version="1.0.0",
                    content_hash=content_hash,
                    verdict=D9_VERDICT_DENY,
                    reason="known bypass",
                ),
            )
        },
    )

    result = await evaluate_d9_gate(
        FakeHass(tmp_path),
        _config_with_ack("known_bad", version="1.0.0", content_hash=content_hash),
    )

    assert result["by_component"]["known_bad"]["verdict"] == D9_VERDICT_DENY
    assert result["blocking"] == ["known_bad"]


async def test_tier2_blocks_enforce(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TIER-2 rows need extra controls and block v1 enforce."""
    component = _write_component(tmp_path, "tier2_component")
    monkeypatch.setattr(
        d9_gate,
        "CLASSIFICATIONS",
        {
            "tier2_component": (
                D9ClassificationEntry(
                    version="1.0.0",
                    content_hash=compute_component_hash(component),
                    verdict=D9_VERDICT_TIER_2,
                    evidence_type="tier2_accepted",
                    reason="requires separate control path",
                ),
            )
        },
    )

    result = await evaluate_d9_gate(FakeHass(tmp_path), default_config_data())

    assert result["by_component"]["tier2_component"]["verdict"] == D9_VERDICT_TIER_2
    assert result["blocking"] == ["tier2_component"]
    assert result["enforce_blocked"] is True


async def test_tier2_without_evidence_is_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TIER-2 rows also require an explicit evidence type."""
    component = _write_component(tmp_path, "tier2_without_evidence")
    monkeypatch.setattr(
        d9_gate,
        "CLASSIFICATIONS",
        {
            "tier2_without_evidence": (
                D9ClassificationEntry(
                    version="1.0.0",
                    content_hash=compute_component_hash(component),
                    verdict=D9_VERDICT_TIER_2,
                    reason="missing evidence type",
                ),
            )
        },
    )

    result = await evaluate_d9_gate(FakeHass(tmp_path), default_config_data())

    component_result = result["by_component"]["tier2_without_evidence"]
    assert component_result["verdict"] == D9_VERDICT_UNKNOWN
    assert component_result["source"] == "classification"


async def test_table_allow_without_evidence_type_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Table ALLOW rows require an explicit evidence type."""
    component = _write_component(tmp_path, "missing_evidence")
    monkeypatch.setattr(
        d9_gate,
        "CLASSIFICATIONS",
        {
            "missing_evidence": (
                D9ClassificationEntry(
                    version="1.0.0",
                    content_hash=compute_component_hash(component),
                    verdict=D9_VERDICT_ALLOW,
                    reason="missing evidence type",
                ),
            )
        },
    )

    result = await evaluate_d9_gate(FakeHass(tmp_path), default_config_data())

    assert result["by_component"]["missing_evidence"]["verdict"] == D9_VERDICT_UNKNOWN
    assert result["by_component"]["missing_evidence"]["source"] == "classification"


def test_aliased_view_import_is_detected_as_http_surface() -> None:
    """The AST detector still resolves aliased HomeAssistantView imports.

    Generic HTTP surfaces no longer hard-veto in D9 v2, so this asserts the
    detector directly, decoupled from the now-permissive verdict policy.
    """
    src = (
        "from homeassistant.components.http import HomeAssistantView as HV\n"
        "class View(HV):\n"
        "    pass\n"
    )

    assert d9_gate.SURFACE_HTTP in d9_gate._detect_python_surfaces(src)


def test_auth_mutation_call_is_detected_as_auth_surface() -> None:
    """The AST detector resolves an auth-store mutation call to SURFACE_AUTH."""
    src = (
        "async def f(hass):\n"
        "    await hass.auth.async_update_user(None, group_ids=[])\n"
    )

    assert d9_gate.SURFACE_AUTH in d9_gate._detect_python_surfaces(src)


@pytest.mark.parametrize(
    "expr",
    [
        "hass.auth.async_create_system_user",
        "hass.auth.async_get_or_create_user",
        "hass.auth.async_enable_user_mfa",
        "hass.auth.async_disable_user_mfa",
        "hass.auth.async_set_expiry",
        "hass.auth.async_update_user_credentials_data",
    ],
)
def test_honest_auth_manager_mutations_are_detected(expr: str) -> None:
    """Real HA AuthManager mutation APIs (gate finding) resolve to SURFACE_AUTH."""
    src = f"def f(hass):\n    return {expr}\n"

    assert d9_gate.SURFACE_AUTH in d9_gate._detect_python_surfaces(src)


def test_usermeta_provider_provisioning_is_auth_surface() -> None:
    """A custom auth provider assigning a group via UserMeta is auth-relevant."""
    src = (
        "from homeassistant.auth.providers import UserMeta\n"
        "async def async_user_meta_for_credentials(self, credentials):\n"
        "    return UserMeta(name='x', is_active=True, group='system-admin')\n"
    )

    assert d9_gate.SURFACE_AUTH in d9_gate._detect_python_surfaces(src)


def test_direct_groups_write_is_auth_surface() -> None:
    """Direct membership reassignment ``user.groups = [...]`` is auth-relevant."""
    src = "def f(user, groups):\n    user.groups = groups\n"

    assert d9_gate.SURFACE_AUTH in d9_gate._detect_python_surfaces(src)


def test_groups_read_is_not_auth_surface() -> None:
    """Reading membership must not flag — precision guard against over-blocking."""
    src = "def f(user):\n    return [g.id for g in user.groups]\n"

    assert d9_gate.SURFACE_AUTH not in d9_gate._detect_python_surfaces(src)


def test_text_path_detects_auth_marker_only() -> None:
    """The manifest/yaml text scan surfaces auth markers but not generic ones."""
    assert d9_gate.SURFACE_AUTH in d9_gate._detect_text_surfaces(
        "this calls async_update_user somewhere"
    )
    assert d9_gate.SURFACE_AUTH not in d9_gate._detect_text_surfaces(
        "this only does register_view"
    )


def test_invented_group_apis_are_not_markers() -> None:
    """Regression: async_create_group/async_remove_group are not real HA APIs.

    They were invented in the first draft and removed; the noisy bare ``_groups``
    marker was replaced by the precise AUTH_WRITE_ATTRS Store-write detector.
    """
    assert "async_create_group" not in d9_gate.AUTH_MUTATION_MARKERS
    assert "async_remove_group" not in d9_gate.AUTH_MUTATION_MARKERS
    assert "_groups" not in d9_gate.AUTH_MUTATION_MARKERS


async def test_runtime_verified_allow_permits_auth_surface(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """runtime_verified_allow asserts the surface itself was verified -> ALLOW.

    Unlike no_surface_verified (rejected when a veto surface is present), this
    evidence type intentionally permits the surface it was verified against.
    """
    component = _write_component(
        tmp_path,
        "verified_auth",
        py_source=(
            "async def async_setup(hass, config):\n"
            "    await hass.auth.async_update_user(None, group_ids=[])\n"
        ),
    )
    monkeypatch.setattr(
        d9_gate,
        "CLASSIFICATIONS",
        {
            "verified_auth": (
                D9ClassificationEntry(
                    version="1.0.0",
                    content_hash=compute_component_hash(component),
                    verdict=D9_VERDICT_ALLOW,
                    evidence_type="runtime_verified_allow",
                    reason="runtime verified safe with its surface",
                ),
            )
        },
    )

    result = await evaluate_d9_gate(FakeHass(tmp_path), default_config_data())

    assert result["by_component"]["verified_auth"]["verdict"] == D9_VERDICT_ALLOW
    assert result["by_component"]["verified_auth"]["source"] == "classification"


async def test_getattr_string_auth_marker_is_surface(tmp_path: Path) -> None:
    """AST detection catches an auth mutation referenced via a string marker."""
    _write_component(
        tmp_path,
        "getattr_auth",
        py_source=(
            "async def async_setup(hass, config):\n"
            '    getattr(hass.auth, "async_update_user")(None)\n'
        ),
    )

    result = await evaluate_d9_gate(FakeHass(tmp_path), default_config_data())

    component_result = result["by_component"]["getattr_auth"]
    assert component_result["verdict"] == D9_VERDICT_UNKNOWN
    assert component_result["source"] == "surface_veto"


async def test_unparseable_py_is_surface(tmp_path: Path) -> None:
    """Unparseable Python fails closed because static analysis is incomplete."""
    _write_component(tmp_path, "broken_python", py_source="def broken(:\n")

    result = await evaluate_d9_gate(FakeHass(tmp_path), default_config_data())

    component_result = result["by_component"]["broken_python"]
    assert component_result["verdict"] == D9_VERDICT_UNKNOWN
    assert component_result["source"] == "surface_veto"


def test_hash_covers_non_source_files(tmp_path: Path) -> None:
    """Non-source payload files are part of the D9 trust anchor."""
    component = _write_component(tmp_path, "payload_component")
    before = compute_component_hash(component)
    (component / "payload.bin").write_bytes(b"opaque payload")

    assert compute_component_hash(component) != before


async def test_compiled_artifact_is_surface(tmp_path: Path) -> None:
    """Compiled or extension artifacts fail closed as executable surfaces."""
    component = _write_component(tmp_path, "compiled_component")
    (component / "native.so").write_bytes(b"opaque native code")

    result = await evaluate_d9_gate(FakeHass(tmp_path), default_config_data())

    assert compute_component_hash(component)
    assert result["by_component"]["compiled_component"]["verdict"] == D9_VERDICT_UNKNOWN
    assert result["by_component"]["compiled_component"]["source"] == "surface_veto"


def test_pycache_excluded_from_hash(tmp_path: Path) -> None:
    """Regenerated Python bytecode caches do not churn the content hash."""
    component = _write_component(tmp_path, "cache_component")
    before = compute_component_hash(component)
    pycache = component / "__pycache__"
    pycache.mkdir()
    (pycache / "__init__.cpython-313.pyc").write_bytes(b"unstable bytecode")

    assert compute_component_hash(component) == before


def test_compute_hash_is_stable(tmp_path: Path) -> None:
    """Hashing the same component twice is deterministic."""
    component = _write_component(tmp_path, "stable_component")

    assert compute_component_hash(component) == compute_component_hash(component)


def test_path_swap_changes_hash(tmp_path: Path) -> None:
    """Relative paths are part of the hash to prevent path-swap collisions."""
    component = _write_component(tmp_path, "path_swap")
    (component / "a.txt").write_text("one", encoding="utf-8")
    (component / "b.txt").write_text("two", encoding="utf-8")
    first_hash = compute_component_hash(component)
    (component / "a.txt").write_text("two", encoding="utf-8")
    (component / "b.txt").write_text("one", encoding="utf-8")

    assert compute_component_hash(component) != first_hash


async def test_loader_path_merges_and_version_precedence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Loader entries merge with disk entries and override disk versions."""
    _write_component(tmp_path, "loader_and_disk", version="1.0.0")
    monkeypatch.setattr(
        d9_gate,
        "_async_get_custom_components",
        AsyncMock(
            return_value={
                "loader_and_disk": type("Integration", (), {"version": "9.9.9"})(),
                "loader_only": type("Integration", (), {"version": "3.0.0"})(),
            }
        ),
    )

    result = await evaluate_d9_gate(FakeHass(tmp_path), default_config_data())

    assert result["by_component"]["loader_and_disk"]["version"] == "9.9.9"
    assert result["by_component"]["loader_and_disk"]["verdict"] == D9_VERDICT_ALLOW
    assert result["by_component"]["loader_only"] == {
        "verdict": D9_VERDICT_ALLOW,
        "version": "3.0.0",
        "content_hash": None,
        "source": "default",
        "reason": "no auth-relevant surface and no blocking classification or ack",
    }


async def test_fresh_disk_hash_beats_stale_table(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fresh disk hash prevents stale table entries from matching."""
    _write_component(tmp_path, "fresh_hash")
    monkeypatch.setattr(
        d9_gate,
        "CLASSIFICATIONS",
        {
            "fresh_hash": (
                D9ClassificationEntry(
                    version="1.0.0",
                    content_hash="0" * 64,
                    verdict=D9_VERDICT_ALLOW,
                    evidence_type="no_surface_verified",
                    reason="stale hash",
                ),
            )
        },
    )

    result = await evaluate_d9_gate(FakeHass(tmp_path), default_config_data())

    component_result = result["by_component"]["fresh_hash"]
    assert component_result["verdict"] == D9_VERDICT_ALLOW
    assert component_result["source"] == "default"


def test_versions_equal_trailing_zero_parity(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fallback version comparison mirrors AwesomeVersion trailing-zero behavior."""
    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "awesomeversion":
            raise ModuleNotFoundError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    assert d9_gate._versions_equal("1.0", "1.0.0") is True


def test_ack_matches_tolerates_missing_keys() -> None:
    """Malformed future ack payloads fail closed instead of raising KeyError."""
    assert (
        d9_gate._ack_matches(
            {"version": "1.0.0", "accepted_at": "now"},  # type: ignore[typeddict-item]
            "1.0.0",
            "a" * 64,
        )
        is False
    )


def test_config_schema_accepts_d9_acks() -> None:
    """Config schema validates version/hash-bound D9 acks."""
    content_hash = "a" * 64
    config = _config_with_ack(
        "unknown_component", version=None, content_hash=content_hash
    )

    assert validate_config_data(config)["d9_acks"]["unknown_component"] == {
        "version": None,
        "content_hash": content_hash,
        "accepted_at": "2026-06-30T00:00:00Z",
    }


@pytest.mark.parametrize(
    ("ack", "match"),
    [
        ({"version": 1, "content_hash": "a" * 64, "accepted_at": "now"}, "version"),
        (
            {"version": "1", "content_hash": "not-a-hash", "accepted_at": "now"},
            "sha256",
        ),
        ({"version": "1", "content_hash": "a" * 64, "accepted_at": ""}, "accepted_at"),
    ],
)
def test_config_schema_rejects_invalid_d9_acks(
    ack: dict[str, object], match: str
) -> None:
    """Config schema rejects malformed D9 acknowledgements."""
    config = default_config_data()
    config["d9_acks"] = {"component": ack}  # type: ignore[typeddict-item]

    with pytest.raises(TesseraSchemaError, match=match):
        validate_config_data(config)


def test_config_schema_normalizes_uppercase_d9_ack_hash() -> None:
    """Uppercase ack hashes are normalized to the lowercase hexdigest shape."""
    config = _config_with_ack("component", version="1", content_hash="A" * 64)

    assert validate_config_data(config)["d9_acks"]["component"]["content_hash"] == (
        "a" * 64
    )
