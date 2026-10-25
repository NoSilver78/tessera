# HA-Berechtigungssystem: Stand 2026.11 (`dev`) · Authentik-Einbindung

Review · Claude · 2026-10-25 · Auslöser: „ändert sich etwas am Rechtesystem, und wie binden wir
Authentik am besten ein?" (vor dem Commit der v0.9.5-Arbeit)

Geprüft gegen **2026.8.1** (letzte Linie vor der Umstellung), **2026.10.4** (aktuelles Stable,
= `rc`) und **`dev` @ 2026.11.0.dev0**. Ein 2026.11-Beta existiert noch nicht.

---

## 1. Ändert sich etwas am Berechtigungs-/Rechtesystem? Nein.

Der Dateisatz von `homeassistant/auth/` ist über alle drei Stände identisch
(`__init__.py`, `auth_store.py`, `const.py`, `jwt_wrapper.py`, `models.py`, `mfa_modules/`,
`permissions/`, `providers/`).

| Was | 2026.8.1 → `dev` |
|---|---|
| `auth/auth_store.py` | **byte-identisch** |
| `auth/const.py` | **byte-identisch** |
| `auth/permissions/const.py` | **unverändert**: `CAT_ENTITIES`, `CAT_CONFIG_ENTRIES`, `SUBCAT_ALL`, `read`/`control`/`edit` |
| `auth/permissions/system_policies.py` | **unverändert**: `ADMIN_POLICY = USER_POLICY = {entities: True}`, `READ_ONLY_POLICY = {entities: {all: {read: True}}}` |
| `auth/permissions/{events,merge,models,types,util}.py` | **unverändert** |
| `auth/permissions/entities.py` | geändert in **2026.9** (effektive Geräte-Area, Child-Devices) — seit 2026.10.4 → `dev` wieder byte-identisch |
| `auth/permissions/__init__.py` | geändert in **2026.10**: `voluptuous` → `probatio` (Import-Zeile, gleiche Schema-Shape) |
| `auth/models.py` | geändert in **2026.10**: PKCE-Felder am `AuthFlowContext` (Login-Flow), `models.Group` unverändert |

**Das Modell selbst steht also unverändert:** drei Systemgruppen, Owner-Bypass, allow-only
Entity-Policies, keine Rollen, keine Bereichs-Scopes, `change`/`is_admin` global. Für 2026.11 ist
bislang **nichts** am Policy-Schema geändert.

### Drei Beobachtungen, die wichtiger sind als die Diffs

1. **Es gibt weiterhin keine öffentliche API, um Gruppen zu schreiben.** `AuthStore` und
   `AuthManager` bieten nur **lesend** `async_get_group` / `async_get_groups`; die
   WebSocket-Kommandos in `components/config/auth.py` sind `list`/`create`/`update`/`delete` für
   **User**, nicht für Gruppen. Tesseras privater Schreibpfad bleibt damit der einzige Weg — die
   Abhängigkeit verschwindet nicht, und die Strategie „Guard + Diff-Protokoll + Contract-Tests pro
   Linie" ist nicht Übergangslösung, sondern Dauerzustand. Richtig investiert.
2. **Wo HA tatsächlich arbeitet, ist der Credential-/Provider-Pfad, nicht das Rechtemodell.**
   2026.10 härtet das Löschen von Nutzern (Owner nicht löschbar, Refresh-Tokens werden beim Löschen
   widerrufen). `dev` ergänzt `DuplicateCredentialsError` und initialisiert Auth-Provider jetzt
   fault-isoliert (`asyncio.gather(..., return_exceptions=True)`, Fehler wird geloggt statt den
   Start zu reißen). Beides ist genau die Ecke, die eine IdP-Anbindung berührt — ein defekter
   Dritt-Auth-Provider nimmt ab 2026.11 nicht mehr alle Login-Wege mit.
3. **`EVENT_USER_REMOVED` existiert** und wird z. B. von der `person`-Integration konsumiert.
   Tessera hört heute nicht darauf: wird ein HA-Nutzer gelöscht, bleibt sein Eintrag in
   `membership.by_user` als Waise stehen (die Bindings-Schicht erkennt Waisen, aber der Store wird
   nicht aufgeräumt). Kleiner, klar begrenzter Fix — gehört in den Backlog, nicht in dieses Release.

---

## 2. Authentik einbinden

### Die Ausgangslage hat sich nicht verschoben

