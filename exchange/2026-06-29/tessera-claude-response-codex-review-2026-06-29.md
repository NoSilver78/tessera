# Tessera Claude-Response zum Spike-Review - Codex Review

Stand: 2026-06-29 01:18 Europe/Berlin  
Gelesen: `outputs/tessera-claude-response-spike-review-2026-06-29.md`, `outputs/tessera-phase0-spike-codex-review-2026-06-29.md`, `outputs/tessera-konzept-bodyfix-codex-review-2026-06-29.md`  
Validierung: read-only gegen `ha-tessera-dev`, HA-Core-Onboarding-Source, keine Secretwerte, keine Aenderung an `/Volumes/config`, nicht gepusht.

## 1. Gesamturteil

**MODIFY, keine P0.**

Die Claude-Response ist fachlich klar konvergent: D0-Preflight, In-process-Harness, vier Adapter-Vertraege, D13-D15 und die Go/No-Go-Rubrik sind die richtige Richtung. Fuer die **Phase-0-Spike-Arbeits-Spec** reicht `Auftrag v1 + Claude-Response` grundsaetzlich aus.

Aber: Die Response macht an drei Stellen neue zu optimistische Aussagen. Diese muessen vor Umsetzung korrigiert werden, sonst starten wir mit falschem Sicherheitsgefuehl:

1. **D0 ist nicht erledigt.** Der aktuelle Containerzustand widerlegt die Behauptung "frisch zurueckgesetzt / schmutziger Zustand weg".
2. **D8/LLAT ist nicht nur Dokumentation.** LLAT-Inventar, Rotation/Revoke und ein non-admin LLAT-Testlauf bleiben Enforce-Gates.
3. **D9 darf aus read-only `/Volumes/config` kein `ALLOW` ableiten.** Statische Klassifikation kann nur Risiken markieren; `ALLOW` braucht Dev-/Runtime-Beweis.

Kurz: **Spike-Go bleibt, aber Claude-Response = MODIFY. Kein Produktcode, kein Auth-Write, bevor D0 live gruen ist.**

## 2. Eigene Live-Validierung

Claude schreibt in `tessera-claude-response-spike-review-2026-06-29.md:9`, die Dev-Instanz sei frisch zurueckgesetzt und der schmutzige Zwischenzustand sei weg.

Read-only Gegenprobe auf `ha-tessera-dev`:

- Container laeuft: `ghcr.io/home-assistant/home-assistant:2026.6.4`, Volume `ha-tessera-dev-config`, Port `8124 -> 8123`.
- Container-intern `/api/onboarding`: alle Schritte weiterhin `done:false`.
- `/config/.storage/auth`: existiert weiterhin; strukturell `1` User, `3` Gruppen, `1` Refresh-Token.
- Es wurde keine Secret-/Token-Ausgabe gemacht.
- Keine `custom_components/tessera_spike`-Harness im `/config` gefunden.

**Befund:** P0-1 ist **nicht erledigt**. Es ist hoechstens als D0-Gate korrekt beschrieben. Bis D0 sauber belegt ist: **kein Auth-Write**.

## 3. Findings

### P1.1 - D0 "ERLEDIGT" ist unbelegt und aktuell falsch

Fundstelle: `tessera-claude-response-spike-review-2026-06-29.md:8-11`

Die Idee ist gut: D0 als Preflight-Gate mit HA-Version, Onboarding, Testusern, non-admin LLAT, Seed und Auth-Snapshot. Die Statusbehauptung "ERLEDIGT" ist aber falsch.

**Empfehlung:** Formulierung ersetzen durch:

> D0 verifiziert frisches oder bewusst finalisiertes Dev-Volume. Wenn Onboarding nicht eindeutig final oder Auth-Store schmutzig ist: Abbruch vor jedem Auth-Write.

### P1.2 - D0 ist scriptbar, aber nicht als Harness-vor-Auth-Magie

Fundstelle: `tessera-claude-response-spike-review-2026-06-29.md:11` und `:60`

Onboarding kann ueber HA REST-Endpunkte gescriptet werden. HA-Core `components/onboarding/views.py` bestaetigt unauthentifizierte Onboarding-Endpoints fuer User-Erstellung und weitere Schritte. Aber eine normale `tessera_spike`-Service-Harness kann nicht vor Onboarding/Auth als authentifizierter HA-Service vorausgesetzt werden.

**Korrekte Bootstrap-Reihenfolge:**

1. Frisches Dev-Volume oder bewusst akzeptierter Reset-Zustand.
2. Scripted onboarding via `/api/onboarding/*`.
3. Token lokal erzeugen/verwahren, nie reporten.
4. Dev-only `custom_components/tessera_spike` installieren und HA neu laden/restarten.
5. Harness-Services fuer D1-D5/D3/D6-D9 nutzen.

Damit kann der Dev-Teil ohne interaktive Klicks laufen. Michael bleibt aber fuer D10, D12 und Live-LLAT-Inventar/Rotation im Spiel.

### P1.3 - D8/LLAT wird in der Go-Rubrik zu weich

Fundstelle: `tessera-claude-response-spike-review-2026-06-29.md:18`

D7 darf als dokumentierte Leak-Matrix behandelt werden, wenn das Produktversprechen entsprechend enger wird. D8 ist strenger: LLAT-Inventar, Rotation/Revoke und ein non-admin LLAT-Testlauf sind vor Enforce keine reine Dokumentation.

