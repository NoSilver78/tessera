All findings have already been confirmed with verdicts, so I have what I need to write the report directly.

# Tessera Produkt-Audit (Security + Code-Quality)

## Gesamt-Einschätzung

**Kein Gate-Blocker. Foundation ist solide und für die Phase-1-Grenze (monitor-only, read-only gegenüber HA-Auth) korrekt fail-safe.** Alle 39 bestätigten Findings sind verifiziert; in der Querprüfung wurden mehrere Severities **nach unten** korrigiert (mehrere `high`→`low`, einige `medium`→`nit`). Das bestätigt: es gibt **keine ausnutzbare Schwachstelle** und **keinen aktiven Verhaltens-Bug**.

Kernbefunde:
- **Security:** Alle „security"-Findings sind defense-in-depth / Hygiene auf einer heute nicht scharfgeschalteten Enforce-Schicht — kein Daten-/Auth-Leak, keine Privilege-Eskalation. Der einzige unauthentifizierte Trigger (`tessera.recompile`) verändert nichts Natives und gibt nichts zurück.
- **Größte reale Lücken sind Doku/Tests**, nicht Code: fehlende `services.yaml`, komplett unübersetzter OptionsFlow, und mehrere **maskierende/vacuous Test-Assertions** über sicherheitsrelevanten Guards (Mutationstests M2/M8/M15/M16 überleben).
- **Wichtigste sicherheitskritische Vormerkung für E3:** Restore-on-Unload ist als Docstring-Zusage vorhanden, aber weder implementiert noch getestet — vor Enforce-Scharfschaltung Pflicht (CONTRACT.md §11).

**Empfohlene Umsetzungsreihenfolge:** P1-Tests zuerst (sie schützen die auditierten Security-Eigenschaften vor stillem Regress), dann P0/P2-Doku (rein additiv, risikolos), dann P3 in einem Aufwasch pro Datei.

---

## P0 — Security-must-fix

**Es gibt keinen klassischen P0.** Kein Finding ist ausnutzbar; nichts blockt das Phase-1-Gate. Die folgenden zwei Punkte sind die einzigen mit Security-Relevanz, die bewusst **terminiert** werden müssen — nicht heute zu fixen, aber verbindlich vor E3:

### E3-Pflicht (vor Enforce-Scharfschaltung — kein heutiger Code-Fix)
- **`__init__.py` · `async_unload_entry` (Z.58-66) — Restore-on-Unload fehlt.** *Problem:* Docstring sagt Native-Policy-Restore beim Unload zu; nicht implementiert, nicht getestet. Heute kein Lockout-Risiko (Enforce dormant, kein Native-Write). Ab E3 würde ein Tessera-Remove verwaiste `tessera:`-Gruppen/Bindings hinterlassen. *Änderung:* vor E3 `RecoveryController.async_restore` + `async_assert_no_admin_lockout` implementieren **und** testen (Recreate/Restore-Proof = Freigabe-Blocker laut CONTRACT.md §11). Beachten: `async_restore` braucht einen zur Enforce-Zeit via `async_snapshot` erzeugten Snapshot, der über die Restart/Uninstall-Boundary persistiert (heute nur in-memory). · **behaviorRisk: none** (heute reine Vormerkung).
- **`auth_adapter.py` · `async_set_group_policy` (Z.145-167), create-branch — kein `system_generated`-Re-Check.** *Problem:* Create-Zweig prüft `system_generated` nicht (nur Update-Zweig). Strukturell nicht ausnutzbar (Namespace-Guard `_assert_tessera_group_id` + HA-System-Gruppen außerhalb `tessera:`); Adapter dormant. *Änderung:* beim E3-Wiring optional asserten, dass das Factory-Ergebnis nicht `system_generated` ist (belt-and-suspenders im Apply-Pfad). · **behaviorRisk: none**.

---

## P1 — Korrektheit / Quality

Diese Findings betreffen **Test-Fidelity über sicherheitsrelevanten Guards** und **Duplizierung mit Drift-Risiko**. Die Tests sind das eigentliche Risiko: sie sind heute grün, würden aber einen Regress der auditierten Fail-safe-/RBAC-Invarianten **nicht** auffangen. **Alle P1-Test-Änderungen sind behaviorRisk=none (test-only).**

