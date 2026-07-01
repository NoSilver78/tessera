# Machbarkeit echter Mandantentrennung auf EINER Home-Assistant-Instanz

**Datum:** 2026-07-01 · **Methode:** Agenten-Workflow (7 Pfad-Enumerations-Linsen + adversariale Bypass-Jagd + Synthese), **jeder Pfad gegen den echten HA-Quellcode verifiziert** (HA 2025.1.4 im venv, `file:line`). · **Frage:** Kann ein Mieter A auf einer geteilten HA-Instanz die Daten/Steuerung von Mieter B über KEINEN Pfad erreichen?

## Kern-Verdikt: NO-GO für echte Isolation auf einer Instanz
- **(a) Tessera allein: NO-GO.** Native `PolicyPermissions` decken NUR die per-Entity-Read/Control-Prüfung (`get_states`, REST `/api/states`, `subscribe_entities`, `entity_service_call`). Alles, was diese Ebene nicht befragt, leckt **vollständig und lautlos**. Tessera kann diese Pfade konstruktiv nicht schließen.
- **(b) Tessera + Custom-WS-Filter: TEILWEISE.** Schließt die *WS-basierten* Leaks (render_template, Registry-Lists, config-Leaks, history/logbook-WS, camera/media-WS), erreicht aber strukturell **nicht**: HTTP-Proxy-Views (Camera/Image), die **DB-Reads** (History/Logbook/Recorder — kein per-user-Hook), das **Automation-Kontext-Stripping** und den **Admin-Bypass**. Notwendig, nicht hinreichend.
- **(c) Reverse-Proxy allein: NO-GO.** Sieht nicht in die Automation-/Template-Sensor-Ausführung hinein (passiert im HA-Prozess, kein API-Call passiert den Proxy).
- **(d) HA-Core-Patch: prinzipiell GO, praktisch untragbar.** Permanenter Fork von ~15 Core-Dateien, Rebase/Re-Audit bei jedem HA-Release (~4 Wochen).

**Ehrlich:** Echte Mieter-Isolation auf einer Instanz ist mit vertretbarem Aufwand **nicht erreichbar**. Die Kern-Löcher verlangen Core-Patches oder ein Gateway — und selbst dann bleibt Automation-/Template-Bridging ein Rest-Loch, das nur durch **Authoring-Governance** (Betriebsversprechen) geschlossen wird, nicht durch eine erzwungene Grenze.

## Die tragenden Löcher (needs-architecture, von Tessera NICHT schließbar) — quellcode-belegt
1. **Permissiver Group-Merge (Wurzel):** `auth/permissions/merge.py:26-49` („most permissive wins") + `system_policies.py` `USER_POLICY={CAT_ENTITIES:True}` + `auth_store.py:624` (`system-users`=read-all). Mieter in `system-users` **und** Tessera-Gruppe → Merge = read-all → **alles** umgangen, lautlos. Tessera's `auth_adapter.py:527-531` verbietet system-users + ersetzt das Group-Set — aber **nur für gebundene Nutzer**; ein manuell zurückgesetzter Mieter = stiller Total-Leak.
2. **Admin-Bypass:** `helpers/service.py:937`, `api/__init__.py:218`, `websocket_api/commands.py:317` — jeder je-Admin-Mieter umgeht alles. Provisioning-Invariante, kein Code-Fix.
3. **Automation-Kontext-Stripping:** `automation/__init__.py:644-646` verwirft `user_id` → Aktionen laufen als System → geteilte Automation überbrückt Mieter komplett. Der zentrale indirekte Steuerkanal.
4. **History/Logbook/Recorder/Energy DB-Reads:** kein per-user-Filter. `/api/logbook` ohne Filter dumpt das ganze Haus; `recorder/list_statistic_ids` enumeriert alle. Höchstes Rest-Risiko (oft übersehen).
5. **render_template (WS + Mobile-Webhook):** `websocket_api/commands.py:600-609` kein `@require_admin`, kein check_entity → jeder Nicht-Admin liest jede Entity. (In dieser Version reiner Read-Leak — Templates rufen keine Services.)
6. **Camera-/Image-Proxy HTTP-Views:** `camera/__init__.py:942-1030`, `image/__init__.py:280-320` — Bytes ohne PolicyPermissions-Hook.
7. **Non-Entity-/Target-lose Services:** `core.py:2690` prüft nichts (python_script, shell_command, Legacy-notify).

**tessera-closable (Custom-WS-Interceptor):** Registry-Lists (`config/*/list`, `search/related`), `automation/config`+`script/config`+`lovelace/config` (volle Fremd-YAML!), Assist/LLM-Read (globale Exposure), camera/media-WS.
**native-gated (HÄLT, konditional):** state-read-Pfade + entity-service-control **sofern Tessera die read-all-Default ersetzt UND Mieter strikt non-admin sind**. Skript-Innenaktionen tragen die Caller-user_id (geteiltes Skript aktuiert nichts Fremdes). subscribe_trigger/execute_script = `@require_admin`.

## Empfehlung: **getrennte HA-Instanzen pro Einheit**
Echte Isolation per **Prozess-/Auth-Grenze** — kein render_template/History/Automation-Stripping kann je eine fremde Instanz erreichen, weil die Entities dort nicht existieren. Kein Custom-Security-Code, kein Core-Fork, kein Re-Audit pro Release. Fehler sind **laut** (Instanz down = sichtbar), nicht still.
- **Preis:** n× Betrieb (leichtgewichtig; HA läuft problemlos in getrennten VMs/Containern).
- **Geteilte Hardware (KNX/PV/WP):** eine „Haus-Instanz" besitzt die geteilten Geräte + exponiert **nur** explizit freigegebene Entities pro Einheit (MQTT-Bridge / `remote_homeassistant`-Whitelist) → die Grenze wird **explizit + laut**.
- **Entscheidend:** getrennte Instanzen = „nichts freigegeben" ist Default, jede Freigabe bewusst. Eine Instanz = „alles sichtbar" ist Default, jede Grenze muss aktiv+vollständig+wartungstreu erkämpft werden, mit stillen Lücken. Für echte fremde Parteien (ggf. DSGVO): Default-deny-durch-Architektur > Default-allow-durch-Custom-Code.

## Tessera-Positionierung (Konsequenz)
Tessera ist **NICHT** die Mandantentrennungs-Lösung und darf nicht als solche verkauft werden (wäre falsche Sicherheitszusage). Tessera bleibt **hervorragend** für: (1) fein abgestuftes **Ein-Haushalt-RBAC** (Gast/Kind/Putzhilfe/Kiosk einschränken — kein echter Angreifer), und (2) als **Intra-Instanz-RBAC** innerhalb jeder Einheit im Multi-Instanz-Modell. Die Tenant-Grenze ist die **Instanz**, nicht Tessera. Tesseras `SECURITY.md` dokumentiert die Leak-Pfade bereits ehrlich — Posture stimmt.

## Unsicherheiten
Verifiziert gegen **2025.1.4** (Versions-Drift — HA ändert WS/Permissions/Templates häufig); Tesseras Invarianten-Halten unter allen Pfaden (Rebind/Race/Neustart) nicht erschöpfend auditiert; WS-Kommando-Vollständigkeit unbeweisbar (hunderte Kommandos, Add-ons registrieren eigene); Template-Service-Fähigkeit über alle custom_components nicht geprüft; Automation/Script-Kontext in Randfällen (Device-Actions, verschachtelte Ketten, Blueprints) fallweise.
