# Codex Abnahme - Tessera Round-2 Work-Order v2

Stand: 2026-06-29

Geprueft read-only:
- `outputs/tessera-claude-round2-workorder-v2-2026-06-29.md`
- `outputs/tessera-codex-review-claude-round2-workorder-2026-06-29.md`

Gegenpruefung:
- Ein unabhaengiger Subagent hat v2 gegen die Codex-MODIFY-Auflagen geprueft.

## Entscheidung

**ACCEPT.**

Die Work-Order v2 erfuellt die Codex-Auflagen ausreichend klar und darf als verbindliche Round-2-Basis verwendet werden.

## Abgenommene Punkte

| Punkt | Status | Beleg |
|---|---|---|
| Freigabesprache korrigiert | ACCEPT | Kein `D0-GREEN`, kein `Risikokern bewiesen`, kein `Neubau GO`; D5 bleibt unbewiesen und finaler Architektur-/Enforce-Go gesperrt. |
| Globale Invarianten | ACCEPT | `ha-tessera-dev` only, kein Live-CM5-Write, `/Volumes/config` read-only, keine Token-/Passwort-/Auth-Code-/LLAT-Werte, Failure-Redaction. |
| Basis-Evidence ab Welle A | ACCEPT | Jede Welle verlangt `exit_code`, `gate_results[]`, Abbruchgrund, Secret-Redaction-Status und Log-Check. |
| A-Gate | ACCEPT | Welle A blockiert B/C-Bewertung; verlangt 8-Service-Load-Check und sauberes Log ohne `Detected blocking call`. |
| `system-users` Gate | ACCEPT | Eigenes B3-Gate vor/nach Restore und Restart. |
| D9 Default | ACCEPT | Service/HTTP/WS-Komponenten sind bis Runtime-Beleg `UNKNOWN_BLOCK_ENFORCE`; D9 ist Muss vor finalem Gate. |
| C/D Final-Gate | ACCEPT | D11/D13/D15 und C-Matrix bleiben Muss vor finaler Enforce-/Architekturentscheidung. |

## Kleine Ausfuehrungshinweise fuer Welle A

- A1 und A2 sollten als eigener Lauf mit eigenem Report enden, nicht still in B/C uebergehen.
- Der A-Report muss mindestens enthalten: geaenderte Dateien, 8 registrierte Services, `services.yaml` valide, Logauszug ohne blocking-I/O-Warnungen, Seed-Inventar, Secret-Scan.
- `/Volumes/config` bleibt read-only; Live-CM5 bleibt tabu.

## Finales Urteil

**Welle A darf starten.**

Kein Enforce-/Produkt-/Live-Go. Nur Instrument- und Fixture-Haertung auf `ha-tessera-dev`.

