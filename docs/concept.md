I have all the grounding I need. I have the full picture: 5 design dimensions (one is a placeholder "test"), 3 adversarial validations with critical findings, the requirements catalog (R1-R10, D1-D11), the charter, and the synthesis. 

The most important verified corrections from validation I must incorporate:
- **CRITICAL**: bare-True short-circuit in `util.compile_policy` → never emit bare True, always dicts
- **CRITICAL**: no public group-CRUD API → write path is the #1 risk, Phase-0 spike
- **CRITICAL**: system-users gets force-injected `USER_POLICY={entities:True}` at load → Dim1 was WRONG; remove-from-system-users is a HARD invariant
- **CRITICAL**: `group_ids` REPLACE semantics → cross-role lockout risk
- render_template/logbook/Assist/MQTT read+act leaks NOT closeable patch-free
- change=is_admin is TOTAL not scoped
- Authentik dimension is unspecified placeholder

Now I'll write the canonical specification.

# TESSERA — Kanonische Spezifikation des Berechtigungssystems

**Standalone HA-RBAC-Integration · v1-Konzept · Stand 2026-06-28 (HA 2026.6.4)**
**Status: G0-Foundation · Diskussionsgrundlage für Codex · Verdikt aller drei Validatoren eingearbeitet (MODIFY/REVISE)**

Dieses Dokument synthetisiert die fünf Design-Dimensionen (Datenmodell/RBAC-Kern · Resolution/Pflege-Ebene · Enforcement/Compiler · Authentik/IdP · Pflege-UX/Lifecycle) zu **einer** widerspruchsfreien Spezifikation. Wo die Dimensionen sich widersprachen, ist der Konflikt unten **explizit aufgelöst** — autoritativ ist immer die gegen den HA-Core-2026.6.4-Quelltext verifizierte Aussage, nicht die Behauptung einer Design-Dimension.

> **Vorab — die vier härtesten Wahrheiten (alle gegen Core-Quelltext verifiziert), die das gesamte Konzept formen:**
> 1. **`system-users` ist NICHT harmlos.** `auth_store.py` injiziert beim Laden zwangsweise `USER_POLICY = {"entities": True}`. Jeder gemanagte Nutzer, der in `system-users` verbleibt, hat **allow-all** — der most-permissive-Merge hebelt jede Tessera-Einschränkung aus. Dim1 behauptete das Gegenteil; **Dim1 ist hier falsch**. → Gemanagte User MÜSSEN aus `system-users` entfernt werden — als harte, beim Start geprüfte Invariante.
> 2. **Es gibt KEINE bare-`True`-Leafs.** `util.compile_policy` short-circuitet beim ersten `bool`-Wert auf `lambda: True` für **alle** Keys+Entities. `entities:true`/`domains:true` = read+control+edit auf **alle** Entities; `domains:{cover:true}` = **alle Keys** (read+control+**edit**) für die cover-Entities (util.py:82-96), nicht „cover-control". → Compiler emittiert **niemals** bare `True` und **nie** `domains:{x:true}` wo view≠change gewollt — nur **schema-aware** Dicts (verboten `entities:true`/`…domains:true`/`…entity_ids.X:true`; erlaubt `…X.read/control:true`).
> 3. **Es gibt KEINE public Gruppen-CRUD-API.** Weder `config/auth/group/*` (existiert nicht) noch `async_create_group/remove_group` (existieren nicht). Der gesamte Schreibpfad ist die größte Unbekannte → **Phase-0-Spike ist harte Vorbedingung**.
> 4. **`view`-Vertraulichkeit ist single-instanz NICHT vollständig durchsetzbar.** `render_template`, `logbook`, allowlisted Events und Assist/Conversation lesen restricted Entities patchfrei vorbei. → `operate`/`control` ist die echte Grenze; `view` ist „get_states/REST/history-Hiding **plus dokumentierte Rest-Leaks**".

---

## 1. Konzeptüberblick + Designprinzipien

### 1.1 Was Tessera ist

Tessera ist eine **eigenständige HACS-Integration** (`custom_components/tessera`, Python 3.13 Backend + optionales Lit/TS-Admin-Panel), die die seit 2020 offene HA-Lücke schließt: HA hat intern read/control/edit-Policies, aber **kein UI, nur 3 fixe Systemgruppen und Owner-Bypass**. Tessera liefert pro **Rolle × Scope × Stufe (view/operate/change)** echte Durchsetzung auf den **nativen HA-`PolicyPermissions`** — **kein Monkeypatch, kein Core-Fork**.

**Zero-Dependency ist Akzeptanzkriterium:** Tessera läuft auf einer Vanilla-HA-Installation ohne Atrium, ohne anderes HACS-Paket, ohne IdP. Authentik ist ein **zuschaltbarer Mitgliedschafts-Provider**, keine Voraussetzung.

### 1.2 Die zentrale Architektur-Metapher: Store ist SoT, native Policy ist generierte Projektion

Exakt wie in der Homelab-Governance „NetBox = Fakten-SoT, `host.yml` = generierte Projektion": Der **Tessera-ACL-Store** ist die einzige von Menschen gepflegte Wahrheit; ein **deterministischer, idempotenter Compiler** projiziert ihn in native HA-Gruppen-Policies. **Niemand editiert die native Policy von Hand** — sie wird beim nächsten Apply überschrieben.

### 1.3 NIST SP 800-162 ABAC-Funktionspunkte (sauber getrennt)

| Funktionspunkt | Realisierung in Tessera |
|---|---|
| **PAP** (Policy Administration Point) | Tessera-ACL-Store + Admin-UI — hier wird modelliert |
| **PIP** (Policy Information Point) | HA-Registries (entity/device/area/floor/label) + Authentik-`groups`-Claim |
| **PDP** (Policy Decision Point) | **Tessera-Compiler** — entscheidet **at compile time**, nicht per-request |
| **PEP** (Policy Enforcement Point) | HA-nativer `PolicyPermissions.check_entity` (read/control) — **unverändert** |
| **Decision-Audit** | Tessera-Audit-Log + Monitor/Dry-Run |

### 1.4 Designprinzipien (best-practice begründet)

1. **NIST RBAC (INCITS 359):** Permissions hängen an **Rollen**, nie direkt an Usern. Core-RBAC (USERS/ROLES/UA/PA), Hierarchical-RBAC (Rollen-Vererbung via Komposition), Constrained-RBAC (Static SoD). DSD (dynamische Rollenaktivierung) ist bewusst v2 — HA hat kein Session-Rollenkonzept.
2. **Least-Privilege:** `operate` impliziert `view`, `view` impliziert **nicht** `operate`, `change` ist abgekoppelt. Neue Entities sind per Default in keiner Rolle → unsichtbar bis zugeordnet.
3. **Deny-by-default:** Was kein Grant matcht, ist verboten. „Verboten" entsteht durch **Abwesenheit** eines Grants, **nie** durch einen Deny-Eintrag (HA hat keine Deny-Semantik).
4. **ABAC/PBAC-Anteile:** Label-/`entity_category`-/floor-Selektoren sind Attribut-Prädikate (Policy-as-Data) — Bulk-Werkzeuge über dem RBAC-Kern.
5. **Policy-as-Data + Compiler:** Store deklarativ/versioniert/diffbar (terraform-plan-artiges Apply-Gate); native Policy = idempotente, rollback-bare Projektion.
6. **Defense-in-depth, ehrlich abgegrenzt:** Backend-Durchsetzung (native `check_entity`) ist **die** Grenze für operate/control; Frontend-Hide (browser_mod/Lovelace) ist reine UX-Konsistenz, nie Sicherheit. Für `view`-Vertraulichkeit gegen untrusted Subjekte → **Tier-2 (2-Instanz-Isolation)**, außerhalb dieses Produkts.
7. **Fail-safe / kein Lockout:** Owner wird strukturell nie angefasst; ≥1 Admin-Bindung ist Compiler-Invariante; bei Tessera-**internem** Fehler → `mode=off` (nativ unverändert), **nicht** alles-deny.
8. **Auditierbarkeit:** Append-only Change- + Decision-Log mit before/after-Hash-Chain (**tamper-evident**; echte Non-Repudiation nur mit externem Export/Signatur — lokale `.storage`-JSONL ist admin/root-editierbar), getrennt vom Policy-Store.

---

## 2. Konzeptuelles Modell

### 2.1 Die Subjekt-Kette (NIST Core RBAC: USERS/ROLES/UA/PA)

```
User (HA-Account: lokal ODER OIDC)
  → gebunden an  → Authentik-Gruppe(n)   [via groups-Claim; lokale User: by_user-Bindung]
     → gemappt auf → ROLLE(n)            [n:m, konfigurierbar, NICHT hartkodiert]
        → Rolle = benanntes Bündel von  → GRANTS
           → Grant = (Selector, Stufe, Effekt=ALLOW)
```

