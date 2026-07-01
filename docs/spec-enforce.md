# TESSERA — Enforce-Build-Spec (nativer Schreibpfad)
Stand 2026-06-29 · **Voraussetzung: Spike Welle A–E PASS** (Schreibpfad/Rescue/Lifecycle validiert) · gated hinter **ADR 0005** (`by_group` v1-inert) + **D10** (Michael-Paket).

## 0. Was der Spike bewiesen hat — LEITPLANKEN (nicht verhandelbar)
- **REPLACE → volles Superset.** `async_update_user(group_ids=…)` ist REPLACE. Jeder Write berechnet das VOLLE Soll-Gruppen-Superset des Users und übergibt es — **nie ein Delta** (sonst Drop-Lockout). [D5/D15/A2]
- **No-Admin-Lockout.** Mind. 1 Owner/Admin behält immer Zugang; Boot-Rescue + fail-safe-to-off. [D5]
- **Version-Fail-Closed.** Unsupported HA-Version → enforce **verweigern** (vor jedem nativen Write), Repairs-Issue + Rückfall monitor/off. [D11]
- **E2E-Lifecycle.** off (kein Write) → monitor (Preview) → enforce (Superset-Write + `invalidate_cache`) → restore (exakt, kein verwaister Grant). [D15]
- **system-users-Gate.** Managed User nie in der allow-all `system-users`-Gruppe; Rescue-Restore namespace-guarded (`tessera:`-only). [B3/A3]
- **`operate/control` ist die Grenze.** `view` leakt (Registry/`render_template`) → view = Best-Effort-Sichtbarkeit, **keine** Confidentiality-Boundary. [D3/D6/D7]
- **D9-fail-closed.** Custom-Components `UNKNOWN_BLOCK_ENFORCE` bis runtime-verifiziert. [D9]
- **Cross-Rollen-Deny unmöglich.** Most-permissive-Merge → kein rollenübergreifender Deny → **Linter Pflicht**. [concept §5.2]
- **Allow-only.** Kein Deny-Effekt im Compile-/Enforce-Pfad; Floor-, Area- und Entity-Regeln werden additiv vereinigt. [concept §2.2]

## 1. Der Auth-Choke-Point = 4 kleine Verträge (kein Monolith)
1. **AuthPolicyStoreAdapter** — liest/schreibt native Gruppen-`PolicyPermissions` (privater `_store._groups`-Pfad, **version-geguarded** — größtes Update-Risiko → CI-Version-Pin + Smoke-Test).
2. **UserBindingAdapter** — bindet User an Rollen-Gruppen via `async_update_user(group_ids=volles_Superset)` (REPLACE-bewusst, Caller berechnet das Superset).
3. **PermissionProbeAdapter** — `check_entity`-Proben (Monitor-Preview + Verify + **Impersonation-Preview** = Wahrheitsquelle des Linters).
4. **RecoveryController** — Boot-Rescue (Snapshot/Restore, namespace-guarded), No-Admin-Lockout-Garantie, fail-safe-to-off.

## 2. Enforce-Build-Schritte (jeder Tier-1 → Adversarial-Panel-Gate)
- **E1 — Auth-Adapter.** Die 4 Verträge, version-geguarded, Smoke-Test gegen `ha-tessera-dev`. Noch **kein** scharfes Enforce (Adapter isoliert testbar).
- **E2 — Cross-Rollen-Linter (concept §5.2, VOR Scharfschaltung — Security-HIGH).** Rechnet pro managed User die volle Cross-Rollen-Merge-Menge; flaggt jede Entity, die eine Rolle verbirgt aber eine andere exponiert, als **ERROR** → blockt Apply / erzwingt Ack. Impersonation-Preview merged real. SoD-by-assignment.
- **E3 — Mode-Manager + Enforce-Scharfschaltung.** off→monitor→enforce→restore (D15). Enforce schreibt das **volle Superset** via UserBindingAdapter, `invalidate_cache`, **fail-safe-to-monitor** bei Fehler. **Version-Gate (D11) + D9-Gate (`UNKNOWN_BLOCK_ENFORCE` blockt) + Linter (E2) VOR jedem Write.** Projiziert **nur `by_user`** (ADR 0005).
- **E4 — Uninstall/Recovery.** RecoveryController stellt native Policies beim Unload zurück (**kein Lockout**); Boot-Rescue scharf.
- **E5 — Enforce-E2E + Härtung.** Voller Lifecycle im **Produkt** (nicht nur Spike-Harness), Lockout-Tests, Doku, Repairs-UX.

## 3. Gating-Reihenfolge
ADR 0005 ✅ → **D10 (Michael)** → **E1 → E2 (Linter) → E3 (Enforce) → E4 → E5.** Jeder Schritt: Codex-Task → PR → **Adversarial-Panel** (enforce-kritisch) → Merge. `by_group` bleibt inert.

## 4. Out-of-scope v1 (post-v1)
`by_group`/OIDC-At-Login-Hook (D12-Live) · granular per-Area-`change` (bleibt global `is_admin`) · 8-Selektor-Vollausbau (label/category — v1 = floor+area+entity+domain) · hard-`view`-Isolation (Tier-2 / 2 Instanzen + `remote_homeassistant`).
