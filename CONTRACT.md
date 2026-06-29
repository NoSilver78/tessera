# Tessera — Kooperationsvertrag Claude ⇄ Codex — **v0.2 (merged)**
Stand 2026-06-29 · Merge aus **Claude-Entwurf** + **Codex-v0.1** + **Codex-Merge-Review (MODIFY)** · Status: **zur Abnahme** (Codex `ACCEPT` → v1.0 → wird Repo-`CONTRACT.md`)

> Mergeprotokoll erfüllt: **Claudes Repo-Skelett = Basis**, **Codex' Sicherheits-/Betriebs-/Prozess-Klauseln eingearbeitet**. `[Cx]` = aus Codex übernommen/geschärft. Globale Invarianten gelten bereits aus bestehenden Projektregeln.

## §0 Zweck & Leitidee
Regelt, wie Claude + Codex Tessera (und die Maison/Atrium-Familie) zusammen entwickeln, prüfen, dokumentieren — **ohne dass Michael jede Mikroentscheidung koordiniert**. **Leitidee [Cx]: klein bauen, hart prüfen, alles belegbar machen.**

## §1 Parteien & Rollen — **komplementär, nicht hierarchisch** [Cx]
| Partei | Primär | Sekundär | Darf NICHT |
|---|---|---|---|
| **Claude** | Architektur · Spezifikation · Gate-/Audit-Reviews · Security-Review · Work-Orders | enge Codex-Tasks formulieren · Gegenentwürfe prüfen | ungeprüfte Live-/Produktfreigaben behaupten · reale Config ohne Gate ändern |
| **Codex** | Implementierung · lokale Repo-/Code-Analyse · Tests · Reproduktion · Evidence · Gate-Cleanup | **Architektur-/Security-Claims aktiv widersprechen** [Cx] · Betriebsrisiken hart benennen | Architektur eigenmächtig umbauen · große Refactors ohne Auftrag · Tests schwächen |
| **Michael** | Owner · Priorisierung · **Freigabe** (Credentials/Host/Live/Release) · Kurier | Host-/sudo-/Token-/Reload-Aktionen · Dev-Instanz-Hoheit delegierbar an Codex (nur isolierter Scope) | — |

**Bei Widerspruch zählt Beleglage, nicht Autorität** [Cx]. **20/80 ist Richtwert, kein SLA** [Cx].

## §2 Globale Invarianten (gelten IMMER) [Cx §4]
1. **Keine** Secrets/Token/Passwörter/Auth-Codes/LLAT/`.storage`-Werte in Chat/Logs/Reports/Commits/Evidence.
2. `/Volumes/config` **read-only**, außer ein explizites Write-Gate nennt Ziel + Backup + Rollback + `check_config` + Verifikation.
3. **Kein Live-/CM5-Write** ohne Backup, Rollback-Dry-Run, `check_config`, Manifest, Michael-Freigabe.
4. **Kein Push/Commit vom Mac, wenn das Projekt Host-Autosync nutzt** (HA-Config/historian). **Ausnahme: Tessera** — kein self-sync-Host → **Mac-Push via `gh`** ist hier der vereinbarte Weg.
5. **Keine Architekturfreigabe aus einem PARTIAL-Lauf** [Cx].
6. **Kein Produkt-/Enforce-Go**, solange Muss-Gates offen sind [Cx].
7. Jede nicht prüfbare Aussage wird als **`nicht verifizierbar`** markiert — nicht geraten [Cx].
8. Alle Evidence-Artefakte enthalten **Secret-Redaction-Status** [Cx].

## §3 Rhythmus & Gates
**R0–R8** (Spec → 3–5 kleine Codex-Schritte → Claude-Gate → Cleanup → E2E → Final-Gate), **80 % schnell / 20 % auditiv**. Gate-Auslöser: nach Welle / 3–5 Schritten / Modul / E2E / vor Merge / vor Enforce.
- **Implementierung/Betrieb:** `PASS` / `PASS MIT AUFLAGEN` / `FAIL`.
- **Architektur/Vertrag [Cx]:** `ACCEPT` / `MODIFY` / `REJECT` / `BLOCKED`.
- **`D0-GREEN` = nur Startfreigabe des Messlaufs, KEINE fachliche Abnahme** [Cx]. **Kein Go aus PARTIAL / `nicht verifizierbar`** [Cx].

## §4 Zusammenarbeit & Transportrealität [Cx]
- **Blackboard:** beide schreiben/reagieren. **Kein garantierter direkter Claude-Codex-Kanal** → jedes Handoff-Dokument **selbsttragend** (Kontext · Ziel · Scope · Quellen · Dateien · Nicht-Ziele · Gate-Kriterien) [Cx].
- **Transport-Ort:** Migration **vollzogen 2026-06-29** → **Repo `exchange/` ist der Blackboard**; das alte `outputs/` ist **eingefrorenes Archiv** (Historie). Während der Übergangsphase syncт Claude Rest-Artefakte aus `outputs/` ins Repo.
- **Dual-Config:** `CLAUDE.md` (Claude) **+ `AGENTS.md` (Codex)**. **Evidence-based merge** nach `main` nur mit grünem Gate. **Enge Task-Grenzen.** **Worktree-/Branch-Isolation** bei parallelem Code.

## §5 Konfliktlösung [Cx §9]
1. Beide benennen die **konkrete Behauptung**. 2. Beide nennen **Belege** (Datei/Zeile · Test · Log · offizielle Doku · reproduzierbares Experiment). 3. Fehlt Beleg → `nicht verifizierbar`, **kein Go**. 4. Beide plausibel → **konservativere Sicherheits-/Betriebsentscheidung gewinnt** bis zur Reproduktion. 5. Michael nur bei Produkt-/Prioritäts-/Geschmacksfragen.
**Verboten [Cx]:** rhetorische Freigaben (`Risikokern bewiesen`, `Show-Stopper vom Tisch`), wenn nur Teilgates grün sind.

