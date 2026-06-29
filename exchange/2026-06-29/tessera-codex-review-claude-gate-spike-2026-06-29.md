# Codex Gegenreview - Claude Spike-Gate Tessera

Stand: 2026-06-29T07:12:00+0200

Geprueft read-only:
- `outputs/tessera-claude-gate-review-spike-2026-06-29.md`
- `outputs/tessera-spike-report-2026-06-29.md`
- `outputs/tessera-spike-result-2026-06-29.json`
- `outputs/tessera-gate-review-d0-d1-d9-2026-06-29.md`
- `outputs/tessera-phase0-SPEC-2026-06-29.md`
- `tools/tessera_spike/d0_preflight_spike.py`
- Docker-Logs `ha-tessera-dev` read-only
- Primaerquellen: Home Assistant Developer Docs zu asyncio blocking operations und Authentication API.

Zwei Gegenpruef-Agenten wurden getrennt eingesetzt:
- Agent A: Spezifikation, M1-M8, D1-D15, Go/No-Go-Rubrik
- Agent B: Security, Betrieb, Recovery, Secrets, Transport-/Leak-Risiken

## Entscheidung

MODIFY zu Claudes Spike-Gate-Review.

Claudes Review ist im Kern brauchbar: `PASS MIT AUFLAGEN`, kein Enforce-Go, Round-2-Haertung noetig. Aber die Sprache ist stellenweise zu breit. Der Spike beweist starke positive Signale fuer D1/D2/D4, nicht den gesamten Risikokern. `Neubau GO` und `Risikokern bewiesen` muessen abgeschwaecht werden zu:

**Schreibpfad-Machbarkeit positiv signalisiert; weiterer Phase-0-Haertungslauf freigegeben; kein Enforce-/Produkt-Go.**

## Wichtigste Korrektur

Die Go/No-Go-Rubrik der Spec verlangt fuer v1-Enforce unter anderem D1/D2/D4/D5/D11 PASS, D3/D6 PASS entity-targeted, D13/D15 PASS und dokumentierte D7/D8-Matrix. Der aktuelle Spike hat:

- D1/D2/D4: PASS-Signale
- D3/D5/D6/D7/D8/D9: PARTIAL
- D11/D13/D15: nicht gelaufen
- M2: 8 Services nicht umgesetzt
- M4/M5/M6: nicht voll erfuellt

Daraus folgt: Weiterhaerten ja, Enforce nein, finales Architektur-Go nein.

## Hohe Punkte

| Bereich | Problem | Auswirkung | Konkrete Korrektur |
|---|---|---|---|
| Gate-Sprache | Claude schreibt `Risikokern bewiesen`, `Show-Stopper vom Tisch`, `Neubau GO`. | Kann als finales Architektur-/Produkt-Go missverstanden werden, obwohl D5, M2, M4, M5, M6 offen sind. | Umformulieren zu `D1/D2/D4 positiv; Neubau bleibt plausibler Default; finales Go erst nach Round-2-Gates`. |
| M2 Harness-Schnittstelle | Das Harness registriert nur `tessera_spike.run_spike`; die 8 geforderten Services sind nicht vorhanden. | Einzelvertraege und Adaptergrenzen sind nicht isoliert pruefbar. | Vor weiterer Matrix-Breite zuerst 8 Services implementieren und einzeln belegen. |
| D5 Recovery | `boot_rescue_corruption_tested:false`; Boot-Rescue bei kaputtem Store/Setup-Exception wurde nicht ausgefuehrt. | Der sicherheitskritische Lockout-/Rescue-Pfad ist nicht bewiesen. | D5 als hartes High-Gate behandeln, nicht als normale Haertung: Store/Setup-Exception erzwingen, Restore ohne gesunden Tessera-Start beweisen. |
| M4 Transport-/Leak-Matrix | WS, Logbook, Registry, History, Systemkontext, non-entity Service und `return_response changed_states` fehlen. | Durchsetzung ist nur fuer einen engen REST/Service-Ausschnitt belegt. | D3/D6/D7/D8 vollstaendig messen; `entity_id: all` mit Vor-/Nach-Zustand erlaubt/verboten pruefen. |
| M5 D9 Runtime | D9 ist nur statischer Scan; keine `ALLOW/DENY/TIER-2/UNKNOWN_BLOCK_ENFORCE`-Runtime-Klassifikation. | Custom Components mit Service/HTTP/WS koennen Enforce umgehen. | Bis zur Runtime-Klassifikation jede Custom Component mit Service/HTTP/WS als `UNKNOWN_BLOCK_ENFORCE` behandeln. |
| M6 D11/D13/D15 | Version-Gate, HACS-Update-Governance und E2E `off->monitor->enforce->restore` sind nicht gelaufen. | Keine Gesamtentscheidung fuer v1-Enforce moeglich. | D11/D13/D15 als Muss-Gates fuehren, nicht als optionale Nachziehpunkte. |
| Betrieb / HA-Async | Docker-Logs zeigen `Detected blocking call` fuer `read_text`, `write_text` und `open` im `tessera_spike`-Event-Loop. Die HA-Developer-Doku verlangt fuer blocking I/O den Executor. | Messinstrument kann Lognoise, Instabilitaet oder verfalschte Laufzeitmessungen erzeugen. | Datei-I/O im Harness via `hass.async_add_executor_job`, HA-Store oder async Helper auslagern; Log muss danach sauber sein. |

