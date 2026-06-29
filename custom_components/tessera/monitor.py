"""Monitor-mode helpers for Tessera policy compilation."""

from __future__ import annotations

import logging
from typing import TypedDict

from .compiler import CompiledPolicies, compile_policies
from .linter import LintReport, empty_lint_report, lint_cross_role
from .resolver import AreaEntityResolver
from .schema import TesseraConfigData, TesseraPolicyData
from .store import TesseraStore

LOGGER = logging.getLogger(__name__)


class RolePreview(TypedDict):
    """Redacted policy summary for one role."""

    entities: int
    read: int
    control: int


class MonitorPreview(TypedDict):
    """Redacted monitor-mode policy summary."""

    roles: dict[str, RolePreview]
    roles_total: int
    entities_total: int
    read_total: int
    control_total: int
    lint: LintReport


async def compile_current(
    store: TesseraStore,
    resolver: AreaEntityResolver,
    *,
    config: TesseraConfigData | None = None,
    policy: TesseraPolicyData | None = None,
) -> CompiledPolicies:
    """Compile the current Tessera stores into an in-memory native policy.

    Args:
        store: Tessera storage adapter.
        resolver: Area resolver used to expand policy area grants.
        config: Optional preloaded config store payload.
        policy: Optional preloaded policy store payload.

    Returns:
        Deterministic native Home Assistant policy projection.
    """
    config_data = config if config is not None else await store.async_load_config()
    policy_data = policy if policy is not None else await store.async_load_policy()
    return compile_policies(config_data, policy_data, resolver)


def monitor_preview(
    compiled: CompiledPolicies, *, lint_report: LintReport | None = None
) -> MonitorPreview:
    """Build a redacted summary of a compiled policy.

    Args:
        compiled: Native policy projection from the compiler.
        lint_report: Optional cross-role lint report to include in preview output.

    Returns:
        Count-only summary suitable for monitor-mode logs.
    """
    roles: dict[str, RolePreview] = {}
    for role_id, role_policy in sorted(compiled.items()):
        entity_ids = role_policy["entities"]["entity_ids"]
        read = sum(1 for leaf in entity_ids.values() if leaf.get("read") is True)
        control = sum(1 for leaf in entity_ids.values() if leaf.get("control") is True)
        roles[role_id] = {
            "entities": len(entity_ids),
            "read": read,
            "control": control,
        }

    return {
        "roles": roles,
        "roles_total": len(roles),
        "entities_total": sum(role["entities"] for role in roles.values()),
        "read_total": sum(role["read"] for role in roles.values()),
        "control_total": sum(role["control"] for role in roles.values()),
        "lint": lint_report or empty_lint_report(),
    }


def log_monitor_preview(
    compiled: CompiledPolicies,
    *,
    mode: str,
    lint_report: LintReport | None = None,
    logger: logging.Logger | None = None,
) -> MonitorPreview:
    """Log and return the redacted monitor-mode preview.

    Args:
        compiled: Native policy projection from the compiler.
        mode: Tessera operating mode that produced the preview.
        lint_report: Optional cross-role lint report to include in the preview.
        logger: Optional logger for tests.

    Returns:
        The redacted count-only preview.
    """
    preview = monitor_preview(compiled, lint_report=lint_report)
    target_logger = logger or LOGGER
    target_logger.info(
        "Tessera %s preview: roles=%d entities=%d read=%d control=%d "
        "lint_conflicts=%d lint_blocking=%s role_counts=%s",
        mode,
        preview["roles_total"],
        preview["entities_total"],
        preview["read_total"],
        preview["control_total"],
        preview["lint"]["conflicts_total"],
        preview["lint"]["blocking_conflicts"],
        preview["roles"],
    )
    return preview


def lint_current_preview(
    config: TesseraConfigData,
    policy: TesseraPolicyData,
    resolver: AreaEntityResolver,
    compiled: CompiledPolicies,
) -> LintReport:
    """Return the read-only cross-role lint report for monitor previews."""
    return lint_cross_role(config, policy, resolver, compiled=compiled)
