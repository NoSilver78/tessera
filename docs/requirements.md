# Requirements-Katalog: HA-Berechtigungskonzept (Entity/Area-RBAC)
Ergänzt `berechtigungskonzept_aufgabenpaket.md` · Stand 2026-06-28 · Tags **[M]**ust/**[S]**hould/**[C]**ould · **⟶ Dx** = offene Entscheidung

## R1 — Subjekt-Modell (WER)
- [M] Rollen = benannte Permission-Bündel; Gruppen→Rollen; User ∈ mehrere Gruppen/Rollen.
- [M] **Rollen-Mitgliedschaft dual-mode (pluggable Provider):** (a) **lokale** Zuweisung User↔Rolle im eigenen Store — ohne jeden IdP, **Baseline/funktioniert immer**; (b) **Authentik** OIDC-`groups`→Rolle — optional, first-class, **getestet+lauffähig**. **Kern hängt NIE an Atrium oder IdP** („muss auch ohne funktionieren").
- [M] Kombinations-Semantik bei Mehrfach-Mitgliedschaft (Union der Allows, höchste Stufe gewinnt — kein nativer Deny).
- [S] Technische/Service-Accounts (mqtt-service, Automationen) als eigene Rolle.
- [M] Owner-Bypass akzeptiert + dokumentiert (ha-admin sieht/darf IMMER alles).
- [M] Sichere Default-Rolle für nicht-gemappte User (minimal).
- **⟶ D2:** lokale 4 User auf OIDC migrieren **oder** lokale-User→Rollen-Zuweisung in HA unterstützen?

## R2 — Authentik / IdP-Integration (zentral)
- [M] Authentik = Single Source of Truth für Gruppen-Mitgliedschaft (Personen→Gruppen werden in Authentik gepflegt).
- [M] Konfigurierbares Mapping **Authentik-Gruppe → HA-Rolle → Permission-Set** (nicht hartkodiert).
- [M] `groups`-Claim parallel zu `auth_oidc` v1.1.1 lesen (reicht nur binär admin/user durch).
- [S] Nested Authentik-Gruppen / Hierarchie unterstützen.
- [S] Verhalten bei Authentik-Ausfall: gecachte Claims / lokaler Notfall-Override (Verfügbarkeit).
- [M] "authentik Admins" → HA-Admin bleibt bestehen.
- Truth-Level-Sauberkeit: **Authentik = Identität, HA-Integration = App-Permissions** (passt zu NetBox/1Password-Trennung).
- **⟶ D4:** Sync-Zeitpunkt — nur Login-Zeit (Claim) **oder** near-real-time (Authentik-API-Poll/Webhook)?

## R3 — Objekt-Modell / Scope (WORAUF)
- [M] Scope-Hierarchie mit fester Precedence: **global-default → domain → area → (device) → entity-override**.
- [M] **Area = primäre Sicherheitszone** ("mehrere Bereiche").
- [M] Entity-Level-Override für Ausnahmen.
- [M] Eigener Area-Vererbungs-Resolver (Device→Area + Override; nativ nur `device.area_id`, 1402 Entities area-los).
- [S] **Label-Selektoren** für Bulk (797 Entities gelabelt; z. B. `label:sensibel` → restricted).
- [S] `entity_category`-Selektor (493 diagnostic / 374 config → Admin-Kandidaten).
- [S] Domain-Selektoren (alle `lock`/`camera`/`alarm_control_panel`).

## R4 — Berechtigungsebenen (WAS)
- [M] 3 Kernstufen **view (ansehen) / operate (bedienen) / change (ändern)**. Map: view=`POLICY_READ`, operate=`POLICY_CONTROL`.
- [S] Semantik "kennt-Entity-nicht" (unsichtbar) vs. "sichtbar-aber-gesperrt".
- [C] Feinere Sub-Stufen: view(state | +history | +attribute), operate(direkt | mit-Bestätigung | rate-limited).
- **⟶ D1:** change **granular pro Area/Entity** (teuer, WS-config-Interception, update-fragil, +5–10 PT) **vs. Admin/Non-Admin-Trennung** (empfohlen, update-fest).

## R5 — Enforcement / Sicherheit (WIE)
- [M] **Echte Backend-Durchsetzung** über native Hooks: WS `get_states`, REST `/api/states`, `call_service`.
- [M] ⚠️ **Alle Zugriffsflächen bewerten/abdecken:** WS (`subscribe_events`, `render_template` ← Template-Leak!, `history`/`logbook`, `config/*`), REST, Service-Calls, Recorder/Statistics.
- [S] Voice/Assist-Exposure pro User · Companion-App · Conversation/LLM-Agent-Entity-Exposure.
- [S] **Audit-Log**: wer hat was gesehen/bedient/geändert (passt zu deiner Change-Mgmt-Philosophie).
- [M] **Fail-safe**: bei Integrations-Fehler → sicher (deny), aber **NIE Owner/Admin aussperren** (Lockout-Schutz).
- [S] Defense-in-depth: Backend (C) + Frontend-Hide (A) konsistent.
- Hinweis: Automationen/Scripts laufen als System-Kontext → umgehen die ACL (Standard; bewusst so lassen).
- **⟶ D5:** Template-/History-Leakage mit abdecken (Viewer liest restricted Entity über sichtbaren Template-Sensor)?

## R6 — Verwaltung / UX
- [M] Admin-UI: Rollen definieren · Permissions je Area/Entity · Authentik-Gruppen-Mapping.
- [M] Bulk-Operationen (Area-weit, Label-weit, Domain-weit).
- [S] **Preview/Impersonation** "was sieht/darf User X?".
- [S] Matrix-Ansicht (39 Areas × Rollen).
- [M] Onboarding neuer Entities: Default-Policy + Hinweis "N neue Entities unzugeordnet".
- [S] Import/Export (YAML) → Versionierung + Backup + Community-Sharing.
- [S] Lokalisierung DE/EN.

## R7 — Nicht-funktional
- [M] **Update-Festigkeit**: kein Monkeypatch/Core-Fork (Kern-Constraint).
- [M] Performance: 2661 Entities × 7 User — Policy-Compile schnell, Per-Request-Check günstig.
- [M] Security-kritische Testabdeckung (Owner/Admin/User/RO-Pfade, Lockout, Migration an 2661 Entities).
- [S] **HACS-distribuierbar** (= die "Alternative zum bestehenden Paket"; Community-Nutzen).
- [S] Graceful Degradation bei HA-Updates · Observability/Debug-Logs.

## R8 — Betrieb / Migration / Lifecycle
- [M] Migration 2661 Entities/39 Areas; **Datenhygiene-Vorlauf** (1402 area-lose Entities + 107 area-lose Devices zuordnen).
- [S] **Monitor-/Dry-Run-Modus**: loggen, was geblockt WÜRDE, ohne durchzusetzen → dann scharf (analog deinem FreeRADIUS-Monitor-Mode).
- [M] **Panik-/Disable-Schalter**: ACL aus → zurück auf nativ (Lockout-Notausgang).
- [M] Backup/Restore der ACL überlebt HA-Restore.
- [S] Orphan-Cleanup (Entity/Area gelöscht → ACL-Eintrag).
- [S] Änderungs-Journal der Permission-Änderungen (Audit-Trail).
- **⟶ D3:** Default-Policy — **deny-by-default** (sicher, mehr Migration) vs. **allow-view-by-default** (sanfter Start).

## R9 — Community-Abfallprodukte (mitnehmbar)
- [S] **Per-User-Dashboards** auto-generiert aus sichtbaren Entities — [#1171](https://github.com/orgs/home-assistant/discussions/1171), [Community 317971](https://community.home-assistant.io/t/view-access-per-user/317971), 331905.
- [S] **Kids-/Kinder-Konten** (Security-Roles, nur eigenes Zimmer) — [#634179](https://community.home-assistant.io/t/security-roles-kids-account/634179).
- [S] **Sensible Entities** (Kameras/Schlösser/Präsenz) vor Usern verbergen — [Community 720255](https://community.home-assistant.io/t/hide-entities-sensors-from-user/720255).
- [S] Karten-/View-Sichtbarkeit per Rolle (state-switch-artig, aus derselben ACL) — schließt Regression [#28480](https://github.com/home-assistant/frontend/issues/28480).
- [C] **Gäste-/Temporär-Zugang** (zeitlich begrenzte Rolle, QR) — HA-Pass-artig.
- [C] **Scoped Long-Lived Access Tokens** (entity-scoped) — [#190504](https://community.home-assistant.io/t/support-for-permissions-on-long-lived-access-tokens/190504), [WTH #805237](https://community.home-assistant.io/t/wth-cant-i-set-permissions-on-a-long-lived-access-token/805237), [arch #832](https://github.com/home-assistant/architecture/issues/832).

## R10 — Erweitert / visionär (meist [C], v2+)
- [C] **Kontext-/bedingungsabhängige** Permissions (Tageszeit, Anwesenheit home/away, Standort) — "Kinder nachts kein Thermostat", "Gäste nur wenn jemand daheim".
- [M] **Koexistenz** mit nativer `Read Only`-Gruppe + HA-"exposed entities" (Assist/Cloud) — nicht brechen.
- [S] Benachrichtigung bei **verweigertem Zugriff** (Security-Alerting).
- [S] Read-only-Sharing-Use-Cases (Energie-Dashboard für Dritte ohne Steuerung).
- [C] Approval-Workflow (Zugriff anfragen → Admin bestätigt) · Quotas/Rate-Limits auf operate.

## Offene Entscheidungen (gemeinsam durchgehen)
| # | Entscheidung | Empfehlung (vorläufig) |
|---|---|---|
| **D1** | change-Granularität | Admin/Non-Admin-Trennung (update-fest) |
| **D2** | lokale User vs. OIDC | alle 7 auf OIDC migrieren |
| **D3** | Default-Policy | deny-by-default, aber Monitor-Mode zuerst |
| **D4** | Authentik-Sync-Timing | Login-Zeit (Claim) v1, near-real-time später |
| **D5** | Template/History-Leak abdecken | ja (sonst Sicherheitslücke) |
| **D6** | Scoped Tokens in-scope | v2 (fällt teilweise ab) |
| **D7** | Per-User-Dashboards in-scope | v2 (fällt aus ACL ab) |
| **D8** | Monitor-/Dry-Run-Mode | ja (Pflicht für sicheren Rollout) |
| **D9** | Gruppen→Rollen-Mapping | n:m, nested später |
| **D10** | Frontend-A-Layer (browser_mod) | dünn mitnehmen (UX-Konsistenz) |
| **D11** | Policies für alle 2661 oder nur 2220 aktive Entities? | nur aktive + Default-Deny-Fallback |

---

## Codex-Review (unabhängige 2. Instanz) — eingearbeitet 2026-06-28
Codex hat (a) eine **eigene** Schätzung erstellt **und** (b) mein Agentensystem-Ergebnis validiert (Verdikt **MODIFY**). Quellen: `~/Documents/Codex/2026-06-14/.../outputs/berechtigungskonzept-{aufwandsschaetzung,agentensystem-ergebnis}-2026-06-28.md`.

### Bestätigt (Konvergenz → höhere Konfidenz)
Neubau auf **nativen HA-Policies (C)** statt Frontend-Paket patchen · C(+B)-Zielarchitektur, A/B = nur UX/keine Sicherheit · Modell read/control/edit + scopes entity/device/area/domain/all + most-permissive-wins · change/configure = Phase-1 **admin-only** · Default-`Users` gefährlich · Authentik-Gruppen als Rollenquelle.

### Technische Korrekturen (eingearbeitet)
- **[M] Allow-only, KEIN Deny:** HA-Policies mergen most-permissive — eine restriktive Entity-Regel überschreibt KEINE breitere Domain/All-Allow. ⇒ Compiler darf **keine breiten Allow-Regeln** erzeugen, wo Ausnahmen nötig sind; Overrides = *erlaubende* Spezialisierungen. *(schärft R4/R5 + Datenmodell)*
- **[M] `area_ids` = Device-Area:** native `area_ids` löst über `device.area_id` auf → die **419 direkt-entity-zugeordneten** Entities deckt es NICHT; Resolver muss sie selbst zu `entity_ids` expandieren. *(schärft R3)*
- **[M] Custom-Service-Bypass:** nur Entity-Component-Services werden auto-geprüft; Custom-/Domain-Services, `entity_id:all`, Templates, Scripts können Enforcement umgehen → Guard + Test. *(R5-Risiko)*
- **[S] Owner ≠ Admin:** Owner bypassed alles; Admin = volle Entity-Rechte (System-Policy) + `is_admin` — nicht identisch. *(R1)*

### Grounding-Korrekturen (Codex-Recount)
- **15 YAML-Dashboards** (11 `dashboards/` + 4 `atrium/`) + 1 Storage-Dashboard — **nicht 11**.
- **441 disabled/hidden** Entities (436+5) → nur **2220 enabled+visible** (⟶ D11).
- **1 HA-Owner** (nicht 3); die „3" = 3 `Administrators`-Mitglieder.
- Area effektiv: 419 direkt + 840 via Device = **1259**, **1402 ohne** (1074 ohne bei enabled+visible).
- Labels (797 Entities) **fachlich belegt** → als ACL-Labels nur mit Namespace/Trennung. *(schärft R3-Label-Selektor)*

### Paket-Landschaft (erweitert/korrigiert)
- **`Darkdragon14/ha-access-control-manager` (ACM)** = nächstliegendes „bestehendes Paket": schreibt **native HA-Gruppen-Policies** + Lovelace-`visible`-Sync (v1.10.1 2026-06-28, ~33★). ABER schreibt primär `entity_ids` (kein `area_ids`) → Area-Vererbung/OIDC/Override/Migration fehlen. **⇒ viabler Fork-/Upstream-Kandidat, nicht nur Blueprint.**
- NEU: `WOOWTECH/ha_permission_manager` (archiviert, A/B, ungeeignet) · `hfehrmann/hass-dash-bouncer` (B, nur Dashboard-Nav).
- `user-rbac` **demotet**: nur operate-Middleware-Referenz (instabil; view=future; Scripts umgehen RBAC).

### NEUE Requirements (von Codex)
- [M] **Compiler-Constraint „keine breiten Allows"** (Folge fehlender Deny-Semantik).
- [S] **Drift-Erkennung** (Repair/Sensor): neue/unzugeordnete Entities, Area-Move-Drift, Policy-Differenz.
- [M] **Active-vs-all-Entscheidung** (D11).
- [S] **Custom-Service-Guard + Test-Harness** für Service-Calls ohne sauberen `entity_id`-Pfad.
- [C] **Sonderoption „2. HA-Instanz"** (`remote_homeassistant`) für *harte* Etagen-/Tenant-Isolation (untrusted-tauglich, Infra-Projekt).

### ⚖️ Aufwand — RECONCILIATION (wichtigster Punkt)
| Quelle | Neubau × C | Anmerkung |
|---|---|---|
| Mein Agentensystem | ~20–42 PT impl / **~32 PT** Planung | **MVP-optimistisch** (schlanke UI, change=admin) |
| Codex (eigene Schätzung) | **55–100 PT** produktionsnah · 30–75 PT ACM-Fork | volle Admin-UI 10–20 + Test-Harness 8–18 + Drift/Doku |
| **Konsolidiert** | **MVP ~30–45 · ACM-Fork ~40–75 · Produktionsreif ~55–100** | Differenz = Reifegrad, kein Widerspruch |

**Ehrlich:** Codex' Höher-Schätzung ist berechtigt — mein ~32 PT war das untere MVP-Ende; produktionsreif (echte Admin-UI 39 Areas × Rollen + Override-Editor + Preview/Diff/Apply/Rollback + Security-Test-Harness) liegt realistisch bei **55–100 PT**.

### 🔑 Verfahrens-Empfehlung (von Codex übernommen): SPIKE FIRST
**Nicht sofort bauen — erst 5–8 PT Spike** mit ACM in Dev: Policy-Schreibpfad, `Users`-Merge, direkte-Entity-Area vs. Device-Area, Non-Admin REST/WS/Service real messen. **Danach** Entscheidung ACM-Fork (~40–75 PT) vs. Neubau (~55–100 PT). De-riskt die größte Unbekannte für kleines Geld.

---

## Bezug zum bestehenden Atrium-Projekt (Verzeichnis-Suche 2026-06-28)
Das Berechtigungskonzept existiert **nicht isoliert** — das `maison-atrium`-Projekt (gleiches `outputs/`-Verzeichnis) enthält bereits überlappende Zugriffs-/Rollen-Arbeit, die **wiederzuverwenden/zu integrieren** ist (nicht duplizieren).

### Bereits in Atrium vorhanden
- **Actor-/Rollen-Modell** (`household-layer-v0`, `responsibility-policy-v1`): `authorization ∈ {authenticated · resident · operator · admin}` + `credential ∈ {session · pin}`; Rollen **Admin/Operator · Haushalt · Gast** (Authentik-Gruppen), Gast-Modus. ⇒ **RBAC soll diese Actor-Stufen wiederverwenden, keine Parallel-Rollen erfinden.** *(überschreibt R1/R2 teilweise)*
- **Laufzeit-Action-Governance** (`responsibility-policy-v1`/D25-Dispatcher): `effective_class = max(base, scope_floor, context_floor, responsibility_floor)` + Deny-Regeln; **deny-by-default**; **A/B/C-Friktion** (allow / Vorschau→Bestätigen / require-elevation+PIN); „shared/external nie still"; detaillierte Klassentabelle je Aktion. ⇒ **Das ist die natürliche Enforcement-/Friktions-Schicht für „bedienen/ändern".** *(betrifft R4/R5)*
- **Harte-Isolation-Entscheidung** (`zugriff-rechtemanagement-recherche`): für „Michael (eg-nutzer) darf UG/OG NICHT steuern" als *untrusted-taugliche* Grenze ist **2 Instanzen + `remote_homeassistant`** gewählt (Single-Instanz = kosmetisch, WS/REST flach). *(konkretisiert die Codex-Sonderoption)*

### Architektonische Konsequenz — ZWEI-TIER-MODELL
1. **Tier „Soft-RBAC" (dieses Konzept, Single-Instanz):** view/operate/change × Rolle × Area/Entity über native HA-Policies, für *vertraute* Nutzer (Familie). Echte read/control-Durchsetzung; **Atrium-Dispatcher liefert die operate/change-Friktion**. *Nicht* untrusted-hart.
2. **Tier „Hard-Isolation" (2 Instanzen + remote_homeassistant):** für *untrusted*-Grenzen (Etage/Tenant) — Entitäten existieren physisch nicht. Infra-Projekt.
⇒ Familien-Fälle = **Tier 1**; der UG/OG-Michael-Fall = **Tier 2**. Beide im Konzept benennen.

### Verortung & Komposition
- **WER×WAS (RBAC-Matrix: view/operate/change × Rolle × Area/Entity)** ist der **Komplement** zum Atrium-Dispatcher **WIE (Friktion A/B/C)**: RBAC entscheidet *ob* erlaubt, der Dispatcher *mit welcher Hürde*. Beide komponieren.
- **⚠️ ENTSCHEIDUNG 2026-06-28 (Michael): EIGENSTÄNDIGES PRODUKT, unabhängig von Atrium.** Die frühere „Modul-in-Atrium"-Verortung ist **überholt**. Stattdessen: **standalone HACS-Integration** (eigener Repo, eigenes `custom_components/<name>`), die für *jede* HA-Installation funktioniert. Die Atrium-Funde (Actor-Modell, Dispatcher) bleiben wertvoller **Kontext**, werden aber **nicht als Abhängigkeit** übernommen — höchstens als **optionale, abhängigkeitsfreie Integrations-Schnittstelle** (das Produkt exponiert seine ACL-Entscheidungen sauber, sodass ein externer Governance-Layer wie Atriums Dispatcher sie *konsumieren kann*, ohne dass eines vom anderen abhängt). Voll-Foundation: `rbac_product_charter.md`.
- **Effort-Wirkung:** Actor-Modell + Dispatcher wiederverwenden spart Teile von R1/R4; dafür Integrations-Surface zu D19/D25/D27. Netto bleibt der Korridor (MVP ~30–45 / Produktion ~55–100), aber die Architektur ist klarer: **`atrium_acl` als RBAC-Modul, das in den vorhandenen Dispatcher einspeist.**

### Arbeitsweise (role-contract)
Claude↔Codex läuft über das etablierte Ping-Pong (`outputs/` + Michael als Kurier; ACCEPT/MODIFY/REJECT; Gates G0–G3). „Codex-Feedback einarbeiten" folgt genau diesem Protokoll.
