# TESSERA — E3-Design-Paket (Vor-Scharf-Architektur)

Stand 2026-06-30 (Architekt: Claude) · **Löst `spec-e3-enforce.md` §6 (Design-Fragen) + §7 (Plan-Lücken)** auf, damit E3 umsetzungsreif ist. **Non-scharf:** spezifiziert E2.5 (baubar JETZT) + legt die §6-Empfehlungen zur Freigabe vor.

> **Adversarial-gegated** (Gate `wb77hllxb`, 4 Reviewer): Verdikt **SOUND-MIT-FIXES** — Skelett trägt, aber der D9-Gate hatte echte Löcher (fälschbare Surface-Heuristik, fehlende Integritätsbindung, Cache/Re-Eval-Lücke, A.1/C1/C2-Overclaims). **Diese Fassung arbeitet alle 16 Befunde ein.**

> **Status:** Teil A (E2.5) = Codex-baubar (read-only). Teil B = Apply-Konzept. **Teil C = ENTSCHIEDEN** (Sign-off Michael 2026-06-30 — C1/C2/C3 alle „so festschreiben").

---

## Teil A — E2.5: D9-Produkt-Gate (baubar jetzt, non-scharf)

### A.1 Problem & Scope-Grenze (ehrlich)
`spec-e3-enforce.md` §2 Schritt 3 verlangt vor jedem Enforce-Write ein **D9-Gate**: existieren installierte Komponenten mit **user-token-erreichbarer** Bypass-Oberfläche (nicht-entity-geprüfte Services, HTTP-Views, WS-Commands, die ein *confined User* aufruft), muss Enforce **fail-closed blockiert** werden.

> **Scope-Grenze:** Der Gate reduziert die **user-erreichbare** Angriffsfläche. Den **System-Kontext** (`Context(user_id=None)`: Automationen/Skripte/Agent-Tool-Calls) deckt er **strukturell NICHT** ab — eine bösartige *geladene* Integration agiert dort unabhängig vom D9-Verdikt. Das bleibt der von **C1** akzeptierte, patchfrei-unschließbare Rest-Bypass und gehört **nicht** in die Liste dessen, was der Gate „verhindert".

### A.2 Echte HA-API (verifiziert gegen `homeassistant/loader.py`, 2026.6.x) — inkl. der Fallen
- `loader.async_get_custom_components(hass) -> dict[str, Integration]` — **installierte** Custom-Integrationen. **⚠️ prozesslebenslang gecacht** in `hass.data[DATA_CUSTOM_COMPONENTS]`, **nicht** bei neuen Installs invalidiert → für den Gate **nicht allein** verlassen (s. A.4).
- **Untaugliche Trust-/Surface-Signale** (Gate-Befund, NICHT für ALLOW nutzen):
  - `Integration.has_services` = **nur** `services.yaml`-Präsenz. Eine Komponente, die Services via `hass.services.async_register()` in `async_setup()` registriert (ohne `services.yaml`), hat `has_services==False` bei voller Service-Oberfläche.
  - `Integration.integration_type` = `manifest.get("integration_type")` = **autor-kontrolliert** (kein Trust-Signal).
  - `manifest`-Dependencies `http`/`websocket_api` = **kein** verlässliches Surface-Signal: `hass.http.register_view`/`websocket_api.async_register_command` verlangen **keine** deklarierte Dependency.
- **Brauchbar:** `Integration.version: AwesomeVersion | None` (Trust-Anchor-Teil), `hass.config.components` (`_ComponentSet(set[str])`, geladene Domains — **read-only**, nie mutieren).

### A.3 Klassifikation (fail-closed, gehärtet)
Verdikt je installierte Custom-Komponente ∈ `{ALLOW, DENY, TIER-2, UNKNOWN_BLOCK_ENFORCE}`, **Default `UNKNOWN_BLOCK_ENFORCE`**.

**(1) Surface-Erkennung = PFLICHT-Hard-Veto (vor Tabelle/Ack):**
- **Statischer Marker-Scan** des `custom_components/<domain>/`-Quellcodes via `async_add_executor_job` (off-loop) auf: `async_register`(+`services`), `HomeAssistantView`/`register_view`/`panel`, `websocket_command`/`async_register_command`.
- **Plus Runtime:** `hass.services.async_services().get(domain)` (tatsächlich registrierte Dienste).
- **Regel:** **jedes** positive Surface-Signal ⇒ **Zwangs-`UNKNOWN_BLOCK_ENFORCE`**, egal was Tabelle/Ack sagen. Die Heuristik ist ein **hartes Veto**, keine nachgeschaltete Bestätigung. `has_services`/`integration_type`/manifest-deps werden **nie** für ALLOW herangezogen.

**(2) Trust-Anchor = `(domain, version, content_hash)`:**
- `content_hash` = sha256 über die sortierten `*.py`/`*.yaml`/`manifest.json` der Komponente (off-loop, Executor).
- **ALLOW** (via gebündelter Tabelle ODER User-Ack) **nur**, wenn alle drei exakt matchen **und** Surface-Veto nicht griff. Gleiche `version` + geänderter Code ⇒ Hash kippt ⇒ Ack/Tabelle erlischt ⇒ UNKNOWN. Schließt „gleiche Version, neuer Code" **und** Domain-Squat (identität via name+version ohne Integritätsbindung war die Wurzel).
- **Versions-Vergleich** immer via `AwesomeVersion(...)`, nie roh-`str`; `version` ist `None`-fähig.

**(3) Quellen** (Präzedenz, alle fail-closed — Codex-Review 2026-06-30 eingearbeitet):
- **Klassifikations-Tabelle** (`d9_classification.py`): jeder ALLOW-Eintrag trägt einen **expliziten Belegtyp** (`runtime_verified_allow` / `no_surface_verified` / `tier2_accepted`) + `version` + `content_hash` + Grund. **Ohne Belegtyp ⇒ fail-closed** (wie UNKNOWN). Zeigt die Komponente eine im Eintrag **nicht erwartete Oberfläche** ⇒ fail-closed, auch bei Hash-Match.
- **User-Ack** (`config.d9_acks`, auditiert + ablaufend, C2-Stil) — gilt **NUR für `UNKNOWN_BLOCK_ENFORCE`**, versions+hash-gebunden. **`DENY` ist NICHT per Admin-Ack freischaltbar** (sonst = UNKNOWN unter anderem Namen) → DENY bleibt blockierend bzw. braucht einen separaten, höherwertigen Sign-off (Tier-2/Out-of-scope, dokumentiert).
- sonst **UNKNOWN**.

### A.4 Re-Evaluation & ehrliche Grenze (Gate-Befund)
- **Frischer Bestand pro Apply:** vor jedem Enforce-Apply/`recompile` den `custom_components/`-Bestand **frisch von Platte** scannen (Executor) — **nicht** allein das gecachte `async_get_custom_components`-Dict.
- **Listener korrekt:** auf **`EVENT_COMPONENT_LOADED`** hören (feuert beim **Laden**, nicht Installieren). Die frühere Formulierung „Listener auf `hass.config.components`" ist gestrichen (ein `set` hat kein Event).
- **Ehrliche Grenze:** eine **post-apply** via HACS installierte Komponente ohne Reload/Restart wird erst beim nächsten Restart re-gated. → Bei Erkennung neuer/ungeklärter Komponenten **fail-safe-to-monitor + Repairs-Issue**, nie still in Enforce bleiben.

### A.5 Baubar JETZT (non-scharf) — frisch, nicht vom Spike
`d9_gate.py` ist **read-only** (enumeriert + scannt + klassifiziert; schreibt nichts nativ) → vor E3 baubar, liefert schon im Monitor den „Was würde Enforce blockieren?"-Report. **Nicht** vom Spike-`_classify_custom_components` ableiten (Dev-Harness, kein produktions-fail-closed-Mechanismus) → **frisch** gegen die echte Loader-API + Executor-Scan bauen.

### A.6 DoD (Codex-Task E2.5) — mit den Loader-Quirks als Adversarial-Tests
- `d9_gate.py` + `d9_classification.py` (Tabelle) + Schema `config.d9_acks`.
- **Adversarial-Tests (Pflicht):** (a) Komponente mit runtime-registrierten Services **ohne** `services.yaml` ⇒ UNKNOWN; (b) `integration_type="entity"` aber mit View/WS-Marker ⇒ UNKNOWN; (c) gleiche `version`, geänderter `content_hash` ⇒ Ack erlischt ⇒ UNKNOWN; (d) post-apply-Install ⇒ fail-safe-to-monitor; (e) Tabellen-ALLOW + neu erkannte/nicht-deklarierte Oberfläche ⇒ UNKNOWN; (f) Ack überschreibt `DENY` **nicht**; (g) Tabellen-Eintrag ohne Belegtyp ⇒ fail-closed. Plus: `async_get_custom_components` + Scan gemockt (HA-frei). · **Adversarial-Panel** vor Merge.

---

## Teil B — Gruppen-Lifecycle (Konzept für E3-Apply)

Schließt `spec-e3-enforce.md` §7 Lücke 2. Baut auf den **E1-Adaptern** (`AuthPolicyStoreAdapter.async_set_group_policy`/`async_remove_group`, `UserBindingAdapter.async_bind_full_superset`).

### B.1 Identität & Naming-Guard (konkret implementieren)
- **Rolle = immutable `role_id`**; native Gruppe = **`tessera:<role_id>`**.
- **Schema-Guard in `validate_config_data` (real ergänzen, §8.4-Auflage):** `role_id` wird **abgewiesen** gegen `:` (Gruppen-ID-Separator) **und** gegen den reservierten Präfix `tessera` (case-insensitiv, am Anfang) — **symmetrisch** in der Membership-Validierung. (Heute existiert der Guard nur als Auflage, nicht im Code.)

### B.2 Rename (Name-Änderung) — nativer No-Op, festgelegt
Bindungen + Policy = No-Op (Gruppe hängt an `role_id`, nur `name` ändert sich). **Festlegung:** der **native Gruppen-Name wird NICHT vom Rollen-Anzeigenamen abgeleitet** (stabil = `tessera:<role_id>`) → Umbenennen ist garantiert nativ-folgenlos (kein 1-Feld-Drift-Write).

### B.3 Delete (Rolle entfernt) — Rebind→Remove + Empty-Union-Fall
1. Betroffene User bestimmen (`<role_id>` in `by_user`; `by_group` v1-inert).
2. **Pro User volle Gruppen-Union NEU berechnen, OHNE die gelöschte Rolle** (= No-Drop-Caller-Vertrag §8.2: `expected` = *alle verbleibenden* `tessera:*`-Gruppen + System-Gruppen). Rebind via `async_bind_full_superset` (REPLACE, Lockout-Guard).
3. **Erst danach** die referenz-freie `tessera:<role_id>` via `async_remove_group` entfernen.
> **Reihenfolge `Rebind → Remove`**: nie referenziert ein User mid-operation eine fehlende Gruppe; Crash zwischen 2/3 → nur mitgliedslose Hülle (idempotent beim nächsten Apply entfernt). Two-Phase-Journal (`tessera.state`, §8.8).

> **⚠️ Empty-Union-Sonderfall (Gate-Befund HIGH):** wird die **letzte** Rolle eines Users gelöscht, ist die Union leer → `async_bind_full_superset` würfe `IncompleteSuperset`. **Rückbinden auf `system-users` ist VERBOTEN** (allow-all = Privileg-**Eskalation**, §6.3-CRITICAL). **Resolution:** jeder gemanagte User mappt auf **≥1** Gruppe — fehlt jede explizite Rolle, ist das die kompilierte **`default_role`-Gruppe** (Tessera-Baseline, **deny-by-omission**, leere Grants). Damit ist die Union nie leer **und** der „kein Rolle"-Zustand ist *minimal*, nicht *allow-all*. (Erfordert `default_role` im Modell — kleine `concept.md`-Ergänzung; alternativ: Löschen der letzten Rolle eines Users erzwingt Admin-Bestätigung.)

### B.4 Promotion-Guard (Gate-Befund — heute nur Demotion geguarded)
In `_validate_full_group_superset` ergänzen: **`system-admin` im neuen Set ist nur zulässig**, wenn der User es **bereits hatte** ODER eine `is_admin`-Rolle trägt, deren Projektion `system-admin` explizit vorsieht — sonst `LockoutRisk`/`UnsafeAuthTarget`. (Verhindert, dass ein Non-Admin-Rebind versehentlich `system-admin` ergibt.)

### B.5 Orphan-Gruppen
`tessera:<id>`-Gruppe ohne korrespondierende Rolle (Drift/abgebrochener Delete/Restore) → beim Apply erkannt, nach „kein User referenziert sie" entfernt (Store gewinnt, §8.4). Nie still einen User droppen, um eine Gruppe zu leeren.

---

## Teil C — §6-Design-Entscheidungen — ENTSCHIEDEN (Sign-off 2026-06-30)

### C1 · System-Kontext `Context(user_id=None)` — differenziert (Gate-Befund)
**Empfehlung, zweigeteilt:**
- **(a) Echter System-Kontext** (`user_id=None`: Automationen, Skripte, Agent-Tool-Calls): **dokumentierter Trust-Boundary-Ausschluss** (hält — patchfrei unschließbar, Override = Monkeypatch = verboten). Ehrlich im Threat-Model.
- **(b) Assist NICHT pauschal mithineinwerfen:** Assist hat mit nativem **`exposed_entities`** eine **patchfreie Teil-Scoping-Option** — die für non-admins exponierte Entity-Menge lässt sich eingrenzen. → v1 dokumentiert Assist-Scoping über `exposed_entities` als Option, statt „totaler Bypass, nichts machbar".
**Begründung:** Ehrlichkeit ohne Unter-Verkauf; deckt sich mit concept §6.5/§11.

### C2 · Linter-Ack-UX — entkoppelt + Breakglass (Gate-Befund)
**Empfehlung:**
- **(a) Sprachlich entkoppeln:** die **Tessera-Apply-Sequenz blockt** (Schritt 4, §2) — *das* ist das Gate. Das **Repairs-Issue ist nur Surface/Notification**, nicht das Gate.
- **(b) Ack = auditiertes, ablaufendes Breakglass-Artefakt** mit **Konflikt-Fingerprint** (Entität/exposing/restricting-Rollen), Zeitstempel, Ablauf. Ändert sich der Fingerprint, **erlischt** der Ack → erneuter Block. (Kein dauerhafter Ein-Klick-Freibrief.)
**Begründung:** hebt C2 auf den §11-Standard (kein still-durchrutschender SoD-Footgun).

### C3 · Snapshot-Persistenz — `tessera.state` (hält)
**Empfehlung: persistent in `.storage/tessera.state`** (concept §8.8), `pre_install_snapshot` **IMMUTABLE** (§8.6), Two-Phase-Journal (`apply_in_progress`). In-memory verlöre genau den Recovery-Zustand → Lockout-Risiko. Zusätzlich die **Welle-B-A3-Namespace-Guards** referenzieren. *Kein echtes Gegenargument außer Komplexität (über E1-Snapshot-Typen vorgebaut).*

---

## Was das freischaltet
- **Sofort baubar (non-scharf, Codex):** Teil A → `d9_gate.py` (E2.5), in der **gehärteten** Fassung (Hard-Veto-Scan + content_hash + frischer Bestand). Nach Panel-Gate mergebar.
- **Teil C entschieden** (Sign-off 2026-06-30): in `spec-e3-enforce.md` §6 festgeschrieben; bei E3-Bau in `concept.md` §6.5/§11 + §8 einarbeiten.
- **Bleibt gesperrt:** der E3-Scharf-Schritt — weiterhin **D10 + Human-Go + Soak**.