### `tests/` — maskierende / fehlende Assertions (sofort umsetzbar, test-only)

- **`tests/test_schema.py` · `test_policy_schema_rejects_unsafe_leaf_shapes` (Z.78-84).** *Problem:* `pytest.raises(TesseraSchemaError)` ohne `match=` — Entfernen des Bare-Bool-Guards (`schema.py:207-208`, HA allow-all-Shortcut) lässt Suite grün (M8 survived). *Änderung:* parametrisieren mit `match=` je Fall: `match="bare bool"` (True), `match="unsupported permission keys"` (`{entities:True}`/`{domains:True}`), `match="must be boolean"` (`{read:"yes"}`), `match="must not be empty"` (`{}`). · **behaviorRisk: none**.
- **`tests/test_compiler.py` · fehlender control-only `entity_override` (betrifft `compiler._normalize_leaf` Z.89-90).** *Problem:* Invariante `control ⇒ read` im Override-Pfad ungetestet; M2 (control impliziert read NICHT mehr) survived. *Änderung:* `entity_overrides = {"light.sofa": {"operator": {"control": True}}}` → assert `compiled["operator"]["entities"]["entity_ids"]["light.sofa"] == {"read": True, "control": True}`. Optional: control-only Override zieht reinen read-Area-Grant hoch. · **behaviorRisk: none**.
- **`tests/test_compiler.py` · `test_compile_is_deterministic` (Z.192-211).** *Problem:* tautologisch (`compile(...) == compile(...)`, gleiche Inputs; dict-`==` ist ordnungsunempfindlich) — Entfernen aller `sorted()` (M18/M19) survived. *Änderung:* dieselbe Policy mit **umgekehrter** Insertion-Reihenfolge bauen und `list(compiled) == sorted(compiled)` + `list(entity_ids) == sorted(entity_ids)` asserten (Muster wie `test_linter_sorts_…`). Hinweis: FakeResolver muss Entities **unsortiert** liefern, sonst greift die entity-id-Assertion vacuous. · **behaviorRisk: none**.
- **`tests/test_auth_adapter.py` · `test_auth_trap_records_swallowed_auth_access` (Z.500-518) + analog `test_init.py:90`.** *Problem:* `assert "compiled" not in entry_data` ist vacuous (Key war nie da); Stale-Cleanup-Pop (`__init__.py:141-142`, M15) survived — Fail-safe „verwirf veraltete Projektion bei späterem Compile-Fehler" ungetestet. *Änderung:* `entry_data` mit Stale-Werten vorbelegen: `{"store": RaisingStore()/ModeStore("monitor"), "compiled": {"OLD":1}, "preview": {"OLD":1}}`, dann assert beide **entfernt**. Achtung: muss den **direkten** `_compile_for_mode_safely`-Pfad nutzen (test_init's `async_setup_entry` überschreibt `domain_data[entry_id]` mit frischem Dict). · **behaviorRisk: none**.
- **`tests/test_init.py` · Panel-Registrierung `_async_register_matrix_panel` (`__init__.py:109-131`, `require_admin=True` Z.128) — kein Test.** *Problem:* `require_admin=True → False` (M16) survived; FakeHass setzt kein `hass.http`, Pfad wird per `if not hasattr(hass,"http")` (Z.114) übersprungen → der Admin-Gate des RBAC-Panels ist ungetestet. *Änderung:* `hass`-Double mit `http` (awaitable `async_register_static_paths`) + Fakes für `async_register_panel`/`StaticPathConfig`; asserten: Aufruf mit `require_admin=True`, `frontend_url_path=PANEL_URL_PATH`, `webcomponent_name=PANEL_WEBCOMPONENT`, `DATA_PANEL_REGISTERED` gesetzt, Idempotenz (2. Setup kein Re-Register). Implementierung: `tessera_init.async_register_panel`/`StaticPathConfig` monkeypatchen (wie bei `TesseraStore`). · **behaviorRisk: low** (neuer Test gegen real HA-Symbole — Fakes nötig).
- **`tests/test_init.py` · Panel-Removal-Branch (`__init__.py:73-75`) ungetestet.** *Problem:* Unload-Test setzt nie `DATA_PANEL_REGISTERED` → `async_remove_panel` + Pop sind tote Branch im Test. *Änderung:* im bestehenden Unload-Test vor letztem Unload `hass.data[DOMAIN][DATA_PANEL_REGISTERED]=True` + `async_remove_panel`-Fake; assert genau ein Aufruf mit `PANEL_URL_PATH` und Sentinel danach weg (vom `isinstance(value,dict)`-Guard korrekt ignoriert). · **behaviorRisk: none**.
- **`tests/test_config_flow.py` · gesamte `TesseraOptionsFlow`-Maschinerie (`config_flow.py:190-433`) ungetestet.** *Problem:* nur freie Helfer + `async_step_user` getestet; alle 7 Steps, `except (KeyError, TesseraSchemaError)`-Re-Render-Branches, `_save_preview_finish`, Leerstand-Forms (`no_roles`/`no_area_grants`) und `unknown_action`-Abort sind ungeprüft. *Änderung:* mit FakeHass/FakeStore je Aktion Happy-Path (`_save_preview_finish`→CREATE_ENTRY, Store gespeichert) + Fehlerfall (`errors={"base":"invalid"}`); `async_step_action` unknown→ABORT `unknown_action`; `_form_remove_role` ohne Rollen→`no_roles`. `AreaEntityResolver.from_hass` monkeypatchen. · **behaviorRisk: none**.

