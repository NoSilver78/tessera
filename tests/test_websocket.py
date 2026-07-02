"""Tests for Tessera matrix WebSocket helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from custom_components.tessera.const import DOMAIN
from custom_components.tessera.resolver import AreaEntityResolution
from custom_components.tessera.schema import default_config_data, default_policy_data
from custom_components.tessera.websocket import (
    async_get_matrix,
    async_set_matrix_floor_grant,
    async_set_matrix_grant,
    async_set_matrix_label_grant,
    websocket_matrix_get,
)
from homeassistant.exceptions import Unauthorized


@dataclass(frozen=True)
class FakeArea:
    """Small AreaEntry-compatible test double."""

    id: str
    name: str
    floor_id: str | None = None


@dataclass(frozen=True)
class FakeFloor:
    """Small FloorEntry-compatible test double."""

    floor_id: str
    name: str
    level: int | None = None


class FakeFloorRegistry:
    """Floor registry double for matrix tests."""

    def __init__(self, floors: list[FakeFloor]) -> None:
        """Index floors by id."""
        self._floors = {floor.floor_id: floor for floor in floors}

    def async_get_floor(self, floor_id: str) -> FakeFloor | None:
        """Return the floor for ``floor_id`` (or None)."""
        return self._floors.get(floor_id)

    def async_list_floors(self) -> list[FakeFloor]:
        """Return floors in registry order (the panel's ordering fallback)."""
        return list(self._floors.values())


class FakeAreaRegistry:
    """Area registry double for matrix tests."""

    def __init__(self, areas: list[FakeArea]) -> None:
        """Initialize area rows."""
        self._areas = areas

    def async_list_areas(self) -> list[FakeArea]:
        """Return fake areas."""
        return self._areas


@dataclass(frozen=True)
class FakeLabel:
    """Small LabelEntry-compatible test double."""

    label_id: str
    name: str
    icon: str | None = None
    color: str | None = None


class FakeLabelRegistry:
    """Label registry double for matrix tests."""

    def __init__(self, labels: list[FakeLabel]) -> None:
        """Initialize label rows."""
        self._labels = labels

    def async_list_labels(self) -> list[FakeLabel]:
        """Return fake labels."""
        return self._labels


class FakeResolver:
    """Deterministic area resolver for preview compilation and the panel expand."""

    def entity_ids_for_area(self, area_id: str) -> tuple[str, ...]:
        """Resolve fake areas to fake entities."""
        return ("light.sofa", "switch.lamp") if area_id == "living" else ()

    def entity_ids_for_floor(self, floor_id: str) -> tuple[str, ...]:
        """Resolve a floor to its entities."""
        return ("light.sofa", "switch.lamp") if floor_id == "ground" else ()

    def entity_ids_for_label(self, label_id: str) -> tuple[str, ...]:
        """Resolve a label to its entities."""
        return ("light.sofa",) if label_id == "cozy" else ()

    def entity_ids_for_areas(self, area_ids: Any) -> AreaEntityResolution:
        """Resolve multiple areas at once (used by the panel entity expand)."""
        by_area = {aid: self.entity_ids_for_area(aid) for aid in area_ids}
        entity_ids = {eid for ids in by_area.values() for eid in ids}
        return AreaEntityResolution(entity_ids=entity_ids, by_area=by_area)


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


def _conflict_config() -> dict[str, Any]:
    config = _config()
    config["membership"]["by_user"] = {"user-1": ["operator", "viewer"]}
    return config


def _conflict_policy() -> dict[str, Any]:
    policy = default_policy_data()
    policy["area_grants"] = {
        "living": {
            "operator": {"read": True, "control": True},
            "viewer": {"read": True},
        }
    }
    return policy


def _install_matrix_doubles(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch the area registry and resolver doubles the matrix API depends on."""
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
        "custom_components.tessera.websocket.lr.async_get",
        lambda hass: FakeLabelRegistry([FakeLabel("cozy", "Cozy", color="amber")]),
    )
    monkeypatch.setattr(
        "custom_components.tessera.websocket.AreaEntityResolver.from_hass",
        classmethod(lambda cls, hass: FakeResolver()),
    )


def _install_floor_doubles(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch area+floor registries and the resolver for floor-grant tests."""
    monkeypatch.setattr(
        "custom_components.tessera.websocket.ar.async_get",
        lambda hass: FakeAreaRegistry(
            [
                FakeArea("living", "Living Room", floor_id="ground"),
                FakeArea("kitchen", "Kitchen", floor_id="ground"),
            ]
        ),
    )
    monkeypatch.setattr(
        "custom_components.tessera.websocket.fr.async_get",
        lambda hass: FakeFloorRegistry([FakeFloor("ground", "Ground", level=0)]),
    )
    monkeypatch.setattr(
        "custom_components.tessera.websocket.lr.async_get",
        lambda hass: FakeLabelRegistry([]),
    )
    monkeypatch.setattr(
        "custom_components.tessera.websocket.AreaEntityResolver.from_hass",
        classmethod(lambda cls, hass: FakeResolver()),
    )


@pytest.fixture
def matrix_hass(monkeypatch: pytest.MonkeyPatch) -> FakeHass:
    """Return a fake HA instance wired for matrix responses."""
    store = FakeStore(_config(), _policy())
    hass = FakeHass(store)
    _install_matrix_doubles(monkeypatch)
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
    assert result["lint"]["conflicts_total"] == 0


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
    assert result["preview"]["lint"]["conflicts_total"] == 0
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
async def test_matrix_set_grant_in_enforce_reapplies_native(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CXR-02: saving a grant in enforce re-applies via the central mode handler."""
    config = _config()
    config["mode"] = "enforce"
    store = FakeStore(config, _policy())
    hass = FakeHass(store)
    _install_matrix_doubles(monkeypatch)

    calls: list[tuple[Any, str, dict[str, Any]]] = []

    async def _spy_compile(
        spy_hass: Any, entry_id: str, entry_data: dict[str, Any]
    ) -> None:
        calls.append((spy_hass, entry_id, entry_data))

    monkeypatch.setattr(
        "custom_components.tessera._compile_for_mode_safely", _spy_compile
    )

    result = await async_set_matrix_grant(
        hass,
        area_id="living",
        role_id="operator",
        read=True,
        control=False,
    )

    assert store.saved_policies, "policy must be persisted before re-apply"
    assert len(calls) == 1, "enforce must re-apply through the central handler once"
    spy_hass, entry_id, entry_data = calls[0]
    assert spy_hass is hass
    assert entry_id == "entry-1"
    assert entry_data is hass.data[DOMAIN]["entry-1"]
    assert result["grants"]["living"]["operator"]["read"] is True


@pytest.mark.asyncio
async def test_matrix_set_grant_in_monitor_does_not_reapply(
    matrix_hass: FakeHass, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Monitor keeps the matrix API read-only on native auth (no native re-apply)."""
    calls: list[tuple[Any, ...]] = []

    async def _spy_compile(*args: Any) -> None:
        calls.append(args)

    monkeypatch.setattr(
        "custom_components.tessera._compile_for_mode_safely", _spy_compile
    )

    await async_set_matrix_grant(
        matrix_hass,
        area_id="living",
        role_id="operator",
        read=True,
        control=False,
    )

    assert calls == [], "monitor mode must not write native auth"


@pytest.mark.asyncio
async def test_matrix_preview_includes_cross_role_lint_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Matrix preview exposes the E2 linter report without native auth writes."""
    store = FakeStore(_conflict_config(), _conflict_policy())
    hass = FakeHass(store)

    class OneEntityResolver:
        """Resolver double that keeps the lint assertion focused."""

        def entity_ids_for_area(self, area_id: str) -> tuple[str, ...]:
            return ("light.sofa",) if area_id == "living" else ()

        def entity_ids_for_floor(self, floor_id: str) -> tuple[str, ...]:
            return ()

        def entity_ids_for_label(self, label_id: str) -> tuple[str, ...]:
            return ()

        def entity_ids_for_areas(self, area_ids: Any) -> AreaEntityResolution:
            by_area = {aid: self.entity_ids_for_area(aid) for aid in area_ids}
            entity_ids = {eid for ids in by_area.values() for eid in ids}
            return AreaEntityResolution(entity_ids=entity_ids, by_area=by_area)

    monkeypatch.setattr(
        "custom_components.tessera.websocket.ar.async_get",
        lambda hass: FakeAreaRegistry([FakeArea("living", "Living Room")]),
    )
    monkeypatch.setattr(
        "custom_components.tessera.websocket.lr.async_get",
        lambda hass: FakeLabelRegistry([]),
    )
    monkeypatch.setattr(
        "custom_components.tessera.websocket.AreaEntityResolver.from_hass",
        classmethod(lambda cls, hass: OneEntityResolver()),
    )

    result = await async_get_matrix(hass)

    assert result["lint"]["conflicts_total"] == 1
    assert result["lint"] == result["preview"]["lint"]
    assert result["lint"]["users"]["user-1"]["conflicts"][0] == {
        "user_id": "user-1",
        "entity_id": "light.sofa",
        "exposing_roles": ["operator"],
        "restricting_roles": ["viewer"],
        "level": "control",
        "severity": "error",
    }


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


@pytest.mark.asyncio
async def test_matrix_get_splits_floor_and_area_sources_with_entities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Matrix get exposes floor/area per-source grants, area floors, and entities."""
    config = _config()
    policy = default_policy_data()
    policy["area_grants"] = {"living": {"viewer": {"read": True}}}
    policy["floor_grants"] = {"ground": {"viewer": {"read": True, "control": True}}}
    store = FakeStore(config, policy)
    hass = FakeHass(store)

    monkeypatch.setattr(
        "custom_components.tessera.websocket.ar.async_get",
        lambda hass: FakeAreaRegistry(
            [
                FakeArea("kitchen", "Kitchen", floor_id="ground"),
                FakeArea("living", "Living Room", floor_id="ground"),
                FakeArea("attic", "Attic"),
            ]
        ),
    )
    monkeypatch.setattr(
        "custom_components.tessera.websocket.fr.async_get",
        lambda hass: FakeFloorRegistry([FakeFloor("ground", "Ground", level=0)]),
    )
    monkeypatch.setattr(
        "custom_components.tessera.websocket.lr.async_get",
        lambda hass: FakeLabelRegistry([]),
    )
    monkeypatch.setattr(
        "custom_components.tessera.websocket.AreaEntityResolver.from_hass",
        classmethod(lambda cls, hass: FakeResolver()),
    )

    result = await async_get_matrix(hass)

    # area -> floor labels (floorless area resolves to None)
    assert result["area_floor"]["living"] == {
        "id": "ground",
        "name": "Ground",
        "level": 0,
        "order": 0,
    }
    assert result["area_floor"]["attic"] is None
    # the double: living/viewer is granted via BOTH the floor and a direct area grant
    assert result["floor_grants"]["living"]["viewer"] == {"read": True, "control": True}
    assert result["grants"]["living"]["viewer"] == {"read": True, "control": False}
    # kitchen: floor source only (no direct area grant)
    assert result["floor_grants"]["kitchen"]["viewer"] == {
        "read": True,
        "control": True,
    }
    assert result["grants"]["kitchen"]["viewer"] == {"read": False, "control": False}
    # attic: floorless -> no floor source
    assert result["floor_grants"]["attic"]["viewer"] == {
        "read": False,
        "control": False,
    }
    # entities per area (from the resolver) power the row expand
    assert result["entities_by_area"]["living"] == ["light.sofa", "switch.lamp"]
    assert result["entities_by_area"]["kitchen"] == []


@pytest.mark.asyncio
async def test_matrix_set_floor_grant_writes_and_control_implies_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A floor grant write is schema-aware, control implies read, covers the floor."""
    _install_floor_doubles(monkeypatch)
    store = FakeStore(_config(), default_policy_data())
    hass = FakeHass(store)

    result = await async_set_matrix_floor_grant(
        hass, floor_id="ground", role_id="operator", read=False, control=True
    )

    assert store.policy["floor_grants"]["ground"]["operator"] == {
        "read": True,
        "control": True,
    }
    assert result["floor_grants"]["living"]["operator"] == {
        "read": True,
        "control": True,
    }
    assert result["floor_grants"]["kitchen"]["operator"] == {
        "read": True,
        "control": True,
    }
    assert store.saved_policies == [store.policy]


@pytest.mark.asyncio
async def test_matrix_set_floor_grant_rejects_unknown_floor_and_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unknown floor or role ids fail closed before any policy write."""
    _install_floor_doubles(monkeypatch)
    store = FakeStore(_config(), default_policy_data())
    hass = FakeHass(store)

    with pytest.raises(LookupError, match="Unknown Tessera floor"):
        await async_set_matrix_floor_grant(
            hass, floor_id="attic", role_id="operator", read=True, control=False
        )
    with pytest.raises(LookupError, match="Unknown Tessera role"):
        await async_set_matrix_floor_grant(
            hass, floor_id="ground", role_id="ghost", read=True, control=False
        )

    assert store.saved_policies == []


@pytest.mark.asyncio
async def test_matrix_set_floor_grant_in_enforce_reapplies_native(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CXR-02: saving a floor grant in enforce re-applies via the central handler."""
    config = _config()
    config["mode"] = "enforce"
    store = FakeStore(config, default_policy_data())
    hass = FakeHass(store)
    _install_floor_doubles(monkeypatch)

    calls: list[tuple[Any, str, dict[str, Any]]] = []

    async def _spy_compile(
        spy_hass: Any, entry_id: str, entry_data: dict[str, Any]
    ) -> None:
        calls.append((spy_hass, entry_id, entry_data))

    monkeypatch.setattr(
        "custom_components.tessera._compile_for_mode_safely", _spy_compile
    )

    await async_set_matrix_floor_grant(
        hass, floor_id="ground", role_id="operator", read=True, control=False
    )

    assert store.saved_policies, "policy must be persisted before re-apply"
    assert len(calls) == 1
    assert calls[0][1] == "entry-1"


@pytest.mark.asyncio
async def test_matrix_get_includes_labels_and_label_grants(
    matrix_hass: FakeHass,
) -> None:
    """The matrix payload exposes labels, per-cell label grants, and entities."""
    result = await async_get_matrix(matrix_hass)

    assert result["labels"] == [
        {"id": "cozy", "name": "Cozy", "icon": None, "color": "amber"}
    ]
    assert result["label_grants"]["cozy"]["operator"] == {
        "read": False,
        "control": False,
    }
    assert result["entities_by_label"]["cozy"] == ["light.sofa"]


@pytest.mark.asyncio
async def test_matrix_set_label_grant_writes_and_control_implies_read(
    matrix_hass: FakeHass,
) -> None:
    """A label grant write is schema-aware and control implies read."""
    result = await async_set_matrix_label_grant(
        matrix_hass, label_id="cozy", role_id="operator", read=False, control=True
    )
    store = matrix_hass.data[DOMAIN]["entry-1"]["store"]

    assert store.policy["label_grants"]["cozy"]["operator"] == {
        "read": True,
        "control": True,
    }
    assert result["label_grants"]["cozy"]["operator"] == {
        "read": True,
        "control": True,
    }
    assert store.saved_policies == [store.policy]


@pytest.mark.asyncio
async def test_matrix_set_label_grant_rejects_unknown_label_and_role(
    matrix_hass: FakeHass,
) -> None:
    """Unknown label or role ids fail closed before any policy write."""
    store = matrix_hass.data[DOMAIN]["entry-1"]["store"]

    with pytest.raises(LookupError, match="Unknown Tessera label"):
        await async_set_matrix_label_grant(
            matrix_hass, label_id="ghost", role_id="operator", read=True, control=False
        )
    with pytest.raises(LookupError, match="Unknown Tessera role"):
        await async_set_matrix_label_grant(
            matrix_hass, label_id="cozy", role_id="ghost", read=True, control=False
        )

    assert store.saved_policies == []


@pytest.mark.asyncio
async def test_matrix_set_label_grant_in_enforce_reapplies_native(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CXR-02: saving a label grant in enforce re-applies via the central handler."""
    config = _config()
    config["mode"] = "enforce"
    store = FakeStore(config, default_policy_data())
    hass = FakeHass(store)
    _install_matrix_doubles(monkeypatch)

    calls: list[tuple[Any, str, dict[str, Any]]] = []

    async def _spy_compile(
        spy_hass: Any, entry_id: str, entry_data: dict[str, Any]
    ) -> None:
        calls.append((spy_hass, entry_id, entry_data))

    monkeypatch.setattr(
        "custom_components.tessera._compile_for_mode_safely", _spy_compile
    )

    await async_set_matrix_label_grant(
        hass, label_id="cozy", role_id="operator", read=True, control=False
    )

    assert store.saved_policies, "policy must be persisted before re-apply"
    assert len(calls) == 1
    assert calls[0][1] == "entry-1"
