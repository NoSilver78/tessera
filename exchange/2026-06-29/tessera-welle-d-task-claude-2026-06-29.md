# Codex-Aufgabe — Spike Welle D (D9: Custom-Component-Klassifikation)
Von Claude · 2026-06-29 · Spec: `docs/spec-phase0.md` (M5, Z. 112) · **Branch `welle-d/component-class` (von `main`, NACH Welle C) → PR**

## Ziel
Je relevante Custom-Component ein Urteil **ALLOW / DENY / TIER-2 / UNKNOWN_BLOCK_ENFORCE** mit **Laufzeitbeleg** — *keine* finale Live-`ALLOW` nur aus statischer Analyse (Spec Z. 112).

## Vorgehen
- **Komponenten-Liste als Eingabe** (nicht live `/Volumes/config` scannen — read-only, kein Live-CM5). Quelle: die HACS-/Custom-Components, die für Tessera-Enforce relevant sind (registrieren Services / greifen auf Entities zu). Liste im Bericht explizit machen.
- Im **Dev-Container** zur Laufzeit beobachten: Registriert die Komponente Services **ohne User-Kontext** (`user_id=None`)? Umgeht sie `check_entity`? Eigene Permission-Logik? → Klassifikation je Komponente.
- **Klassifikations-Regeln:**
  - `ALLOW` — respektiert `check_entity`/User-Kontext (Laufzeitbeleg).
  - `DENY` — bekannt unsicher.
  - `TIER-2` — braucht Zusatz-Enforcement (z.B. CI-geprüft).
  - **`UNKNOWN_BLOCK_ENFORCE`** — sicherer **fail-closed** Default für alles, was zur Laufzeit **nicht** verifiziert werden kann.

## Betroffene Dateien
`spike/tools/tessera_spike/...` (Klassifikations-Probe) · `spike/evidence/*` · `spike/reports/*`. **NICHT** `custom_components/tessera`.

## Regeln
Nur `ha-tessera-dev` · kein `/Volumes/config`-Live-Scan · **ehrlich**: lieber `UNKNOWN_BLOCK_ENFORCE` als geratenes `ALLOW`.

## DoD
Klassifikations-Matrix (je Komponente Urteil + Laufzeitbeleg + `file:line`) · `UNKNOWN_BLOCK_ENFORCE` fail-closed als Default · CI grün · **PR mit Bericht** → **Re-Gate**.
