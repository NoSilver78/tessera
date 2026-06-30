# Codex-Arbeitsauftrag — E3.1: Mode-Manager-Skelett + Gate-Sequenz + Gruppen-Plan (read-only)

Von **Claude** · 2026-06-30 · **E3-Build Schritt 1 von ~5** · *Human-Go für E3 erteilt (Michael)* · Quelle: `docs/spec-e3-enforce.md` §2 + `docs/spec-e3-design.md`
**Branch:** `enforce/e3.1-mode-manager` (von `main`) → PR · **NON-SCHARF: kein nativer Write, kein `hass.auth`-Zugriff, dormant (nicht verdrahtet)** · security-relevant (das ist der Enforce-Orchestrator-Kern).

## 0. E3-Roadmap (Kontext — so kommt das Ganze, jeder Schritt panel-gegatet)
- **E3.1 (DIESER Task):** Mode-Manager-Skelett + Gate-Sequenz (Version→Compile→D9→Linter) + **Gruppen-Plan** (welche `tessera:<role>`-Gruppen + Policies) — **read-only, kein Write, kein Auth-Zugriff, dormant.**
- E3.2: User-Binding-Plan (liest `hass.auth`, volle No-Drop-Superset, `default_role`, Orphan-Gruppen) — read-only.
- E3.3: **scharfer nativer Write** (Adapter ausführen + allow-only-Assertion + Promotion-Guard) — **NUR gegen `ha-tessera-dev` (Port 8124), NIE Live-CM5.**
- E3.4: Restore + Two-Phase-Journal (`tessera.state`).
- E3.5: E2E + Soak.

## 1. Aufgabe (E3.1)
Neues Modul `custom_components/tessera/mode_manager.py` mit
`async def compute_enforce_plan(hass, store) -> EnforcePlan`,
das die **Enforce-Gate-Sequenz read-only** fährt und einen **Gruppen-Projektions-Plan** liefert — **ohne** nativen Write, **ohne** `hass.auth` zu berühren.

Sequenz (jede Stufe ein hartes Gate; Fehler/Block an JEDER Stelle → `blocked=True`, fail-safe, **kein Teil-Plan**):
1. **VERSION-GATE:** prüfe die unterstützte HA-Auth-Version (`auth_adapter._assert_supported_auth_version(_homeassistant_version())` bzw. die bestehende `AuthPolicyStoreAdapter.assert_supported_version`). Unsupported → `blocked`, `reason="version"`. *(Berührt `hass.auth` NICHT — nur die Versions-Konstante.)*
2. **COMPILE:** `compile_current(store, resolver, config=..., policy=...)` (rein, deterministisch).
3. **D9-GATE:** `evaluate_d9_gate(hass, config)` → bei `enforce_blocked` → `blocked`, `reason="d9"`, `block_detail = d9["blocking"]`.
4. **LINTER:** `lint_cross_role(config, policy, resolver, compiled=<aus 2>)` + `has_blocking_conflicts(...)` → `blocked`, `reason="linter"`, `block_detail = <Konflikt-Entities/User>`.
5. **GRUPPEN-PLAN:** je Rolle ein `GroupPlan {group_id: f"tessera:{role_id}", role_id, policy: <kompilierte native Policy der Rolle>}`. **Nur** die Gruppen-Projektion — **User-Bindings sind E3.2.**

## 2. Datenform
```python
class GroupPlan(TypedDict):
    group_id: str          # "tessera:<role_id>"
    role_id: str
    policy: NativePolicy   # aus compiler

class EnforcePlan(TypedDict):
    groups: list[GroupPlan]       # leer, wenn blocked
    blocked: bool
    block_reason: str | None      # "version" | "d9" | "linter" | None
    block_detail: list[str]       # z.B. blockierende D9-Domains / Linter-Konflikt-Keys
```
Deterministisch (Rollen sortiert).

## 3. Hard-Regeln (was NICHT)
- **KEIN nativer Write:** keine `_store._groups`-Mutation, kein `async_update_user`, kein Aufruf von `async_set_group_policy`/`async_remove_group`/`async_bind_full_superset`.
- **KEIN `hass.auth`-Zugriff:** keine User-Enumeration (das ist E3.2). Die Dormant-Boundary „off/monitor berühren `hass.auth` nicht" muss intakt bleiben — und E3.1 berührt `hass.auth` in **keinem** Pfad.
- **Dormant:** `mode_manager` wird **nirgends verdrahtet** (kein Aufruf aus `__init__.py`/`config_flow.py`/`websocket.py`/`monitor.py`). Reine Callable-Surface wie E1/E2/E2.5.
- Nur `mode_manager.py` (neu) + `tests/test_mode_manager.py` + optional `const.py` (Konstanten) + `schema.py` (nur der Prefix-Guard in §4). Python 3.13, ruff/black/mypy-strict grün, **HA-frei testbar** (compile/D9/linter mit Fakes/`tmp_path` mockbar).

## 4. Schema-Vorarbeit (klein, hier mit rein — B.1 aus `spec-e3-design.md`)
`tessera:`-Namespace reservieren: in `validate_config_data` (schema.py) `role_id` **abweisen**, wenn es `:` enthält **oder** (case-insensitiv) mit `tessera` beginnt — **symmetrisch** in der Membership-Key-Validierung. (Sonst kollidiert ein role_id mit dem `tessera:<role>`-Gruppen-Namespace.) + Tests (`role_id="tessera:x"` und `role_id="a:b"` → `TesseraSchemaError`).

## 5. DoD
- `compute_enforce_plan` + `EnforcePlan`/`GroupPlan` + Schema-Prefix-Guard.
- **Tests:** (a) sauberer Store → `blocked=False`, je Rolle ein korrekter `GroupPlan` (`tessera:<role>` + Policy = Compiler-Output); (b) D9 blockiert (installierte UNKNOWN-Komponente) → `blocked=True, reason="d9"`, `groups==[]`; (c) Linter-Konflikt (SoD) → `blocked=True, reason="linter"`; (d) unsupported HA-Version → `blocked=True, reason="version"`; (e) Schema-Prefix-Guard greift. **(f) Beweis kein-Auth:** ein `hass`-Fake, dessen `.auth`-Property `raise`t, durchläuft `compute_enforce_plan` **ohne** Exception (= auth nie berührt).
- Alle Tests grün · CI grün · **PR mit Bericht** → **Adversarial-Panel** (Gate-Reihenfolge lückenlos + fail-safe bei JEDER Stufe? wirklich kein Write / kein `hass.auth`? Plan deterministisch?).
