All cited guards are verified against the actual code:

- `async_restore_exact_groups` calls `_assert_supported_version()` (line 258) then `_validate_exact_restore_binding` → admin-demotion guard at 450-451, managed-user (owner/system_generated) refusal, allowed-binding-group restriction. Confirmed.
- The `is_active is False` identity comparison appears at both `restore.py:110` and `auth_adapter.py:523` — the weak-finding fix target is real and accurate.
- TOCTOU: no lock anywhere; all three mutators are non-atomic load→check→save with await points. Confirmed.
- Dormancy: zero product callers; `__init__.py` only a deferred-phase TODO. Confirmed.

The verdicts are accurate. One minor citation drift: the restore user-loop op is `async_restore_exact_groups` (the secrets-dormancy block's "bind:" event labels are test-harness names, not product symbols) — does not change any conclusion. I have everything needed to issue the consolidated gate.

---

# QS-Gate — PR #24 `NoSilver78/tessera` (E3.4 Restore/Recovery, dormant)

Branch `enforce/e3.4-restore` → `main` · +685/−10 · 8 Dateien · Worktree `/private/tmp/tessera-enforce-e34-restore`

## Entscheidung: **PASS MIT AUFLAGEN**

Restore schreibt in Recovery-Richtung nativ in den HA-Auth-Store — daher strenger Maßstab auf Lockout-Sicherheit und Immutability. Beide Kerneigenschaften halten im real erreichbaren (single-writer, dormanten) Pfad nachweislich. Es bleiben zwei Robustheits-/Härtungs-Auflagen, die **vor** der E3-Live-Verdrahtung erledigt sein müssen, plus zwei Test-Coverage-Lücken. Kein Befund blockiert das dormante Merge selbst.

---

## Befunde nach Severity

Es gibt **keine** Critical- oder High-Befunde mehr. Die ursprünglich als High vermutete Lockout-Lücke (`async_restore_to_pre_install` entfernt letzten Owner/Admin) ist **widerlegt**: Entfernung trifft ausschließlich `tessera:*`-Gruppen (`async_list_tessera_group_ids` filtert auf `TESSERA_GROUP_PREFIX`, auth_adapter.py:164), `system-admin` wird nie entfernt; der einzige Lockout-Pfad (Snapshot demotiert letzten Admin) wird vom Precheck `_assert_restore_owner_or_admin_survives` **vor dem ersten Write** und vor jedem Bind/Remove geblockt (restore.py:65/71/78, events==[]).

### MEDIUM

**M1 — Test | Journal-Rollback nur vakuös abgedeckt | Auflage vor E3.**
`decide_startup_recovery` liefert korrekt `"rollback"` bei offenem Journal (state.py:91-92, fail-safe verifiziert), aber **nichts konsumiert die Entscheidung**: `snapshot_from_state_data` (die Brücke vom persistierten State zur `AuthRecoverySnapshot`, die Restore braucht) hat **null** Referenzen in Produkt **und** Tests. Persist (store) und Restore (restore.py) sind getrennte Inseln; der End-to-End-Pfad „crashed half-apply → rollback → Restore auf den immutablen Snapshot" ist nie geübt.
**Korrektur:** Round-trip-Test ergänzen: `mark_apply_in_progress(snapshot)` → reload → `decide_startup_recovery == "rollback"` → `snapshot_from_state_data(...)` → `async_restore_to_pre_install(...)` → assert Rebind auf Pre-Install-Gruppen. Übt die aktuell tote `snapshot_from_state_data` und beweist Aktionierbarkeit der Rollback-Entscheidung.

**M2 — Test | Partial-Failure von Restore ungetestet (Restore ist nicht atomar) | Auflage vor E3.**
Empirisch reproduziert: bricht `async_remove_group` bei der 2. von n `tessera:*`-Gruppen ab, bleibt die 1. Gruppe dauerhaft entfernt ohne Rollback (`group_ids_removed=['tessera:a']`, status `failed`/`write-error`). Bind-Fehler bei späterem User lässt frühere User rebound. Der vorhandene Test T4 scheitert nur am allerersten User (0 vorherige Writes). Das Result-Dict meldet Partial-Progress wahrheitsgemäß → **Coverage-Lücke, kein Contract-Bruch** — aber eine Recovery-Routine, die einen ausgesperrten Auth-Store reparieren soll, darf nicht ungetestet halb-restauriert liegen bleiben.
**Korrektur:** Partial-Failure-Test für Mid-Loop-Bind- **und** -Remove-Fehler (welche Writes committed, Result-Accounting stimmt). Explizit entscheiden + dokumentieren/testen: best-effort-continue vs. fail-fast.

### LOW

**L1 — Restore | `is_active`-Identitätsvergleich statt Truthiness | robustheitshärtung.**
`getattr(user, "is_active", True) is False` (restore.py:110, gespiegelt auth_adapter.py:523) schließt nur das Literal-`False`-Objekt aus. Falsy-aber-nicht-`False` (`0`, `None`, `''`) gilt als AKTIV und kann als alleiniger überlebender Admin gutgeschrieben werden (Szenario N: `is_active=0`-Admin → Restore läuft). Auf echten HA-`User`-Objekten ist `is_active` ein echter `bool` → **heute nicht ausnutzbar in Produktion**; Risiko nur gegen Test-Doubles oder ein künftiges truthy-Sentinel in HA.
**Korrektur:** Truthiness verwenden: `if not getattr(user, "is_active", True):` an beiden Stellen (restore.py:110 + auth_adapter.py:523).

**L2 — Store | Immutability/Journal nicht atomar unter NEBENLÄUFIGEN Erst-Schreibern (TOCTOU) | Auflage vor E3.**
Verifiziert: **kein** `asyncio.Lock` im Modul; alle drei State-Mutatoren (`async_set_pre_install_snapshot`, `async_mark_apply_in_progress`, `async_clear_apply_in_progress`) sind nicht-atomare load→check→save-Sequenzen mit await-Punkten. Zwei nebenläufige Erst-Sets können beide `None` sehen → last-writer-wins, verletzt die „IMMUTABLE"-Zusage in diesem Fenster (in isolierter Probe reproduziert: ok=2). **Heute nicht erreichbar** (Pfad dormant; HA-Storage = ein Event-Loop, ein logischer Writer/Apply-Zyklus). Wird real, sobald der E3-Caller diese Writes nebenläufig absetzt (überlappendes apply + uninstall, re-entranter config-flow).
**Korrektur:** Vor der E3-Verdrahtung load+check+save aller drei Mutatoren unter einem `asyncio.Lock` serialisieren (oder CAS-/Seq-Check beim Save). Regressionstest: zwei nebenläufige `async_set_pre_install_snapshot`, genau einer gewinnt. Single-Writer-Annahme in `spec-e3-enforce.md` notieren.

**L3 — Restore | Nicht-Atomizität dokumentieren | optional.**
Reihenfolge ist strikt all-rebinds-dann-all-removals (restore.py:67-80) → keine dangling Group-Referenz möglich, Zustand bleibt konsistent-by-omission. Residual ist reine Nicht-Atomizität (früh rebound-te User committed, spätere nicht).
**Korrektur (optional):** Im Docstring vermerken, dass Restore nicht atomar ist.

**L4 — Restore | Redundante Per-Iteration-Prechecks | optional.**
Die 3 Aufruforte von `_assert_restore_owner_or_admin_survives` (pre-loop + per bind + per remove) sind innerhalb eines Calls beweisbar invariant: der Precheck wertet Snapshot-TARGET-Gruppen aus, die Schleife mutiert keine Nicht-Snapshot-User → Re-Checks ändern nichts und sind als geschrieben untestbar.
**Korrektur (optional):** Auf den einen Pre-Loop-Check reduzieren, **oder** einen Test ergänzen, der live Survivor-State zwischen Iterationen mutiert und so die Re-Checks rechtfertigt.

---

## Positive Beobachtungen (verifiziert gegen Code)

- **Lockout-Sicherheit hält im realen Pfad** (widerlegt den High-Verdacht): Removal trifft nur `tessera:*`; `system-admin` nie entfernt. Precheck vor erstem Write blockiert Sole-Admin-Demotion (refused `lockout`, events==[]). Zusätzlich unabhängige `LockoutRisk` in `async_restore_exact_groups` bei Admin-Demotion (`_validate_exact_restore_binding`, auth_adapter.py:450-451).
- **Reihenfolge Rebind→Remove korrekt** (restore.py:67-80), deckt sich mit Docstring; Event-Order empirisch `[bind:*, …, remove:*, …]`.
- **Survivor-Check gegen korrekten Post-Restore-Zustand** ausgewertet (Snapshot-Target für Snapshot-User, Current für Nicht-Snapshot-User); Owner-Short-Circuit und `system_generated`-Ausschluss konsistent mit den Skip-Regeln in `_is_unmanaged_user`.
- **`async_restore_exact_groups` voll geguardet:** Version-Guard (`_assert_supported_version`, 258), Owner→`LockoutRisk`, system_generated→`UnsafeAuthTarget`, Admin-Demotion→`LockoutRisk`, allow-all/Nicht-Namespace→`UnsafeAuthTarget`; Targets auf `{system-admin, system-read-only}` ∪ `tessera:*` beschränkt. Drop von `tessera:*` für Nicht-Admin erlaubt.
- **Immutability sequentiell hart:** `async_set_pre_install_snapshot` re-liest persistierten State und wirft `TesseraStateError("pre_install_snapshot is immutable")` bei Non-`None` (store.py:124-125). Journal kann Snapshot weder überschreiben noch verlieren (mark setzt nur bei `None`, clear flippt nur das Bool).
- **`decide_startup_recovery` fail-safe:** validiert zuerst, dann `rollback` bei offenem Journal, `none` nur bei geschlossenem — kein silent-continue-Pfad.
- **Invariante „apply_in_progress ⇒ snapshot" zentral & doppelt** in `validate_state_data` durchgesetzt (state.py:50-51, läuft bei JEDEM load UND save). Rekonstruiert frischen dict/list-Baum → kein Aliasing in HAs In-Memory-Cache.
- **Secret-Disziplin lückenlos:** State persistiert nur `{user_id, group_ids}`; `validate_state_data` lehnt jede Fremd-Key ab; grep auf password|token|hash|secret|name|email findet **null** Treffer in state/restore/store; `_redacted_error_detail` gibt ausschließlich `[type(error).__name__]` zurück (verifiziert: token-förmige Exception-Args leaken nicht).
- **Dormanz bestätigt:** null Produkt-Aufrufer von Restore/State/Journal; `__init__.py` erwähnt Restore nur als deferred-phase-TODO im Docstring.
- **Vier Test-Cluster substanziell** (nicht vakuös): immutable-once, rebind-before-remove, lockout (events==[]), owner/system_generated-skip — gegen die echte Implementierung reproduziert.

---

## Nicht prüfbares / Vorbehalte

- **Mutationsproben** laufen laut Auftrag separat — dieses Gate trifft keine Aussage zur Mutations-Score-Abdeckung; M1/M2 adressieren genau die Pfade, die Mutationstests sonst als „survived mutants" markieren würden.
- **`.pytest_cache/lastfailed` mit Eintrag für `test_restore.py`** ist ein Artefakt der homeassistant-losen Sandbox-Collection (Import-Fehler), **kein** echter Test-Fehlschlag — die Logik passt bei direkter Ausführung gegen die Implementierung.
- **Echtes HA-`User.is_active`** ist ein `bool` (Annahme aus HA-Quelle, nicht in diesem PR verifizierbar) — L1 ist deshalb heute nicht ausnutzbar; die Härtung ist defensiv gegen künftige HA-Änderungen.
- **Citation-Drift (unkritisch):** Die Restore-User-Schleife ruft `binding_adapter.async_restore_exact_groups` (restore.py:72), nicht eine generische „bind"-Operation; die „bind:"-Eventlabels in den Verdikten sind Test-Harness-Namen, keine Produkt-Symbole. Ändert keine Schlussfolgerung.

**Bedingungen für PASS:** M1, M2, L2 (Lock + Regressionstest) und L1 sind vor der E3-Live-Verdrahtung zu erledigen; L3/L4 optional. Für das dormante Merge von PR #24 selbst ist nichts davon blockierend.

Geprüfte Dateien (absolut): `/private/tmp/tessera-enforce-e34-restore/custom_components/tessera/{restore.py,auth_adapter.py,state.py,store.py}`