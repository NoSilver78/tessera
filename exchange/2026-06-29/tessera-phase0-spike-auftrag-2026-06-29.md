# Tessera — Phase-0-Spike: Codex-Arbeitspaket (Ping-Pong-Brief)
Stand 2026-06-29 · Ping-Pong: **Propose (Claude) → Implement/Measure (Codex) → Re-Review (Claude)** · Verdikt je Punkt **PASS / FAIL / PARTIAL** mit Code-Beleg

## 0. Auftrag (was dieser Spike ist — und was NICHT)
**Tessera** = standalone HA-RBAC-HACS-Integration (Domain `tessera`), Architektur **Store=SoT → Compiler → native HA-`PolicyPermissions`** (view=read/operate=control echt durchgesetzt, change=global is_admin, kein Monkeypatch). Vollkonzept: **`tessera-konzept-2026-06-29.md`** (gleicher Ordner, 11 Kap.). Beide Agentensysteme (Claude + Codex) konvergierten: **MODIFY → Phase-0-Spike → Go/No-Go**.

**Dieser Spike baut NICHT Tessera.** Er baut die **kleinstmögliche Harness**, die die 12 DoD-Fragen **empirisch auf einer Dev-Instanz** mit Code-Beleg beantwortet — vor allem das **eine echte Restrisiko: den Schreibpfad** (private Auth-Store-API). Ergebnis = Go/No-Go + finale **Fork-vs-Neubau**-Entscheidung.

## 1. Harte Governance (nicht verhandelbar)
- **Dev-Instanz NUR — NIE die Live-CM5.** Auth-Experimente = Lockout-Risiko im echten Familien-Zuhause. Wegwerf-HA **2026.6.4** (= Live-Version) als Container/VM.
- `/Volumes/config` nur **read-only** (Inventar-Abgleich), **keine Secrets/Tokenwerte** ausgeben/committen. Pilzbuche-8-Hardrules (nie vom Mac pushen).
- Schreibzugriffe **nur** auf die Dev-Instanz + den Report nach `outputs/`.

## 2. Dev-Instanz-Setup (Host-Aktion Michael; Codex liefert exakte Schritte)
1. HA **2026.6.4** Container (`ghcr.io/home-assistant/home-assistant:2026.6.4`) oder VM, frisch.
2. Owner `test-owner` + Test-User: `test-admin` (Admin-Gruppe), `test-user` (non-admin), `test-ro` (read-only).
3. Seed-Inventar: ~3 Areas, ~5 Devices, ~20 Entities (Licht/Sensor/Cover/Camera/Lock) + bewusst **einige area-lose** + **einige nur-State (kein Registry-Eintrag)** für die Resolver-Tests. Optional: sekretfreier Subset-Klon des Live-Inventars für Skala.
4. **ACM** (`Darkdragon14/ha-access-control-manager`) installieren = **Schreibpfad-Orakel** (nicht als Basis — als Beleg, wie private Mutation praktisch geht).
5. Ein non-admin **LLAT** für die headless Leak-Tests (D8).

## 3. Der `AuthStoreAdapter`-Contract (Herzstück — der Spike PROVED jede Methode)
Die kleine, **versions-geguardete** Schnittstelle, über die Tessera mit dem Auth-Store spricht. Pro Methode klären: **exakter HA-Core-Aufruf · public vs. private · Restart-Survival · Cache-Wirkung.**

```python
class AuthStoreAdapter:
    HA_VERSION_ALLOWLIST = {"2026.6"}                      # eng starten
    def supported(self) -> bool: ...                        # HA-Version in Allowlist?
    async def ensure_group(self, gid: str, name: str): ...  # create-or-get tessera:role  [auth_store.py:65-71 -> privat?]
    async def set_group_policy(self, gid: str, policy): ... # kompilierte Policy schreiben
    async def remove_group(self, gid: str): ...
    async def set_user_groups(self, uid, group_ids: list): # VOLLE UNION (replace-sicher) [auth_store.py:150-167]
    async def get_user_groups(self, uid) -> list: ...
    async def persist(self): ...                            # _async_schedule_save [auth_store.py:516-547]
    async def invalidate(self, uid: str | None): ...        # Cache-Bust [models.py:80-100]
    async def snapshot(self) -> dict: ...                   # pre_install_snapshot (Mitgliedschaften)
    async def restore(self, snap: dict): ...                # Rescue via PUBLIC async_update_user(group_ids=...)
```
**Frage an den Spike:** Ist `ensure_group/set_group_policy/remove_group` nur über privates `hass.auth._store._groups` + `_data_to_save()` machbar (wie ACM), oder gibt es einen weniger fragilen Pfad? Dokumentiere ACMs konkrete Zeilen in `set_auths.py`.

## 4. Die 12 DoD-Experimente (jeweils: Tun · Messen · Pass-Kriterium · Core-Anker)

