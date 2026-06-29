# Codex-Aufgabe — Finding #3: Widerspruchs-Leaf-SoD-Bypass schließen (MUSS vor E3)
Von Claude · 2026-06-29 nacht · Quelle: holistisches Foundation-Security-Audit (`reports/overnight-2026-06-29.md`) · **Branch `enforce/fix-contradictory-leaf` (von `main`) → PR** · NON-SCHARF (Schema/Linter/Tests) · **security-relevant**

## Problem (MEDIUM, heute erreichbar)
Der Leaf `{read:False, control:True}` ist widersprüchlich, und **drei Module interpretieren ihn verschieden:**
- **Schema** akzeptiert ihn (kein `read≤control`-Check; `schema.py:206-227`).
- **Compiler** `_normalize_leaf` koerziert `control⇒read` → exponiert read (read wird True; `compiler.py:86-93`).
- **Linter** `_explicit_false_levels` liest `read:False` **wörtlich** → registriert die Rolle als Read-Restriktor (`linter.py:229-233`) → der Asymmetrie-Guard (`linter.py:143-144`) kollabiert (Rolle in exposing+restricting) → der **Read-Carve-out wird still gedroppt**.
→ **Stiller SoD-Bypass**, der das E3-Apply-Gate (den Linter) passiert. Heute via direktem `.storage/tessera.policy`-Edit erreichbar; der geplante Override-Editor (`concept.md:456`) öffnet ihn breit. **Das gefährlichste Muster — es kompromittiert das Gate, auf das E3 baut.**

## Fix (Variante a — Schema, fail-closed an der frühesten Grenze)
- `_validate_permission_leaf` (`schema.py`) um eine **`read≤control`-Konsistenz** erweitern: wenn `control` is `True` **und** `read` explizit `False` → `TesseraSchemaError` („control impliziert read; die Kombination ist invalid"). (`control:True` ohne `read`-Key bleibt erlaubt — Compiler koerziert das korrekt.)
- **Regressionstest** mit GENAU dem Repro-Leaf `{read:False, control:True}` → abgelehnt an Schema **+ Store-save + Store-load**.
- **Optional (defense-in-depth):** zusätzlich `_explicit_false_levels` (Linter) NACH der `control⇒read`-Semantik rechnen, damit Linter + Compiler dieselbe Bedeutung teilen — aber der **Schema-Reject ist der primäre Fix**.

## Regeln
Kein nativer Write. Nur `schema.py` (+ optional `linter.py`) + Tests. Best-practice. **Kein legitimer Leaf darf brechen** (`{read:True}`, `{read:True,control:True}`, `{control:True}`-ohne-read, all-false-Removal weiter gültig).

## DoD
`read≤control`-Check + Regressionstest (Repro-Leaf abgelehnt, legitime Leaves grün) · alle bestehenden Tests grün · CI grün · **PR mit Bericht** → **Adversarial-Panel** (schließt der Fix den Bypass vollständig + bricht nichts Legitimes?).
