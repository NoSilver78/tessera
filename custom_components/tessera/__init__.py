"""Tessera — RBAC for Home Assistant.

Store -> Compiler -> native HA ``PolicyPermissions``. The store is the single
source of truth; the compiler projects it into native group policies. See
``docs/spec-phase1-core.md`` for the architecture.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import voluptuous as vol
from homeassistant.components.frontend import async_remove_panel
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.panel_custom import async_register_panel
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import HomeAssistantError, Unauthorized, UnknownUser
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.util import dt as dt_util

from . import websocket as tessera_websocket
from ._user_helpers import _is_unmanaged_user
from .auth_adapter import (
    AuthPolicyStoreAdapter,
    HassAuthLike,
    RecoveryController,
    UserBindingAdapter,
)
from .compiler import compile_policies
from .config_flow import set_floor_grant, set_user_membership
from .const import DOMAIN, MODE_ENFORCE, MODE_MONITOR, MODE_OFF
from .d9_gate import compute_component_ack_target, evaluate_d9_gate
from .linter import lint_cross_role
from .mode_manager import apply_enforce_plan, compute_enforce_plan
from .monitor import compile_current, lint_current_preview, log_monitor_preview
from .resolver import AreaEntityResolver
from .restore import async_restore_to_pre_install
from .schema import (
    D9AckData,
    TesseraConfigData,
    TesseraPolicyData,
    TesseraSchemaError,
    validate_config_data,
    validate_policy_data,
)
from .state import (
    TesseraStateData,
    decide_startup_recovery,
    snapshot_from_state_data,
)
from .store import TesseraStore, mutation_lock

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse

LOGGER = logging.getLogger(__name__)
SERVICE_RECOMPILE = "recompile"
SERVICE_ACK_COMPONENT = "acknowledge_component"
SERVICE_REVOKE_COMPONENT_ACK = "revoke_component_ack"
SERVICE_COMPONENT_SCHEMA = vol.Schema({vol.Required("domain"): cv.string})
SERVICE_SET_MEMBERSHIP = "set_membership"
SERVICE_SET_MEMBERSHIP_SCHEMA = vol.Schema(
    {
        vol.Required("user_id"): cv.string,
        vol.Required("role_ids"): vol.All(cv.ensure_list, [cv.string]),
    }
)
SERVICE_SET_FLOOR_GRANT = "set_floor_grant"
SERVICE_SET_FLOOR_GRANT_SCHEMA = vol.Schema(
    {
        vol.Required("floor_id"): cv.string,
        vol.Required("role_id"): cv.string,
        vol.Required("read"): cv.boolean,
        vol.Required("control"): cv.boolean,
    }
)
SERVICE_IMPORT = "import"
SERVICE_IMPORT_SCHEMA = vol.Schema(
    {
        vol.Optional("roles"): dict,
        vol.Optional("memberships"): dict,
        vol.Optional("area_grants"): dict,
        vol.Optional("floor_grants"): dict,
        vol.Optional("entity_overrides"): dict,
    }
)
SERVICE_PREFLIGHT = "preflight"
# Bookkeeping sentinels stored in the domain bucket alongside per-entry dicts.
# Their values are non-dict (bool), so the isinstance(dict) filter in
# _has_loaded_entries cleanly distinguishes them from real entry data.
DATA_SERVICE_REGISTERED = "__recompile_service_registered"
DATA_ACK_SERVICES_REGISTERED = "__ack_services_registered"
DATA_WEBSOCKET_REGISTERED = "__websocket_registered"
DATA_PANEL_REGISTERED = "__panel_registered"
DATA_MEMBERSHIP_SERVICE_REGISTERED = "__membership_service_registered"
DATA_FLOOR_GRANT_SERVICE_REGISTERED = "__floor_grant_service_registered"
DATA_IMPORT_SERVICE_REGISTERED = "__import_service_registered"
DATA_PREFLIGHT_SERVICE_REGISTERED = "__preflight_service_registered"
PANEL_URL_PATH = "tessera"
PANEL_WEBCOMPONENT = "tessera-matrix-panel"
PANEL_STATIC_URL = "/tessera_static/tessera-panel.js"
PANEL_STATIC_DIR = Path(__file__).parent / "static"
REPAIR_ENFORCE_FAIL_SAFE = "enforce_fail_safe"
REPAIR_RESTORE_FAIL_SAFE = "restore_fail_safe"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tessera from a config entry.

    Args:
        hass: The Home Assistant instance.
        entry: The config entry being set up.

    Returns:
        ``True`` once setup succeeds.
    """
    domain_data = _domain_data(hass)
    domain_data[entry.entry_id] = {"store": TesseraStore(hass)}
    _register_recompile_service(hass)
    _register_ack_services(hass)
    _register_membership_service(hass)
    _register_floor_grant_service(hass)
    _register_import_service(hass)
    _register_preflight_service(hass)
    _register_websocket_api(hass)
    await _async_register_matrix_panel(hass)
    recovered = await _startup_recovery_safely(
        hass, entry.entry_id, domain_data[entry.entry_id]
    )
    if recovered:
        await _compile_for_mode_safely(
            hass, entry.entry_id, domain_data[entry.entry_id]
        )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry.

    If the entry is leaving enforce mode, restore native policies before
    tearing down Tessera's in-memory entry data.

    Args:
        hass: The Home Assistant instance.
        entry: The config entry being unloaded.

    Returns:
        ``True`` once unload succeeds.
    """
    domain_data = _domain_data(hass)
    entry_data = domain_data.get(entry.entry_id)
    if isinstance(entry_data, dict):
        await _restore_on_enforce_exit_safely(hass, entry.entry_id, entry_data)
    domain_data.pop(entry.entry_id, None)
    if not _has_loaded_entries(domain_data):
        if domain_data.pop(DATA_PANEL_REGISTERED, None) is True:
            async_remove_panel(hass, PANEL_URL_PATH, warn_if_unknown=False)
        hass.services.async_remove(DOMAIN, SERVICE_RECOMPILE)
        hass.services.async_remove(DOMAIN, SERVICE_ACK_COMPONENT)
        hass.services.async_remove(DOMAIN, SERVICE_REVOKE_COMPONENT_ACK)
        hass.services.async_remove(DOMAIN, SERVICE_SET_MEMBERSHIP)
        hass.services.async_remove(DOMAIN, SERVICE_SET_FLOOR_GRANT)
        hass.services.async_remove(DOMAIN, SERVICE_IMPORT)
        hass.services.async_remove(DOMAIN, SERVICE_PREFLIGHT)
        domain_data.pop(DATA_SERVICE_REGISTERED, None)
        domain_data.pop(DATA_ACK_SERVICES_REGISTERED, None)
        domain_data.pop(DATA_MEMBERSHIP_SERVICE_REGISTERED, None)
        domain_data.pop(DATA_FLOOR_GRANT_SERVICE_REGISTERED, None)
        domain_data.pop(DATA_IMPORT_SERVICE_REGISTERED, None)
        domain_data.pop(DATA_PREFLIGHT_SERVICE_REGISTERED, None)
    return True


def _register_recompile_service(hass: HomeAssistant) -> None:
    """Register the recompile service once per HA instance."""
    domain_data = _domain_data(hass)
    if domain_data.get(DATA_SERVICE_REGISTERED) is True:
        return

    async def _handle_recompile(call: ServiceCall) -> None:
        """Recompile every loaded Tessera entry for its current mode.

        In off/monitor this rebuilds the read-only projection only; in enforce it
        re-applies the native auth bindings (writes the auth store), like setup.
        """
        del call  # parameterless service; the call carries no Tessera input
        for key, entry_data in list(_domain_data(hass).items()):
            if key == DATA_SERVICE_REGISTERED or not isinstance(entry_data, dict):
                continue
            await _compile_for_mode_safely(hass, key, entry_data)

    hass.services.async_register(DOMAIN, SERVICE_RECOMPILE, _handle_recompile)
    domain_data[DATA_SERVICE_REGISTERED] = True


def _register_ack_services(hass: HomeAssistant) -> None:
    """Register the admin-only D9 ack services once per HA instance.

    A D9 ack is a deliberate admin override of an auth-touching component's
    enforce veto, so both services are gated through HA's
    ``async_register_admin_service`` (the caller must be an admin). The one
    inherited caveat is HA platform behaviour: a context-less/internal service
    call (no ``context.user_id``) skips HA's admin check — but reaching that
    still requires admin rights elsewhere (e.g. editing an automation).
    """
    domain_data = _domain_data(hass)
    if domain_data.get(DATA_ACK_SERVICES_REGISTERED) is True:
        return

    async def _handle_acknowledge(call: ServiceCall) -> None:
        domain = str(call.data["domain"])
        target = await compute_component_ack_target(hass, domain)  # type: ignore[arg-type]
        if target is None:
            raise HomeAssistantError(
                f"Cannot acknowledge unknown or non-disk component: {domain}"
            )

        accepted_at = dt_util.utcnow().isoformat()
        ack: D9AckData = {
            "version": target["version"],
            "content_hash": target["content_hash"],
            "accepted_at": accepted_at,
        }
        # Tessera runs single-entry in practice; the loop applies the ack to
        # every loaded entry (an ack is a global "trust this component"). The
        # per-entry load->save->recompile is fail-safe by direction: a save
        # error propagates to the admin, and any entry not yet acked simply
        # stays MORE restrictive (its veto still blocks enforce). No native auth
        # is half-written — recompile is fail-safe-to-monitor with its own
        # rollback.
        async with mutation_lock(hass):
            for key, entry_data in list(_domain_data(hass).items()):
                if not isinstance(entry_data, dict):
                    continue
                store = cast(TesseraStore, entry_data["store"])
                config = await store.async_load_config()
                config["d9_acks"] = {**config["d9_acks"], domain: ack}
                await store.async_save_config(config)
                await _compile_for_mode_safely(hass, key, entry_data)
                LOGGER.warning(
                    "Tessera D9 component ack recorded: domain=%s version=%s",
                    domain,
                    target["version"],
                )

    async def _handle_revoke(call: ServiceCall) -> None:
        domain = str(call.data["domain"])
        async with mutation_lock(hass):
            for key, entry_data in list(_domain_data(hass).items()):
                if not isinstance(entry_data, dict):
                    continue
                store = cast(TesseraStore, entry_data["store"])
                config = await store.async_load_config()
                revoked_ack = config["d9_acks"].get(domain)
                config["d9_acks"] = {
                    ack_domain: ack_entry
                    for ack_domain, ack_entry in config["d9_acks"].items()
                    if ack_domain != domain
                }
                await store.async_save_config(config)
                await _compile_for_mode_safely(hass, key, entry_data)
                LOGGER.warning(
                    "Tessera D9 component ack revoked: domain=%s version=%s",
                    domain,
                    revoked_ack.get("version") if revoked_ack is not None else None,
                )

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_ACK_COMPONENT,
        _handle_acknowledge,
        schema=SERVICE_COMPONENT_SCHEMA,
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_REVOKE_COMPONENT_ACK,
        _handle_revoke,
        schema=SERVICE_COMPONENT_SCHEMA,
    )
    domain_data[DATA_ACK_SERVICES_REGISTERED] = True


def _register_membership_service(hass: HomeAssistant) -> None:
    """Register the admin-only user membership writer once per HA instance."""
    domain_data = _domain_data(hass)
    if domain_data.get(DATA_MEMBERSHIP_SERVICE_REGISTERED) is True:
        return

    async def _handle_set_membership(call: ServiceCall) -> None:
        user_id = str(call.data["user_id"])
        role_ids = [str(role_id) for role_id in call.data["role_ids"]]
        await _assert_membership_target_user(hass, user_id)

        prepared_configs: list[
            tuple[str, dict[str, Any], TesseraStore, TesseraConfigData]
        ]
        prepared_configs = []
        async with mutation_lock(hass):
            for key, entry_data in list(_domain_data(hass).items()):
                if not isinstance(entry_data, dict):
                    continue
                store = cast(TesseraStore, entry_data["store"])
                config = await store.async_load_config()
                next_config = set_user_membership(config, user_id, role_ids)
                prepared_configs.append((key, entry_data, store, next_config))

            for key, entry_data, store, next_config in prepared_configs:
                await store.async_save_config(next_config)
                await _compile_for_mode_safely(hass, key, entry_data)
                LOGGER.warning(
                    "Tessera user membership updated: user_id=%s role_ids=%s",
                    user_id,
                    sorted(set(role_ids)),
                )

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_SET_MEMBERSHIP,
        _handle_set_membership,
        schema=SERVICE_SET_MEMBERSHIP_SCHEMA,
    )
    domain_data[DATA_MEMBERSHIP_SERVICE_REGISTERED] = True


def _register_floor_grant_service(hass: HomeAssistant) -> None:
    """Register the admin-only floor grant writer once per HA instance."""
    domain_data = _domain_data(hass)
    if domain_data.get(DATA_FLOOR_GRANT_SERVICE_REGISTERED) is True:
        return

    async def _handle_set_floor_grant(call: ServiceCall) -> None:
        floor_id = str(call.data["floor_id"])
        role_id = str(call.data["role_id"])
        read = bool(call.data["read"])
        control = bool(call.data["control"])
        _assert_floor_exists(hass, floor_id)

        prepared_policies: list[
            tuple[str, dict[str, Any], TesseraStore, TesseraPolicyData]
        ]
        prepared_policies = []
        async with mutation_lock(hass):
            for key, entry_data in list(_domain_data(hass).items()):
                if not isinstance(entry_data, dict):
                    continue
                store = cast(TesseraStore, entry_data["store"])
                config = await store.async_load_config()
                policy = await store.async_load_policy()
                next_policy = set_floor_grant(
                    config,
                    policy,
                    floor_id=floor_id,
                    role_id=role_id,
                    read=read,
                    control=control,
                )
                prepared_policies.append((key, entry_data, store, next_policy))

            for key, entry_data, store, next_policy in prepared_policies:
                await store.async_save_policy(next_policy)
                await _compile_for_mode_safely(hass, key, entry_data)
                LOGGER.warning(
                    "Tessera floor grant updated: "
                    "floor_id=%s role_id=%s read=%s control=%s",
                    floor_id,
                    role_id,
                    read,
                    control,
                )

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_SET_FLOOR_GRANT,
        _handle_set_floor_grant,
        schema=SERVICE_SET_FLOOR_GRANT_SCHEMA,
    )
    domain_data[DATA_FLOOR_GRANT_SERVICE_REGISTERED] = True


def _register_import_service(hass: HomeAssistant) -> None:
    """Register the admin-only declarative model-import service once per instance.

    ``tessera.import`` provisions the whole model in one idempotent call — the
    surface substitute while role/floor/membership editors are not yet in the
    panel/options-flow. Each PROVIDED dimension REPLACES that dimension
    declaratively; omitted dimensions are preserved. Operational fields (``mode``,
    ``membership.by_group``, ``d9_acks``, ``staging``) are ALWAYS preserved —
    import provisions the *model*, never the enforcement switch. It is fail-closed
    (schema + role-reference validation over ALL entries before the first save)
    and routes through the same guarded ``_compile_for_mode_safely`` path.
    """
    domain_data = _domain_data(hass)
    if domain_data.get(DATA_IMPORT_SERVICE_REGISTERED) is True:
        return

    async def _handle_import(call: ServiceCall) -> None:
        payload: Mapping[str, Any] = call.data
        async with mutation_lock(hass):
            prepared: list[
                tuple[
                    str,
                    dict[str, Any],
                    TesseraStore,
                    TesseraConfigData,
                    TesseraPolicyData,
                ]
            ]
            prepared = []
            for key, entry_data in list(_domain_data(hass).items()):
                if not isinstance(entry_data, dict):
                    continue
                store = cast(TesseraStore, entry_data["store"])
                config = await store.async_load_config()
                policy = await store.async_load_policy()
                next_config = _import_into_config(config, payload)
                next_policy = _import_into_policy(policy, payload)
                _assert_import_roles_resolve(next_config, next_policy)
                prepared.append((key, entry_data, store, next_config, next_policy))

            for key, entry_data, store, next_config, next_policy in prepared:
                await store.async_save_config(next_config)
                await store.async_save_policy(next_policy)
                await _compile_for_mode_safely(hass, key, entry_data)
                LOGGER.warning(
                    "Tessera model imported: roles=%d memberships=%d area_grants=%d "
                    "floor_grants=%d entity_overrides=%d",
                    len(next_config["roles"]),
                    len(next_config["membership"]["by_user"]),
                    sum(len(m) for m in next_policy["area_grants"].values()),
                    sum(len(m) for m in next_policy["floor_grants"].values()),
                    sum(len(m) for m in next_policy["entity_overrides"].values()),
                )

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_IMPORT,
        _handle_import,
        schema=SERVICE_IMPORT_SCHEMA,
    )
    domain_data[DATA_IMPORT_SERVICE_REGISTERED] = True


def _import_into_config(
    config: TesseraConfigData, payload: Mapping[str, Any]
) -> TesseraConfigData:
    """Return config with provided model dimensions replaced (declarative)."""
    next_config = validate_config_data(config)
    if "roles" in payload:
        next_config["roles"] = payload["roles"]
    if "memberships" in payload:
        next_config["membership"]["by_user"] = payload["memberships"]
    return validate_config_data(next_config)


def _import_into_policy(
    policy: TesseraPolicyData, payload: Mapping[str, Any]
) -> TesseraPolicyData:
    """Return policy with provided grant dimensions replaced (declarative)."""
    next_policy = validate_policy_data(policy)
    if "area_grants" in payload:
        next_policy["area_grants"] = payload["area_grants"]
    if "floor_grants" in payload:
        next_policy["floor_grants"] = payload["floor_grants"]
    if "entity_overrides" in payload:
        next_policy["entity_overrides"] = payload["entity_overrides"]
    return validate_policy_data(next_policy)


def _assert_import_roles_resolve(
    config: TesseraConfigData, policy: TesseraPolicyData
) -> None:
    """Fail closed if any imported grant or membership references an unknown role."""
    known = set(config["roles"])
    for name, matrix in (
        ("area_grants", policy["area_grants"]),
        ("floor_grants", policy["floor_grants"]),
        ("entity_overrides", policy["entity_overrides"]),
    ):
        for target, role_map in matrix.items():
            unknown = sorted(role for role in role_map if role not in known)
            if unknown:
                raise TesseraSchemaError(
                    f"import: policy.{name}.{target} references unknown roles: "
                    f"{unknown}"
                )
    for role_ids in config["membership"]["by_user"].values():
        unknown = sorted(role for role in role_ids if role not in known)
        if unknown:
            raise TesseraSchemaError(
                f"import: membership references unknown roles: {unknown}"
            )


def _register_preflight_service(hass: HomeAssistant) -> None:
    """Register the admin-only, read-only enforce-preflight service once per instance.

    Provisioning tells you nothing about whether ``enforce`` would actually succeed.
    ``tessera.preflight`` runs the full enforce-planning pipeline READ-ONLY (no native
    write, no mode change) and returns it as a service response: the would-enforce
    verdict, the complete D9 component breakdown (which components would veto and why —
    the enforce-readiness blocker list), the cross-role linter conflicts, and a model
    summary. Registered directly with ``supports_response`` and a manual admin gate,
    because HA's ``async_register_admin_service`` cannot return a response.
    """
    domain_data = _domain_data(hass)
    if domain_data.get(DATA_PREFLIGHT_SERVICE_REGISTERED) is True:
        return

    async def _handle_preflight(call: ServiceCall) -> ServiceResponse:
        # Admin gate mirrors homeassistant.helpers.service._async_admin_handler; this
        # read-only diagnostic exposes the RBAC model plus a custom-component scan.
        if call.context.user_id:
            user = await hass.auth.async_get_user(call.context.user_id)
            if user is None:
                raise UnknownUser(context=call.context)
            if not user.is_admin:
                raise Unauthorized(context=call.context)

        entry_data = next(
            (
                data
                for data in _domain_data(hass).values()
                if isinstance(data, dict) and "store" in data
            ),
            None,
        )
        if entry_data is None:
            raise HomeAssistantError("Tessera is not loaded")
        store = cast(TesseraStore, entry_data["store"])
        config = await store.async_load_config()
        policy = await store.async_load_policy()
        resolver = AreaEntityResolver.from_hass(hass)
        # Full D9 breakdown: compute_enforce_plan short-circuits at the first blocker,
        # so evaluate the gate directly to enumerate ALL components + verdicts.
        d9 = await evaluate_d9_gate(hass, config, self_domain=DOMAIN)  # type: ignore[arg-type]
        compiled = compile_policies(config, policy, resolver)
        lint = lint_cross_role(config, policy, resolver, compiled=compiled)
        # Authoritative "would enforce succeed" verdict — never writes native auth.
        plan = await compute_enforce_plan(hass, store)
        return _preflight_response(config, policy, compiled, plan, d9, lint)

    hass.services.async_register(
        DOMAIN,
        SERVICE_PREFLIGHT,
        _handle_preflight,
        schema=vol.Schema({}),
        supports_response=SupportsResponse.ONLY,
    )
    domain_data[DATA_PREFLIGHT_SERVICE_REGISTERED] = True


def _preflight_response(
    config: TesseraConfigData,
    policy: TesseraPolicyData,
    compiled: Mapping[str, Any],
    plan: Mapping[str, Any],
    d9: Mapping[str, Any],
    lint: Mapping[str, Any],
) -> ServiceResponse:
    """Build the redacted, JSON-safe enforce-preflight report."""
    d9_components = {
        domain: {
            "verdict": result["verdict"],
            "source": result["source"],
            "reason": result["reason"],
            "version": result["version"],
        }
        for domain, result in sorted(d9["by_component"].items())
    }
    lint_conflicts = [
        {
            "user": conflict["user_id"][:8],
            "entity_id": conflict["entity_id"],
            "exposing_roles": conflict["exposing_roles"],
            "restricting_roles": conflict["restricting_roles"],
            "level": conflict["level"],
            "severity": conflict["severity"],
        }
        for report in lint["users"].values()
        for conflict in report["conflicts"]
    ]
    return {
        "mode": config["mode"],
        "would_enforce_succeed": not plan["blocked"],
        "blocked_reason": plan["block_reason"],
        "blocked_detail": plan["block_detail"],
        "d9": {
            "enforce_blocked": d9["enforce_blocked"],
            "blocking": sorted(d9["blocking"]),
            "components": d9_components,
        },
        "lint": {
            "conflicts_total": lint["conflicts_total"],
            "blocking": lint["blocking_conflicts"],
            "conflicts": lint_conflicts,
        },
        "model": {
            "roles": sorted(config["roles"]),
            "members": len(config["membership"]["by_user"]),
            "floor_grants": sum(len(m) for m in policy["floor_grants"].values()),
            "area_grants": sum(len(m) for m in policy["area_grants"].values()),
            "entity_overrides": sum(
                len(m) for m in policy["entity_overrides"].values()
            ),
            "compiled_entities_per_role": {
                role: len(compiled[role]["entities"]["entity_ids"])
                for role in sorted(compiled)
            },
        },
    }


async def _assert_membership_target_user(hass: HomeAssistant, user_id: str) -> None:
    """Fail closed unless ``user_id`` is a managed HA user."""
    if not user_id:
        raise HomeAssistantError("Cannot set Tessera membership for empty user id")
    user = (await _users_by_id(hass)).get(user_id)
    if user is None:
        raise HomeAssistantError("Cannot set Tessera membership for an unknown user")
    if _is_unmanaged_user(user):
        raise HomeAssistantError(
            "Cannot set Tessera membership for owner or system-generated users"
        )


def _assert_floor_exists(hass: HomeAssistant, floor_id: str) -> None:
    """Fail closed unless ``floor_id`` exists in Home Assistant's floor registry."""
    if not floor_id:
        raise HomeAssistantError("Cannot set Tessera grant for empty floor id")
    from homeassistant.helpers import floor_registry as fr

    if fr.async_get(hass).async_get_floor(floor_id) is None:
        raise HomeAssistantError(
            f"Cannot set Tessera grant for unknown floor: {floor_id}"
        )


