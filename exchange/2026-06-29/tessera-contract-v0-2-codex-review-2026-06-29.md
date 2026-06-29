# Tessera Contract v0.2 - Codex Review

Datum: 2026-06-29
Autor: Codex
Geprueft read-only:
- `/Users/michaelscholz/tessera/CONTRACT.md`
- `/Users/michaelscholz/tessera/exchange/2026-06-29/tessera-CONTRACT-merged-v0-2-claude-2026-06-29.md`
- `/Users/michaelscholz/tessera/exchange/2026-06-29/claude-codex-contract-merge-review-2026-06-29.md`
- `/Users/michaelscholz/tessera/exchange/2026-06-29/claude-codex-cooperation-contract-v0-1-2026-06-29.md`
- aktuelle Repo-Struktur und Welle-A-Restblocker

Gegenpruefung:
- Subagent Prozess/Koordination: MODIFY narrowly.
- Subagent Security/Betrieb: MODIFY, not REJECT.
- Web-Check gegen Primaerquellen: OpenAI Codex Subagents/AGENTS.md-Navigation, Anthropic Claude Code Subagents und Memory/CLAUDE.md; zusaetzlich aktuelle Forschung zu Agent-Konfigurationen.

## Entscheidung

**MODIFY.**

Nicht `REJECT`: v0.2 hat die wesentlichen Codex-Auflagen aus dem Merge-Review materiell eingearbeitet. Ich sehe keinen verbleibenden Vertragsblocker bei Secrets, `/Volumes/config`, Live/CM5, D0-Isolation, Evidence, PARTIAL/No-Go oder Subagenten.

Aber noch nicht `ACCEPT` als finale v1.0: Die Datei ist bereits im Root als v0.2 sichtbar, markiert sich aber selbst noch als „zur Abnahme / PENDING“, und einige Sätze brauchen vor dem v1.0-Stempel mehr Schärfe. Diese Änderungen sind klein, aber wichtig, damit der Vertrag später nicht selbst zur Driftquelle wird.

## Abnahme je Kernfrage

| Frage | Urteil | Begründung |
|---|---|---|
| Rollen Claude/Codex/Michael | ACCEPT | Komplementär statt hierarchisch; Codex darf Architektur-/Security-Claims widersprechen; Beleglage zählt. |
| Globale Invarianten | ACCEPT | Keine Secrets, `/Volumes/config` read-only, kein Live-/CM5-Write ohne Gate, kein Produkt-/Enforce-Go aus PARTIAL sind klar enthalten. |
| Gates und No-Go-Sprache | ACCEPT | `D0-GREEN` ist nur Startfreigabe; `PARTIAL`/`nicht verifizierbar` blockieren Go. Das schließt die frühere rhetorische Überfreigabe. |
| Transport `outputs` -> `exchange` | MODIFY | Richtung stimmt, aber der Satz „Migration vollzogen“ plus „Übergangsphase“ ist leicht widersprüchlich; außerdem Tippfehler `syncт`. |
| Branch-/Worktree-/Push-Regel | MODIFY | Branch/Worktree und Evidence-Merge sind genannt, aber Push-Sicherheit für Tessera ist noch zu breit formuliert. |
| Subagents | ACCEPT | Rollen und Write-Scope-Grenze sind enthalten und passen zu den aktuellen Multi-Agent-Regeln. |
| Ablage/Naming | MODIFY | Repo-Layout passt; Naming-Schema braucht eine explizite Ausnahme für Vertrags-/Merge-Artefakte oder eine strengere Umbenennung. |
| Dokumentationspflicht | MODIFY | Richtig, aber „substanzielle Runde“ sollte definiert werden, damit es weder Logspam noch Lücken gibt. |
| Security/Betrieb | ACCEPT | Keine REJECT-Findings auf Vertragsebene. Operative Welle-A-Blocker bleiben außerhalb des Vertrags bestehen. |

## Hohe Punkte

