# Gate Review

## Entscheidung

PASS MIT AUFLAGEN

## Kurzbewertung

Der aktuelle Stand ist als **D0-Bootstrap + erster D1-D9-Messlauf** brauchbar und ehrlich reportet: D0 ist gruen, D1/D2/D4 liefern belastbare positive Signale, und der Report erzeugt keine Scheinsicherheit fuer Enforce. Weiterbauen an der Phase-0-Haertung ist moeglich.

Kein Go fuer produktive Nutzung, HACS-Enforce oder v1-Enforce. Mehrere Muss-Anforderungen der konsolidierten Spec sind erst teilweise erfuellt: M2 fordert 8 Harness-Services, M4 fordert REST+WS+Service/Leak-Matrix, M5 fordert D9-Klassifikation, M6 fordert D11/D13/D15. Zudem zeigen die HA-Logs reale Harness-Warnungen durch blockierende Datei-I/O im Event Loop.

## Kritische Punkte

| Bereich | Problem | Auswirkung | Konkrete Korrektur |
|---|---|---|---|
| Produktivfreigabe | Kein kritischer Punkt fuer weiteres Phase-0-Haerten. | Weiterarbeit ist vertretbar; produktive Nutzung bleibt gesperrt. | Keine Enforce-/Produktfreigabe aus diesem Gate ableiten. |

## Hohe Punkte

| Bereich | Problem | Auswirkung | Konkrete Korrektur |
|---|---|---|---|
| Spezifikation M2 / Schnittstellen | Das Harness implementiert nur `tessera_spike.run_spike`, nicht die geforderten 8 Services `ensure_group`, `set_group_policy`, `set_user_groups`, `flush_auth_store`, `invalidate_user`, `snapshot`, `restore`, `probe_check_entity`. | Die Messung ist weniger modular, einzelne Adapter-Vertraege sind nicht isoliert pruefbar, Wiederholbarkeit je Operation ist eingeschraenkt. | Harness in die 8 spezifizierten Services aufteilen und jeden Service separat mit PASS/PARTIAL/FAIL belegen. |
| Spezifikation M4 / Testabdeckung | D3/D6/D7/D8 sind nur PARTIAL: kein WS-Test, keine komplette Leak-Matrix, kein Logbook/Registry/History, kein Systemkontext, kein `return_response changed_states`, keine echte LLAT-Rotation. | Die zentrale Aussage "REST+WS+Service" ist noch nicht belegt; Risiken bei view-Leaks und Service-Bypaessen bleiben offen. | D3/D6/D7/D8 um WS-Client, Registry-WS-Reads, Logbook REST+WS, History, `render_template`, `return_response`, non-entity Service und echten LLAT-Lifecycle erweitern. |
| D5 Recovery | `public_async_update_user_restore_available` ist belegt, aber Boot-Rescue bei kaputtem Store/Setup-Exception wurde nicht ausgefuehrt. | Rescue-Vertrag ist nicht bewiesen; Lockout-Szenario bleibt offen. | Dev-only Korruptions-/Setup-Exception-Test bauen und beweisen, dass Restore ohne gesunden Tessera-Start greift. |
| Spezifikation M5 / D9 | D9 ist nur statischer Scan von 14 Custom Components; keine Klassifikation `ALLOW / DENY / TIER-2 / UNKNOWN_BLOCK_ENFORCE`. | D9 kann keine Enforce-Entscheidung stuetzen; Custom-Service-/WS-/HTTP-Risiko bleibt unbekannt. | Pro Custom Component services.yaml, HTTP/View/Panel/WS und Runtime-Verhalten klassifizieren; Ergebnis je Komponente in die vier Klassen mappen. |
| Logs / Betriebsfaehigkeit | HA-Logs melden blockierende `read_text`/`write_text`/`open`-Aufrufe im Event Loop des Harness. | Der Spike funktioniert, aber das Messinstrument verletzt HA-Async-Regeln und erzeugt Lognoise; spaetere Messungen koennen dadurch verfaelscht oder instabil werden. | Datei-I/O im Harness ueber Executor/HA-Store/async Helper auslagern; danach Log erneut pruefen. |
| Seed / Datenmodell | Seed-Fixture ist sehr schmal: zwei `input_boolean`, eine state-only Entity; keine Area/Device-Registry, keine hidden/disabled, keine mehreren Domains wie Sensor/Cover/Camera/Lock. | Resolver-/Domain-/Registry-Verhalten aus Spec wird nicht getestet; D3/D6/D7 bleiben strukturell begrenzt. | Deterministische Seed-Fixture mit Areas, Devices, mehreren Domains, hidden/disabled und state-only Fall anlegen. |

