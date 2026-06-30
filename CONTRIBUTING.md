# Mitwirken an Tessera

Danke für dein Interesse! Tessera ist eine sicherheitskritische Integration (sie verändert
HA-Zugriffsrechte), darum legen wir Wert auf **Sorgfalt, Ehrlichkeit und nachvollziehbare Reviews**.
Dieses Dokument erklärt, wie das Projekt gebaut wird, wie du beitragen kannst, und — am wichtigsten —
**wo wir Unterstützung gut gebrauchen können**.

## Wie Tessera gebaut wird (transparent)

Tessera entsteht in einem ungewöhnlichen, bewusst offengelegten Modell:

- **Claude** — Architektur, Spezifikation, Gate/Audit (siehe [`CLAUDE.md`](CLAUDE.md), [`CLAUDE_WORKFLOW.md`](CLAUDE_WORKFLOW.md)).
- **Codex** — Implementierung in kleinen Schritten (siehe [`AGENTS.md`](AGENTS.md)).
- **Michael** — Eigentümer, Orchestrierung, finale Entscheidungen.

Der verbindliche Prozess steht in [`CONTRACT.md`](CONTRACT.md). Jeder Schritt durchläuft **vor dem
Merge** ein **adversariales Mehr-Agenten-Gate** (mehrere skeptische Reviewer, die widerlegen sollen)
plus **Mutationsproben** (Tests werden gezielt gebrochen, um zu beweisen, dass sie den Regress
fangen). Der Zweck bei einer sicherheitskritischen Integration: **jeder Auth-Schreibpfad** wird vor
dem Merge von mehreren unabhängigen, skeptischen Reviews geprüft, nicht nur vom Autor. Die Übergaben liegen offen in [`exchange/`](exchange/), die Gate-Reviews in
[`reports/`](reports/), Architektur-Entscheidungen in [`decisions/`](decisions/).

Du musst dieses Modell **nicht** nutzen, um beizutragen — menschliche PRs sind willkommen und
durchlaufen dieselbe Review-Sorgfalt.

## Wie du beiträgst

1. **Issue zuerst** — für alles über einen Tippfehler hinaus bitte erst ein Issue öffnen, damit wir
   Richtung und Scope abstimmen.
2. **Fork → Branch → PR** gegen `main`. Kleine, fokussierte PRs sind leichter zu reviewen.
3. **Qualitäts-Tor:** Code muss `ruff`, `black` und `mypy --strict` bestehen und Tests mitbringen.
   Die CI führt zusätzlich Home-Assistant-Tests aus. *(Hinweis: Während der Vor-Release-Verdrahtung
   kann `main` zeitweise rot sein — der Setup-Block unten beschreibt den Ziel-Zustand.)*
4. **Sicherheits-Regel (hart):** Auth-schreibende Tests laufen **nur** gegen eine **separate
   Dev-Instanz**, **niemals** gegen eine Produktiv-Instanz. Keine Secrets ins Repo.

### Entwicklungs-Setup (Kurz)

```bash
python -m venv .venv && . .venv/bin/activate
pip install homeassistant ruff black mypy pytest
ruff check . && black --check . && mypy --strict custom_components/tessera && pytest
```

## Help wanted — wo wir Unterstützung gut gebrauchen können

Das sind die **offenen Flanken** (siehe auch [ROADMAP.md](ROADMAP.md)). Genau hier hilft Mitarbeit am meisten:

- **🧪 Tests auf vielfältigen Multi-User-Setups.** Tessera muss reale Haushalte abbilden. Wenn du HA
  mit mehreren Nutzern/Rollen betreibst: Passt das `Rolle × Bereich × Aktion`-Modell? Fehlt ein
  Scope? Berichte, was nicht passt.
- **🔄 HA-Versions-Kompatibilität (größtes Dauer-Risiko).** Tessera schreibt teils über
  nicht-öffentliche HA-Auth-APIs. Hilfe beim **Testen gegen neue HA-Releases** und beim Melden, wenn
  eine interne API bricht, ist extrem wertvoll. (→ [docs/MAINTENANCE.md](docs/MAINTENANCE.md))
- **🔍 Unabhängiges Security-Review.** Frische Augen auf den Auth-Schreibpfad, die Guards
  (allow-only, Lockout-Precheck) und die Restore-/Recovery-Logik. Verantwortungsvolle Meldung über
  [SECURITY.md](SECURITY.md).
- **🕳️ Leak-Pfad-Mitigationen.** Ideen oder PRs, um `render_template`/Logbook/Assist-Lecks
  HA-seitig zu entschärfen oder klarer zu dokumentieren.
- **🎨 Frontend-Panel.** Das Admin-Panel (Matrix-Editor) verträgt UX-Politur und Übersetzungen.
- **🔌 `by_group` / Authentik-OIDC.** Der additive IdP-Gruppen-Pfad ist inert, bis der
  Roh-Claim-Seitenkanal verlässlich nachgewiesen ist — Erfahrung mit Authentik/OIDC-`groups` gesucht.
- **📖 Dokumentation & Übersetzungen.** Klarere Anleitungen, Beispiele, `en`-Übersetzung.

### „Good first issues"
- README/Doku-Beispiele für ein konkretes Rollen-Setup ergänzen.
- Edge-Case-Tests für den Compiler (area-lose Entitäten, leere Rollen) beisteuern.
- Übersetzungs-Strings vervollständigen.

## Verhaltenskodex

Sei respektvoll und konstruktiv. Wir gehen von guter Absicht aus und bewerten Beiträge nach Sache
und Sicherheit, nicht nach Person.

## Lizenz der Beiträge

Mit einem Beitrag stimmst du zu, dass er unter der **[MIT-Lizenz](LICENSE)** des Projekts
veröffentlicht wird.
