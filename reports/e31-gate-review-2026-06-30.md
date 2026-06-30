Guard behavior confirmed exactly as reviewers stated: legitimate ids accepted, namespace ids rejected, and the over-rejection of `tesseract`/`tesserae`/`tessera_intern` is real (spec-mandated word-prefix). 

I now have enough to consolidate. The findings I could independently verify by source + pure-Python: dormancy (holds), no-write/no-auth call graph (holds), gate sequence + empty-on-block invariant (holds), schema guard logic + symmetry-in-code + grant-matrix gap (all hold), and crucially the **refuted medium** — the uncaught-raise gap at L73-75 and L84 (holds: confirmed source shows them outside try/except, and store/d9 do raise). What I could NOT re-run: the HA-dependent pytest suite and the named mutation probes (no `homeassistant` on this host).

The decision driver: one **medium** finding (fail-closed contract gap) on a module that is **provably dormant** (no live caller). That is exactly a PASS-MIT-AUFLAGEN profile — not FAIL (no live exposure, no auth-write reachable, security boundary directionally fail-closed), not clean PASS (the docstring contract is refuted and the corrupt-store/d9-IO/resolver paths are untested).

---

## QS-GATE — PR #21 (E3.1 Mode-Manager, dormant/read-only/non-scharf)

# ENTSCHEIDUNG: PASS MIT AUFLAGEN

Begründung: Die Sicherheits-Kerneigenschaften halten verifizierbar (kein nativer Auth-Write, kein `hass.auth`, keine User-Enumeration auf dem Plan-Pfad; Modul nachweislich dormant — kein Live-Caller; Gate-Sequenz lückenlos und empty-on-block-invariant). Es bleibt **ein Medium-Befund**: Der im Docstring zugesicherte „immer fail-closed, gibt stets einen EnforcePlan zurück"-Vertrag ist widerlegt — Store-Loads, Resolver-Konstruktion und der D9-Gate-Aufruf liegen außerhalb jeder `try/except` und können uncaught raisen. Wegen der Dormanz (kein Caller heute) ist das Risiko begrenzt → kein FAIL; wegen der widerlegten Vertragszusage + fehlender Tests → kein sauberes PASS. Auflagen sind vor dem Scharfschalten (E3.2/E3.3) zu erfüllen.

---

## Befunde nach Severity

**MEDIUM**
- **Bereich: mode_manager.compute_enforce_plan — Fail-closed-Vertrag** | **Problem:** Nur Version-Gate (L68-71) und Compile-Schritt (L77-82) fangen Fehler in `_blocked()` ab. Drei Schritte raisen uncaught aus der Funktion und verletzen die Docstring-Zusage „always returns a deterministic EnforcePlan when any gate refuses enforce": (1) `store.async_load_config()/async_load_policy()` (L74-75) rufen `validate_config_data`/`validate_policy_data`, die bei korruptem persistiertem Store `TesseraSchemaError` werfen — und liegen VOR dem Compile-`try` (öffnet erst L77); (2) `AreaEntityResolver.from_hass()` (L73) kann bei nicht verfügbaren HA-Registries raisen; (3) `evaluate_d9_gate` (L84) → `compute_component_hash` → `_iter_hash_files`/`file_path.read_bytes()` (d9_gate.py:170) hat KEIN per-File-Guard → `OSError`/`PermissionError` bzw. TOCTOU (Datei verschwindet mid-scan) propagiert. Quell-verifiziert: L73-75 + L84 stehen außerhalb try; store L60/L79 + d9_gate L170 sind raise-fähig. Richtung ist fail-closed (nie Allow), aber ein Caller, der laut Vertrag nur `block_reason` liest und nichts fängt, würde crashen. **Korrektur:** Store-Loads + Resolver (L73-75) und `evaluate_d9_gate` (L84) in `try/except` kapseln, das Infrastruktur-Fehler auf `_blocked()` mit passendem Reason mappt (z. B. `config`/`d9`), ODER D9-Hashing per-File `OSError` als fail-closed-Signal schlucken. Tests ergänzen: `async_load_config` wirft `TesseraSchemaError` und `evaluate_d9_gate` wirft `OSError` → Erwartung: blockierter EnforcePlan, keine propagierende Exception.

