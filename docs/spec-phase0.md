# Technische Spezifikation — Tessera Phase-0-Spike

> **Architekturmodus → Übergabemodus.** Konsolidiert die 8 Ping-Pong-Runden (Auftrag + Reviews + Responses) in **eine** verbindliche Spec. Vollprodukt-Konzept: `tessera-konzept-2026-06-29.md`. Diese Spec deckt **nur Phase 0 (Spike)** ab. Stand 2026-06-29.

## Ziel
Das eine harte Restrisiko **empirisch entscheiden, bevor Produktcode entsteht**: Funktioniert der private Auth-Store-Schreibpfad (Gruppen-Policy schreiben · Mitgliedschaft als volle Union · Cache-Invalidierung · Restart-Survival · Rescue) — und halten die tragenden HA-Core-Annahmen auf einer **Dev-Instanz**? Ergebnis: **Go/No-Go für v1-Enforce + finale Fork-vs-Neubau-Empfehlung.** Kein Produktbau.

## Anforderungen

### Muss-Anforderungen
- **M1 — D0-Preflight** als Skript-Artefakt: harte Target-Isolation · exakte Fresh-Baseline-Allowlist · REST-Onboarding + Seed · sanitized Snapshot · tokenfreie Evidence · Restore/Recreate-Proof · fail-closed.
- **M2 — In-process-Harness** `custom_components/tessera_spike` (8 Services) gegen das laufende `hass.auth` — Messinstrument, nach Spike entfernbar.
- **M3 — D1–D5** Auth-Write / Cache / Restore **in-process**.
- **M4 — D3/D6/D7/D8** Durchsetzung + Leak-Matrix über **REST + WS + Service** (+ Systemkontext, alle Registry-Reads).
- **M5 — D9** Custom-Component-Klassifikation: je Komponente `ALLOW / DENY / TIER-2 / UNKNOWN_BLOCK_ENFORCE`.
- **M6 — D11/D13/D15**: Version-Gate · HACS-Update-Governance · E2E `off→monitor→enforce→restore`.
- **M7 — Evidence** je Kriterium PASS/PARTIAL/FAIL + Exit-Code/Abbruchgrund, **ohne Secret-Werte**.
- **M8 — Governance:** nur `ha-tessera-dev` · `/Volumes/config` read-only · keine Tokenwerte · **nie Live-CM5**.

### Soll-Anforderungen
- **S1** D0 voll scriptbar (REST-Onboarding, keine manuellen Klicks).
- **S2** ACM-Schreibpfad mit konkreten `set_auths.py`-Zeilen belegt (Regression-Orakel).
- **S3** 4-Adapter-Schnitt im Spike erkennbar vorbereitet.

### Nicht-Ziele
- Produktbau · HACS-Enforce · **Live-CM5-Write** · `by_group`-Enforce.
- **D10** (CM5-`.storage/auth`-Benchmark) + **D12** (OIDC-`groups`) → **menschliche Pakete**, nicht im Dev-Lauf.
- Harte `view`-Vertraulichkeit gegen untrusted Tokens (= Tier-2, außerhalb dieses Produkts).

## Annahmen
- HA **2026.6.4** = Live-Version. **Virgin-Baseline** = genau **1 `system_generated`-User „Home Assistant Content"** (system-read-only) + 1 `system`-Token + 3 Systemgruppen, Onboarding offen (quell-belegt: `http/auth.py` `CONTENT_USER_NAME` / `async_setup_auth`; `auth/__init__.py` System-Token-only).
- `group_ids` ist **Replace** → volle Union schreiben. **Keine** public Gruppen-CRUD (privat `_store._groups` + `_data_to_save`). `operate/control` = echte Grenze; `view` begrenzt.

## Risiken und offene Punkte
| Risiko / Punkt | Auswirkung | Empfehlung |
|---|---|---|
| Schreibpfad privat/instabil | ganzes Produkt steht/fällt | **= Kern des Spikes** (D1/D4); Adapter version-geguarded |
| Cache-Invalidierung unklar | Policy-Change wirkt nicht ohne Restart | D2: deterministischen Pfad finden (`invalidate_cache`/`_groups`) |
| view-Leaks (template/logbook/registry) | view nicht untrusted-grade | D7 dokumentieren → **Scope-Reduktion, nicht No-Go** |
| Write auf falschen/Live-Container | echter Schaden | D0 hartes Isolations-Gate → `FAIL_TARGET_ISOLATION` |
| unerwarteter System-/Owner-User | Baseline-Fehlklassifikation | `FAIL_BASELINE_ANOMALY` statt stiller Annahme |
| Custom-Service ohne User-Kontext | Enforce-Lücke | D9 → `UNKNOWN_BLOCK_ENFORCE` |

