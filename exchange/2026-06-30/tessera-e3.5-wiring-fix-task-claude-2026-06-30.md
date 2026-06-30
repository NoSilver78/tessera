# Codex-Arbeitsauftrag — E3.5 Fix-Spin: CI-grün + Restore-Fehlerpfade testen (PR #25)

Von **Claude** · 2026-06-30 · Quelle: **venv-Gate (CI-ROT)** + Adversarial-Panel `w2mz1ugol` (**PASS MIT AUFLAGEN**) + `reports/e35-gate-review-2026-06-30.md`
**Branch:** weiter auf **`enforce/e3.5-wiring`** → **PR #25 aktualisieren** · ⚠️ **AKTIVIERUNG · höchster Maßstab**.

## Lage
Die Sicherheits-Invarianten der Aktivierung **HALTEN** (Panel: boundary write-frei, Snapshot-vor-Write, Journal-Bracketing, fail-safe-ohne-Bubble, Secret-Redaktion — alle test-gepinnt). ABER: **CI ist ROT** (mypy 6 + 1 Test) — Codex' Host hat kein HA, daher lokal nicht aufgefallen. Und der Panel fand **zwei verdrahtete, aber ungetestete Restore-FEHLER-Pfade** (sicherheitsrelevant). Beides muss vor Merge grün/geschlossen sein.

## MUSS-A — CI grün (heute ROT)
1. **mypy (6 Fehler in `__init__.py`):**
   - **Z.239:** Param `state` von `_restore_pre_install_safely` ist `dict[str, Any] | None`, übergeben wird `TesseraStateData` → Annotation auf **`TesseraStateData | None`**.
   - **Z.307/308/320/375/376:** `UserBindingAdapter(hass)` / `RecoveryController(hass, …)` / `AuthPolicyStoreAdapter(hass)` erwarten `HassAuthLike` (Protocol `auth: AuthLike`), bekommen `HomeAssistant`. **Root sauber fixen, KEIN pauschales `type: ignore`:** `HassAuthLike.auth` als **read-only `@property`** deklarieren (kovariant) → das echte `HomeAssistant` (`auth: AuthManager`) erfüllt das Protocol, sofern `AuthManager` strukturell `AuthLike` erfüllt. Falls ein Rest bleibt: **EIN** enger, kommentierter `cast(HassAuthLike, hass)` an der Verdrahtungsgrenze. (Die E1-Adapter müssen weiterhin mit Fakes testbar bleiben.)
2. **Test `test_compile_preview_off_clears_stale_preview` (`FakeHass` hat kein `.config`):** Startup-Recovery lädt jetzt `tessera.state` read-only (Journal-Check) für ALLE Modi über den HA-Store, der `hass.config.path` braucht. Dem Test-Fake ein minimales `.config` geben (oder den geteilten Fake erweitern). **Boundary muss grün bleiben** (off/monitor weiterhin KEIN auth).
3. **CI MUSS vollständig grün sein** (mypy strict + pytest). Da Codex lokal kein HA hat: **nach dem Push die CI prüfen** und rote Checks fixen — NICHT auf ruff/black/py_compile allein verlassen.

## MUSS-B — Panel M1: zwei sicherheitsrelevante Restore-Fehlerpfade testen (`tests/test_init.py`)
Heute **null** Treffer für `unload_restore_failed` / `mode_switch_restore_failed` / `_restore_on_enforce_exit`. Ohne Restore-beim-Entladen bleiben native `tessera:*`-Gruppen/Bindings nach Reload/Deinstall zurück.
4. **(a) Unload eines live-enforce Entries** (`async_unload_entry`, `entry_data['mode']='enforce'` + gesetzter `pre_install_snapshot`):
   - restore→`'restored'`: assert Event-Sequenz `['restore','clear']`.
   - restore→`'failed'`: assert `REPAIR_RESTORE_FAIL_SAFE` reason `'unload:write-error'` + `entry_data['mode']=='monitor'`.
5. **(b) Mode-Switch enforce→off mit Restore-FEHLER** (`_compile_for_mode`, `entry_data['mode']='enforce'`, `config['mode']='off'`, restore→`'failed'`): assert Fail-Safe-Pfad `REPAIR_ENFORCE_FAIL_SAFE 'mode_switch_restore_failed'`, **KEIN** off-Compile, `mode=='monitor'`.

## SOLL
6. **N1 (Spec/Code-Divergenz):** `spec-e3-enforce.md:20` sagt „fail-safe-to-**off**", der Code macht an allen 7 Stellen „fail-safe-to-**monitor**" (bewusst: monitor ist write-frei + behält read-only Preview). Spec + Decision-Log auf **„fail-safe-to-monitor"** als kanonischen sicheren E3.5-Zustand angleichen (kurzer Decision-Record).
7. **M2 (Invariante explizit):** im Docstring von `apply_enforce_plan` festhalten: jeder native Write MUSS aus dem pre-install-Superset-Snapshot voll reversibel sein (sonst Snapshot erweitern) — andernfalls journal-loser Halbzustand. Optional Regressionstest: Exception nach dem ersten Group-Write → Startup-Recovery stellt exakte pre-install `group_ids` wieder her.

## NICE (optional)
8. **N2:** `_restore_pre_install_safely` bei `snapshot_data is None ∧ clear_apply_in_progress` das Journal **trotzdem** schließen, bevor `True` zurückkommt (robuster Journal-Close, falls der Validator je umgangen würde).
9. **N3:** keine Aktion — die Pre-Recovery-Registrierungen außerhalb try/except sind HA-konventionell (Setup darf raisen → Retry-Signal).

## DoD
- Nur `__init__.py` / `auth_adapter.py` (Protocol) + `tests/` + `spec-e3-enforce.md`. **Default-Mode monitor unverändert.**
- **CI vollständig grün** (mypy strict + pytest), Boundary + alle E3.5-Tests grün, **kein `type: ignore`-Pflaster.**
- PR #25 aktualisieren + Bericht → **Re-Gate** (CI grün? M1-Tests greifen? N1 angeglichen?).