## Mittlere Punkte

| Bereich | Problem | Auswirkung | Konkrete Korrektur |
|---|---|---|---|
| Evidence-Schema | D0-Evidence ist secretfrei, aber nicht voll nach Spec: kein expliziter Exit-Code, keine PASS/PARTIAL/FAIL-Aufschluesselung je 12 D0-Gate-Punkt, Snapshot nur kompakt. | Reviewbarkeit ist ok, aber nicht voll maschinenlesbar fuer spaetere Gates. | D0-Evidence um `exit_code`, `gate_results[]`, Vor-/Nach-Snapshot und Abbruchgrund normalisieren. |
| Report / Core-Anker | Core-Anker sind genannt, aber ohne konkrete `file:line`-Zeilen. | Re-Review muss Quellen erneut suchen; Belegqualitaet niedriger als gefordert. | Report um konkrete HA-Core-Datei-/Zeilenanker fuer Auth-Store, Permissions, REST API und Service-Pruefung erweitern. |
| D2 Interpretation | D2 PASS zeigt Wirkung nach manuellem `test_user.invalidate_cache()`, aber noch nicht, ob reine Policy-Mutation automatisch invalidiert. | Der deterministische Invalidierungspfad ist nur teilweise geklaert. | Separaten Negativ-/Positivtest: Policy mutieren ohne invalidate, messen; dann definierte Invalidierung anwenden und messen. |
| D6 `entity_id: all` | `entity_id: all` ergibt 200, aber der Report sagt nicht, welche Entities tatsaechlich ausgewaehlt/geaendert wurden. | 200 allein beweist nicht, dass nur erlaubte Entities betroffen waren. | Vor-/Nach-Zustand erlaubter und verbotener Entity bei `entity_id: all` messen. |
| D0 Isolation Evidence | Docker-Isolation ist geprueft, aber Mount-Source wird in der Evidence nicht ausgewiesen. | Geringere Nachvollziehbarkeit, auch wenn Type/Name korrekt sind. | Sanitized Evidence um Mount-Source-Klasse oder Hash/Prefix `docker-volume` ergaenzen, ohne Hostgeheimnisse. |
| Harness-Doku | Tooling ist in einem grossen Skript mit eingebettetem Harness. | Wartbarkeit sinkt; gezielte Reviews werden schwerer. | Harness-Dateien in `tools/tessera_spike/harness/` auslagern und vom Orchestrator kopieren lassen. |

## Niedrige Punkte

| Bereich | Problem | Auswirkung | Konkrete Korrektur |
|---|---|---|---|
| Imports | `os`, `shutil`, `textwrap` wirken ungenutzt. | Kleiner Wartbarkeits- und Lesbarkeitsverlust. | Unbenutzte Imports entfernen. |
| HA services.yaml | Log meldet fehlende/ungueltige `services.yaml` fuer `tessera_spike`. | Funktional nicht blockierend, aber unnoetiger Lognoise. | Minimal valide `services.yaml` fuer den Harness mit `run_spike` bzw. spaeter 8 Services schreiben. |
| Git-Status | `git status` war nicht pruefbar, weil dieses Verzeichnis kein Git-Repo ist. | Keine Aussage zu uncommitted Changes moeglich. | Falls Versionskontrolle relevant ist, im eigentlichen Repo oder Artefaktordner pruefen. |

## Positive Beobachtungen

- D0 bricht fail-closed bei falscher Target-Isolation ab; der erste Fehlversuch hat das tatsaechlich bewiesen.
- Fresh-Baseline-Allowlist fuer HA 2026.6.4 wurde korrekt angewandt.
- Recreate-Proof wurde ausgefuehrt; `ha-tessera-dev` laeuft isoliert auf `ha-tessera-dev-config`, Port 8124.
- Keine Secret-Matches in Report, Evidence JSON, Spike JSON oder Tooling gefunden.
- Der Lauf hat einen wichtigen Architekturpunkt empirisch bestaetigt: User in `system-users` ueberstimmen restriktive Tessera-Policies additiv; managed User muessen aus `system-users` raus.
- D1 Restart-Survival, D2 explizite Cache-Invalidierung und D4 Union/Restore sind als positive Signale verwertbar.
- Der Report sagt klar: **kein Enforce-Go**.

