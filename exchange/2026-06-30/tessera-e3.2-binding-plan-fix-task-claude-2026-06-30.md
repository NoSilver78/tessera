# Codex-Arbeitsauftrag — E3.2 Fix-Spin: `__default__`-Reservierung + auth-fail-closed-Tests (PR #22)

Von **Claude** · 2026-06-30 · Quelle: Adversarial-Gate `wzij2vysm` (**PASS MIT AUFLAGEN**) + `reports/e32-gate-review-2026-06-30.md`
**Branch:** weiter auf **`enforce/e3.2-binding-plan`** → **PR #22 aktualisieren** · read-only/dormant · security-relevant.

## Verdikt
**PASS MIT AUFLAGEN.** Die **drei kritischen Security-Invarianten HALTEN** (Panel adversarial widerlegt + lokale Mutationsproben: keine Privileg-Eskalation, kein No-Drop-Bruch, nie `system-users`; Owner/system_generated nie gebunden; kein nativer Write; CI 154 passed). **ZWEI MEDIUM** vor Merge zu schließen — E3.3 baut auf dem Plan **und** auf dem auth-fail-closed-Vertrag auf.

## MUSS
1. **`__default__`-Kollision schließen (MEDIUM — Plan-Integrität):** `_require_role_id` (schema.py) reserviert `:` + den `tessera`-Prefix, aber **nicht** `__default__`. Ein echter role_id `"__default__"` → `compute_enforce_plan` emittiert `tessera:__default__` aus der Rollen-Schleife (mit der ECHTEN kompilierten Policy) UND — falls ein rollenloser User existiert (`needs_default_role`) — ein **ZWEITES** `tessera:__default__` mit `_empty_policy()` → **doppelte `group_id` mit widersprüchlichen Policies** im Plan. Beim E3.3-Write = last-writer-wins / Überschreiben der echten Policy mit leer.
   **Fix:** in `_require_role_id` zusätzlich den **Dunder-Prefix `__` reservieren** (reject `role_id.startswith("__")`) — deckt `__default__` + künftige interne Sentinels generisch ab. **Test:** role_id `"__default__"` und `"__x"` → `TesseraSchemaError(match="reserved")`; Gegenprobe: ein rollenloser User + (jetzt unmöglicher) `__default__`-Rollen-Versuch wird am Schema abgewiesen → kein doppeltes `group_id` mehr möglich.
2. **auth-Read fail-closed testen (MEDIUM — Vertrag ungetestet):** `_compute_user_bindings_and_orphans` ist in `try/except → _blocked("auth")` (mode_manager.py:118-121) gekapselt, aber **kein Test** prüft den Block-Pfad; und `_user_id` (mode_manager.py:270-274) **raised `ValueError`** bei fehlender/leerer id — nur durch dasselbe try/except geschützt, ungetestet.
   **Tests:** (a) `hass.auth.async_get_users` (oder `hass.auth._store.async_get_groups`) wirft → `blocked=True`, `block_reason=="auth"`, `block_detail` trägt den Exception-Typ; (b) ein gemanagter Fake-User mit leerer/fehlender `id` → `_user_id`-`ValueError` → `_blocked("auth")` (propagiert nicht).

## NICE (NICHT E3.2-blockierend — für E3.3/E4 vormerken)
3. **Sticky-Admin-Audit:** ein User, der einmal `system-admin` hatte, behält es über jeden Recompute (Retention via aktuelle Mitgliedschaft) — auch wenn seine `is_admin`-Rollen entfernt werden. Keine Eskalation (vorher legitim), aber sticky + silent. Optional beim Apply/Audit (E3.3/E4) ein **informatives Signal** emittieren, wenn `system-admin` für einen User **ohne** is_admin-Rolle erhalten bleibt. Nicht in E3.2 umsetzen.

## DoD
- Nur `schema.py` + `mode_manager.py` + `tests/test_mode_manager.py`. **read-only/dormant bleiben** (kein Write, `hass.auth` nur nach allen Gates).
- ruff/black/mypy-strict + pytest grün, CI grün. **PR #22 aktualisieren** + Bericht → **Re-Gate** (greift die `__default__`/Dunder-Reservierung? sind beide auth-fail-closed-Pfade getestet? keine doppelte `group_id` mehr konstruierbar?).
