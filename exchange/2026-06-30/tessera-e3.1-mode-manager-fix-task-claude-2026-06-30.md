# Codex-Arbeitsauftrag — E3.1 Fix-Spin: Fail-closed-Vertrag vervollständigen (PR #21)

Von **Claude** · 2026-06-30 · Quelle: Adversarial-Gate `wsk00jc3q` (**PASS MIT AUFLAGEN**) + `reports/e31-gate-review-2026-06-30.md`
**Branch:** weiter auf **`enforce/e3.1-mode-manager`** → **PR #21 aktualisieren** · non-scharf/read-only/dormant · security-relevant.

## Verdikt
**PASS MIT AUFLAGEN.** Security-Kern hält verifiziert (kein nativer Write / kein `hass.auth` / dormant / Gate-Sequenz lückenlos / empty-on-block; Mutationsproben Version/D9/Linter grün, CI 139 passed). **EIN Medium** vor Merge zu schließen, weil E3.2/E3.3 auf diesem Vertrag aufbauen.

## MUSS — Fail-closed-Vertrag vervollständigen (MEDIUM)
`compute_enforce_plan` verspricht im Docstring „always returns a deterministic EnforcePlan when any gate refuses enforce" — aber **nur Version (L68-71) + Compile (L77-82)** fangen ab. **Drei Schritte raisen uncaught** und verletzen den Vertrag:
- **Store-Loads (L74-75):** `async_load_config/policy` rufen `validate_config_data/policy_data` → `TesseraSchemaError` bei korruptem persistierten Store — und liegen **vor** dem Compile-`try` (öffnet erst L77).
- **Resolver (L73):** `AreaEntityResolver.from_hass` kann bei nicht verfügbaren Registries raisen.
- **D9 (L84):** `evaluate_d9_gate` → `compute_component_hash` → `_iter_hash_files`/`read_bytes` (d9_gate.py:170) ohne per-File-Guard → `OSError`/`PermissionError`/TOCTOU; `loader.async_get_custom_components` kann ebenfalls raisen.

**Fix:**
1. Store-Loads + Resolver-Konstruktion (L73-75) **und** den `evaluate_d9_gate`-Aufruf (L84) je in `try/except` kapseln → bei Fehler `_blocked(reason, [detail])` zurückgeben, **nie** propagieren. `BlockReason`-Literal erweitern. Vorschlag Reasons: Store-Load/Validate → `"store"`; Resolver → `"resolver"` (oder `"internal"`); D9-Raise → `"d9"`. **`asyncio.CancelledError` NICHT schlucken** (nur `Exception`, nicht `BaseException` — wie beim Compile-Catch).
2. Docstring/Vertrag wahr machen: **jede** Gate-/Infra-Störung → blockierter Plan, deterministisch.

**Tests:**
- `async_load_config` wirft `TesseraSchemaError` → `blocked=True, reason="store"`, **keine** propagierende Exception.
- `evaluate_d9_gate` (gemockt) wirft `OSError` → `blocked=True, reason="d9"`.
- (optional) `resolver.from_hass` wirft → `blocked`.

## SOLL
3. **`except Exception`-Breite (LOW):** der Compile-Catch (L81) etikettiert auch Programmierfehler/Validate-Fehler als `block_reason="compile"`. Mit #1 (separates `"store"`) wird das schärfer; zusätzlich optional auf erwartete Typen einengen (`TesseraSchemaError` + definierter Compile-Fehler) **oder** im Docstring klar festhalten, dass `compile` bewusst fail-closed-breit fängt.
4. **Grant-Matrix-role_id (LOW):** `_validate_grant_matrix` (schema.py:250) validiert Rollen-Keys nur via `_require_non_empty_string` → zusätzlich über `_require_role_id` führen (macht die Schema-Schicht selbsttragend, unabhängig vom Compiler-Cross-Check). + Test (`area_grants` mit Rollen-Key `"tessera:foo"` → `TesseraSchemaError`).

## NICE
5. `by_group`-Fall in `test_schema_membership_role_id_namespace_guard` ergänzen (Symmetrie gegen künftige Refaktorierung pinnen).
6. (optional) Ein Test mit `AuthTrapHass` + **REALEM** `evaluate_d9_gate`/`resolver.from_hass` (minimales HA-Double mit `config`/`services`/Registries, aber trapping `.auth`) → dynamischer no-auth-Beweis der echten Callees.
7. tessera-Prefix-Breite (`tesseract`/`tesserae` werden abgewiesen): **spec-konform** (B.1 = Wort-Prefix), akzeptabel — Intention im Docstring von `_require_role_id` festhalten **oder** auf `"tessera:"` (mit Doppelpunkt) einengen. Eure Wahl, kein Blocker.

## DoD
- Nur `mode_manager.py` / `schema.py` + `tests/test_mode_manager.py`. **Dormant/non-scharf bleiben** (kein Write, kein `hass.auth`, nicht verdrahtet).
- ruff/black/mypy-strict + pytest grün, CI grün. **PR #21 aktualisieren** + Bericht → **Re-Gate** (propagiert wirklich nichts mehr? jeder neue Fail-closed-Test greift? `groups==[]` in jedem Block-Branch?).
