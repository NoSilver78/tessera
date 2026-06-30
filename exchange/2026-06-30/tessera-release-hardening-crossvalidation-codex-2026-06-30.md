# Tessera Release-Hardening Crossvalidation — Codex

Datum: 2026-06-30T19:56:57Z  
Branch: `chore/release-hardening`  
HEAD: `462c614 exchange: Codex cross-validation request for release-hardening (independent review)`  
Scope: unabhängiges Review gegen die 11 Linsen aus `exchange/2026-06-30/tessera-release-hardening-crossvalidation-request-claude-2026-06-30.md`.

## Kurzurteil

**NO-GO für Public-Release / Public-Flip in diesem Stand.** Der Code enthält eine merge-/release-blockierende Recovery-Lücke im scharfen Apply-Fehlerpfad und mehrere öffentliche Doku-/Release-Gate-Drifts, die Nutzer und Reviewer über den realen Enforce-Status bzw. die HACS-/HA-Version-Gates irreführen können.

Unverändert respektiert: kein Review von Live-`/Volumes/config`, keine Secrets gelesen, keine Codeänderungen vorgenommen.

## Findings

### CXR-01 · Linse 1/2/6 · Severity HIGH · Kind correctness/security/test-gap · Ort `custom_components/tessera/__init__.py:327`, `custom_components/tessera/mode_manager.py:247`, `tests/test_init.py:416`

**Evidenz:** `_apply_enforce_mode` schreibt vor dem Apply den Recovery-Journal (`async_mark_apply_in_progress`) und ruft dann `apply_enforce_plan` auf (`__init__.py:327` bis `__init__.py:331`). Bei jedem nicht-`applied` Ergebnis wird nur `_fail_safe_to_monitor(... refresh_preview=True)` aufgerufen (`__init__.py:338` bis `__init__.py:344`). `apply_enforce_plan` kann aber nach bereits erfolgten nativen Writes fehlschlagen: Gruppen werden ab `mode_manager.py:247` geschrieben, Bindings ab `mode_manager.py:257`, Orphans ab `mode_manager.py:266`; bei Exceptions werden die bereits geschriebenen IDs im Result belassen (`mode_manager.py:270` bis `mode_manager.py:286`). Der Test `test_enforce_apply_failure_fails_safe_and_leaves_journal_open` fixiert genau dieses Verhalten: nach `apply` folgt nur `monitor_preview`, der Store steht auf `monitor`, und `apply_in_progress` bleibt `True` (`tests/test_init.py:459` bis `tests/test_init.py:471`).

**Risiko:** Der sichtbare Modus ist danach `monitor`, aber native Auth kann bereits teilweise geändert sein. Bis zur nächsten Startup-Recovery bleibt ein potenziell scharfer Halbzustand aktiv. Das widerspricht dem Release-Versprechen „kein stiller Halbzustand“ und ist bei Auth-Write-Pfaden lockout-/privilege-relevant.

**Empfehlung:** Auf jedem Apply-Fehler nach geöffnetem Journal sofort den Pre-Install-Snapshot über denselben Restore-Pfad zurückrollen. Nur wenn der Restore selbst fehlschlägt, Journal offen lassen und Repair-Issue eskalieren. Tests ergänzen: Teilfehler nach Gruppenwrite, nach Bindingwrite und nach Orphan-Removal müssen Restore vor Monitor-Preview beweisen.

### CXR-02 · Linse 5/7/6 · Severity MEDIUM · Kind config-admin-surface/test-gap · Ort `custom_components/tessera/websocket.py:142`, `custom_components/tessera/websocket.py:174`, `tests/test_websocket.py:70`

**Evidenz:** `async_set_matrix_grant` speichert eine Policy-Änderung über das Admin-Panel (`websocket.py:142` bis `websocket.py:176`), ruft danach aber nur `_refresh_preview` auf (`websocket.py:174` bis `websocket.py:176`). `_refresh_preview` kompiliert und schreibt `compiled`/`lint`/`preview` in `hass.data` (`websocket.py:179` bis `websocket.py:199`), geht aber nicht durch den zentralen Enforce-Pfad. Die Tests modellieren die Matrix-API sogar ausdrücklich als auth-frei: `FakeHass.auth` wirft bei jedem Zugriff (`tests/test_websocket.py:70` bis `tests/test_websocket.py:80`). Im Gegensatz dazu nutzt der Options-Flow für geladene Entries den zentralen Moduspfad (`config_flow.py:489` bis `config_flow.py:500`).

**Risiko:** Bei einem geladenen Entry im Modus `enforce` kann das Panel Policy/Preview ändern, ohne native HA-Auth erneut anzuwenden. UI, Store und nativer Auth-Zustand driften auseinander, bis ein anderer Recompile-/Reload-Pfad läuft.

