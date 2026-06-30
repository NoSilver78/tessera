# Codex-Arbeitsauftrag — E3.5: Enforce-Verdrahtung + Startup-Recovery (LETZTER Build-Schritt)

Von **Claude** · 2026-06-30 · **E3-Build Schritt 5 von 5** · **⚠️ AKTIVIERUNG — verdrahtet den scharfen Pfad in die Mode-Verarbeitung** · Human-Go erteilt (Michael)
**Branch:** `enforce/e3.5-wiring` (von `main`) → PR · **scharf-aktivierend, ABER Default-Mode bleibt `monitor`** (kein Pfad enforced ohne explizites `mode=enforce`) · Tests HA-frei; **echter Dev-E2E gemeinsam NACH dem Gate** · **security-KRITISCH (höchster Maßstab)**.

## 0. Was E3.5 tut
Verdrahtet die dormanten E3.1–E3.4-Teile (`compute_enforce_plan`, `apply_enforce_plan`, Snapshot/Journal, `async_restore_to_pre_install`, `decide_startup_recovery`) in die Mode-Verarbeitung (`__init__.py`). Ab hier setzt `mode==enforce` **real** durch (zuerst nur auf `ha-tessera-dev`). **Default-Mode bleibt `monitor` — Merging enforced NICHTS auf einem Default-Install.**

## 1. Aufgabe
1. **Startup-Recovery** (in `async_setup_entry`, VOR der Mode-Verarbeitung): `tessera.state` laden → `decide_startup_recovery(state)`:
   - `"rollback"` (offenes Journal = abgebrochener Apply) → `async_restore_to_pre_install(snapshot_from_state_data(state["pre_install_snapshot"]), …)` → danach `async_clear_apply_in_progress`.
   - `"none"` → weiter. Fehler hier → **fail-safe-to-monitor** (kein Enforce-Versuch).
2. **Enforce-Pfad** (in `_compile_for_mode`, `mode==enforce` — ersetzt das heutige „monitor only"-Log):
   - `plan = await compute_enforce_plan(hass, store)`.
   - `plan["blocked"]` → **fail-safe-to-monitor** (Repairs-Issue mit `block_reason`, Monitor-Preview, **kein Write**).
   - sonst: **pre_install-Snapshot** (einmalig/immutable: `RecoveryController.async_snapshot` → `async_set_pre_install_snapshot`, nur falls noch keiner) → `async_mark_apply_in_progress(snapshot)` → Adapter konstruieren (`AuthPolicyStoreAdapter(hass)`, `UserBindingAdapter(hass)`) + `users_by_id` aus `hass.auth.async_get_users()` → `result = await apply_enforce_plan(plan, policy_store, binding_adapter, users_by_id)` → bei `result["status"]=="applied"`: `async_clear_apply_in_progress`; sonst **fail-safe-to-monitor** + Repairs-Issue mit `refused_reason` (Journal **bleibt offen** → Startup-Recovery fängt's beim nächsten Start).
3. **Mode-Wechsel `enforce→monitor/off`** (Options-Flow `set_mode` / Reload): war vorher enforce + jetzt nicht → `async_restore_to_pre_install` (Durchsetzung sauber zurücknehmen), State/Journal konsistent.
4. **Fail-safe überall:** jeder Fehler im Enforce-/Recovery-Pfad → `monitor`, redigiertes Log, Repairs-Issue, **nie** Deny-all, **nie** ein stiller Half-State **ohne** offenes Journal.

## 2. Hard-Regeln
- **Default-Mode `monitor`.** Enforce nur bei explizitem `mode=enforce`. Owner/system_generated nie angefasst.
- Schreibt nur über die bestehenden E1-Adapter + E3.3/E3.4-Callables (kein neuer Write-Pfad). **Snapshot VOR Apply, Journal um Apply.**
- **Keine Secrets** in Logs/Repairs (nur IDs/Counts/Reason).
- Python 3.13, ruff/black/mypy-strict + pytest grün. **HA-frei testbar** (compute/apply/restore/snapshot/store/Repairs als Spies/Fakes).

## 3. DoD + Tests (HA-frei) — Dev-E2E separat danach
- Verdrahtung in `__init__.py` (+ ggf. `config_flow` für den Mode-Wechsel).
- Tests: (a) `mode=monitor`/`off` → **kein** Enforce (kein apply/snapshot; die bestehenden „off/monitor berühren kein hass.auth"-Boundary-Tests bleiben grün); (b) `mode=enforce` + blocked-Plan → fail-safe-to-monitor, kein Write, Repairs mit reason; (c) `mode=enforce` + sauberer Plan → Snapshot(einmalig)→mark→apply→clear **in Reihenfolge** (Spies); (d) apply schlägt fehl → monitor + Journal **bleibt offen**; (e) Startup mit offenem Journal → restore→clear; (f) Mode-Wechsel enforce→off → restore; (g) zweiter enforce-Lauf → Snapshot **nicht** überschrieben (immutable); (h) **jeder** Fehler → monitor, **nie** Exception aus `async_setup_entry`.
- CI grün · PR + Bericht → **Adversarial-Panel (höchster Maßstab):** fail-safe lückenlos? Snapshot-vor-Apply + Journal korrekt um Apply? Startup-Recovery? Mode-Wechsel-Restore? **kein Enforce in monitor/off**? Secrets-frei? · **Danach: echter Dev-E2E gegen `ha-tessera-dev` (gemeinsam mit Michael) → Soak → CM5-Live-Go (separat).**
