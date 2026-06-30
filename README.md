# Tessera

> Rollenbasierte Zugriffskontrolle (RBAC) für Home Assistant — *Read / Control* × **Rolle** × **Bereich**.

Tessera ist ein eigenständiges Berechtigungssystem für Home Assistant. Es schließt eine seit
Jahren offene Lücke: HA kennt nur drei feste Systemgruppen, kein UI für feingranulare Rechte und
einen Owner-Bypass. Tessera kompiliert deklarative Richtlinien (**Rolle × Bereich × Aktion**) zu
**nativen** HA-`PolicyPermissions` und schreibt sie — **im `enforce`-Modus** — in den
Home-Assistant-Auth-Store. **Kein Monkeypatch, kein Core-Fork.**

> ⚠️ **Sicherheitskritische Integration.** Tessera verändert, wer in deiner Home-Assistant-Instanz
> was sehen und tun darf. Im `enforce`-Modus **schreibt Tessera aktiv** in den HA-Auth-Store. Lies das
> **[Sicherheitsmodell](#sicherheitsmodell-ehrlich)** unten, bevor du `enforce` aktivierst — und beachte
> den **[Projektstatus](#projektstatus)**: Durchsetzung ist gebaut und verdrahtet, aber noch nicht in
> der Praxis (End-to-End/Soak/Dogfood) bewiesen. Beginne mit `monitor`.

## Was Tessera tut

- **Deklarative Policies** — Rollen × Bereiche × Aktionen. Pro Bereich × Rolle vergibst du im Panel
  **Read** (ansehen) und/oder **Control** (bedienen); eine dritte Stufe **change** entspricht
  HAs globalem `is_admin` (siehe [Sicherheitsmodell](#sicherheitsmodell-ehrlich)).
- **Compiler** — übersetzt Policies in native HA-`PolicyPermissions` (expandiert Bereiche zu
  Entity-IDs, inkl. der area-losen Direkt-Entitäten, die HAs `area_ids` allein verfehlt).
- **Linter** — prüft Policies vor dem Anwenden auf Konflikte und Lücken.
- **Dual-Mode-Mitgliedschaft** — lokale Rollen (`by_user`, Baseline, ohne Fremdabhängigkeit) **oder**
  additiv ein Mapping aus einem externen IdP (`by_group`, z. B. Authentik/OIDC — optional).
- **Admin-Panel** „Tessera" in der HA-Seitenleiste (nur Administratoren).
- **Drei Betriebsmodi** mit nicht-eingreifendem Default — siehe unten.

## Projektstatus

**Aktiver Aufbau · noch kein Release · noch nicht für den Produktiveinsatz freigegeben.**

| Baustein | Stand |
|---|---|
| **Core** (Store · Compiler · Linter · Schema · Config-Flow) | ✅ funktionsfähig |
| **Monitor** (read-only Vorschau + Matrix-Panel) | ✅ funktionsfähig |
| **Enforce-Maschinerie** (Plan · Bindings · Write+Guards · Restore/Recovery) | ✅ gebaut, adversarial gegated |
| **Enforce-Verdrahtung** (`mode=enforce` schaltet scharf) | ✅ verdrahtet (E3.5) — `mode=enforce` schreibt nativen Auth; Fehler → fail-safe auf `monitor` |
| **Echter End-to-End-Test gegen eine Dev-Instanz + Soak** | ⏳ ausstehend (vor Praxiseinsatz) |
| **HACS-Aktivierung** (`hacs.json` · HACS+hassfest-CI · Brand-Icon) | ✅ erledigt (Datei-Check braucht öffentliches Repo) |
| **HACS-Release** (getaggtes Release + Public-Flip) | ⏳ ausstehend |

Die ganze Geschichte — Vision, Phasen, was als Nächstes kommt und **wo wir Unterstützung gut
gebrauchen können** — steht in der **[ROADMAP](ROADMAP.md)** und in **[CONTRIBUTING](CONTRIBUTING.md)**.

## Installation (HACS — Custom Repository)

> Tessera ist (noch) **nicht** im HACS-Default-Store, und es gibt **noch kein getaggtes Release**.
> Sobald das erste Release veröffentlicht ist, läuft die Installation so:

1. HACS öffnen → Drei-Punkte-Menü oben rechts → **Custom repositories**.
2. URL: `https://github.com/NoSilver78/tessera` · Kategorie: **Integration** → **ADD**.
3. Tessera in der HACS-Liste auswählen und herunterladen.
4. **Home Assistant neu starten.**
5. **Einstellungen → Geräte & Dienste → Integration hinzufügen → Tessera**.

**Getestete HA-Version:** Home Assistant **2026.6.4** (siehe *[Version-Guard](#version-guard-private-ha-apis)*).
Auf einer abweichenden HA-Version blockiert der Laufzeit-Guard den `enforce`-Schreibpfad und hält
Tessera im read-only `monitor`-Zustand.

## Sicherheitsmodell (ehrlich)

Tessera kennt drei Betriebsmodi. **Der Default ist nicht-eingreifend.**

| Modus | Wirkung |
|---|---|
| `off` | Tessera tut nichts. |
| `monitor` | Tessera **berechnet** Permissions und zeigt Abweichungen (Panel + Logs), **schreibt aber NICHT** in den Auth-Store. Sicher zum Einfahren. |
| `enforce` | Tessera **schreibt** die kompilierten Permissions aktiv in den HA-Auth-Store (native Gruppen-`PolicyPermissions` + Rebind der `group_ids`) und greift real in Zugriffe ein. |

> **Aktueller Stand:** `enforce` ist verdrahtet (seit E3.5) und **schreibt** beim Setzen von
> `mode=enforce` nativen Auth-Zustand — nach einer fail-closed Gate-Sequenz (HA-Version → Compile →
> [D9-Vorprüfung](#d9-vorprüfung-enforce-gate) → Linter → Lockout-Precheck → unveränderlicher
> Snapshot/Journal → Apply). **Jeder Fehler in dieser Kette fällt sicher auf `monitor` zurück**
> (kein halb-scharfer Zustand); ein abgebrochener Lauf wird beim Start aus dem Pre-Install-Snapshot
> wiederhergestellt. Was noch **aussteht**, ist der Praxis-Nachweis (End-to-End gegen eine
> Dev-Instanz + Soak + Dogfood, siehe [ROADMAP](ROADMAP.md)). Beginne deshalb mit `monitor`, prüfe
> die berechneten Verdicts, und wechsle erst dann bewusst zu `enforce`.

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

- **Aktiver Schutz (Laufzeit-Guard):** Der Auth-Schreibpfad prüft im Code auf die **exakt getestete**
  HA-Version (`SUPPORTED_HA_AUTH_VERSION`, derzeit **2026.6.4** — exakter Gleichheits-Match). Auf jeder
  abweichenden Version wird der Schreibpfad **fail-closed blockiert** und `enforce` fällt auf den
  read-only `monitor`-Zustand zurück — **kein** nativer Write.
- Ein zusätzlicher `hacs.json`-Pin der HA-Mindestversion ist **bewusst noch nicht** gesetzt (die
  HACS-Validierung lehnte den Wert als künftiges Minimum ab); er kann mit dem Public-Flip als
  optionale zweite Hürde ergänzt werden. Die eigentliche Absicherung ist und bleibt der
  Laufzeit-Guard oben.
- Bricht eine interne API, wird die getestete/gepinnte Version angehoben und eine neue
  MAJOR-Version veröffentlicht.

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
