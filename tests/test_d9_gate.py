"""Tests for Tessera's dormant D9 custom-component gate."""

from __future__ import annotations

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


async def test_runtime_service_without_services_yaml_is_unknown(tmp_path: Path) -> None:
    """Runtime services hard-veto even when services.yaml is absent."""
    component = _write_component(tmp_path, "sneaky_service")
    hass = FakeHass(tmp_path, {"sneaky_service": {"do_it": object()}})

    result = await evaluate_d9_gate(hass, default_config_data())

    assert compute_component_hash(component)
    assert result["by_component"]["sneaky_service"]["verdict"] == D9_VERDICT_UNKNOWN
    assert result["by_component"]["sneaky_service"]["source"] == "surface_veto"
    assert result["blocking"] == ["sneaky_service"]
    assert result["enforce_blocked"] is True
    assert hass.executor_calls == 1


async def test_entity_component_with_view_or_ws_marker_is_unknown(
    tmp_path: Path,
) -> None:
    """Static View/WS markers hard-veto faked entity-style integrations."""
    _write_component(
        tmp_path,
        "sneaky_http",
        py_source=(
            "from homeassistant.components.http import HomeAssistantView\n"
            "async def async_setup(hass, config):\n"
            "    hass.http.register_view(HomeAssistantView())\n"
            "    hass.components.websocket_api.async_register_command(lambda: None)\n"
        ),
    )

    result = await evaluate_d9_gate(FakeHass(tmp_path), default_config_data())

    assert result["by_component"]["sneaky_http"]["verdict"] == D9_VERDICT_UNKNOWN
    assert result["by_component"]["sneaky_http"]["source"] == "surface_veto"
    assert "sneaky_http" in result["blocking"]


async def test_ack_expires_when_content_hash_changes(tmp_path: Path) -> None:
    """Ack is bound to domain, version, and exact content hash."""
    component = _write_component(tmp_path, "mutable_component")
    stale_hash = compute_component_hash(component)
    (component / "__init__.py").write_text("# changed\n", encoding="utf-8")

    result = await evaluate_d9_gate(
        FakeHass(tmp_path),
        _config_with_ack("mutable_component", version="1.0.0", content_hash=stale_hash),
    )

    assert result["by_component"]["mutable_component"]["verdict"] == D9_VERDICT_UNKNOWN
    assert result["by_component"]["mutable_component"]["source"] == "default"


async def test_unknown_component_defaults_to_blocking_unknown(tmp_path: Path) -> None:
    """Unknown installed custom components block enforce by default."""
    _write_component(tmp_path, "unknown_component")

    result = await evaluate_d9_gate(FakeHass(tmp_path), default_config_data())

    assert result["by_component"]["unknown_component"]["verdict"] == D9_VERDICT_UNKNOWN
    assert result["enforce_blocked"] is True


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


async def test_table_allow_with_new_surface_is_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Surface hard-veto runs before table ALLOW."""
    component = _write_component(
        tmp_path,
        "mutated_allow",
        py_source=(
            "async def async_setup(hass, config):\n"
            "    hass.http.register_view(view)\n"
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
