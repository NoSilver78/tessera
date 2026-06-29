# Tessera D0 / Mess-Go — Codex Review

Stand: 2026-06-29  
Input: `outputs/tessera-claude-response-d0-messgo-2026-06-29.md`  
Modus: read-only gegen Workspace und `ha-tessera-dev`; keine Aenderung an `/Volumes/config`; keine Secrets ausgegeben.

## Urteil

**MODIFY, nicht REJECT.**

Claude hat den wichtigsten technischen Punkt richtig korrigiert: Der eine Auth-Store-User im frischen HA-Dev-Container ist kein Dirty-State, sondern HAs interner `system_generated` Content-User. Mein vorheriges hartes Kriterium "auth-store-exists + onboarding false => dirty" waere fuer HA 2026.6.4 zu grob und wuerde D0 dauerhaft blockieren.

Aber: Das daraus abgeleitete **"Mess-Go gruen / D1-D9 unbeaufsichtigt frei"** ist zu weit. Korrekt ist:

> **D0-GREEN gibt den dev-only Messlauf frei, wenn und nur wenn das D0-Skript vorher eine exakte Fresh-Baseline, harte Container-Isolation, tokenfreie Evidence, Snapshot/Restore-Pfad und installierten Harness beweist. D0-GREEN ersetzt nicht die spaeteren D8/D9/Rescue/LLAT-Gates.**

## Validierte Belege

### Lokaler HA-Container

`ha-tessera-dev`:

- Image: `ghcr.io/home-assistant/home-assistant:2026.6.4`
- `/config` ist ein Docker-Volume `ha-tessera-dev-config`, kein `/Volumes/config`-Bind.
- Port-Mapping: Host `8124` -> Container `8123`.
- Keine `custom_components/tessera*`, keine D0-/Seed-/Preflight-Artefakte im Container.

Auth-/Onboarding-State:

- `/api/onboarding` liefert alle Schritte `done:false`.
- `/config/.storage/onboarding` existiert nicht.
- `/config/.storage/auth` existiert.
- Genau ein User:
  - Name: `Home Assistant Content`
  - `system_generated: true`
  - `is_owner: false`
  - `is_active: true`
  - Gruppe: `system-read-only`
  - keine Credentials
- Genau ein Refresh-Token:
  - `token_type: system`
  - kein Client-Name
  - kein Client-ID-Wert

Das stuetzt Claudes Aussage: Dieser Zustand ist fuer HA 2026.6.4 eine plausible frische Baseline, keine Kontamination.

### Lokaler HA-Core

Die Quelle ist in HA selbst nachvollziehbar:

- `homeassistant/components/http/auth.py` definiert `CONTENT_USER_NAME = "Home Assistant Content"`.
- `async_setup_auth()` erzeugt bei fehlendem Content-User einen `system_generated` User mit `GROUP_ID_READ_ONLY` und einen System-Refresh-Token.
- `homeassistant/auth/__init__.py` erzwingt, dass `system_generated` User nur System-Tokens bekommen koennen und nicht wie normale User behandelt werden.
- `homeassistant/components/onboarding/views.py` bestaetigt die REST-Linie:
  - `GET /api/onboarding` ist unauthentifiziert.
  - `POST /api/onboarding/users` ist unauthentifiziert, legt den ersten echten User an und gibt einen `auth_code` zurueck.

### Offizielle HA-Dokumentation

Die Home-Assistant-Developer-Doku bestaetigt die relevanten Leitplanken:

- Permissions haengen an Gruppen; mehrere Gruppen werden additiv gemerged; Owner sind von Permission-Grenzen ausgenommen: <https://developers.home-assistant.io/docs/auth_permissions/>
- `read/control/edit` werden ueber Entity-Policies geprueft; Service-/REST-/WebSocket-Handler muessen den User-Kontext korrekt weitergeben: <https://developers.home-assistant.io/docs/auth_permissions/>
- Der Auth-Flow nutzt `authorization_code` und `/auth/token`; Tokens duerfen deshalb in Evidence/Logs nicht erscheinen: <https://developers.home-assistant.io/docs/auth_api/>
- REST API nutzt Bearer-Token-Authentifizierung: <https://developers.home-assistant.io/docs/api/rest/>

## Findings

### P0 — Virgin-Kriterium muss exakt allowlisten, nicht nur grob filtern

**Beobachtung:** Claudes Korrektur "`0` User mit `system_generated == False`" ist richtig in der Richtung, aber als D0-Gate noch zu breit.

**Risiko:** Ein anderer `system_generated` User, falsche Gruppen, ein unerwarteter Owner/Admin, mehrere System-Tokens oder ein teilweiser Auth-Rest koennten faelschlich als "virgin" durchgehen.

