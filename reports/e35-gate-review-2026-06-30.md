Beide tragenden Befunde sind am Code bestätigt:

1. **Spec-Divergenz bestätigt** — `spec-e3-enforce.md` Z.20 sagt wörtlich „fail-safe-to-off", der Code ruft an allen 7 Stellen `_fail_safe_to_monitor` auf. Nit.
2. **Testlücke bestätigt** — `grep` über `tests/` für `unload_restore_failed`, `mode_switch_restore_failed`, `_restore_on_enforce_exit` liefert NICHTS. Die zwei verdrahteten Restore-Fehler-Pfade (Mode-Switch-Restore-Fehler Z.202, Unload-Restore Z.90/Z.352) sind ungetestet. Medium.

Damit sind alle drei Verdikte-Blöcke konsolidierbar: 2× `pass` (boundary-failsafe, order-journal), 1× `pass-with-conditions` (switch-secrets-complete). Keine FAIL-Befunde, keine high/critical.

---

# QS-GATE — PR #25 · E3.5 Verdrahtung (ENFORCE-AKTIVIERUNG)

## Entscheidung: **PASS MIT AUFLAGEN**

Der scharfe Pfad darf aktiviert werden. Die Sicherheits-Invarianten des Enforce-Mechanismus — Write-Freiheit in monitor/off, Snapshot-vor-Write, Journal-Bracketing, fail-safe-ohne-Bubble, Secret-Redaktion — **halten alle statisch und test-gepinnt**. Die Auflagen betreffen **zwei verdrahtete, aber ungetestete Restore-Fehlerpfade** und eine **Spec/Code-Divergenz** — keiner davon bricht das Sicherheitsmodell, aber beide müssen vor dem Schließen des Build-Schritts adressiert werden, weil dies der höchste Maßstab ist und sicherheitsrelevante Verdrahtung (Restore beim Entladen/Moduswechsel) sonst ungeschützt gegen Regression bleibt.

Default-Mode bleibt `monitor` — die Aktivierung schaltet nur die Fähigkeit frei, nicht den scharfen Betrieb selbst.

---

## Befunde nach Severity

### MEDIUM

**M1 · Tests | Zwei verdrahtete Restore-Fehlerpfade sind ungetestet** (`switch-secrets-complete`, weak)
Verifiziert: `grep` über `tests/` für `unload_restore_failed`, `mode_switch_restore_failed`, `_restore_on_enforce_exit` liefert **null Treffer**. Damit ungeschützt:
- **(a) Restore-beim-Entladen** eines live-enforce Entries (`__init__.py:90` → `_restore_on_enforce_exit_safely` → `unload_restore_failed` Z.352). Der einzige Unload-Test nutzt `OffStore` (mode≠enforce), betritt den Branch also nie. Sicherheitsrelevant: ohne diesen Restore bleiben native `tessera:*`-Gruppen/Bindings nach Reload/Deinstall zurück.
- **(b) Mode-Switch enforce→off/monitor mit Restore-**Fehler** (`__init__.py:202`, `mode_switch_restore_failed`) — nur der Erfolgsfall ist getestet.
**Korrektur:** Zwei Tests in `tests/test_init.py` ergänzen: (a) `async_unload_entry` mit `entry_data['mode']='enforce'` + gesetztem `pre_install_snapshot`, je eine Variante `restored` (assert events `['restore','clear']`) und `failed` (assert `REPAIR_RESTORE_FAIL_SAFE 'unload:write-error'` + `entry_data['mode']=='monitor'`). (b) `_compile_for_mode` mit `entry_data['mode']='enforce'`, `config['mode']='off'`, Restore→`failed`: assert Fail-Safe-Pfad (`REPAIR_ENFORCE_FAIL_SAFE 'mode_switch_restore_failed'`, kein off-Compile, `mode=='monitor'`).

**M2 · Crash-Window-Reversibilität | Residual-Annahme (kein Defekt heute)** (`order-journal`, Claim 5, holds/medium)
Die Journal-loses-Halbzustand-Freiheit hält **nur**, weil jeder native Write in `apply_enforce_plan` aus dem pre-install Superset-Snapshot reversibel ist. Heute (E3.5) gilt das ausnahmslos — kein Defekt. Aber die Invariante ist implizit.
**Korrektur:** Invariante explizit halten — jeder künftige native-Write-Schritt in `apply_enforce_plan` muss aus dem Snapshot voll reversibel sein (oder Snapshot erweitern). Optional Regressionstest: Exception nach dem ersten Group-Write injizieren, Startup-Recovery muss exakte pre-install group_ids wiederherstellen.

### NITS

**N1 · Doku | Spec/Code-Divergenz fail-safe-to-off ↔ fail-safe-to-monitor** (`boundary-failsafe`)
Verifiziert: `spec-e3-enforce.md:20` sagt wörtlich „fail-safe-to-off (kein Teil-Write bleibt unkontrolliert)", der Code ruft an **allen 7 Stellen** `_fail_safe_to_monitor` (`__init__.py:160,198,244,253,297,328,351`). Bewusste, sichere Evolution — monitor ist write-frei (verifiziert) und behält eine read-only Preview statt Teardown. Kein Sicherheitsdefekt; No-Write- und No-Bubble-Garantie halten für das monitor-Ziel.
**Korrektur:** `spec-e3-enforce.md` (+ Decision-Log) auf „fail-safe-to-monitor" als kanonischen sicheren Zustand für E3.5 angleichen, oder Decision-Record für den off→monitor-Wechsel ergänzen, damit Vertrag und Code übereinstimmen.

