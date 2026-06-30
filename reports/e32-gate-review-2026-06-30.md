# QS-Gate Konsolidierung — PR #22 (E3.2 Binding-Plan, read-only/dormant)

Ich konsolidiere die drei Verdikt-Blöcke (`binding-escalation`, `owner-orphan-write`, `schema-determinism`) zu einem Gate-Urteil.

---

## ENTSCHEIDUNG: **PASS MIT AUFLAGEN**

Die vier sicherheitskritischen Primär-Invarianten (Keine native Admin-Eskalation, kein `system-users` Allow-all-Leak, No-Drop, kein nativer Write auf Block-Pfaden) sind **gehalten** und durch Tests gepinnt — alle vier Eskalations-/Leak-Behauptungen wurden **widerlegt** (refuted), keine Critical/High blieb stehen. Das Modul ist nachweislich **dormant** (kein Importer/Caller außer Definitionsstelle). Der PR ist daher grundsätzlich freigabefähig. Die Auflagen betreffen **Hardening vor dem späteren Enforce-Write** (nicht E3.2-Read-only-Korrektheit) sowie eine **echte Testlücke** im Fail-Closed-Pfad.

---

## BEFUNDE NACH SEVERITY

### MEDIUM (Auflagen — vor Enforce-Wiring zu schließen)

**M1 · `__default__`-Sentinel-Kollision** (`schema.py` _require_role_id 310-317 / `mode_manager.py` 123-139)
Ein real angelegter Rollen-Name `__default__` ist schema-erlaubt (kein `:`, kein `tessera`-Prefix) und kollidiert mit der synthetischen Default-Gruppe → zwei `GroupPlan`-Einträge mit identischer `group_id` und konfligierenden Policies (echte Rollen-Policy vs. `_empty_policy()`). Plan-Integritätsdefekt, der erst im Enforce-Write (last-writer-wins) durchschlägt. **Verdict: weak/medium — widerlegt KEINE Primär-Claim, aber Härtung vor Enforce nötig.**
*Korrektur:* `__default__` in `_require_role_id` reservieren (ablehnen wie `tessera`/`:`) **oder** in `compute_enforce_plan` den synthetischen Default überspringen, wenn `__default__` bereits in `compiled`. Test mit literaler `__default__`-Rolle + role-losem User ergänzen.

**M2 · Fail-Closed-Auth-Pfad ungetestet** (`mode_manager.py` 118-121, `_user_id` ValueError 273)
Der `try/except Exception → _blocked("auth")` um den einzigen `hass.auth`-Zugriff ist strukturell fail-closed, aber **kein Test** trifft den Branch (kein Assert auf `block_reason=="auth"`, keine Fixture lässt `async_get_users`/`_store` werfen). Der reale `_user_id`-ValueError-Pfad (leere User-ID) ist nur durch genau dieses ungetestete `try/except` geschützt. **Verdict: weak/medium — Claim „fail-closed" nur per Code-Reading belegt, nicht durch Test.**
*Korrektur:* Test ergänzen: `FakeAuth` mit werfendem `async_get_users`/`_store.async_get_groups` → `result==blocked`, `block_reason=="auth"`, Exception-Typ im `block_detail`; zweiter Fall managed User mit leerer ID → `_user_id`-ValueError → `_blocked("auth")`.

### LOW (kein Blocker — Operator-Sichtbarkeit / Audit)

**L1 · Demotion-Limitierung (Retain-existing-admin)** (`mode_manager.py` 247-251)
Ein bestehender nativer System-Admin behält `system-admin` auch bei Zuweisung einer Nicht-Admin-Rolle — **bewusstes No-Lockout-Verhalten** (spec §8.5.3, durch Test gepinnt). Keine Eskalation, kein Lockout. Reale Design-Grenze: Tessera kann einen pre-existing Admin **nicht** per Rollenzuweisung demoten — das muss out-of-band in HA geschehen.
*Korrektur:* Keine Code-Änderung. Operator-Doku muss explizit machen, dass Demotion eines bestehenden nativen Admins das direkte Entfernen von `system-admin` in HA erfordert.

**L2 · Sticky/silent Admin-Grant** (`mode_manager.py` Retention-Branch / `auth_adapter.py` 373)
Die Admin-Retention keyt auf die *aktuelle* native `system-admin`-Mitgliedschaft → ein einmaliger Admin behält `system-admin` über jeden Recompute, auch nachdem alle `is_admin`-Rollen entfernt wurden; der Binder *bewahrt* nur, *hinterfragt* nie. Keine Eskalation (Privileg war legitim), aber klebrig & unsichtbar.
*Korrektur (optional, nicht erforderlich):* Informationssignal (kein Block) emittieren, wenn `target` `system-admin` für einen User behält, dessen effektive Rollen kein `is_admin` enthalten — macht sticky Grants auditierbar.