- **UA (User-Assignment):** Authentik pflegt Person→Gruppe; Tessera pflegt Gruppe→Rolle **und** (Baseline) User→Rolle direkt.
- **PA (Permission-Assignment):** Rolle→Grant — der eigentliche RBAC-Kern.
- **Sessions:** v1 = alle zugewiesenen Rollen statisch immer aktiv. DSD = v2.

**Zwei Bindungs-Provider, pluggable (Auflösung des Zero-Dependency-Constraints):**
- **`by_user` (Baseline, funktioniert IMMER, ohne jeden IdP)** — direkte User↔Rolle-Zuweisung im Store. Dies ist der **Default-Pfad**, weil 4 von 7 Usern lokal authentifizieren und der `groups`-Seitenkanal v1 erst gebaut werden muss.
- **`by_group` (additiv, first-class)** — Authentik-`groups`-Claim → Rolle. **Inert**, solange (a) der Seitenkanal nicht steht oder (b) der User nicht via OIDC kommt.

### 2.2 Permission = Grant = (Selector, Stufe, Effekt)

| Element | Bedeutung |
|---|---|
| **Selector** | WORAUF — einer von 8 Scope-Typen (§2.4) |
| **Stufe** | WIE TIEF — `view < operate < change` (totale Ordnung) |
| **Effekt** | **konstant `ALLOW`**. Es gibt **keinen** Deny-Effekt im Datenmodell |

**Begründung Allow-only:** HA-Merge short-circuitet beim ersten `True`; ein Deny-Grant wäre im Compile-Ziel **nicht ausdrückbar** — er wäre eine Lüge im Schema. Restriktion entsteht durch **enge Selektoren + Abwesenheit von Grants**, nicht durch Deny.

