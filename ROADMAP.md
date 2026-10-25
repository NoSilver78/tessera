# Roadmap

Dieses Dokument beschreibt **wohin Tessera will**, **wo es gerade steht** und **was noch zu tun
ist**. Stand: **2026-10-25** (v0.9.4 — im HACS-Default-Store; HA-Linien 2026.7–2026.10 validiert).
Es ist bewusst ehrlich — auch über offene Flanken (siehe ganz unten).

## Vision

Home Assistant hat seit Jahren keine brauchbare rollenbasierte Zugriffskontrolle: drei feste
Systemgruppen, kein UI, ein Owner-Bypass. Tessera soll **die fehlende RBAC-Schicht** sein — ohne
Core-Fork, ohne Monkeypatch, ohne Zwang zu einem bestimmten Identity-Provider. Ein Administrator
beschreibt **Rollen × Bereiche × Aktionen** deklarativ; Tessera setzt das auf HAs **eigene**
Permission-Mechanik um.

## Architektur in Kürze

Tessera kombiniert das **NIST-RBAC-Rollenmodell** (INCITS 359) mit der
**ABAC-Funktionspunkt-Trennung** aus **NIST SP 800-162** (PAP/PDP/PEP):

```
Store (Source of Truth, PAP)
   → Compiler (Policy Decision Point, at-compile-time)
      → native HA-Gruppen-Policies (PolicyPermissions)
         → HAs check_entity (Policy Enforcement Point)
```

- **Stufen** (UI-Bezeichner in Klammern): `view` (**Read**) = lesen · `operate` (**Control**) =
  bedienen (echt durchgesetzt) · `change` = globales `is_admin` (nicht bereichs-scoped, keine
  Grant-Zelle im Panel).
- **Allow-only** — Policies *gewähren*, sie *verbieten* nicht (Spezialisierung statt Deny).
- **Pflege-Ebene Bereich × Rolle** als Primärfall (~90 %); der Compiler expandiert Bereiche zu den
  konkreten Entity-IDs.
- **Drei Modi:** `off` / `monitor` (read-only) / `enforce` (schreibt) — Default nicht-eingreifend.

## Phasen & Status

### ✅ Phase 0 — Machbarkeits-Spike *(abgeschlossen)*
Nachweis, dass der Auth-Store-Schreibpfad trägt: Schreiben persistiert, überlebt Neustart,
Cache-Invalidierung + Union/Restore funktionieren. Ergebnis: Neubau plausibel, Schreibpfad
machbar.

