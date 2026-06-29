# Codex-Aufgabe — Core Config-UI (Basics, Monitor-Mode bedienbar)
Von Claude · 2026-06-29 · **Branch `core/config-ui-basics` (von `main`) → PR** · nicht enforce-gegated

## Aufgabe
Erweitere die Tessera-Config-UI, sodass man die **Basics ohne YAML pflegen** kann und der Monitor-Preview greift: **Mode · Rollen · Area×Rolle-Grants**. Persistiert über den bestehenden `TesseraStore` (Schema-validiert), löst danach `compile_current`/Preview aus (read-only, ADR 0004 — **kein nativer Write**).

## Betroffene Dateien
`custom_components/tessera/config_flow.py` (Options-Flow erweitern) + ggf. kleine Helfer · `tests/test_config_flow.py` (neu). **Nichts am Enforce/Auth-Adapter.**

## Erwartete Umsetzung (HA OptionsFlow)
- **Mode** wählen: `off` / `monitor` / `enforce` (Selector). *(enforce wird vom Monitor-Wiring weiterhin als Preview+Warn behandelt — nur speichern, nicht scharfschalten.)*
- **Rollen** verwalten: hinzufügen/entfernen (role_id + optional name/description). Schema-validiert.
- **Area×Rolle-Grant** hinzufügen/entfernen: Area-Selector (HA `AreaSelector`) + Rolle + Toggles `read`/`control` → schreibt `policy.area_grants` (schema-aware `{read[,control]}`, **nie bare-True**).
- Nach jedem Speichern: Store schreiben (validiert) + `compile_current` + Preview-Log (read-only).

## Bewusst NICHT in diesem Schritt (Folge-Schritte)
Entity-Overrides-UI · Membership-by_group-UI · das visuelle Matrix-Panel (eigener Schritt, ggf. mit Design-Pass).

## Regeln
- **Kein nativer Write / keine `hass.auth`-Mutation.** Best-Practice: Type-Hints, Docstrings, async, kein blocking I/O.
- Schema ist die Wahrheit: alle Eingaben über `schema.py` validieren; ungültiges sauber abweisen (Flow-Fehler, kein Crash).
- Testbar: Store/Flow-Eingaben injizierbar/simulierbar.

## Tests
Options-Flow setzt Mode · legt Rolle an/entfernt · legt Area-Grant an (read / read+control) → Store korrekt + schema-valid · ungültige Eingabe abgewiesen · **kein bare-True** im resultierenden policy.

## NACHTRAG (Audit-Auflagen M2+M3 — hier mitnehmen, da `config_flow.py` betroffen)
Quelle: `reports/core-audit-2026-06-29.md`.
- **M2 — Single-Instance-Guard:** in `async_step_user` vor `async_create_entry` → `await self.async_set_unique_id(DOMAIN)` + `self._abort_if_unique_id_configured()` (alternativ `single_config_entry: true` in `manifest.json`). Grund: beide Stores nutzen feste Keys `tessera.config`/`tessera.policy` (nicht pro `entry_id`) — eine zweite Integration würde sie clobbern.
- **M3 — Translations:** `custom_components/tessera/strings.json` (+ `translations/en.json`) mit `config.step.user.title`/`description` und `config.abort.already_configured`.
- **Tests** (`test_config_flow.py`): zweiter Setup → Abort `already_configured`; erster Setup → `async_create_entry(title="Tessera")`; Options-Flow-Pfade (s.o.).

## Definition of Done
Config-UI-Basics + **M2+M3** + Tests · **CI grün** · **PR** mit Bericht · keine Scope-Ausweitung · **kein nativer Write** (im Bericht bestätigen).