ADR [0005](../../decisions/0005-by-group-v1-inert.md) hat `membership.by_group` als **v1-inert**
festgelegt, weil (a) HA-Core keinen OIDC-Provider hat und (b) kein At-Login-Claim-Hook existiert.
Beides gilt unverändert: `auth/providers/` enthält über alle drei Stände nur `homeassistant`,
`command_line`, `trusted_networks`, `insecure_example`. Es gibt in 2026.11 **keinen** nativen
OIDC-/OAuth-Login und keinen Hook, der einem Custom-Component den `groups`-Claim eines fremden
Providers zustellt.

Die Blockade von D12 war damit nie „Authentik geht nicht", sondern: **„der Claim kommt nicht bei uns
an."** Das ist eine Aussage über den *Transportweg*, nicht über die Datenquelle.

### Vier Wege, bewertet

| Weg | Wie | Urteil |
|---|---|---|
| **A — Status quo** | Authentik authentifiziert (Proxy/Forward-Auth + Header-Component), Tessera autorisiert pro **lokalem HA-Nutzer** (`by_user`) | Funktioniert heute, ohne jede Abhängigkeit. Aber: Rollenpflege bleibt manuell, zweite Wahrheit neben Authentik |
| **B — Pull aus Authentiks API** ⭐ | Ein Sync holt Gruppen-Mitgliedschaften aus Authentiks REST-API (`/api/v3/core/...`, Endpunkte beim Bau gegen die laufende Instanz verifizieren), mappt Authentik-Gruppe → Tessera-Rolle und schreibt das Ergebnis in `by_user` | **Empfehlung.** Braucht den fehlenden Claim-Hook **gar nicht**: wenn die Mitgliedschaft aus der API kommt, ist der Login-Seitenkanal irrelevant |
| **C — Push aus Authentik** | Authentik-Notification/Webhook → HA-Webhook → `tessera.set_membership` | Guter Beschleuniger *neben* B (Latenz von Minuten auf Sekunden), aber allein unzureichend: kein Reconcile, entzogene Mitgliedschaften können still ausbleiben |
| **D — Claim beim Login** | Header-/Claim-Auth-Component liefert `groups` beim Login | Dritt-Component in der Login-Strecke, Zustand nur bei Login aktuell, und genau der Weg, den ADR 0005 als unbewiesen eingestuft hat. Nicht empfohlen |

### Warum B so gut passt

