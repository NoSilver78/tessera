# Codex Review - Claude Round-2 Work-Order Tessera

Stand: 2026-06-29T07:17:00+0200

Geprueft read-only:
- `outputs/tessera-claude-round2-workorder-2026-06-29.md`
- `outputs/tessera-codex-review-claude-gate-spike-2026-06-29.md`
- `outputs/tessera-codex-review-claude-gate-d0-2026-06-29.md`
- `outputs/tessera-spike-report-2026-06-29.md`
- `outputs/tessera-phase0-SPEC-2026-06-29.md`
- `tools/tessera_spike/d0_preflight_spike.py`

Zwei Gegenpruef-Agenten:
- Agent A: Spezifikation, Sequenz, Go/No-Go-Sprache
- Agent B: Security, Betrieb, globale Invarianten

## Entscheidung

MODIFY.

Die Work-Order ist inhaltlich stark und die Sequenz ist im Kern richtig: **Welle A Instrument/Fixture zuerst**, danach **B Kernluecken**, danach **C/D Breite, Klassifikation und Lifecycle-Gates**. Sie sollte als Arbeitsbasis verwendet werden, aber nicht unveraendert, weil einige Formulierungen und Prioritaeten noch zu viel Freigabe suggerieren.

## Hohe Punkte

| Bereich | Problem | Auswirkung | Konkrete Korrektur |
|---|---|---|---|
| Freigabesprache | `Schreibpfad-Risikokern positiv aufgeloest`, `Schreibpfad bewiesen`, `Neubau` bleiben zu stark. | Kann als finales Architektur- oder Enforce-Go gelesen werden, obwohl D5, M2, M4, M5 und M6 offen sind. | Ersetzen durch: `Schreibpfad-Machbarkeit positiv signalisiert; Neubau bleibt plausibler Default; finale Architektur-/Enforce-Entscheidung erst nach kompletter Round-2-Rubrik`. |
| D2 Status | `D2-PASS bleibt gueltig` ist zu pauschal. | Reine Policy-Mutation ohne definierte Invalidierung ist noch offen. | Status enger formulieren: `D2 positiv fuer explizite Invalidierung; automatische/unklare Invalidierung bleibt B1-Gate`. |
| M5/M6 Prioritaet | D9 und D11/D13/D15 stehen unter `P2`; das kann wie nice-to-have wirken. | Spec fuehrt M5/M6 als Muss und Go/No-Go-Rubrik-Bestandteile. | Umbenennen: nicht P2 optional, sondern `Muss vor finalem Enforce-/Architektur-Gate`; D9-Provisional sofort `UNKNOWN_BLOCK_ENFORCE` fuer Service/HTTP/WS-Komponenten. |
| Evidence zu spaet | Evidence-Schema ist erst in Welle D. | A/B/C sind sonst schwer sauber gate-reviewbar. | Basisevidence in Welle A beginnen: `exit_code`, `gate_results[]`, Abbruchgrund, Secret-Redaction-Status, Log-Check; Core-`file:line` kann bis D erweitert werden. |
| Globale Invarianten fehlen | Keine explizite globale Regel fuer `/Volumes/config read-only`, keine Token-/Secretwerte, keine Live-/CM5-Writes. | Einzelne Wellen koennten versehentlich zu breit laufen. | Vor Welle A einen Abschnitt `Globale Invarianten fuer alle Wellen` ergaenzen: nur `ha-tessera-dev`, `/Volumes/config` read-only, keine Tokenwerte/Passwoerter/Auth-Codes/LLATs, kein Live-CM5-Write, Failure-Artefakte redakten. |
| `system-users` Gate fehlt im Backlog | Work-Order erkennt die Invariante, fuehrt aber keinen expliziten Test. | Rueckfall in `system-users` koennte spaeter restriktive Policies aushebeln. | In B2 oder eigenes B3 aufnehmen: managed User haben exakt erwartete Tessera-Gruppen und keinen `system-users`-Rueckfall, vor/nach Restore und Restart. |

## Mittlere Punkte

