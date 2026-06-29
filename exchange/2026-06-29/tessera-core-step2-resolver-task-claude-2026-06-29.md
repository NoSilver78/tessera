# Codex-Aufgabe — Phase-1 Schritt 2: Area-Resolver
Von Claude · 2026-06-29 · Spec: `docs/spec-phase1-core.md` (Schritt 2) · **Branch `core/phase2-resolver` (von `main`) → PR wenn fertig**

## Aufgabe
Implementiere `custom_components/tessera/resolver.py`: löst eine **`area_id`** auf die Menge der zugehörigen **`entity_ids`** auf — über **BEIDE** Wege:
- **Device-Area:** Entities, deren Device in der Area liegt (`device.area_id`).
- **Direkte Entity-Area:** Entities mit eigener `entity.area_id`.

Das schließt die native-HA-Lücke (natives `area_ids` löst **nur** `device.area_id` auf → verfehlt direkt-zugewiesene + überschreibende Entities — der Kern-Grund für Tessera).

## Betroffene Dateien
`custom_components/tessera/resolver.py` (neu) + `tests/test_resolver.py` (neu). **Nichts anderes.**

## Regeln
- Best-Practice: Type-Hints, Google-Docstrings, **kein blocking I/O**, async wo nötig.
- **Testbar:** Registries injizierbar (analog `store.py`-Factory-Pattern) — kein harter HA-Import im Test.
- **Override-Semantik:** direkte `entity.area_id` **überschreibt** die Device-Area.
- **Edge-Cases:** Entity ohne Area (gehört zu keiner) · disabled (out-of-scope) vs hidden (in-scope) · Entity mit Device in Area X aber eigener `area_id` Y → gehört zu **Y**.

## Erwartete Umsetzung
- `resolve_area_entities(area_id, ...) -> set[str]` und `resolve_all() -> dict[str, set[str]]` (Area → Entity-IDs; letzteres für den Compiler in Schritt 3).
- Registries als Parameter/injiziert.

## Tests
Device-Area-Auflösung · direkte-Entity-Area · Override (entity-area schlägt device-area) · area-lose Entity · disabled ausgeschlossen / hidden eingeschlossen.

## Definition of Done
`resolver.py` + Tests · **CI grün** (ruff/black/mypy/pytest) · **PR** mit Bericht (geänderte Dateien · Tests+Ergebnis · Risiken) · keine Scope-Ausweitung.

---
**Parallel offen (eigener Branch `welle-a/harness-hardening` → PR):** Spike Welle A laut `exchange/.../tessera-claude-round2-workorder-v2` + ADR 0001 — **zuerst** Runner-Routing-Fix (kein `outputs/`-Write mehr) + Failure-Redaction, **dann** 8 Services + Seed-Fixture.
