# Welle-B-Gate (PR #7) — 2026-06-29
Adversariales Agenten-Panel (6 Skeptiker, je 1 Safety-Claim widerlegen → Synthese). Worktree-Review gegen `welle-b/auth-core` + Live-HA-Core im Dev-Container.

## Entscheidung: **FAIL** (kein Enforce-Go)
Drei `high`-Claims auf **Tier-1-Pfaden** (D5-Korrupt-Store-Rescue, Native-Write/No-Lockout, D12-OIDC) sind mit `confidence:high` als **refuted** bestätigt. Tier-1-Refute → kein Enforce-Go. **Nicht** Schludrigkeit: Evidence-Integrität und Produkt-Isolation sind sauber — das Problem ist, dass die sicherheitskritischsten Verträge **gar nicht real getestet** wurden, das Gate sie aber als grünes PASS emittiert.

## Claim-für-Claim
- **D5 Korrupt-Store-Rescue** — **WIDERLEGT · high.** Korrumpiert wird nur die Tessera-Sidecar `tessera.config`, **nie** der echte Auth-Store `.storage/auth` (`auth_store_corrupted:False`). Restore liest ausschließlich den *gesunden* Snapshot via `async_update_user` (setzt geladenen, gesunden Store voraus). Real getestet: „Re-Apply einer Gruppen­mitgliedschaft aus Snapshot beim Boot" — **nicht** der behauptete Failsafe gegen kaputten Auth-Store. `boot_rescue_corruption_tested:False`.
- **Native Write = „Vereinigung"/kein Drop-Lockout** — **WIDERLEGT · high.** `group_ids` ist **REPLACE** (`user.groups = groups`, HA-Core `auth_store.py:159-166`), keine Union. Eigene Evidence zeigt Drop (`expected=[tessera:test]` → `drifted=[tessera:extra]`). „Kein Lockout" gilt nur unter **Caller-Disziplin** (volles Superset übergeben), nicht als API-Eigenschaft.
- **D12 OIDC-Claim→Rolle real bewiesen** — **WIDERLEGT · high.** Lauf war `BLOCKED` (`OP_NOT_SIGNED_IN`, `secrets_read:false`). Selbst bei grünem Lauf synthetisch: `_mapping_probe` konstruiert die Map im Code, prüft nur Schema-Akzeptanz; `product_hook_present:False`, kein At-Login-Hook im Produkt.
- **system-users-Gate** — **hält · low (Härtung).** Exklusion bewiesen, restart-durabel, echter Detektor. Aber Boot-Rescue-Restore (`__init__.py:241`) schreibt Ziel-`group_ids` **ohne** Namespace-Guard → präpariertes Snapshot mit `system-users` würde geschrieben.
- **Evidence-Integrität** — **hält · keine.** Alle DoD-PASS (D0/D1/D2/D4/D5-mechanisch/B3) gedeckt; D12 ehrlich `BLOCKED`; PARTIAL ehrlich `*_tested:false`. Caveats: `failure_redaction`-Gate hardcodiert-PASS statt gemessen; Report `tessera-gate-review-d0-d1-d9` stale.
- **Produkt-Isolation (ADR 0004)** — **hält · keine.** Diff = 10 Dateien alle unter `spike/`; Produkt `custom_components/tessera` unverändert + enforce-frei (`grep hass.auth` = none). Native Writes nur in der gevendorten Wegwerf-Harness `tessera_spike`.

## Codex-Auflagen (Re-Spin → Enforce-Go)
**A1 — D5 echter Korrupt-Auth-Store-Rescue (Tier-1, blockierend).** Pfad bauen, der das **echte** `/config/.storage/auth` gezielt korrumpiert (nicht `tessera.config`). Beweise beim Restart: (a) HA bootet (kein Brick), (b) **kein Admin-Lockout** (≥1 Owner/Admin behält Zugang), (c) managed User kontrolliert restauriert/degradiert. Flags: `auth_store_corrupted:true`, `boot_rescue_corruption_tested:true`, `no_admin_lockout:true` (Roh-Messung). Gate-Logik `d0_preflight_spike.py` (D5 ~696-708) auf diese Flags umstellen. **Wenn HA mit korruptem `.storage/auth` nicht bootet: ehrlich `D5 PARTIAL` mit Begründung — kein PASS.**

**A2 — No-Lockout-Vertrag präzisieren (Tier-1, blockierend).** Doku/Claim korrigieren: `async_update_user(group_ids=...)` ist **REPLACE**, keine Union. Test ergänzen, der den destruktiven Drop zeigt (Subset → ausgelassene Gruppen weg) **und** den sicheren Caller-Vertrag verifiziert (vor jedem Write das volle Soll-Superset neu berechnen + übergeben). Flags `native_write_is_replace:true`, `caller_passes_full_superset:true`. Jede „inhärent gruppenverlust-sicher"-Formulierung streichen.

**A3 — Boot-Rescue-Restore mit Namespace-Guard (Tier-1, blockierend trotz „low", da allow-all-Eskalation).** Restore (`__init__.py:~241`) durch `_validate_managed_group_id` (tessera:-only) führen (analog `:262-265, 971-976, 1003`). Negativtest: Snapshot mit `system-users` → Restore **abgelehnt**. Flag `rescue_restore_namespace_guarded:true`.

**A4 — D12 ehrlich (Tier-1 für jeden D12-Anspruch).** Kurzfristig: D12 **ehrlich `BLOCKED`/`PARTIAL`** lassen — **kein** PASS-Claim. Echter D12 (Live-OIDC gegen die fertige Authentik, realer Token-`groups`→Rolle) gehört an den späteren Produkt-Schritt mit At-Login-Claim-Hook (`product_hook_present:False`, `schema.py:28` = nur Docstring). Voraussetzung Live-Lauf: `op`-Login (Michael). Gate darf D12 nur bei echtem Token-Beleg auf PASS setzen.

**A5 — Hygiene (nicht blockierend).** (i) `failure_redaction`-Gate (`d0_preflight_spike.py:578`) von hardcodiert-PASS auf gemessen. (ii) Stale Report `tessera-gate-review-d0-d1-d9` als veraltet markieren/neu generieren.

## DoD Re-Spin
A1–A4 **umgesetzt ODER ehrlich als PARTIAL/BLOCKED** markiert (kein falsches grünes PASS) · A5 · CI grün · PR #7-Update mit Bericht → **Re-Gate per Agenten-Panel**.