def _register_websocket_api(hass: HomeAssistant) -> None:
    """Register Tessera's WebSocket API once per HA instance."""
    domain_data = _domain_data(hass)
    if domain_data.get(DATA_WEBSOCKET_REGISTERED) is True:
        return

    tessera_websocket.async_register(hass)
    domain_data[DATA_WEBSOCKET_REGISTERED] = True


async def _async_register_matrix_panel(hass: HomeAssistant) -> None:
    """Register the Tessera custom panel and its static JS module."""
    domain_data = _domain_data(hass)
    if domain_data.get(DATA_PANEL_REGISTERED) is True:
        return
    if not hasattr(hass, "http"):
        LOGGER.debug("Skipping Tessera panel registration without HA HTTP server")
        return

    await hass.http.async_register_static_paths(
        [StaticPathConfig("/tessera_static", str(PANEL_STATIC_DIR), False)]
    )
    await async_register_panel(
        hass,
        frontend_url_path=PANEL_URL_PATH,
        webcomponent_name=PANEL_WEBCOMPONENT,
        sidebar_title="Tessera",
        sidebar_icon="mdi:shield-account",
        module_url=PANEL_STATIC_URL,
        require_admin=True,
        config_panel_domain=DOMAIN,
    )
    domain_data[DATA_PANEL_REGISTERED] = True