**N2 · Robustheit | None-Snapshot-Early-Return verlässt sich allein auf Cross-Field-Validator** (`order-journal`, Claim 6)
`_restore_pre_install_safely` gibt bei `snapshot_data is None` True zurück **ohne** das Journal zu schließen (Z.370-371). Aktuell unerreichbar, weil `validate_state_data` (`state.py:50-51`) `apply_in_progress=True ∧ snapshot=None` verbietet. Schutz hängt am Invarianten-Validator, nicht an einem lokalen Guard.
**Korrektur (optional):** Bei `snapshot_data is None ∧ clear_apply_in_progress=True` das Journal trotzdem schließen, bevor True zurückkommt — macht den Journal-Close robust auch falls der Validator je umgangen würde.

**N3 · Vollständigkeit Fail-Safety | async_setup_entry Vorab-Schritte nicht gekapselt** (`boundary-failsafe`, Claim 2)
Die vier Pre-Recovery-Schritte (`domain_data`-Init, `_register_recompile_service`, `_register_websocket_api`, `_async_register_matrix_panel`, Z.60-63) liegen außerhalb jedes try/except — eine Exception dort bubbled raus und lässt Setup hart fehlschlagen. **HA-konventionell** (Setup darf raisen → Retry-Signal) und **nicht** der Enforce/Recovery-Pfad. Kein Defekt gegen den Claim.
**Korrektur (optional):** Falls totale Fail-Safety von `async_setup_entry` gewünscht, Panel/Websocket/Service-Registrierung mit-kapseln.

---

## Positive Beobachtungen

- **Write-Freiheit der unsicheren Pfade hart bewiesen.** `grep` über `resolver.py`/`linter.py`/`compiler.py`/`monitor.py` zeigt **null** `hass.auth`-Referenzen; off ist reine Dict-Ops, monitor nutzt nur Store + Registry-Reads. Der `FakeHass.auth`-Trap (AssertionError) in blocked- und Setup-Exception-Tests beweist real, dass unsichere Enforce-Pfade `hass.auth` nie anfassen.
- **Defense-in-depth bei blocked-Plan.** Doppelte Absicherung: Orchestrator returnt vor jedem Auth/Snapshot/Journal-Write (`__init__.py:296-304`), UND `apply_enforce_plan` short-circuitet selbst auf `plan['blocked']` (`mode_manager.py:214`). Test pinnt `events==['compute','monitor_preview']` und unveränderten Store.
- **Snapshot-Immutabilität dreifach abgesichert.** Orchestrator-None-Check + `async_set_pre_install_snapshot` raise + `async_mark_apply_in_progress` setzt nur bei None + `_state_lock`. Test pinnt byte-identischen Snapshot über zwei Enforce-Läufe, `async_snapshot` wird nie ein zweites Mal gerufen.
- **Journal bracketet die einzige Write-Oberfläche strikt.** mark vor apply, clear ausschließlich unter `status=='applied'`; jeder Nicht-applied-Ausgang lässt Journal offen → Startup-Rollback. Auch Pre-Write-Validation-Failures liegen nach dem mark — kein „blocked/failed vor mark"-Fenster.
- **`_fail_safe_to_monitor` ist selbst non-raising.** Alle Sub-Schritte (`_record_repair_issue`, `_set_mode_monitor`, Preview-Refresh) einzeln gewrappt — selbst die except-Handler können nicht bubblen. Test pinnt Setup-return-True bei Enforce-Exception.
- **Secret-Redaktion sauber verdrahtet.** Repair-reasons speisen sich nur aus Literalen + Aufrufer-Token + `err.__class__.__name__`; `block_detail` (mit Exception-Message) fließt nirgends nach Repairs; `_redacted_error_detail()` gibt nur Typnamen. RaisingStore-Test prüft explizit `'light.private' not in caplog.text`. Translations referenzieren nur `{entry_id}` (HA-UUID) + redigiertes `{reason}`.
- **Restore-vor-Moduswechsel korrekt gegated.** `previous_mode==ENFORCE` wird nur nach erfolgreichem Snapshot+Journal+Apply (`__init__.py:325`) gesetzt — ein bloß in config gespeicherter enforce-Wert kann keinen fälschlichen Restore-Skip verursachen.

---

## Nicht prüfbares / Verifikations-Grenzen

- **Test-Ausführung nur statisch in dieser Umgebung.** Kein `homeassistant`-Modul installiert; die +504 Test-Zeilen in `test_init.py` (Event-Sequenzen, FakeHass-Auth-Trap, Rollback) wurden **per Control-Flow + Grep** verifiziert, nicht ausgeführt. Laut Aufgabenkontext laufen venv-Mutationsproben + Boundary-Tests **separat** — deren grünes Ergebnis ist Voraussetzung dieses Gate-Votums und liegt mir hier nicht vor.
- **Laufzeit-Verhalten des nativen `hass.auth`-Apply** (echte Gruppen-/Binding-Writes gegen eine reale HA-Instanz) ist nicht gegengeprüft — nur die Adapter-Aufrufstruktur und ihr einziger Call-Site (`__init__.py:319`).
- **M1-Korrektur ist verifizierbar erst nach Ausführung** der zwei neuen Tests in der CI-venv.

---

**Auflagen zum Schließen (Reihenfolge):** M1 (zwei Restore-Fehlertests) → N1 (Spec angleichen). M2/N2/N3 sind dokumentierte Härtungen ohne aktiven Defekt — als Decision-Notes/Backlog akzeptabel, nicht blockierend.

Arbeitskopie verifiziert: `/private/tmp/tessera-enforce-e35-wiring/` (HEAD `68f9b09` „Wire E3.5 enforce mode lifecycle"). Tragende Stellen: `custom_components/tessera/__init__.py:90,202,325,352,405`, `mode_manager.py:214`, `state.py:50-51`, `docs/spec-e3-enforce.md:20`.