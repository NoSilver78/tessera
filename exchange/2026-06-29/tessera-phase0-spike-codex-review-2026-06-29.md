# Tessera Phase-0 Spike - Codex Review / Umsetzungsfreigabe

Stand: 2026-06-29 00:55 Europe/Berlin  
Gelesen: `outputs/tessera-phase0-spike-auftrag-2026-06-29.md`, `outputs/tessera-konzept-2026-06-29.md`, `outputs/warden-claude-response-codex-review-2026-06-29.md`  
Validierung: read-only gegen Dev-Container `ha-tessera-dev`, read-only Strukturprobe gegen `/Volumes/config`, keine Secretwerte ausgegeben, keine Aenderung an `/Volumes/config`, nicht gepusht.

## 1. Gesamturteil

**MODIFY, aber mit Go fuer die Phase-0-Spike-Implementierung nach Preflight.**

Der Auftrag ist fachlich richtig geschnitten: Tessera baut nicht sofort ein Produkt, sondern prueft zuerst den einen harten Risikokern - native HA-`PolicyPermissions` als Enforcement-Projektion und den privaten Auth-Store-Schreibpfad. Das ist die richtige Reihenfolge.

Ich wuerde die Implementierung uebernehmen, **aber nicht blind im aktuellen Dev-Zustand starten**. Vor dem ersten Auth-Write braucht es drei Vorbedingungen:

1. **Dev-Instanz eindeutig sauber:** entweder frisches Volume oder bewusst finalisiertes Onboarding. Aktuell meldet `/api/onboarding` im Container alle Schritte `done:false`, waehrend `/config/.storage/auth` bereits `1` User, `3` Gruppen und `1` Refresh-Token enthaelt. Das ist fuer einen reproduzierbaren Auth-Spike ein schmutziger Zwischenzustand.
2. **In-process Harness statt externem `docker exec python -c`:** D1-D5 muessen im laufenden HA-Prozess gegen `hass.auth` laufen. Ein separater Python-Prozess beweist weder Cache-Invalidierung noch Live-User-Verhalten.
3. **Explizite Go/No-Go-Rubrik:** Die 12 DoD sind gut, aber noch keine Entscheidungslogik. Am Ende muss eindeutig feststehen, welche PASS/PARTIAL/FAIL-Kombination Enforce erlaubt, v1-Scope reduziert oder No-Go ausloest.

Kurz: **Spike ja. Produktbau nein. Enforce-Architektur erst nach bestandenen P0-Daten.**

## 2. Eigene Kontrollbefunde

- `ha-tessera-dev` laeuft mit Image `ghcr.io/home-assistant/home-assistant:2026.6.4`, Port-Mapping `8124 -> 8123`.
- Innerhalb des Containers laeuft `python3 -m homeassistant --config /config`.
- Container-intern antwortet `http://127.0.0.1:8123/api/onboarding` mit allen Onboarding-Schritten `done:false`.
- `/config/.storage/auth` existiert bereits und enthaelt strukturell `1` User, `3` Gruppen, `1` Refresh-Token. Es wurden keine Tokenwerte gelesen oder ausgegeben.
- `/Volumes/config/custom_components` enthaelt read-only gezaehlt `14` Custom-Component-Verzeichnisse; `8` davon haben `services.yaml`: `browser_mod`, `dreame_vacuum`, `epex_spot`, `gruenbeck_cloud`, `solarman`, `solcast_solar`, `unifi_insights`, `unifi_network_map`.
- Unter `/Volumes/config/dashboards` wurden read-only `11` YAML-Dateien gezaehlt. Falls die Konzeptzahl `15` Dashboards meint, muss D9/Dashboard-Test den Suchpfad explizit machen.

## 3. Befunde mit Schwere

### P0 - Dev-Preflight ist nicht sauber genug

Der Container ist da, aber nicht spike-ready. Der Auth-Store ist nicht leer, Onboarding ist nicht abgeschlossen, und damit ist unklar, ob wir einen frischen Testzustand oder ein halb initialisiertes Volume messen.

**Risiko:** D1-D5 koennen falsch positiv oder falsch negativ werden, weil vorhandene Gruppen/User/Refresh-Tokens den Startzustand kontaminieren.

**Empfehlung:** Vor Start eine harte Preflight-Datei erzeugen lassen:

- HA-Version exakt `2026.6.4`
- Onboarding abgeschlossen oder Volume bewusst frisch reset
- Testuser vorhanden: `test-owner`, `test-admin`, `test-user`, `test-ro`
- non-admin LLAT vorhanden, aber Wert nie im Report
- Seed-Inventory deterministisch dokumentiert
- Auth-Snapshot vor Write erstellt
- Abbruch, wenn diese Checks nicht gruen sind

