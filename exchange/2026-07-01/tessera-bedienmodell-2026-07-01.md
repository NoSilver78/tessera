# Tessera — Bedien-/UX-Modell (Entwurf zur Validierung)

**Von:** Claude (Architektur) · **Datum:** 2026-07-01 · **Status:** Entwurf — Codex-Agentensystem-Validierung läuft.
**Owner-Entscheidungen (2026-07-01):** (1) **Authentik parallel** zu lokal (nicht zurückgestellt — `by_group` soll funktional werden; s. §7-Risiko Owner-Aussperrung); (2) **erst Codex-Validierung**, dann bauen; (3) **Wizard: ja, schlank, zuletzt**. Verbleibende offene Fragen (§6): Deny-Log-Quelle, Membership-/Rollen-UI-Ort, Preset-Personas, Authentik-Matching.
**Quelle:** Multi-Agenten-Workflow (5 Web-Recherche-Linsen → Anforderungen → 3 UI-Entwürfe → adversariale Kritik → Synthese; 11 Agenten). Von Claude gegen `main` code-verifiziert.

---

## 0) Verifizierte Realität (tragende Behauptungen, am Code geprüft)
- **Deny-Log fehlt:** `monitor.py` liefert nur Aggregat (`read_total`/`control_total` + per-Rolle-Zähler) — **kein per-Event „would-block"-Log**. „Observe-before-enforce" zeigt heute nur kompilierte **Absicht**, nicht die **Auswirkung** auf echte Nutzer. ✔ verifiziert.
- **`by_group` ist inert:** `compiler.py` `BY_GROUP_PROJECTION_MODE="v1-inert"` (ADR 0005; `concept.md`:427, `spec-enforce.md`). Authentik-Gruppen werden geparst/validiert/persistiert, aber **nicht** in native Policies/Bindings projiziert. **v1-Enforce trägt ausschließlich `by_user`.** ✔ verifiziert — und **dokumentierte Entscheidung**, keine „versteckte Schuld".
- **D9-Ack-Services existieren** (`tessera.acknowledge_component`/`revoke_component_ack`, admin-gated, seit PR #36 + dev-E2E-bewiesen) — **nur die UI fehlt.** (Der Recherche-Anforderungstext war hier veraltet.)
- **Enforce-Preflight existiert:** `compute_enforce_plan` liefert bereits D9-Gate + Cross-Role-Linter + Auth-Version-Guard + Owner-Survives-Lockout-Guard + Allow-only-Assertion + fail-safe-to-monitor. Das UI muss es nur **sichtbar rendern**, nicht neu bauen.

**Wichtigste Einordnung:** Die UI-Ansatz-Wahl ist **zweitrangig** gegenüber zwei Backend-Projekten (Effective-Access-Read-Layer + optional per-Event-Deny-Log). Ohne sie ist ein „grünes" Vorschau-UI eine **Attrappe**, die zum blinden enforce-Flip verleitet.

---

## 1) Empfohlener Ansatz: **C-modifiziert** — Panel-Stepper-Wizard + Betriebs-Panel; Options-Flow nur für Skalare/Fallback
Drei Surfaces sauber nach **Form** trennen (KNX/MQTT-Vorbild):
| Surface | Aufgaben | HA-Mechanismus |
|---|---|---|
| **Options-Flow** (idiomatisch, geschenkt) | globaler Skalar **MODE** (off/monitor/enforce); linearer Rollen-CRUD-Fallback | `SchemaOptionsFlowHandler`, Auto-Reload |
| **Config-Subentry _oder_ Panel-Sektion** (Owner-Entscheidung, s. Frage 2/3) | Rollen-Liste, **User→Rolle** (`by_user`), Gruppe→Rolle (`by_group`) | Subentry „Add member/role" _oder_ Panel-Tab |
| **Custom-Panel** (Pflicht — plattformseitig nur hier möglich) | **Area×Rolle-Matrix**, **2-Richtungs-Effective-Access**, Enforce-Preflight-Checkliste+Diff, D9-Acks, Authentik-Mapping | Lit + `ha-data-table`/`ha-form`, admin-only, mit Integration gebündelt |

**Warum nicht A (nur Options-Flow):** Die zwei MUST-Haves **Area×Rolle-Matrix** und **2-Richtungs-Effective-Access** sind in HA-Options-Flows **plattformseitig unmöglich** (keine Tabellen/Live-Matrix/Diff). A bleibt nur als schmaler Skalar-/Fallback-Pfad *innerhalb* C.
**Warum nicht B (Panel-Big-Bang):** Gleiche Panel-Bauleistung wie C, aber als 6-View-App auf einmal statt in Wert-Reihenfolge. C liefert nach jedem Schritt nutzbaren Wert; die Frontend-Drift-Fläche wächst kontrolliert. **Ehrlichkeit: C ist nicht *billiger* als B, nur besser *sequenziert*.**

## 2) Bedienung je Kern-Aufgabe (Store bleibt einzige Source-of-Truth)
- **Rollen (CRUD):** Persona-Presets als Seed (Household/Guest/Kids/Cleaner/Kiosk/Power-User) gegen Blank-Slate + Rollen-Explosion. **Rolle ist immer Persona, nie per-Area** („kein Kitchen-Guest"; Area ist Grant-Dimension *innerhalb* der Rolle = parametrische-Rolle-Vorteil).
- **Grants (Area×Rolle, allow-only):** bestehende **Tri-State-Matrix** (`tessera/matrix/set_grant`, none→read→control) bleibt Dauerpfad; erweitert um **Floor-Gruppierung** + Role-Detail als Primär-Edit, Vollmatrix als Audit-Lens. `control` impliziert `read`; **allow-only bleibt unangetastet** (kein Deny/Override).
- **Membership lokal (`by_user`) — LÜCKE 1, höchster Sofort-Hebel, kein Backend-Blocker:** neuer Writer `tessera/membership/set` (`require_admin`) + „Mitglieder"-Fläche (Person-Picker × Rolle). Schema trägt `by_user` schon, `remove_role` räumt schon auf — es fehlt nur der **Schreibpfad**. `by_user` = IdP-unabhängiger Anker (Bootstrap, Owner-Zugang, IdP-Ausfall-Resilienz).
- **Authentik (`by_group`) — LÜCKE 2, ZULETZT:** „SSO/Authentik"-Reiter via **Progressive Disclosure** (nicht co-equal — sonst Keycloak-groups-vs-roles-Falle). **Erst aktivieren, nachdem der Compiler `by_group` projiziert (ADR-0005-Aufhebung) UND der Owner-Lockout-Guard gegen leeren Claim live verifiziert ist.**
- **Modus/Enforce:** MODE bleibt Options-Flow-Skalar; der angst-besetzte monitor→enforce-Flip ist ein **gerahmter Panel-Schritt**: rendert `compute_enforce_plan` als PASS/BLOCK-Checkliste (D9/Linter/Auth-Version/Owner-survives/Allow-only) + **Effective-Diff** + Deny-Log als Pflichtlektüre, bevor der Flip möglich ist.
- **Review/Audit (wer-kann-was):** neue Panel-Sektion aus `tessera/effective/get` (**kompilierter** Zustand, nicht nur authored). Zwei Richtungen (per-User forward / per-Area reverse), Union sichtbar mit Herkunft (via Rolle X aus by_user/by_group). **Anomalie-first** (sensible Areas, Rolle-ohne-User, User-ohne-Rolle) mit HA-Klarnamen + Inline-Fix.
- **D9-Acks:** Services existieren → nur Panel-Sektion „D9-Freigaben" (Domain/Version/Content-Hash, Ack/Revoke, Progressive Disclosure im Mode&Safety-Kontext).

## 3) Wizard-Entscheidung: **sinnvoll-optional, eng begrenzt — als Panel-Stepper, NICHT Options-Flow**
Ja, aber nur für **drei Momente** (nie Dauer-Interface): (1) **First-Run/Empty-State** (Presets → Owner/Haushalt zu Rollen → Effective-Access sichten → in monitor bleiben; jeder Schritt schreibt echte Store-Objekte, re-runbar, kein Dead-End); (2) **monitor→enforce-Ramp** (Deny-Log+Gates+Diff → bewusster Flip); (3) **einmalige Authentik-Verdrahtung**. **Alltag läuft NIE durch den Wizard** (Matrix-Klick + Membership-Editor direkt), sonst Bevormundung des versierten Owners. Panel-Stepper statt Options-Flow, weil der 2D-Grant-Schritt nie sequenzialisiert werden darf (NNG-Anti-Muster) — im Panel ist er ein Tab-Wechsel.

## 4) Authentik-Anbindung: UX + Präzedenz
- **UX:** einmaliger 3–4-Schritt-Verbindungs-Wizard (Claim-Name Default `groups`, **Slug-Matching empfohlen**; **Live-Test** „welche Gruppen sehe ich?" — deckt die belegte #1-Fehlerquelle „groups nicht im id_token" auf) → führt IN die Panel-Mapping-Matrix. Dauerhaft: Gruppe→Rolle als 2. Panel-Reiter.
- **Voraussetzung:** `groups` müssen im id_token landen; Custom-Scope-Expression **`User.groups`**, NICHT das deprecatete `user.ak_groups`.
- **Präzedenz (hart):** **ADDITIV/Union** (effektive Rollen = `by_user` ∪ `by_group`), **nie authoritative/replace-on-login als Default**. Leerer/kaputter Claim entzieht **niemandem** etwas (v.a. nicht dem Owner). **Getrennte Store-Keys** — by_group-Sync fasst `by_user` NIE an. Rolle = stabile Abstraktion, Authentik = reiner Gruppen-Lieferant (kein roles-claim-Zwang).

## 5) Umsetzungs-Reihenfolge (damit der Soak vollständig wird)
1. **Backend zuerst (wahrer kritischer Pfad):** (a) **Effective-Access-Read-Layer** aus `compiler.py` (forward+reverse; **ohne Traffic-Hook berechenbar** — Claude-Präzisierung); (b) **per-Event-Deny-Log** in `monitor.py` (die härtere Kür; Quelle/Retention = Frage 1).
2. **LÜCKE 1 sofort:** `by_user`-Membership-Writer + Fläche. Höchster Hebel, plattform-sauber, kein Blocker — macht den **Soak überhaupt mit echten Personen befüllbar**.
3. **Panel inkrementell (C):** Membership → Effective-Access → Mode&Safety-Preflight (rendert fertiges `compute_enforce_plan`) → D9-Ack-Sektion. Parallel Migration auf `ha-data-table`, `hass`-Render-Gating.
4. **First-Run-Wizard** als Panel-Stepper (dünn) obendrauf.
5. **`by_group` + Authentik-Wizard ZULETZT** — erst nach Compiler-De-Inertness + Owner-Guard-Verifikation gegen leeren Claim.

## 6) Offene Owner-Entscheidungen (Konsequenzen)
1. **Deny-Log-Quelle/Retention:** synthetisch aus Enforce-Resolver im monitor (schneller, „hypothetisch", reicht als Gate) **vs.** realen Traffic mitschneiden (aussagekräftiger, Hook+Retention+DSGVO).
2. **Membership-UI-Ort:** Config-Subentry (idiomatisch, geschenkte Reconfigure/Delete-UI, aber sequentiell/zersplittert) **vs.** Panel-Sektion (einheitlich, mehr Eigenbau).
3. **Rollen-CRUD:** Subentry (gratis Delete/Reconfigure) **vs.** Panel (Einheitlich + Persona-Seeds). *Empfehlung: konsistent — wenn Membership ins Panel, dann Rollen auch.*
4. **Preset-Personas:** welche genau + Default-Grants? **Blockiert den Wizard-Inhalt**; braucht Abgleich mit realem Pilzbuche-8-Bestand (falsche Defaults = Über-Berechtigung oder Reib-Frust).
5. **Authentik-Matching:** Slug (robust bei Umbenennung, empfohlen) vs. Name (lesbar, bricht bei Umbenennung).
6. **`by_group`-Zeitpunkt:** Mapping-UI jetzt (erfasst totes Datum, „warum passiert nichts?") vs. erst nach Compiler-Aktivierung. *Empfehlung: spät.*

## 7) Risiken/Unsicherheiten (ehrlich)
- **Größtes Risiko:** Deny-Log/Effective-Access ist der echte kritische Pfad, nicht die UI. UI vor Backend = Owner wird auf ein nichtssagendes grünes Signal trainiert → **blinder enforce-Flip = Outage-Falle.**
- **`by_group` ist unterschätzte Integrationsarbeit** (OIDC-Token lesen, Compiler-Projektion, Owner-Guard gegen leeren Claim) — der Guard ist im inerten Zustand **ungetestet**; scharfschalten vor Verifikation = Owner-Aussperr-Risiko.
- **Frontend-Drift:** `ha-data-table`/`hass-tabs-subpage-data-table` sind keine stabil garantierte HA-API → Wartungslast; jede neue WS-Command = zusätzliche `@require_admin`/Redaction-Prüfstelle (Leak-Regressionsfläche).
- **Wizard-Scope-Creep:** ohne harte Disziplin (nur Erststart + Enforce-Ramp + Authentik) bevormundet er den Owner.

---

## 8) Nachtrag: Abgleich mit dem „authentik + HA RBAC"-Übergabepaket (2026-07-01)
Das Paket ist der **ursprüngliche Brief** (vor/parallel zu Tessera). **~70 % sind bereits durch Tessera + dieses Modell beantwortet:** OIDC=Login-nicht-Sync + Gruppen-Richtung (authentik→OIDC→HA), Mapping-Schicht Gruppe→Rolle, Custom-Integration statt Core-Patch/Proxy (native HA-Gruppen-Permissions), Owner-Fallback/„Bewohner nie Owner"/„mit echten Testusern testen", read/control, Slug-Matching, und die Leak-Pfade (WS/REST/History/Logbook/Scripts/Scenes/Helpers/Token/Mobile — in `SECURITY.md` als by-design dokumentiert). **Neue/schärfende Punkte, die ins Modell einfließen:**

1. **★ MEHRPARTEIEN-ISOLATION (materiell — reframt die Risiko-Posture).** Der Paket-Use-Case ist **echter Mehr-Wohneinheiten-Betrieb** (EG/UG/DG-Bewohner, die sich gegenseitig NICHT sehen dürfen). Das ist **stärker** als „Gast/Kind im Haushalt einschränken". Tesseras dokumentierte Leak-Pfade (Templates/Assist/manche indirekte Read-Pfade) sind für ein Haushalts-RBAC vertretbar, für **echte Tenant-Isolation aber potenziell ein Sicherheits-Gap**. **Offene Kernfrage an Owner (blockiert die Risiko-Bewertung): Mehrparteien-Isolation ODER Ein-Haushalt-fein?**
2. **`tenant_scope` / Labels statt nur Areas.** Areas sind keine stabile Sicherheitsgrenze (Entity ohne Area, Device falsche Area). Explizites Label `tenant:<unit>` ist robuster/auditierbar. **Deckt sich mit Tesseras Roadmap** (`spec-enforce.md`: floor/label/category-Selektor-Ausbau, v1=area+entity+domain) — die Mehrparteien-Linse schärft die Priorität von **Label-Grants**.
3. **Deny-Vorrang (Paket) vs. allow-only (Tessera).** allow-only liefert „deny by default" gratis; „Bereich X erlauben AUSSER Kameras" ist nur via `entity_overrides` ausdrückbar, nicht elegant. Design-Diskussion, kein Blocker — allow-only bleibt der Usability/Sicherheits-Moat.
4. **Konkrete OIDC-Integration.** Paket empfiehlt `hass-oidc-auth` (christiaangoossens); Tessera-Kontext (`concept.md`:427) nennt `auth_oidc v1.1.1`, das „`groups` nur binär admin/user" durchreicht. **Für den Authentik-Parallel-Track ZWINGEND zu klären:** welche OIDC-Integration liefert den **rohen `groups`-Claim** an HA? Ohne den bekommt `by_group` keine echten Gruppen.
5. Service-Calls ohne Target / domainweite Calls / Szenen-Skripte-Automationen-als-Steuerkanal: Tessera delegiert an HAs **native** Permission-Prüfung (check_entity); die Vollständigkeit dieser nativen Prüfung für target-lose/indirekte Calls ist der **Härtetest der Mehrparteien-Tauglichkeit** und gehört in die Testmatrix.
