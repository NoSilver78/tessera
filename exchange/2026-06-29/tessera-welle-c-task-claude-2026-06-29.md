# Codex-Aufgabe — Spike Welle C (D3/D6/D7/D8: Enforcement + Leak-Matrix)
Von Claude · 2026-06-29 · Spec: `docs/spec-phase0.md` (M4, Zeilen 110–112) · **Branch `welle-c/enforce-matrix` (von `main`) → PR**

## Ziel
Die Runtime-Durchsetzungs- und Leak-Dimensionen von **PARTIAL → belastbar** bringen. **Leitprinzip wie Welle B: ehrlich messen, kein falsches PASS.** Alles nur gegen den isolierten `ha-tessera-dev` (Isolation-Gate), **kein** `/Volumes/config`, **kein** Live-CM5. Evidence tokenfrei.

## Dimensionen
**D3 — check_entity erlaubt/verboten × READ/CONTROL über REST + WS + Service.**
- **WS-Kanal ergänzen** (fehlt aktuell). Für dieselbe Policy: `internal == REST == WS == Service` konsistent erlauben/verbieten.
- DoD: **D3 PASS (entity-targeted)** wenn alle Kanäle konsistent; sonst PARTIAL mit benannter Lücke.

**D6 — Service-Matrix.**
- entity / `entity_id:all` / non-entity Services · `return_response`-Leak · WS-Response · **Systemkontext** (`user_id=None` / Automation / Script / Assist).
- DoD: **D6 PASS (entity-targeted)** wenn entity-Services korrekt geprüft **und** die non-entity/`return_response`/Systemkontext-Fälle dokumentiert sind (welche umgehen `check_entity` → **Enforce-Lücke benennen**).

**D7 — Leak-Matrix non-admin (UI + LLAT) — DOKUMENTIEREN (nicht zwingend PASS).**
- Vektoren: `render_template` · logbook (REST+WS) · **alle** Registry-Reads (entity/device/area/floor/label/category) · history.
- Pro Vektor Laufzeitbeleg: leakt `view`-Info trotz fehlendem Grant? → Matrix **ALLOW / LEAK / BLOCKED**.
- DoD: **vollständige Leak-Matrix** — sie fundiert die Scope-Entscheidung (hard-`view` nicht untrusted-grade → `operate/control` ist die echte Grenze; Spec Z. 39/83).

**D8 — LLAT headless.**
- Echter Long-Lived-Access-Token-Lifecycle: erstellen → headless nutzen → rotieren/revoken → Wirkung auf `check_entity`.
- DoD: **D8 PASS** wenn LLAT-Pfad dem UI-Pfad in der Durchsetzung gleicht; sonst PARTIAL mit Befund.

## Betroffene Dateien
`spike/tools/tessera_spike/harness/custom_components/tessera_spike/__init__.py` (Probe-Matrix erweitern) · `spike/tools/tessera_spike/d0_preflight_spike.py` (Gate-Logik D3/D6/D7/D8 **gemessen**, nicht hardcoded) · `spike/evidence/*` · `spike/reports/*`. **NICHT** `custom_components/tessera` (Produkt bleibt enforce-frei, ADR 0004).

## DoD
D3/D6 **PASS (entity-targeted) oder ehrlich PARTIAL** · D7 **vollständige Leak-Matrix** · D8 PASS/PARTIAL · jede Gate-Zelle auf gemessene Booleans rückführbar (kein Streu-Grün) · CI grün · **PR mit Bericht** (je Dimension Verdikt + `file:line` + Zahlen) → **Re-Gate per Agenten-Panel**.
