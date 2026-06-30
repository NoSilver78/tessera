# Technische Spezifikation — Tessera Phase-1 Core (MVP v1)
Stand 2026-06-29 · Scope: ADR 0002 · Prozess: ADR 0003 · baut parallel zur Spike-Härtung (isoliert, eigener Branch)

## Ziel
Ein **lauffähiger Tessera-Kern**: **Store → Compiler → native HA-`PolicyPermissions`**, Pflege über **Area × Rolle**, Stufen **view/operate** echt durchgesetzt, Mitgliedschaft **`by_user` + `by_group` (Authentik/OIDC)**, Modi **off/monitor/enforce**, **sauberes Uninstall**. Im **Monitor-Mode jetzt baubar + testbar** (Schreibpfad via Spike D1/D4 bewiesen); **Live-Enforce-Flip** bleibt hinter dem Round-2-Gate.

## Anforderungen
### Muss (v1)
- **Store** (`.storage/tessera.*`): Rollen · Area×Rolle-Grants · Entity-Overrides · Mitgliedschaft (`by_user` + `by_group`) · `mode` (off/monitor/enforce).
- **Schema + Validierung:** schema-aware (kein bare-`True`; `{read[,control]}`-Leafs).
- **Area-Resolver:** Device-Area **und** direkte Entity-`area_id` → zu `entity_ids` expandieren (nativ löst `area_ids` nur Device-Area auf — diese Lücke schließen).
- **Compiler:** Store → native Gruppen-Policies, **deterministisch + idempotent** (gleicher Store → gleiche Policy).
- **Authentik/OIDC `by_group`:** roher `groups`-Claim → Rolle (parallel zu `auth_oidc`). **v1-Pflicht** (ADR 0002); D12-Beweis ist Vorbedingung für Enforce.
- **Auth-Adapter** (4 Verträge aus dem Spike): `AuthPolicyStore` · `UserBinding` (group_ids volle Union) · `PermissionProbe` · `RecoveryController`.
- **Mode-Manager:** off (nativ unverändert) · monitor (kompiliert+loggt, schreibt nicht) · enforce (schreibt nativ). **Monitor→Enforce nur mit explizitem User-Confirm.**
- **Uninstall/Recovery:** native Policies vollständig zurück; **fail-safe → off** bei internem Fehler; Owner nie angefasst; ≥1 Admin-Invariante (Compiler-Guard).
- **config_flow + Minimal-Panel:** Area×Rolle-Matrix + Apply/Rollback.

### Soll
- Drift-Erkennung (neue/unzugeordnete Entities) · Audit-Log (tamper-evident Hash-Chain).

### Nicht-Ziele (v1)
Label-/category-Bulk · Hochglanz-Lit-Panel · Community-Features · granulares `change` · harte untrusted-`view`-Vertraulichkeit (Tier-2).

## Annahmen
- Spike beweist die Enforce-Kanten (D5-Rescue, Leak-Matrix, D9, D11/13/15) **vor** Live-Enforce. Core baut + testet bis dahin im **Monitor-Mode**.
- HA 2026.6.x; Auth-Schreibpfad wie im Spike belegt (`_groups`/`_data_to_save`/`async_save`).

## Risiken und offene Punkte
| Risiko / Punkt | Auswirkung | Empfehlung |
|---|---|---|
| **D12 OIDC-`groups`-Claim** jetzt v1-kritisch | ohne Beweis kein `by_group`-Enforce → v1 unvollständig | **Test-Authentik-Paket** (Michael): Client + Test-Gruppen gegen `auth.pilzbuche8.de`; früh beweisen |
| Compile-Performance (2661 Entities) | große `.storage/auth`-Writes | `except`→`device_ids`-Schwelle (Spike D10); enumerieren nur wo nötig |
| Enforce-Flip = riskanteste Aktion | Lockout | User-Confirm + Lockout-Sim + Auto-Snapshot + fail-safe-off |
| Monitor↔Enforce-Divergenz | Policy ≠ Ist | in enforce **ist** die Policy nativ (kein Parallel-Pfad) |

## Architekturentscheidung
**Store = SoT (PAP) → Compiler (PDP, at-compile-time) → native Gruppen-Policies → HA-`check_entity` (PEP).** Mensch pflegt nur den Store; native Policy = generierte, rollback-bare Projektion (Analogie NetBox=Fakten/host.yml=Projektion). **Allow-only** (HA hat kein Deny). Authentik-Seitenkanal liest den rohen `groups`-Claim parallel zu `auth_oidc`.

