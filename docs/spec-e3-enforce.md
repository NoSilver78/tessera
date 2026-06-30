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
  Fehler an JEDER Stelle → fail-safe-to-monitor (kein Teil-Write bleibt unkontrolliert), redigiertes Log, nie Deny-all.
```

## 3. Restore / Mode-Wechsel
- `enforce → monitor/off`: RecoveryController stellt den Snapshot-Zustand exakt wieder her (native Policy zurück, kein verwaister Grant), No-Admin-Lockout-Check.
- Idempotenz: gleiche Policy ⇒ kein Write (Diff gegen Ist).

## 4. Harte Invarianten (aus Welle A–E, nicht verhandelbar)
volles Superset (kein Delta) · ≥1 Owner/Admin behält Zugang · Version-fail-closed · D9-fail-closed · Linter blockt vor Apply · `by_user` only (ADR 0005) · fail-safe-to-monitor · Allow-only.

## 5. Gating
E3 als **mehrere kleine Codex-Schritte** (Mode-Manager-Skelett → Write-Sequenz mit Gates → Restore → E2E), **jeder enforce-kritisch → Adversarial-Panel**. **Erst nach D10-PASS + explizitem Human-Go.** Default-Mode bleibt `monitor` bis bewusst auf `enforce` gestellt + Soak.

## 6. Design-Fragen — ENTSCHIEDEN (2026-06-30, Sign-off Michael; Vollfassung: `spec-e3-design.md` Teil C)
- **C1 · `Context(user_id=None)`-Systemkontext:** dokumentierter Trust-Boundary-Ausschluss (patchfrei unschließbar). **Assist NICHT pauschal** — via nativem `exposed_entities` für non-admins teil-scopebar (v1-Option).
- **C2 · Linter-Ack-UX:** die **Apply-Sequenz blockt** (Schritt 4 = das Gate); Repairs-Issue = nur Notification; Ack = **ablaufendes Breakglass-Artefakt** mit Konflikt-Fingerprint (Fingerprint ändert sich → Ack erlischt → erneuter Block).
- **C3 · Snapshot-Persistenz:** persistent in `.storage/tessera.state` (`pre_install_snapshot` IMMUTABLE, Two-Phase-Journal), **nicht** in-memory.

## 7. Plan-Lücken — SPEZIFIZIERT (Vollfassung: `spec-e3-design.md` Teil A/B; adversarial-gegated `wb77hllxb`)
- **D9-Produkt-Gate → E2.5 spec'd** (`spec-e3-design.md` Teil A): fail-closed Klassifikation installierter Custom-Components, **Surface-Scan als Hard-Veto** (nicht die fälschbare `has_services`-Heuristik), `content_hash`-Trust-Anchor, frischer Platten-Scan gegen den `async_get_custom_components`-Cache. **Read-only, baubar JETZT** (Codex-Task E2.5).
- **Gruppen-Lifecycle → spec'd** (`spec-e3-design.md` Teil B): `role_id` immutable (Rename = nativer No-Op), Delete = **Rebind→Remove** (No-Drop §8.2), **Empty-Union → `default_role`** (NIE zurück in system-users = Eskalation), Promotion-Guard, `tessera:`-Prefix-Schema-Guard.

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