Der entscheidende Punkt ist, **wohin** der Sync schreibt: nach `membership.by_user`. Damit bleibt
die Enforce-Strecke exakt die bereits gegatete — Compiler, Bindings, Lockout-Precheck, Restore sehen
weiterhin nur `by_user` → Rolle. **Kein neuer Projektionspfad, kein Re-Gate des
sicherheitskritischen Codes.** `by_group` bleibt, was es im Schema schon ist: die *Mapping-Regel*
(Authentik-Gruppe → Rolle), nicht eine zweite Subjekt-Quelle. ADR 0005 muss dafür nicht widerrufen
werden — sein Guard („Compiler projiziert `by_group` nicht") bleibt wörtlich in Kraft.

### Entwurf (noch nicht gebaut)

- **Konfiguration:** `authentik_sync` im Config-Store — Basis-URL, Token-Referenz, Mapping
  `{authentik_group: [role_id, ...]}`, Intervall. **Kein Token-Wert im Store**: Referenz auf
  1Password (Titel + UUID), Wert zur Laufzeit über die HA-Secrets/`!secret`-Strecke.
- **Identitäts-Brücke:** Authentik-Nutzer → HA-Nutzer. Sicherer Weg: Matching über die bereits
  verknüpften Credentials (`username`/`sub`), **nie** über E-Mail-Heuristik; was sich nicht eindeutig
  zuordnen lässt, wird **nicht** gemappt und als Repairs-Issue sichtbar.
- **Fail-closed, wie überall hier:** IdP nicht erreichbar oder Antwort unplausibel → **letzter
  bekannter Stand bleibt**, niemals Ausweitung, niemals implizites Entziehen ohne Beleg. Gruppen, die
  auf eine Rolle mit `is_admin` zeigen, brauchen eine **explizite** Opt-in-Bestätigung (eine
  IdP-Gruppenänderung darf nicht unbemerkt HA-Admin verteilen).
- **Nachvollziehbarkeit:** jede Änderung mit Provenienz (`source: authentik`, Gruppe, Zeitpunkt) ins
  Journal; Vorschau im Monitor-Modus, bevor etwas durchgesetzt wird — der gleiche monitor-first
  Ablauf wie beim Rest.
- **Reihenfolge:** (1) read-only Sync, der nur eine Vorschau erzeugt → (2) Schreiben nach `by_user`
  hinter einem eigenen Schalter → (3) optional Webhook (C) als Beschleuniger.

### Was vorher geklärt sein muss

1. **Welche Authentik-Anbindung läuft bei dir real?** Forward-Auth/Proxy mit Header-Component, oder
   nur Authentik als Login-Portal vor HA? Davon hängt ab, ob HA-Nutzer überhaupt automatisch
   entstehen und wie sie heißen.
2. **Ein Token mit Leseberechtigung** auf Gruppen/Nutzer in Authentik — minimal gescoped.
3. **Die Richtungsfrage:** soll Authentik die *Source of Truth* für Mitgliedschaft werden (dann
   gewinnt der Sync und manuelle `by_user`-Einträge werden überschrieben) oder nur eine *additive*
   Quelle (Union, nichts wird entzogen)? Das ist eine Produktentscheidung, keine technische —
   und sie gehört in einen ADR, bevor Code entsteht.

---

## Fazit

Am Rechtesystem von Home Assistant ändert sich **nichts** — weder in 2026.10 noch in der
Vorschau auf 2026.11. Es gibt weiterhin keine öffentliche Gruppen-API und keinen OIDC-Provider,
also bleibt Tesseras Ansatz richtig und die Versions-Wachsamkeit notwendig. Für Authentik ist der
sinnvolle Weg nicht der blockierte Claim-Hook, sondern ein **Pull aus Authentiks API, der nach
`by_user` schreibt** — damit wird aus einem blockierten Feature ein additiver Baustein, ohne die
gegatete Enforce-Strecke anzufassen.

---

## Nachtrag: Hängt Tessera dann an Authentik?

Rückfrage Michael: *„Wenn Authentik Source of Truth wird — funktioniert Tessera dann auch nur noch
mit Authentik?"*

**Nein — und zwar nicht aus Kulanz, sondern weil die Reichweite der SoT-Aussage falsch gesetzt war.**
Die ROADMAP-Vision sagt ausdrücklich „ohne Zwang zu einem bestimmten Identity-Provider", und ADR
0005 nennt die Dependency-Freiheit von `by_user` eine *harte Vorgabe*. Ein Modus, der Authentik zur
Voraussetzung macht, wäre ein Bruch mit beidem. Es gibt auch keinen technischen Grund dafür.

### Die SoT-Frage ist nicht global, sondern pro Eintrag

Durchgesetzt wird immer nur `membership.by_user`. Der Sync ist einer von mehreren **Schreibern** auf
diese Map — nicht ihr Eigentümer. Entscheidend ist deshalb nicht „wer ist SoT?", sondern **„welche
Einträge besitzt der Sync?"**:

- Jedes `(user, role)`-Paar bekommt eine **Provenienz**. Der Sync darf ausschließlich Paare anfassen,
  die ihm gehören (`source: authentik`); von Hand, per Service oder Panel gesetzte Paare bleiben
  unberührt.
- Eine Instanz **ohne** Authentik hat keinen konfigurierten Sync → es gibt keine fremden Einträge, und
  alles verhält sich exakt wie heute. Tessera bleibt **standalone-first**.
- Eine Instanz **mit** Authentik mischt beides: IdP-gepflegte Rollen für die Nutzer in gemappten
  Gruppen, lokale Rollen für alle anderen (Gäste, Dienstkonten, der Admin selbst).

### Drei Modi statt „SoT oder additiv"

| Modus | Sync fügt hinzu | Sync entfernt | Urteil |
|---|---|---|---|
| **off** (Default) | — | — | Status quo, keine Abhängigkeit |
| **additiv** | ja | **nein** | Klingt harmlos, ist aber die schlechtere Sicherheitswahl: wer aus der Authentik-Gruppe entfernt wird, behält seine Rechte. Ein IdP, dessen Entzug nicht durchschlägt, ist eine halbe Integration |
| **managed** ⭐ | ja | ja, **nur eigene Einträge** | Entzug schlägt durch (der eigentliche Zweck eines IdP), manuelle Einträge überleben, ohne Authentik bricht nichts |

Damit beantwortet sich die ursprüngliche Richtungsfrage anders als gestellt: nicht „SoT **vs.**
additiv", sondern **„SoT für den Bereich, den der Sync verwaltet"**.

### Was beim Abschalten oder Ausfall passiert

- **Authentik unerreichbar:** letzter bekannter Stand bleibt stehen, keine Ausweitung, kein Entzug
  ohne Beleg. Tessera setzt weiter durch, was zuletzt gültig war.
- **Plausibilitäts-Guard (wichtig):** ein Token-Entzug oder ein Filter-Fehler kann eine *erfolgreiche*
  Antwort mit **leerer** Gruppenliste liefern. Eine naive Umsetzung würde daraus „alle haben die
  Gruppe verlassen" ableiten und im `enforce`-Modus reihenweise Rechte abräumen. Ein Sync-Ergebnis,
  das mehr als einen konfigurierten Anteil der verwalteten Mitgliedschaften entfernt, wird daher
  **nicht angewandt**, sondern als Repairs-Issue zur Bestätigung vorgelegt.
- **Sync dauerhaft abgeschaltet:** die bisher verwalteten Einträge **bleiben** (kein stiller
  Rechteverlust) und werden als „nicht mehr verwaltet" markiert — der Admin übernimmt sie als manuell
  oder entfernt sie. Deinstallieren von Authentik kostet also keine Konfiguration.

### Schema-Kosten: minimal

`by_user` ist heute `dict[user_id, list[role_id]]`, und `validate_config_data` **pickt** bekannte
Schlüssel (`membership_raw.get("by_user")` / `.get("by_group")`) statt unbekannte abzulehnen. Eine
dritte, gleich geformte Map — z. B. `membership.managed` als die Teilmenge der `by_user`-Paare, die
dem Sync gehören — ist damit **rein additiv**: fehlt sie, ist sie leer, und alles gilt als manuell.
Keine Migration, kein Bruch, und dieselbe „additiv und zunächst inert"-Mechanik, mit der `by_group`
und `staging` schon im Schema liegen.

---

## Nachtrag 2: Wie die Live-Instanz heute an Authentik hängt

Gelesen (read-only) in `/Volumes/config`.

### Der Ist-Stand

**SSO läuft schon — über echtes OIDC, nicht über Header-Proxy.** `configuration.yaml` konfiguriert
die HACS-Integration **`hass-oidc-auth` v1.2.1** (Domain `auth_oidc`, `@christiaangoossens`) gegen
Authentik:

| | |
|---|---|
| Discovery | `https://<authentik-host>/application/o/home-assistant/.well-known/openid-configuration` |
| User-Linking | `automatic_user_linking: true`, Username-Claim **`preferred_username`** → gleichnamige HA-Benutzer |
| Person-Anlage | `automatic_person_creation: true` |
| Groups-Claim | `claims.groups: "groups"` (Scope `groups` wird mit angefragt) |
| Rollen-Mapping | `roles.admin: "authentik Admins"` |
| Fallback | lokaler `ha-admin`-Login bleibt |
| Netz | hinter Reverse-Proxy und Cloudflare-Tunnel, `use_x_forwarded_for` + `trusted_proxies` gesetzt |

Tessera selbst liegt ebenfalls auf dieser Instanz (`custom_components/tessera`).

### Der entscheidende Befund: der Claim ist da — er wird nur nicht geteilt

`tools/oidc_client.py` liest den `groups`-Claim (aus `id_token`, ersatzweise aus `userinfo`) und
leitet daraus **genau einen** Wert ab:

```
role = "invalid"
if self.user_role in groups or self.user_role is None:  role = "system-users"
if self.admin_role in groups:                           role = "system-admin"
```

Zurückgegeben wird dann ausschließlich `{sub, display_name, username, role}` — **die Gruppenliste
wird verworfen.** Sie landet in keinem Store, es gibt kein Event, und `provider.py` benutzt `role`
nur noch als `UserMeta(group=role)`.

Damit ist Option **D** („Claim beim Login") für diese Instanz nicht theoretisch, sondern **belegt
versperrt**: der At-Login-Hook *existiert* hier sogar, aber er gibt nichts heraus. Tessera käme nur
über einen Patch an der HACS-Integration heran (wird beim nächsten Update überschrieben) oder über
ein Upstream-Feature. ADR 0005 bleibt also richtig — mit einer genaueren Begründung als damals.

### Gute Nachricht für den Pull-Entwurf

Die Identitäts-Brücke, die ich im Hauptteil noch als Risiko markiert hatte, ist hier **trivial und
deterministisch**: Authentik liefert `preferred_username`, HA linkt darüber, und die HA-Benutzer
heißen genau so. Kein E-Mail-Matching, keine Heuristik — der Sync kann
Authentik-Nutzer direkt über denselben Namen auf HA-Nutzer abbilden. Was fehlt, ist nur ein
**Authentik-API-Token** (der OIDC-Client-Secret ist keines) — minimal gescoped auf Lesen von
Nutzern/Gruppen, Wert nach Hausregel ausschließlich in 1Password (`Pilzbuche8`), im Store nur die
Referenz.

### Kollisions-Check: überschreibt ein SSO-Login Tesseras Bindings?

**Nein** — in HAs `auth/__init__.py` (gegen `dev` geprüft) gilt:

- `async_get_or_create_user()` kehrt bei `credentials.is_new == False` **sofort mit dem bestehenden
  Nutzer zurück**; es werden keine Gruppen neu gesetzt.
- `group_ids=[GROUP_ID_ADMIN if info.group is None else info.group]` steht **nur** im
  Erzeugungspfad.

Ein OIDC-Login eines bereits verknüpften Nutzers lässt dessen `tessera:<rolle>`-Gruppen also in
Ruhe. Nur ein **neu** angelegter SSO-Nutzer landet zunächst in `system-users`/`system-admin` und
wird erst beim nächsten Enforce-Lauf umgebunden. Das ist kein Fehler, aber ein Zeitfenster — und
HA feuert bei der Anlage `EVENT_USER_ADDED` (Zeile 306). Darauf zu hören wäre ein kleiner, klar
begrenzter Gewinn (Gegenstück zu `EVENT_USER_REMOVED` aus Abschnitt 1).

> Auf dem Papier geprüft, nicht gefahren: ein echter Erst-Login über Authentik gegen
> **`ha-tessera-dev`** sollte das bestätigen, bevor sich jemand darauf verlässt.

### Eine Grenze, die man kennen muss

`roles.admin: "authentik Admins"` bedeutet: **HA-Admin wird heute schon von Authentik entschieden.**
Genau dort ist Authentik bereits Source of Truth — und genau dort liegt Tesseras Stufe `change`
(= `is_admin`, global, nicht bereichs-scoped). Eine Tessera-Rolle mit `is_admin` und das
OIDC-Admin-Mapping können sich also widersprechen. Für den Sync heißt das: **Admin-Vergabe bleibt
beim IdP**, Tessera verwaltet `view`/`operate` — und eine Authentik-Gruppe darf nie *über Tessera*
zu `is_admin` führen, ohne dass das explizit bestätigt wurde.

### „Gibt es inzwischen Besseres?"

Kurz: **nein, der Weg ist der richtige.** HA-Core hat bis einschließlich `dev` (2026.11) keinen
eigenen OIDC-Provider — `auth/providers/` enthält nur `homeassistant`, `command_line`,
`trusted_networks`, `insecure_example`. Damit bleibt eine Custom-Integration die einzige Option für
echtes SSO, und `hass-oidc-auth` ist die gepflegte (v1.2.1, aktiver Codeowner).

Die Alternative — Forward-Auth/Proxy mit Header-Component — wäre hier ein **Rückschritt**: kein
echter Login-Flow, und die Sicherheit hängt daran, dass der Header nirgends gefälscht werden kann.
Die bestehende Lösung ist sauberer.

Erwähnenswert ist nur eine Verbesserung *am Rand*: HA `dev` initialisiert Auth-Provider künftig
fault-isoliert (ein defekter Provider reißt nicht mehr alle Login-Wege mit) — für ein Setup mit
Dritt-Provider plus lokalem Fallback eine echte Verbesserung, die mit 2026.11 von selbst kommt.

**Die Lücke liegt also nicht beim Login, sondern zwischen Gruppe und Rolle** — und genau die
schließt der Pull-Sync aus dem Hauptteil.

---

## Nachtrag 3: Eigene OIDC-Schnittstelle in Tessera?

Rückfrage Michael: *„Was verwenden wir heute als OIDC-Schnittstelle, und macht es Sinn, das in
Tessera selbst zu integrieren — also eine eigene Schnittstelle an Authentik?"*

### Was heute die Schnittstelle ist

`hass-oidc-auth` ist ein vollwertiger **HA-Auth-Provider**: `@AUTH_PROVIDERS.register("oidc")` auf
einer `AuthProvider`-Subklasse, dazu vier HTTP-Views (Redirect, Callback, Finish, Device-SSE) und
ein eigener State-Store für die laufenden Flows. Eingehängt wird er in `__init__.py` so:

```
provider = OpenIDAuthProvider(hass, hass.auth._store, my_config)
existing_auth_providers = hass.auth._providers.copy()
...
hass.auth._providers = providers        # neu gesetzt, OIDC nach vorn sortiert
```

Also: **`hass.auth._store` und `hass.auth._providers` direkt** — zwei private Attribute, plus das
Umsortieren der Provider-Reihenfolge, damit der OIDC-Login zuerst erscheint.

### Antwort: ja zur Schnittstelle, nein zum Login

**Den OIDC-Login sollte Tessera nicht übernehmen.** Vier Gründe, in der Reihenfolge ihres Gewichts:

1. **Schadensradius.** Tesseras ganze Sicherheitsgeschichte ist *fail-safe auf `monitor`*: wenn
   etwas schiefgeht, verliert man die Durchsetzung — **nie den Zugang**. Ein Auth-Provider dreht das
   um: ein Fehler sperrt alle aus. Dass auf der Instanz bewusst ein lokaler `ha-admin`-Fallback
   steht, zeigt, dass genau dieses Risiko schon einmal durchdacht wurde.
2. **Eine zweite Private-API-Abhängigkeit, an der schlimmstmöglichen Stelle.** Tessera hat heute
   *eine* (`AuthStore`-Schreibpfad), und was sie kostet, ist in diesem Release nachzulesen: Guard,
   Diff-Protokoll, Contract-Tests und `mypy` pro Linie, Nightly. Ein eigener Provider bedeutet
   `hass.auth._providers` **und** `hass.auth._store` **im Login-Pfad** — dieselbe Wartung, doppelt,
   an der kritischsten Stelle.
3. **Es widerspricht der eigenen Architektur.** Tessera ist PAP/PDP/PEP (NIST SP 800-162);
   Authentifizierung kommt in dieser Kette nicht vor. Die ROADMAP-Vision sagt ausdrücklich „ohne
   Zwang zu einem bestimmten Identity-Provider" — ein eigener OIDC-Login wäre genau dieser Zwang.
4. **Es gäbe nichts zu gewinnen.** `hass-oidc-auth` ist gepflegt (v1.2.1, aktiver Codeowner) und
   funktioniert. Zwei Integrationen, die beide `hass.auth._providers` umschreiben wollen, wären ein
   Konflikt, und für die HACS-Aufnahme wäre ein Auth-Provider im RBAC-Produkt ein deutlich härterer
   Verkauf als das, was gerade durch den Review gegangen ist.

**Eine eigene Schnittstelle an Authentik ist trotzdem richtig — nur auf der Datenebene.** Die
Trennung, auf die es ankommt:

| Ebene | Wer | Tessera? |
|---|---|---|
| **Login** (wer ist das?) | Authentik + `hass-oidc-auth` | **nein** — Finger weg vom Login-Pfad |
| **Identität→Gruppe** (wo gehört er hin?) | Authentik | nein, das ist IdP-Hoheit |
| **Gruppe→Rolle→Rechte** (was darf er?) | — *heute Lücke* | **ja, genau hier** |

Konkret also der Pull-Sync aus dem Hauptteil, und zwar bewusst als **generischer „Group Source"**
mit Authentik als erster Implementierung (LDAP, Keycloak, ein simpler Webhook könnten folgen). Die
Naht generisch zu halten kostet jetzt fast nichts und verhindert, dass sich eine
Authentik-Spezifität ins Schema frisst — dieselbe Vision-Zeile wie oben.

**Ergänzend, nicht ersatzweise:** ein kleines Upstream-Feature für `hass-oidc-auth` — den
`groups`-Claim nach dem Login *herausgeben* (Event oder „last known groups" pro Nutzer) statt ihn
zu verwerfen. Das wäre ein schlanker PR, nützt auch anderen, und würde den Sync ergänzen: Event =
kurze Latenz, Pull = Wahrheit und Reconcile. Scheitert der PR, trägt der Pull allein.