async def _compile_for_mode_safely(
    hass: HomeAssistant, entry_id: str, entry_data: dict[str, Any]
) -> None:
    """Compile/apply the active mode, failing safe to monitor on errors."""
    try:
        await _compile_for_mode(hass, entry_id, entry_data)
    except Exception as err:
        await _fail_safe_to_monitor(
            hass,
            entry_id,
            entry_data,
            reason="compile",
            detail=err.__class__.__name__,
            refresh_preview=False,
        )
        LOGGER.error(
            "Tessera mode handling failed for entry %s; falling back to monitor "
            "mode (%s)",
            entry_id,
            err.__class__.__name__,
        )


async def _compile_for_mode(
    hass: HomeAssistant, entry_id: str, entry_data: dict[str, Any]
) -> None:
    """Handle Tessera's current mode.

    ``monitor`` compiles a read-only preview. ``enforce`` computes, journals,
    applies, and clears through the guarded native-auth adapters. Leaving
    ``enforce`` restores the immutable pre-install snapshot first.
    """
    store = cast(TesseraStore, entry_data["store"])
    config = await store.async_load_config()
    previous_mode = entry_data.get("mode")

    if previous_mode == MODE_ENFORCE and config["mode"] != MODE_ENFORCE:
        restored = await _restore_pre_install_safely(
            hass,
            entry_id,
            entry_data,
            reason="mode_switch",
            clear_apply_in_progress=True,
        )
        if not restored:
            await _fail_safe_to_monitor(
                hass,
                entry_id,
                entry_data,
                reason="mode_switch_restore_failed",
                refresh_preview=True,
            )
            return

    if config["mode"] == MODE_OFF:
        entry_data.pop("compiled", None)
        entry_data.pop("preview", None)
        entry_data["mode"] = MODE_OFF
        return

    if config["mode"] == MODE_MONITOR:
        await _compile_monitor_preview(hass, store, config, entry_data)
        entry_data["mode"] = MODE_MONITOR
        return

    if config["mode"] == MODE_ENFORCE:
        await _apply_enforce_mode(hass, entry_id, store, entry_data)
        return


