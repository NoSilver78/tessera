# Codex-Aufgabe — E1: Auth-Adapter (4 Verträge, isoliert, NOCH NICHT scharf)
Von Claude · 2026-06-29 · Spec: `docs/spec-enforce.md` §1 + E1 · **Branch `enforce/e1-auth-adapter` (von `main`) → PR** · **ENFORCE-KRITISCH (Adversarial-Panel-Gate)** · nicht von D10 blockiert (isolierte Schicht)

## ⚠️ Boundary-Wechsel (lies das zuerst)
Bis jetzt galt „**kein nativer `hass.auth`-Write im Produkt**" (ADR 0004). Der Spike (Welle A–E PASS) hat Schreibpfad + Rescue + No-Lockout validiert → für die **Adapter-Schicht** ist die Schranke aufgehoben. **ABER: E1 BAUT die Adapter, schaltet sie NICHT scharf.** `off`/`monitor` bleiben no-write; die Mode-Behandlung in `__init__.py` bleibt **Monitor-Preview-only** — **kein Mode triggert einen nativen Write**. Die Adapter sind vorhanden + getestet, aber **dormant**. **E3** verdrahtet sie. Ein Test belegt „im Betrieb kein nativer Write".

## Aufgabe — die 4 Verträge als isolierte, getestete Adapter
Datei(en): `custom_components/tessera/auth_adapter.py` (oder kleines Paket). **Alle Leitplanken aus `docs/spec-enforce.md` §0 baken.**
1. **AuthPolicyStoreAdapter** — liest/schreibt native Gruppen-`PolicyPermissions`.
   - **Version-Guard (D11):** unsupported HA-Version → `refuse` (Exception/Sentinel), **KEIN Write**. Version-Pin-Konstante.
   - Schreibpfad: privates `_store._groups` (keine public CRUD-API) — gekapselt + version-geguarded.
2. **UserBindingAdapter** — bindet User an Rollen-Gruppen.
   - **REPLACE-bewusst (D5/D15/A2):** `bind(user, target_group_ids)` erwartet/schreibt das **VOLLE Soll-Superset** via `async_update_user(group_ids=full_superset)` — **nie ein Delta**. Guard, dass das Superset vollständig ist.
   - **system-users-Exklusion (B3) + Namespace-Guard (A3):** Targets nur `tessera:`-namespaced; `system-users`/non-`tessera:` **abgelehnt**.
3. **PermissionProbeAdapter** — `check_entity(user, entity_id, level)` (Preview/Verify/Impersonation).
4. **RecoveryController** — Snapshot/Restore (namespace-guarded), **No-Admin-Lockout-Check** (≥1 Owner/Admin behält Zugang), **fail-safe-to-off**-Helper.

## Harte Regeln
- **Adapter NICHT in die Mode-Behandlung verdrahten** — Produkt bleibt im Betrieb enforce-frei bis E3.
- Best-Practice: Type-Hints, Google-Docstrings, async, kein blocking I/O, `hass.auth` fakebar (wie Core-Tests).

## Tests (`tests/test_auth_adapter.py`)
- UserBinding schreibt **volles Superset** (Fake-`hass.auth`: `group_ids == Superset`, nie Subset/Delta).
- `system-users`/non-`tessera:`-Target → abgelehnt.
- Version-Guard: unsupported → refuse, **kein** Write-Call (Spy).
- RecoveryController: Snapshot→Restore exakt · No-Admin-Lockout-Check · fail-safe-to-off.
- **Boundary-Test:** `async_setup_entry` in `off`/`monitor` ruft **keinen** Adapter-Write.

## DoD
4 Adapter + Tests · **dormant** (nicht verdrahtet) · CI grün · **PR mit Bericht** → **Adversarial-Panel** (Schreibpfad-Korrektheit + „dormant im Betrieb").
