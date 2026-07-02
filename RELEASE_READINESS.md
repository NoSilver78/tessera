# Tessera — RELEASE_READINESS

Release-Engineering-Dossier für die Auslieferung von **Tessera** als HACS-Integration.
Stand: **2026-06-30** · **Update 2026-07-01** (siehe Kasten). Quelle: HACS-Doku (`hacs.xyz`), HA-Developer-Docs, `home-assistant/brands`,
adversariell gegengeprüft (VALIDATION). Korrekturen aus der Validierung sind eingearbeitet;
Unsicheres ist explizit als **⚠️ UNSICHER** markiert.

> **📌 Stand-Update 2026-07-01 (überholt die „ROT"-Status in §4):**
> **Gate-1 (Verteilung) = GRÜN** — Repo public, Description+Topics gesetzt, Releases **v0.2.0–v0.6.0**
> getaggt (manifest byte-genau), HACS+hassfest-CI grün, Brand-Assets inline, LICENSE/SECURITY/README
> vorhanden. Tessera ist als **Custom Repository sauber installierbar**.
> **Gate-2 (Reife) = weitgehend erfüllt** — `enforce` ist **dev-erprobt** (voller Dev-E2E gegen
> `ha-tessera-dev`) **und in einer Live-Instanz aktiv verifiziert** (Bewohner real eingeschränkt,
> Owner/Admin-Bypass, fail-safe intakt); ein **breiter Multi-Setup-Soak** bleibt erwünscht (Help-wanted).
> **Verbleibend für den Default-Store (Pfad B):** ein PR gegen `hacs/default` vom Owner-Account +
> Klärung/Erfüllung der `brands`-Prüfung (Inline-`brand/` vs. `home-assistant/brands`-Eintrag) —
> beide sind **externe GitHub-PRs des Owners**, kein Code. Die Checklisten unten bleiben als Referenz.

Repo: `/Users/michaelscholz/tessera` · Domain `tessera` · default branch `main` · origin `NoSilver78/tessera`.

---

## 0. Strategie in einem Satz

Zwei Pfade, sequenziell:

1. **Pfad A — HACS-Custom-Repo (jetzt):** Repo wird per URL als „Custom repository" in HACS
   hinzugefügt. **Kein PR, kein Review.** Installierbar, sobald die Repo-Struktur stimmt.
2. **Pfad B — HACS-Default-Store (später):** PR gegen `hacs/default` mit automatischen Checks +
   Merge durch das HACS-Team. Strengere Pflichtmenge, öffentlich gelistet.

> **Wichtige Klarstellung (aus VALIDATION):** „Privat kuratiert" kann sich NUR auf
> „nicht im Default-Store gelistet" beziehen. Das GitHub-Repo selbst **muss öffentlich (public)**
> sein, sonst kann HACS es nicht abrufen — auch als Custom-Repo.
> Quelle: https://www.hacs.xyz/docs/publish/start/

---

## 1A. PFAD A — HACS-Custom-Repo (Pflicht-Checkliste, JETZT)

Diese Liste ist das **minimal hinreichende** Set, damit ein Nutzer Tessera per
„Custom repositories" installieren kann. Jeder Punkt mit Quelle.

1. **Genau EINE Integration pro Repo** — nur ein Unterverzeichnis unter `custom_components/`.
   Für Tessera exakt `custom_components/tessera/` als einziges Unterverzeichnis.
   Quelle: https://www.hacs.xyz/docs/publish/integration/
2. **Alle Laufzeit-Dateien in `custom_components/tessera/`** (`__init__.py`, `manifest.json`,
   `config_flow.py`, …). `content_in_root` NICHT setzen (Standard-Layout).
   Quelle: https://www.hacs.xyz/docs/publish/integration/
3. **`hacs.json` im Repo-Root**, mindestens Key `name`. Minimal: `{"name": "Tessera"}`.
   `name` ist der **einzige Pflicht-Key**. **(FEHLT aktuell — Blocker, siehe §2)**
   Quelle: https://www.hacs.xyz/docs/publish/start/
4. **`hacs.json` Key `homeassistant`** (optional): minimale getestete HA-Version; HACS blockt
   Download/Update bei älterem HA. **Für Tessera derzeit bewusst NICHT gesetzt** — die `hacs/action`
   lehnte den Wert als künftiges Minimum ab. Die Private-API-Absicherung (siehe §3) übernimmt der
   **Laufzeit-Guard** `SUPPORTED_HA_AUTH_VERSION` (exakter Match → fail-closed auf `monitor`); der Pin
   kann beim Public-Flip optional nachgezogen werden.
   Quelle: https://www.hacs.xyz/docs/publish/start/
5. **`manifest.json` in `custom_components/tessera/`** mit den HACS-Pflicht-Keys:
   `domain`, `documentation`, `issue_tracker`, `codeowners`, `name`, `version`.
   **(VORHANDEN — alle gesetzt, version=0.1.0)**
   Quellen: https://www.hacs.xyz/docs/publish/integration/ ·
   https://developers.home-assistant.io/docs/creating_integration_manifest/
6. **`manifest.json` `version`** ist für Custom-Integrationen **Pflicht**, AwesomeVersion-valide
   (SemVer/CalVer). Aktuell `0.1.0`. **Muss byte-genau dem späteren Release-Tag entsprechen.**
   Quelle: https://developers.home-assistant.io/docs/creating_integration_manifest/
7. **GitHub-Repo öffentlich (public).**
   Quelle: https://www.hacs.xyz/docs/publish/start/
8. **GitHub-Repo-Description** gesetzt (wird in HACS angezeigt).
   Quelle: https://www.hacs.xyz/docs/publish/start/
9. **GitHub-Topics** gesetzt (Such-Keywords im Store; nicht sichtbar angezeigt).
   Quelle: https://www.hacs.xyz/docs/publish/start/
10. **README** im Repo-Root mit Nutzungs-Informationen. **(VORHANDEN, aber Inhalt prüfen — §2)**
    Quelle: https://www.hacs.xyz/docs/publish/start/
11. **Add-Custom-Repository-Flow** (Installation): 3-Punkte-Menü → „Custom repositories" →
    Repo-URL eingeben → Typ **„Integration"** wählen → „ADD". HACS lehnt ab, wenn die Struktur
    (Punkte 1–3) nicht stimmt.
    Quelle: https://hacs.xyz/docs/faq/custom_repositories/
12. **Download-Ziel:** Integration landet in `<HA-config>/custom_components/`. Danach Einrichtung
    via Settings → Devices & services (config_flow). **HA-Neustart** praktisch nötig, damit die
    Integration geladen wird — **⚠️ UNSICHER:** Die HACS-User-Doku nennt den Restart nicht
    wörtlich (erwähnt nur Browser-Cache-Clear); in der Praxis ist er erforderlich.
    Quelle: https://www.hacs.xyz/docs/use/repositories/type/integration/

### Für Pfad A **empfohlen, nicht zwingend**
- **GitHub-Release v0.1.0** statt nur Branch-Install. Ohne Release nutzt HACS den Default-Branch
  und zeigt einen 7-stelligen Commit-SHA als „Version" (schlechte Update-UX). **Reines Tag-Pushen
  genügt NICHT — es muss ein echtes Release sein.** **(FEHLT — keine Tags/Releases im Repo)**
  Quelle: https://www.hacs.xyz/docs/publish/start/
- **Inline-Brand-Icon** `custom_components/tessera/brand/icon.png` (HA 2026.3+). Für Custom-Repo
  nicht hart erforderlich, aber Polish. **(VORHANDEN — PR #27)**
  Quelle: https://developers.home-assistant.io/blog/2026/02/24/brands-proxy-api/
- **`hacs/action` + `hassfest` CI** (siehe Pfad B Punkt 9–10) — empfohlen, fängt Fehler früh.
  **(VORHANDEN — `validate.yml`, PR #27/#31; HACS-Datei-Check `continue-on-error` bis Public-Flip.)**

---

## 1B. PFAD B — HACS-Default-Store (Pflicht-Checkliste, SPÄTER)

Zusätzlich zu allem aus Pfad A. Jeder Punkt wird durch einen Auto-Check im `hacs/default`-PR
erzwungen.

1. **Repo public** (Check `repository`).
   Quelle: https://www.hacs.xyz/docs/publish/include/
2. **Description gesetzt** (Check `repository`).
   Quelle: https://www.hacs.xyz/docs/publish/include/
3. **Topics gesetzt** (Check `repository`).
   Quelle: https://www.hacs.xyz/docs/publish/include/
4. **README mit Nutzungsinfo** (Check `information`).
   Quelle: https://www.hacs.xyz/docs/publish/include/
5. **GitHub Issues aktiviert** (Check `issues` / `repository`).
   Quelle: https://www.hacs.xyz/docs/publish/include/
6. **Repo NICHT archiviert** (Check `archived`).
   Quelle: https://www.hacs.xyz/docs/publish/include/
7. **Mindestens ein vollwertiges GitHub-RELEASE** (Check `releases`) — Tag allein reicht nicht.
   **„Create a new GitHub release (not just a tag, a full release) after the actions run
   successfully."**
   Quelle: https://www.hacs.xyz/docs/publish/include/
8. **Brand-Assets** (Check `brands`): `brand`-Directory mit mindestens `icon.png` **ODER**
   Fallback auf `home-assistant/brands`. Für Tessera: Inline-Pfad (siehe §Brands).
   Quelle: https://www.hacs.xyz/docs/publish/include/
9. **`hacs/action` (category: integration) grün** — als CI im Repo + Voraussetzung des PR.
   Quelle: https://www.hacs.xyz/docs/publish/action/
10. **`hassfest` (HA-Action) grün** — validiert `manifest.json`.
    Quelle: https://developers.home-assistant.io/blog/2020/04/16/hassfest/
11. **`manifest.json` mit den 6 Pflicht-Keys** (Check `manifest`, + hassfest).
    Quelle: https://www.hacs.xyz/docs/publish/include/
12. **`hacs.json` mit `name`** (Check `HACS manifest`).
    Quelle: https://www.hacs.xyz/docs/publish/include/
13. **PR-Einreicher ist Owner oder Major-Contributor** (Check `owner`). Für Tessera: PR vom
    Owner-Account (`NoSilver78`).
    Quelle: https://www.hacs.xyz/docs/publish/include/
14. **PR muss editierbar sein → NICHT von einem Organization-Account einreichen.**
    Quelle: https://www.hacs.xyz/docs/publish/include/
15. **Fork von `hacs/default`, neuer Branch von `master`, Eintrag in Datei `./integration`**
    (JSON-Liste von `owner/repo`-Slugs).
    Quelle: https://www.hacs.xyz/docs/publish/include/
16. **Eintrag ALPHABETISCH einsortieren** (nicht ans Ende) — Checks `lint jq` (valides JSON) +
    `lint sorted` (Sortierung).
    Quelle: https://www.hacs.xyz/docs/publish/include/
17. **Repo ist KEINE Core-Integration im alpha/beta-Test und überschreibt KEINE Core-Integration.**
    Tessera (eigenständiges RBAC) ist nicht betroffen.
    Quelle: https://www.hacs.xyz/docs/publish/include/
18. **Alle Auto-Checks grün** — „All checks must pass unless otherwise agreed upon with the HACS
    team before the PR was opened."
    Quelle: https://www.hacs.xyz/docs/publish/include/
19. **Nach Merge:** Aufnahme erst beim **nächsten geplanten Scan** (kein sofortiges Erscheinen).
    **⚠️ UNSICHER:** Keine feste Review-/Wartezeit dokumentiert (Maintainer-Kapazität).
    Quelle: https://www.hacs.xyz/docs/publish/include/

> **⚠️ Risiko (aus VALIDATION, kein dokumentiertes Ausschlusskriterium):** Tessera schreibt über
> teils **private/undokumentierte HA-Auth-APIs** in den Auth-Store. Das ist KEIN dokumentierter
> HACS-Default-Ausschluss — die dokumentierten Ausschlüsse betreffen nur „alpha/beta core testing"
> und „override core integrations". Es ist aber **nicht auszuschließen**, dass HACS-Maintainer das
> bei manueller Sichtung thematisieren, da private APIs bei HA-Updates brechen können. Nicht aus
> der Doku verifizierbar; ggf. vorab mit dem HACS-Team klären.

---

## 2. GAP-ANALYSE — was im Repo `/Users/michaelscholz/tessera` fehlt

Quelle der Bestandsaufnahme: lokales Datei-Listing (facet `repo-gap`), 2026-06-30.
`[ ]` = offen/Blocker · `[x]` = bereits vorhanden.

### Blocker für Pfad A (Custom-Repo)
- [x] **`hacs.json` im Repo-Root vorhanden** (`{"name": "Tessera"}`, PR #27). Der optionale
      `homeassistant`-Pin ist bewusst **nicht** gesetzt: die `hacs/action`-Validierung lehnte den Wert
      als künftiges Minimum ab. Die HA-Versions-Absicherung übernimmt stattdessen der Laufzeit-Guard
      `SUPPORTED_HA_AUTH_VERSION` (exakter Match, fail-closed auf `monitor`); ein `hacs.json`-Pin kann
      beim Public-Flip optional nachgezogen werden.
      → `/Users/michaelscholz/tessera/hacs.json`
- [ ] **GitHub-Release / Tag v0.1.0 fehlt.** Keine Tags im Repo; default branch `main`.
      `manifest.json` hat `version=0.1.0`, aber kein passendes Release. Tag-String muss
      **byte-genau** `0.1.0` (bzw. konsistent `v0.1.0`) entsprechen — Konvention einmal festlegen
      und einfrieren (AwesomeVersion vergleicht den Tag; `v0.1.0` vs. `0.1.0` kann fehlordnen).
      → Release über den Sync-/Release-Weg, NICHT vom Mac pushen (siehe §Push-Mechanik).
- [x] **README ist user-facing.** Auf `release-prep` überarbeitet (Install, Sicherheitsmodell,
      Datenschutz). Seit **HACS 2.0.0** rendert HACS die **Repo-Root-`README.md` verbatim** als
      Info-Tab; die Dev-Prozess-Dateien (`CLAUDE.md`, `exchange/`, `reports/`, …) bleiben bewusst im
      Repo (Transparenz), sind aber nicht der Info-Tab.
      Quelle: https://github.com/hacs/integration/issues/3994
- [ ] **GitHub-Description + Topics setzen** (Topics = Store-Such-Keywords). Nicht im lokalen
      Datei-Befund prüfbar — am Repo verifizieren.

### Blocker erst für Pfad B (Default-Store), jetzt schon sinnvoll
- [x] **`hacs/action`-Workflow vorhanden** (`.github/workflows/validate.yml`, Job `hacs`, PR #27/#31).
      Der HACS-Datei-Check ist bis zum Public-Flip `continue-on-error`: `hacs/action` liest
      `hacs.json`/`manifest` **unauthentifiziert** und scheitert am privaten Repo; er wird automatisch
      grün, sobald das Repo öffentlich ist — dann `continue-on-error` entfernen.
- [x] **`hassfest`-Workflow vorhanden** (`validate.yml`, Job `hassfest`) — grün.
- [x] **Brand-Icon vorhanden** (`custom_components/tessera/brand/icon.png` + `icon@2x.png` + `icon.svg`,
      PR #27). `brands` bleibt im HACS-Job ignoriert, bis `tessera` in `home-assistant/brands`
      eingetragen ist (Inline-Pfad deckt HAs Icon-Rendering).
- [x] **LICENSE vorhanden** (MIT, © 2026 Michael Scholz) — auf `release-prep`.
      **⚠️ UNSICHER als HARTER HACS-Gate:** Keine der gefetchten HACS-Check-Listen führt LICENSE
      als Auto-Check. **Aber:** Ohne Lizenz ist der Code rechtlich „all rights reserved" → blockiert
      die Weiterverteilung, die HACS-Distribution impliziert, und scheitert an GitHub Community
      Standards. **Empfehlung:** permissive Lizenz (MIT oder Apache-2.0; HACS selbst nutzt MIT).
      Quelle (Begründung): https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository

### Empfohlene Zusatz-Artefakte (aus VALIDATION „missing")
- [x] **`SECURITY.md`** vorhanden (auf `release-prep`). GitHub Private Vulnerability Reporting noch
      **am Repo zu aktivieren** (Settings → Security). Tessera schreibt in den **Auth-Store**
      (sicherheitskritische RBAC-Fläche) → privater Disclosure-Kanal ist faktische Release-Pflicht.
      Quelle: https://docs.github.com/en/code-security/getting-started/adding-a-security-policy-to-your-repository
- [x] **Datenschutz-/GDPR-Notiz** in der README vorhanden: welche personenbezogenen Daten Tessera liest/schreibt
      (HA-User, Rollen, Area-Zuordnungen), dass alles **lokal** bleibt (keine Cloud/Telemetrie), und
      wo persistiert wird (HA-Auth-Store + eigener `store.py`). Für eine öffentlich (DE/EU)
      verteilte Identity/Permission-Komponente erwartete Transparenz.
- [ ] **`documentation`-URL-Konsistenz prüfen:** `manifest.json` zeigt `documentation` +
      `issue_tracker` auf `https://github.com/NoSilver78/tessera`. hassfest/HACS validieren das
      URL-Format und HACS verlangt ein **public** Repo unter genau diesem Namen → vor Release
      verifizieren, dass `NoSilver78/tessera` existiert und public ist.
      Quelle: https://developers.home-assistant.io/docs/creating_integration_manifest/
- [ ] **Frontend-Asset-Auslieferung absichern:** `custom_components/tessera/static/tessera-panel.js`
      liegt korrekt INNERHALB des Integrationsordners (wird mit ausgeliefert, wird getrackt — nicht
      gitignored). Falls jemals ein Build-Schritt das Asset erzeugt: die **gebaute Datei muss im
      Release/Tag liegen**, da HACS Repo-Inhalt (bzw. Release-ZIP) lädt, nicht den lokalen Build.

### Was NICHT zu tun ist (Korrekturen aus VALIDATION)
- [x] **KEIN `info.md` anlegen.** Seit HACS 2.0.0 wird immer die Root-`README.md` gerendert;
      `info.md` wäre totes Gewicht. (Repo-gap-Item „info.md" → **nicht benötigt**.)
      Quelle: https://github.com/hacs/integration/issues/3994
- [x] **KEIN `render_readme` in `hacs.json`.** Key ist in der aktuellen HACS-Key-Tabelle nicht
      mehr aufgeführt und wird ignoriert.
      Quelle: https://www.hacs.xyz/docs/publish/start/
- [x] **KEIN PR an `home-assistant/brands` für die Custom-Integration.** Der `custom_integrations/`-
      Pfad ist seit HA 2026.3.0 **Legacy**; der korrekte Weg ist das Inline-`brand/`-Verzeichnis.
      Quelle: https://developers.home-assistant.io/blog/2026/02/24/brands-proxy-api/
      **⚠️ UNSICHER:** Die in der RESEARCH genannte Behauptung, ein Workflow
      `close-new-custom-integrations.yml` schließe neue Custom-Brand-PRs **automatisch**, ist in der
      Brands-README **nicht belegt** — nicht als Faktum behandeln. Der Inline-Weg gilt unabhängig
      davon als der richtige.

### Bereits vorhanden (kein Handlungsbedarf)
- [x] `manifest.json` vollständig (domain, name, version=0.1.0, documentation, issue_tracker,
      codeowners=[@NoSilver78], config_flow=true, single_config_entry=true, iot_class=calculated,
      integration_type=service, requirements=[]).
- [x] Integrationscode: genau ein Verzeichnis `custom_components/tessera/` mit 16 Python-Dateien (15 Module + `__init__.py`) +
      `strings.json`, `services.yaml`, `translations/en.json`, `static/tessera-panel.js`.
- [x] README vorhanden (Inhalt aber noch user-facing zu machen, s.o.).
- [x] Code-CI `.github/workflows/ci.yml` (ruff/black/mypy --strict/pytest, Python 3.13).
- [x] Testsuite `tests/` mit 14 Modulen.
- [x] `pyproject.toml` (Tooling-Konfig).

> **Korrektur-Hinweis zu `manifest.json` (aus VALIDATION):** `integration_type` und `iot_class`
> sind **nicht unbedingt Pflicht** (entgegen Teilen der RESEARCH). `integration_type` defaultet bei
> Custom-Integrationen auf `hub`; `iot_class` ist in den aktuellen HA-Docs nicht als „required"
> ausgewiesen. Tessera setzt beide (`service`/`calculated`) — gut, aber kein hassfest-Blocker.
> Quelle: https://developers.home-assistant.io/docs/creating_integration_manifest/

---

## 3. MAINTENANCE — HA-Versions-Tracking wegen der Private-API-Abhängigkeit

Tessera schreibt über **teils private/undokumentierte HA-Auth-APIs** in den Auth-Store
(`auth_adapter.py`, `restore.py`). **HA veröffentlicht KEINEN Stabilitätsvertrag für Interna** —
sie können sich zwischen den monatlichen `YYYY.M`-Releases ändern. Das ist das **zentrale
Wartungsrisiko**. Weder `hassfest` noch `hacs/action` prüfen Laufzeit-/API-Stabilität.

> **⚠️ UNSICHER (aus VALIDATION):** Es gibt **kein** offizielles HA-Dokument, das wörtlich sagt
> „interne APIs haben keine Stabilitätsgarantie". Die folgenden Maßnahmen sind gut belegte Best
> Practice / Community-Konsens, teils abgeleitet — nicht aus einem einzelnen offiziellen Vertrag
> zitiert. Genau **diese fehlende Zusage IST das Risiko.**
> Quelle: https://developers.home-assistant.io/docs/creating_integration_manifest/

### Der Tracking-Prozess (pro HA-Release)
1. **Laufzeit-Guard auf die exakt getestete HA-Version** (`SUPPORTED_HA_AUTH_VERSION`, derzeit
   `2026.6.4`, exakter Gleichheits-Match) — **dies ist die aktive Absicherung.** Vor jedem nativen
   Write geprüft; auf abweichender Version fail-closed → kein Write, `enforce` fällt auf `monitor`.
   **Bei jeder verifizierten neuen HA-Version anheben.** Optionaler Zusatz beim Public-Flip: ein
   Minimum-HA-Pin in `hacs.json` (`"homeassistant": "…"`), der HACS-Download/Update auf älterem HA
   blockt — derzeit **nicht** gesetzt (die `hacs/action` lehnte ihn als künftiges Minimum ab).
   Quelle: https://www.hacs.xyz/docs/publish/start/
2. **Import-Guards um private APIs.** `try/except ImportError` + Feature-Detection um die privaten
   Auth-Imports in `auth_adapter.py`/`restore.py`, sodass ein HA-Upgrade **graceful degradiert**
   statt das Setup hart abstürzen zu lassen.
3. **Test pro HA-Release.** Bei jedem neuen HA-`YYYY.M` (inkl. Betas) die privaten Auth-Pfade
   gegen die neue Version testen. **CI-Hebel:** `hassfest@master` und `hacs/action@main` tracken
   Beta → der nightly `schedule`-Trigger (cron `0 0 * * *`) warnt früh vor Inkompatibilität, ohne
   dass ein Commit nötig ist.
   Quelle: https://www.hacs.xyz/docs/publish/action/
4. **Version-Bump + Changelog bei jedem Bruch.** `manifest.json`-`version` (MAJOR bei
   internem Bruch) anheben, HA-Versions-Anforderung in `CHANGELOG.md` dokumentieren. MAJOR-Bumps an
   Auth-API-Brüche koppeln = sauberstes Signal an Nutzer.
   Quelle: https://developers.home-assistant.io/docs/creating_integration_manifest/
5. **Releases veröffentlichen (nicht nur Tags),** damit Nutzer auf älterem HA auf eine zur ihrer
   HA-Version passende **frühere Release** pinnen können. HACS zeigt die 5 neuesten Releases +
   Default-Branch zur Auswahl.
   Quelle: https://www.hacs.xyz/docs/publish/start/
6. **Version-Sync-Invariante:** Release-Tag == `manifest.json`-`version` (byte-genau). HACS nutzt
   den **Release-Tag** als Remote-Version, HA lädt die **`manifest.json`-version**.
   **⚠️ UNSICHER:** Das Verhalten bei Abweichung ist **nicht dokumentiert** → Gleichheit als
   verbindlich behandeln.
   Quelle: https://www.hacs.xyz/docs/publish/start/

### Dokumentations-Artefakt
- Kurze **Version-Bump-Policy** in `README`/`CONTRIBUTING`: „Minimum-HA wird bei jeder internen
  API-Änderung angehoben; Tessera dokumentiert die getestete HA-Spanne pro Release." Macht die
  Fragilität für Nutzer transparent.

---

## 4. NOT-READY-GATE (ehrlich)

**Tessera ist NICHT release-fertig.** Es gibt zwei Gates: ein **Verteilungs-Gate** (Repo-Hygiene,
oben) und ein **Reife-Gate** (funktionale Erprobung). Der `enforce`-Modus darf erst freigegeben
werden, wenn das Reife-Gate durch ist.

### Gate-1: Verteilungs-Gate (Pfad A installierbar)
**Status: ROT.** Mindestens diese Blocker offen, bevor ein Nutzer überhaupt sicher installieren kann:
- ~~`hacs.json` fehlt~~ → **erledigt** (`{"name": "Tessera"}`, PR #27).
- ~~`hacs/action`+`hassfest`-CI fehlt~~ → **erledigt** (`validate.yml`, PR #27/#31; HACS-Datei-Check
  `continue-on-error` bis Public-Flip).
- ~~Brand-Icon fehlt~~ → **erledigt** (`custom_components/tessera/brand/`, PR #27).
- ~~README noch nicht user-facing~~ → **erledigt** (auf `release-prep`).
- ~~LICENSE fehlt~~ → **erledigt** (MIT, auf `release-prep`).
- **Kein Release/Tag v0.1.0** (noch offen).
- **Repo noch nicht öffentlich** (Public-Flip steht aus; aktiviert zugleich den HACS-Datei-Check).
- **Description/Topics am Repo unverifiziert.**

→ **Erst wenn Gate-1 grün ist**, ist Tessera als Custom-Repo überhaupt sauber installierbar.

### Gate-2: Reife-Gate (enforce erst dev-proven + gesoakt)
**Status: ROT (per Design — operative Empfehlung, kein Code-Lock).** `enforce` (aktives Schreiben in
den Auth-Store) ist die sicherheitskritische Stufe. **Wichtig:** Es gibt **keinen** Reife-Code-Gate,
der das Schreiben sperrt — sobald ein Admin `mode=enforce` setzt **und** die Lauf-Vorprüfungen
(HA-Versions-Guard, D9, Linter, Lockout-Precheck) bestehen, **schreibt** Tessera nativen Auth-Zustand.
Die folgende Reihenfolge ist daher **operative Disziplin** dafür, *wann* man bewusst umschalten
sollte — nicht etwas, das der Code erzwingt:

1. **`off`/`monitor` zuerst.** Tessera nur beobachtend laufen lassen — Resolver/Compiler/Linter
   gegen reale Policy/Rollen, ohne in den Auth-Store zu schreiben.
2. **Dev-proven:** Auf einer **Nicht-Produktiv-HA-Instanz** verifizieren, dass `enforce` exakt die
   beabsichtigten Permissions setzt — inkl. **Restore-/Rollback-Pfad** (`restore.py`), der den
   Auth-Store sauber zurücksetzt.
3. **Gesoakt:** Über mehrere Tage in `monitor` auf der echten Instanz mitlaufen lassen; Diff
   zwischen „würde setzen" und Ist beobachten (`monitor.py`), bis keine unerwarteten Verdicts mehr
   auftreten.
4. **Erst dann `enforce`** auf der produktiven Instanz freischalten — und nur, wenn die HA-Version
   exakt der vom Laufzeit-Guard getesteten Version (`SUPPORTED_HA_AUTH_VERSION`) entspricht;
   andernfalls fällt der Schreibpfad ohnehin fail-closed auf `monitor` zurück.

### Ehrliche Aussage für den Owner
- **Heute auslieferbar:** als **Pfad-A-Custom-Repo im `monitor`-Modus**, sobald Gate-1 grün ist —
  als kontrollierter Early-Access, NICHT als „aktiviere enforce".
- **Noch NICHT auslieferbar:** Default-Store (Pfad B) und `enforce`-als-Default. `hacs.json`,
  HACS+hassfest-CI und Brand-Icon sind erledigt; Default-Store braucht noch Public-Flip + Release +
  Brands-Eintrag (`home-assistant/brands`) + ggf. Maintainer-Klärung zur Private-API-Frage. `enforce`
  ist verdrahtet und schreibt, ist aber bis zum Praxis-Nachweis (Gate-2: Dev-E2E + Soak + Dogfood)
  nicht als Default zu empfehlen.
- **Größtes Restrisiko:** die Private-Auth-API-Abhängigkeit ohne HA-Stabilitätsvertrag (§3) — sie
  ist kein HACS-Blocker, aber der wahrscheinlichste Grund für stillen Bruch nach einem HA-Update.

---

## Anhang: Quellen-Index
- HACS Publish – Integration: https://www.hacs.xyz/docs/publish/integration/
- HACS Publish – Start (hacs.json): https://www.hacs.xyz/docs/publish/start/
- HACS Publish – Include (Default-Store): https://www.hacs.xyz/docs/publish/include/
- HACS Publish – Action (CI): https://www.hacs.xyz/docs/publish/action/
- HACS FAQ – Custom repositories: https://hacs.xyz/docs/faq/custom_repositories/
- HACS Use – Integration type: https://www.hacs.xyz/docs/use/repositories/type/integration/
- HA – Integration manifest: https://developers.home-assistant.io/docs/creating_integration_manifest/
- HA – hassfest: https://developers.home-assistant.io/blog/2020/04/16/hassfest/
- HA – Brands Proxy API (2026.3): https://developers.home-assistant.io/blog/2026/02/24/brands-proxy-api/
- home-assistant/brands README: https://github.com/home-assistant/brands
- HACS integration#3994 (README/info.md): https://github.com/hacs/integration/issues/3994
- GitHub – Licensing a repository: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository
- GitHub – Security policy: https://docs.github.com/en/code-security/getting-started/adding-a-security-policy-to-your-repository