**Empfehlung:** Nach Matrix-Policy-Writes bei `mode=enforce` denselben zentralen Handler wie der Options-Flow auslösen oder die Panel-API explizit auf „monitor-only/staged“ begrenzen und im Response sichtbar machen. Tests für `monitor` ohne `hass.auth` und `enforce` mit zentralem Apply-Aufruf trennen.

### CXR-03 · Linse 8/10/11 · Severity HIGH · Kind docs-code-drift/release-blocker · Ort `README.md:11`, `README.md:35`, `README.md:67`, `custom_components/tessera/__init__.py:227`

**Evidenz:** Die README warnt, Enforce sei „noch nicht aktiv“ (`README.md:11` bis `README.md:14`), die Enforce-Maschinerie ruhe und sei nicht verdrahtet (`README.md:35` bis `README.md:36`), und `mode=enforce` schreibe nicht (`README.md:67` bis `README.md:69`). Der Code tut inzwischen das Gegenteil: `_compile_for_mode` ruft bei `MODE_ENFORCE` `_apply_enforce_mode` auf (`__init__.py:227` bis `__init__.py:229`), und dieser Pfad führt zu `compute -> snapshot -> journal -> apply` (`__init__.py:303` bis `__init__.py:344`).

**Risiko:** Die öffentliche Startseite unterschlägt den real aktiven nativen Write-Pfad. Nutzer könnten `enforce` mit falscher Sicherheitsannahme aktivieren; Reviewer/HACS-Nutzer sehen keine korrekte Risikokommunikation.

**Empfehlung:** README vor Public-Flip aktualisieren: Enforce ist verdrahtet, Default bleibt `monitor`, Enforce ist sicherheitskritisch, nur nach Dev-Proven/Soak aktivieren. Changelog/Release Notes konsistent dazu anpassen.

### CXR-04 · Linse 5/10 · Severity MEDIUM · Kind source-doc-drift · Ort `custom_components/tessera/auth_adapter.py:1`, `custom_components/tessera/mode_manager.py:112`, `custom_components/tessera/restore.py:50`, `custom_components/tessera/state.py:80`

**Evidenz:** Mehrere sicherheitsrelevante Module behaupten weiterhin, sie seien dormant bzw. nicht verdrahtet: `auth_adapter.py:1` bis `auth_adapter.py:8`, `mode_manager.py:112` bis `mode_manager.py:118`, `mode_manager.py:203` bis `mode_manager.py:211`, `restore.py:50` bis `restore.py:63`, `state.py:80` bis `state.py:89`. Tatsächlich importiert und nutzt `__init__.py` diese Pfade im Enforce-, Startup-Recovery-, Mode-Switch- und Unload-Verhalten.

**Risiko:** Source-nahe Reviewer, Contributor und Security-Audits bekommen ein falsches Bild der aktiven Write-/Restore-Oberfläche. Das ist bei privaten HA-Auth-APIs mehr als kosmetisch.

**Empfehlung:** Dormant-Terminologie in aktiven Modulen entfernen und durch aktuelle Vertragsinvarianten ersetzen: wann gelesen wird, wann geschrieben wird, welche Guards gelten, wann Restore/Recovery läuft.

### CXR-05 · Linse 11/10 · Severity MEDIUM · Kind release-doc-drift · Ort `RELEASE_READINESS.md:152`, `RELEASE_READINESS.md:169`, `RELEASE_READINESS.md:287`

**Evidenz:** `RELEASE_READINESS.md` markiert `hacs.json` als fehlend (`RELEASE_READINESS.md:152` bis `RELEASE_READINESS.md:154`, erneut `RELEASE_READINESS.md:285` bis `RELEASE_READINESS.md:288`) und sagt, es gebe nur `ci.yml`, also keinen HACS-/hassfest-Workflow (`RELEASE_READINESS.md:168` bis `RELEASE_READINESS.md:170`). Im Repo existieren aber `hacs.json`, `.github/workflows/validate.yml`, `custom_components/tessera/brand/icon.png` sowie `custom_components/tessera/brand/icon.svg`.

**Risiko:** Das zentrale Release-Gate-Dokument ist nicht mehr belastbar. Es kann falsche Blocker melden, echte Restblocker verdecken und Panel-/Owner-Gates in die Irre führen.

**Empfehlung:** `RELEASE_READINESS.md` auf aktuellen Repo-Stand bringen: vorhandene Artefakte abhaken, verbleibende harte Gates separat ausweisen (Release/Tag, Public-Flip, HACS-Job blocking, HA-Minimum-Pin, Dev-Proven/Soak).

### CXR-06 · Linse 11/6 · Severity MEDIUM · Kind ci-release-gate · Ort `.github/workflows/validate.yml:21`

