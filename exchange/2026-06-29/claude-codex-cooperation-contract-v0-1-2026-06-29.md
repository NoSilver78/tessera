# Claude/Codex Cooperation Contract v0.1

Stand: 2026-06-29
Status: **Codex-Vorschlag zur Verhandlung mit Claude**. Gilt erst als verbindlich, wenn Claude ihn mit `ACCEPT` bestätigt oder ein Gegenentwurf gemerged wurde.

## 0. Zweck

Dieser Vertrag regelt, wie Claude und Codex in Maison/Atrium/Warden/Tessera zusammen entwickeln, prüfen und dokumentieren, ohne dass Michael jede Mikroentscheidung koordinieren muss. Er ersetzt nicht die Projektanforderungen, sondern legt den Arbeitsmodus fest: Wer denkt, wer baut, wer prüft, wo Wahrheit liegt, wann gestoppt wird.

Leitidee: **klein bauen, hart prüfen, alles belegbar machen.**

## 1. Quellen und Herleitung

Dieser Vertrag konsolidiert:
- `outputs/maison-atrium-role-contract.md` vom 2026-06-23.
- `codex_prompt_packet/CODEX_WORKFLOW.md` aus Michaels Prompt-Packet.
- die Tessera-Gate-Runden vom 2026-06-29.
- aktuelle Tool-Dokumentation: Claude Code beschreibt Planung vor Edits, parallele Sessions, Subagents und Workflows; Codex dokumentiert Subagents, Workflows, Worktrees und Automations; Forschungs-/Praxisquellen zu AI-Code-Review betonen menschliche Aufsicht, Tests und klare Review-Gates.

Quellen:
- Claude Code Overview: https://code.claude.com/docs/en/overview
- Claude Code Common Workflows: https://code.claude.com/docs/en/common-workflows
- Claude Code Subagents: https://code.claude.com/docs/en/sub-agents
- OpenAI Codex Docs: https://developers.openai.com/codex/cloud
- OpenAI Codex Subagents: https://developers.openai.com/codex/concepts/subagents
- Human-AI Synergy in Agentic Code Review: https://arxiv.org/abs/2603.15911

## 2. Beteiligte und Rollen

| Rolle | Primäre Aufgabe | Sekundäre Aufgabe | Darf nicht |
|---|---|---|---|
| Claude | Architektur, Semantik, Spezifikation, UX-/Produktlinie, Gate-Reviews, Work-Orders | Codex-Tasks formulieren, Gegenentwürfe prüfen | Ungeprüft Live-/Produktfreigaben behaupten, reale Config ändern ohne explizites Gate |
| Codex | Implementierung, lokale Repo-/Dateianalyse, Tests, Reproduktion, Evidence, Gate-Cleanup | Architektur auf Widersprüche prüfen, Security-/Betriebsrisiken hart benennen | Architektur eigenmächtig umbauen, große Refactors ohne Auftrag, Tests schwächen |
| Michael | Owner, Priorisierung, Freigabe produktiver Schritte, Relay wenn nötig | Host-/sudo-/Token-/Reload-Aktionen | Muss nicht Mikroentscheidungen treffen, solange Vertrag und Gates eindeutig sind |

Rollen sind **komplementär, nicht hierarchisch**: Claude kann Codex korrigieren, Codex kann Claude korrigieren. Bei Widerspruch zählt Beleglage, nicht Autorität.

## 3. Transportrealität

Es gibt keinen garantierten direkten Claude-Codex-Kanal. Übergabe erfolgt über Dateien und Michael/Watcher.

Verbindliche Arbeitsorte:
- `outputs/` = Review-, Spezifikations-, Work-Order-, Evidence- und Vertragsartefakte.
- `scratchpad/` = temporäre Anforderungen oder Claude-Artefakte, wenn von außen dort abgelegt.
- `/Volumes/config` = echte Home-Assistant-Konfiguration, grundsätzlich **read-only**, außer Michael gibt explizit eine Write-Phase frei.
- `tools/` oder projektspezifische Dev-Pfade = Codex-Implementierung, wenn im Scope.

Jedes Handoff-Dokument muss selbsttragend sein: Kontext, Ziel, Scope, Quellen, Dateien, Nicht-Ziele, Gate-Kriterien.

## 4. Globale Invarianten

Diese Regeln gelten immer:

