"""Tests for shared user helper functions."""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType


def _load_user_helpers() -> ModuleType:
    """Load the helper module without importing Home Assistant integration setup."""
    helper_path = (
        Path(__file__).parents[1] / "custom_components" / "tessera" / "_user_helpers.py"
    )
    spec = importlib.util.spec_from_file_location(
        "tessera_user_helpers_test", helper_path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_USER_HELPERS = _load_user_helpers()
_is_unmanaged_user = _USER_HELPERS._is_unmanaged_user
_user_group_ids = _USER_HELPERS._user_group_ids


@dataclass(frozen=True)
class FakeGroup:
    """Small group double with a Home Assistant-like id attribute."""

    id: str


@dataclass
class FakeUser:
    """Small user double for helper tests."""

    group_ids: list[object] | None = None
    groups: list[FakeGroup] | None = None
    is_owner: bool = False
    system_generated: bool = False


@dataclass
class FakeGroupsOnlyUser:
    """Small user double exposing only Home Assistant-like groups."""

    groups: list[FakeGroup]


def test_user_group_ids_prefers_group_ids_attribute() -> None:
    """group_ids are stringified and sorted when present."""
    user = FakeUser(group_ids=["viewer", "admin", 3])

    assert _user_group_ids(user) == ["3", "admin", "viewer"]


def test_user_group_ids_falls_back_to_groups_attribute() -> None:
    """Groups with id attributes are stringified and sorted."""
    user = FakeGroupsOnlyUser(groups=[FakeGroup("viewer"), FakeGroup("admin")])

    assert _user_group_ids(user) == ["admin", "viewer"]


def test_is_unmanaged_user_detects_owner() -> None:
    """Owner users are unmanaged."""
    assert _is_unmanaged_user(FakeUser(is_owner=True)) is True


def test_is_unmanaged_user_detects_system_generated() -> None:
    """System-generated users are unmanaged."""
    assert _is_unmanaged_user(FakeUser(system_generated=True)) is True


def test_is_unmanaged_user_allows_normal_users() -> None:
    """Normal users are managed."""
    assert _is_unmanaged_user(FakeUser()) is False
