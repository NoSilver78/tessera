# Core-Audit (Multi-Agent) — 2026-06-29
Gegenstand: gemergter Tessera-Core auf `main` (`5434c0c`) — `const/schema/store/resolver/compiler/monitor/config_flow/__init__` + Tests.
Methode: 4 Review-Dimensionen (Security/RBAC · HA-Best-Practice · Test-Abdeckung · Architektur) → **adversariale Verifikation jedes Findings** → Synthese. 38 Agenten.

## Entscheidung: PASS
Kein bestätigtes Finding erreicht nach Verifikation **kritisch** oder **hoch**. Alle vier ursprünglich als „hoch" gemeldeten Punkte wurden belegt abgestuft (Service-/Flag-Leak → niedrig; Single-Instance-Guard → mittel; `entity_overrides`-fail-closed-Coverage → niedrig; vacuous assertions → mittel). Höchster verbleibender Schweregrad: **mittel**.

**Einordnung:** Enforce ist nachweislich **nicht** implementiert (`__init__.py:91-96` loggt nur eine Warnung, keine nativen Writes). Alle Sicherheits-Findings sind heute **ohne realen Blast-Radius** (kein Lockout möglich), betreffen aber Verträge/Pfade, die **vor Enforce** geschlossen sein müssen. Auflagen, nicht gate-blockierend in Phase 1.

## Mittel (vor Enforce schließen)
| # | Bereich | Problem | Fix |
|---|---|---|---|
| M1 | `__init__.py` | `async_setup_entry` ohne fail-safe-to-off — Compile/Resolver-Exception bricht Setup ab statt `mode=off` (Vertrag `spec-phase1-core.md:16,57`). Kein einziges `except` im Component. | `_compile_for_mode` in `try/except`; interner Fehler → redigiert loggen + effektiv `off` (kein Native-Write, nie Deny-all). |
| M2 | `config_flow.py`+`store.py` | Kein Single-Instance-Guard; beide Stores nutzen feste Keys `tessera.config`/`tessera.policy` (nicht pro `entry_id`) → zweite Integration clobbert sie (mode-clobber untergräbt `off`-Panik). | `async_set_unique_id(DOMAIN)`+`_abort_if_unique_id_configured()` **oder** `single_config_entry: true`. |
| M3 | `config_flow.py` | Kein `strings.json`/`translations/`; Step `user` ohne `title`/`description`, kein `already_configured`-Abort-Key. | `strings.json`+`translations/en.json` anlegen; an M2 koppeln. |
| M4 | `test_compiler.py` | `test_output_never_contains_bare_true_shortcuts` (Z.202-204): 2 von 3 Assertions tautologisch (`dict is not True` immer wahr). | `not isinstance(..., bool)` + Grant der einen Shortcut „verlockt" + Nicht-Leerheit asserten. |
| M5 | `test_compiler.py` | Per-Rollen-Isolation eines all-false-Overrides ungetestet — Mutationstest zeigt: Bug, der Entity aus **allen** Rollen popt, bleibt grün, Rolle B verliert still Grant (Lockout-Klasse). | Zwei-Rollen-Test: A+B beide via Area auf `light.x`, Override entfernt nur für A → assert `{a:{}, b:{light.x:{read,control}}}`. |

## Niedrig (Hygiene; teils mit den Mediums billig mitnehmbar)
Service-/Flag-Leak in `async_unload_entry` (No-op, kein Crash) · fehlende `test_init.py`/`test_config_flow.py` · `entity_overrides`-fail-closed-Test fehlt (heute durch KeyError fail-closed) · all-false-AREA-Grant + bad-`mode`-Compile-Test fehlt · `staging` nur als Mapping validiert (Compiler liest es nie) · fehlende `services.yaml` für `recompile` · `resolve_area_entities`/`resolve_all` ungenutzt + irreführender Docstring · Compiler typt `AreaEntityResolver` konkret statt `ResolverLike(Protocol)` · `membership` validiert/persistiert aber unkonsumiert (Phase-1-Grenze, TODO setzen) · `_normalize_leaf` loop-invariant in Area-Innenschleife.

## Remediation (Tracks)
- **M1 + M4 + M5 + billige Test-Lücken** → Task `core/hardening-audit` (`__init__.py` + `tests/`, **kein** Konflikt mit Config-UI).
- **M2 + M3** → **in die laufende `core/config-ui-basics`-PR falten** (editiert ohnehin `config_flow.py`).
- Rest (niedrig, nicht-Test) → späterer Cleanup-Pass, nicht jetzt.
