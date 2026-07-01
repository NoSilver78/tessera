# Codex-Auftrag T-Concurrency: Lost-Update bei parallelen Store-Mutationen schließen

**Von:** Claude (Architektur/Gate) · **An:** Codex · **Datum:** 2026-07-01
**Typ:** Bugfix auf sicherheitskritischem Pfad (Datenverlust in der Policy) · **Risiko:** mittel-hoch — Reentranz-/Deadlock-Falle, höchste Sorgfalt.

## Belegter Befund (real auf ha-tessera-dev gefunden)
Beim Bauen des Haushaltsmodells: **8 gleichzeitige `tessera/matrix/set_grant` (verschiedene Zellen) → nur 1 Grant persistierte.** Ursache: jeder Mutations-Handler macht `load → mutate → save` auf dem **ganzen** Policy-Store ohne Serialisierung. Laufen zwei Handler nebenläufig (HA verarbeitet WS-Kommandos einer Verbindung als **parallele Tasks** über `@async_response` — schnelles Zell-Toggeln im Panel genügt), laden beide dieselbe Basis, addieren je einen Grant, speichern → **last-write-wins = stiller Grant-Verlust.** Gleiches Risiko bei `set_floor_grant`, `set_membership`, D9-Ack, Options-Flow-Schreibungen.

## Branch-Basis
`main` (aktuell). Branch `fix/store-mutation-lock`. PR gegen `main`. Claude gate't hart (volle venv-Suite + `mypy --strict` + **deterministische** Nebenläufigkeits-Tests + Deadlock-Test + Mutationsproben).

## Vorab lesen
`custom_components/tessera/store.py` (`TesseraStore`, hat bereits `self._state_lock` für State — **NICHT** wiederverwenden), `docs/spec-enforce.md`, `docs/QUALITY.md`.

## Die 8 Mutations-Einstiegspunkte (load → mutate → save, alle betroffen)
| Datei | Stelle | Mutation |
|---|---|---|
| `websocket.py` | `async_set_matrix_grant` (Z.174 save) | area_grant + `_compile_for_mode_safely` |
| `__init__.py` | `_handle_set_floor_grant` (Z.334) | floor_grant + compile |
| `__init__.py` | `_register_membership_service` handler (Z.282) | membership |
| `__init__.py` | `_handle_acknowledge` (Z.212) + revoke (Z.233) | d9_acks |
| `config_flow.py` | Options-Flow (Z.423–424) | config+policy (Mode) |
| `auth_adapter.py` | Z.377 | config (Recovery-Binding) |

## Fix-Design (verbindliche Architektur)
1. **Ein `asyncio.Lock` je Store** — `self._mutation_lock = asyncio.Lock()` in `TesseraStore.__init__` (getrennt von `_state_lock`). Deckt config **und** policy ab (Options-Flow mutiert beide → ein Lock verhindert Cross-Interleaving). Tessera ist Single-Config-Entry (`unique_id==DOMAIN`) → ein Lock je Store ist topologisch ausreichend.
2. **Lock NUR am Top-Level jedes Mutations-Einstiegspunkts** halten, um die **gesamte** Sequenz `load → mutate → save → (compile/apply/fail-safe)` atomar zu machen. Empfohlen: ein Context-Manager `async with store.async_mutation():` bzw. Zugriff auf `store.mutation_lock`. Optional Convenience-Helfer `async_mutate_policy(fn)`/`async_mutate_config(fn)` für die reinen load-mutate-save-Fälle (Matrix, Ack).
3. **⚠️ REENTRANZ-INVARIANTE (deadlock-kritisch, `asyncio.Lock` ist NICHT reentrant):** Der Compile-/Enforce-/Fail-Safe-/Restore-Pfad läuft **innerhalb** des gehaltenen Locks — `_compile_for_mode_safely`, `_handle_current_mode`, `_apply_enforce_mode`, `_fail_safe_to_monitor`, **`_set_mode_monitor` (Z.724 — `load_config`+`save_config`!)**, `_restore_pre_install_safely` und **alle** dort geschachtelten Saves MÜSSEN die **rohen** `async_load_*`/`async_save_*` nutzen und dürfen `_mutation_lock` **NIE** (erneut) akquirieren. Das Lock wird ausschließlich an den Top-Level-Eintrittspunkten der Tabelle oben genommen.
4. **Reads lock-frei:** reine Lesepfade (`tessera/matrix/get`-Preview, Monitor-Compile-nur-lesen) akquirieren das Lock NICHT (keine Über-Serialisierung; atomare Datei-Saves liefern konsistente Sicht).
5. **Setup-Pfad:** `async_setup_entry`/Startup-Recovery läuft vor Service-Registrierung ohne Nebenläufigkeit — kein Lock nötig; wenn du es dennoch wrappst, dann ebenfalls nur Top-Level und ohne Reentranz.