**Evidenz:** Der HACS-Job in `validate.yml` ist vorhanden, aber absichtlich nicht blockierend: `continue-on-error: true` (`validate.yml:21` bis `validate.yml:37`). Die Kommentare erklären, dass dies bis zum Public-Flip erwartet ist und danach entfernt werden soll (`validate.yml:4` bis `validate.yml:9`, `validate.yml:26` bis `validate.yml:28`).

**Risiko:** Für einen Public-Release ist das korrekt als temporärer Zustand dokumentiert, aber noch kein hartes Gate. Wenn der Public-Flip/Release ohne Entfernung dieser Zeile erfolgt, kann HACS-Validation rot sein, ohne den Merge/Release zu stoppen.

**Empfehlung:** Vor Public-Flip `continue-on-error` entfernen und einen grünen HACS-Lauf als Release-Gate verlangen. Falls privates Repo weiterhin blockiert, Public-Flip und HACS-Gate in genau dieser Reihenfolge als Release-Runbook fixieren.

### CXR-07 · Linse 2/8/9/11 · Severity MEDIUM · Kind release-metadata/docs-drift · Ort `hacs.json:1`, `README.md:98`, `SECURITY.md:72`, `docs/MAINTENANCE.md:21`

**Evidenz:** README, Security- und Maintenance-Doku versprechen für den ersten Release einen HACS-HA-Minimum-Pin über `hacs.json` (`README.md:98` bis `README.md:99`, `SECURITY.md:72` bis `SECURITY.md:75`, `docs/MAINTENANCE.md:21` bis `docs/MAINTENANCE.md:24`). Die aktuelle `hacs.json` enthält aber nur den Namen (`hacs.json:1` bis `hacs.json:3`).

**Risiko:** Der Code-Guard blockiert zwar den Schreibpfad bei abweichender HA-Version, aber die Distribution verhindert Installation/Update auf ungeeigneten HA-Versionen noch nicht wie dokumentiert. Das ist besonders relevant, weil der Auth-Schreibpfad private HA-APIs nutzt.

**Empfehlung:** Vor Release die dokumentierte `homeassistant`-Mindestversion in `hacs.json` ergänzen oder die Doku ehrlich auf „nur Code-Guard, noch kein HACS-Pin“ ändern. Release-Checklist muss diese Invariante prüfen.

## Lens Summary

1. **Correctness / Async Lifecycle:** Blockierend wegen CXR-01. Startup-Recovery ist vorhanden, aber Apply-Fehlerpfade rollen nicht sofort zurück.
2. **Auth Security:** Blockierend wegen CXR-01; zusätzlich HACS-/HA-Version-Pin-Drift in CXR-07.
3. **Simplification:** Keine eigenständige Simplification-Blockade gefunden. Hauptbedarf ist Entfernen veralteter Dormant-Schichten in Text/Doku, nicht neue Abstraktion.
4. **Type Sharpness:** Kein neuer Typfehler-Befund. `pyproject.toml` setzt `mypy strict = true`; CI ruft `mypy custom_components/tessera` auf und nutzt damit die Projektkonfiguration.
5. **Consistency / Public Surface:** CXR-02, CXR-03 und CXR-04 zeigen Drift zwischen Panel/API, Source-Doku und öffentlicher README.
6. **Test Fidelity:** Tests decken viele Guards ab, fixieren aber bei CXR-01 das unsichere Verhalten und modellieren die Matrix-API bei CXR-02 nur auth-frei.
7. **Config / Admin Surface:** Options-Flow nutzt den zentralen Handler; Matrix-WebSocket nicht. CXR-02 bleibt relevant.
8. **README / Contributor Onboarding:** README ist in Bezug auf Enforce nicht releasefähig (CXR-03); Contributor-Doku ist ansonsten plausibel.
9. **Security Docs Honesty:** Security-Doku benennt Scope und Limits gut, driftet aber beim HACS-Version-Pin (CXR-07).
10. **Docs-Code Drift:** Mehrere harte Drifts: öffentliche README, Source-Docstrings, Release-Readiness (CXR-03 bis CXR-05).
11. **Release Readiness:** NO-GO bis CXR-01 und die Release-Gate-Drifts CXR-03/CXR-05/CXR-06/CXR-07 behoben sind.

## Gegenchecks / Nicht-Funde

- `mode=off` und `mode=monitor` berühren laut vorhandenen Tests keinen nativen Auth-Pfad; kein gegenteiliger Codepfad gefunden.
- Options-Flow-Änderungen an einem geladenen Entry gehen über `_compile_for_mode_safely` und sind daher nicht Teil des Panel-WebSocket-Befunds.
- Keine Secrets oder Live-Konfigurationswerte wurden in dieses Review übernommen.

