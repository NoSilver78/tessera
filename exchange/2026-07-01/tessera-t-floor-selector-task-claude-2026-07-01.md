# Codex-Auftrag T-Floor: Floor-Grant-Selektor (Etagen-Grant)

**Von:** Claude (Architektur/Gate) · **An:** Codex · **Datum:** 2026-07-01
**Typ:** Feature auf sicherheitskritischem Pfad (neue Grant-Dimension → Compiler → Enforce-Plan) · **Risiko:** mittel-hoch — höchste Sorgfalt · **Motivation:** `exchange/2026-07-01/tessera-haushaltsmodell-pilzbuche8-2026-07-01.md` (etagen-basiertes Modell → ~41 Area-Grants auf ~14 reduzieren)

## Branch-Basis
`main` (aktuell, T1 gemergt). Branch `feature/floor-grant-selector`. PR gegen `main`. Claude gate't hart (volle venv-Suite + `mypy --strict` + Mutationsproben + adversariale R7-Review, weil neue Grant-Dimension = enforce-kritisch).

## Vorab lesen
`docs/spec-enforce.md` (floor/label/category-Ausbau, v1=area+entity+domain), `docs/QUALITY.md`, das Haushaltsmodell (o. g.). **Vorbilder im Code exakt spiegeln:** `config_flow.add_area_grant`/`remove_area_grant` (Grant-Mutator), `compiler.compile_policies` (Z.68 area_grants-Loop → `resolver.entity_ids_for_area` → Union), `resolver.AreaEntityResolver` (`entity_ids_for_area`, `from_hass`), `__init__._register_membership_service` (#T1 — admin-Service-Muster mit All-Entry-Preflight + `_compile_for_mode_safely` + redacted Audit + Unload).

## Kontext / Design
Grants sind heute `policy["area_grants"]: {area_id: {role_id: PermissionLeaf}}`, im Compiler via `resolver.entity_ids_for_area` zu Entity-Permissions expandiert und **allow-only unioniert** mit `entity_overrides`. HA-**Areas tragen `floor_id`** (Area-Registry). Ein Floor-Grant expandiert zu allen Areas der Etage → deren Entities → in dieselbe Union.

## Aufgabe
1. **Schema (`schema.py`):** neue Policy-Dimension `floor_grants: dict[floor_id, dict[role_id, PermissionLeaf]]` **parallel** zu `area_grants` (in `TesseraPolicyData`, `default_policy_data` `"floor_grants": {}`, Validierung via `_validate_grant_matrix` wie area_grants).
2. **Resolver (`resolver.py`):** `entity_ids_for_floor(floor_id) -> tuple[str,...]` — via **Area-Registry** alle Areas mit `area.floor_id == floor_id` sammeln, dann deren `entity_ids_for_area` **vereinigen** (sortiert, dedupliziert). `from_hass` + `__init__` um die Area-Registry ergänzen (analog entity/device-Registry). Kleine Registry-Protokolle wie bei den bestehenden.
3. **Compiler (`compiler.py`):** in `compile_policies` einen `floor_grants`-Loop **vor/neben** dem area_grants-Loop: je `(floor_id, role_map)` → `resolver.entity_ids_for_floor(floor_id)` → dieselbe Per-Entity-Permission-Union wie area_grants (allow-only, `control` impliziert `read`, Max über alle Quellen floor ∪ area ∪ entity_override). **Keine** neue Präzedenz — reine additive Union. `policy.floor_grants` in die Evidenz-/Validierungs-Liste (Z.129 f.) aufnehmen.
4. **Mutator (`config_flow.py`):** `set_floor_grant(config, policy, floor_id, role_id, *, read, control)` **exakt** analog `add_area_grant` (gleiche Signatur-Form/Return, gleiche Validierung: `role_id` muss in `config["roles"]` existieren → sonst `TesseraSchemaError`; `control` impliziert `read`; leeres Leaf/entfernen analog `remove_area_grant`). Plus `remove_floor_grant` analog.
5. **Admin-Service `tessera.set_floor_grant`** (`__init__.py`, via `async_register_admin_service`, **spiegle `_register_membership_service` (#T1)**): Schema `{floor_id: cv.string, role_id: cv.string, read: cv.boolean, control: cv.boolean}`. Handler: `_assert_floor_exists(hass, floor_id)` (**fail-closed** gegen die HA-Floor-Registry, analog `_assert_membership_target_user`), dann **All-Entry-Preflight** (alle Entries `set_floor_grant` vorbereiten VOR dem ersten Save), dann je Entry `async_save_policy` + `_compile_for_mode_safely` (**kein** direkter Native-Write), redacted Audit (`floor_id`/`role_id`/read/control), Unload-Deregistrierung.
6. `services.yaml`/`strings.json`/`translations/en.json` + **QUALITY.md**-Invariante („Floor-Grant additiv unioniert, admin-only, fail-closed").

## Sicherheits-AUFLAGEN (verbindlich)
- Admin-only; **kein** direkter Native-Auth-Write (nur Store + `_compile_for_mode_safely`).
- Schema-validiert; unbekannte Floor/Rolle **fail-closed**; All-Entry-Preflight (keine Teil-Schreibung).
- in enforce zwingend über den zentralen Guarded-Recompile-Pfad; redacted Audit.
- **Rein additive Union** — allow-only-Invariante + bestehende Lockout-/D9-/Linter-/Version-Gates dürfen NICHT umgangen oder aufgeweicht werden. Kein Deny/Override.

## Regeln
`ruff`/`black`/`mypy --strict`/`pytest` grün. Keine Secrets. Auth-Tests nur `ha-tessera-dev`. Stop-Regel bei Unklarheit/Risiko → melden.

## Tests (mutationsfest, realistische Fixtures R2)
- `set_floor_grant`/`remove_floor_grant`-Mutator: unbekannte Rolle → fail-closed; control impliziert read; entfernen idempotent.
- Resolver `entity_ids_for_floor`: Floor mit mehreren Areas → Union der Entities; Floor ohne Areas → leer; unbekannter Floor → leer.
- Compiler: Floor-Grant expandiert korrekt zu allen Floor-Entities; **Union** mit einem überlappenden area_grant (Max read/control); allow-only bleibt.
- Service: admin-only; **unbekannter Floor → fail-closed ohne Save/Compile**; All-Entry-Preflight (invalider Grant → kein Teil-Save); enforce → recompile (kein Native-Write); recompile-failure → fail-safe-to-monitor.
- QUALITY.md-Invarianten-Tabelle ergänzt.

## Definition of Done
- [ ] `floor_grants`-Schema + `entity_ids_for_floor`-Resolver + Compiler-Union + `set_floor_grant`/`remove_floor_grant`-Mutator + `tessera.set_floor_grant`-Admin-Service + Unload.
- [ ] additive Union verifiziert (floor ∪ area ∪ entity, allow-only); kein Native-Write-Bypass.
- [ ] services.yaml/strings/translations + QUALITY.md.
- [ ] ruff/black/mypy/pytest grün; Tests wie oben; fail-closed + Union bewiesen.
- [ ] Branch `feature/floor-grant-selector` + PR gegen `main`.

## Abschlussbericht (PR-Body)
Geänderte Dateien · Zusammenfassung · Tests+Ergebnis (v. a. Union + fail-closed) · bestätigt: additiv/allow-only, admin-only, kein Native-Write · Risiken/Annahmen.

## Hinweis
Erster nutzbarer Increment = **Service** `tessera.set_floor_grant` (Dev Tools, für den Soak). Options-Flow-Aktion + Panel-Integration (Floor-Zeilen in der Matrix) = Folge-Task. Label/category-Selektor = **separater** späterer Task (nicht hier).
