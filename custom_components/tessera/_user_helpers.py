"""Shared helpers for Home Assistant user-like objects."""

from __future__ import annotations

from typing import Any


def _user_group_ids(user: Any) -> list[str]:
    """Return sorted group ids from HA user or test double objects."""
    if hasattr(user, "group_ids"):
        return sorted(str(group_id) for group_id in user.group_ids)
    return sorted(str(group.id) for group in user.groups)


def _is_unmanaged_user(user: Any) -> bool:
    """Return whether Tessera must not manage this user."""
    return bool(getattr(user, "is_owner", False)) or bool(
        getattr(user, "system_generated", False)
    )