## Architekturentscheidung
**Getrennte Sequenz:** (1) **externer D0-Bootstrap** (Isolation → Baseline → Onboarding → Token → Seed → Snapshot) → (2) **Harness-Install/Load-Check** → (3) **in-process D1–D9** via `tessera_spike`. Der Auth-Choke-Point wird als **vier kleine Verträge** modelliert (kein Monolith): `AuthPolicyStoreAdapter` · `UserBindingAdapter` · `PermissionProbeAdapter` · `RecoveryController`. Enforcement bleibt **Store → Compiler → native Policy**.

## Begründung der Architektur
- Ein Custom-Component-Harness existiert **nicht vor** Onboarding/Install/Reload → der Bootstrap muss zuerst **extern** laufen (sonst nicht diagnostizierbar).
- D1–D5 brauchen das **laufende** `hass.auth` (Cache, `User.permissions`, lebende Gruppenobjekte) → **in-process**, nicht `docker exec python`.
- Vier Verträge verhindern ein „AuthStoreAdapter"-Sammelbecken aus Auth/Recovery/Probing/Produktlogik; der **RecoveryController** liegt bewusst **außerhalb** des normalen Tessera-Starts (Rescue darf nicht am gesunden Store hängen).

## Modulstruktur
| Modul | Aufgabe | Schnittstellen | Risiken |
|---|---|---|---|
| `d0_bootstrap` (extern) | Isolation-Gate, Baseline-Allowlist, Onboarding, Seed, Snapshot, Evidence | Docker-CLI, HA-REST `/api/onboarding/*` | falscher Container/Bind → fail-closed |
| `tessera_spike` (in-process) | 8 Mess-Services gegen `hass.auth` | HA Service/WS-Registry | Harness ≠ Produkt; muss entfernbar sein |
| `AuthPolicyStoreAdapter` | private Gruppen/Policies + Version-Gate | `hass.auth._store` | privat → fragil, version-geguarded |
| `UserBindingAdapter` | Membership via public `async_update_user(group_ids=UNION)` | public Auth-API | Replace-Lockout, Owner-Guard |
| `PermissionProbeAdapter` | check_entity, REST/WS/Service-Proben, Cache-Bust | HA-APIs | Transport-Inkonsistenz |
| `RecoveryController` | Boot-Rescue außerhalb Tessera-Start | File-Trigger/Boot-Hook | darf nicht am Store/Panel hängen |
| `evidence` | PASS/PARTIAL/FAIL, Redaction | JSONL/MD | Secret-Leak → Redaction-Gate |

## Datenmodell / Konfiguration
- **Baseline-Allowlist (D0):** `ha_version=2026.6.4` · Image-Allowlist · `expected_system_users=[{name:"Home Assistant Content", system_generated:true, is_owner:false, group:"system-read-only", credentials:0}]` · `non_system_users=0` · `owners=0` · `non_system_tokens=0` · `onboarding_store=absent`.
- **Evidence-Schema:** Version/Image/Container-ID(kurz)/Mount-Klasse/Port · Onboarding vor/nach · Auth-Metadaten vor/nach (Counts/Klassen/Flags, **keine** IDs/Tokens) · Token-Klassen + Revocation (nie Werte) · PASS/PARTIAL/FAIL je Kriterium · Exit-Code/Grund.
- `.storage/auth`: nur Zähler/Flags lesen, nie Werte.

## Fehlerbehandlung
**Fail-closed, kein Write bei:** `FAIL_TARGET_ISOLATION` (Name/Image/Volume/Port/Bind falsch) · `FAIL_BASELINE_ANOMALY` (non-system User/Token, unerwarteter Owner/`system_generated`) · fehlende Secret-Redaction · fehlender Snapshot/Restore-Pfad. **Re-Read** des Auth-States **direkt vor** dem ersten Write. Bei Tessera-internem Fehler → `mode=off` (nativ unverändert), **nie** alles-deny.

