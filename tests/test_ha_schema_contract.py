"""Contract tests for the schema library Tessera builds its own schemas with.

Home Assistant is migrating voluptuous -> probatio in two steps that do not
coincide: 2026.9 ships probatio and installs it *as* voluptuous at import time,
2026.10 flips the type annotations. ``custom_components/tessera/_vol.py``
depends on the runtime half of that — ``import voluptuous`` yielding probatio
wherever probatio exists — and deliberately leaves the static half untyped,
because no concrete type fits all four validated lines at once.

These tests pin the runtime half against the *installed* Home Assistant, so the
day HA drops the shim (or stops installing it) shows up here instead of as a
schema that silently stops validating service calls. See
docs/MAINTENANCE.md for the validation workflow.
"""

from __future__ import annotations

import importlib
import importlib.util

import pytest

# Import Home Assistant first, exactly as a running instance does: the shim is
# installed from homeassistant/__init__.py, and a module that already holds the
# real voluptuous keeps it. Tessera's own import is pulled in afterwards.
pytest.importorskip(
    "homeassistant", reason="contract tests need a real Home Assistant install"
)

HAS_PROBATIO = importlib.util.find_spec("probatio") is not None


def test_voluptuous_resolves_to_probatio_exactly_when_probatio_is_installed() -> None:
    """``import voluptuous`` follows whatever the installed HA line ships.

    On 2026.7/2026.8 there is no probatio and voluptuous is the real library;
    from 2026.9 Home Assistant replaces the ``sys.modules`` entry with its
    probatio shim, so the same import yields probatio objects.
    """
    vol_module = importlib.import_module("voluptuous")
    resolves_to_probatio = vol_module.Schema.__module__.startswith("probatio")

    assert resolves_to_probatio is HAS_PROBATIO, (
        f"probatio installed: {HAS_PROBATIO}, but voluptuous.Schema comes from "
        f"{vol_module.Schema.__module__} — _vol.py assumes these move together"
    )


def test_tessera_builds_schemas_with_the_library_home_assistant_validates_with() -> (
    None
):
    """Tessera's ``vol`` is the very library HA's own validators use.

    Mixing the two is the failure this guards: Tessera would build real
    voluptuous markers while HA validates with probatio (or the reverse), and
    service and websocket schemas would be validated by a library that does not
    recognise them.
    """
    tessera_vol = importlib.import_module("custom_components.tessera._vol").vol
    ha_vol = importlib.import_module("voluptuous")

    assert tessera_vol.Schema is ha_vol.Schema, (
        "custom_components.tessera._vol imported a different schema library than "
        "the one Home Assistant has in sys.modules — check import order"
    )


@pytest.mark.skipif(not HAS_PROBATIO, reason="probatio arrives with HA 2026.9")
def test_probatio_still_offers_the_marker_api_tesseras_schemas_use() -> None:
    """The handful of voluptuous-style names Tessera builds schemas from exist."""
    vol = importlib.import_module("custom_components.tessera._vol").vol

    for name in ("Schema", "Required", "Optional", "All", "In"):
        assert hasattr(vol, name), f"schema library has no {name}"