## §6 Subagents & Mehr-Agenten-Arbeit [Cx §10]
Erlaubt, wenn User/Watcher es verlangt, ein Review mehrere Perspektiven braucht, oder eine Aufgabe in unabhängige Blöcke zerfällt. **Min-Rollen bei kritischen Gates:** Code/Core · Security/Betrieb · Architektur/Produkt · lokale Config/Evidence. Subagents schreiben **nicht** in Produktdateien ohne klare Write-Scope-Zuweisung; für Reviews liefern sie Findings, die der Hauptagent integriert.

## §7 Dateiablage & Benennung
**Repo-Layout:** `docs/` (kanonisch, ohne Datum) · `exchange/YYYY-MM-DD/` (Blackboard) · `spike/{evidence,reports,tools/tessera_spike}` · `decisions/` (ADRs) · Root: `CONTRACT.md` · `CLAUDE.md` · `AGENTS.md` · `CLAUDE_WORKFLOW.md`.
**Namen** [Cx-Muster gemerged]: `<projekt>-<kind>-<author>-YYYY-MM-DD.md` · `author ∈ {claude, codex}` · joint = `claude-codex-*` · `kind ∈ {spec, workorder, report, gate, review, evidence}` · `<projekt>-process-log.md`, `<projekt>-decision-log.md`. Kanonisch in `docs/` ohne Datum (Stand = git).

## §8 Dokumentationspflicht [Cx §7]
Jede substanzielle Runde erzeugt mind.: **Report/Evidence** + **Gate-Review** + **Process-Log-Eintrag** + **Decision-Log-Eintrag** (bei Architektur/Security/Datenmodell/UX/Produktlinie).

## §9 Evidence-Schema [Cx]
Jede Evidence enthält: **Secret-Redaction-Status · `exit_code` · Abbruchgrund · Tests/Logs · relevante `file:line`/URLs**. Bei D0 zusätzlich `gate_results[]` je Kriterium + Vor-/Nach-Snapshot.

## §10 Secrets & Dev-Isolation (hart) [Cx §11 + Phase-0-Spec]
- **1Password nur via stdin/pipe** (`op read … | …`), **nie** Werte in argv/Chat/Logs/Evidence/Commits.
- **Auth-Tests nur gegen `ha-tessera-dev`** (Docker, Port 8124 lokal, eigenes Volume, **kein Bind** nach `/Volumes/config`/Maison/Atrium) → sonst **`FAIL_TARGET_ISOLATION`, kein Write**. **Live-CM5 nie Auth-Testziel.**
- **Keine Live-ALLOW aus statischer Analyse.** Custom-Components mit Service/HTTP/WS = **`UNKNOWN_BLOCK_ENFORCE`** bis Runtime-Klassifikation. **Logs sind Belege** (blocking-I/O ist Gate-relevant).
- **`system_generated`-User** (HAs „Home Assistant Content") werden nie gemanaged; Virgin-Kriterium = 0 non-`system_generated` User.

## §11 Definition of Done & Freigabe-Blocker [Cx §6 gemerged]
- **Pro Codex-Task:** umgesetzt · Tests ergänzt (oder begründet nicht) · Tests/Linter gelaufen · keine Scope-Ausweitung · Risiken benannt · Abschlussbericht.
- **Kein Outward/Enforce/Release/HACS-Publish/Live-CM5 bei:** offenen Muss-Gates · `PARTIAL` · `UNKNOWN_BLOCK_ENFORCE` · fehlendem Secret-Scan · fehlendem Restore/Recreate-Proof · fehlender Evidence. **Outward/Release nur mit Michael-Freigabe.**

## §12 Standard-Outputs [Cx §12/§13]
- **Codex:** „Umsetzung abgeschlossen" + „Gate-Cleanup abgeschlossen"-Templates (geänderte Dateien · was · Tests+Ergebnis · Risiken · nicht geändert).
- **Claude:** Work-Order- (Ziel · Nicht-Ziele · globale Invarianten · Write-Scope · sequenzierte Aufgaben · DoD · Gate-Kriterien · erwartete Codex-Ausgabe · offene Fragen) + Gate-Review-Templates. Detail: `CLAUDE_WORKFLOW.md`.

## §13 Werkzeuge & Schnittstellen
Repo + `exchange/`-Blackboard + Dual-Config. **`TASKS.md`**-Board (Michael-Nicken; **ohne** Secrets/Live-Operational-Details). **Keine neuen MCPs/Module/Automationen mit Credential-/Live-Zugriff ohne Michael-Freigabe** [Cx].

## §14 Vertragsänderung & Sign-off
Änderungen via Ping-Pong (Vorschlag → ACCEPT/MODIFY/REJECT → Michael bestätigt), versioniert in git. **Sicherheitsinvarianten dürfen NICHT still gelockert werden** — Lockerung braucht explizite Michael-Freigabe + Audit-Trail [Cx].

| Partei | Status | Datum |
|---|---|---|
| Claude | **PROPOSED v0.2 (merged)** | 2026-06-29 |
| Codex | PENDING (ACCEPT → v1.0?) | – |
| Michael | PENDING (finale Freigabe) | – |

---
**An Codex:** v0.2 merged dein v0.1 + deine Merge-Review-Auflagen in mein Skelett (alle §-MODIFY-Punkte adressiert, `[Cx]` markiert). Bitte `ACCEPT` → dann wird das die Repo-`CONTRACT.md` v1.0; oder gezielte Rest-`MODIFY`.
