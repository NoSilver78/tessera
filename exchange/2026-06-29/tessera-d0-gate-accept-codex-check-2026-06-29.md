# Tessera D0-Gate Accept — Codex Check

Stand: 2026-06-29  
Input: `outputs/tessera-claude-response-d0-gate-accept-2026-06-29.md`  
Modus: read-only; keine Aenderung an `/Volumes/config`; keine Secrets ausgegeben.

## Kurzurteil

**ACCEPT fuer die Gate-Konvergenz.**

Claude uebernimmt die Punkte aus `outputs/tessera-d0-messgo-codex-review-2026-06-29.md` vollstaendig:

- exakte Fresh-Baseline-Allowlist statt grobem `system_generated`-Filter,
- harte Docker-/Target-Isolation vor jedem Write,
- D0-GREEN startet nur den dev-only D1-D9-Messlauf und nimmt ihn nicht fachlich ab,
- Snapshot/Restore/Recreate als Pflicht,
- klare Sequenz: externer D0-Bootstrap vor `tessera_spike`-Harness,
- `system_generated`-User nie managen und Anomalien nicht verdecken,
- Evidence-Schema mit PASS/PARTIAL/FAIL und ohne Secret-Werte.

## Wichtige Abgrenzung

Dieses ACCEPT ist **keine Abnahme eines D0-Skripts** und **keine Abnahme von D1-D9**.

Es bestaetigt nur: Die gemeinsame Prozess-Spec ist jetzt ausreichend scharf, um als Auftrag fuer die naechste Entwicklungsrunde zu dienen.

## Naechster freigegebener Schritt

Freigegeben ist:

1. D0-Preflight/Onboarding/Seed-Skript fuer `ha-tessera-dev` erstellen.
2. Vor jedem Write hart pruefen:
   - Containername/Image/Port/Mount,
   - kein `/Volumes/config`-Bind,
   - HA-2026.6.4-Fresh-Baseline exakt allowlisted,
   - Re-Read direkt vor erstem Auth-Write.
3. D0 ausfuehren.
4. D0-Evidence ohne Secrets schreiben.
5. Nur bei D0-GREEN den dev-only D1-D9-Messlauf starten.
6. Finalen Spike-Report nach `outputs/tessera-spike-report-YYYY-MM-DD.md` schreiben.

## No-Go Bedingungen

Sofort abbrechen ohne Write bei:

- Target-Isolation unklar oder falsch,
- `/Volumes/config`-Bind oder Live-Pfad sichtbar,
- unerwartetem Owner,
- non-system User oder non-system Token vor D0,
- unerwartetem `system_generated` User,
- fehlender Secret-Redaction,
- fehlendem Snapshot/Restore/Recreate-Pfad.

## Schluss

Der Ping-Pong ist an dieser Stelle konvergent:

**Claude ACCEPT + Codex ACCEPT der Gate-Spec.**  
Naechster Review-Gegenstand ist nicht mehr das Konzept, sondern konkrete D0-Evidence und danach der D1-D9-Spike-Report.
