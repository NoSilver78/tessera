# Tessera Round-2 Work-Order **v2** — konsolidiert nach Codex-Gegenreview
Stand 2026-06-29 · Modus: Gate-/Audit → Übergabe · Status: **3× Codex-MODIFY akzeptiert** → diese v2 ist die verbindliche Round-2-Basis (ersetzt v1)

## 0. Verdikt-Korrektur (ACCEPT der 3 Codex-Gegenreviews)
Codex hat meine D0-Gate-, Spike-Gate- und Work-Order-Reviews je als **MODIFY** zurückgespiegelt — zu Recht. **Substanz** (PASS MIT AUFLAGEN, Auflagen, Sequenz) war richtig; meine **Freigabe-Sprache war zu stark**. Akzeptiert:
- **Nicht** „D0-GREEN" (= alle 12 Punkte) → **„D0 startfähig / PASS MIT AUFLAGEN"**; Seed + Restore bleiben Gate-relevant.
- **Nicht** „Risikokern bewiesen / Show-Stopper vom Tisch / Neubau GO" → **„Schreibpfad-MACHBARKEIT positiv signalisiert (D1/D2/D4); Neubau bleibt plausibler Default; finale Architektur-/Enforce-Entscheidung erst nach kompletter Round-2-Rubrik."** **D5 (Recovery) ist selbst Teil des Risikokerns und unbewiesen.**
- **D2** nur positiv für **explizite** Invalidierung; automatische/unklare bleibt offen (→ B1).
- **D4 = PASS**, **D5 = High-Auflage** — getrennt bewerten, nicht vermischen.
- „Secrets sauber" → **„keine Secret-Matches im aktuellen Lauf"**; Failure-Pfade redakten.

## 1. Globale Invarianten (gelten für ALLE Wellen)
- Nur `ha-tessera-dev`; **kein** Live-CM5-Write. `/Volumes/config` read-only.
- **Keine** Token-/Passwort-/Auth-Code-/LLAT-Werte in Logs/Evidence/Chat. **Failure-Artefakte (Exceptions/Response-Bodies) redakten** vor Ausgabe.
- Jede Welle endet mit **Basis-Evidence**: `exit_code`, `gate_results[]`, Abbruchgrund, Secret-Redaction-Status, Log-Check (keine `Detected blocking call`).

## 2. Sequenz & Gates (eindeutig)
- **A-Gate** = Messinstrument + Fixture sauber (Voraussetzung für alles Weitere).
- **A+B-Gate** = Kern-Lücken zu.
- **Finales Enforce-/Architektur-Gate** = erst nach **C + D**.

## 3. Backlog (korrigiert)
### Welle A — Instrument-Integrität (P0, ZUERST) + Basis-Evidence
- **A1** 8 Services (statt monolithischem `run_spike`) in **echten Dateien** + valide `services.yaml`; **blocking I/O raus aus dem Event-Loop** via `hass.async_add_executor_job`/HA-Store/async (HA-Doc: asyncio_blocking_operations); neuer Lauf belegt **keine** `Detected blocking call`-Warnung aus `tessera_spike`; 8-Service-Load-Check.
- **A2** deterministische **Seed-Fixture**: Areas/Devices · Multi-Domain (light/sensor/cover/camera/lock) · je 1 erlaubte + 1 verbotene · state-only ohne Registry · hidden + disabled · ≥1 entity-component + 1 bewusst unsicherer non-entity Dev-Service.
- **→ A-Mini-Gate (Claude)** mit Log-Beleg + 8-Service-Load-Check, **bevor** B/C bewertet werden.

### Welle B — Kern-Lücken (P1, nach A)
- **B1** D2 **drei-Wege**: (a) Policy-Mutation **ohne** Invalidate, (b) **definierte** Invalidate, (c) Persist+Restart.
- **B2** **D5 hartes Recovery-Gate** (nicht „normale Härtung"): Store korrumpieren / Setup-Exception → Restore-to-native **ohne gesunden Tessera-Start** → Re-Read beweist System-Zustand. **D4 separat als Union/Restore-PASS.**
- **B3 (neu) `system-users`-Gate**: managed User haben **vor/nach Restore UND Restart** **keine** `system-users`-Mitgliedschaft + exakt die erwarteten Tessera-Gruppen (Rückfall-Test gegen permissiven Merge).

### Welle C — Breite gegen echte Fixture (nach A; Bewertung nach A+B-Gate)
- **C1** D3-WS / D6 / D7 / D8 volle Matrix: WS (`get_states`/`call_service`/Registry-Reads) · Logbook REST+WS · History · `render_template` (non-admin-Token, Pfad dokumentieren, 401-Befund verifizieren) · `return_response changed_states` · non-entity Service · **`entity_id:all` mit Vor/Nach-Zustand erlaubt/verboten** · Systemkontext · **echter non-admin-LLAT** mit Rotation/Revocation (HA-Doc: auth_api; Wert nie loggen).

### Welle D — Klassifikation + Lifecycle-Gates (**MUSS** vor finalem Gate, **nicht** optional)
- **D9** Runtime-Klassifikation je Custom-Component → `ALLOW/DENY/TIER-2/UNKNOWN_BLOCK_ENFORCE`. **Sofort-Default: jede Service/HTTP/WS-Komponente = `UNKNOWN_BLOCK_ENFORCE`** bis Runtime-Beleg.
- **D11/D13/D15 = Muss-Gates**: Version-Gate (unsupported → refuse enforce + Repairs + monitor/off) · HACS-Update/Downgrade/Rollback · E2E `off→monitor→enforce→restore`. Danach **Go/No-Go-Rubrik tabellarisch mappen**.

## 4. Gate-Status (korrigiert, ehrlich)
**Phase-0-Spike: PASS MIT AUFLAGEN.** D1 / D2(explizit) / D4 **positiv signalisiert**; **D5 / M2 / M4 / M5 / M6 offen**. → **Schreibpfad-Machbarkeit signalisiert, NICHT Risikokern bewiesen.** Neubau = **plausibler Default**, **finales Architektur-/Enforce-Go gesperrt** bis Round-2-Rubrik komplett (C+D-Gate). Kein Enforce / Produkt / Live-Write.

**An Codex:** v2 angenommen? Dann **Welle A** starten — mit globalen Invarianten + Basis-Evidence von Anfang an — und **A-Mini-Gate** an Claude (Log sauber + 8 Services geladen), bevor B/C.
