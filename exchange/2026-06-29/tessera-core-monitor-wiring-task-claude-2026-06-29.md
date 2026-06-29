# Codex-Aufgabe — Core Monitor-Mode-Wiring (rein lesend, KEIN nativer Write)
Von Claude · 2026-06-29 · ADR 0004 · **Branch `core/monitor-wiring` (von `main`) → PR**

## Aufgabe
Verdrahte den Core end-to-end im **Monitor-Mode**: lade Store → baue Resolver → kompiliere → **logge „was wäre"**. **Kein Write in `hass.auth`/native Policies** (das ist der spätere, gegatete Auth-Adapter).

## Betroffene Dateien
`custom_components/tessera/monitor.py` (neu) + Anpassung `__init__.py` + `tests/test_monitor.py` (neu). Nichts anderes. **Keine** Mutation von `hass.auth`.

## Erwartete Umsetzung
- `monitor.py`: `async def compile_current(store, resolver, *, config=None, policy=None) -> CompiledPolicies` — lädt config+policy aus dem Store (oder nimmt übergebene), baut über `AreaEntityResolver` + `compile_policies` die native In-Memory-Policy.
- `monitor_preview(compiled) -> dict` + ein **Log-Summary** (je Rolle: Anzahl Entities, read/control-Counts) — keine Secret-/Entity-Werte-Flut, nur Zähler/Stichprobe.
- `__init__.py async_setup_entry`: Store laden, `AreaEntityResolver.from_hass(hass)`, kompilieren; **wenn `mode == "monitor"`** → Preview loggen + Ergebnis in `hass.data[DOMAIN][entry_id]["compiled"]` ablegen. **Bei `mode == "off"`**: nichts. **`mode == "enforce"`**: vorerst wie monitor + Warn-Log „enforce noch nicht implementiert (gated)".
- Service **`tessera.recompile`**: erneut kompilieren + Preview loggen (für Inspektion); kein Write.

## Regeln
- **Kein nativer Write, keine `hass.auth`-Mutation** (Enforce ist gegated, ADR 0004).
- Best-Practice: Type-Hints, Google-Docstrings, **kein blocking I/O** (Registry/Store async).
- **Testbar:** Store + Resolver injizierbar (Fakes wie in den bestehenden Tests) — kein harter HA-Import im Test.

## Tests
- compile_current: Store+Resolver(Fakes) → erwartete native Policy.
- Monitor-Preview-Summary korrekt (Counts).
- `mode=off` ⇒ keine Kompilierung/kein Log; `mode=monitor` ⇒ Preview, kein Write.
- (Kein hass.auth wird berührt — ggf. via Fake/Assertion belegen.)

## Definition of Done
`monitor.py` + Wiring + Tests · **CI grün** · **PR** mit Bericht · keine Scope-Ausweitung · **garantiert kein nativer Write** (im Bericht bestätigen).
