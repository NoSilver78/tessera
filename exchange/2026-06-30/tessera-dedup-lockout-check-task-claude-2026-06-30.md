# Codex-Auftrag: Lockout-Survivor-Check deduplizieren (Analyse-Fund #17)

**Von:** Claude (Architektur/Gate) · **An:** Codex (Implementierer) · **Datum:** 2026-06-30
**Typ:** Refactor / Dedup in **sicherheitskritischem** Code · **Risiko:** mittel — höchste Sorgfalt

## Branch-Basis
- **Basiere auf `main`** (die Härtung + der #16-Dedup sind gemergt; HEAD `ebeccc9`). Branch:
  `core/dedup-lockout-check`. PR **gegen `main`**. Claude gate't.

## Kontext (Claude hat die Äquivalenz schon geprüft)
Der Owner/Admin-Survivor-Lockout-Check ist in zwei Modulen **near-dupliziert**:
- `mode_manager._assert_owner_or_admin_survives` (`mode_manager.py:339–357`)
- `restore._assert_restore_owner_or_admin_survives` (`restore.py:109–126`)

**Die Survivor-Loop-Logik ist identisch** (skip inactive → skip `system_generated` → return bei
`is_owner` → return bei `GROUP_ID_ADMIN` im Ziel → sonst `raise LockoutRisk`). **Unterschiede, die je
Aufrufer bleiben müssen:**
1. **Quelle der Ziel-Gruppen:** Plan-`bindings` (`binding["user_id"]` / `binding["target_group_ids"]`)
   vs. Snapshot-`users` (`user_snapshot.user_id` / `user_snapshot.group_ids`).
2. **LockoutRisk-Message:** `"lockout"` vs. `"restore would remove the last owner/admin recovery path"`.
3. Mini-Abweichung im is_active-Check: `getattr(...) is False` (mode_manager) vs. `not getattr(...)`
   (restore) — für Bool äquivalent.

## Aufgabe
Extrahiere die **gemeinsame Survivor-Loop** in **eine** Helfer-Funktion; die zwei Aufrufer bauen nur
noch ihre `target_group_ids_by_user`-Map und rufen den Helfer mit ihrer Message auf. **Kein
Verhaltenswechsel.**

## Erwartete Umsetzung
1. In **`auth_adapter.py`** (hat bereits `GROUP_ID_ADMIN`, `LockoutRisk`, `_user_group_ids`) eine
   Funktion hinzufügen:
   ```python
   def _assert_owner_or_admin_survives_in(
       target_group_ids_by_user: Mapping[str, set[str]],
       users_by_id: Mapping[str, Any],
       *,
       message: str,
   ) -> None:
       """Fail closed (LockoutRisk(message)) if no active owner/admin survives.

       Shared by the enforce-plan and the restore lockout prechecks; each caller
       builds target_group_ids_by_user from its own source (plan bindings vs
       pre-install snapshot) and passes its own message.
       """
       for user_id, user in users_by_id.items():
           if not getattr(user, "is_active", True):
               continue
           if getattr(user, "system_generated", False):
               continue
           if getattr(user, "is_owner", False):
               return
           group_ids = target_group_ids_by_user.get(user_id, set(_user_group_ids(user)))
           if GROUP_ID_ADMIN in group_ids:
               return
       raise LockoutRisk(message)
   ```
   (Vereinheitlichte is_active-Form `not getattr(...)` — für Bool identisch zum bisherigen Verhalten.)
2. **`mode_manager._assert_owner_or_admin_survives`**: nur noch die Map aus `plan["bindings"]` bauen
   und `_assert_owner_or_admin_survives_in(map, users_by_id, message="lockout")` aufrufen. (Import aus
   `.auth_adapter` ergänzen.)
3. **`restore._assert_restore_owner_or_admin_survives`**: nur noch die Map aus `snapshot.users` bauen
   und mit `message="restore would remove the last owner/admin recovery path"` aufrufen. (Import ergänzen.)

## Regeln / was NICHT ändern
- **Kein Verhaltenswechsel.** Gleiche Exception-Klasse (`LockoutRisk`), **gleiche Messages** je Aufrufer,
  gleiche Skip-/Return-Reihenfolge. Die `set(...)`-Defaults exakt übernehmen.
- **Sicherheitskritisch:** Wenn beim Extrahieren irgendein Unterschied auffällt, den du nicht 1:1
  abbilden kannst → **STOPP, melden** (nicht „glätten").
- Tests nie entfernen/abschwächen. `ruff`/`black`/`mypy`(strict)/`pytest` grün. Keine Secrets,
  Auth-Tests nur `ha-tessera-dev`.

## Tests
- Bestehende Lockout-Tests müssen **unverändert grün** bleiben (Beweis = kein Verhaltenswechsel):
  u. a. `test_apply_enforce_plan_lockout_guard_blocks_all_writes`,
  `test_apply_enforce_plan_owner_survivor_allows_demoting_admins`,
  `test_apply_enforce_plan_system_generated_admin_is_not_a_survivor`,
  `test_restore_lockout_precheck_blocks_before_writes`,
  `test_restore_system_generated_admin_is_not_a_survivor`.
- **Neu** (am extrahierten Helfer, direkt): owner überlebt · admin-im-Ziel überlebt · nur
  system_generated-admin → `LockoutRisk` · inactive wird übersprungen · leer → `LockoutRisk(message)`
  mit **genau der übergebenen Message**.

## Definition of Done
- [ ] `_assert_owner_or_admin_survives_in` existiert **einmal**; beide Aufrufer nutzen es.
- [ ] Beide alten Bodies enthalten nur noch Map-Bau + Aufruf; Messages unverändert je Aufrufer.
- [ ] `ruff`/`black`/`mypy`/`pytest` grün; **kein Verhaltenswechsel**.
- [ ] Helfer-Tests + alle Lockout-Tests grün.
- [ ] Branch `core/dedup-lockout-check` gepusht + `gh pr create` gegen `main`.

## Abschlussbericht (PR-Body)
Geänderte Dateien · Zusammenfassung · Tests+Ergebnis · bestätigt: gleiche Messages/Exceptions/Logik ·
Risiken/Annahmen · alles, was abwich.