### P0 - D1-D5 brauchen einen In-process Harness

Die Zeile im Auftrag, D1-D5 per `docker exec ha-tessera-dev python -c "..."` zu fahren, ist nur dann tragfaehig, wenn dadurch Code im laufenden HA-Prozess ausgeloest wird. Ein normaler `docker exec` startet einen zweiten Python-Prozess ohne Zugriff auf das Live-`hass`-Objekt.

**Risiko:** Direkte `.storage/auth`-Manipulation wuerde Restart-Survival testen, aber nicht HA-Cache, `User.permissions`, laufende Gruppenobjekte oder `async_update_user`.

**Empfehlung:** Dev-only Custom-Integration `custom_components/tessera_spike` mit minimalen Services/WS-Kommandos:

- `tessera_spike.ensure_group`
- `tessera_spike.set_group_policy`
- `tessera_spike.set_user_groups`
- `tessera_spike.flush_auth_store`
- `tessera_spike.invalidate_user`
- `tessera_spike.snapshot`
- `tessera_spike.restore`
- `tessera_spike.probe_check_entity`

Diese Harness ist nicht Tessera und nicht HACS-Produktcode. Sie ist ein Messinstrument und muss nach dem Spike entfernbar sein.

### P0 - Entscheidungsrubrik fehlt

Der Auftrag fordert Go/No-Go und Fork-vs-Neubau, definiert aber nur Einzel-DoD. Das reicht fuer Messung, nicht fuer Entscheidung.

**Empfehlung fuer die Rubrik:**

- **Go fuer v1-Enforce:** D1, D2, D4, D5, D10, D11 PASS; D3/D6 PASS fuer getestete entity-targeted Pfade; D7/D8 als dokumentierte Leak-Matrix; D12 PASS oder `by_group` explizit v1-inert.
- **No-Go fuer Enforce:** kein deterministischer Persist+Restart+Cache-Pfad; Rescue haengt vom gesunden Tessera-Code ab; HA-Version-Gate kann umgangen werden; `group_ids`-Restore ist nicht vollstaendig.
- **Scope-Reduktion:** D7/D8/D12 FAIL fuehrt nicht automatisch zu No-Go, sondern zu engerem Produktversprechen: `operate/control` ja, harte `view`-Vertraulichkeit nein; `by_group` raus aus v1-Enforce.
- **Architektur:** Neubau Tessera bleibt Default; ACM nur Schreibpfad-Orakel, kein Produktfundament.

### P1 - D6/D7/D9 muessen haerter messbar werden

D6/D7/D9 sind richtig, aber noch zu weich:

- D6 braucht zusaetzlich WS-Service-Response-Vergleich, nicht nur REST `return_response`.
- D6 muss Systemkontext-Pfade abpruefen: Automation/Script/Assist/Tool-Calls mit `user_id=None` oder weitergereichtem User-Kontext.
- D7 darf nicht nur `config/entity_registry/list` pruefen, sondern Registry-Reads fuer `entity`, `device`, `area`, `floor`, `label`, `category`.
- D9 darf nicht bei "Allowlist-Kandidaten" stehenbleiben. Ergebnis je Custom Component: `ALLOW`, `DENY`, `TIER-2`, `UNKNOWN_BLOCK_ENFORCE`.

**Warum:** Home Assistant dokumentiert selbst, dass Entity-Component-Services automatisch Permission-Checks bekommen, eigene Service-Handler aber selbst korrekt mit User-Kontext pruefen muessen. Damit gibt es keinen universalen Service-Interceptor, auf den Tessera sich verlassen kann.

### P1 - Konzeptdokument enthaelt noch alte Widersprueche im Body

`tessera-konzept-2026-06-29.md` korrigiert in Abschnitt 11 viele Punkte sauber, aber der kanonische Body ist noch nicht ueberall bereinigt:

- Zeile 23 sagt noch sinngemaess, `domains:{cover:true}` erteile Zugriff auf alle 2661 Entities; Abschnitt 11 korrigiert spaeter, dass es schema-aware differenziert werden muss.
- Zeile 60 und 482 verwenden noch "Non-Repudiation"; Abschnitt 11 korrigiert auf "tamper-evident Hash-Chain".
- Zeile 443 laesst `unmanaged=true -> bleibt in system-users` stehen; Abschnitt 11 korrigiert spaeter, dass `unmanaged` nicht allow-all sein darf.

