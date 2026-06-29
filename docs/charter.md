# Produkt-Charter — Eigenständiges HA-Berechtigungssystem (RBAC)
Name: **Tessera** *(gewählt 2026-06-29 — lat. römisches Zugangs-/Identitäts-Token)* · Domain `tessera` · Repo `NoSilver78/tessera` (geplant) · Stand 2026-06-29
Status: **Foundation / G0** · Scope-Entscheidung: **vollständiges System, eigenständiges Produkt, unabhängig von Atrium**

## 1. Vision (One-liner)
**Das fehlende echte RBAC für Home Assistant:** pro Area/Entity die Stufen *ansehen / bedienen / ändern*, gespeist aus deinem IdP (Authentik/OIDC), **echt durchgesetzt auf nativen HA-Policies** (kein Core-Fork, kein Monkeypatch), mit einer richtigen Admin-UI. Standalone HACS-Integration, für *jede* HA-Installation.

## 1a. Harte Constraints (nicht verhandelbar)
- **Zero-Dependency:** läuft standalone auf einer **vanilla HA-Installation** — **KEINE Abhängigkeit von Atrium**, keinem anderen HACS-Paket, keinem IdP. „Funktioniert auch ohne" ist **Akzeptanzkriterium**, nicht Nice-to-have.
- **Rollen-Mitgliedschaft = pluggable Provider:** **(a) LOKAL** (User↔Rolle im eigenen Store, ohne IdP — Default/Baseline, funktioniert immer) **+ (b) Authentik/OIDC-Gruppen** (optional, **first-class, getestet, lauffähig**). Der RBAC-Kern hängt **nie** am IdP; Authentik ist eine *Quelle* der Mitgliedschaft, keine Voraussetzung.
- **Authentik wird voll berücksichtigt und funktioniert** (`groups`-Claim → Rolle, parallel zu `auth_oidc`) — aber als zuschaltbarer Provider, nicht als Pflicht.

