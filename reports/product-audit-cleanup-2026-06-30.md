# Tessera Produkt-Audit-Cleanup — Umsetzungsbericht (2026-06-30)

Umsetzung des Produkt-Audits (`reports/product-audit-2026-06-30.md`, 51 validierte Findings,
**kein P0**). **Claude-implementiert** (nicht Codex, per Nutzer-Anweisung), direkt auf Branch
`chore/audit-cleanup` → **PR #19**, jeder Batch ruff+black+py_compile lokal + CI-validiert,
behaviorRisk-bewusst (alle Audit-Auflagen beachtet).

## Ergebnis
- **Tests: 89 → 97 passed** (netto +8: 9 neue, 1 toter resolver-Test entfernt) — alle CI-real (kein Hollow-Green).
- **CI durchgehend grün** (ruff `.`, black `.`, mypy strict `custom_components/tessera`, pytest).
- **Kein Verhaltens-/Security-Bruch** — reine Cleanup-/Doku-/Test-Arbeit; die auditierten Invarianten (allow-only, operate/control-Grenze, fail-safe, Determinismus, Dormanz) bleiben unangetastet.

## Umgesetzt (9 Batches)
**P2 — Doku (rein additiv):**
- `services.yaml` (neu) + `services.recompile` Name/Beschreibung.
- Volle OptionsFlow-i18n (`strings.json` + `translations/en.json`): 6 Steps + Felder + `error.*` + `abort.unknown_action` + Action-Selector-Optionen (`translation_key="action"`).
- README: Phase-1-Funktionsumfang + **Sicherheits-Hinweis** (enforce = Monitor-Fallback, KEINE nativen Writes); irreführendes „echt durchgesetzt" in Zeile 3 als Architektur-Ziel präzisiert.
- Docstrings/Verträge: `auth_adapter` (Dormanz + no-drop-Caller-Vertrag korrigiert + level→native-Key), `compiler` (negative-override-beats-area + Re-Validierung als Defense-in-Depth), `resolver`, `__init__` (Sentinels), `websocket` (`MatrixGrant`/Single-Entry), `const`, `tessera-panel.js` (Datei-Header + Tri-State-Zyklus).
- `spec-phase1-core.md` iot_class-Drift angeglichen.

**P3 — Modernisierung & Nits (none-risk):**
- `const`: `frozenset(MODES)`; `resolver`: `-> Self`, tote `resolve_area_entities`/`resolve_all` entfernt (+ Test); `schema`: toter `PermissionKey`-Alias raus, `staging` als inert markiert.
- `linter`: `BY_GROUP_PROJECTION_MODE`-Konstante statt Literal, `LEVELS_{READ,CONTROL}_FIRST`, `_iter_levels` raus, control-first-Reihenfolge kommentiert (lasttragend).
- `__init__`: `ServiceCall`-Typisierung; `manifest`: `single_config_entry`, `iot_class=calculated`.
- `GRANT_SEPARATOR`-Konstante + `encode_grant`/`decode_grant` (single-source über config_flow + websocket).
- Panel-JS: `_grantFor`-Helfer, `_loading`-Init, doppeltes `state`/`label` gemerged.

**P1 — Test-Fidelity (tötet maskierende Mutanten):**
- `test_schema`: per-Fall `match=` auf Unsafe-Leaf-Reject (**M8**).
- `test_compiler`: control-only-Override-impliziert-read (**M2**); echter Sortier-Determinismus mit un-sortierten Inputs statt Tautologie (**M18/M19**).
- `test_init`: stale-Projection-Cleanup (vorbelegt → entfernt, **M15**); Panel-`require_admin=True` + Idempotenz (**M16**).
- `test_config_flow`: 5 OptionsFlow-Maschinerie-Tests (init-Form, unknown→abort, set_mode happy→save+create, invalid→form+error+kein-save, remove_role-ohne-Rollen→no_roles) — zuvor komplett ungetestet.
- `auth_adapter`: Versions-Guard-Dedup (Modul-Helfer `_assert_supported_auth_version`, beide Adapter delegieren).

## Bewusst NICHT umgesetzt (mit Begründung)
**P0 → E3-Zeit (kein heutiger Fix, in `spec-e3-enforce.md` §7/§8 verankert):**
- Restore-on-Unload implementieren + testen (heute dormant; Pflicht vor Scharf).
- `async_set_group_policy` Create-Branch `system_generated`-Re-Check; allow-only-Assertion am Choke-Point; no-drop-Caller-Vertrag erzwingen; Promotion-Guard; `tessera:`-Prefix-Reservierung — alle beim E3-Adapter-Wiring.

**P3/P1-Refactors — geringer Wert / höheres Risiko ohne lokales Test-Netz (Follow-up):**
- **Preview-Refresh 3-fach-Dedup**: off-mode-Gating-Falle (websocket kompiliert bewusst auch bei `off`, init/config_flow nicht) — Dedup würde das still ändern; nur mit sorgfältigem Test sinnvoll.
- **OptionsFlow-`__init__`-Modernisierung**: aktueller Code nicht deprecated (privates `_config_entry`); HA-`config_entry`-Property-Setup würde die neuen Tests verkomplizieren — kein Netto-Gewinn.
- **`_conflicts_for_user`-Helfer-Extraktion**: Read-Suppression braucht `control_restricting_roles`-Kontext → nur Teil-Extraktion möglich; control-first-Kommentar als Readability-Gewinn genügt.
- **recompile-Admin-Guard**: Dienst ist harmlos (kein nativer Write, keine Rückgabe); Guard wäre Verhaltensänderung auf security-nahem Pfad ohne realen Gewinn.
- **Teardown `DATA_WEBSOCKET_REGISTERED`-Pop**: Re-Register-Idempotenz von `async_register_command` unklar; aktuelles Verhalten harmlos.
- **Lokale Test-Kollektierbarkeit (conftest/HA-Stub)**: Dev-Komfort; CI ist autoritativ.

## Bilanz
Audit (Agentensystem, 51 Findings, doppelt verifiziert) + Umsetzung der gesamten P1/P2/P3-non-deferred-Liste,
9 Commits, **kein Verhaltens-/Security-Bruch**, **CI durchgehend grün**, **97 Tests**. Die E3-relevanten
Findings sind sauber als Vor-Scharf-Auflagen verankert, nicht stillschweigend übergangen.
