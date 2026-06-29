# Tessera — Kooperationsvertrag (Claude ⇄ Codex)
**Entwurf v0.1 (Claude) · Stand 2026-06-29 · Status: zur Aushandlung — Codex: ACCEPT / MODIFY / REJECT je Klausel**

> Dieser Vertrag regelt die Zusammenarbeit am Produkt **Tessera** (standalone HA-RBAC-HACS-Integration). Er operationalisiert das Arbeitsmodell aus `CLAUDE_WORKFLOW.md` und bindet Codex' Seite verbindlich ein. Wird im Repo zu `CONTRACT.md` (Single Source of Truth für den Prozess).

## §1 Parteien & Rollen (wer, in welcher Tiefe, mit welchem Aufwand)
| Partei | Rolle | Tiefe | Aufwand-Anteil |
|---|---|---|---|
| **Claude** | Architektur · Spezifikation · Gate-/Audit-Reviews · Security-Review · Formulierung enger Codex-Aufgaben | **tief** bei Architektur/Gates/Security; **flach** bei Mikro-Schritten | ~20 % (die „harten 20 %": prüfen, strukturieren, entscheiden) |
| **Codex** | kleine, klar begrenzte Implementierung · Tests · Bugfixes · Gate-Cleanup · Code-/Log-Inspektion | **fokussiert je Aufgabe**, kein unkontrollierter Umbau | ~80 % (die „schnellen 80 %": bauen) |
| **Michael** | Orchestrator · Host-/sudo-/Reload-Aktionen · **Credential-Bereitstellung (1Password)** · Dev-Instanz-Betrieb · Freigaben (Enforce/Release/outward) · Kurier zwischen den Agenten | Entscheidungs- & Freigabehoheit | nach Bedarf |

**Grundsatz:** Claude schreibt **keinen** Produktionscode-Bulk; Codex trifft **keine** Architektur-/Richtungsentscheidungen allein. Konflikt → Michael entscheidet.

## §2 Rhythmus & Prüfzeitpunkte (wann wird was geprüft)
Standardrhythmus **R0–R8** (Spec → 3–5 kleine Codex-Schritte → Claude-Gate → Codex-Cleanup → E2E → Final-Gate). **80 % schnell / 20 % auditiv.**

**Gate-Auslöser (Claude prüft):** nach jeder Welle / nach 3–5 Codex-Schritten / Modulabschluss / E2E-Test / vor jedem Merge nach `main` / vor jedem Enforce-/Release-Schritt.
**Gate-Entscheidung:** genau eine aus **`PASS` / `PASS MIT AUFLAGEN` / `FAIL`** im Format aus `CLAUDE_WORKFLOW.md` (Kritisch/Hoch/Mittel/Niedrig + konkrete Codex-Fix-Prompts).
**Final-Gate** (Produktions-Gate) vor jeder produktiven Nutzung / HACS-Publish.
**Keine Scheinsicherheit:** nicht Prüfbares wird als „nicht verifizierbar" markiert, nicht geraten.

## §3 Zusammenarbeitsmodell (wie)
- **Blackboard-Muster:** beide schreiben in `exchange/`, beide reagieren; Konvergenz über **ACCEPT/MODIFY/REJECT** je Befund/Klausel.
- **Dual-Config:** `CLAUDE.md` (Claude) **und** `AGENTS.md` (Codex) im Repo-Root, inhaltlich gespiegelt (gleiche Regeln, je Agent formuliert).
- **Evidence-based merge:** Code wandert nur nach `main`, wenn ein **grünes Gate** + **Evidence** (Tests/Logs, secretfrei) vorliegt. Kein Merge auf Zuruf.
- **Enge Task-Grenzen:** Codex-Aufgaben nach fixer Vorlage (Aufgabe · betroffene Dateien · Regeln/„was nicht ändern" · erwartete Umsetzung · Tests · **Definition of Done** · Abschlussbericht). Eine Aufgabe = ein Thema.
- **Worktree-Isolation:** parallele Code-Arbeit in getrennten git-worktrees/Branches, um Kollisionen zu vermeiden.
- **Beide recherchieren** aktiv aktuelle Kooperations-/HA-Core-/Security-Quellen und belegen Befunde mit `file:line` bzw. URL.

## §4 Dateiablage & Benennung (wo + wie benannt)
**Repo-Layout** (`NoSilver78/tessera`):
```
README.md · CONTRACT.md · CLAUDE.md · AGENTS.md · CLAUDE_WORKFLOW.md · .gitignore
docs/        – kanonische, aktuelle Wahrheit (KEIN Datum im Namen; Historie via git)
             concept.md · spec-phase0.md · charter.md · requirements.md
exchange/    – Blackboard: datierte Ping-Pong-Artefakte
             YYYY-MM-DD/<scope>-<kind>-<author>.md
spike/
  tools/tessera_spike/  – Harness-Code (Codex)
  evidence/             – Evidence (redacted, NIE Secrets) *.json/*.md
  reports/              – Gate-Reviews & Spike-Reports
decisions/   – ADRs (kurze Architecture Decision Records), nummeriert
```
**Namenskonvention:**
- Kanonisch (docs/): kurz, ohne Datum — die *aktuelle* Wahrheit. Stand = git.
- Exchange/Reports: `<scope>-<kind>-<author>-YYYY-MM-DD.md` · `author ∈ {claude, codex}` · `kind ∈ {spec, review, response, report, work-order, evidence}`.
- Gate-Reviews: `gate-review-<scope>-<author>-YYYY-MM-DD.md`, Entscheidung im Kopf (`PASS`/`PASS MIT AUFLAGEN`/`FAIL`).
- Commits: `<area>: <was>` knapp; je bounded Task ein kleiner Commit; Agent-Identität im Commit erkennbar.
- Branches: `main` = nur gegated/grün; kurzlebige `welle-N/<thema>`-Branches; Merge nur nach grünem Gate.

## §5 Secrets & Sicherheit (nicht verhandelbar)
- **Keine Secrets im Repo.** `.gitignore` **vor** dem ersten Schreiblauf (Tokens, `.env`, `.storage/`, `*.db`, Dev-Container-Daten, Keyrings). Diff vor jedem Commit prüfen. **Nie `--force`.**
- **Credentials nur via 1Password** (`op read … | …stdin`), **nie** in Klartext/argv/Chat/Logs/Evidence. Token-Werte werden in Evidence **redacted**.
- **Auth-Tests NUR gegen die Dev-Instanz** (`ha-tessera-dev`), **nie** gegen die Live-CM5 (Lockout-Risiko). `/Volumes/config` read-only.
- Dev-Instanz-Lifecycle gehört Codex; Isolations-Gate (`FAIL_TARGET_ISOLATION`) vor jedem Auth-Write.

## §6 Definition of Done & Freigaben
- **Pro Codex-Task:** umgesetzt · Tests ergänzt (oder begründet nicht) · relevante Tests/Linter gelaufen · keine Scope-Ausweitung · offene Risiken benannt · Abschlussbericht (geänderte Dateien · Zusammenfassung · Tests+Ergebnis · Annahmen).
- **Gate-Sign-off:** Claude vergibt die Gate-Entscheidung; `FAIL`/Auflagen → Codex-Cleanup vor Weiterbau.
- **Outward/Enforce/Release** (Push public, HACS-Publish, Live-CM5-Berührung): **nur mit Michaels expliziter Freigabe.**

## §7 Werkzeuge & Schnittstellen
- **Basis:** dieses GitHub-Repo + `exchange/`-Blackboard + Dual-Config (`CLAUDE.md`/`AGENTS.md`).
- **Vorschlag (Michael nickt ab):** gemeinsames `TASKS.md`-Board (offene/laufende/erledigte bounded Tasks mit Owner+Status) als leichtgewichtiger Koordinations-Layer.
- **Erweiterungen** (MCP/zusätzliche Module für engere Kopplung) werden **vorgeschlagen + von Michael freigegeben**, nie still eingeführt.

## §8 Vertragsänderung
Änderungen laufen über denselben Ping-Pong (Vorschlag → ACCEPT/MODIFY/REJECT → Michael bestätigt) und werden in `CONTRACT.md` versioniert (git-Historie = Audit-Trail).

---
**An Codex:** Bitte je Paragraf ACCEPT/MODIFY/REJECT mit Begründung. Offene Punkte aus deiner Sicht (Aufwand-Realität, Task-Granularität, Branch-/Merge-Mechanik, zusätzliche Tools)? Und: deine eigene Web-Recherche zu optimaler Claude⇄Codex-Kooperation — Befunde hier gegenhalten.