1. Keine Secrets, Token, Passwörter, Auth-Codes, LLAT-Werte oder `.storage`-Inhalte in Chat, Logs, Reports oder Commits.
2. `/Volumes/config` nur read-only, außer ein explizites Write-Gate nennt Ziel, Backup, Rollback und Verifikation.
3. Kein Live-/CM5-Write ohne Backup, Rollback-Dry-Run, `check_config`, Manifest und Michael-Freigabe.
4. Kein Push/Commit vom Mac, wenn das Projekt den Host-Autosync nutzt.
5. Keine Architekturfreigabe aus einem PARTIAL-Lauf.
6. Kein Produkt-/Enforce-Go, solange Muss-Gates offen sind.
7. Jede nicht prüfbare Aussage wird als `nicht verifizierbar` markiert.
8. Alle Evidence-Artefakte enthalten Secret-Redaction-Status.

## 5. Arbeitsmodus

### 5.1 Standardzyklus

```text
Intent -> Spec/Work-Order -> Codex Implementation -> Evidence -> Claude Gate -> Codex Cleanup -> Re-Gate -> Release/Next Wave
```

Für kurze Fixes:

```text
Bug/Gap -> Codex Reproduce -> Minimal Fix -> Tests -> Claude or Codex Gate -> Done
```

Für riskante Architektur:

```text
Claude Proposal -> Codex Adversarial Review -> Claude Response -> Michael Decision -> Implementation
```

### 5.2 Batchgröße

Codex arbeitet in kleinen, testbaren Einheiten. Nach 3 bis 5 Implementierungsschritten, nach jedem Modul, nach jedem E2E-Test, nach Logfehlern und vor produktiver Nutzung kommt ein Gate.

Claude darf größere Konzepte entwerfen, muss sie aber in umsetzbare, sequenzierte Work-Orders herunterbrechen.

## 6. Artefakt-Namen

Alle Dateien beginnen mit Projektpräfix:

- `maison-atrium-...`
- `warden-...`
- `tessera-...`
- `claude-codex-...`

Empfohlene Muster:

- Spezifikation: `outputs/<projekt>-spec-YYYY-MM-DD.md`
- Work-Order: `outputs/<projekt>-workorder-<runde>-YYYY-MM-DD.md`
- Codex-Report: `outputs/<projekt>-codex-report-<runde>-YYYY-MM-DD.md`
- Claude-Gate: `outputs/<projekt>-claude-gate-<runde>-YYYY-MM-DD.md`
- Codex-Gegenreview: `outputs/<projekt>-codex-review-<gegenstand>-YYYY-MM-DD.md`
- Evidence JSON: `outputs/<projekt>-evidence-<runde>-YYYY-MM-DD.json`
- Prozesslog: `outputs/<projekt>-process-log.md`
- Decision-Log: `outputs/<projekt>-decision-log.md`

## 7. Dokumentationspflicht

Jede substanzielle Runde erzeugt mindestens:

1. **Report/Evidence**: was wurde getan, welche Dateien, welche Tests, welche Ergebnisse, welche offenen Punkte.
2. **Gate-Review**: PASS / PASS MIT AUFLAGEN / FAIL oder ACCEPT / MODIFY / REJECT.
3. **Process-Log-Eintrag**: Datum, Runde, Input, Output, Entscheidung, nächster Schritt.
4. **Decision-Log-Eintrag**, wenn Architektur, Security, UX-Grammatik, Datenmodell oder Produktlinie betroffen sind.

Codex darf ohne explizite Anfrage Review-Artefakte in `outputs/` schreiben, wenn ein Watcher oder Gate-Auftrag das verlangt. Projektdateien außerhalb `outputs/` nur im konkreten Implementierungsscope.

## 8. Gate-Entscheidungen

### 8.1 Implementierungs-/Betriebsgates

- `PASS`: Weiterbauen möglich, keine kritischen oder hohen offenen Punkte.
- `PASS MIT AUFLAGEN`: Weiterbauen möglich, aber Auflagen sind terminiert und dürfen nicht vergessen werden.
- `FAIL`: Erst beheben, dann weiterbauen.

### 8.2 Architektur-/Vertragsreviews

- `ACCEPT`: Vertrag/Entscheidung tragfähig.
- `MODIFY`: Richtung stimmt, konkrete Änderungen nötig.
- `REJECT`: Nicht tragfähig; neuer Ansatz erforderlich.
- `BLOCKED`: Ohne externe Information/Freigabe nicht entscheidbar.

Jedes Gate enthält Findings nach Schwere, konkrete Korrektur, nicht prüfbare Punkte und nächste Aufgaben.

## 9. Konfliktlösung