## Security / Secrets
- **Nur** `ha-tessera-dev` (Docker-Volume, Port 8124, lokal) — **kein** Bind nach `/Volumes/config`/Maison/Atrium. **Nie Live-CM5.**
- Keine Token-/Passwort-/`auth_code`-Werte in Argv/Logs/Evidence/Chat. `/Volumes/config` strikt read-only. LLAT-Werte nie im Report.

## Teststrategie
- **D0-Exit-Gate v1 (12 Punkte)** als hartes Tor: Target-Isolation · exakte Baseline · keine non-system User/Tokens · kein Owner · Onboarding offen · REST-Onboarding ok · Token-Exchange ok/ungeloggt · Seed ok · Harness geladen/markiert · Post-Snapshot ohne Secrets · Restore/Recreate bewiesen · Report PASS/PARTIAL/FAIL.
- Je **D1–D15**: PASS/PARTIAL/FAIL mit Core-`file:line`-Anker + gemessenen Zahlen. **D8/D9/Rescue/LLAT behalten eigene Gates** — D0-GREEN startet den Lauf, nimmt ihn nicht fachlich ab.

## Akzeptanzkriterien
- **D0-GREEN** = alle 12 Gate-Punkte grün → D1–D9-Dev-Lauf darf **starten**.
- **Go für v1-Enforce (Rubrik):** D1,D2,D4,D5,D11 PASS · D3/D6 PASS (entity-targeted) · D7/D8 dokumentierte Leak-Matrix · D13,D15 PASS · D12 PASS **oder** `by_group` v1-inert · D10 als Michael-Paket.
- **No-Go:** kein deterministischer Persist+Restart+Cache (D1/D2) · Rescue hängt am gesunden Code (D5) · Version-Gate umgehbar (D11) · Union-Restore unvollständig (D4).
- **Scope-Reduktion statt No-Go:** D7/D8/D12 FAIL → `operate/control` ja, harte `view` nein; `by_group` raus.
- **Architektur:** Neubau Default; ACM nur Orakel.

## Umsetzungsschritte für Codex
1. **D0-Bootstrap-Skript** (extern): Isolation-Gate → Baseline-Allowlist → (recreate-from-scratch optional) → REST-Onboarding (`POST /api/onboarding/users` → `auth_code` → Token) → Seed-Fixture → sanitized Snapshot → Evidence. Fail-closed.
2. **`tessera_spike`-Harness** installieren + Load-Check (Reload/Restart); 8 Services bereitstellen.
3. **D1–D5** in-process: Gruppe/Policy/Restart-Survival · Cache-Invalidierung · check_entity-Proben · group_ids-Union/Restore · Rescue bei kaputtem Store.
4. **D3/D6/D7/D8**: REST+WS+Service-Konsistenz · Service-Matrix (+Systemkontext, `return_response`) · Leak-Matrix (alle Registry-Reads, render_template, logbook, history) · LLAT-headless.
5. **D9**: 14 Komponenten klassifizieren (Urteil je Komponente, Laufzeitbeleg).
6. **D11/D13/D15**: Version-Gate · HACS-Update-Sim/Rollback · E2E-Lifecycle.
7. **D10/D12** als Michael-Host/IdP-Paket **vorbereiten** (nicht vortäuschen).
8. **Report** `outputs/tessera-spike-report-YYYY-MM-DD.md`: PASS/PARTIAL/FAIL, Zahlen, Core-Anker, **Rubrik-Auswertung → Go/No-Go + Fork-vs-Neubau**.