async def _startup_recovery_safely(
    hass: HomeAssistant, entry_id: str, entry_data: dict[str, Any]
) -> bool:
    """Rollback an open startup journal before mode handling."""
    store = cast(TesseraStore, entry_data["store"])
    try:
        state = await store.async_load_state()
        decision = decide_startup_recovery(state)
        if decision == "none":
            return True
        if decision == "rollback":
            restored = await _restore_pre_install_safely(
                hass,
                entry_id,
                entry_data,
                reason="startup_recovery",
                state=state,
                clear_apply_in_progress=True,
            )
            if restored:
                return True
        await _fail_safe_to_monitor(
            hass,
            entry_id,
            entry_data,
            reason="startup_recovery",
            refresh_preview=False,
        )
        return False
    except Exception as err:
        await _fail_safe_to_monitor(
            hass,
            entry_id,
            entry_data,
            reason="startup_recovery",
            detail=err.__class__.__name__,
            refresh_preview=False,
        )
        LOGGER.error(
            "Tessera startup recovery failed for entry %s; falling back to "
            "monitor mode (%s)",
            entry_id,
            err.__class__.__name__,
        )
        return False


async def _compile_monitor_preview(
    hass: HomeAssistant,
    store: TesseraStore,
    config: TesseraConfigData,
    entry_data: dict[str, Any],
) -> None:
    """Compile and log a read-only monitor preview."""
    resolver = AreaEntityResolver.from_hass(hass)
    policy = await store.async_load_policy()
    compiled = await compile_current(store, resolver, config=config, policy=policy)
    lint_report = lint_current_preview(config, policy, resolver, compiled)
    entry_data["compiled"] = compiled
    entry_data["lint"] = lint_report
    entry_data["preview"] = log_monitor_preview(
        compiled, mode=config["mode"], lint_report=lint_report
    )


