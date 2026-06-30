# Codex-Arbeitsauftrag — E3.2: User-Binding-Plan + default_role + Orphan-Detection (read-only)

Von **Claude** · 2026-06-30 · **E3-Build Schritt 2 von ~5** · Quelle: `docs/spec-e3-design.md` Teil B + `docs/spec-e3-enforce.md` §2 Schritt 5
**Branch:** `enforce/e3.2-binding-plan` (von `main`) → PR · **read-only: liest `hass.auth` (User-Enumeration), aber KEIN nativer Write; dormant (nicht verdrahtet)** · security-relevant.

## 0. Wo wir sind
E3.1 (Gate-Sequenz + Gruppen-Plan) ist gemerged + dormant auf main. E3.2 ergänzt die **User-Binding-Seite** des Plans — weiterhin **read-only** (kein Write). E3.3 ist der scharfe Write (nur `ha-tessera-dev`).

## 1. Aufgabe
Erweitere `compute_enforce_plan` (in `mode_manager.py`) um Bindings + default_role + Orphans. **Nur der Erfolgs-Pfad** (nach allen Gates) wird ergänzt — die Gate-/Fail-closed-Logik aus E3.1 **unverändert lassen** (alle Block-Pfade liefern weiter `bindings:[]`, `orphan_group_ids:[]`).

### Datenform (Ergänzung)
```python
class UserBindingPlan(TypedDict):
    user_id: str
    target_group_ids: list[str]   # volles Superset, sortiert
# EnforcePlan += "bindings": list[UserBindingPlan], "orphan_group_ids": list[str]
```

### Schritte (read-only, im Erfolgs-Zweig)
1. **Gemanagte User enumerieren:** `hass.auth.async_get_users()` (über den E1-Read-Pfad `RecoveryController.async_snapshot`/`UserBindingAdapter.snapshot_user_groups` oder direkt) → filtere `not system_generated and not is_owner`. (Owner + system_generated bleiben unangetastet — Lockout strukturell unmöglich.)
2. **Pro gemanagtem User das Ziel-Superset (No-Drop):** `{f"{TESSERA_GROUP_PREFIX}{role}" for role in config["membership"]["by_user"].get(user_id, [])}` **∪ erhaltene System-Gruppen**. **Promotion-Guard (B.4):** `system-admin` kommt NUR ins Ziel-Superset, wenn der User es **aktuell hat** ODER eine `is_admin`-Rolle trägt — sonst nicht. Ergebnis **sortiert** (No-Drop = das VOLLE Set, nie ein Delta).
3. **Empty-Union → default_role:** hat ein gemanagter User KEINE (gültige) Rolle, ist sein Ziel `{f"{TESSERA_GROUP_PREFIX}{DEFAULT_ROLE_ID}"}` (deny-by-omission Baseline) — **NIE `system-users`** (= force-injected allow-all = Privileg-Eskalation, §6.3). `DEFAULT_ROLE_ID` als Konstante (z.B. `"__default__"`); die `tessera:__default__`-Gruppe mit **leerer** Policy (`{"entities": {"entity_ids": {}}}`) zu `groups` hinzufügen, wenn mind. ein User sie braucht.
4. **Orphan-Detection:** existierende `tessera:*`-Gruppen (read via `AuthPolicyStoreAdapter.async_get_group_policy` bzw. Store-Read der `_groups`) ohne korrespondierende Rolle (nicht in `config["roles"]`, nicht `DEFAULT_ROLE_ID`) → `orphan_group_ids` (sortiert).

## 2. Hard-Regeln (was NICHT)
- **KEIN nativer Write:** kein `async_update_user`, kein `async_set_group_policy`/`async_remove_group`, keine `_store._groups`-Mutation, kein `_async_persist_auth_store`. **Nur READS** auf `hass.auth` + Store.
- **Dormant:** weiterhin nirgends verdrahtet (kein Aufruf aus `__init__.py` etc.). Off/monitor berühren weiterhin kein `hass.auth` — E3.2 läuft nur im (dormanten) enforce-Plan-Pfad.
- **No-Drop:** `target_group_ids` ist immer das VOLLE Superset (alle Rollen-Gruppen + zu erhaltende System-Gruppen), nie ein Teil-Array. **default_role NIE `system-users`.** Promotion-Guard respektieren.
- Python 3.13, ruff/black/mypy-strict + pytest grün, **HA-frei testbar** (auth-Reads + Store mit Fakes/Spies mockbar).

## 3. DoD + Tests
- `bindings` + `orphan_group_ids` + ggf. default_role-Gruppe im EnforcePlan; alle Block-Pfade unverändert leer.
- **Tests:** (a) Multi-Rollen-User → volles Superset (alle `tessera:<role>` + `system-admin` wenn admin); (b) **No-Drop:** 2-Rollen-User → BEIDE Gruppen im Superset; (c) Empty-Union-User → `tessera:__default__`, assert **NICHT** `system-users`; (d) **Promotion-Guard:** Non-Admin ohne is_admin-Rolle → KEIN `system-admin` im Superset; ein User mit aktueller system-admin-Mitgliedschaft → behält sie; (e) Owner + system_generated → NICHT in `bindings`; (f) Orphan: existierende `tessera:ghost`-Gruppe ohne Rolle → in `orphan_group_ids`, `tessera:<echte-rolle>` nicht; (g) **kein Write** (Write-Adapter-Methoden via Spy/Trap nie aufgerufen); (h) Block-Pfade (D9/Linter) → `bindings==[]`.
- CI grün · PR + Bericht → **Adversarial-Panel** (No-Drop lückenlos? default_role nie system-users? Promotion-Guard greift? Orphan-Logik korrekt? wirklich kein Write?).
