The task spec fully confirms the verdict structure. The named, blocking deliverables of this PR are explicit:

- §1 step 3: allow-only assertion in `async_set_group_policy` before EVERY group write — **missing**.
- §1 step 1 + 2: version-reassert + lockout-precheck inside `apply_enforce_plan` with `refused_reason` — **missing** (helpers exist but never called by apply).
- §2 ApplyResult contract with `ok` + `refused_reason in (blocked|version|lockout|allow-only|write-error|None)` — **delivered as `status`/no `ok`/no `refused_reason`**.
- §4 DoD tests (c)/(d)/(e) — **unsatisfiable as specified** because the taxonomy is unrepresentable.

Note one nuance the verdicts get slightly conservative on: spec §1 step 4 explicitly says `expected_tessera_group_ids=<die tessera:*-Teilmenge von target_group_ids>` — so the order-failsafe finding that calls the tautology a contract *violation* is partly contradicted by the task spec itself, which mandates deriving expected from the target. The audit-doc/adapter-docstring contract (compute from *current* membership) and the task spec disagree; the delivered code follows the task spec. That makes that finding "the guard is a tautology / defense-in-depth is dead" factually correct, but the framing of "mode_manager violates the §8 contract" is in tension with the task spec it was built to. I'll preserve the finding (the tautology and dead second line are real) but the final report flags the spec/audit contradiction honestly rather than presenting it as an unambiguous caller bug. Dormancy and secrets-free are confirmed.

Here is the consolidated gate.

---

# QS-GATE — PR #23: `apply_enforce_plan` (E3.3, erster nativer Write, dormant)

## ENTSCHEIDUNG: **FAIL**

Scharfer Massstab beim ersten nativen Write angelegt. Der PR liefert die Mechanik (Reihenfolge, Stop-on-Error, Dormanz) sauber, aber **die drei namentlich beauftragten, blockierenden Sicherungen DIESES PRs fehlen** und der Ergebnis-Kontrakt weicht so ab, dass die zugehörigen DoD-Tests gar nicht erfüllbar sind. Zwei `critical`-Refutierungen plus die unerfüllbare Refusal-Taxonomie → kein PASS, auch nicht „mit Auflagen", weil die fehlenden Stücke kein Nachzieh-Feinschliff sind, sondern der Kern des Auftrags (Task-Spec §1 Schritte 1–3, §2, §4 DoD c/d/e).

Wichtig zur Ehrlichkeit: Die Dormanz ist real und bestätigt — es droht **kein produktiver Schaden heute**. Das FAIL ist ein Auftrags-/Vollständigkeits-FAIL, kein „brennt-jetzt"-FAIL. Aber genau für den scharfen Write ist der Massstab Vollständigkeit der Fail-Closed-Garantien VOR dem Verdrahten.

---

## BEFUNDE NACH SEVERITY

### CRITICAL

**1. Allow-only-Assertion am Choke-Point fehlt vollständig** *(write-guards · refuted)*
- **Bereich:** `auth_adapter.py:153-175` (`async_set_group_policy`) / `mode_manager.py:219-225`
- **Problem:** Der Choke-Point prüft nur HA-Version, `tessera:`-Namespace und `system_generated`, macht dann `deepcopy(dict(policy))` (Z.166) und schreibt die Policy **verbatim** in `group.policy` (Z.169/174). Keinerlei Struktur-/Inhaltsprüfung. `bare True`, `{'entities': True}`, `{'domains': {...}}`, oder ein bare-True-Leaf `{'entities':{'entity_ids':{'x':True}}}` würden ungeprüft persistiert. Paketweiter Grep nach `allow-only`/`assert_allow`/„only allow" → **nichts** (die `_assert_allowed_binding_group_id`-Treffer sind Namespace-Checks, keine Policy-Struktur-Assertion). Das ist **kein Wiring-Zeit-Defer**: Task-Spec §1 Schritt 3 + §4 DoD-Test (e) machen die Assertion in `async_set_group_policy` zum benannten, blockierenden Liefergegenstand. `docs/spec-e3-enforce.md:46` warnt explizit: Choke-Point „schreibt sonst `{entities:True}` verbatim" — exakt das gelieferte Verhalten.
- **Korrektur:** Fail-closed-Validator vor JEDEM nativen Group-Write (in `async_set_group_policy` oder in der Group-Schleife von `apply_enforce_plan`). Verwirft: Policy ≠ `{'entities':{'entity_ids':{...}}}`-Dict; `entities == True`; jeden `domains`-Key; jedes `entity_ids[X]`-Leaf ≠ `{'read'/'control': bool}` (per `docs/concept.md` C1). Bei Verstoss `UnsafeAuthTarget`, `refused_reason='allow-only'`, kein Write. DoD-Test (e) ergänzen.

