# Codex-Arbeitsauftrag — E3.3: `apply_enforce_plan` (nativer Write, dormant, dev-only)

Von **Claude** · 2026-06-30 · **E3-Build Schritt 3 von ~5** · **⚠️ ERSTER SCHARFER SCHRITT (nativer `hass.auth`-Write)** · Human-Go erteilt (Michael), Dev-Instanz verfügbar
**Branch:** `enforce/e3.3-apply` (von `main`) → PR · **scharf, ABER dormant: schreibt nativ WENN aufgerufen, wird aber in KEINEM Modus getriggert (Verdrahtung = E3.5)** · **security-KRITISCH**.

## 0. Leitplanken (hart)
- **Dormant:** `apply_enforce_plan` wird **NICHT verdrahtet** (kein Aufruf aus `async_setup_entry`/Mode-Handling/websocket/config-flow). Reines Callable. „mode == enforce → compute+apply" kommt erst **E3.5** (mit Restore).
- **Default-Mode bleibt `monitor`.** Kein Pfad triggert den Write automatisch.
- **Echte native Writes:** Unit-Tests **HA-frei** (gemockte Adapter/Spies). Der **echte Write-E2E gegen `ha-tessera-dev:8124`** (NIE Live-CM5) kommt bei **E3.5** mit Restore + Wiring — E3.3 liefert Code + HA-freie Tests (die E1-Adapter-Schreibmechanik ist bereits Spike-bewiesen D1/D2/D4).

## 1. Aufgabe
`async def apply_enforce_plan(hass, plan: EnforcePlan) -> ApplyResult` (neues `apply.py` oder in `mode_manager.py`). **Schreibt NUR über die E1-Adapter** (kein roher `_store._groups`-Zugriff). Feste Reihenfolge, fail-safe:
0. **Vorbedingung:** `plan["blocked"]` True → **refuse, KEIN Write** (`refused_reason="blocked"`).
1. **VERSION-REASSERT** (defense-in-depth): `AuthPolicyStoreAdapter(hass).assert_supported_version()` — sonst refuse `"version"`.
2. **LOCKOUT-PRECHECK:** `RecoveryController(hass, UserBindingAdapter(hass)).async_assert_no_admin_lockout()` — ≥1 aktiver Owner/Admin muss bleiben; sonst refuse `"lockout"`.
3. **GRUPPEN schreiben:** je `GroupPlan` → `AuthPolicyStoreAdapter.async_set_group_policy(group_id, name, policy)`. **§8.1 allow-only-Assertion am Choke-Point ergänzen:** vor dem Write asserten, dass die Policy **nur Allow-Leaves** enthält (kein bare-`True`, kein `{entities: True}`, kein `{domains: …}`, kein Shortcut) — sonst `UnsafeAuthTarget`, kein Write.
4. **USER rebinden:** je `UserBindingPlan` → `UserBindingAdapter.async_bind_full_superset(user, target_group_ids, expected_tessera_group_ids=<die tessera:*-Teilmenge von target_group_ids>)`. REPLACE, **No-Drop** (volles Superset), Promotion-/Lockout-Guard (bestehend in `_validate_full_group_superset`).
5. **ORPHANS entfernen:** **NACH** den Rebinds, je `orphan_group_id` → `async_remove_group(group_id)` (kein User referenziert sie nach Schritt 4 mehr).
6. **CACHE:** `user.invalidate_cache()` je betroffenem User (in `async_bind_full_superset` bereits enthalten).

**Reihenfolge-Begründung (Teilfehler-Sicherheit):** Gruppen → Rebind → Orphans, sodass ein Abbruch **keinen Lockout** hinterlässt (Gruppen geschrieben, User noch nicht rebound → User in alten Gruppen = kein Lockout; nächster Apply re-konvergiert idempotent). **Echtes Two-Phase-Journal + Rollback = E3.4.** Hier: bei Write-Fehler **STOPPEN** → `ok=False`, `written-so-far` exakt, redigiertes Log, **nie still weiterschreiben**.

## 2. ApplyResult
```python
class ApplyResult(TypedDict):
    ok: bool
    groups_written: list[str]
    users_rebound: list[str]
    orphans_removed: list[str]
    refused_reason: str | None  # "blocked"|"version"|"lockout"|"allow-only"|"write-error"|None
    detail: list[str]           # REDIGIERT — nie User-Namen/Token/Hashes/Secrets
```

## 3. Hard-Regeln
- **Nur über E1-Adapter schreiben**; allow-only-Assertion am Choke-Point; Lockout-Precheck; Owner/system_generated nie angefasst (Plan/Adapter garantieren das bereits).
- **Keine Secrets** in `detail`/Logs (keine User-Namen/Token/Hashes — nur IDs/Counts wo nötig, redigiert).
- Python 3.13, ruff/black/mypy-strict + pytest grün, **HA-frei testbar** (Adapter + RecoveryController als Spies/Fakes).
- `apply.py` (neu) + `auth_adapter.py` (nur die allow-only-Assertion ergänzen) + `tests/`. **Nicht verdrahten.**

## 4. DoD + Tests (HA-frei)
- `apply_enforce_plan` + `ApplyResult` + allow-only-Assertion in `async_set_group_policy`.
- Tests: (a) sauberer Plan → Gruppen/Bindungen/Orphans über Adapter-**Spies** in Reihenfolge Gruppen→Rebind→Orphans; (b) `blocked`-Plan → KEIN Write, `refused="blocked"`; (c) unsupported Version → kein Write, `refused="version"`; (d) Lockout-Precheck schlägt an → kein Write, `refused="lockout"`; (e) Policy mit `{entities: True}`/bare-True → allow-only → kein Write, `refused="allow-only"`; (f) Write-Fehler mitten drin → STOPP, `ok=False`, `written-so-far` korrekt, kein weiterer Adapter-Call; (g) Orphans-Removal erst NACH allen Rebinds (Spy-Reihenfolge); (h) No-Drop: `expected_tessera_group_ids` = volle tessera:*-Teilmenge des Targets; (i) `detail` secrets-frei.
- CI grün · PR + Bericht → **Adversarial-Panel** (Reihenfolge lockout-sicher? allow-only greift wirklich vor JEDEM Gruppen-Write? kein Write bei blocked/version/lockout? No-Drop-`expected` korrekt? Partial-Failure ohne Lockout? Secrets-frei?). **Echter Dev-E2E erst E3.5.**
