# Technische Spezifikation — Group Source (IdP-Gruppe → Tessera-Rolle)

Stand 2026-10-25 · Architekturmodus · Grundlage:
[`exchange/2026-10-25/ha-auth-review-und-authentik-claude-2026-10-25.md`](../exchange/2026-10-25/ha-auth-review-und-authentik-claude-2026-10-25.md)
· berührt [ADR 0005](../decisions/0005-by-group-v1-inert.md) (ohne ihn zu widerrufen)

## Ziel

Die Lücke **Gruppe → Rolle** schließen: Mitgliedschaften aus einem Identity-Provider (erste
Implementierung **Authentik**) werden zu Tessera-Rollen-Mitgliedschaften — **ohne** den Login-Pfad zu
berühren und **ohne** die bereits gegatete Enforce-Strecke anzufassen.

Authentik beantwortet schon heute „wer ist das?" (OIDC via `hass-oidc-auth`) und „in welchen Gruppen
ist er?". Tessera beantwortet „was darf er?". Dazwischen liegt bislang Handarbeit: `by_user` wird
von Hand, per Service oder Panel gepflegt. Diese Spezifikation beschreibt genau diese Naht.

## Anforderungen

| # | Anforderung |
|---|---|
| **R1** | Der Sync schreibt **ausschließlich** `membership.by_user`, und zwar über den bestehenden Pfad (`set_user_membership` → `async_save_config` → `_compile_for_mode_safely`). Kein neuer Projektionspfad, keine Änderung an Compiler, Bindings, Lockout-Precheck oder Restore. |
| **R2** | **Provenienz:** der Sync darf nur `(user, role)`-Paare anfassen, die ihm gehören. Von Hand, per Service oder Panel gesetzte Paare bleiben unberührt. |
| **R3** | **Generische Naht:** ein `GroupSource`-Protokoll; Authentik ist die erste Implementierung, nicht die einzige mögliche (ROADMAP: „ohne Zwang zu einem bestimmten Identity-Provider"). |
| **R4** | **Fail-closed:** IdP unerreichbar, Antwort unplausibel oder Mapping unklar → **letzter bekannter Stand bleibt**. Niemals Ausweitung ohne Beleg, niemals Entzug ohne Beleg. |
| **R5** | **Plausibilitäts-Guard:** ein Lauf, der mehr als einen konfigurierten Anteil der verwalteten Mitgliedschaften entfernen würde, wird **nicht angewandt**, sondern zur Bestätigung vorgelegt. |
| **R6** | **Admin bleibt beim IdP:** eine Rolle mit `is_admin` wird über den Sync **nicht** vergeben, solange das nicht ausdrücklich pro Mapping-Eintrag freigeschaltet ist. |
| **R7** | **Keine Secret-Werte** im Store, in Logs, in Diagnostics, in Repairs-Texten. Nur eine Referenz (1Password-Titel + UUID bzw. `!secret`-Schlüssel). |
| **R8** | **Monitor-first:** der Sync ändert nur den Store; ob daraus ein nativer Write wird, entscheidet allein der bestehende Modus (`off`/`monitor` schreiben nicht). |
| **R9** | **Nachvollziehbarkeit:** jede Änderung mit Provenienz ins Log/Journal; Konflikte und abgelehnte Läufe als Repairs-Issue. |
| **R10** | **Deterministische Identitäts-Abbildung** über den Benutzernamen (bei uns `preferred_username` == HA-Username). Keine E-Mail-Heuristik. Nicht eindeutig zuordenbare IdP-Nutzer werden **nicht** gemappt. |

## Nicht-Ziele

- **Kein OIDC-/Auth-Provider in Tessera.** Login bleibt bei `hass-oidc-auth`; Begründung in
  Nachtrag 3 des Reviews (Schadensradius, zweite Private-API im Login-Pfad, NIST-Funktionstrennung).
- **Kein Schreiben nach Authentik.** Der Sync liest. Gruppenpflege bleibt im IdP.
- **Keine Verwaltung von HA-Admin.** `change`/`is_admin` ist global (HA-Limit) und wird heute schon
  vom IdP entschieden (`roles.admin: "authentik Admins"`).
- **Keine Echtzeit-Garantie.** Der Sync ist eventual consistent; ein optionaler Webhook kann die
  Latenz senken, ersetzt aber den Reconcile nicht.
- **Kein Ersatz für manuelles `by_user`.** Lokale Rollen (Gäste, Dienstkonten, der Admin selbst)
  müssen weiter ohne IdP funktionieren.

## Annahmen

Alle gegen den Ist-Stand geprüft, nicht vermutet:

1. **HA hat keine öffentliche API, um Gruppen zu schreiben** (`AuthStore`/`AuthManager` nur lesend;
   `config/auth`-WebSocket nur User). Geprüft bis `dev` (2026.11). Tesseras Schreibpfad bleibt die
   einzige Option.
2. **`hass-oidc-auth` gibt den `groups`-Claim nicht heraus:** er wird zu *einem* Wert
   (`system-users`/`system-admin`/`invalid`) verdichtet, die Liste wird verworfen. Kein Event, kein
   Store. → Der Claim-Weg ist ohne Upstream-Änderung versperrt.
3. **Die Identitäts-Brücke ist deterministisch:** HA linkt über `preferred_username`, die HA-Nutzer
   heißen genauso.
4. **Ein OIDC-Login überschreibt bestehende Gruppen nicht:** `async_get_or_create_user()` kehrt bei
   `credentials.is_new == False` unverändert zurück; `group_ids` aus `UserMeta` nur im
   Erzeugungspfad. **Auf dem Papier geprüft — auf `ha-tessera-dev` zu bestätigen.**
5. **`validate_config_data()` konstruiert ein Dict mit festen Schlüsseln** und verwirft unbekannte.
   Ein neues Feld muss daher **im selben Schritt** in den Validator, sonst verschwindet es beim
   nächsten Save (das Verwerfen ist das sichere Verhalten, aber kein brauchbares).
6. **Die Integration hat heute keinen Timer** (`async_track_time_interval` kommt nicht vor). Der Sync
   führt die erste geplante Aufgabe ein — mit allem, was dazugehört (Abbruch beim Unload, keine
   überlappenden Läufe).

## Risiken

| Risiko | Wirkung | Gegenmittel |
|---|---|---|
| **Leere IdP-Antwort** (Token entzogen, Filter falsch, HTTP 200 mit `results: []`) | naiv gelesen: „alle haben die Gruppe verlassen" → im `enforce`-Modus reihenweiser Rechteverlust | R5 Plausibilitäts-Guard; leere verwaltete Menge gilt grundsätzlich als unplausibel, wenn vorher Einträge existierten |
| **Rechte-Ausweitung über eine IdP-Gruppe** | Gruppenänderung im IdP verteilt unbemerkt weitreichende Rechte | R6 (`is_admin` nie implizit), Mapping ist explizit (keine Wildcards), Monitor-Vorschau vor Enforce |
| **Namenskollision / Nutzer-Verwechslung** | falscher Nutzer bekommt Rollen | R10: exakte, case-sensitive Username-Gleichheit; Mehrfachtreffer → nicht mappen + Repairs |
| **Zweite Wahrheit** (Sync und Panel pflegen dasselbe Paar) | Flattern bei jedem Lauf | R2 Provenienz; verwaltete Paare im Panel als IdP-verwaltet kennzeichnen |
| **IdP dauerhaft weg / Sync abgeschaltet** | stiller Rechteverlust | verwaltete Einträge **bleiben** stehen, werden als „nicht mehr verwaltet" markiert; Admin übernimmt oder entfernt |
| **Token im Klartext** | Secret-Leak | R7: nur Referenz im Store; Wert über `!secret`/1Password zur Laufzeit; Diagnostics redigiert |
| **Überlappende Läufe** (Timer + manueller Service) | halb geschriebener Zustand | `mutation_lock(hass)` — derselbe Lock, der alle anderen Schreiber serialisiert |

## Architektur

```
              ┌─────────────── Authentik (SoT für Identität + Gruppe) ───────────────┐
              │  OIDC  ──►  hass-oidc-auth  ──►  HA-Login (unberührt)                │
              │  REST  ──►  GroupSource (lesend)                                     │
              └──────────────────────────────┬──────────────────────────────────────┘
                                             │  GroupMembership[]  (username → groups)
                      ┌──────────────────────▼──────────────────────┐
   Timer ───►         │  sync.py                                    │
   Service ───►       │   1 fetch      (GroupSource, read-only)     │
                      │   2 resolve    (username → HA user_id)      │
                      │   3 map        (group → role_ids)           │
                      │   4 diff       (gegen membership.managed)   │
                      │   5 plausible? (R5) ── nein ──► Repairs, Ende│
                      └──────────────────────┬──────────────────────┘
                                             │  nur eigene Paare (R2)
                      ┌──────────────────────▼──────────────────────┐
                      │  bestehender Schreibpfad (unverändert)      │
                      │   mutation_lock → set_user_membership       │
                      │   → async_save_config                       │
                      │   → _compile_for_mode_safely  (fail-safe)   │
                      └─────────────────────────────────────────────┘
                                             │
                        off/monitor: nur Store + Vorschau · enforce: nativer Write
```

Der entscheidende Schnitt liegt bei Schritt 5/6: **unterhalb davon ändert sich nichts.** Der Sync ist
ein weiterer Schreiber auf `by_user`, kein neuer Pfad in die native Auth-Schicht. Damit bleibt das
adversariale Gate der Enforce-Strecke gültig, und ADR 0005 („der Compiler projiziert `by_group`
nicht") bleibt wörtlich in Kraft: `by_group` ist die **Mapping-Regel**, keine zweite Subjekt-Quelle.

### Betriebsmodi des Sync

| Modus | fügt hinzu | entfernt | Zweck |
|---|---|---|---|
| `off` (Default) | — | — | Status quo, keine Abhängigkeit |
| `additive` | ja | nein | Übergang/Erprobung. **Sicherheitlich schwächer**: Entzug im IdP schlägt nicht durch |
| `managed` | ja | ja, nur eigene Paare | Zielmodus: Entzug schlägt durch, manuelle Einträge überleben |

## Module

Neu, unter `custom_components/tessera/group_source/`:

| Datei | Inhalt | Reinheit |
|---|---|---|
| `__init__.py` | `GroupSource`-Protokoll (`async def async_fetch() -> list[GroupMembership]`), DTO `GroupMembership(username: str, groups: frozenset[str])`, `GroupSourceError` | rein |
| `authentik.py` | read-only REST-Client gegen Authentiks API (`/api/v3/core/...`; Endpunkte und Paginierung beim Bau gegen die laufende Instanz verifizieren), Timeout, TLS-Verify an, Bearer-Token aus der Referenz | I/O |
| `mapping.py` | `resolve_roles(groups, mapping, roles) -> list[str]`, deterministisch sortiert; filtert `is_admin`-Rollen ohne Opt-in (R6); unbekannte Rollen-IDs → Fehler | rein |
| `sync.py` | `plan_sync(...) -> SyncPlan` (rein: Diff + Plausibilität) und `async_run_sync(...)` (Writer-Aufruf, Journal, Repairs) | rein + I/O getrennt |

Erweiterungen:

- `schema.py` — `membership.managed`, `config["group_source"]`, Validatoren (siehe Datenmodell)
- `__init__.py` — Service `tessera.sync_groups` (admin-only, `dry_run` optional), Timer-Registrierung
  und -Abbau beim Unload
- `services.yaml`, `strings.json`, `translations/en.json` — Service-Beschreibung (admin-only)
- `docs/GUIDE.md` / `GUIDE.de.md` — Einrichtung, Modi, Fehlerbilder

Die Trennung „rein vs. I/O" ist Absicht: Mapping, Diff und Plausibilität sind ohne HA und ohne Netz
testbar, der Client ist die einzige Stelle mit Außenkontakt.

## Datenmodell

Beides **additiv**; fehlt es, ist es leer, und alles verhält sich wie heute. Keine Migration —
`validate_config_data()` materialisiert die Felder bei jedem Laden (Annahme 5).

```python
class MembershipData(TypedDict):
    by_user: dict[str, list[str]]
    by_group: dict[str, list[str]]      # Mapping-Regel (ADR 0005), nie projiziert
    managed: dict[str, list[str]]       # NEU: Teilmenge von by_user, die dem Sync gehört


class GroupSourceConfig(TypedDict, total=False):
    enabled: bool                       # Default False
    type: str                           # "authentik"
    base_url: str                       # https://auth.pilzbuche8.de
    token_ref: str                      # 1Password-Titel + UUID / !secret-Schlüssel — NIE der Wert
    interval_minutes: int               # Default 15, Minimum 5
    mode: str                           # "off" | "additive" | "managed"
    mapping: dict[str, list[str]]       # IdP-Gruppenname -> Tessera-Rollen-IDs
    allow_admin_roles: list[str]        # explizites Opt-in je Rolle (R6)
    max_removal_ratio: float            # Default 0.34 (R5)
```

**Invariante:** `managed[user]` ⊆ `by_user[user]` für jeden Nutzer. Der Sync darf ausschließlich
Paare aus `managed` entfernen und fügt neue Paare immer in **beide** Maps ein. Ein Linter-Check
prüft die Invariante (siehe Tests).

## Fehlerfälle

| Fall | Verhalten |
|---|---|
| Netzwerk-/DNS-Fehler, Timeout | Lauf abbrechen, letzter Stand bleibt, Log auf `warning`; nach N Fehlläufen Repairs-Issue |
| HTTP 401/403 | Lauf abbrechen, **Repairs-Issue sofort** (Token ungültig/entzogen) — nie als „keine Gruppen" interpretieren |
| HTTP 200, aber leere/teilweise Antwort | Plausibilitäts-Guard (R5) greift → nicht anwenden, Repairs-Issue mit Zahlen |
| Mapping zeigt auf unbekannte Rollen-ID | ganzen Lauf verwerfen (fail-closed), Repairs-Issue mit der Rolle; **kein** Teil-Apply |
| IdP-Nutzer nicht in HA / mehrfach | diesen Nutzer **nicht** mappen, Rest läuft; Sammel-Repairs-Issue |
| Ziel ist Owner oder system-generated | `_assert_membership_target_user` wirft → Nutzer übersprungen, Rest läuft |
| Rolle mit `is_admin` ohne Opt-in | Rolle wird aus dem Ergebnis gefiltert (R6), Hinweis ins Log, Repairs-Issue einmalig |
| Compile/Apply schlägt fehl | bestehendes `_compile_for_mode_safely` → fail-safe auf `monitor` (unverändert) |
| Überlappender Lauf | zweiter Lauf wartet am `mutation_lock`; `dry_run` wartet ebenfalls |
| HA-Neustart mitten im Lauf | kein Zwischenzustand: der Store wird genau einmal geschrieben; das Zwei-Phasen-Journal der Enforce-Strecke bleibt zuständig |

## Security

- **Token:** nur Referenz im Store (R7). Wert zur Laufzeit; nie in Log, Repairs, Diagnostics oder
  Exception-Text. Minimal gescoped: **Lesen** von Nutzern/Gruppen, nichts weiter.
- **Transport:** HTTPS mit Verify an; kein Opt-out-Schalter.
- **Rechte-Richtung:** der Sync kann durch R6 keine Admin-Rechte verteilen und durch R2 keine
  manuell gesetzten Rollen entfernen. Er kann `view`/`operate` innerhalb vorhandener Rollen
  vergeben — nichts erfinden: unbekannte Rollen führen zum Abbruch, nicht zur Anlage.
- **Owner-/System-Konten** bleiben unangetastet (bestehender Guard).
- **Audit:** jede Änderung mit `source`, Gruppe, Zeitpunkt; abgelehnte Läufe mit Grund. Ein
  IdP-getriebener Rechteentzug muss im Nachhinein erklärbar sein.
- **Kein Schreibpfad nach außen:** der Client hat keine POST/PATCH/DELETE-Methoden.

## Tests

Gegen [docs/QUALITY.md](QUALITY.md) R1–R7; Tests behaupten das sichere Soll, nie das Ist.

**Rein (ohne HA, ohne Netz):**
- `mapping`: mehrere Gruppen → sortierte Rollen-Vereinigung · unbekannte Rolle → Fehler ·
  `is_admin`-Rolle ohne Opt-in wird gefiltert · mit Opt-in nicht · leere Gruppen → leere Rollen
- `plan_sync`: Hinzufügen · Entfernen nur eigener Paare · manuelles Paar bleibt · Modus `additive`
  entfernt nichts · Modus `off` plant nichts · Invariante `managed ⊆ by_user` nach jedem Plan
- `plausibility`: Entzug über `max_removal_ratio` → Plan abgelehnt · leere Antwort bei vorher
  gefüllter verwalteter Menge → abgelehnt · Grenzwert exakt → definiert (nicht „irgendwie")

**Failure-Injection am IdP-Rand, gegen einen Fake-Client.** R5 gilt wörtlich für
Native-Write-Pfade, und einen eigenen hat der Sync nicht — dieselbe Disziplin gilt hier
trotzdem, weil die Außengrenze neu ist:
- Timeout · 401 · 403 · HTTP 500 · ungültiges JSON · `results: []` · Teil-Paginierung bricht ab
  → in **jedem** Fall: kein Schreibzugriff, letzter Stand unverändert, definiertes Log/Repairs

**Integration (phcc):**
- `tessera.sync_groups` ist **admin-only** (Regressionstest, Parität zu `recompile`)
- `dry_run: true` schreibt nichts, liefert aber den Plan
- Modus `off`/`monitor`: Store wird geschrieben, **kein** nativer Write
- Nutzer gelöscht → Sync überspringt ihn, Rest läuft
- Timer wird beim Unload abgebaut (keine Läufe nach Entladen)

**Contract (gegen installiertes HA):** keine neue Datei nötig — der Sync berührt keine privaten
HA-APIs. Das ist selbst ein Akzeptanzkriterium.

## Akzeptanzkriterien

1. Mit `group_source.enabled: false` (Default) ist das Verhalten **bit-identisch** zu heute; die
   Testsuite bleibt ohne Änderung grün.
2. Compiler, Bindings, Lockout-Precheck, Restore und Auth-Adapter sind **unverändert** (Diff zeigt
   keine Zeile in `compiler.py`, `auth_adapter.py`, `restore.py`).
3. `managed ⊆ by_user` gilt nach jedem Lauf, auch nach abgebrochenem.
4. Kein Token-Wert in Store, Log, Diagnostics oder Repairs — per Secret-Scan belegt.
5. Jeder Fehlerfall aus der Tabelle hat einen Test, der das sichere Soll behauptet.
6. `off` und `monitor` schreiben nachweislich nicht nativ.
7. `ruff`, `black`, `mypy --strict` und die Contract-Matrix (vier Linien) bleiben grün.
8. Welle 5 ist durch **zwei unabhängige Reviews** gegangen (QUALITY R7) — der Sync kann ab dort
   Rechte vergeben, das ist eine sicherheitskritische Änderung.

## Umsetzungsschritte

| Welle | Inhalt | Gate |
|---|---|---|
| **1** | `schema.py`: `membership.managed` + `group_source` additiv und **inert** (niemand liest sie) | Schema-Tests, Default-Verhalten unverändert |
| **2** | `group_source/__init__.py` + `mapping.py` (rein, vollständig getestet), noch ohne Netz | Gate-Review |
| **3** | `authentik.py` (read-only Client) + Failure-Injection-Tests gegen Fake-Transport | Gate-Review, Secret-Scan |
| **4** | `sync.py` `plan_sync` + Plausibilität, Service `tessera.sync_groups` **nur** `dry_run` | Gate-Review |
| **5** | Writer hinter `enabled` + `mode`, Journal, Repairs | **zwei unabhängige Reviews (QUALITY R7)** + Dev-Instanz-E2E — ab hier kann der Sync Rechte vergeben |
| **6** | Timer + Unload, Doku (GUIDE EN/DE), ADR zur Richtungsfrage | Gate-Review, Doku-Diff |

Die Richtungsfrage (`additive` vs. `managed` als Default, und ob Authentik SoT für die verwalteten
Paare ist) gehört **vor Welle 5** in einen ADR — sie ist eine Produktentscheidung, keine technische.

## Erste Codex-Aufgabe

**Aufgabe:** Welle 1 — `membership.managed` und `config["group_source"]` additiv und inert ins
Schema einführen.

**Betroffene Dateien:** `custom_components/tessera/schema.py`, `tests/test_schema.py`.

**Regeln / was nicht ändern:**
- `compiler.py`, `auth_adapter.py`, `restore.py`, `monitor.py`, `store.py` **nicht anfassen**.
- Niemand liest die neuen Felder in dieser Welle (inert, wie `by_group` und `staging`).
- Keine Migration: `validate_config_data()` materialisiert die Felder beim Laden; fehlen sie im
  gespeicherten Payload, sind sie leer bzw. `enabled: False`.
- `MembershipData` bleibt `total=True`; `managed` wird im Validator **immer** erzeugt.
- Unbekannte Schlüssel weiterhin verwerfen (bestehendes Verhalten nicht lockern).

**Erwartete Umsetzung:**
- `MembershipData` um `managed: dict[str, list[str]]` erweitern; im Validator über
  `_validate_membership_map(membership_raw.get("managed"), "config.membership.managed")`.
- `GroupSourceConfig` als `TypedDict(total=False)` ergänzen, `TesseraConfigData` um
  `group_source: GroupSourceConfig`; Validator mit engen Prüfungen: `enabled`/`mode` gegen eine
  feste Menge, `interval_minutes >= 5`, `0 < max_removal_ratio <= 1`, `mapping`-Werte sind
  bekannte-Form-Rollen-IDs (Existenz wird hier **nicht** geprüft — das ist Welle 4), `token_ref`
  ist ein nicht-leerer String und wird **nicht** interpretiert.
- `default_config_data()` liefert `membership.managed = {}` und `group_source = {"enabled": False}`.

**Tests:**
- Altes Payload ohne beide Felder lädt und bekommt leere Defaults.
- `managed` mit Fremd-Typen → `TesseraSchemaError` (pro Feld ein Fall).
- `interval_minutes: 1`, `max_removal_ratio: 0`, `max_removal_ratio: 1.5`, `mode: "nope"` → Fehler.
- Ein `token_ref` wird unverändert durchgereicht und **nirgends** interpretiert.
- Round-Trip: validieren → speichern → laden ergibt denselben Payload.

**Definition of Done:** `ruff`, `black`, `mypy --strict` grün; vollständige Suite grün; keine Zeile
Diff außerhalb der beiden genannten Dateien; Secret-Scan sauber.

**Abschlussbericht:** geänderte Dateien · Zusammenfassung · Tests + Ergebnis · Risiken/Annahmen.
