# Tessera

> Rollenbasierte Zugriffskontrolle (RBAC) für Home Assistant — *Read / Control* × **Rolle** × **Bereich**.

**Deutsch** · [English](README.md)

Tessera ist ein eigenständiges Berechtigungssystem für Home Assistant. Es schließt eine seit
Jahren offene Lücke: HA kennt nur drei feste Systemgruppen, kein UI für feingranulare Rechte und
einen Owner-Bypass. Tessera kompiliert deklarative Richtlinien (**Rolle × Bereich × Aktion**) zu
**nativen** HA-`PolicyPermissions` und schreibt sie — **im `enforce`-Modus** — in den
Home-Assistant-Auth-Store. **Kein Monkeypatch, kein Core-Fork.**

> ⚠️ **Sicherheitskritische Integration.** Tessera verändert, wer in deiner Home-Assistant-Instanz
> was sehen und tun darf. Im `enforce`-Modus **schreibt Tessera aktiv** in den HA-Auth-Store. Lies das
> **[Sicherheitsmodell](#sicherheitsmodell-ehrlich)** unten, bevor du `enforce` aktivierst — und beachte
> den **[Projektstatus](#projektstatus)**: Durchsetzung ist gebaut, verdrahtet und in einer **Live-Instanz
> nachgewiesen** (Dev-E2E + laufender Betrieb); breite Erprobung über viele Setups steht noch aus.
> **Beginne trotzdem mit `monitor`**, sichte die berechneten Verdicts und wechsle erst dann bewusst zu `enforce`.

## Was Tessera tut

- **Deklarative Policies** — Rollen × Bereiche × Aktionen. Pro Bereich × Rolle vergibst du im Panel
  **Read** (ansehen) und/oder **Control** (bedienen); eine dritte Stufe **change** entspricht
  HAs globalem `is_admin` (siehe [Sicherheitsmodell](#sicherheitsmodell-ehrlich)).
- **Compiler** — übersetzt Policies in native HA-`PolicyPermissions` (expandiert Bereiche, Etagen und
  Labels zu Entity-IDs, inkl. der area-losen Direkt-Entitäten, die HAs `area_ids` allein verfehlt).
- **Linter** — prüft Policies vor dem Anwenden auf Konflikte und Lücken.
- **Dual-Mode-Mitgliedschaft** — lokale Rollen (`by_user`, Baseline, ohne Fremdabhängigkeit) **oder**
  additiv ein Mapping aus einem externen IdP (`by_group`, z. B. Authentik/OIDC — optional).
- **Admin-Panel** „Tessera" in der HA-Seitenleiste (nur Administratoren), mit Umschalter
  `Bereiche ↔ Labels` zwischen zwei Boards: einem **Area-Board** (je Rolle die Herkunftsspalten
  **Floor | Area**, klickbar zum Setzen von Grants, Doppelvergabe-Markierung, aufklappbar bis auf
  Entity-Ebene) und einem **Labels-Board** — Labels als Zeilen mit editierbarer Zelle je Rolle,
  aufklappbar bis zu den Entitäten, die ein Label auflöst.
- **Drei Betriebsmodi** mit nicht-eingreifendem Default — siehe unten.

## Wie sich Tessera zu anderen Ansätzen verhält

Tessera ist nicht der erste Versuch, Home Assistant nutzerbezogene Rechte zu geben — und das ist
eine gute Nachricht: Es zeigt, dass der Bedarf real ist. Im HACS-Store gibt es zwei etablierte
Alternativen, und Tessera geht bewusst einen anderen Weg. Der ehrliche Vergleich:

| | **Durchsetzungs-Mechanismus** | **Scoping-Modell** | **Labels** |
|---|---|---|---|
| **Tessera** | **Native** HA-`PolicyPermissions`, geschrieben in den Auth-Store — **kein Monkeypatch, kein Core-Fork**; jeder Schreibvorgang ist gegated und fällt fail-safe auf `monitor` zurück | **Bereich / Etage als erstklassige Achse** × Rolle × *view / operate / change* | **Lebende Dimension** — Label × Rolle; später passende Entitäten werden beim nächsten Compile neu aufgelöst |
| [`SamAthanas/user-rbac`](https://github.com/SamAthanas/user-rbac) | Middleware, die **Core-Service-Calls abfängt / patcht** (das eigene README weist darauf hin, dass dies bei HA-Updates brechen kann) | Rolle × Domain / Entity, Aktions-Ebene | — |
| [`Darkdragon14/ha-access-control-manager`](https://github.com/Darkdragon14/ha-access-control-manager) | Native HA-Gruppen-Permissions | Gruppe × Entity, read / write | Einmal-Bulk-Helfer (laut dessen README erben später hinzugefügte Entitäten mit demselben Label **nicht** automatisch) |

**Warum du Tessera wählen könntest:**

- **Es patcht den Home-Assistant-Core nicht.** Rechte werden in HAs *native* Gruppen-
  `PolicyPermissions` kompiliert. Deaktivierst du Tessera, kehrt HA in den Auslieferungszustand
  zurück — nichts zurückzudrehen, und keine Abfang-Schicht, die ein Core-Update brechen kann.
- **Bereiche und Etagen sind die primäre Achse**, kein nachträglicher Aufsatz über Entitäten —
  Grants lesen sich so, wie du über dein Haus denkst.
- **Labels bleiben lebendig.** Ein Label-Grant wird bei jedem Compile neu aufgelöst; eine Entität,
  die du nächsten Monat taggst, ist abgedeckt, ohne den Grant erneut anzufassen.
- **Nicht-eingreifend per Default.** `off → monitor → enforce`: Du *beobachtest* die berechneten
  Verdikte, bevor je etwas geschrieben wird — hinter einer fail-closed Gate-Sequenz mit
  unveränderlichem Snapshot und automatischer Wiederherstellung.

Wenn du heute simples Aktions-Blocken willst und mit einer Abfang-Schicht leben kannst, ist
`user-rbac` populär und ausgereift. Wenn du HA-Gruppen ohnehin von Hand pflegst, passt
`ha-access-control-manager` zu dieser Denkweise. Tessera ist für dich, wenn du **bereichszentrische,
deklarative Rechte willst, die in native HA-Permissions kompiliert werden — mit einem sicheren,
monitor-first Rollout.**

## Projektstatus

**Veröffentlicht (v0.9.0) · `enforce` dev-erprobt und in einer Live-Instanz aktiv · breite Multi-Setup-Erprobung erwünscht.**

| Baustein | Stand |
|---|---|
| **Core** (Store · Compiler · Linter · Schema · Config-Flow) | ✅ funktionsfähig |
| **Monitor** (read-only Vorschau + Matrix-Panel) | ✅ funktionsfähig |
| **Enforce-Maschinerie** (Plan · Bindings · Write+Guards · Restore/Recovery) | ✅ gebaut, adversarial gegated |
| **Enforce-Verdrahtung** (`mode=enforce` schaltet scharf) | ✅ verdrahtet — `mode=enforce` schreibt nativen Auth; Fehler → fail-safe auf `monitor` |
| **Area-Board-Panel** (Floor\|Area-Herkunft · Doppel-Markierung · Entity-Aufklappen · Area+Floor editierbar) | ✅ funktionsfähig |
| **End-to-End gegen Dev-Instanz + Live-Betrieb** | ✅ Dev-E2E durchlaufen + Live-`enforce` verifiziert; **breiter Multi-Setup-Soak erwünscht** |
| **HACS-Aktivierung** (`hacs.json` · HACS+hassfest-CI · Brand-Icon) | ✅ erledigt |
| **HACS** (public · getaggte Releases) | ✅ v0.2.0–v0.9.0 · Default-Store-Einreichung eingereicht (in Review) |

Die ganze Geschichte — Vision, Phasen, was als Nächstes kommt und **wo wir Unterstützung gut
gebrauchen können** — steht in der **[ROADMAP](ROADMAP.md)** und in **[CONTRIBUTING](CONTRIBUTING.md)**.

## Ausführliche Anleitung

Vollständige **Einrichtung & Nutzung** — Installation, Betriebsmodi, Rollen/Grants/Mitgliedschaften,
Area-Board-Panel, `enforce` mit Preflight, **„was zu beachten ist"** (Versions-Guard/HA-Updates!),
Troubleshooting und FAQ — mit Screenshots:

**📖 [Deutsch](docs/GUIDE.de.md) · [English](docs/GUIDE.md)**

## Installation (HACS — Custom Repository)

> Tessera ist als **HACS Custom Repository** installierbar — es gibt getaggte Releases (aktuell **v0.9.1**).
> Die Aufnahme in den **HACS-Default-Store** ist eingereicht (in Review); bis dahin über „Custom repositories":

1. HACS öffnen → Drei-Punkte-Menü oben rechts → **Custom repositories**.
2. URL: `https://github.com/NoSilver78/tessera` · Kategorie: **Integration** → **ADD**.
3. Tessera in der HACS-Liste auswählen und herunterladen.
4. **Home Assistant neu starten.**
5. **Einstellungen → Geräte & Dienste → Integration hinzufügen → Tessera**.

**Getestete HA-Linie:** Home Assistant **2026.7.x** (validiert auf **2026.7.1**; siehe
*[Version-Guard](#version-guard-private-ha-apis)*). Innerhalb dieser Feature-Linie wird jedes
Patch-Release akzeptiert; auf einem **anderen** Monats-Release blockiert der Laufzeit-Guard den
`enforce`-Schreibpfad und hält Tessera im read-only `monitor`-Zustand.

## Sicherheitsmodell (ehrlich)

Tessera kennt drei Betriebsmodi. **Der Default ist nicht-eingreifend.**

| Modus | Wirkung |
|---|---|
| `off` | Tessera tut nichts. |
| `monitor` | Tessera **berechnet** Permissions und zeigt Abweichungen (Panel + Logs), **schreibt aber NICHT** in den Auth-Store. Sicher zum Einfahren. |
| `enforce` | Tessera **schreibt** die kompilierten Permissions aktiv in den HA-Auth-Store (native Gruppen-`PolicyPermissions` + Rebind der `group_ids`) und greift real in Zugriffe ein. |

> **Aktueller Stand:** `enforce` ist verdrahtet und **schreibt** beim Setzen von `mode=enforce` nativen
> Auth-Zustand — nach einer fail-closed Gate-Sequenz (HA-Version → Compile →
> [D9-Vorprüfung](docs/GUIDE.de.md#das-d9-gate) → Linter → Lockout-Precheck → unveränderlicher
> Snapshot/Journal → Apply). **Jeder Fehler in dieser Kette fällt sicher auf `monitor` zurück**
> (kein halb-scharfer Zustand); ein abgebrochener Lauf wird beim Start aus dem Pre-Install-Snapshot
> wiederhergestellt. Was noch **aussteht**, ist der breite Praxis-Nachweis (Soak + Dogfood über viele
> Setups, siehe [ROADMAP](ROADMAP.md)). Beginne deshalb mit `monitor`, prüfe die berechneten Verdicts,
> und wechsle erst dann bewusst zu `enforce`.

### Allow-only-Modell
Tessera vergibt Berechtigungen **additiv (allow-only)**: Eine Policy *gewährt* Zugriff; nicht
gewährter Zugriff bleibt verwehrt. Tessera setzt **keine** Deny-Regeln und hebelt **keine**
HA-eigenen Admin-Rechte aus. Owner und systemerzeugte Konten werden nie verändert.

### Dokumentierte Leak-Pfade (bekannte Grenzen)
HA-Permissions wirken **nicht** auf jeder Oberfläche identisch. Tessera kann diese HA-internen
Pfade **nicht** schließen — sie sind hier ehrlich dokumentiert:

- **`render_template` / Template-Sensoren** — Templates können Zustände von Entitäten lesen, auf die
  ein Benutzer per UI keinen Zugriff hat; Werte können indirekt durchsickern.
- **Logbook / History** — Verlaufsansichten können Ereignisse zu eingeschränkten Entitäten
  offenlegen, je nach HA-Version und Konfiguration.
- **Assist / Conversation** — Sprach-/Konversations-Agenten können Zustände abfragen oder Aktionen
  auslösen, die die Permission-Schicht teilweise umgehen.

> Tessera ist **keine** vollständige Daten-Isolation. Sind diese Pfade für dich relevant, ergänze
> HA-seitige Maßnahmen (Entitäten aus Assist ausschließen, Template-Exposition begrenzen).

### Version-Guard (private HA-APIs)
Tessera schreibt teils über **private/undokumentierte HA-Auth-APIs**, für die Home Assistant **keine**
Stabilitätsgarantie gibt — sie können zwischen Releases brechen. Schutz:

- **Aktiver Schutz (Laufzeit-Guard):** Der Auth-Schreibpfad prüft im Code auf die validierte HA-
  **Feature-Linie** (`SUPPORTED_HA_AUTH_FEATURE`, derzeit **2026.7**; validiert auf
  `SUPPORTED_HA_AUTH_VERSION` = **2026.7.1**). HA liefert Auth-Store-Breaking-Changes nur in der
  Monats-Feature-Linie aus, daher wird jedes **Patch** darin (2026.7.x) akzeptiert, während ein
  **anderes Monats-Release** den Schreibpfad **fail-closed** lässt und `enforce` auf den read-only
  `monitor`-Zustand zurückfällt — **kein** nativer Write. **Jedes HA-Monats-Update pausiert `enforce`
  also sicher**, bis eine Tessera-Version die neue Linie verifiziert (Details:
  [Anleitung → Was zu beachten ist](docs/GUIDE.de.md#was-zu-beachten-ist)).
- Ein zusätzlicher `hacs.json`-Pin der HA-Mindestversion ist **bewusst noch nicht** gesetzt (die
  HACS-Validierung lehnte den Wert als künftiges Minimum ab); die eigentliche Absicherung ist und
  bleibt der Laufzeit-Guard oben.
- Bricht eine interne API, wird die getestete Version angehoben und eine neue Version veröffentlicht.

Mehr dazu: **[docs/MAINTENANCE.md](docs/MAINTENANCE.md)**.

## Datenschutz

Tessera verarbeitet **ausschließlich lokal** Account-/Rollen-/Bereichszuordnungen (HA-Benutzer,
Rollen, Bereichszuweisungen — personenbezogene Daten i. S. d. DSGVO). **Keine Cloud, keine
Telemetrie.** Persistenz nur lokal (HA-Auth-Store + Tesseras eigener Store).

## Mitwirken

Tessera ist bewusst offen für Beitragende — besonders **Tests auf vielfältigen Multi-User-Setups**,
**HA-Versions-Kompatibilität** und **Feedback zum RBAC-Modell**. Wo genau Hilfe gebraucht wird, steht
in **[CONTRIBUTING.md](CONTRIBUTING.md)** (Abschnitt *Help wanted*).

## Sicherheitslücken melden

Bitte **nicht** öffentlich als Issue. Nutze GitHub **Private Vulnerability Reporting** (Tab *Security*
des Repos) — Details in **[SECURITY.md](SECURITY.md)**.

## Entwicklung (transparent)

Tessera wird in einem ungewöhnlichen, bewusst dokumentierten Modell gebaut: **Claude** (Architektur,
Gate, Audit), **Codex** (Implementierung) und Michael (Eigentümer/Orchestrierung). Der Sinn ist
**Sicherheit durch Mehraugen-Prinzip**: jeder Auth-Schreibpfad durchläuft vor dem Merge ein
**adversariales Mehr-Agenten-Gate** (mehrere unabhängige, skeptische Reviewer) plus
**Mutationsproben** (Tests werden gezielt gebrochen, um zu beweisen, dass sie den Regress fangen).
Der Prozess ist offen einsehbar: [`CONTRACT.md`](CONTRACT.md), [`CLAUDE_WORKFLOW.md`](CLAUDE_WORKFLOW.md),
die Übergaben in [`exchange/`](exchange/) und die Gate-Reviews in [`reports/`](reports/).

## Lizenz

[MIT](LICENSE) © 2026 Michael Scholz
