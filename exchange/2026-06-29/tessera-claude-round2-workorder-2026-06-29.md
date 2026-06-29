# Tessera Round-2 Work-Order — Konsolidierung der zwei Gate-Reviews
Stand 2026-06-29 · Modus: Gate-/Auditmodus → Übergabemodus · Input: `tessera-claude-gate-review-spike-…` (Claude) + `tessera-gate-review-d0-d1-d9-…` (Codex)

## 1. Konvergenz (beide unabhängig)
Beide Gate-Reviews = **PASS MIT AUFLAGEN · kein Enforce-Go · Phase-0-Härtung möglich**. Der Schreibpfad-Risikokern bleibt **positiv aufgelöst** (D1/D2/D4 PASS). Kreuzvalidierung bestätigt.

## 2. Codex' Mehrwert — was ich aus dem Report allein NICHT sehen konnte (akzeptiert)
Codex hat Harness-Code + HA-Logs inspiziert. Diese Befunde nehme ich an, sie sind belegt:
- **M2-Lücke (hoch):** Harness ist monolithisch `tessera_spike.run_spike`, **nicht** die 8 spezifizierten Services → der **4-Adapter-Schnitt ist nicht isoliert validierbar**, Wiederholbarkeit je Operation eingeschränkt.
- **Instrument-Defekt (hoch):** HA-Logs melden **blockierende `read_text`/`write_text`/`open` im Event-Loop** des Harness → Async-Regelverstoß; **kann spätere Messungen verfälschen/destabilisieren**.
- **Seed strukturell zu dünn (hoch):** nur 2 `input_boolean` + 1 state-only; **keine Area/Device-Registry, kein hidden/disabled, keine Multi-Domain** (sensor/cover/camera/lock) → D3/D6/D7 strukturell begrenzt.
- **D2-Nuance (mittel):** PASS nur nach **manuellem** `invalidate_cache()`; ob **reine Policy-Mutation automatisch invalidiert**, ist offen.
- **D6 `entity_id:all` (mittel):** 200 beweist **nicht**, dass nur erlaubte Entities betroffen waren — Vor/Nach-Zustand fehlt.
- **Evidence-Hygiene (mittel/niedrig):** kein `exit_code`/`gate_results[]`/`file:line`-Anker; unused imports; fehlende `services.yaml`.

## 3. Neue empirische Bestätigung (load-bearing)
Der Lauf hat eine Konzept-Kernwahrheit **empirisch** belegt (vorher nur quell-belegt): **User in `system-users` überstimmen restriktive Tessera-Policies additiv → managed User MÜSSEN aus `system-users` entfernt werden.** (Konzept-Wahrheit #2 bestätigt.)

## 4. QA-Sequenzierung (mein Beitrag: Instrument + Fundament ZUERST)
Codex' 6 Tasks sind richtig, aber **ohne Reihenfolge**. Kritische Sequenz-Entscheidung: **erst das Messinstrument und die Fixture reparieren, dann breit messen** — sonst misst man mit einem defekten Lineal.
- **D1/D2/D4-PASS bleiben gültig** (struktur-/re-read-verifiziert, nicht timing-sensitiv — der blockierende I/O verfälscht persistente Re-Read-Befunde nicht).
- **ABER D3/D6/D7/D8/D9 NICHT (weiter) messen**, solange (a) der Harness blockierende Event-Loop-I/O hat und (b) die Seed-Fixture dünn ist. Sonst sind die Breiten-Verdikte nicht abnahmefähig.

## 5. Konsolidierter Round-2-Backlog (sequenziert — ersetzt beide Einzel-Listen)

### Welle A — Instrument-Integrität (P0, ZUERST, blockiert B/C)
- **A1** Harness reparieren: blockierende Event-Loop-I/O → Executor/HA-async-Helper, **Log gegenprüfen** (kein I/O-Warning mehr); **in die 8 Services splitten** (ensure_group, set_group_policy, set_user_groups, flush_auth_store, invalidate_user, snapshot, restore, probe_check_entity); in **echte Dateien** `tools/tessera_spike/harness/custom_components/tessera_spike/` + valide `services.yaml`. *(= Codex-Aufgabe 1 + Log-Finding)*
- **A2** **Deterministische Seed-Fixture**: Areas, Devices, Multi-Domain (light/sensor/cover/camera/lock), je 1 erlaubte + 1 verbotene Entity, state-only ohne Registry, hidden + disabled, ≥1 entity-component + 1 bewusst unsicherer non-entity Dev-Service. *(= Codex-Aufgabe 4 + Claude-Seed-Auflage)*

### Welle B — Kern-Lücken (P1, nach A)
- **B1** **D2 drei-Wege**: (a) Policy-Mutation **ohne** invalidate messen, (b) definierte Invalidierung, (c) Persist+Restart — klärt den deterministischen Invalidierungspfad endgültig. *(= Codex-Aufgabe 2-Teil + Claude-D2-Note)*
- **B2** **D5 Korrupt-Store-Boot-Rescue**: Tessera-Store absichtlich korrumpieren/Setup-Exception → Restore-to-native **ohne gesunden Tessera-Start** beweisen. *(= Codex-Aufgabe 2-Teil + Claude-Aufgabe 2)*

### Welle C — Breite gegen echte Fixture (P1, nach A)
- **C1** **D3-WS/D6/D7/D8 Runtime-Matrix**: WS-Client (get_states/call_service/Registry-Reads), Logbook REST+WS, History, render_template (non-admin-Token, **401-Befund verifizieren**), `return_response changed_states`, non-entity Service, `entity_id:all` Vor/Nach, **echter Dev-LLAT** (oder sauber begründen). *(= Codex-Aufgabe 3 + Claude-Aufgabe 1)*

### Welle D — Klassifikation, Gates, Evidence (P2)
- **D1** **D9 echte Klassifikation** je Custom-Component → `ALLOW/DENY/TIER-2/UNKNOWN_BLOCK_ENFORCE` (keine Live-ALLOW aus Statik). *(= Codex-Aufgabe 5 + Claude-Aufgabe 3)*
- **D2** **D11/D13/D15** nachziehen (Version-Gate, HACS-Update-Sim, E2E-Lifecycle). *(= Claude-Aufgabe 3)*
- **D3** **Evidence-Schema normalisieren**: `exit_code`, `gate_results[]` (12 D0-Punkte), Vor/Nach-Snapshot, Abbruchgrund, HA-Core-`file:line`-Anker je D1–D15, maschinenlesbare JSON-Summary. *(= Codex-Aufgabe 6 + Claude-Niedrig)*

## 6. Gate-Status & nächstes Tor
**Phase-0-Spike = PASS MIT AUFLAGEN** (unverändert, beidseitig). **Nächstes Gate nach Welle A+B** (Instrument grün + Kern-Lücken zu) — erst dann lohnt die Breite (Welle C/D). **Enforce-Go erst nach vollständigem Round-2.** Architektur-Entscheidung unverändert: **Neubau** (Schreibpfad bewiesen).

**Empfehlung an Codex:** Welle A zuerst (ein Lauf), dann melden — ich gate-reviewe das Instrument, bevor Breite gemessen wird.
