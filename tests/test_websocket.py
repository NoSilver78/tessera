"""Tests for Tessera matrix WebSocket helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from custom_components.tessera.const import DOMAIN
from custom_components.tessera.schema import default_config_data, default_policy_data
from custom_components.tessera.websocket import (
    async_get_matrix,
    async_set_matrix_grant,
    websocket_matrix_get,
)
from homeassistant.exceptions import Unauthorized


@dataclass(frozen=True)
class FakeArea:
    """Small AreaEntry-compatible test double."""

    id: str
    name: str


class FakeAreaRegistry:
    """Area registry double for matrix tests."""

    def __init__(self, areas: list[FakeArea]) -> None:
        """Initialize area rows."""
        self._areas = areas

    def async_list_areas(self) -> list[FakeArea]:
        """Return fake areas."""
        return self._areas


class FakeResolver:
    """Deterministic area resolver for preview compilation."""

    def entity_ids_for_area(self, area_id: str) -> tuple[str, ...]:
        """Resolve fake areas to fake entities."""
        return ("light.sofa", "switch.lamp") if area_id == "living" else ()


class FakeStore:
    """Async in-memory Tessera store double."""

    def __init__(self, config: dict[str, Any], policy: dict[str, Any]) -> None:
        """Initialize store data and write capture."""
        self.config = config
        self.policy = policy
        self.saved_policies: list[dict[str, Any]] = []

    async def async_load_config(self) -> dict[str, Any]:
        """Load fake config data."""
        return self.config

    async def async_load_policy(self) -> dict[str, Any]:
        """Load fake policy data."""
        return self.policy

    async def async_save_policy(self, policy: dict[str, Any]) -> None:
        """Persist fake policy data."""
        self.policy = policy
        self.saved_policies.append(policy)


class FakeHass:
    """Minimal Home Assistant double with auth access trapped."""

    def __init__(self, store: FakeStore) -> None:
        """Initialize HA-like data with one loaded Tessera entry."""
        self.data: dict[str, Any] = {DOMAIN: {"entry-1": {"store": store}}}

    @property
    def auth(self) -> object:
        """Fail if the matrix API touches native auth."""
        raise AssertionError("matrix API must not touch hass.auth")


class FakeUser:
    """WebSocket user double."""

    def __init__(self, *, is_admin: bool) -> None:
        """Initialize admin status."""
        self.is_admin = is_admin


class FakeConnection:
    """WebSocket connection double for auth checks."""

    def __init__(self, *, is_admin: bool) -> None:
        """Initialize fake connection state."""
        self.user = FakeUser(is_admin=is_admin)


def _config() -> dict[str, Any]:
    config = default_config_data()
    config["mode"] = "monitor"
    config["roles"] = {
        "operator": {"name": "Operator"},
        "viewer": {"name": "Viewer"},
    }
    return config


def _policy() -> dict[str, Any]:
    policy = default_policy_data()
    policy["area_grants"] = {"living": {"viewer": {"read": True}}}
    return policy


@pytest.fixture
def matrix_hass(monkeypatch: pytest.MonkeyPatch) -> FakeHass:
    """Return a fake HA instance wired for matrix responses."""
    store = FakeStore(_config(), _policy())
    hass = FakeHass(store)

    monkeypatch.setattr(
        "custom_components.tessera.websocket.ar.async_get",
        lambda hass: FakeAreaRegistry(
            [
                FakeArea("kitchen", "Kitchen"),
                FakeArea("living", "Living Room"),
            ]
        ),
    )
    monkeypatch.setattr(
        "custom_components.tessera.websocket.AreaEntityResolver.from_hass",
        classmethod(lambda cls, hass: FakeResolver()),
    )
    return hass


@pytest.mark.asyncio
async def test_matrix_get_returns_shape_and_preview(matrix_hass: FakeHass) -> None:
    """Matrix get returns sorted areas, roles, explicit grants, and preview counts."""
    result = await async_get_matrix(matrix_hass)

    assert result["areas"] == [
        {"id": "kitchen", "name": "Kitchen"},
        {"id": "living", "name": "Living Room"},
    ]
    assert result["roles"] == [
        {"id": "operator", "name": "Operator"},
        {"id": "viewer", "name": "Viewer"},
    ]
    assert result["grants"]["kitchen"]["viewer"] == {
        "read": False,
        "control": False,
    }
    assert result["grants"]["living"]["viewer"] == {"read": True, "control": False}
    assert result["preview"]["read_total"] == 2
    assert result["preview"]["control_total"] == 0


@pytest.mark.asyncio
async def test_matrix_set_grant_writes_schema_valid_read_and_control(
    matrix_hass: FakeHass,
) -> None:
    """Grant writes use schema-aware helpers and control implies read."""
    result = await async_set_matrix_grant(
        matrix_hass,
        area_id="living",
        role_id="operator",
        read=False,
        control=True,
    )
    store = matrix_hass.data[DOMAIN]["entry-1"]["store"]
    leaf = store.policy["area_grants"]["living"]["operator"]

    assert leaf == {"read": True, "control": True}
    assert leaf is not True
    assert result["grants"]["living"]["operator"] == {
        "read": True,
        "control": True,
    }
    assert result["preview"]["control_total"] == 2
    assert store.saved_policies == [store.policy]


@pytest.mark.asyncio
async def test_matrix_set_grant_all_false_removes_grant(
    matrix_hass: FakeHass,
) -> None:
    """All-false input removes the grant instead of storing an empty leaf."""
    result = await async_set_matrix_grant(
        matrix_hass,
        area_id="living",
        role_id="viewer",
        read=False,
        control=False,
    )
    store = matrix_hass.data[DOMAIN]["entry-1"]["store"]

    assert store.policy["area_grants"] == {}
    assert result["grants"]["living"]["viewer"] == {
        "read": False,
        "control": False,
    }
    assert result["preview"]["read_total"] == 0


@pytest.mark.asyncio
async def test_matrix_set_grant_rejects_unknown_area_and_role(
    matrix_hass: FakeHass,
) -> None:
    """Unknown matrix coordinates fail closed before persistence."""
    with pytest.raises(LookupError, match="Unknown Tessera area"):
        await async_set_matrix_grant(
            matrix_hass,
            area_id="garage",
            role_id="viewer",
            read=True,
            control=False,
        )

    with pytest.raises(LookupError, match="Unknown Tessera role"):
        await async_set_matrix_grant(
            matrix_hass,
            area_id="living",
            role_id="ghost",
            read=True,
            control=False,
        )

    store = matrix_hass.data[DOMAIN]["entry-1"]["store"]
    assert store.saved_policies == []


def test_matrix_websocket_requires_admin(matrix_hass: FakeHass) -> None:
    """Matrix WebSocket commands reject non-admin connections."""
    with pytest.raises(Unauthorized):
        websocket_matrix_get(
            matrix_hass,
            FakeConnection(is_admin=False),
            {"id": 1, "type": "tessera/matrix/get"},
        )