**LOW**
- **Bereich: mode_manager — `except Exception` um compile_current (L81)** | **Problem:** Richtung korrekt fail-closed (CancelledError nicht geschluckt, da BaseException), aber überbreit: Programmierfehler (KeyError/TypeError/AttributeError) und echte Schema-Validierungsfehler aus dem Re-Validate in `compile_current` werden alle als `block_reason='compile'` etikettiert → reduzierte Diagnostizierbarkeit, leicht ungenaues Label. **Korrektur:** Optional auf erwartete Typen einengen (definierter Compile-Error + `TesseraSchemaError`) oder separaten `block_reason` für Validierung, damit unerwartete Bugs nicht als `compile` reklassifiziert werden.
- **Bereich: schema._validate_grant_matrix (L250) — role_id-Pfad nicht lückenlos** | **Problem:** Policy-Grant-Matrix validiert Rollen-Keys nur via `_require_non_empty_string`, NICHT `_require_role_id` — `tessera:foo` passiert die Schema-Schicht. Downstream geschlossen durch `compiler._validate_referenced_roles` (Cross-Check gegen geguardete `config.roles`), also kein realer Leak, aber Schema-Schicht ist nicht selbsttragend. Spec B.1 fordert die Matrix nicht → keine Spec-Verletzung. **Korrektur:** Optional Rollen-Keys in `_validate_grant_matrix` ebenfalls über `_require_role_id` führen → schließt den Pfad unabhängig vom Compiler für künftige Aufrufer.

**NIT**
- **Bereich: Test-Symmetrie by_group** | **Problem:** Code-Symmetrie hält (by_user + by_group teilen `_validate_membership_map`, `_require_role_id` auf beiden Wert-Listen, L145-149/L200 — quell- und laufzeit-bestätigt), aber `test_schema_membership_role_id_namespace_guard` parametrisiert nur `by_user`. Künftige Refaktorierung von by_group würde unbemerkt durchrutschen. **Korrektur:** Test um einen `by_group`-Fall erweitern.
- **Bereich: tessera-Prefix-Breite (schema.py:304)** | **Problem:** Guard verbietet Wort `tessera` am Anfang OHNE Doppelpunkt → über-abweisend für `tesseract`/`tesserae`/`tessera_intern` (dynamisch bestätigt). KEIN Sicherheitsloch (group_id `tessera:tesseract` kollidiert nie mit Managed-Gruppe). Spec B.1 verlangt wörtlich genau diesen Wort-Prefix → spec-konform. **Korrektur:** Akzeptabel as-is; falls seltene Wort-Rollen erlaubt sein sollen, gegen `tessera:` (inkl. Doppelpunkt) prüfen, sonst Intention im Docstring festhalten.
- **Bereich: AuthTrap-Testtiefe** | **Problem:** `_mode_manager_fakes` monkeypatcht `AreaEntityResolver.from_hass` und `evaluate_d9_gate` auf HA-freie Fakes → der AuthTrap-Test deckt die ECHTEN hass-berührenden Callees nicht dynamisch ab (nur per Quell-Inspektion bewiesen). **Korrektur:** Optional ein Test mit AuthTrapHass + REALEM `evaluate_d9_gate`/`resolver.from_hass` (minimales HA-Double mit `config`/`services`/Registries, aber trapping `.auth`).

---