| # | Experiment | Pass-Kriterium | HA-Core-Anker |
|---|---|---|---|
| **D1** | `tessera:test`-Gruppe create → Policy setzen → **HA-Restart** → prüfen | Gruppe **+ Policy überleben Restart** | auth_store.py:65-71, 516-547 |
| **D2** | Policy einer Gruppe ändern **ohne** Mitgliedschaftsänderung → `check_entity` eines Mitglieds **ohne Restart** prüfen | deterministischer Invalidierungs-Pfad gefunden (reicht `invalidate_cache(uid)`? invalidiert `_groups`-Mutation automatisch?) | models.py:80-100 |
| **D3** | non-admin: `check_entity(erlaubt,READ)==True`, `(verboten,READ)==False`, dito CONTROL — **über REST + WS + Service-Call**, nicht nur Python-API | alle 3 Transportwege konsistent | api:213-226/242-248, ws commands:351-363/420-465, service.py:672-700 |
| **D4** | User 2 Rollen → `group_ids`=**volle Union** (nicht partiell); 1 Rolle weg → andere überlebt (kein Replace-Lockout); Restore aus Snapshot → zurück in system-users | Union-Semantik + Restore byte-/zustandslogisch belegt | auth_store.py:150-167, config/auth.py:91-140 |
| **D5** | tessera-Store korrumpieren / Setup-Exception → **Rescue greift trotzdem** (`/config/tessera_restore_native` + Boot-Rescue), Mitgliedschaften via public `async_update_user` zurück | Rettung **auch bei kaputtem Tessera-Code/Store** | — (public API) |
| **D6** | non-admin Service-Matrix: Entity-Service (erlaubt/verboten) · `entity_id:all` (nur kontrollierbare gewählt?) · non-entity (`mqtt.publish`/`python_script` — blockiert?) · REST `/api/services/...` **`return_response`** → leakt `changed_states` verbotener Entities? | Execution **und Response** geprüft | service.py:672-735/1008-1015/1068-1071, api:424-455 |
| **D7** | non-admin (UI **und** LLAT) liest **verbotene** Entity via: `render_template` · logbook REST+WS · `config/entity_registry/list` · `subscribe_events` (Allowlist) · history | **Leak-Matrix** dokumentiert (erwartet: template/logbook/registry leaken, history gefiltert) | ws:735-821, logbook ws:282-302/489-519 + rest:68-110, ws:192-212 + events:30-50, config/entity_registry:36-119, history:86-90 |
| **D8** | non-admin **LLAT** erstellen → D7 **headless** durchziehen; 4 Live-LLATs inventarisieren/rotieren | Leaks headless erreichbar bestätigt + LLAT-Rotation dokumentiert | — |
| **D9** | 14 Custom-Components klassifizieren (8 mit `services.yaml`): entity- vs non-entity-Service? User-Kontext? WS/HTTP admin-gated? Response-Seitenpfade? | Allowlist-Kandidaten-Liste | helpers/service.py |
| **D10** | 10–15 Rollen × enumerierte `entity_ids` (worst case ~1100/Rolle) → **`.storage/auth`-Größe + Schreibdauer** auf CM5-Äquivalent; blockiert großer auth-Write andere Auth-Ops? | Schwellwert für `except`→`device_ids` ermittelt (Startwert 200) | — |
| **D11** | Adapter auf **nicht-allowlistete** HA-Version zeigen (z.B. 2026.7-beta-Container) | refuse enforce + **Repairs-Issue** + bleibt `monitor/off` | — |
| **D12** | Roher `groups`-Claim **at/after login** über OIDC lesbar (Seitenkanal)? | by_group **bewiesen** ODER bewusst **aus v1-Enforce raus** (by_user bleibt Baseline) | auth_oidc |

## 5. Rückgabe (Codex → `outputs/tessera-phase0-spike-report-<datum>.md`)
1. **Pro DoD-Punkt:** PASS/FAIL/PARTIAL + Beleg (Core-`file:line`, gemessene Zahlen, exakter Adapter-Aufruf).
2. **Validierter `AuthStoreAdapter`** (lauffähig auf Dev) **oder** die Blocker.
3. **ACM-Schreibpfad** mit konkreten `set_auths.py`-Zeilen belegt.
4. **Leak-Matrix** (bestätigte Leaks) + **Service-Matrix** (geschützt vs. nicht).
5. **CM5-Benchmark-Zahlen** (`.storage/auth`).
6. **Go/No-Go-Empfehlung + finale Fork-vs-Neubau.**

## 6. Rollen & Frage an Codex
- **Codex:** Implementierung/Messung der Harness auf der Dev-Instanz entlang dieser Spec.
- **Michael:** Host-Aktionen (Container starten, Seed, LLAT erstellen, HA-Restarts, CM5-Benchmark-Fenster).
- **Claude:** Re-Review des Spike-Reports → Go/No-Go.

**Frage:** Übernimmst du die Spike-Implementierung? Welche der 12 Punkte brauchen zwingend eine Michael-Host-Aktion (vs. von dir allein machbar)? Und: Reicht dir der `AuthStoreAdapter`-Contract als Schnitt, oder schlägst du einen anderen Choke-Point vor?

## 7. Dev-Instanz (bereitgestellt 2026-06-29, auf dem Mac — läuft bereits)
- Container **`ha-tessera-dev`** · Image **`ghcr.io/home-assistant/home-assistant:2026.6.4`** (= Live-CM5-Version, bestätigt) · UI **`http://localhost:8124`** · Volume `ha-tessera-dev-config` · **isoliert** von `maison-atrium-dev`.
- **Onboarding** (test-owner anlegen) = Michaels einmaliger Schritt vor dem Spike.
- **Auth-Store-Experimente (D1–D5):** `docker exec ha-tessera-dev python -c "…"` bzw. Skript in `/config`; **HA-Restart** (D1) = `docker restart ha-tessera-dev`; HA-Core-Source liegt im Container unter `/usr/src/homeassistant/homeassistant/…`.
- **REST/WS-Tests (D3/D6/D7/D8):** gegen `http://localhost:8124` mit Token des jeweiligen Test-Users bzw. LLAT.
- **Reset:** `docker rm -f ha-tessera-dev && docker volume rm ha-tessera-dev-config`.
- **NICHT** die Live-CM5. **D10** (CM5-`.storage/auth`-Benchmark) + **D12** (echte/Test-Authentik) brauchen separat Michaels Hardware/IdP.
