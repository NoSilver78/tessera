# Codex-Auftrag T1: by_user-Membership-Writer (Soak-Unblocker)

**Von:** Claude (Architektur/Gate) · **An:** Codex · **Datum:** 2026-07-01
**Typ:** Feature auf sicherheitskritischem Pfad (Membership → Enforce-Plan) · **Risiko:** mittel — höchste Sorgfalt

## Branch-Basis
Basiere auf `main` (aktueller Stand). Branch `feature/membership-by-user`. PR gegen `main`. Claude gate't hart (volle venv-Suite + `mypy --strict` + Mutationsproben; ggf. unabhängige R7-Review).

## Vorab lesen (Kontext, alles auf `main`)
`exchange/2026-07-01/00_tessera-gesamtpaket-codex-2026-07-01.md` (Gesamtstand + Backlog), `exchange/2026-07-01/tessera-bedienmodell-2026-07-01.md` §9 (deine eigenen AUFLAGEN), `exchange/2026-07-01/tessera-bedienmodell-crossvalidation-codex-2026-07-01.md` (dein Report). Scope-Klärung: Pilzbuche 8 = **Haushalt**, eine Instanz, Tessera = Ein-Haushalt-RBAC.

## Kontext — die Lücke
Tessera hat KEINEN Schreibpfad, um HA-User an Rollen zuzuweisen. `membership.by_user` (`schema.py`) wird nur GELESEN (`mode_manager.compute_enforce_plan` baut daraus die Bindings; `linter.py`) und beim Rollen-Löschen aufgeräumt (`config_flow.remove_role`). Ohne Schreibpfad bindet enforce niemanden → das ist der **Soak-Unblocker**.
**Vorbilder im Code (spiegeln):** D9-Ack-Services (#11, `__init__.py._register_ack_services` via `async_register_admin_service`) für die admin-gated Service-Registrierung + Unload-Deregistrierung; `websocket.async_set_matrix_grant` (CXR-02) für „Config/Policy ändern → in enforce via `_compile_for_mode_safely` re-applien"; `config_flow.add_role` für den reinen Config-Mutator.

## Aufgabe
1. **Reiner Config-Mutator** in `config_flow.py` (neben `add_role`/`remove_role`): `set_user_membership(config, user_id, role_ids) -> TesseraConfigData`. Setzt `config["membership"]["by_user"][user_id] = sorted(set(role_ids))`; **leere Liste ⇒ `by_user.pop(user_id, None)`** (idempotentes Entfernen). **Fail-closed:** jede `role_id` muss in `config["roles"]` existieren, sonst `TesseraSchemaError`. Schema-validieren (wie die anderen Mutatoren).
2. **Admin-Service** `tessera.set_membership` in `__init__.py` (via `async_register_admin_service`, exakt wie die D9-Ack-Services): Schema `{vol.Required("user_id"): cv.string, vol.Required("role_ids"): vol.All(cv.ensure_list, [cv.string])}`. Handler: geladene Entry(s) auflösen (wie `_handle_recompile`), `config` via Store laden, `set_user_membership` anwenden, `store.async_save_config(config)`, **und in `enforce` zwingend** `await _compile_for_mode_safely(hass, key, entry_data)` — **kein direkter Native-Auth-Write**. **Redacted** Audit-Log (`user_id` + `role_ids`, KEINE Tokens/Claims/Secrets). Im Unload deregistrieren (wie die Ack-Services).
3. `services.yaml` + `strings.json` + `translations/en.json` Einträge.

## Sicherheits-AUFLAGEN (deine eigenen, verbindlich)
- Admin-only (`async_register_admin_service`), **kein** direkter Native-Auth-Write.
- Schema-validierter Store-Write; unbekannte User/Rolle **fail-closed**.
- In `enforce` **zwingend** derselbe zentrale `_compile_for_mode_safely`/Apply-Guard-Pfad wie Matrix-Updates (der Guarded Plan fängt Lockout/Allow-only/D9/Linter/Version ab).
- **Redacted** Audit (User-/Rollen-IDs ja; keine Tokens/Claims/Secrets).
- Bestehende Allow-only-/Version-/D9-/Linter-/Lockout-Gates dürfen NICHT umgangen werden.

## Regeln
`ruff`/`black`/`mypy --strict`/`pytest` grün. **Keine Secrets.** Auth-Tests nur `ha-tessera-dev`, **nie** Live-CM5. Bei Unklarheit/Risiko → **STOPP + melden**, nicht raten.

## Tests (realistische Fixtures, QUALITY.md R2; mutationsfest, kein Vakuum)
- unbekannter `user_id` / unbekannte `role_id` ⇒ fail-closed (kein Save, kein Native-Write).
- **last-admin/owner-risk:** eine Membership-Änderung, die in enforce zur Aussperrung führen würde, wird vom recompile-Plan (Lockout-Guard) geblockt → fail-safe, **kein** Halb-Zustand.
- owner / `system_generated` als Target ⇒ Rejection (nie binden/schreiben).
- **kein** Native-Write, wenn der Plan blockt.
- recompile-failure ⇒ fail-safe-to-monitor.
- set → (get/Store-)Roundtrip; idempotentes Entfernen (leere Liste).
- **QUALITY.md** Invarianten-Tabelle ergänzen: „Membership-Write admin-only + fail-closed".

## Definition of Done
- [ ] `set_user_membership`-Mutator + `tessera.set_membership`-Admin-Service + Unload-Deregistrierung.
- [ ] enforce ⇒ Auto-Recompile via `_compile_for_mode_safely`; **kein** direkter Native-Write.
- [ ] services.yaml/strings.json/translations/en.json; QUALITY.md-Tabelle.
- [ ] ruff/black/mypy/pytest grün; Tests wie oben; fail-closed bewiesen.
- [ ] Branch `feature/membership-by-user` gepusht + `gh pr create` gegen `main`.

## Abschlussbericht (PR-Body)
Geänderte Dateien · Zusammenfassung · Tests+Ergebnis (v. a. fail-closed + last-admin/owner-risk) · bestätigt: admin-only, kein Native-Write, enforce→recompile · Risiken/Annahmen · alles, was abwich.

## Hinweis (Reconciliation)
Deine Validierung nannte einen WS-Service `tessera/membership/set`. Für den ERSTEN sofort nutzbaren Increment implementieren wir es als **Admin-Service** `tessera.set_membership` (wie die #11-D9-Ack-Services — direkt in Developer Tools → Aktionen aufrufbar, damit der Soak sofort Personen zuweisen kann). **Alle Sicherheits-AUFLAGEN gelten unverändert.** Die Panel-„Mitglieder"-Sektion mit Person-Picker (liest/schreibt denselben Store) ist der unmittelbare Folge-Task (T1b).
