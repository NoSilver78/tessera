"""Tests for D5 recovery-gate verdict truthfulness."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def load_spike_runner() -> ModuleType:
    """Load the dev spike runner without importing Home Assistant."""
    path = (
        Path(__file__).resolve().parents[1]
        / "spike"
        / "tools"
        / "tessera_spike"
        / "d0_preflight_spike.py"
    )
    spec = importlib.util.spec_from_file_location("d0_preflight_spike", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def d5_pass_result() -> dict[str, object]:
    """Return the minimal measured D5 PASS shape."""
    return {
        "pre_restart": {},
        "post_restart": {
            "d5_boot_rescue_after_restart": {
                "requested": True,
                "snapshot_present": True,
                "run_id_matches": True,
                "auth_store_corrupted": True,
                "managed_group_replace_drift_injected": True,
                "boot_rescue_corruption_tested": True,
                "no_admin_lockout": True,
                "rescue_independent_of_healthy_tessera": True,
                "reread_state_matches_intended": True,
                "owner_system_unmanaged_never_touched": True,
                "rescue_restore_namespace_guarded": True,
                "post_boot_measured": True,
                "errors": [],
                "verdict": "PASS",
            }
        },
        "d5_authstore_corruption_observation": {"d5_pass_lever": False},
    }


def test_d5_pass_requires_all_measured_flags() -> None:
    """D5 passes only when all measured S1/S1b conditions are explicitly true."""
    runner = load_spike_runner()

    verdicts = runner.verdicts_from_result(d5_pass_result(), True)

    assert verdicts["D5"]["verdict"] == "PASS"


def test_d5_missing_one_flag_stays_partial() -> None:
    """Any missing required D5 flag keeps the gate PARTIAL."""
    runner = load_spike_runner()
    result = d5_pass_result()
    rescue = result["post_restart"]["d5_boot_rescue_after_restart"]
    rescue["no_admin_lockout"] = False

    verdicts = runner.verdicts_from_result(result, True)

    assert verdicts["D5"]["verdict"] == "PARTIAL"


def test_d5_s2_observation_never_creates_pass() -> None:
    """S2 auth-store corruption observation is not a D5 PASS lever."""
    runner = load_spike_runner()
    result = d5_pass_result()
    result["d5_authstore_corruption_observation"] = {
        "d5_pass_lever": True,
        "auth_store_corruption_injected": True,
        "auth_store_restored_from_backup": True,
    }

    verdicts = runner.verdicts_from_result(result, True)

    assert verdicts["D5"]["verdict"] == "PARTIAL"