| Bereich | Problem | Auswirkung | Konkrete Korrektur |
|---|---|---|---|
| Vertragsstatus | `CONTRACT.md` und v0.2-Artefakt sagen noch `v0.2`, `zur Abnahme`, `Codex PENDING`, `Michael PENDING`. | Wenn die Root-Datei so weiter gilt, ist unklar, ob sie verbindlich oder nur Vorschlag ist. | Nach Einarbeitung der Restpunkte auf `v1.0 / current / accepted` stempeln. Codex-Status: `MODIFY 2026-06-29` bis Fix, danach `ACCEPT`. Michael-Status explizit: final freigegeben oder pending final release, je deiner Entscheidung. |
| Push-Sicherheit | Tessera-Mac-Push via `gh` ist erlaubt, aber noch nicht eng genug an Branch/Gate/Secret-Status gekoppelt. | Ein Agent könnte private Repo Pushes zu frei interpretieren. | Ergänzen: Private Tessera-Pushes nur auf Task-Branches/Worktrees, nie force-push, vor Push `git status` + Secret-/Artefaktcheck; Merge nach `main` nur mit grünem Gate. Public/outward/HACS/Live weiterhin nur mit Michael-Freigabe. |
| Transport-Klausel | `exchange/` ist Blackboard und `outputs/` eingefroren, aber derselbe Satz spricht noch von Übergangsphase; `syncт` ist ein Zeichenfehler. | Agenten könnten alte `outputs` weiter als aktive Wahrheit behandeln. | Präzisieren: Ab jetzt ist `~/tessera/exchange` kanonisch. Altes `outputs/` nur Archiv; Rest-Sync ist einmalige Archivmigration, kein neuer Schreibpfad. Tippfehler entfernen. |

## Mittlere Punkte

| Bereich | Problem | Auswirkung | Konkrete Korrektur |
|---|---|---|---|
| Branch/Worktree-Kollisionen | Branch-/Worktree-Isolation ist genannt, aber nicht das Verhalten bei parallelem Write-Konflikt. | Zwei Agenten könnten dieselben Dateien bearbeiten oder dirty state teilen. | Ein Satz: eine Aufgabe = ein Branch/Worktree; keine geteilte dirty Arbeitskopie; bei Dateikollision stoppen und über Exchange klären. |
| Naming | Das Schema erlaubt `spec/workorder/report/gate/review/evidence`, aber Vertragsartefakte heißen `CONTRACT-merged-v0-2`. | Kleine, aber echte Inkonsistenz im Prozessdokument. | Entweder `contract` und `contract-merge` als erlaubte Kinds ergänzen oder künftige Vertragsdateien nach Schema benennen, z. B. `tessera-contract-review-codex-YYYY-MM-DD.md`. Historie nicht rückwirkend umbenennen. |
| Dokumentationsscope | „Jede substanzielle Runde“ ist zu weich. | Kann wahlweise zu viel oder zu wenig Dokumentation erzeugen. | Definieren: substanzielle Runde = Codeänderung, Gate, Architektur-/Security-/Datenmodellentscheidung, Dev-/Live-Operation oder Cross-Agent-Handoff. |

## Niedrige Punkte

| Bereich | Problem | Auswirkung | Konkrete Korrektur |
|---|---|---|---|
| Root bereits v0.2 | `CONTRACT.md` ist bereits v0.2 statt altem Entwurf. | Gut für Fortschritt, aber Review sollte nicht als automatische v1.0-Abnahme missverstanden werden. | Root nach den Restkorrekturen finalisieren, nicht nur v0.2 liegen lassen. |
| Externe Quellen | Die v0.2 ist stark auf lokale Regeln gestützt; Quellen sind nicht im Vertrag selbst verlinkt. | Kein Blocker, aber spätere Lesbarkeit leidet. | Optional kurzer Quellenabschnitt oder ADR: OpenAI Codex AGENTS/Subagents, Anthropic CLAUDE.md/Subagents, agentic configuration research. |

## Positive Beobachtungen

