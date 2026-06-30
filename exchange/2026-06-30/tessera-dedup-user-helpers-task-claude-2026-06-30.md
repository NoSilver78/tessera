# Codex-Auftrag: Duplizierte User-Helfer konsolidieren (Analyse-Fund #16)

**Von:** Claude (Architektur/Gate) · **An:** Codex (Implementierer) · **Datum:** 2026-06-30
**Typ:** Cleanup / Dedup · **Risiko:** niedrig (reine Utilities, **kein Verhaltenswechsel**)

## Branch-Basis (wichtig — Koordination)
- **Basiere auf `chore/release-hardening`** (NICHT `main` — `main` hat den aktuellen Härtungsstand
  noch nicht; dort fehlen u. a. der CRITICAL-Snapshot-Fix und CXR-01). Branch: `core/dedup-user-helpers`.
- PR **gegen `chore/release-hardening`** (oder, falls die Härtung bis dahin auf `main` gemergt ist,
  gegen `main` rebasen). Claude gate't den PR.

## Aufgabe
Drei **identische** private Helfer sind über mehrere Module dupliziert. Konsolidiere sie in **ein**
neues, abhängigkeitsfreies Modul `custom_components/tessera/_user_helpers.py` und importiere sie von
dort. **Kein Verhaltenswechsel.**

Duplikate (jeweils byte-gleicher Body — vor dem Verschieben verifizieren):
- `_user_group_ids(user)` — in `auth_adapter.py:533`, `mode_manager.py:471`, `restore.py:134`
- `_user_id(user)` — in `auth_adapter.py:540`, `mode_manager.py:477`
- `_is_unmanaged_user(user)` — in `mode_manager.py:465`, `restore.py:128`

## Betroffene Dateien
- **neu:** `custom_components/tessera/_user_helpers.py` (die drei Funktionen, exakt die bestehenden Bodies)
- **geändert:** `auth_adapter.py`, `mode_manager.py`, `restore.py` — lokale Defs entfernen, statt dessen
  `from ._user_helpers import _user_group_ids, _user_id, _is_unmanaged_user` (nur die jeweils genutzten)
- **neu:** `tests/test_user_helpers.py` (Unit-Tests der Utilities)
- ggf. Test-Imports anpassen, falls ein Test eine dieser Funktionen direkt importiert (vorher `grep`)

## Regeln / was NICHT ändern
- **Byte-Äquivalenz-Pflicht:** Verschiebe einen Helfer nur, wenn sein Body in allen Vorkommen
  **exakt identisch** ist. Weicht eine Kopie ab (auch nur ein Zeichen) → **STOPP, nicht mergen,
  im Bericht melden** (es könnte ein versteckter Unterschied sein).
- **Kein Verhaltenswechsel, keine Logik-Änderung.** NICHT anfassen: Lockout-/Survivor-Checks
  (`_assert_restore_owner_or_admin_survives` & Co.), die Binding-Guards, `_is_active_owner_or_admin`
  (nur 1 Vorkommen → bleibt in `auth_adapter.py`), irgendwelche `raise`/Guard-Logik.
- **Tests nie entfernen/abschwächen.** Alle bestehenden **248 Tests müssen grün bleiben** — das ist
  der Beweis, dass sich nichts verhält ändert.
- `ruff check .`, `black --check .`, `mypy custom_components/tessera` müssen sauber bleiben (mypy strict).
- **Keine Secrets**, kein Live-`/Volumes/config`/CM5, Auth-Tests nur gegen `ha-tessera-dev`.

## Erwartete Umsetzung
1. `_user_helpers.py` anlegen mit `from __future__ import annotations`, `from typing import Any` und den
   drei Funktionen (Docstrings beibehalten/ergänzen; mypy-strict-konform).
2. In den drei Modulen die lokalen Defs löschen und den Import ergänzen (Import-Block ruff-sortiert).
3. `grep -rn "_user_group_ids\|_user_id\|_is_unmanaged_user" custom_components/tessera tests` →
   sicherstellen, dass es je **genau eine** Definition gibt und alle Aufrufer den Import nutzen.

## Tests
- `tests/test_user_helpers.py`: je Funktion Happy-Path + Grenzfälle:
  - `_user_group_ids`: Objekt mit `group_ids` **und** Objekt nur mit `groups` (id-Attribute) → sortierte Strings.
  - `_user_id`: gültige id; fehlende/leere/Nicht-String-id → erwartetes Verhalten (vorher den Code lesen,
    **das tatsächliche** Verhalten testen, nicht annehmen).
  - `_is_unmanaged_user`: owner=True, system_generated=True, normaler User.
- Alle bisherigen Tests bleiben unverändert grün.

## Definition of Done
- [ ] `_user_helpers.py` existiert; jede der drei Funktionen **genau einmal** definiert.
- [ ] `auth_adapter.py`/`mode_manager.py`/`restore.py` importieren statt zu duplizieren.
- [ ] `ruff`/`black`/`mypy`/`pytest` (248+) grün; **kein Verhaltenswechsel**.
- [ ] `tests/test_user_helpers.py` deckt die Utilities ab.
- [ ] Branch gepusht + `gh pr create` gegen `chore/release-hardening`.

## Abschlussbericht (im PR-Body)
Geänderte Dateien · Zusammenfassung · Tests+Ergebnis (Zahl grün) · Byte-Äquivalenz bestätigt? ·
Risiken/Annahmen · alles, was abwich (z. B. eine nicht-identische Kopie).

---
*Nächste mögliche Wellen (separat, nicht Teil dieses Auftrags): #17 Lockout-Check-Dedup
(sicherheitskritisch — Claude prüft erst Äquivalenz), CXR-02 Matrix-Reapply, #11 D9-Ack-Admin-Service.*
