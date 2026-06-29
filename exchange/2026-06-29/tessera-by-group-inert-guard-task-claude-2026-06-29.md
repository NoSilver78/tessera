# Codex-Aufgabe — ADR-0005-Durchsetzung: `by_group` v1-inert (Guard + Test + Doku)
Von Claude · 2026-06-29 · ADR `decisions/0005-by-group-v1-inert.md` · **Branch `core/by-group-inert-guard` (von `main`) → PR** · trivial, **kein Panel**

## Kontext
`membership.by_group` wird bereits geparst/validiert/persistiert, aber vom Compiler **nicht** konsumiert (Audit-Befund: `membership` wird von keinem Compile-Pfad gelesen). Mach das **explizit + regressions-geschützt**, damit ADR 0005 durchgesetzt + dokumentiert ist.

## Aufgabe
1. **Compiler-Marker/Guard:** expliziter Kommentar/Konstante im Compiler, dass `membership.by_group` in v1 **nicht** projiziert wird (kein stilles „wirkt schon"). Optional: bei nicht-leerem `by_group` eine Info-/Repairs-Notiz loggen („v1-inert, kommt post-v1").
2. **Test** (`tests/test_compiler.py` o. neu): `membership.by_group = {...}` ändert die kompilierte Policy **nicht** (Output identisch zu leerem `by_group`).
3. **Doku:** `docs/concept.md` §7 als „**v1-inert**" markieren (Pointer auf ADR 0005).

## DoD
Marker/Guard + Test + concept-§7-Markierung · CI grün · **PR mit Bericht**. (Kein nativer Write, reine Compiler-/Doku-Klarstellung.)