---

## POSITIVE BEOBACHTUNGEN

- **Defense-in-depth durchgängig:** `system-users`-Leak in **zwei** unabhängigen Schichten geblockt (Planner entfernt + Binder `_validate_full_group_superset` hard-reject); Owner/system_generated in **beiden** Pfaden geschützt (Plan-Filter `_is_unmanaged_user` + Write-Guard `_assert_managed_user` raises LockoutRisk/UnsafeAuthTarget + `RecoveryController.async_assert_no_admin_lockout` fail-closed).
- **Brute-Force-Widerlegung:** Alle Rollen-Subset × Current-Group-Subset-Kombinationen mit 0 Admin-Rollen / 0 Current-Admin → **0 Eskalationen, 0 native-allow-all-Leaks, 0 gedroppte Rollen-/Recovery-Gruppen**.
- **Gate-Ordering bewiesen:** `AuthTrapHass` (`.auth` raises bei jedem Zugriff) ist der hass für **alle** Block-Pfad-Tests (version/store/resolver/d9/linter) → kein Auth-Zugriff auf irgendeinem Block-Pfad.
- **No-Write nachgewiesen:** `WriteTrapStore.save_calls`/`FakeAuth.update_calls` + explizite `==0`-Asserts nach vollem Plan (Bindings + Orphan-Detection).
- **Determinismus vollständig:** Alle vier Output-Listen (groups/bindings/target_group_ids/orphans) + `block_detail` + Linter-Detail-String per `sorted()` über stabile Keys — keine Set-Iteration leakt in die Ausgabe-Reihenfolge.
- **Orphan-Semantik korrekt:** `tessera:__default__` unkonditional managed (nie Orphan); by_group-only Rollen (ADR 0005 inert) bleiben in `known_role_ids` → nicht orphaned; nur echte stale `tessera:*` werden gemeldet.
- **`is_admin`-Validierung sauber:** nur `bool`/optional; `isinstance(1, bool) is False` → Ints korrekt abgelehnt; Consumer `.get("is_admin") is True` safe bei fehlend/None.
- **Tests substanziell, nicht vakuös:** Full-Dict/Full-Equality-Asserts auf Supersets statt Truthiness; beide Branches der Admin-discard/keep-Logik abgedeckt.

---

## NICHT PRÜFBARES / OFFEN

- **Mutationsproben** (No-Drop / default_role / Promotion) laufen **separat** und sind in dieses Gate **nicht** eingeflossen — dieses Urteil stützt sich auf Code-Reading + den grünen no-write-Grep + venv-Lauf (**154 passed**). Bestätigung der Mutationsproben steht aus; bei Fund einer überlebenden Mutation in diesen drei Invarianten ist das Urteil neu zu bewerten.
- **Komponierter No-Drop-Pfad nur teilweise im Binder prüfbar:** `_validate_full_group_superset` prüft nur `expected ⊆ full`, **nicht** gegen die tatsächlichen aktuellen `tessera`-Gruppen des Users (spec §8.5.2: caller-asserted). Der E3-Caller `compute_enforce_plan` berechnet `expected` aus Full-Membership → komponierter Pfad sound; der **Binder allein** kann eine vom Caller vergessene `tessera`-Gruppe nicht erkennen. Korrektheit hängt am (hier nicht-aktiven) Enforce-Caller.
- **Doc-Inkonsistenz (nicht load-bearing):** Modul-Docstring referenziert teils `E3.1` vs. `E3.2`; `_compute_user_bindings_and_orphans`-Docstring leicht ungenau. Verhalten verifiziert korrekt — nur Reviewer-Verwirrung. Optional angleichen.
- **getattr-Default-Annahme:** Plan-Owner/system-Filter verlässt sich auf `getattr(..., False)` — ein HA-User-Objekt ohne `is_owner`/`system_generated` würde als managed behandelt. Real definiert HA diese Attribute immer → theoretisch.

---

**Begründung der Entscheidung:** Keine Critical/High überlebt (alle vier Eskalations-/Leak-Claims refuted, brute-force-bestätigt); Modul dormant; No-Write + Gate-Ordering test-gepinnt. → kein FAIL. Es bleiben jedoch zwei **Medium**-Punkte (M1 Plan-Integrität `__default__`, M2 echte Testlücke Fail-Closed) → kein reines PASS. **PASS MIT AUFLAGEN**: M1+M2 vor dem Enforce-Wiring (E3.3+) schließen; L1 als Operator-Doku, L2 optional als Audit-Signal. Endgültige Bestätigung vorbehaltlich der separaten Mutationsproben.