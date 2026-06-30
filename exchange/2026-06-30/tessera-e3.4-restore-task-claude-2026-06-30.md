# Codex-Arbeitsauftrag — E3.4: Restore/Recovery + Two-Phase-Journal (dormant)

Von **Claude** · 2026-06-30 · **E3-Build Schritt 4 von ~5** · Quelle: `docs/concept.md` §6.4/§8.6/§8.8 + `docs/spec-e3-enforce.md` §3 · E3.3-Gate-Auflage (Rollback)
**Branch:** `enforce/e3.4-restore` (von `main`) → PR · **dormant: Restore schreibt nativ WENN aufgerufen, wird aber in KEINEM Modus getriggert (Verdrahtung = E3.5)** · Tests HA-frei (gemockte Adapter); echter E2E erst E3.5 · security-relevant.

## 0. Warum
E3.3 (`apply_enforce_plan`) hat **kein** Rollback — ein Teil-Abbruch hinterlässt einen idempotent re-applybaren Half-State. **Vor** der Verdrahtung (E3.5) braucht es die **Recovery-Gegenrichtung**: (a) einen **immutablen pre_install-Snapshot** (Zustand VOR Tessera je geschrieben hat), (b) ein **Restore** (enforce → monitor/off / Panik), (c) ein **Two-Phase-Journal** für Crash-mid-apply. Die E1-`RecoveryController` (`async_snapshot`/`async_restore`) deckt **Bindings** ab — E3.4 vervollständigt sie + persistiert.

## 1. Aufgabe
1. **pre_install-Snapshot (immutable):** beim allerersten Apply den Vor-Zustand der gemanagten User (`group_ids`) als `pre_install_snapshot` erfassen (E1-`RecoveryController.async_snapshot`) und **persistent + IMMUTABLE** in einem neuen Store `tessera.state` ablegen (neuer `STATE_STORAGE_KEY`, Schema + Validierung; einmal geschrieben, nie überschrieben). Secret-frei (nur user_id + group_ids).
2. **Restore (`async_restore_to_pre_install`):** Gegen-Operation zu apply — (a) jeden gemanagten User per `UserBindingAdapter.async_bind_full_superset` auf seine `pre_install`-`group_ids` zurückbinden (REPLACE; No-Lockout-Guard), (b) **alle `tessera:*`-Gruppen entfernen** (`async_remove_group`) — sie sind Tessera-erzeugt, im pre_install-Zustand existierten sie nicht. Reihenfolge: **erst Rebind, dann Gruppen entfernen** (kein User referenziert sie mehr). Lockout-Precheck wie in apply.
3. **Two-Phase-Journal (`apply_in_progress`):** in `tessera.state` vor einem Apply `apply_in_progress=True` + den Snapshot setzen, nach Erfolg clearen. Eine reine **Recovery-Entscheidungs-Funktion** (dormant, HA-frei): `decide_startup_recovery(state) -> "reapply" | "rollback" | "none"` — bei `apply_in_progress` True beim Start → restriktive Entscheidung (rollback auf pre_install ODER idempotenter Re-Apply; dokumentiere die Wahl). **Die tatsächliche Startup-Verdrahtung ist E3.5** — hier nur die reine Entscheidungs-/Restore-Logik + Journal-Schreiber.

## 2. Hard-Regeln
- **Dormant:** nichts wird verdrahtet (kein Aufruf aus `async_setup_entry`/Mode-Handling). Restore/Snapshot/Journal sind Callables.
- **pre_install_snapshot IMMUTABLE:** einmal geschrieben, nie verändert (Startup-Assertion, dass ein erneutes Setzen abgewiesen wird).
- **Restore lockout-sicher:** Owner/system_generated nie angefasst; Lockout-Precheck; Reihenfolge Rebind→Remove.
- **Keine Secrets** in `tessera.state`/Logs (nur user_id + group_ids — keine Namen/Token/Hashes).
- Python 3.13, ruff/black/mypy-strict + pytest grün, **HA-frei testbar** (Adapter/Store als Spies/Fakes).

## 3. DoD + Tests (HA-frei)
- `tessera.state`-Schema (`pre_install_snapshot`, `apply_in_progress`) + Validierung; `async_restore_to_pre_install` + `decide_startup_recovery` + Journal-Schreiber.
- Tests: (a) pre_install-Snapshot wird einmal gesetzt, **zweites Setzen abgewiesen** (immutable); (b) Restore bindet User auf pre_install zurück + entfernt alle `tessera:*`-Gruppen, Reihenfolge Rebind→Remove (Spy); (c) Restore lockout-sicher (Owner/Admin behält Zugriff; Precheck greift); (d) `decide_startup_recovery`: `apply_in_progress=True` → die gewählte restriktive Entscheidung, `False` → "none"; (e) Restore secrets-frei; (f) Owner/system_generated nicht zurückgebunden.
- CI grün · PR + Bericht → **Adversarial-Panel** (Snapshot wirklich immutable? Restore lockout-sicher + vollständig [Gruppen weg]? Journal-Entscheidung restriktiv/fail-safe? Secrets-frei? dormant?). **Echter Dev-E2E (apply→restore-Zyklus) erst E3.5.**