### Code-Duplizierung mit Drift-Risiko

- **`monitor.py` / `__init__.py:171-179` / `config_flow.py:457-465` / `websocket.py:184-194` — 3× kopierte Preview-Refresh-Sequenz.** *Problem:* identischer Compile→Lint→Log→`entry_data`-Write-Kern dreifach; Divergenz beginnt bereits (websocket setzt zusätzlich `entry_data['store']` + schreibt `hass.data` zurück). *Änderung:* gemeinsame `refresh_entry_preview(hass, entry_id, entry_data, store, *, config, policy)` in `monitor.py`. **Kritisch:** (1) Mode-Gating bleibt an den Call-Sites in `__init__`/`config_flow` **vor** dem Aufruf — websocket ist bewusst **ungated** (kompiliert auch bei `mode==off`); Gating in den Kern zu ziehen würde das still ändern (kein Test fängt es). (2) websocket-Extra-Writes (`store`, `hass.data`-Writeback) bleiben am websocket-Call-Site. (3) Policy einmal am Caller laden (Test `policy_loads==2` bleibt). · **behaviorRisk: low** (subtile off-mode-Falle, sorgfältig umsetzen + testen).
- **`auth_adapter.py` · `_assert_supported_version` (Z.181-187 + Z.239-245) — byte-identisch in zwei Adaptern.** *Problem:* sicherheitsrelevanter Fail-Closed-Versions-Guard copy-paste; Drift latent (Schwellenwert selbst ist via Konstante `SUPPORTED_HA_AUTH_VERSION` schon single-sourced, aber Logik+Message dupliziert). *Änderung:* Modul-Funktion `_assert_supported_auth_version(ha_version)` (Stil wie die bestehenden freien Guard-Funktionen Z.375-395), beide Klassen delegieren. Token/Namespace-Guards **nicht** anfassen. · **behaviorRisk: low** (Tests prüfen nur Exception-Typ, kein Methodenname).

---

## P2 — Doku

Rein additive Metadaten/i18n/Prosa — **behaviorRisk=none durchgehend**, keine Test-/Security-/Verhaltens-Auswirkung. Sicher sofort umsetzbar.