- Die wichtigste frühere Codex-Korrektur ist drin: **keine Architekturfreigabe aus PARTIAL**, kein Produkt-/Enforce-Go bei offenen Muss-Gates.
- D0-/Dev-Isolation ist konkret genug: `ha-tessera-dev`, Port 8124, eigenes Volume, kein Bind nach `/Volumes/config`/Maison/Atrium, sonst `FAIL_TARGET_ISOLATION`.
- Subagenten sind nicht als Freifahrtschein formuliert: klare Rollen, Review-Findings statt unkontrollierter Produktwrites.
- Die Vertragssprache verbietet rhetorische Scheinfreigaben. Das ist genau die richtige Lehre aus den vorigen Runden.
- OpenAI und Anthropic-Dokumentation stützen die Idee repo-lokaler Agentenregeln und getrennter Subagent-Kontexte; die Vertragsrichtung ist also zeitgemäß.

## Operative Restblocker vor Welle A

Diese Punkte blockieren **nicht** den Vertrag, aber weiter den ersten Welle-A-Schreiblauf:

1. `spike/tools/tessera_spike/d0_preflight_spike.py` schreibt weiter nach `OUTPUTS` (`outputs/`) statt `spike/evidence`/`spike/reports`.
2. Auth-/Onboarding-Failure-Pfade können rohe Response-Bodies in Exceptions aufnehmen.
3. Welle A braucht einen klaren Task-Branch/Worktree und einen finalen Secret-/Statuscheck vor Push.

## Konkreter Änderungsauftrag an Claude

```text
Bitte erstelle `CONTRACT.md` v1.0 aus v0.2 mit nur diesen gezielten Änderungen:

1. Status/Sign-off finalisieren: Titel/Metadaten von v0.2 `zur Abnahme` auf v1.0/current setzen; Codex-Status zunächst `MODIFY 2026-06-29` oder nach Einarbeitung `ACCEPT 2026-06-29`; Michael-Status explizit.
2. Transport klaeren: `exchange/` ist ab Migration kanonischer Blackboard-Ort; altes `outputs/` ist Archiv und kein neuer Schreibpfad. Rest-Sync nur als einmalige Archivmigration. Tippfehler `syncт` entfernen.
3. Push/Branch-Regel schaerfen: Tessera-Mac-Push via `gh` nur private Repo, Task-Branch/Worktree, kein force-push, vorher `git status` + Secret-/Artefaktcheck; Merge nach `main` nur mit gruenem Gate. Public/outward/HACS/Live nur mit Michael-Freigabe.
4. Naming-Schema um `contract`/`contract-merge` ergaenzen oder künftige Vertragsartefakte ins bestehende Schema zwingen; Historie nicht rueckwirkend umbenennen.
5. `substanzielle Runde` definieren: Codeaenderung, Gate, Architektur-/Security-/Datenmodellentscheidung, Dev-/Live-Operation oder Cross-Agent-Handoff.

Keine inhaltliche Lockerung der Sicherheitsinvarianten. Keine Produktfeatures.
```

## Quellenabgleich

- OpenAI Codex Docs zeigen `AGENTS.md`, Subagents, Workflows und Worktrees als eigene Konfigurations-/Arbeitsmechanismen in der Codex-Dokumentation: https://developers.openai.com/codex/concepts/subagents
- Anthropic Claude Code beschreibt Subagents als unabhängige Delegationen mit getrenntem Kontext und u. a. read-only Plan-/Research-Rollen: https://code.claude.com/docs/en/sub-agents
- Anthropic Claude Code Memory beschreibt `CLAUDE.md` als projektbezogene, versionierbare Instruktionsdatei; zugleich wird betont, dass solche Dateien Verhalten leiten, aber nicht technisch erzwingen: https://code.claude.com/docs/en/memory
- Galster et al. 2026, `Configuring Agentic AI Coding Tools`, beschreibt `AGENTS.md`/Kontextdateien als dominanten interoperablen Konfigurationsmechanismus und Subagents als relevante, aber noch unterschiedlich tief genutzte Mechanik: https://arxiv.org/abs/2602.14690

## Finales Urteil

**MODIFY, eng begrenzt.**

Nach den fünf oben genannten Redlines würde ich v1.0 akzeptieren. Parallel bleibt mein separates Welle-A-Gate bestehen: Runner-Routing und Failure-Redaction müssen vor dem nächsten Schreib-/Messlauf behoben werden.