## Positive Beobachtungen
- **Kein nativer Auth-Write auf dem Plan-Pfad, transitiv bestätigt:** Die nativen Auth-Write-Surfaces (`async_set_group_policy`, `async_remove_group`, `async_update_user`/`async_bind_full_superset`, `_async_persist_auth_store`) leben grep-bestätigt ausschließlich in `auth_adapter.py` + `tests/test_auth_adapter.py` + dem unrelated `spike/`-Harness — nie auf dem `compute_enforce_plan`-Pfad. `mode_manager` importiert aus `auth_adapter` nur die 4 reinen Helfer (keine Adapter-Klasse).
- **Kein `hass.auth`/keine User-Enumeration:** Einziger `hass.auth`-Treffer in `mode_manager.py` ist der Docstring-String (L53). Plan-Pfad erreicht nur `config`/`services`/Loader/Registry/Store-Surfaces.
- **Dormanz hält:** `__init__.py`, `websocket.py`, `config_flow.py` importieren weder `mode_manager`/`compute_enforce_plan` noch eine Auth-Adapter-Klasse; einziger Importer ist `tests/test_mode_manager.py`.
- **Gate-Sequenz + empty-on-block:** Alle vier Failure-Branches gehen über `_blocked()` mit hartem `groups:[]`; `groups` wird nur im einzigen Success-Return (nach allen Gates) befüllt — kein Teil-Write, kein Fall-through. `block_detail` ist in jedem Branch durch `sorted()` deterministisch.
- **Gruppen-Projektion:** `tessera:<role_id>` über `sorted(compiled)`, injektiv, im reservierten Namespace; auch leere Policies (deny-by-omission Baseline) werden projiziert.
- **Schema-Guard (dynamisch bestätigt):** legitime ids (`viewer`, `op-1`, `read_only` …) akzeptiert, Namespace-ids (`tessera:foo`, `a:b`, `TesseraAdmin`) abgewiesen; Symmetrie by_user/by_group im Code real geteilt.

---

## Nicht-prüfbares (ehrlich)
- **HA-abhängige Test-Suite + Mutationsproben (Version/D9/Linter-Gate) konnte ich auf diesem Host NICHT re-runnen:** `homeassistant` ist hier nicht installiert (`__init__.py:14` importiert `homeassistant.components.frontend`, Collection bricht ab; keine HA-venv auf dem Mac auffindbar). Die grün gemeldeten Läufe (Version/D9/Linter-Mutation, no-write/no-auth-Grep) übernehme ich als **Attest des Auftraggebers**, nicht als hier reproduzierte Evidenz. Die Grep-Befunde (no-write/no-auth, Dormanz) und die reinen Python-/Quell-Checks (Gate-Sequenz, `_blocked`, Schema-Guard inkl. dynamischer Replikation) habe ich dagegen selbst verifiziert.
- **Reales Laufzeitverhalten der korrupt-Store-/D9-IO-/Resolver-Raise-Pfade:** Per Quell-Inspektion als uncaught-raise belegt (Medium-Befund), aber mangels HA-Env **nicht dynamisch** ausgelöst — die fehlenden Tests sind genau Teil der Auflage.
- **PR-Nummer #21:** In `NoSilver78/HA` existiert keine PR #21; das E3.1-Material liegt im separaten `tessera`-Repo, Branch `enforce/e3.1-mode-manager` (HEAD 8836f4d „Add dormant E3.1 enforce planner", Diff vs `main`: `mode_manager.py` +132, `schema.py` +13/-2, `tests/test_mode_manager.py` +264). Gate wurde gegen diesen Branch gefahren; die „#21"-Zuordnung konnte ich nicht gegen ein PR-Objekt auflösen.

---
**Relevante Pfade (absolut):**
- `/private/tmp/tessera-enforce-e31-mode-manager/custom_components/tessera/mode_manager.py` (Plan-Pfad; L73-75 + L84 ungekapselt)
- `/private/tmp/tessera-enforce-e31-mode-manager/custom_components/tessera/d9_gate.py` (L170 `read_bytes()` ohne per-File-Guard)
- `/private/tmp/tessera-enforce-e31-mode-manager/custom_components/tessera/store.py` (L60/L79 validate→raise)
- `/private/tmp/tessera-enforce-e31-mode-manager/custom_components/tessera/schema.py` (L302-308 Guard; L250 Grant-Matrix-Lücke)
- `/private/tmp/tessera-enforce-e31-mode-manager/tests/test_mode_manager.py` (Test-Lücken: by_group, real-d9/resolver unter AuthTrap)