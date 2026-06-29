# Claude/Codex Contract Merge Review

Stand: 2026-06-29
Geprueft:
- `outputs/tessera-CONTRACT-claude-draft-2026-06-29.md`
- `outputs/claude-codex-cooperation-contract-v0-1-2026-06-29.md`
- `outputs/maison-atrium-role-contract.md`
- `outputs/tessera-phase0-SPEC-2026-06-29.md`
- aktuelle Claude-/Codex-Dokumentation und Agentic-Code-Review-Quelle aus dem Codex-Entwurf

Zwei Gegenpruef-Agenten:
- Prozess/Rollen/Repo-Layout
- Security/Betrieb/Dev-Isolation

## Gesamturteil

**MODIFY.**

Claudes Entwurf ist die bessere Basis fuer ein spaeteres Tessera-Repo-`CONTRACT.md`, weil er konkrete Repo-Struktur, Branches, Dual-Config und `TASKS.md` adressiert. Er ist aber noch nicht hart genug bei Betriebssicherheit, bestehender `outputs/`-Realitaet, Subagent-Regeln, Evidence-Schema und Konfliktloesung.

Empfehlung: **Claude-Entwurf als Basis nehmen, Codex-Klauseln hineinmergen, dann v0.2 erstellen.**

## Paragrafenurteil zu Claudes Entwurf

| Paragraf | Urteil | Begruendung | Korrektur |
|---|---|---|---|
| §1 Parteien & Rollen | MODIFY | Rollen stimmen grob. Codex' aktive Gegenpruefrolle bei Architektur/Security fehlt. Dev-Instanz-Verantwortung ist uneindeutig zwischen Michael und Codex. `20/80` darf kein SLA sein. | Codex darf Architektur-/Security-Claims widersprechen. Codex verwaltet nur isolierte Dev-Instanz im beauftragten Scope; Michael bleibt Freigabeinstanz fuer Credentials, Host, Live, Release. 20/80 als Richtwert markieren. |
| §2 Rhythmus & Pruefzeitpunkte | MODIFY | R0-R8 und Gatepunkte passen. Es fehlt: kein Go aus PARTIAL, D0-GREEN nur Startfreigabe, nicht fachliche Abnahme; nicht pruefbar = kein Go. | Codex §8/§9 uebernehmen: PASS/PASS MIT AUFLAGEN/FAIL plus ACCEPT/MODIFY/REJECT/BLOCKED; PARTIAL und `nicht verifizierbar` blockieren Produkt-/Enforce-Go. |
| §3 Zusammenarbeitsmodell | MODIFY | Evidence-based Merge, Task-Grenzen, Worktrees sind gut. `exchange/` kollidiert mit aktueller `outputs/`-Transportrealitaet. Subagents fehlen. Recherchepflicht zu pauschal. | `outputs/` bleibt bis Repo-Migration verbindlicher Handoff-Ort; `exchange/` wird Zielstruktur fuer neues Tessera-Repo. Subagent-Regeln aus Codex §10 ergaenzen. Recherche nur bei instabilen/aktuellen/High-Risk-Fragen, mit Quellenpflicht. |
| §4 Dateiablage & Benennung | MODIFY | Repo-Layout stark, aber Namensschema inkonsistent und nicht kompatibel mit aktuellen Artefakten. Evidence-Anforderungen fehlen. | Zwei Ebenen definieren: aktuell `outputs/`; spaeter Repo `docs/`, `exchange/`, `spike/evidence`, `spike/reports`, `decisions/`. Naming vereinheitlichen. Evidence immer mit Redaction-Status, Exit-Code, Abbruchgrund. |
| §5 Secrets & Sicherheit | MODIFY | Gute Basis, aber Phase-0-Spec ist praeziser. | Ergaenzen: keine Token/Passwoerter/auth_code/LLAT/.storage-Werte in argv/Chat/Logs/Evidence/Commits; 1Password nur stdin/pipe; `/Volumes/config` strikt read-only; Live-CM5 nie Auth-Testziel; D0-Isolation konkret: `ha-tessera-dev`, Port 8124 lokal, Docker-Volume, kein Bind nach `/Volumes/config`/Maison/Atrium, sonst `FAIL_TARGET_ISOLATION`, kein Write. |
| §6 Definition of Done & Freigaben | MODIFY | DoD passt, aber Dokumentationspflicht und harte Release-Blocker fehlen. | Report/Evidence, Gate-Review, Process-Log, Decision-Log bei Architektur/Security/Datenmodell als Pflicht. Kein Outward/Enforce/Release/HACS/Live-CM5 bei offenen Muss-Gates, PARTIAL, UNKNOWN_BLOCK_ENFORCE, fehlendem Secret-Scan, fehlendem Restore/Recreate-Proof oder fehlender Evidence. |
| §7 Werkzeuge & Schnittstellen | MODIFY | `TASKS.md`, Dual-Config und Freigabe fuer Erweiterungen sind gut. Direkter Kanal/Watcher-Realitaet und Subagent-Scope fehlen. | Kein garantierter direkter Claude-Codex-Kanal; Handoffs selbsttragend. Keine neuen MCPs/Module/Automationen mit Credential-/Live-Zugriff ohne Michael. `TASKS.md` ohne Secrets/Live-Operational-Details. |
| §8 Vertragsaenderung | ACCEPT MIT AUFLAGE | Verfahren passt. | Sicherheitsinvarianten duerfen nicht still gelockert werden; Lockerungen brauchen explizite Michael-Freigabe und Audit-Trail. |

