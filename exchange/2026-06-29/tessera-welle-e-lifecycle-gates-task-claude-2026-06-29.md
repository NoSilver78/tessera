# Codex-Aufgabe — Spike Welle E (D11/D13/D15: Version-Gate · HACS-Governance · E2E-Lifecycle)
Von Claude · 2026-06-29 · Spec: `docs/spec-phase0.md` (M6, Z. 113) · **Branch `welle-e/lifecycle-gates` (von `main`) → PR**

## ⚠️ Koordination mit dem parallel laufenden D5-real-Task (PFLICHT)
D5-real und diese Welle E teilen sich **dieselben Spike-Dateien** (`tessera_spike/__init__.py`, `d0_preflight_spike.py`, `spike/evidence/*`, `spike/reports/*`) **und** den Container `ha-tessera-dev`.
- **Container-Läufe NICHT überlappen:** nie beide Spike-Harnesses gleichzeitig gegen `ha-tessera-dev` feuern (d0 recreatet ihn).
- **Merge-Regel:** Wer als **zweites** merged, **rebaset** auf den ersten Stand **und lässt den Spike einmal neu laufen** → eine saubere, gemergte `spike-result.json`/`tessera-spike-report-2026-06-29.md` (kein hand-gemergtes Evidence-JSON).
- Neue Proben als **eigene Funktionen** ergänzen (nicht in D5-Funktionen editieren) → minimiert Code-Konflikte.

## Ziel
Die Lifecycle-/Governance-Dimensionen ehrlich abnehmen. **Leitprinzip wie Welle B/C/D: lieber `PARTIAL`/`BLOCKED` als falsches grünes `PASS`.** Nur `ha-tessera-dev`, kein `/Volumes/config`, kein Live-CM5. Evidence tokenfrei.

## Dimensionen
**D11 — Unsupported-HA-Version → refuse enforce.**
- Simuliere eine nicht unterstützte HA-Version → der Enforce-Pfad muss **verweigern** (Repairs-Issue + Rückfall auf monitor/off), **nie** trotzdem schreiben.
- DoD: D11 PASS wenn version-mismatch nachweislich enforce blockt + sauber auf monitor/off degradiert; sonst PARTIAL.

**D13 — HACS-Update-Governance (Sim/Downgrade/Rollback).**
- Simuliere ein HACS-Update der Komponente → verifiziere Rollback/Restore-Pfad (Policy/State überlebt oder wird sauber wiederhergestellt; keine verwaiste/inkonsistente native Policy).
- DoD: D13 PASS wenn Update→Rollback ohne Lockout/Inkonsistenz gemessen; sonst PARTIAL mit Befund.

**D15 — E2E-Lifecycle `off → monitor → enforce → restore` (enforce-kritisch).**
- Vollständiger Durchlauf **in der Harness** (`tessera_spike` hat die nativen Write-Primitive): off (kein Write) → monitor (Preview, kein Write) → enforce (nativer Write der kompilierten Policy, **volles Gruppen-Superset**, kein Delta) → restore (native Policy sauber zurück, **kein Admin-Lockout**).
- DoD: D15 PASS nur wenn jeder Übergang gemessen **und** restore beweisbar lockout-frei; sonst PARTIAL/FAIL. **Kein falsches grünes Enforce.**

## Betroffene Dateien
`spike/tools/tessera_spike/harness/custom_components/tessera_spike/__init__.py` · `spike/tools/tessera_spike/d0_preflight_spike.py` · `spike/evidence/*` · `spike/reports/*`. **NICHT** `custom_components/tessera` (Produkt bleibt enforce-frei, ADR 0004).

## DoD
D11/D13/D15 PASS **oder ehrlich PARTIAL/BLOCKED** (kein falsches PASS) · Gate-Zellen gemessen (kein Streu-Grün) · CI grün · **PR mit Bericht** → **Re-Gate per Agenten-Panel** (D15 ist enforce-kritisch).