> **Konflikt-Auflösung (Dim1/Dim-Pflege vs. Dim2/Dim5):** Dim2 und Dim5 erlauben im Store-Schema lokale `deny`/`except`-Annotationen. Dim1 verbietet jeden Deny. **Auflösung:** Beides ist vereinbar, wenn man scharf trennt: Ein `except`/Carve-out ist eine **Compiler-Direktive zur Differenzmengen-Bildung INNERHALB einer Rolle**, kein Grant-Effekt. Sie verschwindet in der Projektion (→ „nicht-enumeriert"). Ein **rollenübergreifender** Deny ist **verboten und unmöglich** (most-permissive-Merge, §5). Das Store-Schema (§3) führt darum `effect` NICHT als Grant-Feld, sondern Carve-outs als explizites `except:[...]` am Selector.

### 2.3 Die drei Stufen — Mapping auf HA-nativ

| Tessera-Stufe | HA-Key | Bedeutung | Materialisierung im Compile |
|---|---|---|---|
| **view** | `read` | Zustand+Historie lesen | `{read: true}` — **nie** bare True |
| **operate** | `control` | Dienst aufrufen / steuern | `{read: true, control: true}` (view ist enthalten) |
| **change** | `is_admin`-Gate | Registry/Config ändern | **NIE per Grant granular** — nur via Admin-Rolle |

**Stufen-Monotonie (hart erzwungen):** `eff_view = view ∨ operate ∨ change`; `eff_operate = operate ∨ change`. Wer steuern darf, sieht; wer ändern darf, steuert+sieht. Verhindert die unintuitive Falle „darf bedienen, sieht aber nicht".

> **change ist v1 GLOBAL, nicht scoped — und das ist gefährlich (Validierungs-Finding HIGH, eingearbeitet).** `is_admin = is_owner OR Mitglied(GROUP_ID_ADMIN)`. `is_admin` wird **vor** jeder Entity-Filterung geprüft (get_states, REST, history) **und** schaltet `config/*` frei. Eine `change`-Rolle macht ihre Mitglieder zu **Voll-Admins auf alles** und **nullifiziert stillschweigend jede view/operate-Einschränkung derselben Rolle**. → **Re-Label: die Stufe heißt überall „Voll-Admin (global)", nicht „ändern (Area X)".** Eine `change`-Rolle DARF keine narrowing view/operate-Scopes tragen (Validator-Error). Granulares per-Area-change (WS-config-Interception, +5–10 PT, update-fragil) ist **explizites Nicht-Ziel v1**.

### 2.4 Die 8 Scope-Typen + Spezialitäts-Ordnung

Im **Store** gibt es 8 Selector-Typen. Im **Compile-Ziel** existieren nativ nur 4 Subkategorien (`entity_ids > device_ids > area_ids > domains > all`). Tessera überbrückt das mit einem **eigenen Resolver**.

| Store-Selector | Charakter | Compile-Strategie |
|---|---|---|
| `all` | RBAC grob | nur Admin/Owner; sonst verboten |
| `domain:<d>` | RBAC | ohne Ausnahme: `domains:{d:{read,control}}` (Dict!); mit Ausnahme → entity_ids |
| `floor:<f>` | RBAC-Hierarchie | Resolver: Areas mit `floor_id=f` → deren Entities → entity_ids |
| `area:<a>` | RBAC Primärzone | Resolver: `entity.area_id==a` ∪ `device.area_id==a` → entity_ids **oder** device_ids |
| `device:<dev>` | RBAC | native `device_ids` (native Device-Lookup ist korrekt) |
| `entity:<e>` | RBAC Override | `entity_ids:{e:{...}}` — feinste Ebene |
| `label:<ns/lbl>` | ABAC | Resolver: Entities mit Label → entity_ids (Namespace `wd:`/`acl:` PFLICHT) |
| `category:<cfg|diag>` | ABAC | `entity_category==X` → entity_ids |

**Allow-only-Strategie „Spezialisierung statt Deny" (4 Compiler-Regeln):**
- **S1 — Kein breiter Allow, wo Ausnahmen existieren.** Statt „allow domain X" + „deny X.geheim" → Differenzmenge `{X} \ {geheim}` als enumerierte entity_ids.
- **S2 — Stufen-Monotonie + minimaler Key-Satz.** view→`{read}`, operate→`{read,control}`, `edit` nie. Fehlende Keys = implizit verweigert.
- **S3 — Breiter Allow nur für „darf-alles"-Rollen** — und auch dort als **Dict**, nie bare True.
- **S4 — Sensibles ist eigene Spezialisierung, nie Ausnahme von Breitem** und wird **nie vererbt**. Kamera/Schloss/Alarm/Präsenz erhalten Grants nur über dedizierte, eng gescopte Rollen.

---

## 3. Datenmodell (Store-Schema)

Fünf getrennte Stores (HA `Store`-Helper, `version`/`minor_version` + `async_migrate_func`), getrennt nach Änderungsfrequenz/Backup-Bedarf.

> **Konflikt-Auflösung (Dim1 1-Datei vs. Dim5 5-Dateien):** Dim5's 5-Store-Topologie gewinnt — sie trennt sauber das versionierte Herz (`policy`) vom regenerierbaren Cache (`compiled`), Audit (append-only) und Runtime-State (Snapshots). Dim1's Ein-Datei-Schema bleibt als logische Sicht erhalten, ist aber physisch aufgeteilt.

```jsonc
// .storage/tessera.config (v1) — klein, selten
{ "enforcement_mode": "off|monitor|enforce",
  "default_role": "role_guest_min",          // Fail-safe für nicht-gemappte User
  "deny_by_default": true,
  "panic_active": false,
  "fail_safe": { "owner_untouched": true, "require_admin_binding": true },
  "schema": "tessera/v1" }

// .storage/tessera.policy (v1) — das versionierte Herz, YAML-exportierbar
{
  "version": 1, "minor_version": 1,
  "data": {
    "schema": "tessera/v1",
    "meta": { "active_revision": 42, "modified_by": "<user_id|system>" },
    "roles": {
      "role_admin": {
        "name": "Administrator",
        "is_admin": true,                     // => Voll-Admin global (NICHT scoped!)
        "inherits": [],
        "grants": [ { "selector": {"type":"all"}, "level":"operate" } ]
        // is_admin=true ⇒ keine narrowing-Grants erlaubt (Validator-Error)
      },
      "role_eg_viewer": {
        "name": "EG (nur ansehen)", "is_admin": false, "inherits": [],
        "grants": [ { "selector":{"type":"floor","floor_id":"eg"}, "level":"view" } ]
      },
      "role_eg_operator": {
        "name": "EG Bewohner (bedienen)", "is_admin": false,
        "inherits": ["role_eg_viewer"],       // erbt view-Grants
        "grants": [
          { "selector": {"type":"floor","floor_id":"eg",
                         "except":[ {"type":"label","label":"wd:sensibel"} ]},
            "level":"operate" }               // except = Differenzmengen-Direktive
        ]
      },
      "role_kids": {
        "name": "Kinderzimmer", "is_admin": false, "inherits": [],
        "grants": [ { "selector":{"type":"area","area_id":"og_kind1"}, "level":"operate" } ],
        "ssd_conflicts": ["role_admin"]
      },
      "role_energy_readonly": {
        "name": "Energie-Dashboard (extern)", "is_admin": false, "inherits": [],
        "grants": [ { "selector":{"type":"label","label":"wd:energie"}, "level":"view" } ]
      },
      "role_service_mqtt": {
        "name": "MQTT-Service (technisch)", "is_admin": false, "unmanaged_hint": false,
        "grants": [ { "selector":{"type":"domain","domain":"..."}, "level":"operate" } ]
      }
    },
    "bindings": {
      "by_user": {                            // BASELINE — funktioniert immer
        "<uid_michael>": ["role_admin"],
        "<uid_oksana>":  ["role_eg_operator"],
        "<uid_mqtt>":    ["role_service_mqtt"]
      },
      "by_group": {                           // additiv, inert bis Seitenkanal+OIDC
        "ha-eg-bewohner":   ["role_eg_operator"],
        "ha-energie-gaeste":["role_energy_readonly"],
        "authentik Admins": ["role_admin"]
      }
    },
    "managed_users": {                        // wer wird von Tessera verwaltet (vs. unmanaged)
      "<uid_oksana>": { "roles":["role_eg_operator"],
                        "original_groups":["system-users"], "unmanaged": false }
    },
    "constraints": { "ssd": [ {"name":"kein Kind-Admin",
                               "roles":["role_kids","role_admin"], "cardinality":1} ] },
    "selectors_meta": { "precedence":
      ["entity","entity_area","device_area","floor","domain","label","category","global","all"] }
  }
}

// .storage/tessera.compiled (v1) — REGENERIERBAR, nie autoritativ
{ "source_hash":"sha256:…", "groups": { "tessera:role_eg_operator": { /* native policy */ } },
  "user_rebind": { "<uid>": {"add":["tessera:role_eg_operator"], "remove":["system-users"]} } }

// .storage/tessera.audit (v1) — append-only JSONL
// change: {ts,actor,action,target,revision,before_hash,after_hash,diff}
// decision: {ts,user,entity,key,result,deciding_selector,path}

// .storage/tessera.state (v1) — Runtime
{ "inventory_fingerprint": {…}, "last_apply":"…", "apply_in_progress": false,
  "rollback_ring": [ /* letzte 20 Snapshots */ ],
  "pre_install_snapshot": { "native_groups":[…], "memberships":{…} }   // IMMUTABLE
}
```

**Selector-Schema (alle 8 + optional `except`):**
```jsonc
{"type":"all"} | {"type":"domain","domain":"light"} | {"type":"floor","floor_id":"eg"} |
{"type":"area","area_id":"eg_wohnen"} | {"type":"device","device_id":"<uuid>"} |
{"type":"entity","entity_id":"camera.eg_eingang"} |
{"type":"label","label":"wd:sensibel"}      // Namespace PFLICHT
{"type":"category","category":"config|diagnostic"}
// optional an jedem Selector: "except":[<selector>,…]  -> Differenzmengen-Direktive
```

**Versionierung:** `async_migrate_func` ab v1 Pflicht; jede Migration schreibt zuerst `tessera.policy.premigrate.<ts>` (Rollback-Garantie); `schema`-Stempel zusätzlich zur Store-`version` (Fremd-YAML erkennen); jsonschema-Validierung bei jedem Load **und** vor jedem Apply (fail-closed: invalider Store → Monitor-Fallback statt Enforce mit Müll-Policy).

---

## 4. PFLEGE-EBENEN — die zentrale Auftraggeber-Frage

**Leitsatz: Der Admin pflegt die ABSICHT auf der GRÖBSTMÖGLICHEN Ebene; Tessera BERECHNET die feinkörnige native Durchsetzung. Nichts wird doppelt gepflegt.**

### 4.1 Tabelle — welche Eigenschaft wird auf WELCHER Ebene gesetzt vs. ist berechnet

| Ebene | Was wird hier GESETZT | Selektor-Typ | Häufigkeit / Wer fasst es an | GESETZT oder BERECHNET |
|---|---|---|---|---|
| **global-default je Rolle** | Grundhaltung der Rolle (deny-by-default / view-default) | `default` | Einmalig je Rolle | **GESETZT** |
| **floor** (4 Etagen) | Etagen-Rollup als Bulk-Beschleuniger (OG/EG/UG/Außen) | `floor:<f>` | Selten, Bulk-Start | **GESETZT** |
| **AREA × ROLLE** ⭐ | **Die Alltags-Arbeitsfläche** — Stufe je Area×Rolle | `area:<a>` | **~90% der Pflege; Matrix 39 Areas** | **GESETZT** |
| **domain** | Sensible Domains in einem Rutsch (`lock`/`camera`/`alarm_control_panel`) | `domain:<d>` | Themenweit, selten | **GESETZT** |
| **label (`wd:`/`acl:`)** | Querschnitt quer zu Räumen (z.B. `wd:sensibel`, `wd:energie`) | `label:<ns/k>` | Themenweit, selten | **GESETZT** |
| **entity_category** | `config`(374)→Admin-only, `diagnostic`(493)→view-only | `category:<c>` | Einmal-Bulk (erschlägt ~867 area-lose) | **GESETZT** |
| **device** | Alle Entities eines Geräts | `device:<d>` | Punktuell | **GESETZT** |
| **entity-override** | Punktuelle Ausnahme (ALLOW/Carve-out) | `entity:<e>` | **Bewusst selten** (Override-Zähler als Hygiene-Signal) | **GESETZT** |
| — | native Gruppen-Policy `entity_ids{read,control}` | — | NIE | **BERECHNET** |
| — | Area→entity_ids-Expansion (direkt ∪ device) | — | NIE | **BERECHNET** |
| — | Deny-Elimination / breit-vs-explizit-Wahl | — | NIE | **BERECHNET** |
| — | Stufen-Monotonie (change⇒operate⇒view) | — | NIE | **BERECHNET** |
| — | `is_admin`-Projektion für change-Rollen | — | NIE | **BERECHNET** |
| — | Cross-Rollen-OR-Merge | — | NIE | **BERECHNET** |
| — | `group_ids`-Rebind (User aus system-users → tessera:*) | — | NIE | **BERECHNET** |

### 4.2 Die vier Autoren-Ebenen, nach Häufigkeit

- **B1 PRIMÄR (Alltag ~90%): AREA × ROLLE.** Matrix 39 Areas × Rollen, Zellwert = Stufe oder leer=erben. Floor-Rollup über 4 Etagen als Bulk. Skaliert: wenige Areas dominieren (eingangsbereich 312, elektro 221, waschküche 172, hvac 128). **Diese Ebene fasst der Auftraggeber im Alltag an.**
- **B2 AUSNAHMEN: ENTITY-OVERRIDE.** Höchste Spezifität, bewusst selten, Override-Zähler je Rolle als Hygiene-Signal.
- **B3 QUERSCHNITT: DOMAIN/LABEL/entity_category-Bulk** (ABAC-Schicht, liegt in der Precedence UNTER Area).
- **B4 DEFAULT: global je Rolle** + EIN sicherer Minimal-Default für nicht-gemappte User.

### 4.3 Sonderfall: die 1402 area-losen Entities (1074 enabled)

**Werden NIE einzeln gepflegt.** Fallback-Auswertung: Domain-Regel → `wd:`-Label → `entity_category` (config→deny, diagnostic→view-only) → Rollen-Default → system-deny. Plus **Drift-Sensor** „N neue/unzugeordnete Entities", der zur **Area-Nachpflege** (Datenhygiene) anstößt statt ACL-Einzelpflege. Ein `entity_category=config`-Selektor erschlägt 374, `diagnostic` 493 Entities mit je **einer** Regel.

> **State-only-Entities (Validierungs-Finding MEDIUM):** Live existieren ≥8 Entities im State-Machine OHNE Registry-Eintrag (`sensor.pv1_ertrag_heute`, …). Der Resolver expandiert area/label/category **durch Registry-Abfrage** → diese 8 sind NUR per `entity:<id>` scopebar, fallen sonst auf deny-by-default (sichere Richtung), erscheinen aber im Hygiene-Report als „N state-only, nicht area/label-scopebar". `all`/`domain`-Expansion muss zusätzlich `hass.states.async_entity_ids` scannen.

---

## 5. Resolution-Algorithmus

Die Auflösung läuft in **zwei Schichten**: Schicht 1 (Authoring-Resolver, **unser Code**, autoritativ — kennt Deny/Vererbung) liefert die Wahrheit; Schicht 2 (native HA-Engine) ist nur das Vehikel, in das die materialisierte Allow-Projektion geschrieben wird.

### 5.1 Precedence INNERHALB einer Rolle (first-match-wins, MIT Deny/UNSET)

| # | Ebene | Quelle |
|---|---|---|
| 1 | **entity-override** | Regel auf `entity_id == e` |
| 2 | **entity-area** | `area(e)` über DIREKTE `entity.area_id` |
| 3 | **device-area** | `area(e)` über `device.area_id` |
| 4 | **floor** | `floor(e)` — Etagen-Rollup (optional) |
| 5 | **domain** | `domain(e)` |
| 6 | **label / entity_category** | ABAC-Attribut |
| 7 | **global-default je Rolle** | Rollen-Grundhaltung |
| 8 | **system-deny** | Fail-safe |

Jede Ebene liefert `ALLOW · DENY · UNSET`. Erste Ebene mit ALLOW/DENY gewinnt; UNSET fällt durch. `DENY` wirkt **nur als Carve-out innerhalb derselben Rolle** gegen breitere Allows dieser Rolle.

### 5.2 Cross-Rollen-Merge (most-permissive — JEDES ALLOW gewinnt)

```
decide(u,e,a) = ALLOW  ⟺  ∃ r ∈ Rollen(u): decide_role(r,e,a) = ALLOW
```
**Es gibt KEINEN rollenübergreifenden Deny** (nicht nativ projizierbar). Ein DENY in Rolle A wird durch ALLOW in Rolle B überstimmt.

> **Validierungs-Finding HIGH (eingearbeitet): „Admin muss sich merken, dass Deny nicht cross-role ist" ist ein inakzeptabler Footgun für ein Sicherheitsprodukt.** → Statt bloßer Dokumentation: ein **aktiver Linter** im Compile/Preview rechnet pro gemanagtem User die **volle Cross-Rollen-Merge-Menge** und flaggt jede Entity, die eine Rolle verbirgt aber eine andere exponiert, als **ERROR** (blockt Apply oder erzwingt explizites Ack). Die **Impersonation-Preview ist die Wahrheitsquelle** (sie merged real). Prinzip: **SoD-by-assignment** — wer X nicht darf, trägt die X-erlaubende Rolle gar nicht.

### 5.3 Stufen-Ordnung (Monotonie)

```python
def effective(user, e):
    chg = decide(user, e, "change")
    opr = chg==ALLOW or decide(user, e, "operate")==ALLOW
    viw = opr or decide(user, e, "view")==ALLOW
    return {"read": viw, "control": opr}     # -> entity_ids-Projektion
```

### 5.4 Area-Resolver (das zentrale Eigen-Kunststück)

Nativ löst `area_ids` NUR über `device.area_id` → verfehlt die **419 direkt via `entity.area_id`** zugeordneten Entities. Tessera:
```
area(e) = entity.area_id ?? device.area_id ?? ∅
```
Jede Area-Regel wird zur **vollständigen entity_ids-Liste** expandiert (419 direkt ∪ 840 via-device = 1259 effektiv). Native `area_ids` wird höchstens als Device-Area-**Optimierung** mitgeschrieben, nie als alleinige Wahrheit.

### 5.5 Durchgerechnete Beispiele

**Beispiel A — Kind, eigenes Zimmer + ein Wohnzimmerlicht.** Store: `default={view:deny,operate:deny}`; `area:og_kind1 operate`; `entity:light.eg_wohnen_decke operate`.
- `sensor.og_kind1_temp`/view: E1 UNSET → E2/E3 area=ALLOW → sichtbar+bedienbar.
- `light.eg_wohnen_decke`/operate: E1 override=ALLOW → bedienbar; /view: override hat kein view → fällt durch → default deny → **ABER Monotonie: operate⇒view ⇒ eff_view=true** → Kind sieht das Licht (nötig zum Bedienen), sonst nichts aus dem Wohnzimmer.
- `climate.eg_wohnen`/view: keine Regel → default deny → unsichtbar.
- **Compiler emittiert:** `entity_ids:{ alle og_kind1:{read,control}, light.eg_wohnen_decke:{read,control} }` — kein breiter Allow.

**Beispiel B — Override sticht Domain-Deny.** Rolle `household`: `default={view:allow}`; `floor:eg operate`; `domain:camera {view:deny}` (Carve-out); `entity:camera.eg_eingang {view:allow}`.
- `camera.og_flur`/view: E5 domain camera=DENY → unsichtbar.
- `camera.eg_eingang`/view: E1 override=ALLOW → sichtbar (spezifischer als Domain).
- `climate.eg_kueche`/operate: E4 floor eg=ALLOW → bedienbar.

**Beispiel C — Cross-Rollen-Merge hebt Deny auf (die Lehre).** Oksana trägt `household` (EG operate, camera-deny) UND `resident_og` (OG view via `area:og_bad`). `camera.og_bad`: household→keine og-Regel; resident_og→area og_bad ALLOW(view), **kein camera-deny** → ALLOW gewinnt → **Kamera sichtbar**. → Der **Linter (§5.2) flaggt das als ERROR** vor Apply.

**Beispiel D — change=Voll-Admin.** Rolle `house_admin` (`is_admin=true`) → Mitglied in `system-admin` → `is_admin=true` → sieht+steuert ALLES, darf `config/*`. Kein per-Area-change. Die UI zeigt die Rolle als **„FULL ADMIN (system-weit, umgeht ALLE Tessera-Restriktionen)"**.

---

## 6. Enforcement & Compile-to-native-Policy

### 6.1 Compiler-Pipeline (Store → native Policies)

`compile(store, registries) → {group: PolicyType}` + `apply()`:
1. **Load & Snapshot** — Store + Registries; Content-Hash treibt Inkrementell-Recompile.
2. **Resolve Roles** — Grants sammeln, Vererbung (`inherits`) transitiv+zyklenfrei flatten.
3. **Expand Selectors → entity_ids** — area (beide Pfade!), floor, label, category über Resolver; device→native `device_ids`; domain/all native.
4. **Most-permissive-Fold per Rolle** — `decide_role` pro (Rolle×Entity), flache Allow-Menge.
5. **Emit Policy** — `entity_ids:{e:{read[,control]}}`; **immer Dict, nie bare True** (s.u.); deny = Key weglassen.
6. **Diff & Validate** — Invarianten asserten (s. 6.6).
7. **Apply (atomic, journaled)** — eine Gruppe je Rolle, User rebinden, Caches invalidieren.

### 6.2 ⚠️ CRITICAL: Kein bare-True-Leaf (Validierungs-Finding, eingearbeitet)

`util.compile_policy` macht aus **jedem** `bool`-Wert irgendwo `lambda: True` für alle Keys+Entities. **Harte Compiler-Invariante:** Tessera emittiert **niemals** bare `True`. Auch „ganze Domain operieren" wird `domains:{cover:{read:true,control:true}}` (Dict). **Post-Compile-Assertion:** walke die emittierte Policy, **ABORT** wenn irgendein Wert unter `entities` `is True` (Ausnahme: keine — selbst Admin bekommt `all:{read,control}` als Dict, oder bleibt schlicht über `is_admin` ungeschrieben). Unit-Test: je Rolle `check_entity == False` für ≥1 bekannt-restricted Entity.

### 6.3 Gruppen-/User-Topologie

- **Eine HA-Gruppe je Rolle:** `tessera:<role>`, policy = kompilierte entities-Policy, `tessera:`-Präfix für Drift-Erkennung.
- **Jeder gemanagte User wird aus `system-users` ENTFERNT** und in genau seine `tessera:*`-Gruppe(n) gelegt. Multi-Rolle → mehrere Gruppen → nativer most-permissive-Merge = gewünschte Union.

> **⚠️ CRITICAL (Validierungs-Finding, Dim1 korrigiert): `system-users` ist NICHT harmlos.** `auth_store.py` injiziert beim Laden zwangsweise `USER_POLICY = {"entities": True}`. Ein in `system-users` verbliebener gemanagter User hat **allow-all** und hebelt jede Einschränkung aus. Dim1's Behauptung „system-users policy ist None, leakt nicht" ist **falsch**; Dim3 ist korrekt. → Entfernen-aus-system-users ist **harte Invariante + Startup-Assertion + Drift-Check + Both-groups-Leak-Test**.

> **⚠️ CRITICAL (Validierungs-Finding HIGH): `group_ids`-REPLACE-Semantik → Cross-Rollen-Lockout.** `async_update_user(group_ids)` **ersetzt** die komplette Gruppenliste, kein Owner-Guard. Ein inkrementeller Recompile, der eine Rolle „vergisst", löscht sie beim Update. → **Harte Invariante:** `group_ids` ist **immer die vollständige Union ALLER Rollen-Gruppen** (+ ggf. `system-admin`), pro betroffenem User komplett aus dem Store rekonstruiert, **nie** ein Teil-Array. Apply-Assert. Admin-User behalten `system-admin` **zusätzlich**.

### 6.4 Schreibpfad — die größte Unbekannte (Phase-0-Spike-Pflicht)

> **⚠️ CRITICAL: Es gibt KEINE public Gruppen-CRUD-API.** `components/config/auth.py` registriert nur `config/auth/{list,create,delete,update}` für **User**, kein `group/*`. `auth_store.py` hat `async_get_group(s)`, aber **kein** `async_create_group/update_group/remove_group`. Apply läuft also nur über Mutation des privaten `_store._groups` + `_async_schedule_save` + manuelle Cache-Invalidierung — genau die fragile Privat-API.

**Auflösung / Härtung (Phase-0-Spike #1, auf Dev-Instanz, NIE Live-CM5):**
1. Exakt nachstellen, welchen Aufruf ACM (`Darkdragon14/ha-access-control-manager`) zum Persistieren nutzt und ob er über Releases überlebt; wenn sauber → exakt übernehmen.
2. Sonst dünner **versions-geguardeter Adapter** als **single choke-point je HA-Version**: `async_create_user/async_update_user(group_ids)` (public, stabil) für Mitgliedschaft + least-private stabile Methode für Policy, hinter HA-Version-Allowlist, die bei ungeprüfter Version ein **Repairs-Issue** wirft und auto-**Soft-Disable** auslöst. Die Behauptung „fully update-fest" wird **ehrlich heruntergestuft**.
3. **Panik-Disable hängt NICHT am fehlenden Group-DELETE:** User-`group_ids` per public `async_update_user` auf `pre_install_snapshot` zurücksetzen, `tessera:*`-Gruppen als mitgliedslose Hüllen liegenlassen.

### 6.5 Die drei Hooks + Leak-Guards

**view/operate reiten auf nativer Durchsetzung** — Compiler schreibt Policy, HA prüft:
- **POLICY_READ (view):** `get_states`/REST/`subscribe_entities` filtern via `check_entity(e, POLICY_READ)`; `subscribe_events state_changed` via `_forward_events_check_permissions`.
- **POLICY_CONTROL (operate):** Entity-Component-`call_service` prüft `check_entity(e, POLICY_CONTROL)` automatisch.

**Verifizierte Leak-Pfade (Validierungs-Findings, ehrlich abgegrenzt):**

| Pfad | Status | Behandlung |
|---|---|---|
| **render_template** (WS) | kein read-Check; Guard bräuchte Handler-Override = Monkeypatch (verboten) | **NICHT patchfrei schließbar.** Als dokumentiertes Rest-Leak im Threat-Model; view-Vertraulichkeit gegen non-admin-Token NICHT garantiert. |
| **logbook** (WS) | `get_events`/`event_stream` filtern NICHT (anders als history) | **NICHT patchfrei schließbar.** Dokumentiertes Rest-Leak; Tier-2 für confidentiality-kritisch. |
| **subscribe_events** non-state | nur `state_changed` gefiltert; Allowlist-Events ungated forwarded | Allowlist (`events.py SUBSCRIBE_ALLOWLIST`) im Spike enumerieren+dokumentieren; Tessera kann sie patchfrei nicht verengen. |
| **Custom-/Domain-Services + entity_id:all** | Auto-Check nur bei Entity-Component-Services; `mqtt.publish` etc. ungeprüft | **ALLOWLIST statt Denylist:** non-admins dürfen nur freigegebene entity-getargetete Services; alles andere (python_script, shell_command, *.reload, mqtt.*, custom async_register) default deny. MQTT/raw-Side-Channels sind außerhalb der Auth-Layer → Tier-2. |
| **Assist/Conversation/LLM-Agent** | läuft als System-Kontext (`user_id=None`) → POLICY_CONTROL/READ übersprungen | **Totaler Bypass.** Native exposed-entities ist die einzige patchfreie Scoping-Option; Assist für non-admins auf confidentiality-kritischen Installs deaktivieren; sonst Tier-2. |
| **history** (WS) | filtert aktuell (per-Version verifizieren) | Security-Test im Spike. |
| **Long-Lived Access Tokens** | erben volle Live-Policy des Users (nicht entity-scopebar) | Confinement gilt für non-admin-LLATs auf enforced Pfaden; macht render_template/logbook/mqtt **headless erreichbar**. Die 4 existierenden LLATs im Spike auditieren (god-tokens?). Security-Tests **durch einen LLAT** laufen. |

**Defense-in-depth:** dünner Frontend-Layer (browser_mod/Lovelace `visible:`) verbirgt nur, was das Backend ohnehin verweigert — UX, nie Grenze.

### 6.6 Fail-safe / kein Lockout

- **Owner** (`is_owner`, `ha-admin`): hart bypassed, **nie** in Rolle gezwungen, Tessera fasst Owner-Policies nie an. Lockout strukturell unmöglich.
- **Compiler-Invariante:** ≥1 nicht-leere Admin-Bindung muss bestehen, sonst **Abbruch ohne Schreiben**.
- **Apply-Lockout-Guard:** nach Simulation muss ≥1 nicht-Owner-Admin Vollzugriff behalten UND der Bediener sich nicht selbst aussperren — sonst Abbruch.
- **Owner-/Admin-Schutz im Rebind:** kein User mit `is_owner` oder aktueller `GROUP_ID_ADMIN`-Mitgliedschaft wird je in ein Tessera-`group_ids`-Update einbezogen, das `GROUP_ID_ADMIN` entfernt (getesteter Unit-Test).
- **Physischer Notausgang ohne UI:** Datei `/config/tessera_disabled` → Soft-Disable, damit ein ausgesperrter Admin via Samba/SSH-an-die-VM den Notausgang ohne `is_admin` ziehen kann.

### 6.7 Performance (2661 Entities)

- Voll-Compile ist klein: Expansion O(Entities × Rollen) Registry-Filtering (~ms), I/O = N Gruppen-Policies + 7 User-Rebinds. Ziel <1s, Heavy-Filtering auf Executor.
- **Caching:** expandierte entity-Sets je `(selector, registry_hash)` (Area-Expansion über Rollen wiederverwendet).
- **Inkrementell:** Content-Hash; Store-only → nur betroffene Rollen re-folden; Registry → nur membership-sensitive Selektoren re-expandieren.
- **Trigger:** Admin-Apply; Registry-Events (debounced 5–10s gegen Bulk-Import, **Fast-Path** für sicherheitsrelevante Single-Moves); Login (nur Membership prüfen, kein Voll-Recompile); Authentik-groups-Change.
- **Cache-Invalidierung ohne Restart:** `User.invalidate_cache()` poppt die `permissions`-`cached_property`. **Offen (Spike):** ob reine **Policy**-Änderung bei gleicher Mitgliedschaft den Cache platzt — empirisch messen, im Zweifel alle 7 User invalidieren (billig).
- **Größen-Budget (Validierungs-Finding HIGH):** Differenzmengen (z.B. domain:sensor minus 3 = ~1100 IDs) blähen `.storage/auth` auf. → Bei Differenz >~200 Entities **device_ids** nutzen (native Device-Lookup korrekt) statt jede entity_id; nur 419 direkt-area + area-lose einzeln. Apply bricht mit Warnung ab bei Überschreiten eines Eintrags-/Größen-Schwellwerts. Spike-Benchmark auf CM5.

---

## 7. Authentik/IdP-Mapping

> **Diese Dimension wurde als Platzhalter („test") eingereicht — BLOCKING-Gap. Hier vollständig spezifiziert aus R1/R2/D2/D4/D9 + Validierungs-Findings.**

### 7.1 Truth-Level-Trennung

**Authentik = Identität + Gruppen-Mitgliedschaft (SoT für Person→Gruppe). Tessera = App-Permissions (Gruppe→Rolle→Policy).** Saubere Analogie zur NetBox/1Password-Trennung. Authentik trägt **keine** Permission-Logik, nur Pointer (Gruppennamen).

### 7.2 Der `groups`-Claim-Seitenkanal (Kernproblem)

`auth_oidc` v1.1.1 reicht `groups` **nur binär admin/user** durch. Der rohe `groups`-Claim muss **parallel** gelesen werden. **ADR 0005 / v1:** `membership.by_group` bleibt geparst, validiert und persistiert, ist aber **v1-inert** und wird vom Compiler nicht in native Policies oder User-Bindings projiziert. Aktivierung erst post-v1 mit At-Login-Hook, D12-Live-Beweis und Re-Gate. **Bis dahin tragen ausschließlich `by_user`-Bindungen v1-Enforce.**

### 7.3 Mapping-Kette (n:m, konfigurierbar)

```
Authentik-Gruppe ──(bindings.by_group, v1-inert)──▶ Tessera-Rolle(n) ──▶ Grants ──▶ native Policy
"authentik Admins" ─────────────────────▶ role_admin (is_admin) → system-admin
```
- **n:m** (D9): eine Gruppe → mehrere Rollen, eine Rolle ← mehrere Gruppen. Nested Gruppen = v2.
- **`authentik Admins` → HA-Admin bleibt bestehen** (R2 [M]).
- **Sync-Timing (D4):** v1 = Login-Zeit (Claim); near-real-time (API-Poll/Webhook) = v2.

### 7.4 Dual-Login / lokale User (D2 — kritisch, Validierungs-Finding MEDIUM)

4 von 7 Usern authentifizieren lokal (`homeassistant`-Provider) → `by_group` greift für sie **nicht**.

**Auflösung (Zero-Dependency-Constraint gewinnt):** **`by_user` ist der Baseline-Pfad, der IMMER funktioniert** (R1 [M]); `by_group` ist additiv. → v1 führt lokale User **explizit per `by_user`** einer Rolle zu (kein „OIDC-Migration ist harte Vorbedingung"). **Enforce-Gate:** Apply nach `enforce` verweigern, solange ein aktiver nicht-Owner/nicht-Admin-User weder einer Rolle zugewiesen noch als **`unmanaged`** markiert ist (Service-Accounts wie `mqtt-service` → **Default: eigene Tessera-Service-Rolle**; `unmanaged=true` ist **kein** Verbleib-in-`system-users`-allow-all, sondern nur **Breakglass** mit Ablaufdatum + Audit + rotem UI — sonst hebelt es via `system-users` alles aus). Wenn ein User via no-groups-Provider authentifiziert aber nur eine `by_group`-Bindung hat → Enforce verweigern.

### 7.5 Authentik-Ausfall (R2 [S])

Gecachte Claims (letzter erfolgreicher Login) bleiben gültig; lokaler Notfall-Override über `by_user` + Owner-Bypass. Ein Authentik-Ausfall darf **nie** zum Lockout führen — der RBAC-Kern hängt nie am IdP.

---

## 8. Pflege-UX / Admin-UI, Migration, Monitor, Drift, Audit, Panik, Store/Backup

### 8.1 Admin-UI

- **Area × Rolle Matrix (Primäransicht):** Y = 39 Areas + Pseudo-Zeilen („⚠️ Ohne Area (1402/1074 enabled)", „Nach Label", „Nach Domain", „Global-Default"); X = Rollen. Zelle = Aggregat-Tristate (●/○/◐) + „n Overrides"-Badge. Virtualisiertes Grid, Area-Aggregat statt Entity-Liste. Filter: nur-Konflikte/nur-Overrides/nur-area-los/Label/Suche.
- **Override-Editor:** zeigt **effektive Auflösung** (welcher Selektor gewinnt, Precedence-Kette) **vor** Änderung; erklärt explizit „Sperren = aus Allow herausnehmen (kein Deny-Override)"; **Guard** warnt, wenn ein „Sperren" durch eine breitere Allow-Regel einer anderen Gruppe wieder erlaubt würde (most-permissive sichtbar machen — §5.2-Linter).
- **Impersonation-Preview „Was sieht/darf User X?":** rechnet die volle Merge-Policy read-only gegen Ist ODER Staging; 3 Listen (sichtbar/bedienbar/verborgen) gruppiert nach Area + Zähler; **Owner-Warnung** „bypassed ALLE ACL"; **jede `is_admin`-Rolle** zeigt „Voll-Admin — sieht/darf alles". Nutzt exakt die native Merge-/Compile-Logik (kein Parallel-Pfad).
- **Diff/Apply/Rollback (3-Phasen, Pflicht-Gate):** Stage (sammelt in `tessera.policy.staging`) → Diff/Plan (pro User +gewonnen/−verloren view/operate, wie `terraform plan`) → Apply (Revision schreiben, Auto-Rollback-Snapshot, kompilieren, native schreiben, Re-Read-Verify, Audit; Teilfehler → Auto-Rollback). Revisions-Ring (20) + Ein-Klick-Rollback.

### 8.2 Migration / Seed (FreeRADIUS-Monitor-Analogie)

- **Phase 0 — Inventar-Snapshot & Hygiene-Report (read-only):** 419 direkt-area, 840 via-device, **1402 area-los (1074 enabled)**, 493 diagnostic, 374 config, 797 gelabelt, 8 state-only. CSV/UI der area-losen enabled-Entities → Datenhygiene-Vorlauf (4–9 PT, Pflicht).
- **Phase 1 — Seed (deny-by-default, D3):** Rollen aus Bindungen; Default = leerer Allow-Satz; Bulk **selektorbasiert** (Area-Regeln je Area×Rolle, `wd:`-Labels, `entity_category` config/diagnostic, sensible Domains) — nicht 2661 einzeln.
- **Phase 2 — MONITOR/DRY-RUN (Pflicht-Tor):** `mode=monitor` loggt `tessera_would_block`-Events ohne Durchsetzung; mehrtägiger Realbetrieb → Auswertung welche legitimen Zugriffe blockiert würden → nachjustieren. **Kein Scharfschalten ohne grünen Lauf.** Pro existierendem User Report „verliert nach enforce X sichtbare Entities" (speziell die 4 lokalen + `mqtt-service`).
- **Phase 3 — Enforce (gestaffelt):** erst Test-User scharf, dann Rest; User aus system-users → tessera-Gruppen.
- **D11:** v1 kompiliert nur 2220 enabled+visible; 441 disabled/hidden unter Default-Deny-Fallback. **Disabled (436, absent aus State-Machine) ≠ hidden (5, present+leakbar)** — hidden MÜSSEN in-scope (Validierungs-Finding).

### 8.3 Monitor / Dry-Run

Drei Modi in `tessera.config`: `off` (lädt, schreibt nichts, nativ unverändert — Panik-Äquivalent), `monitor` (kompiliert+evaluiert+loggt, schreibt NICHT), `enforce` (schreibt nativ). In enforce **ist** die Policy nativ — kein Parallel-Pfad (sonst Divergenz). Umschaltung monitor→enforce = riskanteste Aktion → Confirm + Lockout-Sim + Auto-Snapshot. Sampling/Dedup gegen Log-Flut.

### 8.4 Drift & Onboarding

Inventar-Fingerprint + Registry-Event-Listener. Klassen: (1) neue Entity von Selektor erfasst → INFO; (2) **orphan-new** → Default-Deny + Notify „N neue unzugeordnete Entities"; (3) **Area-Move** → betroffene Regeln neu kompilieren, sicherheitsrelevante Moves **Fast-Path** (nicht debounced), Device-Area-Move zeigt **Fan-out** (N Entities); (4) **Policy-Drift extern** (compiled-Hash ≠ nativ, z.B. nach HA-Restore) → Notify + „Re-Apply (Store gewinnt)". **HA-Repairs-Integration.** Täglicher Reconcile als Netz für verpasste Events. **entity_id-Recycling** (gelöscht+gleichnamig neu) → Re-Bestätigung statt stiller Override-Reaktivierung.

### 8.5 Orphan-Cleanup

Gelöschte Entity/Area/Device, noch referenziert → als `stale` markieren, aus Compile ausschließen (tote Referenz = kein nativer Eintrag), „N verwaiste Regeln bereinigen?" anbieten (nicht still löschen, Audit-Spur, optional 30-Tage-Grace). Area-Löschung = Drift-F2 + Orphan-G kombiniert.

### 8.6 Audit-Log

Append-only JSONL, getrennt vom Policy-Store: `change` (ts, actor, action, target, revision, before/after-Hash, diff) + `decision` (monitor/sampled). before/after-Hash-Chain = **tamper-evident** (echte Non-Repudiation nur mit externem Export/Signatur). Rotation (Ring) + optionaler Export.

### 8.7 Panik-Disable (mehrstufig)

- **Stufe 1 Soft-Disable** (`mode=off` / `tessera.disable` / Big-Red-Button / Datei `/config/tessera_disabled`): kompiliert/erzwingt nichts; native Policies bleiben aber bestehen.
- **Stufe 2 Restore-to-native:** User aus `pre_install_snapshot` (eingefroren bei allererster Aktivierung, **IMMUTABLE**) zurück in system-Gruppen via public `async_update_user`, tessera-Gruppen als Hüllen liegenlassen → exakt Zustand vor Tessera.
- **Stufe 3 Owner-Garantie:** Owner bypassed strukturell, kann immer Stufe 1/2 auslösen.
- **Fail-closed vs. fail-safe-Balance:** Bei Tessera-**internem** Fehler (Store korrupt, Compile-Exception) → Stufe 1 (`off`, nativ unverändert), **NICHT** alles-deny. Deny-by-default gilt für **unbekannte Entities**, nicht für „Integration kaputt".

### 8.8 Store / Backup

`.storage/tessera.*` fährt im HA-Backup mit. **Restore-Konsistenz-Check beim Start:** `tessera.policy`-Hash vs. `tessera.compiled.source_hash`; nach Restore (native Gruppen evtl. aus anderem Stand) → Drift → **Auto-Re-Compile + Re-Apply** (Store gewinnt). compiled ist nie autoritativ (Selbstheilung aus Policy). Atomic writes (tmp+rename). **Two-Phase-Apply mit Journal** (`apply_in_progress` in `tessera.state`): bei Crash mid-apply → beim Start vollständig re-applien (idempotent) oder auf pre-apply-Snapshot zurück, BEVOR Integration normal startet; Reihenfolge restriktiv (erst Gruppen, dann Rebind). **YAML-Export/Import** (`tessera.export_yaml`/`import_yaml`): deterministisch sortiert, schema-gestempelt, Import nur über Staging + erzwungenen Diff; keine Secrets → committierbar.

---

## 9. Eingearbeitete Validierungs-Findings (Severity + Lösung) + Restrisiken

| # | Severity | Finding | Lösung in dieser Spec |
|---|---|---|---|
| 1 | **CRITICAL** | bare-True short-circuit (`util.compile_policy`) — `domains:{x:true}` = allow-all | §6.2: nie bare True, immer Dict; Post-Compile-Assertion ABORT bei `is True`; Unit-Test |
| 2 | **CRITICAL** | `system-users` force-injiziert `USER_POLICY={entities:True}` — Dim1 war falsch | §6.3: Entfernen-aus-system-users = harte Invariante + Startup-Assert + Drift + Both-groups-Test |
| 3 | **CRITICAL** | keine public Gruppen-CRUD-API | §6.4: Phase-0-Spike, versions-geguardeter Adapter, Panik unabhängig vom Group-DELETE |
| 4 | **CRITICAL** | `group_ids`-REPLACE → Cross-Rollen-Lockout | §6.3: `group_ids` immer vollständige Union, Apply-Assert; Admin behält system-admin |
| 5 | **HIGH** | render_template/logbook read-leak — Guard = Monkeypatch (verboten) | §6.5: ehrlich als nicht-patchfrei-schließbare Rest-Leaks dokumentiert; view ≠ untrusted-grade; Tier-2 |
| 6 | **HIGH** | Custom-/Domain-Service-Bypass (`mqtt.publish` ungeprüft) | §6.5: ALLOWLIST statt Denylist; MQTT/Side-Channels → Tier-2; user_id-Propagation als Test-Invariante |
| 7 | **HIGH** | change=is_admin TOTAL nicht scoped | §2.3: Re-Label „Voll-Admin (global)"; Validator verbietet narrowing-Grants in admin-Rolle; Preview zeigt „bypassed alles" |
| 8 | **HIGH** | most-permissive hebt Cross-Rollen-Deny auf | §5.2: aktiver Linter (ERROR vor Apply), nicht bloß Doku; Preview = Wahrheitsquelle |
| 9 | **HIGH** | Teil-Apply nicht atomar (kein natives Transaction) | §8.8: Two-Phase-Apply mit Journal, restriktive Reihenfolge |
| 10 | **HIGH** | Compile-Größe/Perf (Differenzmengen blähen auf) | §6.7: device_ids ab >200, Größen-Budget-Abbruch, Spike-Benchmark |
| 11 | **HIGH** | Cache-Invalidierung bei reiner Policy-Änderung ungeklärt | §6.7: explizite `invalidate_cache`, im Zweifel alle 7; Spike-Verifikation |
| 12 | **MEDIUM** | Assist/Conversation = System-Kontext-Bypass | §6.5: Threat-Model, exposed-entities aligned, Assist für non-admins deaktivieren / Tier-2 |
| 13 | **MEDIUM** | LLATs erben Voll-Scope, machen Leaks headless erreichbar | §6.5: 4 LLATs auditieren, Security-Tests durch LLAT |
| 14 | **MEDIUM** | logbook + allowlisted Events | §6.5: dokumentiert; Allowlist im Spike enumerieren |
| 15 | **MEDIUM** | state-only + hidden vs. disabled Entities | §4.3/§8.2: state-machine-Scan, hidden in-scope, Hygiene-Report |
| 16 | **MEDIUM** | lokale User: by_group inert | §7.4: by_user-Baseline, Enforce-Gate, unmanaged-Markierung |
| 17 | **BLOCKING-GAP** | Authentik-Dimension = Platzhalter „test" | §7: vollständig spezifiziert |
| 18 | **LOW** | „system-users = entities:true breit" überzeichnet vs. korrekt | §6.3: korrekt zugeordnet (entities:True via USER_POLICY-Injection ist real; ADMIN_POLICY ist die breite — beide gefährlich, Merge unkontrolliert → Konsequenz „raus aus system-users" bleibt) |

### Verbleibende Restrisiken (ehrlich)
- **view-Vertraulichkeit ist single-instanz NICHT untrusted-grade** (render_template/logbook/Assist/LLAT). DoD muss qualifiziert werden: „operate/control durchgesetzt; view = get_states/REST/history-Hiding + dokumentierte Rest-Leaks". Confidentiality-kritisch → Tier-2.
- **Schreibpfad bleibt die größte Update-Fragilität** bis Spike-Verifikation; „update-fest" nur für die enforced read/control-Hooks, nicht für die Group-Persistenz.
- **Granulares change** bewusst nicht gelöst (Nicht-Ziel v1).
- **Authentik-Seitenkanal ungebaut** → by_group bis dahin inert.

---

## 10. Offene Fragen / Entscheidungen für Codex (Diskussionsgrundlage)

**Block A — Phase-0-Spike (harte Vorbedingung, Dev-Instanz, NIE Live-CM5):**
1. **Schreibpfad (#1-Risiko):** Welcher exakte Aufruf persistiert Gruppen-Policy + Mitgliedschaft? Übernimmt ACMs Mechanismus, oder eigener versions-geguardeter Adapter? Über welche HA-Versionen stabil?
2. **Cache-Invalidierung ohne Restart** bei reiner Policy-Änderung (gleiche Mitgliedschaft): platzt `invalidate_cache` die `cached_property`? Empirisch messen.
3. **Service-Call-Choke-Point:** existiert ein supporteter Interception-Punkt für ALLE Service-Calls, oder muss non-entity-Service-Control als nicht-patchfrei deklariert werden?
4. **Allowlist `SUBSCRIBE_ALLOWLIST`** (events.py) enumerieren — welche Events tragen Entity-Daten?
5. **history-WS** auf 2026.6.x: filtert es restricted Entities für non-admins?
6. **`.storage/auth`-Größe + Schreibdauer** auf CM5 bei 10–15 Rollen × enumerierten entity_ids benchmarken; blockiert ein großer auth-Write andere Auth-Ops?
7. **4 existierende LLATs** auditieren (god-tokens?).

**Block B — Modell-/Scope-Entscheidungen:**
8. **D1 change-Granularität:** Admin/Non-Admin-Split bestätigt — bleibt `change.grant` als gespeicherte Absicht/Anzeige oder ganz raus aus v1-Schema?
9. **D3 Default-Policy:** deny-by-default für alle Rollen, oder „Haushalt" pragmatisch view-allow-by-default (sanfter), während Gast/Default hart deny?
10. **Floor** als erstklassiger Scope-Typ (Tessera-Erweiterung) oder nur interne Area-Sammelhilfe? (4 Floors gepflegt, nützlich.)
11. **except/Differenzmengen-Schwelle:** ab welcher Größe device_ids/Sammelgruppen statt entity_ids? (konkreter Schwellwert)
12. **D11 disabled-vs-hidden:** hidden in-scope bestätigt — disabled bis Reaktivierung defer?

**Block C — Authentik/Provider:**
13. **D2:** by_user-Baseline für lokale User bestätigt (statt „OIDC-Migration ist harte Vorbedingung")? Service-Accounts als eigene Rolle ODER `unmanaged`?
14. **D4 Sync-Timing:** Login-Claim v1, API-Poll/Webhook v2 — bestätigt?
15. **groups-Seitenkanal:** liest er den rohen Claim zuverlässig at-login, oder Authentik-API-Poll schon für v1 nötig?

**Block D — Cross-Rollen / SoD:**
16. **Cross-Rollen-Deny:** Linter/Preview-Warnung (ERROR) statt echtem Cross-Deny bestätigt? Block-Apply oder force-ack?
17. **`wd:`/`acl:`-Label-Namespace:** manuell pflegen oder beim Onboarding semi-automatische Vorschläge (alle camera/lock → `wd:sensibel`)?

**Block E — Lifecycle:**
18. **Rollback-Tiefe** (20 Revisionen?) + max `.storage`-Größe vor Rotation (Forensik vs. Backup-Größe).
19. **Orphan-Grace-Period:** 30 Tage stale oder sofort-Cleanup-Angebot?
20. **Reconcile-Frequenz:** täglicher Voll-Abgleich als Cron-Netz, oder reicht event-getrieben?
21. **YAML-Export-Ablage:** nach `/config/tessera/policy.yaml` (= HA-Repo `NoSilver78/HA` mit Auto-Sync) oder eigenes Tessera-Repo?

**Block F — Strategie:**
22. **ACM-Fork (~40–75 PT) vs. Neubau (~55–100 PT)** — Entscheidung erst NACH Spike (de-riskt die größte Unbekannte).
23. **DoD-Reformulierung:** „Non-Admin sieht+steuert ausschließlich erlaubte Entities — verifiziert auf REST+WS+Service" muss qualifiziert werden zu „...für get_states/single-state/history/service-control; render_template+logbook+Assist+allowlisted-Events = dokumentierte Rest-Leaks, nur via Tier-2 schließbar". **Bestätigen, dass diese ehrliche Abgrenzung akzeptiert ist** — sonst verspricht das Produkt falsche Sicherheit.

---

**Kernaussage für Codex:** Das Konzept ist tragfähig und auf den nativen Hooks korrekt verankert (read/control echt durchsetzbar, Owner/Admin strukturell immun, Area-Resolver schließt die 419-Lücke, Allow-only via Spezialisierung). Drei CRITICAL-Korrekturen sind eingearbeitet (kein bare-True, raus-aus-system-users als Invariante, group_ids-Union). Die zwei verbleibenden Ship-Blocker sind **(a) der Schreibpfad** (Phase-0-Spike) und **(b) die ehrliche Bounding von view-Vertraulichkeit** (render_template/logbook/Assist/LLAT sind single-instanz nicht schließbar → operate/control ist die Grenze, Tier-2 für untrusted). Nicht weiterbauen, bevor Block A auf der Dev-Instanz beantwortet ist.

---

## 11. Codex-Review (Runde 1+2) — eingearbeitet (2026-06-29)
Codex hat unabhängig reviewt (4 Agenten × 2 Runden, gegen HA-Core-2026.6.4-Quelltext im Dev-Container) → **Verdikt MODIFY → Phase-0-Spike → Go/No-Go.** Starke Konvergenz mit meinem Agentensystem, **kein neuer Show-Stopper.** Eingearbeitete Schärfungen:

**Korrekturen an bestehenden Punkten**
- **C1 bare-True → SCHEMA-AWARE** (Codex): nicht „jedes `True` unter `entities` verbieten" (blockt legale `{read,control}`-Leafs!), sondern nur `entities:true` / `entities.domains:true` / `entities.entity_ids.X:true` verbieten; `…X.read/control:true` erlauben. `domains:{cover:true}` = alle Keys für Domain cover, **nicht** alle 2661 (§6.2 war zu grob). *(util.py:40-46/55-57/82-96)*
- **`entity_id:all`** ist KEIN genereller Bypass für Entity-Component-Services **mit** User-Kontext (HA wählt nur kontrollierbare Entities, service.py:672-689). Risiko bleibt non-entity/custom/raw/Systemkontext.
- **Assist/Conversation differenzieren:** Entry-Points tragen oft User-Kontext (conversation/http.py:60-65); echtes Risiko = view-Exposure beim Matching + Control-Bypass nur bei Systemkontext/non-entity/Agent-Tool.

**Erweiterte Leak-Matrix (NEU — view noch weniger vertraulich)**
+ **Registry-WS-Reads** (`config/{entity,device,area,floor,label,category}_registry/list*`) → Namen/Struktur/Existenz/disabled-hidden ungefiltert · + **REST-Service-`changed_states`** (api/__init__.py:424-455, bei `return_response`) · + **Logbook REST** (rest_api.py:68-110, nicht nur WS). → DoD §11-Schluss verschärft.

**Recovery gehärtet (P0/R2)**
- Zwei getrennte Notausgänge: **`tessera_disabled`** (stoppt Tessera, native Policy BLEIBT — hilft NICHT bei policy-verursachtem Lockout) vs. **`tessera_restore_native`** (Restore-to-preinstall via public `async_update_user` = echte Rettung).
- **Boot-Rescue/Safe-Mode-Loader:** greift AUCH bei korruptem Store / kaputtem Tessera-Code (nicht vom gesunden Start abhängig).

**Service-Accounts & LLATs = Enforce-Gates (P0/P1)**
- **`unmanaged` ≠ allow-all:** Default = eigene Tessera-Service-Rolle; `unmanaged` nur Breakglass (Ablauf + rotes UI + Audit).
- **LLATs:** 4 (3 Owner, 1 weiterer Admin, 0 non-admin) → vor Enforce inventarisieren/rotieren; Security-Tests **durch einen LLAT** (nicht nur UI/WS).
- **Service-Choke-Point nicht universal:** v1 verspricht nur **entity-targeted** Core-Service-Control; non-entity/raw/custom = Allowlist oder außerhalb des Versprechens.
- **SoD-Konflikte BLOCKEN Apply** (nicht nur Linter-Warnung); Force-Ack nur Breakglass (Ablauf + Entity-Liste + Audit).

**Terminologie & fehlende Produkt-Doku (Codex §9 — nachzuziehen)**
- **Audit ≠ „Non-Repudiation"** → „tamper-evident Hash-Chain"; echte Non-Repudiation nur mit externem Export/Signatur.
- Nachzuziehen: (1) öffentlicher **„Was Tessera NICHT garantiert"**-Abschnitt · (2) **Threat-Actor-Modell** (Owner/Admin · Haushalt · Gast/Dienstleister · Service-Account · gestohlener LLAT · Systemkontext · böse Custom-Integration) · (3) Token-Lifecycle · (4) Service-Account-Policy · (5) **`AuthStoreAdapter`-Contract** (HA-Version-Allowlist, atomic-ish, re-read-verify, cache-invalidation) · (6) **Test-Matrix** (REST/WS/LLAT/entity-service/entity_id:all/non-entity/template/logbook/history/events/Assist) · (7) **HACS-Update-Governance** (kein Auto-Update in Enforce ohne Preflight; HA beta/current/previous).
- **Custom-Component-Testmatrix:** 14 Custom-Domains (8 mit `services.yaml`, 12 mit HTTP/View/Panel, mehrere WS) + 15 YAML-Dashboards (0 `require_admin`) → Phase-0 klassifizieren + restricted-User-UI-Test.

**Architektur-Entscheidung bestätigt:** **Neubau Tessera**, ACM nur als Schreibpfad-Spike-Referenz + Regression-Orakel (nutzt `hass.auth._store/_groups` + `_data_to_save()` = private API). Endgültige Fork-vs-Neubau nach Phase-0.

**DoD-Reformulierung (akzeptiert, verschärft):**
> Tessera begrenzt Non-Admin-Zugriff für **getestete** Pfade: `get_states`, single-state, History, entity-targeted Service-Control. `render_template`, Logbook (REST+WS), Registry-WS, Service-`changed_states`, Assist, allowlisted Events, Systemkontext und non-entity/raw Services = **dokumentierte Rest-Leaks bzw. Tier-2**. **`operate/control` = die Grenze; `view` = begrenzter Komfortschutz, NICHT harte Vertraulichkeit gegen untrusted.**

### 11.1 Phase-0-DoD (Codex-Gate — beide Systeme einig, harte Vorbedingung für Bau)
Bestanden, wenn grün — auf Dev-Instanz, NIE Live-CM5:
1. `tessera:*`-Gruppen create/update/delete **+ Restart-Survival** · 2. Cache-Invalidierung bei **reiner Policy-Änderung** · 3. echte `check_entity`-Proben je Probe-User · 4. `group_ids`-**Union** + Restore-to-native · 5. **Rescue-Pfad bei defektem Tessera** · 6. Service-Matrix prüft Execution **+ Response-Leaks** · 7. Leak-Matrix (Registry-WS, Logbook REST/WS, render_template, changed_states, Events, Assist) · 8. LLAT-Testmatrix + Rotation · 9. Custom-Component-Service/WS/HTTP-Gate · 10. CM5-`.storage/auth`-Benchmark · 11. ungeprüfte HA-Version → auto `monitor/off` · 12. Authentik `by_group` bewiesen ODER bewusst aus v1-Enforce raus.
