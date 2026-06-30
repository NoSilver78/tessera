# Qualitäts-Charta — Tessera

Diese Regeln sind aus echten Befunden des Härtungslaufs **2026-06-30** entstanden: ein CRITICAL-Bug,
den 41 Review-Agenten **und** ein Dev-E2E übersahen (weil der Test-User leere Gruppen statt des realen
`system-users` hatte), und ein scharfer Apply-Halbzustand, den erst eine **unabhängige
Kreuzvalidierung** fand. Sie gelten für **alle** Beiträge — Mensch wie Agent — und sind Teil des
Review-Gates (siehe [CONTRIBUTING](../CONTRIBUTING.md), [CONTRACT](../CONTRACT.md), [AGENTS](../AGENTS.md)).

## Leitlinie
**Realistische Verifikation schlägt „mehr Reviewer".** Qualität entsteht nicht aus mehr Gates, sondern
aus **realistischen Fixtures, getesteten Invarianten und unabhängigen Perspektiven**.

## Regeln R1–R7
- **R1 — Tests behaupten das sichere Soll, nie nur das Ist.** Ein Test, der einen unsicheren Zustand als
  „erwartet" dokumentiert, ist ein *Finding*, kein Test. *(Anlass: der Apply-Failure-Test fixierte den
  scharfen Halbzustand als korrekt und blockierte damit den Fix.)*
- **R2 — Auth-/Permission-Tests nutzen reale HA-Fixtures.** Normaler Nicht-Admin-Nutzer = `system-users`,
  nie `group_ids=[]`. *(Anlass: der CRITICAL-Bug schlüpfte durch, weil die Fixtures unrealistisch waren.)*
- **R3 — Jede `SECURITY.md`-Zusage hat einen benannten Test.** Neue/geänderte Zusage ⇒ Zeile in der
  Invarianten-Tabelle unten + verlinkter Test.
- **R4 — Modul verdrahten ⇒ Docstring/Phase-Marker im selben Commit aktualisieren.** Der CI-Check
  *stale-markers* erzwingt es: verdrahteter Code darf sich nicht „dormant/not wired" nennen.
- **R5 — Jeder Native-Write-Pfad braucht einen Failure-Injection-Test,** der den **sicheren Endzustand**
  beweist (sofortiger Rollback, kein Halbzustand), nicht nur den Happy Path.
- **R6 — Grünes Gate ≠ Beweis.** Beweis = grünes Gate **+** Mutationsprobe (Verhalten brechen ⇒ Test
  failt) **+** realistischer E2E gegen `ha-tessera-dev`.
- **R7 — Sicherheitskritische Änderung ⇒ zwei *unabhängige* Reviews** (z. B. Claude-Adversarial-Gate +
  Codex), nicht nur redundante. *(Anlass: CXR-01 fand nur Codex, nicht der 41-Agenten-Lauf.)*

> **Schichtungs-Lektion (2026-06-30):** Defense-in-Depth gehört auf die Schicht, die die nötige
> Information hat. Ein Promotion-Guard am Binding-Choke-Point (ohne Rollen-Kontext) konnte legitime
> von verbotener Admin-Vergabe nicht unterscheiden und blockierte still die `change`-Stufe — Rollen-
> Policy gehört in den **Plan** (`_has_admin_role`), nicht in den strukturellen Validator. Ein Guard
> am falschen Layer ist ein False-Positive-Generator. (Vom Verifikations-Panel gefangen → R7.)

## Invarianten ⇄ Tests (R3)
| Sicherheits-Invariante | Beweisende Tests |
|---|---|
| Allow-only (nur gewähren, nie deny) | `test_apply_enforce_plan_allow_only_guard_blocks_all_writes`, `test_policy_store_rejects_non_allow_only_policy_shapes` |
| Kein Owner/Admin-Lockout | `test_apply_enforce_plan_lockout_guard_blocks_all_writes`, `test_apply_enforce_plan_owner_survivor_allows_demoting_admins`, `test_restore_lockout_precheck_blocks_before_writes` |
| `system_generated` zählt nie als Lockout-Survivor | `test_apply_enforce_plan_system_generated_admin_is_not_a_survivor`, `test_restore_system_generated_admin_is_not_a_survivor` |
| Admin-Stufe (`change`) plan-gesteuert: is_admin-Rolle → system-admin, Nicht-Admin-Rolle nie; bestehender Admin bleibt; Binding akzeptiert legitime Promotion | `test_binding_plan_promotion_guard_and_existing_admin_retention`, `test_binding_plan_uses_full_multi_role_superset_and_admin_role`, `test_user_binding_allows_admin_role_promotion` |
| Owner/system-generated nie gebunden oder restored | `test_recovery_snapshot_skips_unmanaged_users`, `test_restore_skips_owner_and_system_generated_users` |
| Pre-Install verbatim erfasst + restored (inkl. `system-users`) | `test_recovery_snapshot_captures_system_users_member_verbatim`, `test_user_binding_restore_exact_allows_system_users` |
| Kein scharfer Halbzustand (sofortiger Rollback bei Apply-Fehler) | `test_enforce_apply_failure_rolls_back_and_clears_journal`, `test_enforce_apply_failure_rollback_failure_leaves_journal_open` |
| Version-Guard blockt Write auf falscher HA-Version | `test_policy_store_version_guard_blocks_native_group_write` |
| Default-Rolle statt allow-all bei leerer Rollen-Union | `test_binding_plan_empty_union_uses_default_role_not_system_users` |
| fail-safe-to-monitor bei jedem Fehler | `test_mode_switch_restore_failure_fails_safe_to_monitor`, `test_enforce_clean_plan_snapshots_journals_applies_and_clears` |
| Persistierter Recovery-State wird validiert | `test_rejects_malformed_snapshot_container`, `test_rejects_snapshot_user_missing_user_id`, `test_rejects_duplicate_snapshot_user_id` (test_state.py) |
| D9 auth-scoped Veto + Ack-Override | `test_auth_mutating_component_is_vetoed`, `test_admin_ack_overrides_auth_surface_veto`, `test_compiled_artifact_is_vetoed` |
| Panel/Matrix nur für Admins | `test_matrix_websocket_requires_admin`, `test_panel_registers_admin_only_and_is_idempotent` |

## Mechanismen
1. **Stale-Marker-CI-Check** (R4) — `.github/workflows/ci.yml` schlägt fehl, wenn verdrahteter Code in
   `custom_components/tessera/*.py` sich „dormant/not wired" nennt. (`v1-inert`/`by_group` sind by-design
   und nicht betroffen.)
2. **Invarianten-Tabelle** (R3, oben) — beim Review jeder sicherheitskritischen Änderung geprüft: jede
   neue/geänderte Zusage trägt einen Test.