| Bereich | Problem | Auswirkung | Konkrete Korrektur |
|---|---|---|---|
| Sequenz C | C wird `nach A` genannt, Gate-Text sagt aber Breite erst nach A+B. | Unklare Ausfuehrungsreihenfolge. | Eindeutig machen: A-Gate fuer Messinstrument, A+B-Gate fuer Kern, C/D danach; finales Gate nach C+D. |
| D9 Default | `keine Live-ALLOW aus Statik` ist gut, aber Default fehlt als Sofort-Regel. | Zwischenzeitliche Klassifikation bleibt interpretierbar. | Sofortregel: bis Runtime-Beleg = `UNKNOWN_BLOCK_ENFORCE` fuer alle Komponenten mit Service/HTTP/WS. |
| A/B Scope | A1+A2 sind als ein Lauf sinnvoll, aber B1/B2 sollten erst nach sauberem A-Log laufen. | Sonst bleiben Messergebnisse angreifbar. | A als eigenes Mini-Gate mit Log-Beleg `keine Detected blocking call` und 8-Service-Load-Check. |

## Positive Beobachtungen

- A1 setzt die wichtigsten Instrument-Probleme richtig: blocking I/O, 8 Services, echte Harness-Dateien, valide `services.yaml`.
- A2 setzt die Seed-Fixture korrekt vor die breite Matrix.
- B2 priorisiert D5 nach Instrument-Haertung, nicht erst am Ende.
- C1 enthaelt die wichtigsten Runtime-Luecken: WS, Registry, Logbook, History, render_template, `entity_id:all`, echter LLAT.
- D9 `ALLOW/DENY/TIER-2/UNKNOWN_BLOCK_ENFORCE` ist enthalten; nur die Prioritaet und Default-Policy muessen schaerfer werden.

## Nicht pruefbar / Grenzen

- Keine neuen Messlaeufe wurden ausgefuehrt.
- Keine Aenderung an `/Volumes/config`.
- Keine Aussage, ob die Work-Order bereits von Claude umgesetzt wurde; bewertet wurde nur das Dokument.

## Konkrete Korrektur fuer die Work-Order

```text
Ueberarbeite `outputs/tessera-claude-round2-workorder-2026-06-29.md` inhaltlich wie folgt:

1. Ersetze `Schreibpfad-Risikokern positiv aufgeloest` / `Schreibpfad bewiesen` / `Neubau` durch:
   `Schreibpfad-Machbarkeit positiv signalisiert; Neubau bleibt plausibler Default; finale Architektur-/Enforce-Entscheidung erst nach kompletter Round-2-Rubrik`.

2. Fuege globale Invarianten fuer alle Wellen ein:
   nur `ha-tessera-dev`, `/Volumes/config` read-only, keine Token-/Passwort-/Auth-Code-/LLAT-Werte in Logs/Evidence/Chat, keine Live-CM5-Writes, Failure-Artefakte redakten.

3. Verschiebe Basisevidence in Welle A:
   `exit_code`, `gate_results[]`, Abbruchgrund, Secret-Redaction-Status, 8-Service-Load-Check, Log-Check ohne blocking-I/O-Warnungen.

4. Fuege `system-users` als explizites B-Gate hinzu:
   managed User haben vor/nach Restore und Restart keine `system-users`-Mitgliedschaft und exakt erwartete Tessera-Gruppen.

5. Schaerfe D9:
   sofortige Provisional-Policy `UNKNOWN_BLOCK_ENFORCE` fuer alle Service/HTTP/WS-Komponenten bis Runtime-Klassifikation; D9 ist Muss vor finalem Gate, nicht optionales P2.

6. Klaere Gates:
   A-Gate = Instrument/Fixture sauber; A+B-Gate = Kernluecken; finales Enforce-/Architektur-Gate erst nach C+D.
```

## Finales Urteil

Work-Order: **MODIFY, aber als Grundlage brauchbar**.

Keine Blockade fuer Welle A. Welle A sollte aber die globalen Invarianten und Basisevidence sofort mittragen, sonst entsteht direkt wieder ein Review-Loch.