## Erste Codex-Aufgabe
```text
Baue und führe den Tessera Phase-0-Spike auf der Dev-Instanz `ha-tessera-dev` (HA 2026.6.4, Docker, Port 8124) aus. NIE die Live-CM5; /Volumes/config read-only; keine Token-/Passwortwerte in Logs/Evidence. Bei jeder Unklarheit: fail-closed, kein Auth-Write.

SCHRITT 1 — D0-Bootstrap-Skript (extern, fail-closed):
- Target-Isolation hart prüfen: Containername == ha-tessera-dev; Image in Allowlist {ghcr.io/home-assistant/home-assistant:2026.6.4}; /config == Docker-Volume ha-tessera-dev-config (KEIN Bind nach /Volumes/config, Maison, Atrium); Host-Port 8124; Ziel-URL lokal. Bei Abweichung: FAIL_TARGET_ISOLATION, kein Write.
- Fresh-Baseline exakt allowlisten: /config/.storage/onboarding fehlt; GET /api/onboarding alle done:false; genau 1 system_generated-User "Home Assistant Content" (is_owner:false, is_active:true, Gruppe system-read-only, keine Credentials); 0 non-system User; 0 Owner; 0 non-system Refresh-Tokens; System-Tokens nur in erwarteter Form. Sonst FAIL_BASELINE_ANOMALY.
- Onboarding scripten: POST /api/onboarding/users (unauth) → auth_code → Token holen → restliche Schritte. Deterministische Seed-Fixture: Registry-Entities mit Area/Device; je Domain ≥1 erlaubte + 1 verbotene; state-only ohne Registry; hidden vs disabled; ≥1 entity-component + 1 non-entity Service; 1 bewusst unsicherer Dev-only Custom-Service.
- Sanitized Snapshot der Mitgliedschaften VOR dem ersten Write. Re-Read des Auth-States direkt vor dem ersten Write.
- Evidence-Datei (Schema: Version/Image/Container-ID kurz/Mount-Klasse/Port; Onboarding vor/nach; Auth-Metadaten vor/nach als Counts/Klassen/Flags OHNE IDs/Tokens; Token-Klassen+Revocation ohne Werte; PASS/PARTIAL/FAIL je Kriterium; Exit-Code+Grund).

SCHRITT 2 — Harness: custom_components/tessera_spike installieren, HA reload/restart, Load-Check. 8 Services: ensure_group, set_group_policy, set_user_groups (volle Union), flush_auth_store, invalidate_user, snapshot, restore, probe_check_entity. Reines Messinstrument, nach Spike entfernbar.

SCHRITT 3 — Nur bei D0-GREEN (alle 12 Exit-Gate-Punkte): dev-only D1–D9 automatisiert messen:
- D1 Gruppe+Policy create → HA-Restart → Survival. D2 Policy-Change ohne Membership → check_entity ohne Restart (Invalidierungspfad). D3 check_entity erlaubt/verboten × READ/CONTROL über REST+WS+Service. D4 group_ids volle Union + Restore-to-native. D5 Rescue bei kaputtem Store/Setup-Exception.
- D6 Service-Matrix (entity/all/non-entity, return_response-Leak, WS-Response, Systemkontext user_id=None/Automation/Script/Assist). D7 Leak-Matrix non-admin (UI+LLAT): render_template, logbook REST+WS, alle Registry-Reads (entity/device/area/floor/label/category), history. D8 LLAT headless.
- D9 je Custom-Component: ALLOW/DENY/TIER-2/UNKNOWN_BLOCK_ENFORCE (Laufzeitbeleg, keine finale Live-ALLOW nur aus statischer Analyse).
- D11 unsupported HA-Version → refuse enforce + Repairs + monitor/off. D13 HACS-Update-Sim/Downgrade/Rollback. D15 E2E off→monitor→enforce→restore.
- D10 (CM5-.storage/auth-Benchmark) + D12 (OIDC-groups-Claim) NICHT faken — als Michael-Host/IdP-Paket vorbereiten.

SCHRITT 4 — Report nach outputs/tessera-spike-report-YYYY-MM-DD.md: je D1–D15 PASS/PARTIAL/FAIL mit HA-Core-file:line-Anker + Zahlen; validierter Adapter-Schnitt (AuthPolicyStore/UserBinding/PermissionProbe/Recovery) oder Blocker; ACM-set_auths.py-Zeilen; Leak-/Service-Matrix; dann Rubrik-Auswertung → Go/No-Go für v1-Enforce + finale Fork-vs-Neubau-Empfehlung.

Verbindliche Spec: diese Datei + tessera-phase0-SPEC-2026-06-29.md + tessera-konzept-2026-06-29.md. Lifecycle der Dev-Instanz liegt bei dir.
```