## Modulstruktur
| Modul | Aufgabe | Schnittstellen | Risiken |
|---|---|---|---|
| `store` | Laden/Speichern `.storage/tessera.*`, Versionierung | HA Store-Helper | Migrationen |
| `schema` | Pydantic/voluptuous-Validierung, schema-aware | — | bare-True verhindern |
| `resolver` | Area→entity_ids (Device + direkte area_id) | entity/device/area-Registry | Registry-Events |
| `compiler` | Store → native Policy, idempotent | resolver, store | Determinismus |
| `providers/authentik` | `groups`-Claim → Rolle | auth_oidc-Seitenkanal | D12-Beweis |
| `auth_adapter` | 4 Verträge (Policy/Binding/Probe/Recovery), version-geguarded | `hass.auth._store` | privat/fragil |
| `mode_manager` | off/monitor/enforce + Confirm + Snapshot/Rollback | compiler, auth_adapter | Enforce-Flip |
| `recovery` | Boot-Rescue/Uninstall, außerhalb normalem Start | public `async_update_user` | darf nicht am Store hängen |
| `config_flow` + `panel` | Setup + Area×Rolle-Matrix + Apply/Rollback | HA frontend | — |

## Datenmodell / Konfiguration
`.storage/tessera.config` (mode, roles, membership: {by_user, by_group}) · `tessera.policy` (Area×Rolle-Grants, Entity-Overrides, staging) · `tessera.compiled` (letzte native Projektion + Hash) · `tessera.audit` (Change-/Decision-Log, Hash-Chain) · `tessera.state` (Drift-Fingerprint). Schemas versioniert.

## Fehlerbehandlung
**Fail-safe:** interner Fehler → `mode=monitor` (keine native Durchsetzung, read-only Preview), nie alles-deny. Owner strukturell unberührt; ≥1 Admin-Bindung Compiler-Invariante. `system_generated`-User nie managen. Apply mit Re-Read-Verify; Teilfehler → Auto-Rollback.

## Security / Secrets
Keine Secrets im Repo/Logs (1Password via stdin). OIDC-Tokenwerte nie loggen. Tests nur gegen Dev-Instanz; **Live-Enforce erst nach Round-2-Gate + Michael-Freigabe**.

## Teststrategie
**pytest + HA-Test-Fixtures**, je Modul Unit-Tests (Happy/Fehler/Grenzfälle). **Monitor-Mode-E2E** auf Dev-Instanz (Store→Compile→would-block-Log). Enforce-Edge-Tests **gated** auf Spike-Round-2. **CI grün = Mergevoraussetzung** (ADR 0003).

## Akzeptanzkriterien (v1 DoD)
Ein Nicht-Admin sieht+steuert via **`by_user` UND Authentik-`by_group`** ausschließlich die erlaubten Areas/Entities — verifiziert über **REST + WS + Service** (nicht nur UI) · `off→monitor→enforce→uninstall` sauber + reversibel · **Owner nie ausgesperrt** · CI grün · überlebt HA-Update.

## Umsetzungsschritte für Codex (klein, CI-grün je Schritt)
1. **Scaffold + Store + Schema** (`custom_components/tessera/`, config_flow-Stub, `.storage`-Roundtrip, Schema-Validierung + Tests).
2. **Resolver** (Area→entity_ids inkl. direkter area_id; Tests gegen Seed-Fixture).
3. **Compiler** (Store→native Policy, idempotent; Monitor-Mode would-block-Log; Tests).
4. **Auth-Adapter** (die 4 Verträge aus dem gehärteten Spike-Harness übernehmen; version-geguarded).
5. **Authentik `by_group`** (groups-Claim→Rolle; gated auf D12-Beweis).
6. **Mode-Manager + Enforce + Uninstall** (Confirm, Snapshot/Rollback, fail-safe-off, Recovery).
7. **config_flow + Minimal-Panel** (Matrix, Apply/Rollback).

## Erste Codex-Aufgabe
```text
Implementiere ausschließlich Schritt 1 (Scaffold + Store + Schema) für die Tessera-HACS-Integration.

Branch/Worktree: core/phase1-store-compiler (NICHT main). Verzeichnis: custom_components/tessera/.

Aufgabe:
- HACS-Integration-Skelett: manifest.json (domain "tessera", config_flow true, iot_class calculated, single_config_entry true, version 0.1.0), __init__.py (async_setup_entry/async_unload_entry, getypt), const.py (DOMAIN), config_flow.py (Minimal-Flow).
- Store-Modul store.py: lädt/speichert .storage/tessera.config + tessera.policy via HA Store-Helper (async, KEIN blocking I/O), Schema-Version, Roundtrip.
- Schema-Modul schema.py: Validierung der Store-Daten; schema-aware (verbiete bare-True / entities:true / domains:true; erlaube {read[,control]}-Leafs).

Regeln:
- Keine Architekturänderung über die Spec hinaus, keine weiteren Module in diesem Schritt.
- Best-Practice: vollständige Type-Hints, Google-Docstrings, kein blocking I/O, async-korrekt.
- Keine Secrets; nur gegen ha-tessera-dev testen; /Volumes/config read-only.

Tests/Linter:
- pytest (Store-Roundtrip, Schema-Validierung happy + reject bare-True), ruff, black --check, mypy. Alles grün.

Definition of Done:
- Schritt-1-Code + Tests, CI lokal grün (ruff/black/mypy/pytest), keine Scope-Ausweitung, Risiken benannt.
- Abschlussbericht: geänderte Dateien, Zusammenfassung, Test-Ergebnis, offene Annahmen.

Nicht ändern: spike/, exchange/, docs/, decisions/, CONTRACT.md.
```