## 2. Warum es existiert (Positionierung)
Schließt eine **seit 2020 offene Lücke** (HA-Discussions [#22](https://github.com/orgs/home-assistant/discussions/22), [#1171](https://github.com/orgs/home-assistant/discussions/1171), Architektur [#832](https://github.com/home-assistant/architecture/issues/832)): HA hat intern read/control/edit-Policies, aber **kein UI, nur 3 fixe Gruppen, Owner-Bypass**.

| Gegen | Abgrenzung |
|---|---|
| **`ha-access-control-manager`** (ACM) | + Authentik-Rollen-Mapping, **persistente Area-Vererbung**, Entity-Overrides, Migrations-Tooling, echte 3-Stufen-Matrix, Drift-Erkennung. ACM schreibt nur `entity_ids` ohne Vererbung/OIDC. |
| **`user-rbac`** | **kein Monkeypatch** → update-fest über dokumentierte Hooks (`check_entity`/`POLICY_READ`/`POLICY_CONTROL`). |
| **kiosk-mode / restriction-card / browser_mod / dash-bouncer** | **echte Backend-Durchsetzung** (REST/WS/Service), nicht nur kosmetisch. |

## 3. Scope — vollständiges System
- **Subjekte:** Rollen (benannte Permission-Bündel) · **Rollen-Mitgliedschaft dual-mode/pluggable: lokal (ohne IdP, Baseline) + Authentik-OIDC-`groups` (optional, first-class)** · Mehrfach-Mitgliedschaft (most-permissive-Merge) · sichere Default-Rolle · Owner-Bypass dokumentiert.
- **Objekte/Scope:** Precedence global→domain→area→device→**entity-override** · **eigener Area-Vererbungs-Resolver** (Device-Area **und** direkte Entity-`area_id` → zu `entity_ids` expandiert, da native `area_ids` nur Device-Area kennt) · Label-/`entity_category`-Selektoren (mit Namespace).
- **Stufen:** **view=read · operate=control** echt durchgesetzt; **change=admin-gated** + eng definierte Eskalation (nativ nicht granular).
- **Enforcement:** Policy-Compiler → native HA-Gruppen-Policies; **Allow-only-Semantik** (keine breiten Allows, wo Ausnahmen nötig — HA hat kein Deny); Guards/Tests für Custom-Service-/Domain-/Template-/Script-Bypass.
- **Admin-UI:** config_flow + Panel — Matrix 39 Areas × Rollen, Override-Editor, **Impersonation-Preview** „was sieht/darf User X", Diff/Apply/Rollback, Drift-Anzeige.
- **Migration/Betrieb:** Bulk-Seed + Default-Policy · **Monitor/Dry-Run-Mode** (loggt, was geblockt würde) · **Panik-Disable** (zurück auf nativ) · backup-festes ACL-Store · Audit-Log · Drift-Repair (neue/unzugeordnete Entities).
- **Optionale Integrations-Schnittstelle:** exponiert ACL-Entscheidungen sauber (Event/Service/Template) → externe Governance-Layer (z. B. Atrium-Dispatcher) *können* konsumieren — **ohne Abhängigkeit in beide Richtungen.**
- **Community-Features (Roadmap):** Per-User-Dashboard-Generator · Gäste-/Kids-Rollen · Sensible-Entity-Hide · scoped-Token-Helfer.

## 4. Nicht-Ziele (v1)
- Granulares per-Entity-„change" (bleibt admin-split; WS-config-Interception zu fragil).
- Reverse-Proxy/Middleware-Ebene (D).
- **Harte untrusted-Isolation** (= 2-Instanz-`remote_homeassistant`-Muster; bewusst *außerhalb* dieses Produkts).
- Kontext-/bedingungsabhängige Permissions (Tageszeit/Anwesenheit) → v2.

## 5. Architektur (standalone)
Eigene Custom Integration `custom_components/<name>` + eigener ACL-Store (`.storage/<name>`). **Policy-Compiler** projiziert den Store zur Login-/Apply-Zeit in **native HA-Gruppen-Policies** (read/control). **Authentik-Seitenkanal** liest den rohen `groups`-Claim parallel zu `auth_oidc`. **Frontend-Panel** (eigenes JS-Bundle) für die Matrix. **Keine** Abhängigkeit zu Atrium/D19/D25/D27.

## 6. Roadmap / Phasen
| Phase | Inhalt | Aufwand |
|---|---|---|
| **0 — Spike** | Native Policy-Schreibpfad, `Users`-Merge, Area-Resolution (direkt vs Device), Non-Admin REST/WS/Service real auf **Dev-Instanz** messen; ACM als Referenz | 5–8 PT |
| **1 — Core** | ACL-Store + Schema + Resolver + Compiler + Authentik-Mapping + Migration + Monitor-Mode | 18–35 PT |
| **2 — Admin-UI** | config_flow + Panel (Matrix, Override, Preview, Apply/Rollback) | 12–20 PT |
| **3 — UX + Betrieb** | Dashboard-/Lovelace-Filter (Komfort) + Drift-Repair + Audit-Log | 8–15 PT |
| **4 — Produktreife** | Security-Test-Matrix, HA-Version-Kompat, i18n DE/EN, Doku, **HACS-Publish**, Community-Features | 12–25 PT |
| **Σ** | **vollständiges Produkt** | **~55–100 PT** |

## 7. Governance (Rollenvertrag, analog Atrium)
- **Claude:** Architektur, Datenmodell, Compiler-/Enforcement-Design, Security-Review, viel Code.
- **Codex:** unabhängige Implementierung/Validierung, Tests, Repo-Analyse — Ping-Pong über `outputs/` + Michael als Kurier, **ACCEPT/MODIFY/REJECT**.
- **Michael:** Orchestrator, Host-/`sudo`-/Reload-Aktionen, Freigaben, **Dev-Instanz** betreiben.
- **Gates G0–G3** (Foundation → Backup/Rollback → Pro-Änderung → DoD). **Auth-Tests NIE gegen die Live-CM5** (Lockout-Risiko) — nur Dev-Instanz.

## 8. Erfolgskriterien (Definition of Done v1)
Ein Nicht-Admin sieht+steuert via Authentik-Gruppe **ausschließlich** die erlaubten Areas/Entities — verifiziert auf **REST + WS + Service-Call** (nicht nur UI) · überlebt ein HA-Update · von einem Fremden via HACS installierbar · **Owner nie ausgesperrt** · Monitor-Mode + Panik-Disable funktionieren.

## 9. Open Decisions (deine Calls)
| # | Frage | Vorschlag |
|---|---|---|
| **N1** | Produktname | ✅ **Tessera** (gewählt 2026-06-29) |
| **N2** | Repo | `NoSilver78/<name>` (eigen, getrennt von HA-config + Atrium) |
| **N3** | Lizenz/Öffentlich | OSS (MIT/Apache-2.0) für Community-Produkt — empfohlen |
| **N4** | Dev-Instanz | separate HA-Instanz (Container/VM) für Auth-Tests — Pflicht vor Phase 1 |
| **N5** | Start | Phase 0 (Spike) als erstes Arbeitspaket |
