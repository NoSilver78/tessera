# Codex Gegenreview — Claude D0-Gate Tessera

Stand: 2026-06-29T07:04:27+0200

Geprueft read-only:
- `outputs/tessera-claude-gate-review-d0-2026-06-29.md`
- `outputs/tessera-gate-review-d0-d1-d9-2026-06-29.md`
- `outputs/tessera-spike-report-2026-06-29.md`
- `outputs/tessera-spike-result-2026-06-29.json`
- `outputs/tessera-phase0-SPEC-2026-06-29.md`
- `tools/tessera_spike/d0_preflight_spike.py`
- Docker-Logs `ha-tessera-dev` read-only

Zwei Gegenpruef-Agenten wurden getrennt eingesetzt:
- Agent A: Spezifikation/Schnittstellen/Testabdeckung
- Agent B: Security/Betrieb/Recovery

## Entscheidung

MODIFY zu Claudes D0-Gate-Review.

Claudes Grundrichtung ist richtig: `PASS MIT AUFLAGEN`, keine Produkt-/Enforce-Freigabe, weiterer Phase-0-Start vertretbar. Aber das Review ist nach dem inzwischen vorliegenden D1-D9-Messlauf zu eng und an zwei Stellen zu lax formuliert. Es sollte nicht als finales D0-GREEN gelesen werden.

## Wichtigste Korrektur

Claude schreibt zugleich `10 der 12 Gate-Punkte voll belegt` und am Ende `D0-GREEN steht`. Das ist widerspruechlich zur Spec: D0-GREEN bedeutet alle 12 Exit-Gate-Punkte gruen. Korrekt ist:

**D0 startfaehig / PASS MIT AUFLAGEN, aber nicht D0-GREEN im strengen Sinn.**

Der D1-D9-Lauf durfte als dev-only Messlauf starten, aber die offenen D0-Auflagen bleiben Gate-relevant und duerfen nicht in der Sprache verschwinden.

## Hohe Punkte

| Bereich | Problem | Auswirkung | Konkrete Korrektur |
|---|---|---|---|
| Gate-Label | Claude nennt trotz `10/12` belegter D0-Punkte `D0-GREEN`. | Erzeugt Scheinsicherheit; spaetere Gates koennten Auflagen als erledigt interpretieren. | Formulierung aendern zu `D0 startfaehig / PASS MIT AUFLAGEN`; D0-GREEN erst nach belegtem Seed-Inventar und Restore/Recreate-/Snapshot-Pfad gemaess Spec. |
| M2 Harness-Schnittstelle | Spec fordert 8 Services; real gibt es nur den monolithischen `tessera_spike.run_spike`. | Adapter-Vertraege und Einzeloperationen sind nicht isoliert pruefbar; Messlauf bleibt weniger belastbar. | Als hohe Auflage ergaenzen: 8 Services `ensure_group`, `set_group_policy`, `set_user_groups`, `flush_auth_store`, `invalidate_user`, `snapshot`, `restore`, `probe_check_entity` implementieren und einzeln belegen. |
| D5 Recovery | Realer Spike zeigt `boot_rescue_corruption_tested: false`; nur Restore-Primitive ist belegt. | Lockout-/Recovery-Vertrag ist nicht bewiesen; fuer Enforce ist das High-Risk. | D5 als eigene hohe Auflage fuehren: kaputten Store/Setup-Exception simulieren und Restore ohne gesunden Tessera-Start beweisen. D4 und D5 getrennt bewerten. |
| Runtime-Matrix | D3/D6/D7/D8 bleiben PARTIAL: kein WS, kein Logbook/History/Registry-WS, kein non-entity Service, kein `return_response changed_states`, keine echte LLAT-Rotation. | Keine belastbare Aussage zur Durchsetzung ueber alle relevanten HA-Transportwege. | Als hohe Folgeauflage aufnehmen: REST+WS+Service/Leak-Matrix vollstaendig ausfuehren und je Pfad PASS/PARTIAL/FAIL berichten. |
| D9 Custom Components | Real nur statischer Scan von `/Volumes/config/custom_components`; keine `ALLOW/DENY/TIER-2/UNKNOWN_BLOCK_ENFORCE`-Klassifikation. | Enforce-Risiko durch Custom Services/HTTP/WS bleibt offen; statische Liste reicht nicht fuer Freigabe. | D9 runtime-faehig klassifizieren; unbekannte Komponenten explizit `UNKNOWN_BLOCK_ENFORCE` statt implizit tolerieren. |
| Harness-Betrieb | Docker-Logs zeigen HA-Warnungen fuer blockierende `read_text`/`write_text`/`open` im Event Loop des Harness. | Messinstrument erzeugt Lognoise und kann Laufzeitverhalten verfaelschen. | Synchrone Datei-I/O im Harness via Executor/HA-Store/async Helper ersetzen; danach Log-Check als Gate-Kriterium. |

## Mittlere Punkte

