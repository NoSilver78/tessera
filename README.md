# Tessera

> Rollenbasierte Zugriffskontrolle (RBAC) für Home Assistant — *ansehen / bedienen / ändern* × **Rolle** × **Bereich**.

Tessera ist ein eigenständiges Berechtigungssystem für Home Assistant. Es schließt eine seit
Jahren offene Lücke: HA kennt nur drei feste Systemgruppen, kein UI für feingranulare Rechte und
einen Owner-Bypass. Tessera kompiliert deklarative Richtlinien (**Rolle × Bereich × Aktion**) zu
**nativen** HA-`PolicyPermissions` und schreibt sie — **im `enforce`-Modus** — in den
Home-Assistant-Auth-Store. **Kein Monkeypatch, kein Core-Fork.**

> ⚠️ **Sicherheitskritische Integration.** Tessera verändert, wer in deiner Home-Assistant-Instanz
> was sehen und tun darf. Lies das **[Sicherheitsmodell](#sicherheitsmodell-ehrlich)** unten, bevor du
> `enforce` aktivierst — und beachte den **[Projektstatus](#projektstatus)**: Durchsetzung ist gebaut,
> aber noch in Validierung und auf dem heutigen Stand **noch nicht aktiv**.

## Was Tessera tut

- **Deklarative Policies** — Rollen × Bereiche × Aktionen (`view` / `operate` / `change`).
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
| **Enforce-Maschinerie** (Plan · Bindings · Write+Guards · Restore/Recovery) | ✅ gebaut, adversarial gegated, **ruht** (nicht verdrahtet) |
| **Enforce-Verdrahtung** (`mode=enforce` schaltet scharf) | 🚧 in Arbeit — auf `main` **noch nicht aktiv** |
| **Echter End-to-End-Test gegen eine Dev-Instanz + Soak** | ⏳ ausstehend |
| **HACS-Release** | ⏳ ausstehend |

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

**Getestete HA-Version:** Home Assistant **2026.6.4** (siehe *[Version-Guard](#version-guard-private-ha-apis)*) —
wird mit dem ersten Release über `hacs.json` gepinnt.

## Sicherheitsmodell (ehrlich)

Tessera kennt drei Betriebsmodi. **Der Default ist nicht-eingreifend.**

| Modus | Wirkung |
|---|---|
| `off` | Tessera tut nichts. |
| `monitor` | Tessera **berechnet** Permissions und zeigt Abweichungen (Panel + Logs), **schreibt aber NICHT** in den Auth-Store. Sicher zum Einfahren. |
| `enforce` | **Zielverhalten:** Tessera **schreibt** die kompilierten Permissions aktiv in den HA-Auth-Store und greift real in Zugriffe ein. |

> **Aktueller Stand:** Auf dem heutigen `main` ist `enforce` **noch nicht verdrahtet** — `mode=enforce`
> liefert die `monitor`-Vorschau **plus eine Warnung** und **schreibt nicht**, bis die Verdrahtung
> gemergt und end-to-end validiert ist (siehe [ROADMAP](ROADMAP.md)). Beginne ohnehin mit `monitor`,
> prüfe die berechneten Verdicts, und wechsle erst dann bewusst zu `enforce`.

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

- Der Auth-Schreibpfad prüft im Code auf die **exakt getestete** HA-Version (derzeit **2026.6.4**).
  Auf einer abweichenden Version wird der Schreibpfad **fail-closed blockiert** — es bleibt beim
  read-only `monitor`-Zustand, **kein** nativer Write.
- Mit dem ersten Release pinnt zusätzlich `hacs.json` die HA-Mindestversion, sodass HACS
  Installation/Update auf ungetesteten Instanzen blockt.
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
