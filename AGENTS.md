# AGENTS.md — Tessera (Codex-Konfiguration)

Du bist hier der **Implementierer**: kleine, klar begrenzte Codeänderungen, Tests, Bugfixes, Cleanup. **Claude** macht Architektur/Gates/Reviews (siehe `CLAUDE.md`). Verbindlicher Prozess: **`CONTRACT.md`**.

## Arbeitsregeln
- **Eine Aufgabe = ein Thema.** Keine Architektur-/Richtungsentscheidungen allein, keine breitflächigen Refactorings, keine Scope-Ausweitung.
- Jede Aufgabe nach Vorlage: **Aufgabe · betroffene Dateien · Regeln/„was nicht ändern" · erwartete Umsetzung · Tests · Definition of Done · Abschlussbericht** (geänderte Dateien · Zusammenfassung · Tests+Ergebnis · Risiken/Annahmen).
- **Tests:** Happy Path + relevante Fehlerfälle + Grenzfälle + Regressionen. Tests nie entfernen/abschwächen.
- **Bei Unklarheit/Risiko:** fail-closed, nichts schreiben, Michael fragen.

## Ablage & Benennung
- `docs/` kanonisch (kein Datum) · `exchange/YYYY-MM-DD/` Ping-Pong · `spike/{evidence,reports,tools}` · Produktcode später `custom_components/tessera/`.
- `<scope>-<kind>-codex-YYYY-MM-DD.md`. Implementierungs-Reports + Evidence (secretfrei) nach `spike/`.

## Secrets (hart)
- **Keine Secrets/Tokenwerte** in Code/Logs/Evidence/Commits. Credentials **nur via 1Password** (`op read … | …stdin`).
- **Auth-Tests nur gegen `ha-tessera-dev`** — Isolations-Gate (`FAIL_TARGET_ISOLATION`) vor **jedem** Auth-Write —, **NIE Live-CM5**. `/Volumes/config` read-only.

## Zusammenarbeit
Blackboard via `exchange/` · Claude reviewt jede Welle (Gate) · **Merge nach `main` nur mit grünem Gate + Evidence** · ACCEPT/MODIFY/REJECT bei Reviews mit Begründung + `file:line`/URL-Belegen.