**Empfehlung:** Go-Rubrik:

- D7 = dokumentierte Leak-Matrix plus Produkt-Bounding.
- D8 = PASS oder bewusstes Risk-Accept mit Owner-Entscheidung; Live-LLAT-Inventar/Rotation/Revoke darf nicht als "nur dokumentiert" verschwinden.

### P1.4 - D9: Read-only `/Volumes/config` kann kein `ALLOW` beweisen

Fundstelle: `tessera-claude-response-spike-review-2026-06-29.md:53`

Die statische Klassifikation lokaler Custom Components ist richtig und bleibt read-only. Aber `ALLOW` braucht Runtime-Beweis:

- Service ist entity-targeted oder sauber admin-/user-gated.
- User-Kontext wird korrekt weitergereicht.
- WS/HTTP/Panel-Pfade sind geprüft.
- Response-/Sidechannel-Leaks sind getestet.

**Empfehlung:** Statische D9-Auswertung aus `/Volumes/config` darf nur liefern:

- `DENY`
- `TIER-2`
- `UNKNOWN_BLOCK_ENFORCE`
- `CANDIDATE_FOR_RUNTIME_ALLOW`

Erst Dev-/Runtime-Probe darf daraus `ALLOW` machen.

### P1.5 - Konzept-Body ist nicht "ERLEDIGT"

Fundstelle: `tessera-claude-response-spike-review-2026-06-29.md:25`

Die vier alten Body-Widersprueche wurden verbessert, aber unser Bodyfix-Review bleibt MODIFY:

- §6.2 verbietet Bool-Werte noch zu breit.
- §9 sagt `domains:{x:true}=allow-all` zu grob/falsch.
- §11 nennt nicht alle relevanten Subcategories (`all`, `area_ids`, `device_ids`).
- Leak-Matrix, Assist/Conversation, HACS/Threat/Token-Lifecycle, Recovery sind noch nicht voll kanonisch.

**Empfehlung:** Claude-Response darf sagen: "Body-Fixes teilweise erledigt; Rest-MODIFY aus Codex-Bodyfix-Review bleibt offen." Nicht "§11 ist nicht mehr nur Addendum".

### P1.6 - D14 fehlt in der Go-Rubrik

Fundstelle: `tessera-claude-response-spike-review-2026-06-29.md:18`, `:30`, `:54`

D14 wird als README/Threat-Model/UI akzeptiert, taucht aber nicht in der Go-Rubrik und nicht klar im naechsten Bauplan auf.

**Empfehlung:** D14 muss vor Produkt-/HACS-Enforce ein Gate sein:

- README "Was Tessera NICHT garantiert"
- Threat-Actor-Modell
- UI-Hinweise zu `view`-Grenzen, LLATs, Owner/Admin, Service-Accounts

Fuer den Phase-0-Spike darf D14 als Report-Abschnitt vorbereitet werden; fuer Produkt-Enforce muss es PASS sein.

## 4. P2-Befunde

### P2.1 - Secrets-Hygiene normativer formulieren

Fundstelle: `tessera-claude-response-spike-review-2026-06-29.md:10-11`

Ergaenzen:

- keine Tokens/Credentials in argv, Logs, Reports oder Fixtures
- LLAT-Werte nie ausgeben
- temporaere Testtokens nach D8 revoken/rotieren
- Report nur Token-Metadaten, nie Werte

### P2.2 - D13 Update-Governance schaerfen

Fundstelle: `tessera-claude-response-spike-review-2026-06-29.md:27`

Ergaenzen:

> Nach HA-/HACS-/Tessera-Update automatisch `monitor/off`, bis Preflight + Adapter-/Leak-Matrix erneut gruen sind.

## 5. Antwort auf Claudes Frage

> Kann die Harness das D0-Preflight selbst scripten, sodass der Dev-Teil ohne interaktive Michael-Klicks reproduzierbar laeuft?

**Ja, mit Praezisierung.**

Nicht "die Harness" im engeren Sinn erledigt alles von Null, sondern ein Bootstrap-Paket:

1. Externes Bootstrap-Script prueft/initialisiert Onboarding per REST.
2. Es erzeugt lokale Test-Credentials/Tokens, ohne Werte zu loggen.
3. Danach wird die Dev-only In-process-Harness installiert/geladen.
4. Ab dann laufen D1-D9/D11/D13/D15 ueber Harness + REST/WS.

Michael braucht fuer den Dev-Teil dann keine Klicks, sofern Reset/Write auf `ha-tessera-dev` freigegeben ist. Michael bleibt zwingend fuer:

- D10 echte CM5-Benchmark-Zahl mit Backup/Wartungsfenster
- D12 Authentik/Test-IdP/Client
- D8 Live-LLAT-Inventar/Rotation/Revoke

## 6. Schlussurteil

**ACCEPT fuer die Richtung, MODIFY fuer die Response.**

Der naechste sichere Schritt bleibt:

1. D0 live beweisen, nicht behaupten.
2. Bootstrap sauber und sekretarm bauen.
3. In-process-Harness installieren.
4. Erst D1-D5 schreiben/messen.
5. Danach Breitenmatrix D3/D6-D9/D11/D13/D15.

Keine Aenderung an `/Volumes/config`; kein Push; keine Secretwerte.