### ✅ Phase 1 — Core + Monitor *(funktionsfähig, auf `main`)*
- **Store** als Source of Truth (Rollen, Bereichszuordnungen, Grant-Matrix, Schema-validiert).
- **Compiler** Bereich → Entity-Expansion (auch area-lose Direkt-Entitäten).
- **Linter** für Policy-Konflikte/Lücken.
- **Config-Flow** + Options (Modus-Umschaltung) + **Matrix-Admin-Panel** in der Seitenleiste.
- **Monitor-Modus** — kompiliert eine read-only Vorschau, **ohne** HA zu verändern.
- **Produkt-Gate (D9, v2 „auth-scoped")** — klassifiziert installierte Custom-Components vor
  `enforce`. Nur Components, die den verwalteten Auth-Zustand mutieren können (oder nicht statisch
  analysierbar sind), blockieren — per **Ack**/Klassifikation freigebbar; generische Surfaces laufen
  per Default (Konflikt-Vermeidung, kein Malware-Sandbox — siehe [SECURITY.md](SECURITY.md)).

### ✅ Phase 2 — Enforce-Maschinerie *(gebaut, gegated, **verdrahtet** — auf `main`)*
Vollständig implementiert, jeweils durch ein adversariales Mehr-Agenten-Gate + Mutationsproben
geführt — und seit E3.5 (Phase 3) im Setup-Pfad verdrahtet:
- **Plan** — Gate-Sequenz (HA-Version → Compile → Produkt-Gate → Linter → Bindings), fail-closed.
- **Bindings** — No-Drop-Superset, Default-Rolle für leere Vereinigung, Promotion-Guard,
  Orphan-Erkennung; Owner/System-Konten unangetastet.
- **Write + Guards** — `tessera:<rolle>`-Gruppen schreiben + User rebinden, mit allow-only-Assertion
  am Choke-Point und **Lockout-Precheck vor jedem Write**.
- **Restore / Recovery / Journal** — unveränderlicher Pre-Install-Snapshot, Restore auf den
  Ursprungszustand, Two-Phase-Journal für Crash-Recovery.

### 🚧 Phase 3 — Verdrahtung & Validierung *(Verdrahtung erledigt, Praxis-Validierung offen)*

> Die Codes `E3.x` sind interne Schritt-Bezeichner unseres Bauprozesses (hier: die Verdrahtung der oben gebauten Teile).
- **E3.5 — Verdrahtung:** ✅ `mode=enforce` löst die Sequenz tatsächlich aus (compute → Snapshot →
  Journal → apply → clear; beim Start → Recovery-Entscheidung → ggf. Restore; jeder Fehler → fail-safe
  auf `monitor`).
- **Dev-E2E:** ⏳ echter Schreib-Zyklus gegen eine **separate Dev-Instanz** (nie Produktiv): enforce
  setzen → native Gruppen/Bindungen verifizieren → zurücknehmen → Restore verifizieren.
- **Soak:** über längere Zeit auf der Dev-Instanz laufen lassen.
- **Dogfood:** auf einer echten, eigenen Instanz betreiben — überlebt es ein HA-Update ohne
  Vorfall?

### ✅ Phase 4 — Release *(Default-Store erreicht)*
- **HACS-Custom-Repo** (kleiner, kuratierter Kreis) → Feedback → **HACS-Default-Store**: am
  **18.10.2026** gemerged ([hacs/default#8877](https://github.com/hacs/default/pull/8877)), seit
  v0.9.4 also direkt über HACS installierbar. Damit ist die Verteilung erledigt — die *Reife*
  (Soak, Dogfood) ist es nicht, siehe Phase 3 und „Offene Flanken".
- **Nicht** Home-Assistant-Core: die nötige Mutation des Auth-Stores über nicht-öffentliche APIs
  würde Core nie akzeptieren — HACS ist der bewusste, einzig sinnvolle Weg.
- Release-Engineering-Details: **[RELEASE_READINESS.md](RELEASE_READINESS.md)**.

## Was als Nächstes zu tun ist (konkret)

- [x] E3.5-Verdrahtung grün (CI + adversariales Gate) → gemergt.
- [x] HACS-Artefakte aktiviert (`hacs.json`, Validierungs-CI hassfest+HACS, `brand/`-Icon) — der
      HACS-Datei-Check ist `continue-on-error`, bis das Repo öffentlich ist.
- [x] Dev-E2E gegen die Dev-Instanz gefahren und protokolliert
      (`spike/reports/tessera-dev-e2e-report-2026-07-01.md`).
- [x] Erstes getaggtes Release + Public-Flip; `continue-on-error` am HACS-Job entfernt.
- [x] README/Doku-Feinschliff fürs öffentliche Repo (bilinguale Guides, Screenshots).
- [x] **Versions-Tracking vom Nachlauf in den Vorlauf gedreht** (nächstes Release): Contract-Tests + `mypy
      --strict` pro validierter Linie in der CI-Matrix, plus nightly gegen die HA-**Pre-Release**,
      und der ganze Weg Grant → Compiler → HAs `PolicyPermissions` als Contract-Test.
- [ ] **Soak-Phase + erste Dogfood-Instanz** — der größte offene Punkt: `enforce` ist gebaut,
      gegated, verdrahtet und dev-erprobt, aber nicht über Zeit in der Praxis bewiesen.
- [ ] `SECURITY.md`-Kanal + Private Vulnerability Reporting scharfschalten.
- [ ] Erste echte Community-Signale abwarten/einholen (Stand 25.10.2026: 0 Stars, 0 Forks,
      0 fremde Issues) — ohne fremde Setups fehlt die Breite, die der Soak braucht.

## Backlog / später

- **`by_group`-Pfad (Authentik/OIDC):** Rollen-Mitgliedschaft additiv aus IdP-Gruppen — derzeit
  **inert**, bis der Roh-Claim-Seitenkanal verlässlich nachgewiesen ist.
- **Klick-UI für die letzten Konfig-Lücken** (Audit v0.9.0, siehe GUIDE → *Konfigurationsreferenz*):
  (a) `is_admin`-Feld im „Add role"-Flow, (b) `tessera.set_entity_override`-Service + Panel-Board für
  Einzel-Entity-Rechte (heute nur `import`), (c) Nutzer→Rollen-Mitgliedschaft per Options-Flow/Panel
  (heute nur Service/`import`). Das Modell setzt alles durch — nur die Editier-UI fehlt.
- **Options-Flow für Floor-/Label-Grants** (heute Panel + Service; nur Area-Grants zusätzlich im Flow).
- **Mitigations-Ideen** für die dokumentierten Leak-Pfade (Template/Logbook/Assist).

## Offene Flanken (ehrlich)

Diese Punkte sind bewusst **nicht** gelöst und teils Stellen, an denen wir **Hilfe gut gebrauchen
können** (→ [CONTRIBUTING.md](CONTRIBUTING.md)):

1. **Private-API-Abhängigkeit** — der Auth-Store-Schreibpfad nutzt teils nicht-öffentliche HA-APIs.
   Größtes Dauer-Risiko: ein HA-Release kann sie brechen. Gegenmittel: Laufzeit-Guard auf die
   validierten Feature-Linien mit Fallback auf `monitor`, ein nachvollziehbares **Diff-Protokoll**
   pro Linie ([docs/MAINTENANCE.md](docs/MAINTENANCE.md)), Contract-Tests + `mypy --strict` pro
   Linie in CI und ein **nightly Lauf gegen die HA-Pre-Release**. Damit ist das Tracking vom
   Nachlauf in den Vorlauf gedreht — Dauer-Arbeit bleibt es trotzdem, und 2026.9 hat gezeigt, dass
   auch *angrenzende* APIs (Device-Registry, Schema-Bibliothek) mitbrechen können, nicht nur der
   Auth-Store. Beim Schema-Import ruht Tessera bewusst auf HAs `voluptuous`-Shim statt auf
   `probatio` — akzeptiertes Risiko mit benannten Auslösern, siehe
   [ADR 0006](decisions/0006-schema-library-compat-over-migration.md).
2. **Leak-Pfade** — `render_template`, Logbook/History und Assist können die Permission-Schicht
   teilweise umgehen (siehe README). Tessera dokumentiert das ehrlich, schließt es aber nicht.
3. **Enforce noch nicht in der Praxis bewiesen** — die Maschinerie ist gebaut, gegated und verdrahtet
   (schreibt bei `mode=enforce`), aber der echte End-to-End-Lauf + Soak + Dogfood stehen aus. Bis
   dahin: read-only `monitor` vertrauen.
4. **`change` ist global** — die Stufe `change` bildet HAs `is_admin` ab und ist nicht
   bereichs-scoped (HA-Limit, kein Tessera-Bug).
5. **Single-Writer-Annahme** beim State/Journal — heute durch einen Lock gedeckt (ein Apply-Lauf pro
   Instanz zur Zeit); bei zukünftiger Parallelität erneut zu prüfen.
