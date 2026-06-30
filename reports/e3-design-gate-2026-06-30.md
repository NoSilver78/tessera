Now I have my design fully in view. Let me consolidate the gate honestly. The reviewers landed several legitimate breaks — I need to own them.

# E3-Design-Gate

**Gesamt-Verdikt: SOUND-MIT-FIXES** — aber knapp. Das Design ist im Kern (fail-closed-Präzedenz, Rebind→Remove-Reihenfolge, Snapshot-Persistenz) tragfähig, hat aber **zwei CRITICAL-Brüche in der D9-Surface-Detektion**, die der Reviewer empirisch (proof_d9.py) widerlegt hat. Diese Brüche untergraben genau die Invariante, mit der Teil A wirbt („kein ALLOW ohne Runtime-Proof"). Solange A.3 nicht umgebaut ist, ist Teil A **als Spec für Codex nicht freigabereif**. Teil B und C sind sound mit Auflagen.

---

## Bestätigte Schwachstellen nach Severity

### CRITICAL

**1 · Teil A.2/A.3 — Surface-Heuristik kann ein unsicheres ALLOW erzeugen (manifest-deps sind blind)**
Problem: Meine ALLOW-Bedingung stützt sich auf `has_services` (= nur `services.yaml` im Verzeichnis, loader.py:875), `integration_type` (frei wählbares Manifest-Feld, Default `hub`) und `manifest.dependencies` auf `http`/`websocket_api`. Alle drei sind statisch und forgeable/blind: Eine Komponente kann via `hass.services.async_register()` ohne `services.yaml`, via `register_view`/`HomeAssistantView` ohne `http`-Dependency oder via `async_register_command` ohne `websocket_api`-Dependency eine voll callbare Bypass-Oberfläche besitzen — und der Heuristik trotzdem als „sauber" erscheinen. Der Reviewer hat das mit `proof_d9.py` real bewiesen: ein `sneaky_http` (integration_type=sensor, kein http-dep, registriert faktisch eine View) wurde zu **ALLOW befördert**. Das verletzt meine eigene A.3-Invariante.
Doc-Korrektur: A.3 Regel 3 ersetzen. Surface-Detektion **nicht** auf manifest-deps stützen. Pflicht statt optional: (a) statischer Quellcode-Marker-Scan via `async_add_executor_job` auf `HomeAssistantView`/`register_view`/`panel`/`websocket_command`/`async_register_command`/`async_register`+`services` (= Spike `_static_surface_markers`), plus (b) Runtime-Service-Probe `hass.services.async_services().get(domain)`. Jedes positive Surface-Signal ⇒ **hartes Veto = Zwangs-UNKNOWN VOR Tabelle/Ack**, egal was Tabelle/Ack sagen. A.2 dahingehend ändern, dass `async_get_custom_components` nur Enumeration + `has_services`/`integration_type`/`version` liefert; Klassifikation **zwingend** Marker-Scan + Runtime-Probe.

**2 · Teil A.3 — Tabelle/Ack vertrauen `domain+version` ohne Integritätsbindung (Ack-Forge + Domain-Squat)**
Problem: Tabelle und Ack verankern Vertrauen an `domain`+`version` — beide selbst-deklarierte, vom Komponenten-Autor frei setzbare Strings, kein Content-Hash. Angriff 1: Admin ackt `foo@1.0.0`; Angreifer liefert bösartiges Update, behält `version:1.0.0` → Ack bleibt gültig → ALLOW. Meine „Ack erlischt bei Versionswechsel"-Garantie greift nur, wenn der Angreifer die Version brav erhöht. Angriff 2: Tabelle führt `foo@1.x` als ALLOW; Nutzer ersetzt das echte `foo` durch ein bösartiges mit gleichem domain+version → erbt das Tabellen-ALLOW.
Doc-Korrektur: A.3 + A.4 — Trust-Anchor um einen Integritäts-Hash ergänzen. Beim Ack und Tabellen-Match einen Content-Hash (sha256 über sortierte `*.py`/`*.yaml`/`manifest`, off-loop via Executor) bilden und speichern; ALLOW nur bei exaktem `(domain, version, content_hash)`-Match. Hash-Drift bei gleicher Version ⇒ Ack/Tabelle erlischt ⇒ UNKNOWN. Schema `config.d9_acks` um `content_hash` erweitern.

### HIGH

**3 · Teil A.4 — Gate ist point-in-time, post-enforce installierte Komponenten sind unsichtbar**
Problem: Der Gate läuft nur bei `async_setup_entry`/recompile. `async_get_custom_components` cached das Installed-Dict prozesslebenslang (`hass.data[DATA_CUSTOM_COMPONENTS]`) und invalidiert nie bei neuen Installs. Eine post-enforce per HACS gedropte Komponente ist für die Enumeration unsichtbar bis HA-Neustart — selbst ein expliziter recompile liest nur den veralteten Cache. Zusätzlich ist mein A.4-Wortlaut „Listener auf `hass.config.components`" wörtlich unmöglich (ein plain set hat kein Event).
Doc-Korrektur: A.4 — (1) Vor jedem Enforce-Apply/recompile den custom_components-Bestand **frisch von Platte** lesen (eigener Executor-Scan, wie Spike `_custom_component_static_inventory`), nicht auf das gecachte Dict allein verlassen. (2) „Listener auf `hass.config.components`" ersetzen durch `EVENT_COMPONENT_LOADED` (setup.py:488) — mit der ehrlichen Caveat, dass dieses Event nur beim Laden, nicht beim Installieren feuert. (3) Dokumentieren: post-apply-Install ohne Reload wird erst beim nächsten Restart re-gated; bei Erkennung neuer/ungeklärter Komponenten **fail-safe-to-monitor + Repairs-Issue**, nicht stillschweigend in Enforce bleiben.

**4 · Teil B.3 — Nicht-Admin verliert letzte Rolle → leere Union → IncompleteSuperset-Crash → Store↔nativ-Drift**
Problem (der gravierendste Lifecycle-Bruch): Für einen Nicht-Admin, dessen einzige Rolle gelöscht wird, ist die in B.3-Schritt 2 berechnete `expected` **leer** (keine Rest-Rolle, kein zu erhaltendes system-admin). `async_bind_full_superset(user, [], [])` wirft doppelt `IncompleteSuperset` (auth_adapter.py:359/364, festgenagelt durch test_auth_adapter.py:280-285). Der Delete bricht in Schritt 2 ab — **aber** `config_flow.remove_role` (config_flow.py:107-118) hat die Rolle bereits aus dem Store gepoppt. Ergebnis: Store sagt „keine Rolle mehr", nativer Rebind lief nie → Orphan/Inkonsistenz. Weder B.3 noch concept §6.6 definieren einen End-Zustand für „Nicht-Admin verliert letzte Rolle".
Doc-Korrektur: B.3 um den Empty-Union-Fall ergänzen — entweder (a) Rebind auf die kompilierte `default_role`-Gruppe (die dann **immer** nicht-leer existieren muss, vor jedem Enforce), oder (b) ein dedizierter `async_unmanage_user`-Pfad, der den User kontrolliert aus allen `tessera:`-Gruppen in einen definierten Nicht-Allow-Zustand (**nicht** system-users — §6.3-Invariante!) führt. Zusätzlich: `remove_role` darf den Store-Pop erst **nach** erfolgreichem Rebind aller betroffenen User committen (two-phase-journaled, Journal-Marker VOR dem Store-Pop). Test ergänzen.

**5 · Teil A.1 — „System-Kontext" überzeichnet, was der Gate leisten kann**
Problem: A.1 listet „System-Kontext" als eine der Bypass-Oberflächen, die der Gate fail-closed blockt. Das kann er strukturell nicht: `Context(user_id=None)` ist laut C1 selbst der akzeptierte, nicht-schließbare v1-Bypass. Eine geladene böse Integration richtet Schaden im Systemkontext an — völlig unabhängig vom D9-Verdikt. Das ist kein Code-Bruch, aber ein Ehrlichkeits-Gap, der die fail-closed-Erzählung schwächt.
Doc-Korrektur: A.1 — „System-Kontext" aus der Liste dessen streichen, was der Gate verhindert. Klarstellen: D9 schützt **nur** gegen user-erreichbare Bypass-Oberflächen; Systemkontext bleibt der von C1 dokumentierte Rest-Bypass. Mit dem concept-§11-Threat-Actor „böse Custom-Integration" verlinken.

**6 · Teil C1 — Assist pauschal als „totaler Bypass" widerspricht dem eigenen concept §11**
Problem: C1 wirft Assist pauschal in den System-Kontext-Topf, obwohl mein eigenes concept.md:577/§11 bereits differenziert: user-initiierter Assist-Entry trägt User-Kontext (conversation/http.py:60-65) — nur Agent-Tool/non-entity-Calls sind echter Systemkontext. Zusätzlich nenne ich `exposed_entities` als „einzige patchfreie Scoping-Option", operationalisiere sie aber nicht — ich verschweige eine real existierende patchfreie Teil-Maßnahme. Damit fällt C1 hinter den bereits erarbeiteten Wissensstand zurück.
Doc-Korrektur: C1 differenzieren statt pauschalisieren. (a) Bewiesener Kern (echter `user_id=None`: Automationen/Skripte/Agent-Tool) bleibt dokumentierter Ausschluss. (b) Assist entlang concept:577 trennen (User-Kontext teils durchsetzbar). (c) `exposed_entities`/`async_should_expose` explizit als v1-Maßnahme aufnehmen — **mit** ehrlicher Caveat „global, nicht rollenscharf". (d) D9-Gate nutzen, um systemkontext-fähige Komponenten konkret im Threat-Model zu enumerieren.

**7 · Teil C2 — „Repairs blockt" ist irreführend; Ack ist schwächer als der eigene §11-Breakglass-Standard**
Problem: C2 formuliert, ein Repairs-Issue „blockt" Enforce. Falsch — ein Repairs-Issue ist advisory; die Blockade kommt ausschließlich aus Tessera-Code (spec-e3-enforce.md:15, Schritt 4). Schwerwiegender: concept.md:590 spezifiziert bereits einen **strengeren** Standard — „SoD-Konflikte blocken Apply; Force-Ack nur Breakglass (Ablauf + Entity-Liste + Audit)". Mein simpler Repairs-Confirm-Button ist schwächer: kein Ablauf, keine Audit-Spur was geackt wurde, keine Bindung an die konkrete Konfliktmenge → ein Stale-Ack reitet auf späteren, neu eingeführten Konflikten mit.
Doc-Korrektur: C2 an den eigenen §11-Standard angleichen. (a) „Tessera-Apply-Sequenz blockt (Schritt 4); Repairs ist nur Surface". (b) Ack als auditierten, ablaufenden Breakglass modellieren, gebunden an einen **Fingerprint der konkreten Konfliktmenge** (exposing/restricting Rollen + Entities) mit `accepted_by`/`accepted_at`/`expiry` — exakt das D9-Ack-Muster. (c) Re-Evaluation: jede Policy-/Rollen-Änderung, die die Konfliktmenge verändert, lässt den Ack erlöschen. (d) Config-Flow-Schritt **nicht** vorschnell verwerfen — er ist der natürliche Ort, den Ack-Datensatz zu persistieren.

### MEDIUM

**8 · Teil C3 — Snapshot-Persistenz korrekt, aber Restore-Pfad ist eine Tamper-Oberfläche (welle-b A3)**
Problem: C3 (persistent in `tessera.state` + Two-Phase-Journal) **hält** — die in-memory-Alternative ist widerlegt. Aber C3 verschweigt: der Boot-Rescue-Restore-Pfad (`__init__.py:~241`) schreibt `group_ids` **ohne** `tessera:`-Namespace-Guard. Ein persistierter Snapshot wird damit zur Tamper-/Korruptions-Oberfläche — ein manipuliertes `tessera.state` mit `system-users` würde beim Restore roh zurückgeschrieben = allow-all-Eskalation.
Doc-Korrektur: C3 annehmen, aber welle-b-A3-Auflagen mitführen: (1) Restore-/Boot-Rescue-Pfad durch `_validate_managed_group_id` (tessera:-only-Guard) führen. (2) `tessera.state` beim Laden integritätsprüfen (Schema + ggf. Hash) → korrupter Snapshot geht fail-safe-to-off statt allow-all. (3) `pre_install_snapshot` strikt write-once/immutable durchsetzen.

**9 · Teil B.1 — `tessera:`-Prefix-Guard ist im Indikativ behauptet, existiert aber nicht im Code**
Problem: B.1 formuliert „`role_id` wird im Schema gegen `:` und `tessera` validiert" im Indikativ — der Guard existiert in schema.py **nicht** (nur `_require_non_empty_string`). Folge solange ungebaut: `role_id="tessera:foo"` oder `"a:b"` ist store-gültig und führt im Apply zu `tessera:tessera:foo` / `tessera:a:b`. Der Adapter-Guard `_assert_tessera_group_id` prüft nur den Präfix, nicht eingebettetes `:`. (Klarstellung: der gedachte Guard bricht **keine** legitimen role_ids wie `eg_viewer`.)
Doc-Korrektur: B.1 vom Indikativ auf „zu ergänzen" korrigieren. Guard real in `validate_config_data` implementieren (role_id verbietet `:` und führendes `tessera` case-insensitiv), **symmetrisch** in Membership-Validierung (by_user/by_group) + `_validate_grant_matrix`. `_assert_tessera_group_id` härten: nach `tessera:` kein weiteres `:`.

**10 · Teil B.3 — fehlender Promotion-Guard: Union-Neuberechnung kann Nicht-Admin still zum Admin eskalieren**
Problem: Nur die Demotion ist geguardet (LockoutRisk wenn system-admin fehlt). Die Gegenrichtung — ein Nicht-Admin, dessen `full_group_ids` fälschlich `system-admin` enthält — ist nicht geprüft; `_assert_allowed_binding_group_id` erlaubt system-admin explizit im Binding-Set. In B.3-Schritt 2 ist die Union-Neuberechnung („zu erhaltende System-Gruppen") genau die Injektionsstelle. Da `change=is_admin` total ist (concept §2.3), wäre das eine stille Voll-Rechte-Eskalation.
Doc-Korrektur: Promotion-Guard in `_validate_full_group_superset` ergänzen (system-admin im neuen Set nur zulässig, wenn User bereits Admin war oder eine is_admin-Rolle trägt; sonst EscalationRisk). In B.3-Schritt-2-Union als Pflicht-Assertion mitführen. (Bereits als §8-SHOULD #3 anerkannt — hier zur Pflicht hochziehen.)

**11 · Teil A.2 — Spike ist keine tragfähige Evidenz für das A.2-Produkt-Design (API-Divergenz)**
Problem: A.2 weist die Loader-API als „verifiziert / wie Spike" aus. Der reale Spike `_classify_custom_components` (Z.1913) ruft `async_get_custom_components` **gar nicht** auf — er nutzt eine hartkodierte 8-Domain-Liste + eigenen FS-Scan. Die Loader-API-Quirks (Cache-Staleness, `integration_type`-Default `hub`, `has_services`=nur-services.yaml), die die kritischen Findings tragen, sind im Spike nie geübt. Zusätzliche Namens-Falle: der Spike-Schlüssel `d9_gate_pass_fail_closed` (Z.2054) ist eine Test-Assertion, **nicht** das Produktions-`enforce_blocked`-Signal.
Doc-Korrektur: A.2/A.3 — klar trennen: „API-Form verifiziert gegen loader.py" (stimmt) von „Klassifikations-Logik wie Spike" (stimmt nur, wenn Marker-Scan + Runtime-Probe übernommen werden). E2.5-Task `d9_gate.py` **frisch** gegen die echte Loader-API bauen, nicht vom Spike ableiten. Produktions-Block-Schlüssel klar von der Test-Assertion trennen (`enforce_blocked` vs. `gate_failed_closed_in_test`). Adversarial-Tests (A.6) um die Loader-Quirks erweitern.

**12 · Teil A.3 — Versionsvergleich: `version` ist AwesomeVersion, nicht str**
Problem: `Integration.version` liefert ein `AwesomeVersion`-Objekt (loader.py:950), kein str. Ein roher `str==str`-Ack-Check kann ein gültiges Ack bei kosmetischem Drift (`1.2.3` vs `1.2.3.0`) fälschlich erlöschen lassen — oder bei Tabellen-Range-Checks die AwesomeVersion-Semantik verfehlen. A.3/A.4 legen nicht fest, ob normalisiert verglichen wird.
Doc-Korrektur: A.3 festschreiben: Ack/Tabellen-Version **immer** über `AwesomeVersion` vergleichen (`AwesomeVersion(ack_ver) == integration.version`), nie roh-str. `version=None` explizit ⇒ UNKNOWN_BLOCK_ENFORCE. DoD-Test auf AwesomeVersion-Äquivalenz (1.2.3 vs 1.2.3.0) ausrichten.

### LOW / NIT

**13 · Teil B.2 — Rename-„No-Op" überzogen (nativer name-Write möglich)**
Problem: Der Compiler emittiert keinen Namen, aber der (noch ungebaute) Apply-Layer ruft `async_set_group_policy(group_id, name, policy)`. Nimmt der Caller den natürlichen Wert `role['name']`, führt ein Rename zu `group.name = name` + Persist (auth_adapter.py:173/175) — also sehr wohl ein nativer 1-Feld-Write. „Keine native Gruppe ändert sich" ist falsch, sobald der name vom Anzeigenamen abgeleitet wird. Folgen harmlos.
Doc-Korrektur: B.2 entweder präzisieren („Bindungen + Policy sind No-Op; der native name kann sich ändern — harmloser idempotenter 1-Feld-Write") oder festlegen, dass der native name konstant aus `tessera:<role_id>` abgeleitet wird (dann echter Voll-No-Op). Im Apply-Layer-Spec festschreiben.

**14 · Teil A.2 — `hass.config.components` ist `_ComponentSet`, nicht plain `set[str]`**
Problem: In HA 2026.6 ist `config.components` ein `_ComponentSet(set[str])` (core_config.py:484/577), enthält auch Plattform-Einträge (`mjpeg.camera`) und verbietet `discard`/Teil-`remove`. Für reinen Membership-Check egal.
Doc-Korrektur: A.2 präzisieren: `_ComponentSet(set[str])`, für Read/Membership wie set nutzbar, nie mutieren, für reine Top-Level-Domains `hass.config.top_level_components` verwenden.

**15 · Teil A.2 — recovery/safe_mode liefert leeres Dict (fail-OPEN-artig)**
Problem: Im recovery/safe_mode gibt `async_get_custom_components` ein leeres Dict (loader.py:298) — der Gate sieht 0 Komponenten, blockiert nichts, während der Host abgesichert hochfährt.
Doc-Korrektur: A.2 — recovery/safe_mode als Sonderfall behandeln (Enforce ist dort ohnehin nicht aktiv) und explizit notieren.

**16 · Teil A.3 — Default `integration_type` ist `hub`, nicht `entity`**
Problem: Der Default ist `hub` (loader.py:854-860), nicht im entity-zentrierten Set. Die Heuristik muss eine Komponente, die `integration_type` weglässt, korrekt als nicht-entity-zentriert/UNKNOWN werten, nicht versehentlich als ALLOW-fähig durchwinken.
Doc-Korrektur: A.3 explizit notieren: fehlendes `integration_type` ⇒ Default `hub` ⇒ nicht ALLOW-fähig.

**17 · Teil B.3 — Two-Phase-Journal-Grenze + enforce-§2-Snapshot-Timing**
Problem: Die „nur mitgliedslose Hülle / kann nicht sperren"-Aussage hält für 2↔3, gilt aber nicht pauschal. (1) Crash zwischen Store-Pop und Rebind = die gefährliche Drift (Finding 4). (2) In enforce §2 steht SNAPSHOT auf Schritt 7, **nach** dem NATIVE WRITE (Schritt 5) — ein Crash zwischen 5 und 7 hinterlässt einen nativ veränderten Zustand ohne frischen Recovery-Snapshot dieses Applys.
Doc-Korrektur: Journal-Marker VOR den Store-Pop ziehen (Store-Mutation + nativer Rebind als eine journaled Unit). In enforce §2 den Vor-Zustand-Snapshot VOR Schritt 5 ziehen (oder in dieselbe two-phase-Unit nehmen), damit jeder native Write einen korrespondierenden Recovery-Punkt hat.

**18 · Teil B.4 — Orphan-Cleanup-Atomarität (nit)**
Problem: Die Verifikation „kein User referenziert sie" ist nicht an eine race-freie Prüfung gebunden; zwischen Verifikation und Remove könnte theoretisch eine Bindung entstehen. Bei serialisiertem Apply praktisch ausgeschlossen.
Doc-Korrektur: B.4 — klarstellen, dass Orphan-Verifikation + Remove in derselben serialisierten Apply-Transaktion laufen. Kein Code-Change.

---

## Was am Design zu ändern ist

1. **A.3 Surface-Detektion neu bauen (CRITICAL #1):** manifest-deps/`has_services`/`integration_type` als ALLOW-Basis raus; Pflicht-Marker-Scan (Executor) + Runtime-Service-Probe als **hartes Veto vor Tabelle/Ack**.
2. **A.3/A.4 Integritäts-Hash (CRITICAL #2):** Tabelle/Ack an `(domain, version, content_hash)` binden; Hash-Drift ⇒ UNKNOWN. Schema `d9_acks.content_hash`.
3. **A.4 Cache-Realität (HIGH #3):** vor jedem Apply frischer FS-Scan statt gecachtem Dict; `EVENT_COMPONENT_LOADED` statt „Listener auf set"; post-apply-Install ehrlich dokumentieren + fail-safe-to-monitor.
4. **B.3 Empty-Union-Pfad (HIGH #4):** definierter End-Zustand für „Nicht-Admin verliert letzte Rolle" (default_role-Rebind ODER `async_unmanage_user`); Store-Pop erst nach erfolgreichem Rebind (journaled, Marker vor Pop).
5. **A.1 Ehrlichkeit (HIGH #5):** „System-Kontext" aus der Liste der vom Gate verhinderten Bypässe streichen.
6. **C1 an concept §11 angleichen (HIGH #6):** Assist differenzieren; `exposed_entities` als v1-Maßnahme mit „global, nicht rollenscharf"-Caveat aufnehmen.
7. **C2 an concept §11 angleichen (HIGH #7):** „Tessera blockt, Repairs ist nur Surface"; Ack = auditierter, ablaufender Breakglass mit Konflikt-Fingerprint; Config-Flow als Ack-Persistenzort nicht verwerfen.
8. **C3 + welle-b-A3 (MEDIUM #8):** persistent annehmen, aber Restore-Pfad durch Namespace-Guard, `tessera.state`-Integritätscheck, write-once `pre_install_snapshot`.
9. **B.1 Guard wirklich bauen (MEDIUM #9):** Indikativ → „zu ergänzen"; role_id-Guard gegen `:`/`tessera` in schema + Membership + grant_matrix; `_assert_tessera_group_id` härten.
10. **B.3 Promotion-Guard (MEDIUM #10):** EscalationRisk gegen ungewollte system-admin-Injektion in der Union-Neuberechnung.
11. **A.2 Spike entkoppeln (MEDIUM #11):** „API verifiziert" ≠ „Logik wie Spike"; d9_gate.py frisch bauen; Prod-Signal `enforce_blocked` vom Test-Schlüssel trennen; Adversarial-Tests um Loader-Quirks erweitern.
12. **A.3 AwesomeVersion (MEDIUM #12):** Versionsvergleich immer über AwesomeVersion; `version=None` ⇒ UNKNOWN.
13. **Kleinkram (LOW/NIT #13–18):** B.2 Rename-No-Op präzisieren/name konstant; A.2 `_ComponentSet` + recovery/safe_mode + `hub`-Default notieren; Journal-Marker/Snapshot-Timing; B.4 Atomaritäts-Notiz.

**Ehrliche Bilanz:** Die Präzedenz-Logik und die fail-closed-Architektur stehen — aber die beiden CRITICAL-Findings brechen meine zentrale Werbung („kein ALLOW ohne Runtime-Proof") empirisch. Teil A geht **nicht** so an Codex, wie es dasteht: A.3 muss auf Marker-Scan + Runtime-Probe + Content-Hash umgebaut werden, sonst baut Codex einen Gate mit einem dokumentierten ALLOW-Bypass. Teil B/C sind mit den Auflagen freigabereif; B.3-Empty-Union (#4) ist die schärfste Lifecycle-Lücke und gehört vor dem E3-Apply geschlossen.