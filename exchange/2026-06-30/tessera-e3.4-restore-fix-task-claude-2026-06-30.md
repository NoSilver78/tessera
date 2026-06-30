# Codex-Arbeitsauftrag — E3.4 Fix-Spin: Recovery-Coverage + Robustheit (PR #24)

Von **Claude** · 2026-06-30 · Quelle: Adversarial-Gate `wu40rhhr1` (**PASS MIT AUFLAGEN**) + `reports/e34-gate-review-2026-06-30.md`
**Branch:** weiter auf **`enforce/e3.4-restore`** → **PR #24 aktualisieren** · dormant · security-relevant.

## Verdikt
**PASS MIT AUFLAGEN.** Die **Kern-Sicherheit HÄLT** (adversarial widerlegt + Mutationsproben: Restore lockout-frei — `system-admin` wird nie entfernt, nur `tessera:*`; Survivor-Precheck blockt Sole-Admin-Demotion; Reihenfolge Rebind→Remove ohne Dangling-Reference; Snapshot immutable; secrets-frei; CI 177). Die Auflagen sind **Coverage + Robustheit** — vor dem **Live-Verdrahten (E3.5)** zu schließen, weil E3.5 genau diese Recovery konsumiert.

## MUSS
1. **Journal→Restore-Bridge testen (MEDIUM — `snapshot_from_state_data` ist toter Code):** die `rollback`-Entscheidung wird nirgends konsumiert; Persist (store) + Restore (restore.py) sind getestete Inseln, die Brücke nicht. **Round-Trip-Test:** `async_mark_apply_in_progress(snapshot)` → State neu laden → `decide_startup_recovery(state) == "rollback"` → `snapshot_from_state_data(state["pre_install_snapshot"])` → `async_restore_to_pre_install(...)` → assert User auf pre_install zurückgebunden + `tessera:*`-Gruppen entfernt. Das exerziert das tote `snapshot_from_state_data` **und** beweist, dass die rollback-Entscheidung actionable ist.
2. **Partial-Failure mid-loop testen (MEDIUM):** (a) `async_restore_exact_groups` wirft beim **zweiten** User → frühere User rebound, `restored_user_ids` korrekt, `status="failed"`/`refused_reason="write-error"`, **kein Lockout**; (b) `async_remove_group` wirft beim **zweiten** `tessera:*`-Gruppen-Remove → erste entfernt, `group_ids_removed` korrekt, restliche Gruppen bleiben (consistent-by-omission). (Heute failt T4 nur beim allerersten User = 0 prior writes.)
3. **`is_active`-Truthiness (LOW — Robustheit):** `getattr(user, "is_active", True) is False` schließt nur das Literal `False` aus; ein falsey-aber-nicht-`False` (0/None/'') würde als aktiv gewertet (auf echten HA-Usern ein bool, also heute nicht ausnutzbar). **Fix:** `if not getattr(user, "is_active", True):` in `restore.py:110` **und** `auth_adapter.py` (`_is_active_owner_or_admin`, ~Z.523) — konsistent.

## SOLL (vor E3.5)
4. **Immutability/Journal-TOCTOU (LOW, dormant):** der set-once-Guard ist load→check→save ohne Lock → zwei gleichzeitige First-Writer könnten beide passieren (heute unerreichbar: dormant + Single-Writer pro Apply-Zyklus). **Fix:** einen `asyncio.Lock` um die read-modify-write der drei State-Mutatoren (`async_set_pre_install_snapshot`/`mark`/`clear`) legen + ein Regressionstest (zwei gleichzeitige `async_set_pre_install_snapshot` → genau einer erfolgreich). Falls aufwändig: die Single-Writer-Annahme in `spec-e3-enforce.md` festhalten, damit der E3.5-Caller sie einhält.
5. **Non-Atomicity dokumentieren:** Docstring von `async_restore_to_pre_install`: Restore ist nicht atomar (frühe User können rebound sein, während ein späterer Fehler den Rest abbricht); die Reihenfolge garantiert **keine Dangling-Reference**, das Result meldet den Teilfortschritt ehrlich.

## DoD
- Nur `restore.py`/`state.py`/`store.py`/`auth_adapter.py` + `tests/`. **Dormant bleiben.** ruff/black/mypy-strict + pytest grün, CI grün.
- **PR #24 aktualisieren** + Bericht → **Re-Gate** (Bridge round-trip greift? Partial-Failure-Tests + is_active-Truthiness? Lock/Single-Writer geklärt?).
