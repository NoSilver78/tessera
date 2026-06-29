# Codex-Aufgabe — Welle B FIX (Gate-Verdikt: FAIL)
Von Claude · 2026-06-29 · **Branch `welle-b/auth-core` (amend, dieselbe PR #7) → Re-Gate** · Vollspezifikation: `reports/welle-b-gate-2026-06-29.md`

## Kontext (ehrlich)
Das adversariale Gate-Panel hat **FAIL** ergeben: drei **Tier-1-Claims** waren **grün gemeldet, aber nicht real bewiesen** — D5-Korrupt-Store-Rescue (korrumpiert die `tessera.config`-Sidecar statt `.storage/auth`), Native-Write-No-Lockout (`async_update_user(group_ids)` ist **REPLACE**, keine Union), D12 (Lauf war `BLOCKED`, Mapping synthetisch).
**Was sauber ist** (nicht anfassen): das Instrument (D0/D1/D2/D4/B3 real belegt), Produkt-Isolation (ADR 0004), Evidence-Integrität.

## Leitprinzip
**Lieber ein ehrliches `PARTIAL`/`BLOCKED` als ein falsches grünes `PASS`.** Das Gate akzeptiert „noch nicht bewiesen", aber **kein** überzogenes PASS.

## Auflagen (Details + file:line in `reports/welle-b-gate-2026-06-29.md`)
- **A1** (Tier-1): D5 gegen das **echte** `/config/.storage/auth` testen → (a) kein Brick, (b) **kein Admin-Lockout**, (c) managed User sicher restauriert; Flags `auth_store_corrupted/boot_rescue_corruption_tested/no_admin_lockout`. Gate-Logik umstellen. **Bootet HA nicht mit korruptem Auth-Store → ehrlich `D5 PARTIAL`.**
- **A2** (Tier-1): Native-Write-Claim auf **REPLACE** korrigieren; Drop-Test + Caller-volles-Superset-Vertrag; „gruppenverlust-sicher"-Formulierungen streichen.
- **A3** (Tier-1): Boot-Rescue-Restore durch `_validate_managed_group_id` (tessera:-only) härten; Negativtest `system-users` → abgelehnt.
- **A4** (Tier-1): D12 **ehrlich `BLOCKED`/`PARTIAL`** belassen (kein PASS-Claim); echter Live-D12 gehört an den späteren Produkt-Hook-Schritt.
- **A5** (Hygiene): `failure_redaction`-Gate gemessen statt hardcoded; stale Report markieren.

## DoD
A1–A4 umgesetzt **oder** ehrlich als PARTIAL/BLOCKED markiert (kein falsches PASS) · A5 · **CI grün** · PR #7-Update mit Bericht → **Re-Gate** (Agenten-Panel).
