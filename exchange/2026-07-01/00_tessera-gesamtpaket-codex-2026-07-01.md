# Tessera — Gesamtpaket für Codex (Bedien-Modell + Mehrparteien) · 2026-07-01

**Von:** Claude (Architektur) · **An:** Codex (Agentensystem) · **Zweck:** konsolidierter Stand aller Anfragen, Ergebnisse und Aufgabenstellungen der Design-Phase „Tessera-Bedienung + Authentik + Mehrparteien". Ein Einstiegspunkt.

> ✅ **Der übergeordnete Gate ist entschieden (Abschnitt 4):** Echte Mieter-Isolation auf EINER HA-Instanz ist quellcode-verifiziert **NICHT mit vertretbarem Aufwand erreichbar** (render_template, History/Logbook-DB-Reads, Automation-Kontext-Stripping, Camera-Proxy, Admin-Bypass lecken lautlos; Tessera deckt nur die native Permission-Ebene). **Empfehlung: getrennte HA-Instanzen pro Einheit.** → Damit ist Tesseras Scope geklärt: **Ein-Haushalt-/Intra-Instanz-RBAC**, NICHT Mandantentrennung. Voller Report: `spike/reports/tessera-multitenant-isolation-feasibility-2026-07-01.md`. **Owner-Entscheidung zur Architektur (Abschnitt 4) steht noch aus.**

---

## 0. Kontext + Owner-Entscheidungen
Tessera ist eine fertige, dev-erprobte, **öffentliche** HA-RBAC-Integration (`NoSilver78/tessera`, HACS-installierbar, Release bewusst noch nicht getaggt). Modell: `{view/operate/change} × Rolle × Area` → native HA-Gruppen-PolicyPermissions (allow-only), Modi off/monitor/enforce (fail-safe-to-monitor), D9-Gate. Verifiziert per Dev-E2E: enforce-Schreib-Zyklus, CXR-02, D9-Ack, Restore byte-genau.

**Owner-Entscheidungen (2026-07-01):**
1. **Mehrparteien = ECHT** — getrennte Einheiten (EG/UG/DG), Mieter dürfen sich technisch NICHT sehen. → macht die dokumentierten Leak-Pfade zum potenziellen **harten Sicherheits-Gap** (Abschnitt 4).
2. **Authentik parallel** — `by_group` soll funktional werden, parallel zum lokalen Pfad. **Aber:** spec/impl parallel, **Scharfschaltung strikt gegated** (Codex-NO-GO für sofortige De-Inertness).
3. **Erst validieren, dann bauen.**
4. **Wizard: ja, schlank, zuletzt.**

## 1. Artefakt-Index (alle Anfragen + Ergebnisse, alle auf `main`)
| Datei | Art | Kern |
|---|---|---|
| `tessera-bedienmodell-2026-07-01.md` | **Ergebnis/Modell** | Bedien-/UX-Modell (§1–7) + Paket-Abgleich (§8) + Codex-Reconciliation (§9) |
| `tessera-bedienmodell-crossvalidation-request-codex-2026-07-01.md` | Anfrage | Validierungsauftrag (9 Dimensionen inkl. Mehrparteien-Härtetest) |
| `tessera-bedienmodell-crossvalidation-codex-2026-07-01.md` | **Ergebnis (Codex)** | ACCEPT-Richtung / AUFLAGEN-Bau / NO-GO-sofort-by_group |
| (extern) authentik-RBAC-Übergabepaket | Anfrage/Brief | ursprünglicher Mehrparteien-Brief (~70 % durch Tessera beantwortet; Rest in §8) |
| *(pending)* Isolations-Machbarkeit | **Ergebnis (läuft)** | Abschnitt 4 — übergeordneter Gate |
| `docs/concept.md`, `docs/spec-enforce.md`, `docs/QUALITY.md`, `SECURITY.md`, ADR 0005 | Referenz | Architektur, allow-only, by_group-Inertness, Leak-Pfade |

## 2. Konsolidierte Ergebnis-Lage (hohe Konfidenz = beide Systeme deckungsgleich)
- **UX-Ansatz: „C-modifiziert"** — Custom-**Panel** (Matrix, Membership, Effective-Access, Preflight, D9-Acks, Authentik-Mapping) · **Options-Flow** nur Skalar `MODE` + lineare Fallbacks · **Wizard** schlank, zuletzt. Store = einzige SoT.
- **Verifizierte Backend-Realität:** Monitor liefert nur Aggregat (kein per-Event-Deny-Log); `by_group` `v1-inert` (ADR 0005); D9-Ack-Services existieren (ohne UI); `compute_enforce_plan` gate't, ist aber **kein renderbarer PASS-Preflight** (braucht neues DTO).
- **Codex-AUFLAGEN übernommen:** siehe Modell §9.

## 3. Aufgaben-Backlog (mit Gating — NICHT einfach abarbeiten)

