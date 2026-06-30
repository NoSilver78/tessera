"""Tests for Tessera persistent recovery-state validation."""

from __future__ import annotations

from typing import Any

import pytest
from custom_components.tessera.state import (
    TesseraStateError,
    default_state_data,
    validate_state_data,
)


def _state(snapshot: Any, apply_in_progress: bool = False) -> dict[str, Any]:
    """Build a top-level recovery-state mapping for validation tests."""
    return {
        "pre_install_snapshot": snapshot,
        "apply_in_progress": apply_in_progress,
    }


def _snapshot(*users: dict[str, Any]) -> dict[str, Any]:
    """Build a pre-install snapshot mapping with the given user entries."""
    return {"users": list(users)}


@pytest.mark.parametrize(
    "data",
    [
        [],
        "oops",
        {"pre_install_snapshot": None, "apply_in_progress": False, "extra": 1},
        {"apply_in_progress": False},
        {"pre_install_snapshot": None},
    ],
)
def test_rejects_wrong_top_level_shape(data: Any) -> None:
    """Non-mappings and unexpected key sets are rejected as malformed state."""
    with pytest.raises(TesseraStateError, match="unexpected recovery state keys"):
        validate_state_data(data)


@pytest.mark.parametrize("apply_in_progress", ["yes", 1, 0, None])
def test_rejects_non_bool_apply_in_progress(apply_in_progress: Any) -> None:
    """``apply_in_progress`` must be a real bool, not a truthy/falsey stand-in."""
    with pytest.raises(TesseraStateError, match="apply_in_progress must be boolean"):
        validate_state_data(_state(None, apply_in_progress))


def test_rejects_apply_in_progress_without_snapshot() -> None:
    """An open journal with no immutable snapshot is unsafe and rejected."""
    with pytest.raises(
        TesseraStateError, match="apply_in_progress requires pre_install_snapshot"
    ):
        validate_state_data(_state(None, apply_in_progress=True))


@pytest.mark.parametrize(
    "snapshot",
    [[], "oops", {"nope": 1}, {"users": "not-a-list"}],
)
def test_rejects_malformed_snapshot_container(snapshot: Any) -> None:
    """A snapshot must be a mapping whose only key is a ``users`` list."""
    with pytest.raises(TesseraStateError):
        validate_state_data(_state(snapshot))


def test_rejects_snapshot_user_missing_user_id() -> None:
    """A snapshot user entry without ``user_id`` is rejected."""
    with pytest.raises(
        TesseraStateError, match="snapshot user must contain user_id and group_ids"
    ):
        validate_state_data(_state(_snapshot({"group_ids": ["system-admin"]})))


def test_rejects_snapshot_user_missing_group_ids() -> None:
    """A snapshot user entry without ``group_ids`` is rejected."""
    with pytest.raises(
        TesseraStateError, match="snapshot user must contain user_id and group_ids"
    ):
        validate_state_data(_state(_snapshot({"user_id": "user-1"})))


@pytest.mark.parametrize("user_id", ["", 5, None])
def test_rejects_non_string_or_empty_user_id(user_id: Any) -> None:
    """A snapshot ``user_id`` must be a non-empty string."""
    with pytest.raises(
        TesseraStateError, match="snapshot user_id must be a non-empty string"
    ):
        validate_state_data(_state(_snapshot({"user_id": user_id, "group_ids": []})))


def test_rejects_duplicate_snapshot_user_id() -> None:
    """Two snapshot entries sharing a ``user_id`` are rejected."""
    with pytest.raises(TesseraStateError, match="duplicate snapshot user_id"):
        validate_state_data(
            _state(
                _snapshot(
                    {"user_id": "user-1", "group_ids": []},
                    {"user_id": "user-1", "group_ids": ["system-admin"]},
                )
            )
        )


@pytest.mark.parametrize("group_ids", ["system-admin", [1], [""], [None]])
def test_rejects_non_string_group_ids(group_ids: Any) -> None:
    """``group_ids`` must be a list of non-empty strings."""
    with pytest.raises(TesseraStateError, match="snapshot group_ids must be strings"):
        validate_state_data(
            _state(_snapshot({"user_id": "user-1", "group_ids": group_ids}))
        )


def test_normalizes_valid_group_ids_by_dedup_and_sort() -> None:
    """Valid state is accepted and its group ids are deduped and sorted."""
    result = validate_state_data(
        _state(
            _snapshot(
                {
                    "user_id": "user-1",
                    "group_ids": ["tessera:b", "tessera:a", "tessera:a"],
                }
            ),
            apply_in_progress=True,
        )
    )

    assert result == {
        "pre_install_snapshot": {
            "users": [{"user_id": "user-1", "group_ids": ["tessera:a", "tessera:b"]}]
        },
        "apply_in_progress": True,
    }


def test_accepts_default_state_unchanged() -> None:
    """The empty default recovery state round-trips through validation."""
    assert validate_state_data(default_state_data()) == default_state_data()
