# Gate Review — Tiefer Code-Review v0.9.4 → v0.9.5 — Claude, 2026-11-15

**Anlass:** Issue #71 (HA 2026.11 vom Versions-Guard blockiert) + Auftrag „tiefer Review des Codes“.
**Methode:** Vier unabhängige Prüfer mit getrennten Zuständigkeiten (Schreibpfad · Lebenszyklus ·
Compiler/Resolver/Schema · Websocket/Options-Flow/D9). Sie lasen den Code ohne Vorannahmen und
belegten Befunde mit Wegwerf-Tests, meist gegen HAs **echten** `AuthStore` (HA 2026.8.2). Jeder
übernommene Befund wurde von Claude am Code nachvollzogen. Danach folgte eine unabhängige
Gegenprüfung des Fix-Diffs.

**Entscheidung: PASS MIT AUFLAGEN.** Die kritischen und hohen Fehler im Schreib- und Restore-Pfad
sind behoben und regressionsgetestet (Commit `5f935c0`). Offen bleiben die unten aufgeführten
Befunde. Keiner davon ist ein Lockout. Zwei davon (O1, O2) sind aber Rechte-Drift: Sie gewähren zu
viel, solange kein Recompile läuft.

## Behoben (Commits `948e9f4`, `5f935c0`)

| # | Schwere | Befund | Fix |
|---|---|---|---|
| F0 | — | #71: HA 2026.11 nicht in `SUPPORTED_HA_AUTH_FEATURES` | Linie gegen 2026.11.1 gediffed: `auth_store.py`, `models.py` und `permissions/` byte-identisch, die drei genutzten `AuthManager`-Methoden ebenfalls; Contract 17/17, mypy grün |
| F1 | **kritisch** | `enforce`→`off` mit nachträglich angelegtem Nutzer → hängende Gruppen-ID → `AuthStore.async_load` `KeyError` → **kein Login** | Restore setzt jeden Nutzer mit `tessera:*` zurück; `async_remove_group` verweigert gebundene Gruppen |
| F2 | hoch | Rollen-Entzug unter `enforce` scheitert immer → Rollback hebt alle Einschränkungen auf | Bindungs-Prüfung: aktuelle Gruppen *bestätigen*, nicht behalten |
| F3 | hoch | Snapshot nie verworfen → stale Restore (Re-Grant `system-admin`) | nach erfolgreichem Restore verwerfen |
| F4 | hoch | Restore nach `is_admin`-Rolle dauerhaft `lockout` | Prüfung auf Herabstufung je Nutzer entfernt; plan-weiter Survivor-Check bleibt |
| F5 | hoch | gelöschter Nutzer → jeder Restore `KeyError` | überspringen |
| F6 | hoch | `off` nach Fail-safe stellt nie wieder her (In-Memory-Modus) | Snapshot = persistierter Marker für `off`/Unload |
| F7 | hoch | `tessera.recompile` ohne `mutation_lock` → Re-Enforce nach `off` | Lock |
| F8 | hoch | `remove_role` lässt `label_grants` stehen → Compile-Fehler / Rechte-Auferstehung | `label_grants` in die Bereinigung |
| F9 | mittel | Options-Flow auf entladenem Eintrag legt Bucket an → Websocket kann nativ `enforce` | `_compile_preview` legt keinen Bucket mehr an |
| F10 | niedrig | Repairs nie gelöscht; `frontend`/`panel_custom` fehlen im Manifest | gelöscht nach Erfolg; Dependencies ergänzt |

Belege: `tests/test_auth_restore_regressions.py` (6 Tests gegen echten `AuthStore`, auf altem Code
alle rot), plus Tests in `test_init.py`, `test_store.py`, `test_config_flow.py`.

### Gegenprüfung des Fix-Diffs (unabhängig, ohne Kenntnis der Begründungen)

Die Gegenprüfung fand einen **Rückschritt durch den eigenen Fix**. F6 machte den Snapshot zum Marker
für „`enforce` aktiv“. Installationen bis 0.9.4 tragen aber einen nie verworfenen Snapshot, und `off`,
Setup oder Unload hätten ihn nach dem Update zurückgespielt. Das ist genau die Rechte-Ausweitung aus
F3, nur jetzt automatisch ausgelöst. Dazu kamen drei mittlere Lücken. Alle vier sind behoben (Commit
nach `5f935c0`):

| # | Schwere | Befund | Fix |
|---|---|---|---|
| V1 | hoch | veralteter Snapshot aus ≤ 0.9.4 wird nach dem Update zurückgespielt | aktiv = Snapshot **und** (Journal offen **oder** Nutzer an `tessera:*` gebunden); sonst ohne Restore verwerfen |
| V2 | mittel | Nutzer ohne Snapshot-Eintrag behält eine `is_admin`-Beförderung | neue Nutzer werden vor ihrer ersten Bindung in den Snapshot aufgenommen |
| V3 | mittel | `tessera:*` auf dem Owner (in HA möglich) blockiert jeden Restore | beim Restore nur die `tessera:*`-IDs entziehen |
| V4 | mittel | Absturz mitten im Restore bei `enforce`→`monitor` wird nie fortgesetzt | Restore unter offenem Journal |

