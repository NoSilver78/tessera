# Tessera D0-Preflight / Mess-Go Check

Stand: 2026-06-29  
Modus: read-only, keine Aenderung an `/Volumes/config`, keine Secrets ausgegeben.

## 1. Dateilagen-Check

Die drei erwartbaren fachlichen Dateien liegen im Watcher-Scratchpad:

1. `/private/tmp/claude-501/-Volumes-config/804c8747-4aad-4340-ad2f-84565e7ef5f2/scratchpad/berechtigungskonzept_REQUIREMENTS.md`
   - mtime: 2026-06-29 00:24:18
2. `/private/tmp/claude-501/-Volumes-config/804c8747-4aad-4340-ad2f-84565e7ef5f2/scratchpad/rbac_product_charter.md`
   - mtime: 2026-06-29 00:25:20
3. `/private/tmp/claude-501/-Volumes-config/804c8747-4aad-4340-ad2f-84565e7ef5f2/scratchpad/rbac_konzept.md`
   - mtime: 2026-06-29 00:57:28

Zusaetzlich liegt dort ein Hilfsskript:

- `/private/tmp/claude-501/-Volumes-config/804c8747-4aad-4340-ad2f-84565e7ef5f2/scratchpad/fix_konzept.py`
  - mtime: 2026-06-29 00:57:17

Nach dem letzten Codex-Review um 01:16 wurde in den ueberwachten Pfaden kein neues Dreierpaket abgelegt. Die drei Dateien sind also vorhanden, aber nicht neuer als der bereits gelesene Tessera-Kontext.

## 2. Dev-Instanz-Zustand

Gefundener Container:

- `ha-tessera-dev`
- Image: `ghcr.io/home-assistant/home-assistant:2026.6.4`
- Status: laufend

Read-only Befund in `/config`:

- Keine installierten `custom_components/tessera*`
- Keine gefundenen D0-/Preflight-/Seed-Artefakte
- `/config/.storage/onboarding` existiert nicht
- `/config/.storage/auth` existiert
- Auth-Store enthaelt: 1 User, 3 Gruppen, 1 Refresh-Token

HTTP-Probe lokal im Container:

```json
[
  {"step":"user","done":false},
  {"step":"core_config","done":false},
  {"step":"analytics","done":false},
  {"step":"integration","done":false}
]
```

Das ist kein ganz sauberer Virgin-State: Onboarding meldet "nicht erledigt", aber ein Auth-Store mit User/Token existiert bereits.

## 3. Kann Codex D0 selbst scripten?

Verdikt: **Ja, technisch scriptbar, aber nur mit fail-closed Preflight.**

Die lokale HA-Implementierung bestaetigt:

- `GET /api/onboarding` ist unauthentifiziert und liefert den Status.
- `POST /api/onboarding/users` ist unauthentifiziert, erzeugt den ersten Admin-User und gibt einen `auth_code` zur Token-Beschaffung zurueck.
- Danach koennen weitere Onboarding-Schritte und Seed-Operationen per REST erfolgen, sobald ein Token vorliegt.

Damit kann Codex D0 fuer eine Dev-Instanz automatisieren:

1. Onboarding-Status lesen.
2. Auth-/Storage-Zustand pruefen.
3. Falls sauber: Test-Admin/Testuser anlegen, Token holen, Core-/Analytics-/Integration-Schritte setzen.
4. Seed via REST/API ausfuehren.
5. Evidence schreiben: Status, erzeugte Testrollen/User, REST/WS/Service-Proben, keine Secrets.

## 4. Kritische Einschraenkung

Der aktuelle Container ist fuer blindes D0 nicht eindeutig sauber:

- Onboarding ist laut API offen.
- Gleichzeitig existiert bereits ein Auth-Store mit User und Refresh-Token.

Ein robustes D0-Skript darf hier nicht einfach weiterlaufen, weil es sonst versehentlich einen zweiten Admin/User erzeugen oder eine halb initialisierte Dev-Instanz als "clean" behandeln kann.

Pflicht vor unbeaufsichtigtem D1-D9:

- D0-Skript existiert als Artefakt.
- D0 bricht bei "onboarding=false + auth-store-exists" standardmaessig ab.
- Alternativ gibt es einen expliziten Modus fuer eine wegwerfbare Dev-Instanz, z. B. `--allow-dirty-dev` oder besser: Container/Config vorher frisch erzeugen.
- D0 schreibt ein Evidence-Protokoll ohne Token/Passwoerter.
- D0 ist klar auf `ha-tessera-dev` begrenzt und fasst `/Volumes/config` nicht an.

## 5. Entscheidung

| Frage | Urteil | Begruendung |
|---|---:|---|
| Drei Dateien vorhanden? | **ACCEPT** | Requirements, Charter und Konzept liegen im Watcher-Scratchpad. |
| D0 grundsaetzlich per REST scriptbar? | **ACCEPT** | Lokale HA-2026.6.4-Onboarding-Views und API-Probe bestaetigen die technische Linie. |
| Aktueller Container sofort fuer blindes D0 geeignet? | **MODIFY** | Auth-Store existiert, Onboarding-Store nicht. Das ist ein Dirty-/Ambiguous-State. |
| Unbeaufsichtigtes D1-D9 jetzt freigeben? | **NO-GO / CONDITIONAL** | Erst D0-Skript + Evidence auf sauberem oder explizit akzeptiertem Dirty-Dev-State. |

## 6. Mess-Go

Mein Mess-Go ist **conditional**:

**Gruen wird es**, sobald D0 als Skript vorliegt und auf einer eindeutig sauberen Dev-Instanz oder mit bewusst freigegebenem Dirty-Dev-Modus erfolgreich Evidence erzeugt.

Bis dahin: **kein vollautomatischer D1-D9-Lauf**. Die Gefahr ist nicht gross, aber sie ist genau die Art kleiner Uneindeutigkeit, aus der spaeter falsche Sicherheit entsteht.