## Mittlere Punkte

| Bereich | Problem | Auswirkung | Konkrete Korrektur |
|---|---|---|---|
| `system-users` Invariant | Claude nennt nicht explizit, dass HA-Rechte permissiv mergen und Tessera-managed User nicht in `system-users` bleiben duerfen. | Restriktive Tessera-Policies koennen durch Systemgruppe ueberstimmt werden. | Gate-Test ergaenzen: managed User haben exakt die erwarteten Tessera-Gruppen und keinen `system-users`-Rueckfall. |
| `entity_id: all` | Status 200 beweist nicht, ob verbotene Entities geaendert wurden. | Bypass-Risiko bleibt offen. | Vor-/Nach-Zustand erlaubter und verbotener Entities bei `entity_id: all` messen. |
| D2 Interpretation | `allowed_read_after_policy_change:false` ist ohne Policy-Richtung schwer lesbar. | PASS ist fuer Reviewer nicht reproduzierbar genug. | D2 in Negativ-/Positivtest trennen: ohne Invalidate, mit definierter Invalidate, Persist+Restart. |
| LLAT | HA beschreibt Long-Lived Access Tokens als eigene, langlebige Tokenklasse; aktueller Lauf nutzt nur normalen Headless-Token. | D8-Risikoklasse nicht getestet. | Echten non-admin-LLAT via WS erzeugen, Wert nie loggen, D7 headless pruefen, Rotation/Revocation belegen. |
| Secrets | Aktuelle Artefakte enthalten keine erkennbaren Tokenwerte; Fehlerpfade koennen aber Response-Bodies in Exceptions tragen. | Failures koennten spaeter sensible Werte leaken. | Fehlerpfade vor Exception-Ausgabe redakten; Secret-Scan auch ueber Failure-Artefakte laufen lassen. |
| Seed | Seed bleibt zu schmal und nur teilweise evidenziert. | Resolver-/Registry-/Domain-Verhalten wird nicht belastbar gemessen. | Deterministische Fixture mit Areas, Devices, mehreren Domains, hidden/disabled und state-only Fall. |

## Positive Beobachtungen

- Claudes Grundentscheidung `PASS MIT AUFLAGEN` ist fuer weiteres Phase-0-Haerten vertretbar.
- D1/D2/D4 sind echte positive Signale: Persist/Restart, explizite Cache-Invalidierung und Union/Restore funktionieren im engen Lauf.
- Claude markiert D3/D5/D6/D7/D8/D9, D11/D13/D15 und D10/D12 im Kern als offen.
- Kein Live-/CM5-Write, kein Enforce-Go, `/Volumes/config` nur read-only.

