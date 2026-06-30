"""Tessera — RBAC for Home Assistant.

Store -> Compiler -> native HA ``PolicyPermissions``. The store is the single
source of truth; the compiler projects it into native group policies. See
``docs/spec-phase1-core.md`` for the architecture.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from homeassistant.components.frontend import async_remove_panel
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.panel_custom import async_register_panel

from . import websocket as tessera_websocket
from .auth_adapter import (
    AuthPolicyStoreAdapter,
    HassAuthLike,
    RecoveryController,
    UserBindingAdapter,
)
from .const import DOMAIN, MODE_ENFORCE, MODE_MONITOR, MODE_OFF
from .mode_manager import apply_enforce_plan, compute_enforce_plan
from .monitor import compile_current, lint_current_preview, log_monitor_preview
from .resolver import AreaEntityResolver
from .restore import async_restore_to_pre_install
from .schema import TesseraConfigData
from .state import (
    TesseraStateData,
    decide_startup_recovery,
    snapshot_from_state_data,
)
from .store import TesseraStore

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant, ServiceCall

LOGGER = logging.getLogger(__name__)
SERVICE_RECOMPILE = "recompile"
# Bookkeeping sentinels stored in the domain bucket alongside per-entry dicts.
# Their values are non-dict (bool), so the isinstance(dict) filter in
# _has_loaded_entries cleanly distinguishes them from real entry data.
DATA_SERVICE_REGISTERED = "__recompile_service_registered"
DATA_WEBSOCKET_REGISTERED = "__websocket_registered"
DATA_PANEL_REGISTERED = "__panel_registered"
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
        domain_data.pop(DATA_SERVICE_REGISTERED, None)
    return True


def _register_recompile_service(hass: HomeAssistant) -> None:
    """Register the monitor-mode recompilation service once per HA instance."""
    domain_data = _domain_data(hass)
    if domain_data.get(DATA_SERVICE_REGISTERED) is True:
        return

    async def _handle_recompile(call: ServiceCall) -> None:
        """Recompile all loaded Tessera entries without native writes."""
        del call  # parameterless service; the call carries no Tessera input
        for key, entry_data in list(_domain_data(hass).items()):
            if key == DATA_SERVICE_REGISTERED or not isinstance(entry_data, dict):
                continue
            await _compile_for_mode_safely(hass, key, entry_data)

    hass.services.async_register(DOMAIN, SERVICE_RECOMPILE, _handle_recompile)
    domain_data[DATA_SERVICE_REGISTERED] = True


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
            "Tessera restore failed for entry %s; falling back to monitor mode " "(%s)",
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