**2. Lockout-Precheck (≥1 Owner/Admin bleibt) im Write-Pfad nicht aufgerufen** *(write-guards · refuted)*
- **Bereich:** `mode_manager.py` (`apply_enforce_plan`) / Helper `auth_adapter.py:315-318`
- **Problem:** Task-Spec §1 Schritt 2 fordert `RecoveryController(...).async_assert_no_admin_lockout()` vor JEDEM Write mit `refused_reason='lockout'`. Der Helper existiert, wird aber von `apply_enforce_plan` **nie aufgerufen** (verifiziert: einziger Treffer ist die Definition). Apply nimmt injizierte Adapter + `users_by_id` und zählt keine globalen Owner/Admin-Überlebenden. Vorhandener Schutz ist nur partiell/per-User (Owner-Skip `mode_manager.py:385-388`; `_validate_full_group_superset` verhindert Demotion eines User, der system-admin aktuell hält, `auth_adapter.py:373-374`) — das ist **nicht** die geforderte fleet-weite Garantie.
- **Korrektur:** `async_assert_no_admin_lockout()` als explizite Vorbedingung am Anfang von `apply_enforce_plan` (nach blocked, vor Version/Group-Writes), refuse `'lockout'` per DoD-Test (d).

### HIGH

**3. ApplyResult/Signatur konform zum E3.3-Kontrakt — refutiert** *(write-guards · refuted)*
- **Bereich:** `mode_manager.py:25,56-59,195-262`
- **Problem:** Spec §2: `apply_enforce_plan(hass, plan) -> ApplyResult{ok, groups_written, users_rebound, orphans_removed, refused_reason in (blocked|version|lockout|allow-only|write-error|None), detail}`. Geliefert: `apply_enforce_plan(plan, policy_store, binding_adapter, users_by_id) -> {status, groups_written, bindings_written, orphan_group_ids_removed, detail}` — **kein `ok`, kein `refused_reason`**, umbenannte Keys, `hass` durch injizierte Adapter ersetzt. Die geforderte Refusal-Taxonomie ist damit **unrepräsentierbar** → DoD-Tests (c)/(d)/(e) sind wie spezifiziert nicht erfüllbar. (Die Adapter-Injektion verschiebt zugleich Version-/Lockout-Konstruktion aus apply heraus und nährt Befunde 1/2.)
- **Korrektur:** `refused_reason` (volle Taxonomie) + `ok` wiederherstellen, version/lockout/allow-only darüber routen. Falls Adapter-Injektion für HA-freie Tests gewollt ist: Adapter für die Precheck-Schritte aus `hass` IN apply bauen, Spies in Tests weiter erlauben.

**4. Choke-Point-Write hängt allein am Upstream-Compiler (keine Belt-and-Suspenders)** *(write-guards · holds, high)*
- **Bereich:** `mode_manager.py:219-225`, `docs/spec-e3-enforce.md:47`
- **Problem:** `apply_enforce_plan` vertraut `plan` vollständig, re-derived nicht via `compute_enforce_plan` und re-assertet die Policy-Form nicht. Allow-only hängt zu 100 % am Compiler (`_normalize_leaf`). Das ist exakt das „No-Drop hängt voll am E3-Caller", das der Foundation-Audit als unzureichend für die Write-Brücke markierte. Ohne §8.1-Assertion gibt es keine zweite Verteidigungslinie, wenn je ein Nicht-Compiler-Plan einläuft.
- **Korrektur:** Wird durch Befund 1 mitgelöst (Choke-Point-Assertion macht die Write-Verteidigung herkunftsunabhängig). Keine separate Änderung nötig.