## Nicht pruefbar / Grenzen

- D10 CM5-Benchmark und D12 OIDC/AuthentiK wurden nicht ausgefuehrt.
- D11/D13/D15 wurden nicht ausgefuehrt.
- Die lokale HA-Core-Quelllage wurde in diesem Gegenreview nicht neu file-line-genau gegen `/usr/src/homeassistant` verankert; fuer das Gate reichen die aktuellen Artefakte, aber der naechste Report sollte echte Core-`file:line`-Anker liefern.
- Webrecherche wurde bewusst eng auf offizielle Home-Assistant-Developer-Dokumentation beschraenkt.

## Quellen

- Home Assistant Developer Docs: Blocking operations with asyncio, insbesondere Executor-Empfehlung sowie `open`, `write_text`, `read_text`: https://developers.home-assistant.io/docs/asyncio_blocking_operations/
- Home Assistant Developer Docs: Authentication API, Long-Lived Access Tokens und Token-Revocation: https://developers.home-assistant.io/docs/auth_api/

## Konkrete Codex-Aufgaben zur Behebung

### Aufgabe 1

```text
Haerte zuerst das Messinstrument, bevor weitere Matrixbreite bewertet wird: Zerlege `tessera_spike` in die 8 spezifizierten Services, lagere das Harness aus dem grossen String in echte Dateien aus, erzeuge eine valide `services.yaml`, entferne alle blocking `read_text`/`write_text`/`open`-Aufrufe aus dem HA-Event-Loop via Executor/HA-Store/async Helper, und belege nach einem neuen Lauf, dass keine `Detected blocking call`-Warnungen aus `tessera_spike` verbleiben. Keine Secrets, `/Volumes/config` nur read-only.
```

### Aufgabe 2

```text
Fuehre D5 als hartes Recovery-Gate aus: korrumpiere den Tessera-Store oder erzwinge eine Setup-Exception, beweise Boot-Rescue/Restore ohne gesunden Tessera-Start, verifiziere per Re-Read den Systemzustand, und teste explizit, dass Tessera-managed User nicht in `system-users` verbleiben oder dorthin zurueckfallen.
```

### Aufgabe 3

```text
Vervollstaendige D3/D6/D7/D8 gegen eine deterministische Seed-Fixture: REST+WS+Service, Registry-WS, Logbook, History, render_template, non-entity Service, Systemkontext, `return_response changed_states`, `entity_id: all` mit Vor-/Nach-Zustand erlaubt/verboten, echter non-admin-LLAT mit Rotation/Revocation. Alle Tokenwerte redakten.
```

### Aufgabe 4

```text
Ersetze D9 Static Scan durch Runtime-Klassifikation je Custom Component. Bis Runtime-Beleg gilt jede Komponente mit Service/HTTP/WS als `UNKNOWN_BLOCK_ENFORCE`. Ergebnis je Komponente: `ALLOW / DENY / TIER-2 / UNKNOWN_BLOCK_ENFORCE` mit kurzer Begruendung und Beleg.
```

### Aufgabe 5

```text
Fuehre D11/D13/D15 als Muss-Gates aus: unsupported HA-Version verweigert Enforce und meldet Reparatur/monitor/off; HACS-Update/Downgrade-Simulation mit Rollback; E2E `off->monitor->enforce->restore`. Danach Go/No-Go-Rubrik explizit tabellarisch mappen.
```

## Finales Urteil

Claudes Spike-Gate-Review: **MODIFY**.

Nicht verwerfen: Die Richtung stimmt, und D1/D2/D4 sind starke positive Signale. Aber die Freigabesprache muss enger werden. Stand jetzt ist nur ein weiterer Phase-0-Haertungslauf freigegeben. Produkt, HACS-Enforce, v1-Enforce und finales Neubau-Go bleiben gesperrt.