async def _apply_enforce_mode(
    hass: HomeAssistant,
    entry_id: str,
    store: TesseraStore,
    entry_data: dict[str, Any],
) -> None:
    """Run the E3.5 enforce sequence through guarded callables."""
    plan = await compute_enforce_plan(hass, store)
    if plan["blocked"]:
        await _fail_safe_to_monitor(
            hass,
            entry_id,
            entry_data,
            reason=f"blocked:{plan['block_reason']}",
            refresh_preview=True,
        )
        return

    users_by_id = await _users_by_id(hass)
    auth_hass = cast(HassAuthLike, hass)
    binding_adapter = UserBindingAdapter(auth_hass)
    recovery = RecoveryController(auth_hass, binding_adapter)
    state = await store.async_load_state()
    if state["pre_install_snapshot"] is None:
        snapshot = await recovery.async_snapshot(
            users_by_id.values(), include_without_tessera=True
        )
        await store.async_set_pre_install_snapshot(snapshot)
    else:
        snapshot = snapshot_from_state_data(state["pre_install_snapshot"])
    await store.async_mark_apply_in_progress(snapshot)

    result = await apply_enforce_plan(
        plan, AuthPolicyStoreAdapter(auth_hass), binding_adapter, users_by_id
    )
    entry_data["last_apply_result"] = result
    if result["status"] == "applied":
        await store.async_clear_apply_in_progress()
        entry_data["mode"] = MODE_ENFORCE
        return

    # Apply failed partway: native auth may be half-written. Roll back to the
    # pre-install snapshot IMMEDIATELY rather than leaving a half-enforced state
    # behind a monitor facade until the next startup recovery (a window in which
    # some users carry half-applied permissions). _restore_pre_install_safely
    # clears the journal on a clean rollback, or records a repair and leaves it
    # open (for startup recovery to retry) if the rollback itself fails.
    await _restore_pre_install_safely(
        hass,
        entry_id,
        entry_data,
        reason=f"apply_failed:{result['refused_reason'] or result['status']}",
        clear_apply_in_progress=True,
    )
    await _fail_safe_to_monitor(
        hass,
        entry_id,
        entry_data,
        reason=f"apply:{result['refused_reason'] or result['status']}",
        refresh_preview=True,
    )