**Risiko:** Claude, Codex oder spaetere Implementierer koennen aus dem falschen Abschnitt bauen.

**Empfehlung:** Vor Produktcode den Body konsolidieren. Abschnitt 11 darf nicht nur Addendum sein, sondern muss die widerspruechlichen Hauptstellen ersetzen.

### P1 - Seed-Inventory ist unterdefiniert

Der Auftrag fordert ~20 Entities inklusive Licht/Sensor/Cover/Camera/Lock, area-los und state-only. Das ist richtig, aber als Testgrundlage noch nicht deterministisch.

**Risiko:** D3/D6/D7 messen zufaellige Integrationsverfuegbarkeit statt RBAC-Verhalten.

**Empfehlung:** Seed als Fixture deklarieren:

- Registry-Entities mit Area/Device
- mindestens eine erlaubte und eine verbotene Entity pro Domain
- state-only Entity ohne Registry-Eintrag
- hidden vs disabled separat
- mindestens ein entity-component service und ein non-entity service
- ein bewusst unsicherer Dev-only Custom-Service zur Systemkontext-Probe

### P1 - HACS-/HA-Update-Governance ist noch nicht Gate

D11 prueft "ungepruefte HA-Version -> monitor/off", aber fuer ein HACS-Produkt reicht das nicht. HACS nutzt eigene Repo-/Release-/Update-Pfade; Updates koennen ueber HA Update-Entities und `update.install` laufen.

**Empfehlung:** Als D13 nachziehen:

- HACS-Install-/Update-Simulation
- Downgrade/Rollback-Probe
- Preflight nach jedem HA- oder Tessera-Update
- Regel: kein Auto-Update in `enforce`, solange Adapter-Matrix nicht bestanden ist

### P2 - Produktversprechen muss noch oeffentlich hart begrenzt werden

Die technische Richtung ist ehrlich: `operate/control` ist die harte Grenze; `view` ist in einer einzelnen HA-Instanz nicht voll vertraulich. Diese Aussage muss in README, Threat Model und UI stehen.

**Empfehlung:** D14 "Was Tessera NICHT garantiert":

- keine harte Vertraulichkeit gegen untrusted non-admin Tokens in Single-Instance-HA
- `render_template`, Logbook, Registry-WS, allowlisted Events, Assist/Systemkontext, non-entity/raw/custom Services sind entweder Rest-Leaks oder Tier-2
- Owner/Admin/LLAT/Service-Accounts sind eigene Risikoklassen

## 4. DoD-Matrix: Wer kann was tun?

| DoD | Codex allein | Michael/Host noetig | Urteil |
|---|---:|---:|---|
| D1 Gruppen create/policy/restart | Teilweise | Ja: sauberer Dev-Zustand, Restart-Go | Machbar nach Preflight |
| D2 Policy-Change ohne Membership | Ja, nach Testuser/Token, mit In-process Harness | Testuser/Token | Machbar, aber nicht per externem Python-Prozess |
| D3 REST/WS/Service-Konsistenz | Ja, nach Testuser/Token/Seed | Testuser/Token/Seed | Machbar |
| D4 group_ids Union/Restore | Ja | Auth-Snapshot/Dev-Write-Go | Machbar, P0 |
| D5 kaputter Store/Boot-Rescue | Teilweise | absichtliche Korruption im Dev-Config, Restart-Go | Machbar, Rescue muss separat minimal sein |
| D6 Service-Matrix | Ja, nach Seed/Token | Seed/Token, evtl. Dev-Custom-Service | Erweitern um WS/Systemkontext |
| D7 Leak-Matrix | Ja, nach Token/LLAT | Token/LLAT | Erweitern um alle Registry-Reads, Assist/Systemkontext |
| D8 LLAT headless + Rotation | Headless Dev-Test ja | Live-LLAT-Inventar/Rotation Michael | Live-Teil nicht durch Codex automatisieren |
| D9 Custom Components | Statisch read-only ja | Runtime-Tests nur mit Dev-Seed/Install | Klassifikation haerter machen |
| D10 CM5 Auth-Benchmark | Nein fuer echte CM5-Zahl | CM5-Wartungsfenster/Backup | Mac-Container ist nur Vorprobe |
| D11 unsupported HA-Version | Ja mit zweitem Container/Monkeypatch | Docker/Netz/Host-Go | Machbar, D13 ergaenzen |
| D12 OIDC groups claim | Nein | Authentik/Test-IdP/Client | Ohne Beweis bleibt `by_group` v1-inert |

