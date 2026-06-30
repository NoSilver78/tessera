# Tessera Dedup User Helpers — BLOCKED

Datum: 2026-06-30  
Autor: Codex  
Auftrag: `exchange/2026-06-30/tessera-dedup-user-helpers-task-claude-2026-06-30.md`  
Status: **BLOCKED — Byte-Äquivalenz-Pflicht verletzt**

## Ergebnis

Keine Codeänderung durchgeführt. Die Workorder verlangt ausdrücklich:

> Weicht eine Kopie ab (auch nur ein Zeichen) → STOPP, nicht mergen, im Bericht melden.

Diese Stop-Regel greift.

## Evidence

### `_user_group_ids(user)`

Vorkommen:
- `custom_components/tessera/auth_adapter.py:533`
- `custom_components/tessera/mode_manager.py:471`
- `custom_components/tessera/restore.py:134`

Der ausführbare Body ist inhaltlich gleich:

```python
if hasattr(user, "group_ids"):
    return sorted(str(group_id) for group_id in user.group_ids)
return sorted(str(group.id) for group in user.groups)
```

Hinweis: `auth_adapter.py` enthält zusätzlich einen lokalen Docstring, die anderen Kopien nicht.

### `_is_unmanaged_user(user)`

Vorkommen:
- `custom_components/tessera/mode_manager.py:465`
- `custom_components/tessera/restore.py:128`

Body ist gleich:

```python
return bool(getattr(user, "is_owner", False)) or bool(
    getattr(user, "system_generated", False)
)
```

### `_user_id(user)` — nicht äquivalent

Vorkommen:
- `custom_components/tessera/auth_adapter.py:540`
- `custom_components/tessera/mode_manager.py:477`

`auth_adapter.py`:

```python
user_id = getattr(user, "id", None)
if not isinstance(user_id, str) or not user_id:
    raise UnsafeAuthTarget("managed users require a stable id")
return user_id
```

`mode_manager.py`:

```python
user_id = getattr(user, "id", None)
if not isinstance(user_id, str) or not user_id:
    raise ValueError("managed users require a stable id")
return user_id
```

Die Exception-Klasse ist verschieden (`UnsafeAuthTarget` vs. `ValueError`). Eine Konsolidierung auf eine gemeinsame Funktion würde mindestens einen Aufrufer semantisch ändern und kann Error-Klassifikation, Tests oder Guard-Semantik beeinflussen.

## Empfehlung

Entweder:

1. Workorder splitten: nur `_user_group_ids` und `_is_unmanaged_user` deduplizieren; `_user_id` separat prüfen.
2. Oder vorher architektonisch festlegen, welche Exception-Klasse für `_user_id` kanonisch ist, und die Verhaltensänderung als eigene sicherheitsrelevante Änderung mit Tests/gate behandeln.

## Secret-Redaction-Status

Keine Secrets gelesen oder geschrieben. Keine Live-/`/Volumes/config`-Prüfung durchgeführt. Keine Produktdateien geändert.