## Sicherheits-AUFLAGEN (verbindlich)
- Das Lock **serialisiert nur** — es ändert **keine** Semantik. allow-only, D9-Veto, Lockout-Guard, Fail-safe-to-monitor, Version-Gate, Snapshot/Restore, Audit **unverändert**.
- **Kein Deadlock:** Reentranz-Invariante (oben) einhalten + durch Test belegen.
- Kein Blockieren des Event-Loops (das Lock ist async; keine sync-Waits).
- Kein Verhaltenswechsel für den Single-Mutation-Fall (bestehende Tests bleiben grün).

## Regeln
`ruff`/`black`/`mypy --strict`/`pytest` grün. Keine Secrets. Auth-Tests nur `ha-tessera-dev`. Stop-Regel bei Unklarheit/Deadlock-Zweifel → melden.

## Tests (deterministisch, KEIN sleep-Flackern)
- **Lost-Update-Regression (muss auf altem Code FAILEN):** `async_load_policy` per Monkeypatch an einem `asyncio.Event` barriere-blockieren, sodass N nebenläufige `async_set_matrix_grant` auf **verschiedene** Zellen alle dieselbe Basis laden, dann freigeben → **ohne** Lock nur 1 Grant, **mit** Lock alle N. Assert: alle N Grants im Store. (Barriere/Event-basiert, kein `sleep`.)
- **Deadlock-/Reentranz-Test:** `set_grant` in `enforce`, dessen `_compile_for_mode_safely` in den Fail-Safe (`_set_mode_monitor`) läuft → Handler **terminiert** (Test mit `asyncio.wait_for`-Timeout, der bei Deadlock feuert), Grant persistiert **und** `mode==monitor`.
- Nebenläufige `set_floor_grant` (versch. Floors) → beide persistieren.
- Nebenläufige `set_membership` (versch. User) → beide persistieren.
- Reine Reads (`matrix/get`) blockieren nicht gegen laufende Mutation (kein Lock-Hold auf dem Read-Pfad — durch Test/Assertion belegen).
- QUALITY.md-Invariante ergänzen („alle Store-Mutationen serialisiert unter `_mutation_lock`; Lock top-level-only, nicht reentrant").

## Definition of Done
- [ ] `_mutation_lock` + Top-Level-Wrapping aller 8 Einstiegspunkte; Reentranz-Invariante dokumentiert + eingehalten.
- [ ] Lost-Update geschlossen (Regression bewiesen: failt auf altem Code, grün mit Fix); Deadlock-Test grün.
- [ ] Reads bleiben lock-frei; Single-Mutation-Verhalten unverändert.
- [ ] ruff/black/mypy/pytest grün; QUALITY.md.
- [ ] Branch `fix/store-mutation-lock` + PR gegen `main`.

## Abschlussbericht (PR-Body)
Geänderte Dateien · Lock-Platzierung + Reentranz-Begründung · Tests+Ergebnis (v.a. Lost-Update-Regression + Deadlock) · bestätigt: nur Serialisierung, keine Semantikänderung, reads lock-frei · Risiken/Annahmen.

## Hinweis
Reiner Bugfix, keine neue Fähigkeit. Der belegte Auslöser ist das Matrix-Panel (schnelles Multi-Zell-Toggeln); die anderen Pfade werden vorsorglich mitgeschützt (gleiches Muster). Beweis-Kontext: Haushaltsmodell-Bau auf ha-tessera-dev, 2026-07-01.
