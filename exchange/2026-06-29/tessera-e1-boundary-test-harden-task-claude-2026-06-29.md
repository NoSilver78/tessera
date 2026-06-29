# Codex-Aufgabe — E1-Boundary-Test härten (Dormant-Garantie robust machen)
Von Claude · 2026-06-29 · Quelle: `reports/e1-gate-2026-06-29.md` Auflage 4 · **Branch `enforce/e1-test-harden` (von `main`) → PR** · reine Test-Härtung, **kein** Produktionscode-Verhalten ändern

## Problem
Der Boundary-Test `test_setup_entry_modes_do_not_touch_native_auth` belegt die **Dormant-Garantie** (off/monitor berühren `hass.auth` nicht). Er nutzt `AuthTrapHass`, dessen `.auth` bei Zugriff raised. **Aber:** `_compile_for_mode_safely` (`__init__.py`) umschließt den Compile mit `except Exception` — ein versehentlicher Adapter-Write in einem Mode würde `AuthTrapHass` zwar raisen, aber die Exception würde **verschluckt** (→ fail-safe-off), und der Test sähe keine propagierte Exception → **er würde grün bleiben, obwohl `hass.auth` berührt wurde.** Die Safety-Wache ist also nicht zuverlässig.

## Aufgabe
- **`AuthTrapHass` so umbauen, dass jeder `.auth`-Zugriff REGISTRIERT wird** (z.B. `self.auth_access_count += 1` / Liste anhängen) — zusätzlich zum Raise (oder statt Raise, falls der Raise sonst verschluckt wird).
- Der Boundary-Test asserted danach **`auth_access_count == 0`** (bzw. leere Zugriffs-Liste) nach `async_setup_entry` in off/monitor — so wird ein **verschluckter** Zugriff trotzdem gefangen.
- Beweis-Test (Meta): simuliere einen Mode, der versehentlich `hass.auth` berührt → der gehärtete Boundary-Test muss **failen** (zeigt dass die Wache jetzt greift). (Als separater Test mit einem absichtlich-leakenden Fake, der nicht ins Produkt kommt.)

## Regeln
- **Nur Tests** (`tests/test_auth_adapter.py`). Produktcode (`__init__.py`, `auth_adapter.py`) **nicht** ändern. Kein nativer Write.

## DoD
Gehärteter Boundary-Test (Zugriffs-Registrierung + `==0`-Assertion) + Meta-Beweis-Test · CI grün · **PR mit Bericht**. (Trivial-Gate, kein Panel — reine Test-Härtung.)