async def _restore_on_enforce_exit_safely(
    hass: HomeAssistant, entry_id: str, entry_data: dict[str, Any]
) -> None:
    """Restore pre-install auth state when unloading a live enforce entry."""
    if entry_data.get("mode") != MODE_ENFORCE:
        return
    restored = await _restore_pre_install_safely(
        hass,
        entry_id,
        entry_data,
        reason="unload",
        clear_apply_in_progress=True,
    )
    if not restored:
        await _fail_safe_to_monitor(
            hass, entry_id, entry_data, reason="unload_restore_failed"
        )


async def _restore_pre_install_safely(
    hass: HomeAssistant,
    entry_id: str,
    entry_data: dict[str, Any],
    *,
    reason: str,
    state: TesseraStateData | None = None,
    clear_apply_in_progress: bool,
) -> bool:
    """Restore the immutable pre-install snapshot, redacting failures."""
    store = cast(TesseraStore, entry_data["store"])
    try:
        recovery_state = state or await store.async_load_state()
        snapshot_data = recovery_state["pre_install_snapshot"]
        if snapshot_data is None:
            return True
        users_by_id = await _users_by_id(hass)
        auth_hass = cast(HassAuthLike, hass)
        result = await async_restore_to_pre_install(
            snapshot_from_state_data(snapshot_data),
            AuthPolicyStoreAdapter(auth_hass),
            UserBindingAdapter(auth_hass),
            users_by_id,
        )
        entry_data["last_restore_result"] = result
        if result["status"] == "restored":
            if clear_apply_in_progress:
                await store.async_clear_apply_in_progress()
            return True
        await _record_repair_issue(
            hass,
            entry_id,
            REPAIR_RESTORE_FAIL_SAFE,
            reason=f"{reason}:{result['refused_reason'] or result['status']}",
        )
    except Exception as err:
        LOGGER.error(
            "Tessera restore failed for entry %s; falling back to monitor mode (%s)",
            entry_id,
            err.__class__.__name__,
        )
        await _record_repair_issue(
            hass,
            entry_id,
            REPAIR_RESTORE_FAIL_SAFE,
            reason=f"{reason}:{err.__class__.__name__}",
        )
    return False