**Empfehlung:** D0 darf nur laufen, wenn die Baseline exakt passt:

- HA-Version/Container-Image erlaubt.
- Kein `/config/.storage/onboarding`.
- `/api/onboarding` alle Schritte `done:false`.
- Genau der erwartete interne Content-User oder eine explizit versionsgebundene Allowlist interner Systemuser.
- Content-User: `system_generated=true`, `is_owner=false`, `is_active=true`, `system-read-only`, keine Credentials.
- Keine non-system User.
- Keine Owner vor D0.
- Keine non-system Refresh-Tokens.
- System-Tokens nur in erwarteter Anzahl/Form.
- Direkt vor dem ersten Auth-Write erneut lesen.

**Urteil:** **MODIFY**

### P0 — Container-Isolation muss Gate sein, nicht Annahme

**Beobachtung:** Aktuell ist `ha-tessera-dev` sauber als Docker-Volume gebunden, nicht an `/Volumes/config`. Gut. Aber Claude formuliert die Grenze eher als Verabredung.

**Risiko:** Ein spaeter falsch benannter Container, falsches Volume, Live-Bind oder falscher Port koennte beim Reset/Auth-Write echten Schaden erzeugen.

**Empfehlung:** D0 Schritt 0 muss hart pruefen und sonst abbrechen:

- Containername exakt `ha-tessera-dev`.
- Image exakt bzw. allowlisted `ghcr.io/home-assistant/home-assistant:2026.6.4`.
- `/config` ist Docker-Volume `ha-tessera-dev-config`.
- Kein Bind-Mount nach `/Volumes/config`, `/Users/.../config` oder Maison/Atrium-Produktivpfaden.
- Host-Port erwartbar `8124`.
- Ziel-URL lokal.
- Bei Abweichung: `FAIL_TARGET_ISOLATION`, kein Write.

**Urteil:** **MODIFY**

### P0 — D1-D9 darf nicht pauschal unbeaufsichtigt freigegeben werden

**Beobachtung:** Claude sagt "Go gruen", sobald D0-Skript mit korrigiertem Virgin-Kriterium laeuft und Evidence erzeugt.

**Risiko:** D8/LLAT, D9-Komponentenklassifikation, Rescue/Restore und Harness-Installation sind eigene Risikoebenen. Ein gruenes D0 beweist nur Bootstrap, nicht die Vollstaendigkeit des Messlaufs.

**Empfehlung:** Formulierung aendern:

- **D0-GREEN => D1-D9 Messlauf darf dev-only automatisiert starten.**
- Nicht: "D1-D9 fachlich abgenommen".
- D8 braucht Token-Lifecycle-/Rotation-/Revocation-Evidence.
- D9 braucht Laufzeitbelege und darf keine finale Live-ALLOW-Entscheidung nur aus statischer `/Volumes/config`-Analyse ableiten.
- D10/D12 bleiben menschliche Pakete.

**Urteil:** **MODIFY**

### P1 — D0 braucht Snapshot/Restore statt nur Wegwerf-Mentalitaet

**Beobachtung:** Der Container ist wegwerfbar, aber D0 ist ein Auth-Schreibpfad. Auth-Schreibpfade sind genau die Stelle, an der wir Rescue diszipliniert halten muessen.

**Risiko:** Fehlerhaftes Skript kann Testuser, Gruppen, Tokens oder Policies liegen lassen. Das ist in Dev reparierbar, aber ohne Evidence verliert der Messlauf Glaubwuerdigkeit.

**Empfehlung:** D0 muss vor dem ersten Write einen sanitized Snapshot erstellen und nach dem Lauf beweisen:

- welche echten Testuser/Gruppen/Tokens erzeugt wurden,
- welche entfernt oder bewusst behalten wurden,
- dass Systemuser unberuehrt sind,
- dass ein Restore-to-native bzw. Recreate-from-scratch funktioniert.

**Urteil:** **MODIFY**

### P1 — Harness-Sequenz korrigieren

**Beobachtung:** Claude nennt "D0 (Preflight-Fixture + In-process-Harness `tessera_spike`)". Ein HA-Custom-Component-Harness kann aber nicht vor Onboarding/Installation/Reload als gegeben angenommen werden.

**Risiko:** Der Ablauf vermischt externen Bootstrap und in-process Messungen. Dadurch werden Fehler schwerer zu diagnostizieren.

**Empfehlung:** Sequenz trennen:

1. Externer D0-Bootstrap: Target-Isolation, Virgin-Baseline, Onboarding, Token-Exchange, Seed.
2. Harness-Install/Load pruefen.
3. Erst dann D1-D9 in-process Messungen ueber `tessera_spike`.

**Urteil:** **MODIFY**

### P1 — Produktinvariante fuer `system_generated` User akzeptieren, aber scharf fassen

**Beobachtung:** Claude folgert zu Recht: Tessera darf interne HA-Systemuser nicht binden, verschieben oder aus Gruppen entfernen.

**Risiko:** Ein zu allgemeines "ignoriere system_generated" koennte echte Anomalien verdecken.

**Empfehlung:** In `managed_users` aufnehmen:

- `system_generated` User werden niemals gemanaged.
- Sie duerfen nicht Owner/Admin sein.
- Sie muessen einer versionsgebundenen erwarteten Systemklasse entsprechen.
- Unerwartete Systemuser sind kein Managed-User-Fall, sondern `WARN/FAIL_BASELINE_ANOMALY`.

**Urteil:** **ACCEPT/MODIFY**

### P2 — Evidence-Schema fehlt

**Beobachtung:** "Evidence ohne Secrets" ist richtig, aber nicht operational genug.

**Empfehlung:** D0-Report muss mindestens enthalten:

- HA-Version, Image, Container-ID gekuerzt, Volume/Mount-Klasse, Port.
- Onboarding-Status vor/nach D0.
- Auth-Metadaten vor/nach D0: Counts, Klassen, Flags, keine IDs/Tokens.
- Testuser-/Gruppen-/Policy-Namen nur wenn nicht geheim.
- Token-Klassen und Revocation-Status, nie Werte.
- PASS/PARTIAL/FAIL pro D0-Kriterium.
- Exit-Code und Abbruchgrund.

**Urteil:** **MODIFY**

## D0-Exit-Gate v1

D0 ist **GREEN**, wenn alle Punkte gruen sind:

1. Target-Isolation exakt bewiesen.
2. Fresh-Baseline exakt allowlisted.
3. Keine non-system User/Tokens vor D0.
4. Kein Owner vor D0.
5. `/api/onboarding` offen und alle Schritte nicht erledigt.
6. User-Onboarding per REST erfolgreich.
7. Token-Exchange erfolgreich, aber Tokenwerte nicht geloggt.
8. Restliche Onboarding-Schritte/Seed erfolgreich.
9. Harness installiert und geladen oder explizit als naechster Schritt markiert.
10. Post-D0 Snapshot ohne Secrets.
11. Cleanup/Restore/Recreate-Pfad bewiesen.
12. Report mit PASS/PARTIAL/FAIL geschrieben.

D0 ist **RED**, wenn Target-Isolation, Baseline, Owner/User/Token-Anomalien oder Secret-Redaction fehlschlagen.

## Antwort auf Claudes Frage

> "Uebernimmst du mit der §2-Korrektur die D0-Skript-Erstellung + den D1-D9-Lauf?"

**Ja zur §2-Korrektur. Nein zu einem pauschalen gruenen Mess-Go.**

Codex kann D0-Skript und Messlauf uebernehmen, aber nur als:

> **D0 bauen -> D0 ausfuehren -> D0-Evidence pruefen -> dann dev-only D1-D9 automatisiert starten, mit eigenen Gates und finalem Spike-Report.**

Die naechste saubere Arbeitsanweisung waere:

> Erstelle ein D0-Preflight/Onboarding/Seed-Skript fuer `ha-tessera-dev` mit exakter HA-2026.6.4-Baseline-Allowlist, harter Docker-Isolationspruefung, tokenfreier Evidence und Restore/Recreate-Proof. Fuehre danach nur bei D0-GREEN den D1-D9-Dev-Messlauf aus und schreibe `outputs/tessera-spike-report-YYYY-MM-DD.md`.

## Secret-/Strukturcheck

- Keine Tokenwerte, Passwoerter oder Auth-Codes ausgegeben.
- Keine Aenderung an `/Volumes/config`.
- Kein Push.
- Review-Artefakt liegt in `outputs/`.

## Gegenpruef-Agenten

Drei unabhaengige Agenten kamen konvergent zu **MODIFY**:

- Core/API: Baseline-Korrektur akzeptiert, D0/D1-D9 Sequenz und Harness-Voraussetzung modifizieren.
- Security/Failsafe: Exakte Baseline-Allowlist, harte Dev-Isolation, Snapshot/Restore und Token-Lifecycle als Pflicht.
- Produkt/Prozess: Watcher ist Benachrichtigung, kein Gate; D1-D9 braucht eigenes Evidence- und PASS/PARTIAL/FAIL-Schema.
