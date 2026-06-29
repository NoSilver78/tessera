# Codex-Aufgabe — Matrix-Panel (Produkt-UI, bounded MVP)
Von Claude · 2026-06-29 · **Branch `core/matrix-panel` (von `main`) → PR** · läuft **parallel** zu Welle C/D (disjunkte Dateien) · **nicht enforce-gegated**

## Ziel
Ein **visuelles Area×Rolle-Grant-Matrix-Panel** in der HA-Sidebar: Zeilen = Areas, Spalten = Rollen, Zelle = `read`/`control`-Status. Klick toggelt → schreibt in den Tessera-**Store** (schema-aware) → Monitor-Preview aktualisiert. Macht den Monitor-Mode visuell bedienbar (heute nur Options-Flow).

## Harte Invarianten (wie der ganze Core)
- **Kein nativer Write, keine `hass.auth`-Mutation.** Geschrieben wird ausschließlich der Tessera-Store (`tessera.config`/`tessera.policy`) über die **bestehenden schema-aware Helfer** (`add_area_grant`/`remove_area_grant`/Rollen-Helfer in `config_flow.py` — wiederverwenden, **DRY**, nicht duplizieren). `control` impliziert `read`, **nie bare-True**.
- **Admin-only:** alle WS-Commands mit `@websocket_api.require_admin` (oder äquivalent).
- Nach jedem Write: `compile_current` + Preview (read-only), wie im Monitor-Wiring.

## Umsetzung (zwei Teile)
**A) Backend — WebSocket-API** (`custom_components/tessera/websocket.py` o.ä., registriert in `__init__.py`):
- `tessera/matrix/get` → liefert `{areas:[{id,name}], roles:[{id,name}], grants:{area_id:{role_id:{read,control}}}, preview:<monitor_preview counts>}`. Areas aus der Area-Registry, Rollen aus config, Grants aus policy.
- `tessera/matrix/set_grant` (`area_id, role_id, read:bool, control:bool`) → schema-aware Store-Write über die `config_flow`-Helfer (all-false ⇒ Grant entfernen) → recompile → liefert aktualisierte Matrix+Preview zurück.
- **Aktuelle HA-Referenz prüfen** (Pflicht, vgl. `check-requirements-first`): `homeassistant.components.websocket_api` Decorator-Form + `async_register_static_paths` (nicht das deprecated `register_static_path`).

**B) Frontend — Custom-Panel** (1 selbst-enthaltenes JS-Modul, **kein** Build-Step; als Static-Path ausgeliefert, via `async_register_panel`/`panel_custom` als Sidebar-Panel „Tessera"):
- Grid: Zeilen Areas, Spalten Rollen; Zelle zeigt `read`/`control` (z.B. zwei kleine Toggles oder ein 3-Zustand-Klick none→read→read+control→none).
- Lädt via `tessera/matrix/get`, schreibt via `tessera/matrix/set_grant` (`hass.connection.sendMessagePromise`), rendert die Preview-Counts.
- **HA-Theme-CSS-Variablen** nutzen (`var(--primary-color)`, `--card-background-color`, …) + grün/amber/grau-Semantik — kein Hardcoding. Funktional zuerst; Design-Politur ist Folge-Schritt.

## Bewusst NICHT in diesem MVP (Folge-Schritte)
Entity-Overrides-Editor · Membership-UI · Mode-Umschaltung im Panel (bleibt Options-Flow) · aufwendige Design-System-Angleichung.

## Tests
`tests/test_websocket.py`: `matrix/get`-Shape · `set_grant` schreibt schema-valide (read / read+control / all-false ⇒ entfernt) · **kein bare-True** im Ergebnis · unbekannte Area/Rolle sauber abgewiesen · **admin required** (non-admin → Fehler) · **kein `hass.auth` berührt** (Assertion, wie in den anderen Tests). (Frontend-JS muss CI nicht durchlaufen, aber lint-sauber/ohne Syntaxfehler.)

## DoD
WS-API + Panel-Registrierung + Frontend-Modul + Tests · **CI grün** · **PR mit Bericht** · keine Scope-Ausweitung · **kein nativer Write** (im Bericht bestätigen).
