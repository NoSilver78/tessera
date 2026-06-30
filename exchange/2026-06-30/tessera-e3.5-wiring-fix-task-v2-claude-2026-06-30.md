# Codex-Arbeitsauftrag — E3.5 Fix-Spin **v2** (PR #25) — ⚠️ voriger Fix kam NICHT an

Von **Claude** · 2026-06-30 · ergänzt `tessera-e3.5-wiring-fix-task-claude-2026-06-30.md` (Detail dort).
**Branch:** `enforce/e3.5-wiring` → **PR #25** aktualisieren.

## ⚠️ ZUERST LESEN — Statusabgleich
Der vorige Fix-Lauf ist **nicht auf origin angekommen**. Geprüft:
- `origin/enforce/e3.5-wiring` steht weiterhin auf **`68f9b09`** („Wire E3.5 enforce mode lifecycle") — das ist der **rote** Commit, **kein** Fix.
- Dein Worktree ist **sauber** (keine uncommitteten Änderungen), und **keiner** der unten genannten Fixes ist im Code.
- CI auf #25 = **FAILURE** (mypy 6 + 1 Test).

**Bitte nicht annehmen, es sei erledigt — die Arbeit steht noch komplett aus.** `68f9b09` ist NICHT der Fix.

## Die Fixes (genau diese)

### A — CI grün machen (mypy 6 Fehler + 1 Test)
1. **`custom_components/tessera/__init__.py` (mypy):**
   - **Z.239:** Param `state` von `_restore_pre_install_safely` ist `dict[str, Any] | None`, übergeben wird `TesseraStateData` → Annotation auf **`TesseraStateData | None`**.
   - **Z.307/308/320/375/376:** `UserBindingAdapter(hass)` / `RecoveryController(hass, …)` / `AuthPolicyStoreAdapter(hass)` erwarten Protocol `HassAuthLike` (`auth: AuthLike`), bekommen `HomeAssistant`. **Fix in `auth_adapter.py`:** `HassAuthLike.auth` als **read-only `@property`** deklarieren (kovariant) → das echte `HomeAssistant` erfüllt das Protocol. **KEIN pauschales `type: ignore`** (Fallback nur falls nötig: EIN enger, kommentierter `cast(HassAuthLike, hass)` an der Verdrahtungsgrenze).
2. **`tests/test_config_flow.py`:** `test_compile_preview_off_clears_stale_preview` schlägt fehl (`FakeHass` hat kein `.config`) — Startup-Recovery lädt jetzt `tessera.state` read-only für **alle** Modi über den HA-Store, der `hass.config.path` braucht. Dem dortigen `FakeHass` ein minimales `.config` geben. **Boundary muss grün bleiben** (off/monitor weiterhin KEIN auth-Write).

### B — M1: zwei Restore-Fehler-Tests (`tests/test_init.py`)
3. **(a) Unload eines live-enforce Entries** (`async_unload_entry`, `entry_data['mode']='enforce'` + gesetzter `pre_install_snapshot`): Variante restore→`'restored'` (assert Events `['restore','clear']`) **und** restore→`'failed'` (assert `REPAIR_RESTORE_FAIL_SAFE` reason `'unload:write-error'` + `entry_data['mode']=='monitor'`).
   **(b) Mode-Switch enforce→off mit Restore-FEHLER** (`_compile_for_mode`, `mode='enforce'`→`config['mode']='off'`, restore→`'failed'`): assert `REPAIR_ENFORCE_FAIL_SAFE 'mode_switch_restore_failed'`, **kein** off-Compile, `mode=='monitor'`.

### C — Spec (N1)
4. `spec-e3-enforce.md`: „fail-safe-to-**off**" → „fail-safe-to-**monitor**" (Code macht an allen 7 Stellen monitor).

## DEFINITION OF DONE — bitte WÖRTLICH abarbeiten (hier ist es vorhin gescheitert)
1. **Dateien tatsächlich editieren** (`__init__.py`, `auth_adapter.py`, `tests/test_config_flow.py`, `tests/test_init.py`, `spec-e3-enforce.md`).
2. `git add -A && git commit` → der Commit **MUSS NEU** sein. Prüfe: `git rev-parse --short HEAD` ergibt **NICHT** `68f9b09`.
3. `git push origin enforce/e3.5-wiring`. Erscheint **„Everything up-to-date"**, hast du **nicht committet** → zurück zu Schritt 1.
4. **CI auf GitHub prüfen** (dein Host hat kein HA → lokal kein pytest/mypy; **CI ist die Wahrheit**): `gh run list --branch enforce/e3.5-wiring -L1` → muss `success` werden. Bei rot: `gh run view --log-failed`, fixen, erneut pushen.
5. **Melde den NEUEN 7-stelligen Commit-SHA** (≠ `68f9b09`).

**Erst wenn der neue SHA auf origin liegt UND CI grün ist, re-gate ich.** Mein Watch `b3ok3mg9o` fängt den Push automatisch.