## Nicht prüfbare Punkte

- Echte LLAT-Rotation und Live-Token-Inventar wurden nicht geprueft.
- D10 CM5-`.storage/auth`-Benchmark wurde nicht geprueft.
- D12 OIDC/AuthentiK-`groups`-Claim wurde nicht geprueft.
- Unsupported-Version-Gate D11, HACS-Update-Governance D13 und E2E `off→monitor→enforce→restore` D15 wurden nicht ausgefuehrt.
- ACM-`set_auths.py`-Zeilen wurden in diesem Lauf nicht belegt.
- Runtime-Klassifikation der 14 Custom Components wurde nicht ausgefuehrt.

## Konkrete Codex-Aufgaben zur Behebung

### Aufgabe 1

```text
Überarbeite `tools/tessera_spike/d0_preflight_spike.py` so, dass das in-process Harness die 8 spezifizierten Services bereitstellt: ensure_group, set_group_policy, set_user_groups, flush_auth_store, invalidate_user, snapshot, restore, probe_check_entity. Lagere das Harness aus dem String in echte Dateien unter `tools/tessera_spike/harness/custom_components/tessera_spike/` aus, inklusive gültiger `services.yaml`. Führe den D0-Lauf erneut aus und schreibe aktualisierte Evidence/Report-Artefakte. Keine Secrets ausgeben, `/Volumes/config` nur read-only.
```

### Aufgabe 2

```text
Erweitere den D1-D5-Teil des Tessera-Spikes: D2 muss getrennt messen (a) Policy-Mutation ohne Cache-Invalidierung, (b) definierte Invalidierung, (c) Persist + Restart. D5 muss einen Dev-only Boot-Rescue-Test mit absichtlich kaputtem Tessera-Store oder Setup-Exception ausführen und Restore-to-native ohne gesunden Tessera-Start belegen. Reportiere PASS/PARTIAL/FAIL mit konkreten HA-Core-Datei-/Zeilenankern.
```

### Aufgabe 3

```text
Erweitere D3/D6/D7/D8 um die fehlende Runtime-Matrix: WebSocket-Client für get_states/call_service/Registry-Reads, Logbook REST+WS, History, render_template, return_response changed_states, non-entity Service und entity_id:all Vor-/Nach-Zustand. Erzeuge einen echten Dev-LLAT oder dokumentiere sauber, warum nur ein normaler headless Token verwendet wurde. Keine Tokenwerte in Logs, Reports oder Shell-History.
```

### Aufgabe 4

```text
Baue eine deterministische Seed-Fixture für den Dev-Container: Areas, Devices, mehrere Domains (light/sensor/cover/camera/lock oder äquivalente HA-Testdomains), je eine erlaubte und verbotene Entity, state-only Entity, hidden und disabled Fall, mindestens ein entity-component Service und ein bewusst unsicherer Dev-only non-entity Service. Wiederhole D3/D6/D7 gegen diese Fixture.
```

### Aufgabe 5

```text
Ersetze D9 Static Scan durch eine belastbare Custom-Component-Klassifikation. Lies `/Volumes/config/custom_components` read-only, klassifiziere jede Komponente mit Services/HTTP/View/Panel/WS nach ALLOW/DENY/TIER-2/UNKNOWN_BLOCK_ENFORCE, und belege mindestens die Komponenten mit `services.yaml` zusätzlich durch Dev-Runtime-Proben oder markiere sie bewusst UNKNOWN_BLOCK_ENFORCE. Keine finale Live-ALLOW nur aus statischer Analyse ableiten.
```

### Aufgabe 6

```text
Normalisiere das Evidence-Schema: D0 muss `exit_code`, `gate_results[]` für alle 12 Gate-Punkte, Vor-/Nach-Snapshot, Secret-Redaction-Status und Abbruchgrund enthalten. Der Spike-Report muss konkrete HA-Core `file:line`-Anker, PASS/PARTIAL/FAIL je D1-D15 und eine maschinenlesbare JSON-Summary enthalten.
```