### 3a. READY — isolations-unabhängig, sofort spec-fertig
- **T1 — `by_user`-Membership-Writer + Panel-Sektion.** Der Soak-Unblocker (schließt „User→Rolle"-Lücke). **Codex-Sicherheits-Spec (verbindlich):** WS-Service `tessera/membership/set` **admin-only** (`require_admin`), **kein** direkter Native-Auth-Write; schema-validiert, unbekannte User/Rolle **fail-closed**; in `enforce` **zwingend** über den zentralen `_compile_for_mode_safely`/Apply-Guard-Pfad (wie Matrix-Updates); **redacted** Audit (User-/Rollen-IDs ja, keine Claims/Secrets). **Tests:** unknown user/role, last-admin/owner-risk, owner/system-generated-Target-Rejection, kein Native-Write bei Block, recompile-failure-fail-safe. Membership-UI-Ort = **Panel** (nicht Options-Flow).

### 3b. READY nach dem Isolations-Verdikt (Tessera-Scope = Intra-Instanz-RBAC, ungated)
- **T2 — Effective-Access-Read-Schicht + Preflight-DTO.** Forward (per-User) + reverse (per-Area), Herkunfts-Attribution, **explizite PASS/BLOCK-Felder** (Owner-survives, Allow-only, D9, Linter, Auth-Version) für die UI. *(Codex-Fund: heute liefert der Plan diese nicht als PASS.)* Nicht mehr isolations-gegated — Tesseras Scope ist geklärt.
- ~~**T4 — Leak-Pfad-Härtung für Ein-Instanz-Isolation**~~ **ENTFÄLLT.** Das Isolations-Verdikt (§4) empfiehlt getrennte Instanzen; die Tenant-Grenze ist die Instanz, nicht Tessera. Kein WS-Filter/Proxy/Core-Patch-Projekt in Tessera.

### 3c. GATED auf die `by_group`-Gates (Authentik-Track, parallel spezifizierbar, nicht scharf)
- **T3 — Authentik-Spec-Branch.** Mindest-Gates VOR Aktivierung: Claim-Hook (redacted), Effective-Union `by_user ∪ valid_by_group` mit Herkunft, **Linter+Preflight prüfen dieselbe Union wie Apply**, leerer/kaputter Claim entfernt nie still Rollen (block/fail-safe), Owner-Survival-Tests, **D12-Live-Beweis**. **„Nur das Compiler-Flag drehen" ist verboten** (koordinierte Änderung über Compiler+Mode-Manager+Linter+Effective-View+Tests). OIDC-Integration klären (`hass-oidc-auth` vs `auth_oidc` — liefert wer den rohen `groups`-Claim?).

### 3d. Später
- entity_overrides-UI (backend-real, UX-unsichtbar) · Rollen-Rename/Duplicate/Delete + Bulk · Deny-Evidence (erst synthetisch, dann real+Retention) · Wizard (Panel-Stepper, nur Erststart/enforce-Ramp/Authentik).

## 4. GATE ENTSCHIEDEN — Mehrparteien-Isolations-Machbarkeit (übergeordnet)
**Verdikt (quellcode-verifiziert gegen HA 2025.1.4, voller Report `spike/reports/tessera-multitenant-isolation-feasibility-2026-07-01.md`):** Echte Mieter-Isolation auf EINER Instanz = **NO-GO mit vertretbarem Aufwand.** Tessera deckt nur die native Permission-Ebene (state-read + entity-service-control, konditional). **Lautlos leckende needs-architecture-Löcher:** permissiver Group-Merge (`merge.py:26-49` + `system-users`=read-all), Admin-Bypass, **Automation-Kontext-Stripping** (`automation/__init__.py:644`, Aktionen laufen als System), **History/Logbook/Recorder-DB-Reads** (kein per-user-Filter, `/api/logbook` dumpt das Haus), **render_template** (kein require_admin/check_entity → jeder liest jede Entity), **Camera/Image-Proxy** (HTTP-Bytes ohne Hook). Custom-WS-Filter schließt nur einen Teil; Reverse-Proxy sieht nicht in Automation/Template-Sensoren; Core-Patch = untragbarer Fork.
**Empfehlung: getrennte HA-Instanzen pro Einheit** (echte Isolation per Prozess-/Auth-Grenze; geteilte HW über eine Whitelist-„Haus-Instanz"). **Konsequenz fürs Backlog:** die Tenant-Grenze ist die **Instanz**, nicht Tessera → **T4 entfällt** (kein Ein-Instanz-Leak-Pfad-Härtungsprojekt). Tesseras Scope ist damit **geklärt + unblockt**: Ein-Haushalt-/Intra-Instanz-RBAC. T1/T2/T3 bleiben gültig (Tessera pro Instanz). **→ Owner-Entscheidung zur Architektur ausstehend.**

## 5. Offene Owner-Entscheidungen (blockieren Detail-Specs)
- **Doku↔Code-Divergenz (vor Authentik):** User ohne wirksame Rolle — Code fällt auf Default-Rolle, `concept.md` fordert enforce-refusal. Welches Verhalten ist korrekt?
- Deny-Log-Quelle (synthetisch zuerst) · Preset-Personas (welche + Grants, gegen realen Bestand) · Authentik-Matching Slug vs Name (Slug empfohlen, D12-unbewiesen).

## 6. Anweisung an Codex
1. **Lies** die Artefakte aus §1 (v. a. Modell §1–9 + deinen eigenen Validierungs-Report).
2. **Bau nichts aus 3b/3c**, bevor das Isolations-Verdikt (§4) da ist und der Owner Go gibt.
3. **T1 (`by_user`-Writer)** ist isolations-unabhängig + spec-fertig — sobald der Owner „go" sagt, ist das der erste PR (Branch `feature/membership-by-user`, PR gegen `main`), streng nach der Sicherheits-Spec + Test-Liste in 3a. Claude gate't hart (Membership berührt den Enforce-Plan → sicherheitsrelevant).
4. **Optional jetzt (reiner Review, kein Code):** prüfe das Task-Backlog + die Gating-Logik auf Vollständigkeit/Fehler und melde Lücken im festen Format — aber ohne Implementierung vor Owner-Go.
