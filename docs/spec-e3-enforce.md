# TESSERA — E3-Spec: Mode-Manager + Enforce-Scharfschaltung
Stand 2026-06-29 (Architekt-Vorbereitung, **noch nicht freigegeben**) · Voraussetzung: **E1✅ E2✅** + **D10 (Michael)** + Human-Go. Leitplanken: `docs/spec-enforce.md` §0.

> **⚠️ E3 ist der Scharf-Schritt** (native `hass.auth`-Writes gehen LIVE). Wird **nicht** autonom gemerged — D10 + Human-Review + Soak-Phase sind Pflicht.

## 1. Was E3 verdrahtet
Die in E1 gebauten (dormanten) Adapter + den E2-Linter in einen **Mode-Manager**, der den D15-Lifecycle `off → monitor → enforce → restore` real fährt.

## 2. Schreib-Sequenz bei `enforce` (jede Stufe ein hartes Gate VOR dem Write)
```
async_setup_entry / recompile, mode == enforce:
  1. VERSION-GATE (D11)      : AuthPolicyStoreAdapter.assert_supported_version()  — sonst refuse → monitor/off + Repairs-Issue
  2. COMPILE                 : compile_current(store, resolver)  (rein, deterministisch)
  3. D9-GATE                 : UNKNOWN_BLOCK_ENFORCE-Komponenten vorhanden? → refuse enforce (fail-closed) + Repairs
  4. CROSS-ROLLEN-LINTER (E2): has_blocking_conflicts(lint_cross_role(...))? → BLOCK apply bis explizit acked (SoD-Footgun)
  5. NATIVE WRITE            : pro managed User UserBindingAdapter.async_bind_full_superset(user, full_superset, expected=tessera_groups)
                               — REPLACE-bewusst, VOLLES Superset, system-users/Namespace-guarded
  6. CACHE                   : user.invalidate_cache() je betroffenem User
  7. SNAPSHOT                : RecoveryController-Snapshot des Vor-Zustands (für restore/uninstall)
  Fehler an JEDER Stelle → fail-safe-to-off (kein Teil-Write bleibt unkontrolliert), redigiertes Log, nie Deny-all.
```

## 3. Restore / Mode-Wechsel
- `enforce → monitor/off`: RecoveryController stellt den Snapshot-Zustand exakt wieder her (native Policy zurück, kein verwaister Grant), No-Admin-Lockout-Check.
- Idempotenz: gleiche Policy ⇒ kein Write (Diff gegen Ist).

## 4. Harte Invarianten (aus Welle A–E, nicht verhandelbar)
volles Superset (kein Delta) · ≥1 Owner/Admin behält Zugang · Version-fail-closed · D9-fail-closed · Linter blockt vor Apply · `by_user` only (ADR 0005) · fail-safe-to-off · Allow-only.

## 5. Gating
E3 als **mehrere kleine Codex-Schritte** (Mode-Manager-Skelett → Write-Sequenz mit Gates → Restore → E2E), **jeder enforce-kritisch → Adversarial-Panel**. **Erst nach D10-PASS + explizitem Human-Go.** Default-Mode bleibt `monitor` bis bewusst auf `enforce` gestellt + Soak.

## 6. Offene Design-Fragen (für die D10/Morgen-Runde)
- `Context(user_id=None)`-Systemkontext (D6-Bypass): in v1 dokumentierter Trust-Boundary-Ausschluss **oder** eigene Behandlung? → explizite Entscheidung nötig (concept §-Update).
- Apply/Ack-UX des Linters: Repairs-Issue vs. blockierender Config-Flow-Schritt.
- Snapshot-Persistenz: in `tessera.state` (two-phase-apply, concept §8) vs. in-memory.

## 7. ⚠️ Lücken in diesem Plan (Claude-Selbstkritik 2026-06-29 nacht — VOR E3 zu lösen)
- **D9-Produkt-Gate fehlt.** Die D9-Klassifikation (`ALLOW/DENY/TIER-2/UNKNOWN_BLOCK_ENFORCE`) existiert nur im **Spike** (Welle D). Schritt 3 der Schreib-Sequenz braucht einen **produktseitigen** Mechanismus, der installierte Custom-Components prüft + bei `UNKNOWN_BLOCK_ENFORCE` enforce blockt (fail-closed). → eigener Vorarbeits-Schritt **E2.5** (Produkt-D9-Gate) vor E3-Scharf.
- **User→Native-Gruppen-Mapping + Gruppen-Lifecycle unter-spezifiziert.** E3 muss pro Tessera-Rolle eine **native HA-Gruppe** mit kompilierter Policy erzeugen/aktualisieren/löschen (`AuthPolicyStoreAdapter`) und User an ihre Rollen-Gruppen binden (`UserBindingAdapter`, volles Superset = alle Rollen-Gruppen + zu erhaltende System-Gruppen). Offen: **Gruppen-Naming + Lifecycle** (Rolle umbenannt/gelöscht → was passiert mit der nativen Gruppe + den Bindungen?). Braucht ein sauberes Konzept VOR der Implementierung — sonst verwaiste native Gruppen / Lockout-Risiko.

## 8. Vor-E3-Auflagen aus dem Foundation-Security-Audit (2026-06-29 nacht)
Gesamt-Urteil des holistischen Audits: **SOLIDE-MIT-AUFLAGEN** (allow-only/operate-control/fail-safe/Determinismus halten unter 6000+/200k-Fuzz; Dormanz bestätigt).
- **BLOCKING (vor Scharf):** Finding #3 — Widerspruchs-Leaf-SoD-Bypass → eigener Task `enforce/fix-contradictory-leaf` (Schema-`read≤control`-Reject). Gate läuft.
- **SHOULD (vor Write-Bridge-Merge, beim Adapter-Wiring):**
  1. **Allow-only-Assertion am Choke-Point** `AuthPolicyStoreAdapter.async_set_group_policy` (schreibt sonst `{entities:True}` verbatim).
  2. **„kein Drop" reparieren:** `_validate_full_group_superset` prüft nur `expected⊆full`, nie gegen die AKTUELLEN tessera-Gruppen des Users → No-Drop hängt voll am E3-Caller. Docstring-Overclaim korrigieren + Caller MUSS `expected` vollständig berechnen.
  3. **Promotion-Guard:** assert, dass Non-Admin-Rollen nie `system-admin` im Superset ergeben (nur Demotion ist heute guarded).
  4. **`tessera:`-Prefix reservieren** für Role-IDs (admin-role-id `tessera:foo` kollidiert mit Managed-Namespace).
  5. **Determinismus:** Per-ID-Diff beibehalten (sicher); falls Hash-über-serialisierte-Payload → `_groups` via `sorted(compiled)` deterministisch.
- **Test-Masken (vor E3 in die Suite ziehen):** Dormant-Setup-Test auch über `enforce` parametrisieren; Test-Double `_data_to_save` darf NICHT sortieren (maskiert das `_groups`-Determinismus-Loch — echtes HA serialisiert Insertion-Order).
- **Bereits akzeptiert (kein neuer Bedarf):** Admin-Bypass · system-users allow-all (namentlich geblockt) · E1-Dormanz/Caller-asserted · SoD-by-assignment.