**5. `expected_tessera_group_ids` macht den No-Drop-Guard zur Tautologie** *(order-failsafe · refuted, high)*
- **Bereich:** `mode_manager.py:273-277` / `auth_adapter.py:367-371`
- **Problem:** `expected_group_ids` wird aus `binding["target_group_ids"]` (NEUES Target) gefiltert auf `tessera:*` abgeleitet und dann als `expected_tessera_group_ids` übergeben, während dasselbe Target als `full_group_ids` läuft. Der Guard prüft `missing = expected - set(full_group_ids)` — per Konstruktion **immer leer**. Die Defense-in-depth-Zweitlinie ist tot; bei einem künftigen Delta-Refactor der Binding-Berechnung würde der Guard nichts fangen. Der echte No-Drop-Schutz ruht allein darauf, dass `_compute_user_bindings_and_orphans` ein volles Rollen-Superset (kein Delta) liefert (das tut es korrekt, durch Tests gedeckt).
- **Ehrliche Einschränkung:** Die Adapter-Docstring (`auth_adapter.py:209-224`) sagt „expected aus der CURRENT-Membership berechnen". Die **Task-Spec §1 Schritt 4 sagt aber wörtlich** `expected_tessera_group_ids=<die tessera:*-Teilmenge von target_group_ids>` — also genau das gelieferte Verhalten, und DoD-Test (h) verlangt es so. Spec und Audit/Docstring **widersprechen sich**. Der gelieferte Code folgt der Task-Spec. Damit ist „Guard ist Tautologie / zweite Linie tot" faktisch korrekt, aber die Einordnung als „mode_manager verletzt den §8-Kontrakt" ist gegenüber der Task-Spec zu hart formuliert.
- **Korrektur:** Den Spec/Audit-Widerspruch auflösen (Entscheidung einholen). Wenn echtes No-Drop gewollt ist: `expected` aus der aktuellen nativen `tessera:*`-Membership des Users berechnen, damit der `IncompleteSuperset`-Check ein unter-berechnetes Target fangen kann. Wenn die Spec-Semantik (Target = volle Absicht) gewollt ist: den Adapter-Check ehrlich als redundanten Sanity-Assert dokumentieren und nicht mehr als No-Drop-Guard bewerben.

**6. Nicht-atomare Sequenz kann verwaisten/teil-enforced Auth-Zustand hinterlassen** *(order-failsafe · refuted, high)*
- **Bereich:** `mode_manager.py:218-241`, `auth_adapter.py:175,186,279-308`
- **Problem:** Reihenfolge (Gruppen→Rebind→Orphans) ist für den Happy-Path korrekt. Aber apply ist eine nicht-atomare Folge unabhängiger Writes **ohne Transaktion/Rollback**. Bricht Binding bei User N ab: ALLE Group-Policies bereits neu geschrieben, User 1..N-1 rebound, N..Ende auf alten Bindings, Orphans nicht entfernt — rebound-User unter neuer (ggf. restriktiverer) Policy, un-rebound-User mit Stale-Membership = echter Teil-Enforce-Zustand. Jeder Group-Write persistiert sofort den ganzen Store (`_async_persist_auth_store`) → der Teilzustand ist **dauerhaft auf Platte**, nicht nur in-memory. `RecoveryController.async_snapshot/async_restore` existieren, werden aber nie genutzt.
- **Ehrliche Einschränkung:** Die Task-Spec §1 erklärt Two-Phase-Journal + Rollback **explizit zu E3.4** und akzeptiert für E3.3 „bei Write-Fehler STOPPEN, `written-so-far` exakt, idempotenter Re-Apply re-konvergiert". Insofern ist die **Nicht-Atomarität spec-konform** — der Befund ist berechtigt als Risiko-Markierung, aber kein PR-Verstoss. Was fehlt (und Verstoss bleibt): `written-so-far` exakt + `ok=False` über den Kontrakt (Befund 3), und `detail` sollte rebound-vs-stale-User benennen.
- **Korrektur:** Apply explizit als best-effort/non-atomic dokumentieren (Re-Apply idempotent, da Targets absolute Supersets). In `detail` festhalten, welche User rebound vs. stale blieben. Rollback ist E3.4 — hier nicht als transaktional darstellen.