async def _fail_safe_to_monitor(
    hass: HomeAssistant,
    entry_id: str,
    entry_data: dict[str, Any],
    *,
    reason: str,
    detail: str | None = None,
    refresh_preview: bool = False,
) -> None:
    """Persist monitor mode and avoid stale projections after an unsafe path."""
    store = cast(TesseraStore, entry_data["store"])
    entry_data.pop("compiled", None)
    entry_data.pop("preview", None)
    entry_data["mode"] = MODE_MONITOR
    await _record_repair_issue(
        hass,
        entry_id,
        REPAIR_ENFORCE_FAIL_SAFE,
        reason=reason if detail is None else f"{reason}:{detail}",
    )
    try:
        config = await _set_mode_monitor(store)
    except Exception as err:
        LOGGER.error(
            "Tessera could not persist monitor fail-safe for entry %s (%s)",
            entry_id,
            err.__class__.__name__,
        )
        return
    if refresh_preview and config is not None:
        try:
            await _compile_monitor_preview(hass, store, config, entry_data)
        except Exception as err:
            entry_data.pop("compiled", None)
            entry_data.pop("preview", None)
            LOGGER.error(
                "Tessera monitor preview after fail-safe failed for entry %s (%s)",
                entry_id,
                err.__class__.__name__,
            )


