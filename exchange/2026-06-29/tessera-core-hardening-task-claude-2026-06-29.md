# Codex-Aufgabe — Core-Hardening (Audit-Auflagen, vor Enforce)
Von Claude · 2026-06-29 · Quelle: `reports/core-audit-2026-06-29.md` · **Branch `core/hardening-audit` (von `main` NACH Merge von PR #6 Config-UI) → PR** · nicht enforce-gegated

## Aufgabe
Schließe die Audit-Auflagen, die **nicht** `config_flow.py` betreffen (das macht die `core/config-ui-basics`-PR). Reiner Hardening-/Test-PR, **kein** Verhaltens-/Scope-Wechsel am Compile-Ergebnis.

## Betroffene Dateien
`custom_components/tessera/__init__.py` · `custom_components/tessera/config_flow.py` · `custom_components/tessera/strings.json` (neu) · `custom_components/tessera/translations/en.json` (neu) · `tests/test_compiler.py` · `tests/test_init.py` (neu) · `tests/test_config_flow.py`. Nichts anderes.

## Umsetzung
1. **M1 — fail-safe-to-off** (`__init__.py`): den Aufruf `await _compile_for_mode(...)` in `async_setup_entry` so absichern, dass **jede** interne Exception (z.B. `TesseraSchemaError` aus korrupter `.storage/tessera.config`, Resolver-Registry-Edge) abgefangen, **redigiert** geloggt (keine Secret-/Entity-Flut) und als effektiver **`mode=off`** behandelt wird — **kein** Native-Write, **nie** Deny-all. Setup darf **nicht** hart fehlschlagen (Entry lädt im sicheren off-Zustand). Vertrag: `docs/spec-phase1-core.md:16,57`.
2. **Niedrig (mitnehmen) — Service-Cleanup** (`__init__.py`): in `async_unload_entry` beim Entladen der letzten Entry `hass.services.async_remove(DOMAIN, SERVICE_RECOMPILE)` aufrufen und `DATA_SERVICE_REGISTERED` zurücksetzen.
3. **M4 — vacuous assertions** (`test_compiler.py`): in `test_output_never_contains_bare_true_shortcuts` die tautologischen `is not True`-Checks durch `not isinstance(..., bool)` ersetzen; einen Grant einspeisen, der einen bare-True-Shortcut „verlocken" würde; Nicht-Leerheit der `entity_ids`-Map asserten.
4. **M5 — Per-Rollen-Isolation** (`test_compiler.py`): Zwei-Rollen-Test — A und B beide via Area auf `light.x` gegrantet, Override entfernt `light.x` **nur für A** → assert `{a:{}, b:{light.x:{read,control}}}`.
5. **Billige Test-Lücken** (`test_compiler.py`): (a) Ghost-Rolle **nur in `entity_overrides`** → erwartet `TesseraSchemaError`/Raise. (b) Area-Grant `{read:False,control:False}` → Entity wird **omittiert** (deny-by-omission). (c) `mode='banana'` → `compile_policies` raised.
6. **Lifecycle-Test** (`test_init.py`, neu): `async_setup_entry`+`async_unload_entry`-Lifecycle (korrekter `entry_id`-Pop, DOMAIN-Bucket nicht versehentlich gelöscht, Service-Removal beim letzten Unload) **und** ein fail-safe-Test zu M1 (gemockter `store.async_load_config`/Resolver wirft → Entry lädt im off-Zustand, keine Exception propagiert).
7. **M2 — Single-Instance-Guard** (`config_flow.py`): in `async_step_user` vor `async_create_entry` → `await self.async_set_unique_id(DOMAIN)` + `self._abort_if_unique_id_configured()` (alternativ `single_config_entry: true` in `manifest.json`). Grund: feste Store-Keys `tessera.config`/`tessera.policy` (nicht pro `entry_id`) — zweite Integration clobbert. Test (`test_config_flow.py`): zweiter Setup → Abort `already_configured`; erster → `async_create_entry(title="Tessera")`.
8. **M3 — Translations** (`strings.json` + `translations/en.json`, neu): `config.step.user.title`/`description` + `config.abort.already_configured`.

## Regeln
- **Kein nativer Write / keine `hass.auth`-Mutation.** Compile-Ergebnis-Semantik **unverändert** (nur fail-safe-Hülle + Tests). Best-Practice: Type-Hints, Docstrings, async, kein blocking I/O.

## Definition of Done
Punkte 1–8 · **CI grün** (Tests real ausgeführt, Zähler im Bericht) · **PR** mit Bericht · keine Scope-Ausweitung · **kein nativer Write** (bestätigen).