| Bereich | Problem | Auswirkung | Konkrete Korrektur |
|---|---|---|---|
| Seed | Claude nennt vor allem fehlende Seed-Evidence; der reale Spike zeigt zusaetzlich eine strukturell zu schmale Fixture. | D3/D6/D7 messen nur einen engen `input_boolean`-Ausschnitt. | Seed-Fixture mit Areas, Devices, mehreren Domains, hidden/disabled, state-only und bewusst unsicherem non-entity Dev-Service erstellen. |
| D4/D5 Vermischung | Claude fasst `D4/D5 Restore-to-native` zusammen. Rueckblickend ist D4 als Union/Restore positiv belegt, D5 aber nicht. | Risiko wird unscharf priorisiert. | D4 als PASS-Signal akzeptieren, D5 als High-Auflage isolieren. |
| `system-users` Invariant | Der reale Lauf hat bestaetigt: `system-users` kann restriktive Tessera-Policies additiv ueberstimmen. Claude nennt diesen Security-Invariant nicht. | Managed User koennten ungewollt mehr Rechte behalten. | Invariant aufnehmen: Tessera-managed User muessen aus `system-users` entfernt sein; Gate-Test gegen Rueckfall hinzufuegen. |
| Secrets | Aktuelle Artefakte sind tokenfrei; Claude formuliert aber zu pauschal `Secrets sauber`. Fehlerpfade im Skript werfen teils Response-Bodies. | Bei kuenftigen Failures koennten sensible Werte in Exceptions/Logs landen. | Formulierung praezisieren: `keine Secret-Matches im aktuellen Lauf`; Fehlerpfade mit Redaction vor Exception-Ausgabe haerten. |
| Evidence-Schema | D0-MD ist knapp; Spec fordert Exit-Code, Gate-Results je Kriterium, Vor-/Nach-Snapshot, Abbruchgrund. | Reviewbarkeit bleibt manuell und weniger maschinenlesbar. | Evidence-JSON/MD normalisieren; D0-12-Punkte als strukturierte Matrix ausgeben. |

## Positive Beobachtungen

- Claude hat die wichtigste Richtung getroffen: Kein Enforce-Go, kein Live-/CM5-Write, weitere Phase-0-Haertung statt Produktbau.
- Isolation, Baseline-Allowlist, Onboarding, Token-Redaction und Recreate-Proof sind im aktuellen Lauf belastbare positive Signale.
- Die Seed- und Restore-Auflagen sind fachlich richtig; sie muessen nur breiter und scharf nach D4/D5 getrennt werden.
- Der reale Spike hat wertvolle Evidenz geliefert: D1/D2/D4 sind positive Signale, waehrend D3/D6/D7/D8/D9 bewusst PARTIAL bleiben.

## Nicht pruefbar / Grenzen

- Keine externe Webrecherche war fuer dieses enge Gegenreview erforderlich; lokale Spec, Artefakte und HA-Logs sind primaere Belege.
- Live-CM5, D10, D12, D11/D13/D15 wurden nicht ausgefuehrt und duerfen aus diesem Review nicht freigegeben werden.
- Secretfreiheit wurde ueber die relevanten Artefakte stichprobenhaft/regex-basiert geprueft; das ersetzt keinen vollstaendigen Secret-Scanner ueber alle temporaeren Container-Dateien.

## Konkrete Codex-Aufgaben zur Behebung

### Aufgabe 1

```text
Korrigiere das D0/D1-D9-Gating sprachlich und technisch: Ersetze `D0-GREEN` durch `D0 startfaehig / PASS MIT AUFLAGEN`, solange nicht alle 12 D0-Exit-Punkte strukturiert belegt sind. Normalisiere die D0-Evidence mit `exit_code`, `gate_results[]`, Vor-/Nach-Snapshot und Abbruchgrund. Keine Secrets ausgeben, /Volumes/config nur read-only.
```

### Aufgabe 2

```text
Zerlege das Tessera-Spike-Harness in die 8 spezifizierten Services und entferne blocking I/O aus dem HA-Event-Loop. Lege eine valide `services.yaml` an. Wiederhole den D0/D1-D9-Lauf und belege im Log, dass keine `Detected blocking call`-Warnungen aus `tessera_spike` verbleiben.
```

### Aufgabe 3

```text
Erweitere die Seed-Fixture und Runtime-Matrix: Areas/Devices, mehrere Domains, allowed/forbidden je Domain, state-only, hidden/disabled, entity-component Service, non-entity Service, bewusst unsicherer Dev-only Service. Fuehre D3/D6/D7/D8 mit REST+WS+Service, Registry/Logbook/History/render_template, `return_response changed_states`, Systemkontext und echtem LLAT-Lifecycle aus.
```

### Aufgabe 4

```text
Fuehre D5 als echten Recovery-Gate-Test aus: simuliere kaputten Tessera-Store oder Setup-Exception, beweise Restore-to-native ohne gesunden Tessera-Start, und pruefe explizit, dass managed User nicht in `system-users` verbleiben. D4 separat als Union/Restore-PASS beibehalten.
```

### Aufgabe 5

```text
Ersetze D9 Static Scan durch Custom-Component-Klassifikation je Komponente: `ALLOW / DENY / TIER-2 / UNKNOWN_BLOCK_ENFORCE`. Komponenten mit Services/HTTP/WS muessen Runtime-Belege oder ein bewusstes UNKNOWN_BLOCK_ENFORCE erhalten. Keine finale Enforce-Freigabe aus statischer Analyse ableiten.
```

## Finales Urteil

Claudes Review: **MODIFY**.

Weiterbauen an Phase-0 ist ok. Produkt-/Enforce-Go bleibt klar **NO-GO**. Die naechste saubere Bewegung ist nicht neue Produktlogik, sondern Messinstrument haerten: 8 Services, Seed-Fixture, vollstaendige Transport-/Leak-Matrix, D5-Boot-Rescue und D9-Klassifikation.