## Was aus Codex v0.1 in v0.2 muss

1. **Komplementaere Rollen, nicht Hierarchie:** Beide duerfen einander korrigieren; Beleglage zaehlt.
2. **Transportrealitaet:** Bis zur Repo-Migration ist `outputs/` die gemeinsame Wahrheitsebene.
3. **Globale Invarianten:** keine Secrets, `/Volumes/config` read-only default, kein Live-/CM5-Write ohne Gate, kein Go aus PARTIAL.
4. **Konfliktloesung:** konkrete Behauptung -> Beleg -> Reproduktion; konservative Sicherheitsentscheidung gewinnt bis zur Klaerung.
5. **Subagents:** erlaubt fuer kritische Gates; Rollen Code/Core, Security/Betrieb, Architektur/Produkt, lokale Config/Evidence; kein Write ohne klaren Scope.
6. **Dokumentationspflicht:** Report/Evidence, Gate, Process-Log, Decision-Log.
7. **Standard-Outputs:** Codex Implementation/Gate-Cleanup und Claude Work-Order/Gate.

## Was aus Claude v0.1 in v0.2 muss

1. Tessera-Repo-Zielstruktur mit `CONTRACT.md`, `CLAUDE.md`, `AGENTS.md`, `docs/`, `exchange/`, `spike/`, `decisions/`.
2. R0-R8-Rhythmus und 3-5 kleine Codex-Schritte vor Gate.
3. Evidence-based Merge nach `main` nur mit gruenem Gate.
4. Worktree-/Branch-Isolation.
5. `TASKS.md` als leichtgewichtiges Board, falls Michael zustimmt.
6. Enge Codex-Aufgaben mit Scope, Nicht-Zielen, Tests und DoD.
7. 1Password-Regel, aber geschaerft: nie Werte in argv/Chat/Logs/Evidence.

## Offene Designentscheidung

**`outputs/` vs. `exchange/`:**

Empfehlung:
- Kurzfristig: `outputs/` bleibt verbindlich, weil Watcher, Claude-Artefakte und bestehende Reviews dort laufen.
- Bei neuem Tessera-Repo: `exchange/` wird Repo-interner Blackboard-Ort.
- Migration: Altes `outputs/` bleibt Archiv; nur kanonische, bereinigte Dokumente wandern nach `docs/`/`exchange/`.

## Konkreter Auftrag an Claude fuer v0.2

```text
Erstelle `outputs/tessera-CONTRACT-merged-v0-2-2026-06-29.md` als Merge aus deinem Vertragsentwurf und Codex' v0.1/Merge-Review.

Basis: dein Tessera-Repo-Layout bleibt erhalten.

Muss einarbeiten:
- `outputs/` bleibt bis Repo-Migration verbindlicher Handoff-Ort; `exchange/` ist Zielstruktur fuer neues Repo.
- Codex darf Architektur-/Security-Claims aktiv widersprechen; Belege schlagen Autoritaet.
- Konfliktloesung: Claim -> Evidence -> Reproduktion; konservative Sicherheitsentscheidung bis Klaerung.
- Subagent-Regeln inkl. Rollen und Write-Scope-Grenzen.
- Globale Invarianten: keine Secrets/Token/Auth-Codes/LLAT/.storage-Werte; `/Volumes/config` read-only; kein Live-/CM5-Write ohne Gate; kein Go aus PARTIAL/nicht verifizierbar.
- D0-/Dev-Isolation konkret: `ha-tessera-dev`, Port 8124 lokal, Docker-Volume, kein Bind nach `/Volumes/config`/Maison/Atrium; bei Abweichung `FAIL_TARGET_ISOLATION`, kein Write.
- Evidence-Pflicht: Redaction-Status, Exit-Code, Abbruchgrund, Tests/Logs, relevante file:line/URLs.
- Freigabe-Blocker: offene Muss-Gates, PARTIAL, UNKNOWN_BLOCK_ENFORCE, fehlender Secret-Scan, fehlender Restore/Recreate-Proof oder fehlende Evidence.
- Vertragsaenderungen duerfen Sicherheitsinvarianten nicht still lockern.

Bitte je geaenderter Klausel kurz markieren, welche Codex-Korrektur eingearbeitet wurde.
```

## Finales Urteil

**MODIFY, nicht REJECT.**

Claude hat das richtige Skelett fuer Tessera geliefert. Codex liefert die fehlenden Sicherheits- und Betriebsnervenbahnen. v0.2 sollte aus beiden entstehen.

