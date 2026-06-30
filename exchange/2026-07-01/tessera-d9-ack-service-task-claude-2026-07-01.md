# Codex-Auftrag: D9-Ack-Admin-Service (Analyse-Gap #11)

**Von:** Claude (Architektur/Gate) · **An:** Codex (Implementierer) · **Datum:** 2026-07-01
**Typ:** **Feature** auf sicherheitskritischem Pfad (Override eines Auth-Veto) · **Risiko:** mittel-hoch — höchste Sorgfalt

## Branch-Basis
- **Basiere auf `main`** (HEAD `12519aa`; #17 + CXR-02 sind gemergt). Branch: `feature/d9-ack-service`.
  PR **gegen `main`**. Claude gate't + fährt eine **unabhängige R7-Review** vor dem Merge.

## Kontext — der Gap
Das D9-Gate (A+E v2) liest Acks aus `config["d9_acks"]` und überschreibt damit den Veto eines
auth-berührenden Components (`_ack_matches` in `d9_gate.py`: matcht nur bei **gleichem domain + version +
content_hash**). **Die Read-Seite existiert — es fehlt jede Oberfläche, die einen Ack SCHREIBT.** Heute kann
ein Admin einen legitimen, aber vetoeten Custom-Component nicht freigeben.

`D9AckData` (schema.py:34) ist schon definiert: `{version: str|None, content_hash: str, accepted_at: str}`,
liegt in `config["d9_acks"]: dict[domain, D9AckData]` (schema.py:53). **Acks laufen nicht ab** — sie sind an
version+content_hash gebunden und verfallen automatisch, sobald sich der Component ändert.

## DER Korrektheits-Hinge (nicht verhandelbar)
Der Service muss `version` + `content_hash` **exakt so** berechnen, wie das Gate sie bei der Prüfung
berechnet — **sonst matcht der Ack nie** und der Service ist wirkungslos. Das Gate (`evaluate_d9_gate`,
d9_gate.py:178–205) tut:
```python
root = Path(hass.config.path("custom_components"))
disk_components = await _run_executor(hass, _scan_custom_components, root)   # dict[domain, _DiskComponent]
loader_components = await _async_get_custom_components(hass)
# je domain:
version = _component_version(integration, disk)     # integration = loader_components.get(domain)
content_hash = disk.content_hash                     # disk = disk_components.get(domain)
```

## Aufgabe — Umsetzung
### 1. Geteilter Helfer in `d9_gate.py` (Quelle der Wahrheit für version+hash)
```python
class D9AckTarget(TypedDict):
    version: str | None
    content_hash: str

async def compute_component_ack_target(hass: _HassLike, domain: str) -> D9AckTarget | None:
    """Return the (version, content_hash) the D9 gate will check for `domain`.

    Reuses the gate's own scan primitives so an ack recorded from this is
    guaranteed to match at gate time. Returns None if the component is not on
    disk (cannot be acknowledged).
    """
```
- **Exakt dieselben Primitive** wie das Gate verwenden: `_scan_custom_components` (via `_run_executor`),
  `_component_version`, `disk.content_hash`. **Den Gate-Loop NICHT umbauen** (sicherheitskritisch) — der
  Helfer macht seinen eigenen Scan mit denselben Funktionen; Konsistenz ist über die geteilten Primitive
  garantiert und wird per Test gepinnt (s.u.).
- `self_domain`-Logik ist hier irrelevant (der Helfer berechnet nur version+hash; ob ein Component
  überhaupt vetoed wird, entscheidet weiter das Gate).

### 2. Services in `__init__.py` — **admin-only**
- **`tessera.acknowledge_component`** und **`tessera.revoke_component_ack`**.
- Registrierung über **`async_register_admin_service`** (`homeassistant.helpers.service`) — **NICHT** das
  ungeschützte `hass.services.async_register` (das der recompile-Service nutzt). Ein Ack ist ein bewusster
  Override eines Sicherheits-Veto → **Admin-Pflicht, fail-closed**.
- Schema: `vol.Schema({vol.Required("domain"): cv.string})`.
- Einmalige Registrierung wie `_register_recompile_service` (Guard-Flag in `domain_data`); **Unregister im
  Unload** analog zu `__init__.py:104`.

### 3. Handler-Logik (mirror `_handle_recompile`-Iteration, __init__.py:115–125)
Über die geladenen Entries iterieren (denselben `isinstance(entry_data, dict)`-Filter wie recompile —
Acks sind eine **globale** „dieser Component ist vertrauenswürdig"-Aussage, gelten also für alle geladenen
Tessera-Entries; in der Praxis ist es eine Entry):
- **acknowledge:** `target = await compute_component_ack_target(hass, domain)`; **wenn `None` → fail-closed
  `raise` (ServiceValidationError/HomeAssistantError)** „unknown or non-disk component". Sonst je Entry:
  `config = await store.async_load_config()`; `config["d9_acks"][domain] = {**target,
  "accepted_at": dt_util.utcnow().isoformat()}`; `await store.async_save_config(config)`;
  `entry_data["store"]`-Config konsistent halten; dann **`await _compile_for_mode_safely(hass, key,
  entry_data)`** (Auto-Recompile über den zentralen fail-safe Pfad — sonst greift der Ack erst beim nächsten
  Reload, dieselbe Bug-Klasse wie CXR-02).
- **revoke:** je Entry `config["d9_acks"].pop(domain, None)` (idempotent), `async_save_config`, recompile.
- **Audit:** `LOGGER.warning(...)` je Aktion mit `domain` + `version` (Audit-Spur für einen Veto-Override;
  **keine Secrets**).

### 4. UI-Strings
`services.yaml` (Service-Name + Beschreibung + `domain`-Feld) + `strings.json` + `translations/en.json`.
Vokabular konsistent zur Doku: „Acknowledge a custom component so its D9 conflict-veto is overridden for
the current installed version (admin-only; the ack auto-invalidates if the component changes)."

## Regeln / was NICHT ändern
- **`_ack_matches` / das Gate NICHT aufweichen.** Der Ack bleibt an version+content_hash gebunden.
- **Admin-Gate ist Pflicht** und muss getestet sein (non-admin → `Unauthorized`).
- Kein Verhaltenswechsel an bestehenden Pfaden außer der neuen Service-Oberfläche.
- ruff/black/mypy(strict)/pytest grün. **Keine Secrets.** Auth-Tests nur `ha-tessera-dev`, nie Live-CM5.
- **Stop-Regel:** Wenn beim Bauen ein Punkt auftaucht, den du nicht 1:1 sicher abbilden kannst
  (z. B. Mehrdeutigkeit bei Multi-Entry, Store-Save-Atomarität) → **STOPP + melden**, nicht raten.

## Tests (QUALITY.md R1–R7 — realistische Fixtures, Invarianten, Mutationsfestigkeit)
1. **Konsistenz-Hinge / End-to-End (der wichtigste):** ein realistisch vetoeter Custom-Component auf der
   (Test-)Disk → `evaluate_d9_gate` blockt ihn → Service `acknowledge_component(domain)` → erneutes
   `evaluate_d9_gate` blockt ihn **nicht mehr**. `revoke_component_ack(domain)` → blockt **wieder**. *(Dieser
   Test ist der Beweis, dass version+hash exakt matchen — Vakuum-frei.)*
2. **admin-only (R3):** non-admin-Aufruf → `Unauthorized`; admin → ok. (Neue Invarianten-Zeile.)
3. **persist + auto-recompile:** acknowledge schreibt `d9_acks[domain]` UND triggert `_compile_for_mode_safely`
   (Spy am Seam — wie die akzeptierte `test_options_flow_*`/CXR-02-Präzedenz).
4. **unknown/non-disk domain → fail-closed raise.**
5. **revoke idempotent:** revoke ohne bestehenden Ack → kein Fehler, kein Schreib-Effekt.
6. **Failure-Injection (R5):** `async_save_config` wirft → kein Halbzustand (Ack nicht „teils" persistiert);
   Service meldet den Fehler.
7. **accepted_at** wird gesetzt (audit-only), beeinflusst `_ack_matches` nicht.

**Update der Invarianten⇄Test-Tabelle in `docs/QUALITY.md`** (R3): Zeilen für „D9-Ack nur durch Admin
schreibbar" und „Ack matcht exakt die aktuelle version+content_hash (Service↔Gate-Konsistenz)".

## Definition of Done
- [ ] `compute_component_ack_target` existiert in d9_gate.py, nutzt die Gate-Primitive, `None` bei non-disk.
- [ ] `acknowledge_component` + `revoke_component_ack` **admin-only** (`async_register_admin_service`),
      Schema `{domain}`, Unregister im Unload.
- [ ] Handler: persist via `async_save_config` + **Auto-Recompile** via `_compile_for_mode_safely`; Audit-Log.
- [ ] services.yaml + strings.json + translations/en.json.
- [ ] Tests 1–7 grün; Konsistenz-/E2E-Test + admin-only-Test vorhanden; QUALITY.md-Tabelle ergänzt.
- [ ] ruff/black/mypy/pytest grün; stale-marker-CI grün; **kein Verhaltenswechsel** an bestehenden Pfaden.
- [ ] Branch `feature/d9-ack-service` gepusht + `gh pr create` gegen `main`.

## Abschlussbericht (PR-Body)
Geänderte Dateien · Zusammenfassung · Tests+Ergebnis (v.a. der E2E-Konsistenz-Beweis) · bestätigt:
admin-only erzwungen, Ack an version+hash gebunden, Auto-Recompile · Risiken/Annahmen · alles, was abwich
oder wo die Stop-Regel griff.

---
*Nach Lieferung: Claude gate't (ACCEPT/AUFLAGEN/FAIL), fährt eine unabhängige adversariale R7-Review (Hinge:
Ack↔Check-Konsistenz, Admin-Gate, Recompile-fail-safe, keine Veto-Aufweichung), Mutationsproben, Merge auf grün.*