## 5. Choke-Point-Urteil

Der `AuthStoreAdapter` ist der richtige Kern, aber als Schnittname zu breit. Ich wuerde ihn in vier kleine Vertraege teilen:

1. **`AuthPolicyStoreAdapter`**  
   Private Gruppen/Policies: `ensure_group`, `set_group_policy`, `remove_group`, `persist`, structural probes, HA-Version-Gate.

2. **`UserBindingAdapter`**  
   Public-ish Memberships ueber `async_update_user(group_ids=FULL_UNION)`, Owner/Admin-Guard, Snapshot/Restore.

3. **`PermissionProbeAdapter`**  
   Re-read-verify, `check_entity`, REST/WS/service probes, Cache-Invalidierung.

4. **`RecoveryController`**  
   Boot-Rescue/Safe-Mode ausserhalb des normalen Tessera-Starts; darf nicht vom gesunden Tessera-Store oder Panel abhaengen.

Diese Trennung ist mehr als Stil: sie verhindert, dass ein grosser "AuthStoreAdapter" still zum Sammelbecken fuer Auth, Recovery, Probing und Produktlogik wird.

## 6. Konkrete naechste Bewegung

**Vor Start der Implementierung:**

1. Michael entscheidet: aktuelles `ha-tessera-dev-config` bewusst weiterverwenden oder frisch resetten.
2. Onboarding finalisieren und Testuser/Tokens anlegen. Tokenwerte nicht in Chat/Report schreiben.
3. Seed-Inventory als YAML/Fixture einfrieren.
4. Spike-Rubrik D1-D12 plus D13-D15 ergaenzen:
   - D13 HACS/HA-Update-Governance
   - D14 oeffentliches Threat Model / "Nicht garantiert"
   - D15 `off -> monitor -> enforce -> restore` End-to-End

**Dann uebernehme ich die Implementierung in dieser Reihenfolge:**

1. Dev-only In-process Harness bauen.
2. Auth-Write/Cache/Restore D1-D5 messen.
3. REST/WS/service/leak D3/D6/D7/D8 messen.
4. `/Volumes/config` nur read-only fuer D9-Realitaetsabgleich.
5. D10/D12 als Michael-Host/IdP-Paket vorbereiten, nicht vortaeuschen.
6. Report `outputs/tessera-phase0-spike-report-<datum>.md` mit PASS/FAIL/PARTIAL, Zahlen, Core-Ankern und Go/No-Go schreiben.

## 7. Quellen / Leitplanken

- Home Assistant Developer Docs, Permissions, zuletzt laut Seite aktualisiert am 2026-06-19: Policies haengen an Gruppen, Owner ist ausgenommen, `True`-Merge ist permissiv, Entity-Component-Services bekommen automatische Permission Checks, eigene Handler muessen User-Kontext pruefen.  
  https://developers.home-assistant.io/docs/auth_permissions/
- HACS Publish Docs: Integrationen brauchen eine definierte Repository-Struktur und `manifest.json`; HACS nutzt Releases/Default-Branch.  
  https://www.hacs.xyz/docs/publish/integration/
- HACS Update Entities: HACS stellt Update-Entities bereit; `update.install` kann Versionen/Tags/SHAs installieren.  
  https://www.hacs.xyz/docs/use/entities/update/
- OWASP Authorization Cheat Sheet: deny-by-default, least privilege, Permission-Checks auf jedem Request, Authorization-Tests als Pflicht.  
  https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html
- NIST SP 800-162: ABAC als attributbasierte Autorisierung ueber Subjekt-, Objekt-, Operations- und Umgebungsattribute; passt als Begruendung fuer Tessera-Selectoren ueber Areas/Devices/Labels, nicht als Ersatz fuer messbares HA-Enforcement.  
  https://csrc.nist.gov/pubs/sp/800/162/upd2/final

## 8. Schlussurteil

**Freigabe:** Phase-0-Spike darf vorbereitet und nach sauberem Dev-Preflight implementiert werden.

**Keine Freigabe:** Produkt-Tessera, HACS-Enforce, Live-CM5-Write, oder `by_group`-Enforce.

**Antwort auf die Kernfrage:** Ja, ich uebernehme die Spike-Implementierung, aber der naechste sichere Schritt ist nicht "direkt schreiben", sondern `Preflight -> In-process Harness -> D1-D5 P0 -> dann erst Breitenmatrix`. Der `AuthStoreAdapter` reicht als Idee, sollte aber in Store, Binding, Probe und Recovery aufgeteilt werden.