### Fehlende HA-Standard-Artefakte (öffentliche API)
- **`custom_components/tessera/services.yaml` — fehlt** (Service `tessera.recompile` registriert in `__init__.py:95`, Handler `del call` = parameterlos). *Änderung:* `services.yaml` mit `recompile:` (keine `fields:`) + `services.recompile`-Block in `strings.json` **und** `translations/en.json` (name/description). Spike-Datei nur als lose Vorlage (Domain dort `tessera_spike`). Korrektur ggü. Finding: HA loggt **keine** Setup-Warnung — Effekt ist rein kosmetisch (Service ohne Name/Beschreibung in Dev-Tools).
- **`strings.json` + `translations/en.json` — OptionsFlow komplett unübersetzt.** *Problem:* nur `config.user` übersetzt; 6 Step-IDs (init/set_mode/add_role/remove_role/add_area_grant/remove_area_grant), `action`-Selector-Optionen, Error-Bases (`invalid`/`no_roles`/`no_area_grants`) und `unknown_action`-Abort rendern als rohe Keys. *Änderung:* `options`-Block (`step.<id>.{title,description,data.<feld>}`, `error.*`, `abort.*`) in `strings.json` ergänzen → nach `translations/en.json` spiegeln (HA lädt `translations/` zur Laufzeit; `strings.json` = Quelle). Optional `de.json` für Pilzbuche-8-Betrieb.

### README / Einstiegs-Doku
- **`README.md` — keine Integrator-/Sicherheitsaussage.** *Problem:* dokumentiert nur Zwei-Agenten-Modell/Spike-Status; README Z.3 bewirbt sogar „echt durchgesetzt" als Ziel ohne den „noch nicht durchgesetzt"-Caveat (irreführend). *Änderung:* Abschnitt „Funktionsumfang & Sicherheitsstand (Phase 1)": Modi off/monitor/enforce; **enforce fällt aktuell auf Monitor-Preview zurück, KEINE nativen HA-Auth-Writes**; Admin-Panel unter Sidebar „Tessera" (`require_admin`); `tessera.recompile`-Dienst.

