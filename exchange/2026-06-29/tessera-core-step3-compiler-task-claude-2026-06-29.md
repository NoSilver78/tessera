# Codex-Aufgabe — Phase-1 Schritt 3: Compiler (Store → native Policy)
Von Claude · 2026-06-29 · Spec: `docs/spec-phase1-core.md` (Schritt 3) · **Branch `core/phase3-compiler` (von `main`) → PR**

## Aufgabe
Implementiere `custom_components/tessera/compiler.py`: projiziert den **Store** (config + policy) in **native HA-Gruppen-Policies** (`PolicyPermissions`-Form) — **rein, deterministisch, idempotent**. Das ist die PDP-Stufe (Store=SoT → Compiler → native Policy). **Noch kein nativer Write** (das ist Schritt 6/Auth-Adapter) — Schritt 3 liefert die Policy als **In-Memory-Struktur** (Monitor-Mode-tauglich).

## Eingaben
- `config` (Rollen, `membership`, mode) + `policy` (`area_grants`, `entity_overrides`) aus `schema.py`.
- `AreaEntityResolver` (Schritt 2) zum Expandieren **Area → entity_ids**.

## Ausgabe
Pro Rolle die native HA-Policy-Struktur, schema-aware:
`{ role_id: {"entities": {"entity_ids": { "<entity_id>": {"read": true[, "control": true]}, ... }}} }`
- **Niemals bare-`True`**, nie `entities:true`/`domains:true` — nur `{read[,control]}`-Leafs (wie `schema.py` erzwingt).
- **Allow-only:** nur Grants erzeugen; keine Deny-Einträge.

## Regeln / Semantik
- **Entity-Override schlägt Area-Grant** (spezifischer gewinnt).
- Mehrere Area-Grants je Rolle → vereinigen. Area→entity_ids via Resolver.
- **Deterministisch:** stabile Sortierung, gleicher Store ⇒ gleiche Policy (für Idempotenz/Diff).
- Best-Practice: Type-Hints, Google-Docstrings, kein blocking I/O, testbar (Resolver/Registries injizierbar — kein harter HA-Import im Test).

## Betroffene Dateien
`custom_components/tessera/compiler.py` (neu) + `tests/test_compiler.py` (neu). Nichts anderes.

## Tests
- Area-Grant → korrekte entity_ids mit `{read}`/`{read,control}`.
- **Entity-Override** schlägt Area-Grant.
- Mehrere Areas je Rolle vereinigt.
- **Determinismus:** zweimaliges Kompilieren ⇒ identische Struktur.
- **Schema-aware Output:** nie bare-`True` (Assertion).

## Definition of Done
`compiler.py` + Tests · **CI grün** · **PR** mit Bericht (geänderte Dateien · Tests+Ergebnis · Risiken) · keine Scope-Ausweitung. Override-Korrektheit zählt (wie bei Schritt 2) — Gate prüft die Semantik, nicht nur CI.