Die Angriffstests der Gegenprüfung für V1 und V3 scheitern jetzt, sind also behoben. Der Test zu V2
ruft das Zurückspielen direkt auf und umgeht dabei den Apply-Pfad, in dem die Aufnahme passiert. Er
beschreibt deshalb nur noch einen **Restfall**: Nutzer, die eine Version ≤ 0.9.4 vor dem Update
gebunden hat, stehen nicht im Snapshot und behalten eine solche Beförderung. Das lässt sich nicht
rückwirkend unterscheiden (HA-Admin oder Tessera-Beförderung?), also wird es hier dokumentiert statt
geraten.

## Offen — braucht eine Richtungsentscheidung oder ist eigener Umfang

| # | Schwere | Befund | Vorschlag |
|---|---|---|---|
| O1 | **hoch** | **Keine Registry-/User-Listener.** Recompile nur per Service, Options-/Websocket-Edit oder Neustart. Zieht eine Entität aus einer freigegebenen Area weg, behält die Rolle ihr `read`/`control` darauf, bis neu kompiliert wird. Nach einer Umbenennung kann eine *neue* Entität mit der alten ID den Grant erben. | Entprellte Listener auf Entity-/Device-/Area-/Floor-/Label-Registry, nur in `enforce`, unter `mutation_lock`, `entry.async_on_unload` |
| O2 | **hoch** | **Neu angelegter Nutzer unter `enforce`** bekommt von HA `system-users` (alles erlaubt), bis neu kompiliert wird. | `EVENT_USER_ADDED`/`EVENT_USER_REMOVED`-Listener → Recompile (gleicher Mechanismus wie O1) |
| O3 | mittel | Versions-Guard blockiert auch den **Restore**: nach HA-Upgrade auf eine nicht validierte Linie bleiben `tessera:*`-Bindungen live, Tessera zeigt `monitor`. | Restore-only-Pfad unter engerer Prüfung erlauben, oder den Zustand im Repairs-Issue klar benennen |
| O4 | mittel | `entity_overrides` mit `false`-Blättern werden akzeptiert, sind aber wirkungslos (allow-only); der Linter verschweigt es. | `false` im Schema ablehnen **oder** als „toter Ausschluss“ linten (Migration bestehender Configs beachten) |
| O5 | mittel | D9-Scan erkennt nur `x.groups = …`; `groups.append`, Slice-Zuweisung, `.policy =`, `is_owner = True` und Symlink-Unterverzeichnisse (auch für den Ack-Hash) entgehen ihm. pyscript/AppDaemon und YAML-`auth_providers` (`command_line` mit `meta`) sieht er gar nicht. | Jede Referenz auf `groups`/`policy`/`_groups`/`_users`/`is_owner` als `SURFACE_AUTH`; Symlinks folgen oder als `SURFACE_DYNAMIC` vetoen; nicht-Standard-`auth_providers` ack-pflichtig |
| O6 | mittel | Das Panel erfährt nicht, dass `enforce` auf `monitor` zurückgefallen ist: Der Websocket meldet Erfolg, die Antwort hat kein `mode`-Feld. | `mode` + `fail_safe`-Grund in die Antwort, im Panel anzeigen |
| O7 | mittel (Unterberechtigung) | Ein Label auf einem Eltern-Gerät erreicht keine Entitäten von Child-Devices. HAs Target-Auflösung zieht Kinder mit ein. | Semantik festlegen (HA-Parität?) |
| O8 | niedrig | Reload des Eintrags unter `enforce` = kurz volle Rechte (Unload stellt wieder her, Setup wendet neu an) | akzeptieren oder Restore nur bei Entfernen (`async_remove_entry`) |
| O9 | niedrig | Sonderfälle bei der Eingabeprüfung: `area_id` im Options-Flow nicht gegen die Registry geprüft; Floor ohne Areas im Panel nicht löschbar; Entity-IDs nicht mit `valid_entity_id` geprüft; Linter-Label-Pfad ungetestet (`FakeResolver` ohne `entity_ids_for_label`) | einzeln nachziehen |

Bewusst so und dokumentiert, kein Befund: Grants auf Area/Floor/Label schließen versteckte Entitäten
und solche mit `entity_category` ein (`test_includes_hidden_entities`).

## Was sich als solide erwiesen hat

- Alle schreibenden Services nutzen `async_register_admin_service`, alle Websocket-Befehle haben
  `@require_admin`, und das Panel ist mit `require_admin=True` registriert.
- Der Compiler erzeugt ausschließlich `entity_ids`-Blätter `{read}` bzw. `{read, control}`.
  `_assert_allow_only_policy` prüft das vor jedem Schreiben. Die Entity-Area gewinnt über die
  Geräte-Area, und die Area-Vererbung bei Child-Devices entspricht HA.
- Die Rollen-ID-Namensräume (`:`, `tessera*`, `__`) verhindern Kollisionen mit `system-*`.
- Der Versions-Guard steht vor jedem nativen Write. Die Lockout-Prüfung ist plan-weit und wird vor
  jedem Write wiederholt. Ein fehlgeschlagener Apply wird sofort zurückgerollt.
- D9 schließt die eigene Domain exakt aus. Acks sind auf Version und Hash gepinnt.

## Prozess-Befund

Der Nightly-Job `HA upcoming line (pre-release)` war seit dem Erscheinen von HA 2026.11 täglich rot,
und zwar genau mit dem Signal, für das er gebaut ist. Bemerkt wurde das erst, als ein Nutzer #71
öffnete. **Auflage:** Ein roter Nightly gehört in die tägliche Beobachtung (Task `tessera-hacs-watch`).