### Docstring-/Vertrags-Lücken (load-bearing Semantik benennen)
- **`compiler.py · compile_policies` (Docstring Z.40-50; Verhalten Z.72-78).** Negativer/level-loser `entity_override` **entfernt** eine per Area-Grant exponierte Entität vollständig (`role_entities.pop`, Z.78) — „negative override schlägt area grant". *Änderung:* Returns-Satz ergänzen + optional Inline-Kommentar an Z.77-78. *Auch:* Re-Validierungs-Kette (`compile_policies` Z.51-52 / `lint_cross_role`) als bewussten Fail-Closed/deepcopy-Defense-in-Depth-Vertrag kommentieren („NICHT entfernen") — schützt vor gut gemeinter, security-brechender „Vereinfachung".
- **`auth_adapter.py · PermissionProbeAdapter.check_entity` (Z.251-256).** Docstring tautologisch; `level` wird 1:1 als nativer HA-Permission-Key durchgereicht (`read`/`control` == `POLICY_READ`/`POLICY_CONTROL`). *Änderung:* Docstring um diese Abbildung erweitern (Args/Returns).
- **`auth_adapter.py · Modul-Docstring (Z.1) + Adapter-Klassen.** „Dormant" konkretisieren: in Phase 1 **kein** Produkt-Call-Site, Writes hinter Versions-/Namespace-/Lockout-Guards fail-closed, Aktivierung erst nach D10-PASS + Panel-Review (Verweis `docs/spec-e3-enforce.md`). **Auflage:** fail-closed-Aussage auf die tatsächlich in-Adapter feuernden Guards beschränken, keinen No-Drop-Overclaim einführen.
- **`resolver.py · resolve_area_entities / resolve_all` (Z.101-134).** Docstring „narrow compiler-facing contract" ist **falsch** (Compiler nutzt `entity_ids_for_area` direkt). *Änderung:* klarstellen: gibt **ungeordnetes `set`** zurück; deterministische Reihenfolge → `AreaEntityResolver.entity_ids_for_area(s)`; realer Consumer = **Test-Suite** (`test_function_contract_returns_sets`), **nicht** Linter. (Siehe auch P3: ganz entfernen ist die Alternative.)
- **`static/tessera-panel.js` — null Kommentare.** *Änderung:* Datei-Kopf (Custom-Element, `hass`-Property, WS-Befehle `tessera/matrix/get|set_grant`) + Block-Kommentar über `_toggle` mit Zyklus `none → read → read+control → none`. Präzise: bei `_grantCell` **überschreibt** `control` das `read`-Label (nicht „impliziert").
- **`__init__.py · _has_loaded_entries (Z.187-192) + Sentinels (Z.30-32).** Kommentar an Sentinels („bewusst keine dicts, damit `isinstance(value,dict)` sie ignoriert"); im Docstring klarstellen, dass alle Nicht-dict-Sentinels via Filter ausgenommen sind. `key != DATA_SERVICE_REGISTERED` ist redundant — als rein defensiv kommentieren (konsistent zu Z.91), nicht entfernen.
- **`const.py · STORAGE_KEYs (Z.10-11) + MODE_* (Z.13-16).** Inline-Kommentare: STORAGE_KEYs = persistente `.storage/`-Schlüssel an `STORAGE_VERSION` gekoppelt; MODE_* = einzig erlaubte, via `schema.MODES` validierte Werte; enforce in Phase 1 inert. (Auf `line-length=88` achten.)
- **`websocket.py · MatrixGrant (Z.53-58) + _get_loaded_entry_data (Z.258-264).** Docstring: `MatrixGrant` = fürs Panel normalisiertes Gegenstück zu `schema.PermissionLeaf` (beide Keys immer **vorhanden**, nicht immer True). Einzeiler an `_get_loaded_entry_data`: Single-active-entry-Annahme (`unique_id=DOMAIN`).

---

## P3 — Modernisierung / Readability / Nits

Überwiegend **behaviorRisk=none**; die markierten Refactors mit `low` brauchen kurze Test-Gegenprüfung. Gut gebündelt pro Datei umsetzbar.

### `custom_components/tessera/linter.py`
- **`v1-inert` hartkodiert (Z.90, Z.105)** statt `compiler.BY_GROUP_PROJECTION_MODE`. *Änderung:* Konstante importieren/verwenden (Import aus `.compiler` existiert bereits). Test-Literale (`test_linter.py:180/~184`) optional umstellen — oder bewusst als Wire-Wert-Pin belassen. · **none**.
- **`_iter_levels` (Z.236-238)** — Ein-Zeilen-Indirektion, 1× genutzt; Reihenfolge an Call-Site (set-comprehension) irrelevant. *Änderung:* entfernen + an Z.232 `("read","control")` inline, **oder** Modul-Konstante `LEVELS`. Beim Entfernen auch `from collections.abc import Iterable` (sonst F401). · **none**.
- **Inkonsistente `read/control`-Darstellung** (`_iter_levels` vs. Inline-Tupel `("control","read")` Z.127). *Änderung:* benannte Konstanten `LEVELS_READ_FIRST`/`LEVELS_CONTROL_FIRST`. **Auflage:** Z.127 muss **control-first** bleiben (tragend — `control_restricting_roles` wird erst nach control-Durchlauf gesetzt). Korrektur ggü. Finding: behauptete Tupel an Z.221-226/182-192 existieren nicht. · **none**.
- **`_conflicts_for_user` (Z.109-162)** — dichteste Funktion; tragende Invariante (control-first für read-Suppression) implizit. *Änderung:* reine Hilfsfunktion `_is_cross_role_conflict(exposing_set, restricting_set) -> bool` (die 4 Set-Bedingungen benennen) + 2-Zeilen-Kommentar über `for level in ("control","read")` (WARUM control zuerst). Logik/Reihenfolge **nicht** ändern. · **behaviorRisk: low** (vor Merge gegen `test_distinct_read_carve_…` testen; Fuzz bestätigte Identität).

### `custom_components/tessera/schema.py`
- **`PermissionKey` (Z.10) ungenutzt** — toter Alias, identisch zu `linter.LintLevel`. *Änderung:* entfernen, **oder** zentral definieren und in `linter` wiederverwenden (DRY; schema.py = kanonisch). · **none**.
- **`TesseraPolicyData.staging` (Z.54; Z.85; Z.168-170)** — validiert/defaulted/deepcopy'd/persistiert, von keinem Consumer gelesen; einziger Grund für `total=False`. *Änderung:* da docs als Phase-2/3-Feature dokumentiert → als bewusst inert markieren (analog `by_group`-Muster). Alternativ entfernen (dann Key + `total=False` mit). · **behaviorRisk: low** (Persistenz-Format; alte Stores verwerfen `staging` schadlos).

### `custom_components/tessera/config_flow.py`
- **`TesseraOptionsFlow.__init__` (Z.193-196) + `async_get_options_flow` (Z.182-187)** — pre-2024.11-Pattern. Da unter **privatem** `self._config_entry` gespeichert, **kein** 2025.12-Deprecation-Break; Target HA 2026.6.4 → reine Modernisierung. *Änderung:* `__init__` droppen, `TesseraOptionsFlow()` zurückgeben (`@staticmethod @callback`), `self._config_entry` → `self.config_entry`. Tests instanziieren OptionsFlow nicht → effektiv kein Test-Change. · **behaviorRisk: low**.
- **`"::"`-Separator** (Z.49 encode, Z.146-147 decode; + `websocket.py:168` encode) — Magic-String an 3 Stellen, implizite websocket↔config_flow-Kopplung. *Änderung:* `GRANT_SEPARATOR="::"` + `encode_grant`/`decode_grant` in `config_flow.py`. · **none**.

### `custom_components/tessera/__init__.py`
- **`tessera.recompile` ohne Admin-Guard (Z.81-96)** — jeder authentifizierte User triggert Recompile (CPU/Registry-Walk); kein Native-Write, keine Rückgabe. *Änderung:* leichter Admin-/Rate-Guard im Handler **und/oder** als harmlosen Trigger dokumentieren (P2 services.yaml deckt den Doku-Teil). Falls Guard: Test `test_recompile_service_refreshes_compiled_preview` ruft Handler direkt mit `object()` → Guard muss call ohne Context tolerieren (oder Test anpassen). · **behaviorRisk: low**.
- **Unsauberer Teardown (`async_unload_entry` vs. statischer Pfad/WS)** — `/tessera_static` + WS-Commands + `DATA_WEBSOCKET_REGISTERED`-Flag bleiben beim Unload stehen. Security-harmlos (eine public JS-Datei; WS admin-only, sauberer `LookupError`). *Änderung:* `DATA_WEBSOCKET_REGISTERED` beim Unload poppen (Re-Register idempotent); statischen Pfad belassen. · **behaviorRisk: low**.
- **`@callback`/`ServiceCall`-Typisierung** — `_handle_recompile(call: object)` + kein `@callback`. *Änderung:* `from homeassistant.core import ServiceCall, callback` (ServiceCall unter `TYPE_CHECKING`), Handler `call: ServiceCall`, `del call` droppen/umbenennen. **Hinweis:** `@callback`-Marker sind harmlos, aber an diesen Call-Sites weitgehend wirkungslos (kein markerinspizierender Dispatcher) — primär ist die `ServiceCall`-Typisierung der Mehrwert. · **behaviorRisk: low** (Annotationen, kein Verhalten).

### `custom_components/tessera/resolver.py`
- **`resolve_area_entities` / `resolve_all` (Z.101-134)** — nur von Tests genutzt, irreführender „compiler-facing"-Docstring, `resolve_all` greift auf privates `_device_area_by_id()` + dupliziert die Disabled/Area-Schleife. *Änderung:* **entfernen** (samt `test_function_contract_returns_sets` + 2 Imports) — sauberster Weg, da totes Public-API; **oder** Docstring fixen (P2) + `resolve_all` über öffentliche `effective_areas()` umschreiben (den `[]`-Bind-Trick + privaten Zugriff eliminieren). · **behaviorRisk: low** (durch `test_function_contract_returns_sets` gedeckt; bei Entfernung Test mit weg).
- **`from_hass` Return-Annotation `-> AreaEntityResolver`** → `-> Self`. *Änderung:* `from typing import Self`; einziger Factory im Repo. · **none**.

### `custom_components/tessera/const.py`
- **`MODES: Final = {…}`** ist mutables `set`. *Änderung:* `frozenset({…})` (wie `ALLOWED_NATIVE_GROUP_IDS`); alle Uses (Membership, `sorted(MODES)`) unverändert. Defense-in-depth auf security-relevanter Allow-List. · **none**.

### `custom_components/tessera/manifest.json`
- **`single_config_entry` fehlt; `iot_class: local_polling` unzutreffend.** *Änderung:* `"single_config_entry": true` ergänzen (unique_id-Guard als belt-and-suspenders behalten — **nicht** „den Flow vereinfachen", das bräche 2 Guard-Tests); `iot_class` → `"calculated"`. **Auch `docs/spec-phase1-core.md:84`** (prescribt `local_polling`) angleichen oder als Entscheidung markieren (SoT-Konsistenz). · **behaviorRisk: low** (Metadaten; Spec-Drift vermeiden).

### `custom_components/tessera/auth_adapter.py`
- **`check_entity` (Z.251-256) — toter Rebind `permission = level`.** *Änderung:* inline: `return bool(user.permissions.check_entity(entity_id, level))`. · **none**.

### `custom_components/tessera/static/tessera-panel.js`
- **`_grantCell` (Z.307-308)** — `state` und `label` identischer Ausdruck. *Änderung:* eine Variable für Klasse + Button-Text. · **none**.
- **Default-Grant `{read:false,control:false}` dupliziert (Z.42-45, 303-306).** *Änderung:* Helfer `_grant(areaId, roleId)`. **Auflage:** Z.48 (`current.control ? {…}`) ist ein State-Target, **kein** Lookup — **nicht** durch `_grant()` routen (würde Toggle brechen). · **none**.
- **`this._loading` im Konstruktor nicht initialisiert** (gelesen Z.13, 222). *Änderung:* `this._loading = false;` ergänzen (truthiness-äquivalent). · **none**.
- **`_toggle` Tri-State (Z.46-51) ↔ `_grantCell` (Z.302-308)** — Zustandsautomat unkommentiert. *Änderung:* 1-Zeilen-Zyklus-Kommentar + optional reine `_cycleGrant(current)`. `_escape`-Härtung **nicht** anfassen. · **none**.

### `tests/` — Infra-Nits
- **`tests/test_websocket.py · test_matrix_websocket_requires_admin (Z.285-292)** koppelt an „`require_admin` raises eager". *Änderung:* Kommentar ergänzen **oder** `pytest.raises` um explizites `await`. **none**.
- **Kein `conftest.py`/Stub** — pure Logik-Module nur mit echtem HA importierbar (`__init__.py` zieht `frontend/http/panel_custom` top-level; pytest scheitert lokal ohne HA). *Optional DX:* (a) in README/CONTRACT vermerken, dass Tests echtes HA (CI) brauchen, **oder** (b) **conditional** `tests/conftest.py` mit `sys.modules`-Stubs (nur wenn HA fehlt → no-op in CI). Verwandt: die 3 HA-Top-Level-Imports in `__init__.py` in die Funktionskörper ziehen (Lazy-Import-Muster wie `resolver.from_hass`) macht Logik-Submodule HA-frei importierbar. · **behaviorRisk: low** (Import-Verschiebung; Lazy-Symbole nur in Funktionskörpern genutzt, kein Re-Export — mechanisch sicher).

---

## Umsetzungs-Cheatsheet

**Sofort sicher (none) — ein Aufwasch:** alle P2-Doku/i18n/services.yaml; P3-nits in `linter.py`/`schema.py`/`const.py`/`auth_adapter.py`/`tessera-panel.js`/`resolver.py(Self)`/`config_flow.py(::-Separator)`; die test-only P1 mit none (test_schema match=, test_compiler control-only + determinism, test_auth_adapter/test_init stale, panel-removal, OptionsFlow-Coverage).

**Vorsichtig + testen (low):** `monitor.py`-Refactor (off-mode-Falle), `_conflicts_for_user`-Extraktion (Fuzz/Test gegen carve-out), `auth_adapter._assert_supported_version`-Dedup, OptionsFlow-Modernisierung, `__init__`-Teardown/Guard/`ServiceCall`, `manifest.json` (+Spec), `staging`-Entscheidung, conftest/Lazy-Import, Panel-Registrierungs-Test (M16).

**Nicht heute — E3-Pflicht:** Restore-on-Unload + No-Admin-Lockout (Blocker laut CONTRACT.md §11), `system_generated`-Re-Check im create-branch.