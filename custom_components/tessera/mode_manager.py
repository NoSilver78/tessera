"""Dormant read-only enforce planning for Tessera E3.1."""

from __future__ import annotations

from typing import Any, Literal, Protocol, TypedDict, cast

from .auth_adapter import (
    TESSERA_GROUP_PREFIX,
    UnsupportedAuthVersion,
    _assert_supported_auth_version,
    _homeassistant_version,
)
from .compiler import NativePolicy
from .d9_gate import evaluate_d9_gate
from .linter import LintReport, has_blocking_conflicts, lint_cross_role
from .monitor import compile_current
from .resolver import AreaEntityResolver
from .schema import TesseraConfigData, TesseraPolicyData

BlockReason = Literal["version", "compile", "d9", "linter"]


class GroupPlan(TypedDict):
    """Read-only native group policy projection for one Tessera role."""

    group_id: str
    role_id: str
    policy: NativePolicy


class EnforcePlan(TypedDict):
    """Read-only E3 enforce plan, blocked before any native write surface."""

    groups: list[GroupPlan]
    blocked: bool
    block_reason: BlockReason | None
    block_detail: list[str]


class _StoreLike(Protocol):
    """Small store subset needed by the dormant mode manager."""

    async def async_load_config(self) -> TesseraConfigData:
        """Load Tessera configuration."""
        ...

    async def async_load_policy(self) -> TesseraPolicyData:
        """Load Tessera policy."""
        ...


async def compute_enforce_plan(hass: object, store: _StoreLike) -> EnforcePlan:
    """Compute the read-only E3.1 enforce plan without touching ``hass.auth``.

    The gate sequence is fail-closed and intentionally dormant: it is not wired
    into setup, websocket, config-flow, or monitor paths. It performs no native
    auth writes and does not enumerate native HA users. E3.2/E3.3 own those
    later surfaces.

    Args:
        hass: Home Assistant instance or test double.
        store: Tessera store adapter or test double.

    Returns:
        A deterministic group-policy plan, or an empty blocked plan when any
        gate refuses enforce.
    """
    try:
        _assert_supported_auth_version(_homeassistant_version())
    except UnsupportedAuthVersion as error:
        return _blocked("version", [str(error)])

    resolver = AreaEntityResolver.from_hass(cast(Any, hass))
    config = await store.async_load_config()
    policy = await store.async_load_policy()

    try:
        compiled = await compile_current(
            cast(Any, store), resolver, config=config, policy=policy
        )
    except Exception as error:
        return _blocked("compile", [f"{type(error).__name__}: {error}"])

    d9 = await evaluate_d9_gate(hass, config)  # type: ignore[arg-type]
    if d9["enforce_blocked"]:
        return _blocked("d9", list(d9["blocking"]))

    lint_report = lint_cross_role(config, policy, resolver, compiled=compiled)
    if has_blocking_conflicts(lint_report):
        return _blocked("linter", _lint_block_detail(lint_report))

    return {
        "groups": [
            {
                "group_id": f"{TESSERA_GROUP_PREFIX}{role_id}",
                "role_id": role_id,
                "policy": compiled[role_id],
            }
            for role_id in sorted(compiled)
        ],
        "blocked": False,
        "block_reason": None,
        "block_detail": [],
    }


def _blocked(reason: BlockReason, detail: list[str]) -> EnforcePlan:
    return {
        "groups": [],
        "blocked": True,
        "block_reason": reason,
        "block_detail": sorted(detail),
    }


def _lint_block_detail(report: LintReport) -> list[str]:
    details: list[str] = []
    for user_id, user_report in sorted(report["users"].items()):
        for conflict in user_report["conflicts"]:
            details.append(
                ":".join(
                    (
                        user_id,
                        conflict["entity_id"],
                        conflict["level"],
                        ",".join(conflict["restricting_roles"]),
                        "blocked-by",
                        ",".join(conflict["exposing_roles"]),
                    )
                )
            )
    return details