### MEDIUM

**7. Lockout/allow-only-Invariante an der Apply-Schicht ungetestet** *(secrets-dormancy · weak)*
- **Bereich:** `tests/test_mode_manager.py:165-205,487-613`
- **Problem:** Ordering, blocked-no-write, beide Partial-Failure-Stops und Missing-User-Pre-Validation sind gut gedeckt. **Lücke:** Apply-Tests injizieren nur ungeguardete `SpyBindingAdapter`/`SpyPolicyStoreAdapter`. Kein Test fährt `apply_enforce_plan` gegen die echten geguardeten Adapter — also kein Apply-Test für Admin-Lockout, Owner-Skip, Namespace-Reject, Version-Block. Die im Auftrag benannte Lockout-Invariante ist an der Apply-Schicht **unverifiziert**.
- **Korrektur:** Apply-Tests mit echten `UserBindingAdapter`/`GroupPolicyAdapter` (oder Fake, der `LockoutRisk`/`UnsafeAuthTarget`/Version-Kontrakt ehrt): (a) Admin verliert system-admin → Abbruch ohne Partial-Write; (b) Owner/system_generated refused; (c) Nicht-`tessera:`-group_id refused; (d) unsupported Version blockt vor Write. DoD-Tests (c/d/e) damit erfüllbar machen (setzt Befund 3 voraus).

**8. Globaler No-Admin-Lockout-Assert fehlt — Lockout nur per-User abgesichert** *(order-failsafe · weak)*
- **Bereich:** `mode_manager.py:374-377,385-388` / `auth_adapter.py:315-318,373-374`
- **Problem:** Owner ist von Management ausgeschlossen (Recovery-Pfad überlebt). Admin-Demotion ist per-User durch `_validate_full_group_superset` (LockoutRisk) + system-admin-Retention abgesichert. Kein **demonstrierbarer** Lockout über diesen Pfad — aber **kein fleet-weites Netz**: würde die per-User-Regel je umgangen, fehlt jede Auffanglinie. Orphan-while-bound kann für erfolgreich rebound-User nicht passieren (Rebind ersetzt volle Group-Set ohne Orphans; Orphan-Removal erst nach allen Bindings).
- **Korrektur:** `async_assert_no_admin_lockout()` nach der Binding-Berechnung/-Schleife (deckt sich mit Befund 2) → Lockout-Frage definitiv geschlossen statt allein per-User.

### LOW (bestätigt korrekt / kleinere Nuancen)

- **Version-Reassert am Adapter vorhanden** *(holds, low)*: `async_set_group_policy`/`async_remove_group` rufen `_assert_supported_version()` bei jedem Write. Zwei Nuancen: (a) prüft `self._ha_version` aus Konstruktionszeit, kein Live-Read; (b) der apply-Level Version-Schritt mit `refused_reason='version'` (Spec §1 Schritt 1) fehlt — Version fällt nur als generischer Write-Error mitten in der Schleife. Optionale Härtung: expliziter Version-Reassert oben in apply.
- **detail/logs secrets-frei** *(refuted leak, low)*: Alle Interpolationen sind `f"{type(error).__name__}: {error}"` + Lint-IDs (HA-User-UUIDs, entity_ids, role-ids) — keine Tokens/Hashes/Credentials. Modul instanziiert keinen Logger, loggt detail nie; `ApplyResult.detail`/`block_detail` sind strukturierte Rückgaben. DoD-Test (i) erfüllt.
- **Stop-on-first-error** *(holds, low)*: Z.218-241 ein gemeinsames `try`, erster Fehler bricht ab, `status=failed`, sequentielle awaits → kein späterer Write. Tests 570/594 bestätigen. DoD-Test (f) erfüllt.
- **Kein Write bei blocked/Missing-User** *(holds, low)*: `plan["blocked"]` → früher Return (Z.203) vor jedem Adapter (Test 526). `_validated_binding_operations` voll-prävalidiert vor der Write-Schleife; Missing-User → `ValueError` → `status=failed`, null Writes (Test 550). DoD-Test (b) erfüllt.