Wenn Claude und Codex widersprechen:

1. Beide benennen die **konkrete Behauptung**.
2. Beide nennen **Belege**: Datei/Zeile, Test, Log, offizielle Doku oder reproduzierbares Experiment.
3. Wenn Belege fehlen: Status `nicht verifizierbar`, kein Go.
4. Wenn beide plausibel sind: konservativere Sicherheits-/Betriebsentscheidung gewinnt bis zur Reproduktion.
5. Michael entscheidet nur bei Produkt-/Prioritäts-/Geschmacksfragen oder wenn zwei technisch zulässige Wege bleiben.

Verboten: rhetorische Freigaben wie `Risikokern bewiesen`, wenn nur Teilgates grün sind.

## 10. Subagents und Mehr-Agenten-Arbeit

Subagents sind erlaubt, wenn:
- User/Watcher es explizit verlangt,
- ein Review mehrere unabhängige Perspektiven braucht,
- oder eine Aufgabe natürlich in unabhängige Recherche-/Prüfblöcke zerfällt.

Mindestrollen bei kritischen Gates:
- Code/Core
- Security/Betrieb
- Architektur/Produkt
- lokale Konfiguration/Evidence

Subagents schreiben nicht selbst in Produktdateien, außer sie sind ausdrücklich als Worker mit klarer Write-Scope-Zuweisung beauftragt. Für Reviews liefern sie Findings, die der Hauptagent integriert.

## 11. Sicherheits- und Betriebsregeln

Für Home Assistant / CM5 / `/Volumes/config`:

- Read-only-Validierung ist Standard.
- Jeder Write braucht Backup, Manifest, Rollback, Dry-Run oder Staging, `check_config`, Secret-Scan und Verifikation.
- Kein Domain-Service-Call gegen reale Aktorik ohne ausdrückliches Aktorik-Gate.
- Keine Live-ALLOW aus statischer Analyse.
- Custom Components mit Service/HTTP/WS bleiben bis Runtime-Klassifikation `UNKNOWN_BLOCK_ENFORCE`.
- Logs sind Belege: Warnungen wie blocking I/O sind Gate-relevant.

## 12. Standard-Output von Codex

Nach Implementierung:

```markdown
## Umsetzung abgeschlossen

### Geänderte Dateien
- ...

### Was wurde geändert?
- ...

### Tests/Linter
Ausgeführt:
- ...

Ergebnis:
- ...

### Offene Risiken / Annahmen
- ...

### Nicht geändert
- ...
```

Nach Gate-Cleanup:

```markdown
## Gate-Cleanup abgeschlossen

### Umgesetzte Gate-Punkte
| Gate-Punkt | Status | Hinweis |
|---|---|---|

### Geänderte Dateien
- ...

### Tests/Linter
- ...

### Verbleibende offene Punkte
- ...
```

## 13. Standard-Output von Claude

Claude-Work-Orders sollen enthalten:

```markdown
# <Projekt> Work-Order <Runde>

## Ziel
## Nicht-Ziele
## Globale Invarianten
## Betroffene Dateien / erlaubter Write-Scope
## Sequenzierte Aufgaben
## Definition of Done
## Gate-Kriterien
## Erwartete Codex-Ausgabe
## Offene Fragen
```

Claude-Gates sollen Findings priorisieren und keine kosmetischen Punkte überbewerten.

## 14. Verhandlung dieses Vertrags

Da Claude dieselbe Aufgabe bekommen hat, gilt folgendes Merge-Protokoll:

1. Codex schreibt diesen Vorschlag.
2. Claude schreibt eigenen Vorschlag oder Review.
3. Codex liest Claudes Vorschlag read-only und erzeugt `claude-codex-contract-merge-review-YYYY-MM-DD.md`.
4. Bei `ACCEPT`: dieser Vertrag wird `v1.0`.
5. Bei `MODIFY`: Codex erstellt `v0.2` mit roter Liste der Änderungen.
6. Bei `REJECT`: Michael entscheidet, welcher Entwurf Ausgangspunkt wird.

Bis dahin ist `v0.1` ein Arbeitsentwurf, aber die globalen Invarianten gelten bereits aus bestehenden Projektregeln.

## 15. Sign-off

| Partei | Status | Datum | Kommentar |
|---|---|---:|---|
| Codex | PROPOSED | 2026-06-29 | Dieser Entwurf |
| Claude | PENDING | - | wartet auf Review/Gegenentwurf |
| Michael | PENDING | - | finale Freigabe |

