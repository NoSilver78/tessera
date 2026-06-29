# Gate Review — Tessera Phase-0 Spike (D1–D9)

> **OBSOLETE / ersetzt:** Dieses frühe Claude-Gate wurde durch
> `reports/welle-b-gate-2026-06-29.md` und den anschließenden Welle-B-Fix
> überholt. Aussagen zu D5, D4/No-Lockout, D12 und Enforce-Go sind nicht mehr
> als aktueller Gate-Stand zu verwenden.

Stand 2026-06-29 · Modus: **Gate-/Auditmodus** · Geprüft: `tessera-spike-report-2026-06-29.md` (+ D0-Evidence) gegen Spec + Go/No-Go-Rubrik

## Entscheidung
**PASS MIT AUFLAGEN**

Kein FAIL — nichts ist fehlgeschlagen, der Risikokern ist bewiesen. Kein blankes PASS — die Breite (D3/D5/D6/D7/D8/D9) ist bewusst unvollständig und bildet die Phase-1-Härtungsmatrix.

## Kurzbewertung
Der Spike beantwortet die **eine existenzielle Frage** des Projekts **positiv**: Der **private Auth-Store-Schreibpfad funktioniert** (`_groups` + `_data_to_save()` + `async_save()`) — Gruppe, Policy und User-Bindung **überleben den HA-Restart** (**D1 PASS**), reine Policy-Änderung **wirkt nach explizitem `invalidate_cache()`** ohne Restart (**D2 PASS**), und `group_ids`-**Union + Restore via public `async_update_user`** funktioniert **ohne Replace-Lockout** (**D4 PASS**). REST/Service-Enforcement greift (verboten → 401, nicht in `state_list`). Damit ist der Show-Stopper, der ein No-Go bedeutet hätte, **vom Tisch → Neubau ist bestätigt machbar**. D3/D5/D6/D7/D8/D9 sind **ehrlich PARTIAL** (erster Lauf; WS, volle Leak-Matrix, non-entity/return_response, echter LLAT, Korrupt-Store-Rescue, Runtime-Klassifikation offen — nichts davon fehlgeschlagen, nur nicht gemessen). Codex' „Go für Härtung ja, Enforce/Produkt nein" deckt sich mit der Rubrik.

## Kritische Punkte
(keine — kein Dimensionsergebnis ist FAIL; der Kern-Schreibpfad ist bewiesen)

