# ADR 0005 — `by_group` ist v1-inert (lokales `by_user` trägt v1)
Stand 2026-06-29 · Status: **aktiv** · Entscheidung: Michael (2026-06-29)

## Kontext
D12 (OIDC-`groups`-Claim → Rolle) ist nach dem Spike ehrlich **BLOCKED**: im Produkt existiert **kein At-Login-Claim-Hook** (`schema.py` `groups` = nur Docstring), HA-Core hat keinen nativen OIDC-Provider, und der reale `groups`-Claim-Seitenkanal ist nicht bewiesen. Die Enforce-Go-Rubrik erlaubt **„D12 PASS ODER `by_group` v1-inert"**.

## Entscheidung
**`membership.by_group` ist in v1 INERT.** Rollen-Mitgliedschaft v1 ausschließlich über **`by_user`** (lokal, ohne IdP — trägt immer). `by_group` (Authentik-OIDC-`groups`) wird weiterhin **geparst + schema-validiert + persistiert**, aber vom **Compiler NICHT in die native Policy projiziert** (kein Subject→Rolle-Binding via Gruppe). Ein expliziter **Compiler-Guard + Test** stellt sicher, dass kein stilles „wirkt schon" entsteht.

## Begründung
`by_user` funktioniert dependency-frei + sofort (harte Vorgabe). `by_group` braucht den At-Login-Claim-Hook (eigener Produkt-Schritt) **und** den Live-OIDC-Beleg (D12) — beides **post-v1**. **Inert-statt-Weglassen** hält das Schema stabil (keine Migration später) und macht die Aktivierung zu einem rein **additiven** Schritt.

## Konsequenz
- **Enforce-Go-Rubrik:** D12-Zeile erfüllt (`by_group` v1-inert). Offen bleiben **D10** (Michael) + **Cross-Rollen-Linter** (Enforce-Build, ADR-folgend in `spec-enforce.md`).
- **Enforce-Build** projiziert **nur `by_user` → Rolle**. `by_group`-Aktivierung = eigener post-v1-Schritt (At-Login-Hook + D12-Live-Beweis + Re-Gate).
- **Doku:** `concept.md` §7 als „v1-inert" markieren; Compiler-Guard + Test („`by_group` wird in v1 nicht projiziert").
