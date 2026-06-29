# Codex-Aufgabe — E2: Cross-Rollen-Linter (concept §5.2, Security-HIGH)
Von Claude · 2026-06-29 · Spec: `docs/spec-enforce.md` E2 + `docs/concept.md` §5.2 · **Branch `enforce/e2-cross-role-linter` (von `main`) → PR** · **reine Compile/Preview-Logik, KEIN nativer Write** · nicht von D10 blockiert · gated **VOR** E3

## Warum
Rollenübergreifender **Deny ist strukturell unmöglich** (HA merged most-permissive, concept §5.2). Eine in Rolle A eingeschränkte Entity wird durch ein Allow in Rolle B desselben Users **stillschweigend exponiert** — das ist der dokumentierte „inakzeptable Footgun für ein Sicherheitsprodukt". Der Linter ist die aktive SoD-Sicherung dagegen.

## Aufgabe (`custom_components/tessera/linter.py` o. ä.)
- `lint_cross_role(config, policy, resolver/compiled) -> LintReport`:
  - Pro **managed User** (aus `membership.by_user`; `by_group` ist v1-inert, ADR 0005) → Rollen-Set.
  - **Cross-Rollen-Merge** exakt wie HA: `read = ∃ Rolle mit read`, `control = ∃ Rolle mit control` (most-permissive).
  - **Konflikt = stillschweigend aufgehobene Einschränkung** (DER Footgun): eine Entity, die in **mindestens einer** Rolle des Users **eingeschränkt** ist (explizit carve-out via `entity_override` all-false **oder** in dieser Rolle nicht gegrantet **obwohl** ihre Area in dieser Rolle abgedeckt ist), aber von **einer anderen** Rolle desselben Users **exponiert** wird. Pro Konflikt: `{user, entity_id, exposing_roles, restricting_roles, level}`.
  - **⚠️ KEIN Rauschen:** „verschiedene Rollen decken verschiedene Bereiche ab" ist **kein** Konflikt. Nur die **Nullifizierung einer Einschränkung** zählt. (Falls die Carve-out-Info am compiled-Level nicht unterscheidbar ist — all-false = Removal — am **Policy-Level** arbeiten.)
  - **`LintReport`** strukturiert, je User die Konflikte; **`has_blocking_conflicts(report) -> bool`**.
- **Monitor-Preview** ergänzt den Lint-Report (sichtbar im Panel/Log).
- **Gate-Hook** `has_blocking_conflicts` — **E3** konsultiert ihn, um Enforce-Apply zu blocken bis acked. (E2 = nur Logik + Hook + Sichtbarkeit; Acken/Blocken verdrahtet E3.)

## Regeln
- **Kein nativer Write, kein `hass.auth`.** Deterministisch (stabile Sortierung). Type-Hints, Docstrings, testbar.
- Merge **exakt** HAs most-permissive (read ∨, control ∨) — die Impersonation-Sicht ist die Wahrheitsquelle.

## Tests
- 2 Rollen: A schränkt `light.x` ein (carve-out / Area-abgedeckt-aber-nicht-gegrantet), B grantet `light.x` → **Konflikt** (exposing=B, restricting=A).
- Verschiedene Bereiche, keine Überschneidung → **kein** Konflikt (kein Rauschen).
- Stufen-Asymmetrie (A read-only, B control auf X) → geflaggt mit level.
- Merge == most-permissive, deterministisch · `has_blocking_conflicts` korrekt.

## DoD
Linter + Monitor-Preview-Integration + `has_blocking_conflicts`-Hook + Tests · **kein nativer Write** · CI grün · **PR mit Bericht** → **Adversarial-Panel** (Security-HIGH: Merge-Korrektheit + Konflikt-Erkennung *vollständig und rauschfrei*).