## Hohe Punkte — = Phase-1-Härtungsmatrix, vor Enforce zwingend
| Bereich | Problem | Auswirkung | Konkrete Korrektur |
|---|---|---|---|
| D3 WS | WebSocket nicht getestet (`ws_tested:false`) | view/operate-Grenze über WS — Haupt-Leseweg — unbelegt | WS `subscribe_entities`/`get_states`/`call_service` erlaubt/verboten messen |
| D7 Leak-Matrix | nur render_template; logbook/registry/history/WS offen | „view ist begrenzt"-Kernaussage unbelegt → Produktversprechen nicht absicherbar | volle Matrix: logbook REST+WS, Registry-WS (entity/device/area/floor/label/category), history |
| D6 Service | non-entity + return_response/changed_states offen | Service-Bypass + Response-Leak ungeprüft | non-entity (mqtt/python_script) + REST `return_response` `changed_states` messen |
| D5 Rescue | Korrupt-Store-Boot-Rescue nicht ausgeführt (`boot_rescue_corruption_tested:false`; = D0-Auflage #2) | Fail-safe bei kaputtem Tessera unbewiesen — sicherheitskritischster Pfad | Store absichtlich korrumpieren → Boot-Rescue greift → Re-Read beweist System-Zustand |
| D8 LLAT | echte LLAT-Rotation nicht durchgeführt (`llat_created:false`) | Long-Lived-Token-Risikoklasse unbelegt | echten non-admin-LLAT → D7 headless → Rotation/Revocation |
| D9 Runtime | nur statischer Scan; Runtime-Klassifikation offen | Custom-Service-Enforce-Lücken unklar | je Komponente Runtime → ALLOW/DENY/TIER-2/UNKNOWN_BLOCK_ENFORCE |
| D11/D13/D15 | nicht gelaufen | Version-Gate, HACS-Update-Governance, E2E-Lifecycle ungeprüft | nachziehen (kleine eigene Läufe) |
| Seed-Evidence | weiterhin kein deterministisches Seed-Inventar (D0-Auflage #1) | D3/D6/D7 messen evtl. zufällige Verfügbarkeit statt RBAC | Seed-Fixture-Inventar explizit evidenzieren |

## Mittlere Punkte
| Bereich | Problem | Auswirkung | Konkrete Korrektur |
|---|---|---|---|
| D2 Lesbarkeit | `allowed_read_after_policy_change:false` unerläutert | PASS aus Roh-JSON schwer nachvollziehbar | explizit: getestete Policy-Richtung (Entzug?) + erwartetes vs. gemessenes Verhalten |
| D7 render_template 401 | render_template gibt für verbotene Entity **401** statt Leak — überraschend (Konzept nahm Leak an) | könnte view-Garantie **stärken** ODER Probe nutzte falschen Token/Pfad | in voller Matrix verifizieren: non-admin-User-Token? leakt template wirklich nicht? |
| Adapter-Schnitt | 4-Verträge-Beleg nicht explizit | Architektur-Validierung offen | Schnitt (AuthPolicyStore/UserBinding/PermissionProbe/Recovery) als gemessen markieren |

## Niedrige Punkte
| Bereich | Problem | Auswirkung | Konkrete Korrektur |
|---|---|---|---|
| Rubrik-Mapping | Verdikte ohne Mapping auf Go/No-Go-Rubrik | Entscheidung manuell abzuleiten | kurze Rubrik-Tabelle (erfüllt/offen) ergänzen |
| ACM-Beleg | `set_auths.py`-Zeilen nicht zitiert | Regression-Orakel undokumentiert | ACM-Schreibpfad-Zeilen nachreichen |

## Positive Beobachtungen
- **Das existenzielle Risiko ist aufgelöst:** privater Schreibpfad funktioniert + **überlebt Restart** (D1) — genau die Frage, die ein No-Go bedeutet hätte. **Neubau GO.**
- **D2:** reine Policy-Mutation wirkt nach **explizitem** `invalidate_cache()` ohne Restart — deterministischer Invalidierungspfad gefunden.
- **D4:** volle `group_ids`-Union + Restore via public API — **kein Replace-Lockout**.
- **REST/Service-Enforcement greift** (verboten → 401, nicht in `state_list`).
- **Core-Anker bestätigt:** `auth_store` `_groups`/`_data_to_save`/`async_save` · `models.invalidate_cache` · `async_update_user` · `http/auth` system_generated.
- **Ehrliche PARTIAL-Kennzeichnung** — keine Scheinsicherheit; jedes Nicht-Getestete benannt.
- **Secrets sauber**, dev-only, `/Volumes/config` read-only.

## Nicht prüfbare Punkte
- **D10** (CM5-Benchmark) + **D12** (OIDC-groups) — korrekt als Mensch-Pakete ausgeklammert.
- Detail-JSON `tessera-spike-result-2026-06-29.json` nicht einzeln geöffnet (Report inlinet die Kern-Probes; Verdikte daraus belegt).

## Konkrete Codex-Aufgaben zur Behebung
Drei kleine, bounded Round-2-Härtungs-Tasks → danach erneutes Gate.

### Aufgabe 1 (hoch — Leseweg-/Leak-Matrix: D3-WS, D6, D7)
```text
Implementiere ausschließlich die folgende Aufgabe.

Aufgabe:
Vervollständige die Tessera-Spike-Leseweg-/Leak-Matrix für einen non-admin-Token gegen ha-tessera-dev (D3-WS, D6, D7).

Betroffene Dateien/Module:
- tessera_spike-Harness (Probe-Services); Spike-Report/Result-JSON.

Regeln:
- Keine Architekturänderungen, keine Features außerhalb der Messung. Nur ha-tessera-dev; /Volumes/config read-only; keine Secrets/Tokenwerte. Bestehende 8 Services beibehalten.

Erwartete Umsetzung:
- D3-WS: subscribe_entities/get_states/call_service für erlaubte+verbotene Entity über WebSocket (Status/Sichtbarkeit).
- D6: non-entity-Service (mqtt.publish/python_script) + REST call_service mit return_response → changed_states verbotener Entities geleakt?
- D7: render_template (explizit non-admin-User-Token, Pfad dokumentieren), logbook REST+WS, Registry-WS (entity/device/area/floor/label/category), history — je: verbotene Entity geleakt ja/nein.

Tests/Linter:
- je Probe Assertion erlaubt-sichtbar / verboten-blockiert; Ergebnis als Matrix.

Definition of Done:
- D3-WS/D6/D7 vollständig (kein *_tested:false mehr); render_template-401-Befund verifiziert/erklärt; keine Scope-Ausweitung; Risiken benannt.

Nach Abschluss berichten: geänderte Dateien, Zusammenfassung, Checks+Ergebnis, offene Annahmen.
```

### Aufgabe 2 (hoch — Recovery härten: D5 Korrupt-Store-Rescue + ausgeführter Restore)
```text
Implementiere ausschließlich die folgende Aufgabe.

Aufgabe:
Härte und beweise den Recovery-Pfad (D5 Korrupt-Store-Boot-Rescue + real ausgeführter Restore in D4/D5).

Betroffene Dateien/Module:
- RecoveryController-Primitive / tessera_spike snapshot+restore; Spike-Report/Result-JSON.

Regeln:
- Keine Architekturänderungen; nur ha-tessera-dev; keine Secrets. Recovery darf NICHT vom gesunden Tessera-Store/Panel abhängen.

Erwartete Umsetzung:
- Tessera-Store absichtlich korrumpieren bzw. Setup-Exception erzwingen → Boot-Rescue greift → Mitgliedschaften via public async_update_user zurück → Re-Read beweist System-Zustand (system_generated unberührt).
- Restore real ausführen, nicht nur Primitive verdrahten.

Tests/Linter:
- Re-Read-Assertions vor/nach Korruption+Rescue (Counts/Flags, keine Werte).

Definition of Done:
- boot_rescue_corruption_tested:true + bestanden; Restore ausgeführt belegt; keine Scope-Ausweitung; Risiken benannt.

Nach Abschluss berichten: geänderte Dateien, Zusammenfassung, Checks+Ergebnis, offene Annahmen.
```

### Aufgabe 3 (mittel — D8 LLAT-Lifecycle + D9 Runtime + D11/D13/D15)
```text
Implementiere ausschließlich die folgende Aufgabe.

Aufgabe:
Schließe D8 (echter LLAT-Lifecycle), D9 (Runtime-Komponenten-Klassifikation) und die Gates D11/D13/D15.

Betroffene Dateien/Module:
- tessera_spike-Harness; Spike-Report/Result-JSON.

Regeln:
- Keine Architekturänderungen; nur ha-tessera-dev; keine Secrets/LLAT-Werte im Report.

Erwartete Umsetzung:
- D8: echten non-admin-LLAT erstellen → D7-Leseweg headless → Rotation/Revocation; LLAT-Wert nie loggen.
- D9: je Custom-Component Runtime-Urteil ALLOW/DENY/TIER-2/UNKNOWN_BLOCK_ENFORCE (entity vs non-entity, User-Kontext, WS/HTTP-Gate).
- D11: unsupported HA-Version → refuse enforce + Repairs + monitor/off. D13: HACS-Update/Downgrade-Sim. D15: E2E off→monitor→enforce→restore.

Tests/Linter:
- je Dimension PASS/PARTIAL/FAIL mit Beleg.

Definition of Done:
- D8/D9/D11/D13/D15 nicht mehr offen; Urteile je Komponente dokumentiert; keine Scope-Ausweitung; Risiken benannt.

Nach Abschluss berichten: geänderte Dateien, Zusammenfassung, Checks+Ergebnis, offene Annahmen.
```

---
**Gate-Fazit:** Phase-0-Spike = **PASS MIT AUFLAGEN**. Der Schreibpfad-Risikokern ist **positiv aufgelöst → Tessera ist baubar, Neubau bestätigt**. Vor jedem Enforce-Schritt sind die Härtungs-Auflagen (Round 2: Aufgaben 1–3) zu schließen. Nächstes Gate: der Round-2-Härtungsreport.