---

## POSITIVE BEOBACHTUNGEN

- **Dormanz bestätigt** (verifiziert): `__init__.py`/`websocket.py`/`monitor.py`/`config_flow.py` referenzieren `mode_manager`/`apply_enforce_plan` **nicht** (Grep: NO REFS). `async_setup_entry` → `_compile_for_mode` loggt für `MODE_ENFORCE` „enforce is not implemented yet; running monitor preview only", schreibt nichts. Kein Produktpfad ruft den Write — heute kein Schadensrisiko.
- **Reihenfolge + Fail-Stop sauber umgesetzt** und durch gezielte Tests gedeckt (Group-fail stoppt vor Bindings; Bind-fail stoppt vor Orphan-Removal; Result-Accounting listet nur tatsächlich erfolgte Writes).
- **Pre-Validation-before-write** korrekt: alle Bindings werden vor dem ersten Write geprüft.
- **Schreibt ausschliesslich über E1-Adapter**, kein roher `_store._groups`-Zugriff aus apply — Architektur-Vorgabe eingehalten.
- **Secrets-Disziplin** im Rückgabepfad sauber (kein Logger, nur strukturierte Rückgabe, keine Credentials in `detail`).

---

## NICHT PRÜFBARES / OFFENE WIDERSPRÜCHE

- **Spec-vs-Audit-Widerspruch zu `expected_tessera_group_ids`** (Befund 5): Task-Spec §1 Schritt 4 + DoD (h) verlangen Ableitung aus dem **Target**; Adapter-Docstring + `spec-e3-enforce.md §8` verlangen Ableitung aus der **CURRENT-Membership**. Beide können nicht gleichzeitig die „No-Drop-Wahrheit" sein. **Entscheidung erforderlich**, bevor der Guard als No-Drop-Schutz gilt. Aus dem Code allein nicht auflösbar.
- **Echte Lockout-/Allow-only-Wirksamkeit gegen reale HA-Auth** ist nicht prüfbar, weil E2E erst E3.5 vorgesehen ist und alle Apply-Tests Spies nutzen. Die Wirksamkeit der per-User-Guards in den Adaptern ist separat (`test_auth_adapter.py`) gedeckt, aber **nicht im Apply-Verbund**.
- **Two-Phase-Journal/Rollback** (Befund 6) ist per Spec auf E3.4 verschoben — die Nicht-Atomarität ist hier bewusst akzeptiert; ob der idempotente Re-Apply in der Praxis sauber re-konvergiert, ist erst mit dem E3.5-Dev-E2E belegbar.

---

## AUFLAGEN ZUM PASS (Re-Submit)

Blockierend (Befunde 1, 2, 3): (i) Allow-only-Assertion vor JEDEM Group-Write am Choke-Point, fail-closed, `refused_reason='allow-only'`. (ii) `async_assert_no_admin_lockout()` als Vorbedingung in apply, `refused_reason='lockout'`. (iii) ApplyResult-Kontrakt (`ok` + volle `refused_reason`-Taxonomie) wiederherstellen; Version-Reassert auf Apply-Ebene ergänzen. (iv) DoD-Tests (c)/(d)/(e) ergänzen + Apply-Level-Guard-Tests (Befund 7). (v) Spec/Audit-Widerspruch zu `expected` (Befund 5) per Entscheidung auflösen und Guard entsprechend korrigieren oder ehrlich als redundanten Assert dokumentieren.