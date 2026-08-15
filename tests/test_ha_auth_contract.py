"""Contract tests against the *installed* Home Assistant, not a test double.

Tessera's enforce path writes through a small subset of HA's private auth store
(``AuthStore._groups``, ``AuthStore._data_to_save``, ``models.Group``, and the
``permissions`` policy shape). Every other test in this suite exercises that
path through ``FakeHass``/``FakeGroup`` doubles, which by construction keep
matching the Protocols in ``auth_adapter`` even after HA changes underneath.

These tests close that blind spot: they assert the same subset against whatever
Home Assistant is actually installed, so a breaking upstream change surfaces as
a red test rather than as a silent fail-closed drop to ``monitor`` on a user's
box. See docs/MAINTENANCE.md for the validation workflow.
"""

from __future__ import annotations

import inspect

import pytest
from custom_components.tessera.auth_adapter import (
    SUPPORTED_HA_AUTH_FEATURES,
    _ha_feature_line,
)

# Import the submodule explicitly: ``import homeassistant`` alone does not bind
# ``homeassistant.const``, so reaching through the package only works when some
# other import happened to load it first (as pytest-homeassistant-custom-
# component's conftest does). These tests must also run in a bare environment
# that has nothing but Home Assistant itself installed.
ha_const = pytest.importorskip(
    "homeassistant.const", reason="contract tests need a real Home Assistant install"
)

HA_VERSION: str = ha_const.__version__


def _installed_feature_line() -> str:
    """Return the ``YEAR.MONTH`` line of the installed Home Assistant."""
    return _ha_feature_line(HA_VERSION)


def _line_sort_key(feature_line: str) -> tuple[int, int]:
    """Order feature lines numerically, so 2026.10 sorts after 2026.7."""
    year, month = feature_line.split(".")[:2]
    return int(year), int(month)


def test_installed_ha_line_is_validated() -> None:
    """Fail loudly when running against an HA line nobody has validated yet.

    This is the early-warning half of the version guard. The guard itself is
    fail-closed at runtime (users silently drop to ``monitor``); this test makes
    the same condition visible in CI the moment HA ships a new monthly line, so
    the line gets diffed and validated deliberately.

    An *older* line is skipped rather than failed: a stale development
    environment is not a product defect.
    """
    installed = _installed_feature_line()
    validated = sorted(SUPPORTED_HA_AUTH_FEATURES, key=_line_sort_key)
    if _line_sort_key(installed) < _line_sort_key(validated[0]):
        pytest.skip(
            f"installed HA {installed} predates every validated line "
            f"({validated}) — stale dev environment"
        )

    assert installed in SUPPORTED_HA_AUTH_FEATURES, (
        f"Home Assistant {HA_VERSION} is newer than every "
        f"validated line {validated}. Diff HA's "
        "homeassistant/auth/auth_store.py, auth/models.py and auth/permissions/ "
        "against the newest validated tag; if the touched subset is unchanged, "
        "add the line to SUPPORTED_HA_AUTH_FEATURES (docs/MAINTENANCE.md)."
    )


def test_installed_auth_store_exposes_the_internals_tessera_writes_through() -> None:
    """The private auth-store subset behind ``AuthStoreLike`` still exists."""
    from homeassistant.auth.auth_store import AuthStore

    assert callable(getattr(AuthStore, "async_get_groups", None))
    assert inspect.iscoroutinefunction(AuthStore.async_get_groups)
    assert callable(getattr(AuthStore, "_data_to_save", None))

    source = inspect.getsource(AuthStore)
    assert "self._groups" in source, "AuthStore no longer keeps a _groups mapping"
    assert "self._store" in source, "AuthStore no longer keeps a _store handle"


def test_installed_group_model_matches_the_adapter_group_protocol() -> None:
    """``models.Group`` still carries the fields ``AuthGroupLike`` declares."""
    from homeassistant.auth import models

    group = models.Group(
        id="tessera:contract",
        name="Contract",
        policy={"entities": {"entity_ids": {"light.kitchen": True}}},
        system_generated=False,
    )

    assert group.id == "tessera:contract"
    assert group.name == "Contract"
    assert group.policy == {"entities": {"entity_ids": {"light.kitchen": True}}}
    assert group.system_generated is False


def test_installed_permissions_accept_tesseras_allow_only_policy_shape() -> None:
    """HA still grants exactly what Tessera's compiled allow-only policy says."""
    from homeassistant.auth.permissions import PolicyPermissions

    # ``perm_lookup`` stays None on purpose: it is only consulted for the
    # area/device/domain sub-policies, and Tessera compiles entity_ids only.
    # Passing None here keeps the contract test free of a hass fixture while
    # still exercising HA's real policy compiler.
    permissions = PolicyPermissions(
        {"entities": {"entity_ids": {"light.kitchen": True}}},
        None,  # type: ignore[arg-type]
    )

    assert permissions.check_entity("light.kitchen", "read") is True
    assert permissions.check_entity("light.hallway", "read") is False