async def _set_mode_monitor(store: TesseraStore) -> TesseraConfigData | None:
    """Persist monitor mode if the store can be updated."""
    config = await store.async_load_config()
    if config["mode"] == MODE_MONITOR:
        return config
    config["mode"] = MODE_MONITOR
    await store.async_save_config(config)
    return config


async def _record_repair_issue(
    hass: HomeAssistant, entry_id: str, issue_id: str, *, reason: str
) -> None:
    """Create a redacted Repairs issue; tests may monkeypatch this helper."""
    try:
        from homeassistant.helpers import issue_registry as ir

        ir.async_create_issue(
            hass,
            DOMAIN,
            f"{entry_id}_{issue_id}",
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key=issue_id,
            translation_placeholders={"entry_id": entry_id, "reason": reason},
        )
    except Exception as err:
        LOGGER.debug(
            "Tessera could not create Repairs issue for entry %s (%s)",
            entry_id,
            err.__class__.__name__,
        )


async def _users_by_id(hass: HomeAssistant) -> dict[str, Any]:
    """Return HA users keyed by stable user id."""
    users = await hass.auth.async_get_users()
    users_by_id: dict[str, Any] = {}
    for user in users:
        user_id = getattr(user, "id", None)
        if not isinstance(user_id, str) or not user_id:
            raise ValueError("managed users require a stable id")
        users_by_id[user_id] = user
    return users_by_id


def _domain_data(hass: HomeAssistant) -> dict[str, Any]:
    """Return the mutable Tessera domain data bucket."""
    return cast(dict[str, Any], hass.data.setdefault(DOMAIN, {}))


def _has_loaded_entries(domain_data: dict[str, Any]) -> bool:
    """Return whether the domain bucket still contains entry data.

    Entry-data values are dicts; bookkeeping sentinels are not, so the
    ``isinstance(value, dict)`` test already excludes them. The explicit
    ``key != DATA_SERVICE_REGISTERED`` guard is kept as defensive redundancy.
    """
    return any(
        key != DATA_SERVICE_REGISTERED and isinstance(value, dict)
        for key, value in domain_data.items()
    )
