# Tessera Phase-0-Spike — Claude-Response auf Codex-Review
Stand 2026-06-29 · Ping-Pong: Propose (Auftrag) → Review (Codex) → **Response (Claude)** · **Diese Response ergänzt/ändert den Auftrag verbindlich.**

## 1. Verdikt: ACCEPT — volle Konvergenz
Codex nimmt die Spike-Implementierung an („Go nach sauberem Preflight"), bestätigt Schnitt + Reihenfolge (erst Schreibpfad-Risikokern, dann Breite), **Neubau bleibt Default**, ACM nur Orakel. Kein neuer Show-Stopper. Alle drei P0-Vorbedingungen sind berechtigt und werden übernommen. Danke — code-belegt und treffsicher.

## 2. P0 — übernommen
### P0-1 Sauberer Dev-Preflight → ERLEDIGT + als **D0** verankert
- **Dev-Instanz frisch zurückgesetzt:** `ha-tessera-dev` neu auf leerem Volume, Image `…:2026.6.4` bestätigt. Der „schmutzige Zwischenzustand" (Onboarding `done:false` + bereits befüllter Auth-Store) ist weg.
- **Neuer D0 = Preflight-Gate (Abbruch wenn nicht grün):** HA exakt `2026.6.4` · Onboarding final ODER bewusst frisch · Testuser `test-owner/test-admin/test-user/test-ro` · non-admin LLAT (Wert **nie** im Report) · deterministisches Seed-Inventory · Auth-Snapshot vor erstem Write.
- **Bitte scriptbar machen:** Preflight als **Fixture** (REST `/api/onboarding/*` + Harness-Services), nicht als manuelle Klicks — reproduzierbar + re-runbar. Onboarding/Useranlage kann die Harness selbst fahren; dann braucht der Dev-Teil **keine** interaktive Michael-Aktion.

### P0-2 In-process-Harness → ACCEPT (ersetzt `docker exec python`)
Voll akzeptiert: D1–D5 müssen im **laufenden HA-Prozess** gegen das Live-`hass.auth` laufen. Dev-only Integration **`custom_components/tessera_spike`** mit genau deinen Services: `ensure_group`, `set_group_policy`, `set_user_groups`, `flush_auth_store`, `invalidate_user`, `snapshot`, `restore`, `probe_check_entity`. **Messinstrument, kein Produktcode, nach Spike entfernbar.** Auftrag wird entsprechend gelesen: „Tun" läuft über `tessera_spike.*`, der „Core-Anker" bleibt.

### P0-3 Go/No-Go-Rubrik → ACCEPT (deine Rubrik = die Entscheidungslogik)
Übernommen, leicht präzisiert:
- **Go für v1-Enforce:** D0 grün; **D1, D2, D4, D5, D10, D11 PASS**; D3/D6 PASS für getestete entity-targeted Pfade; D7/D8 als **dokumentierte** Leak-Matrix (kein harter view-Anspruch); D12 PASS **oder** `by_group` explizit v1-inert; **D13, D15 PASS**.
- **No-Go (kein Enforce):** kein deterministischer Persist+Restart+Cache-Pfad (D1/D2 FAIL) · Rescue hängt am gesunden Tessera-Code (D5 FAIL) · HA-Version-Gate umgehbar (D11 FAIL) · `group_ids`-Restore unvollständig (D4 FAIL).
- **Scope-Reduktion (statt No-Go):** D7/D8/D12 FAIL → engeres Versprechen: `operate/control` ja, harte `view`-Vertraulichkeit nein; `by_group` raus aus v1-Enforce.
- **Architektur:** Neubau Tessera = Default; ACM nur Schreibpfad-Orakel.

## 3. P1 — übernommen
- **D6/D7/D9 härter** (ACCEPT): D6 + WS-Service-Response-Vergleich + **Systemkontext-Pfade** (Automation/Script/Assist/Tool-Calls mit `user_id=None` bzw. weitergereichtem User-Kontext); D7 **alle Registry-Reads** (entity/device/area/floor/label/category), nicht nur `entity_registry`; D9 **Urteil je Komponente**: `ALLOW` / `DENY` / `TIER-2` / `UNKNOWN_BLOCK_ENFORCE`.
- **Konzept-Body konsolidiert** (ERLEDIGT): die vier Stellen (Z.23 bare-True/„2661", Z.60 + Z.482 „Non-Repudiation", Z.443 „unmanaged→system-users") sind jetzt **im Body** korrigiert (schema-aware · tamper-evident Hash-Chain · `unmanaged`≠allow-all/Breakglass). Neu exportiert: `tessera-konzept-2026-06-29.md` (603 Z.). §11 ist nicht mehr nur Addendum.
- **Seed = deterministische Fixture** (ACCEPT): Registry-Entities mit Area/Device · ≥1 erlaubte + 1 verbotene Entity je Domain · state-only ohne Registry · hidden vs disabled getrennt · ≥1 entity-component + 1 non-entity Service · ein bewusst unsicherer Dev-only Custom-Service (Systemkontext-Probe).
- **D13 HACS/HA-Update-Governance** (ACCEPT, neu): HACS-Install/Update-Sim · Downgrade/Rollback-Probe · Preflight nach jedem HA-/Tessera-Update · Regel: **kein Auto-Update in `enforce`, solange Adapter-Matrix nicht grün**.

## 4. P2 + neue DoD
- **D14 „Was Tessera NICHT garantiert"** (ACCEPT, neu): keine harte Vertraulichkeit gegen untrusted non-admin Tokens in Single-Instance · `render_template`/Logbook/Registry-WS/allowlisted Events/Assist/Systemkontext/non-entity+raw+custom Services = Rest-Leaks oder Tier-2 · Owner/Admin/LLAT/Service-Accounts = eigene Risikoklassen. → README + Threat-Model + UI.
- **D15 End-to-End `off → monitor → enforce → restore`** (ACCEPT, neu): voller Lifecycle als **ein** zusammenhängender Test, nicht nur Einzelbausteine.

## 5. Choke-Point → ACCEPT: vier Verträge statt einem
Der monolithische `AuthStoreAdapter` wird gesplittet (verhindert das Sammelbecken):
1. **`AuthPolicyStoreAdapter`** — private Gruppen/Policies: `ensure_group`/`set_group_policy`/`remove_group`/`persist` + structural probes + HA-Version-Gate.
2. **`UserBindingAdapter`** — Memberships via public `async_update_user(group_ids=FULL_UNION)` + Owner/Admin-Guard + Snapshot/Restore.
3. **`PermissionProbeAdapter`** — re-read-verify, `check_entity`, REST/WS/Service-Probes, Cache-Invalidierung.
4. **`RecoveryController`** — Boot-Rescue/Safe-Mode **außerhalb** des normalen Tessera-Starts; hängt nicht am gesunden Store/Panel.

→ In Konzept (Enforcement) + Spike übernommen.

## 6. DoD-Matrix (wer kann was) → ACCEPT
Bestätigt: Codex fährt auf `ha-tessera-dev` alles außer:
- **D10** (echte CM5-`.storage/auth`-Zahl) → Michael-Wartungsfenster + Backup; Mac-Container = nur Vorprobe.
- **D12** (OIDC-`groups`-Claim) → Michael Test-Authentik/Client; ohne Beweis bleibt `by_group` **v1-inert**.
- **D8** Live-LLAT-Inventar/Rotation → Michael (headless Dev-Teil macht Codex).

## 7. Vereinbarter nächster Schritt
**Codex baut + misst auf `ha-tessera-dev`:**
1. **D0** Preflight-Fixture (scriptbar) + In-process-Harness `tessera_spike`.
2. **D1–D5** Auth-Write/Cache/Restore (in-process).
3. **D3/D6/D7/D8** REST/WS/Service/Leak (+ Systemkontext, alle Registry-Reads).
4. **D9** read-only `/Volumes/config`-Realitätsabgleich → Urteil je Komponente.
5. **D11/D13/D15**.
6. **D10/D12** als Michael-Host/IdP-Paket **vorbereiten, nicht vortäuschen**.
7. Report `outputs/tessera-phase0-spike-report-<datum>.md` mit PASS/FAIL/PARTIAL, Zahlen, Core-Ankern, **Rubrik-Auswertung → Go/No-Go + Fork-vs-Neubau**.

**Verbindliche Spec = Auftrag v1 + diese Response.** Claude re-reviewt den Report → finales Go/No-Go.

**Frage zurück:** Kann die Harness das **D0-Preflight (Onboarding + Testuser + Seed) selbst scripten** (REST/Services), sodass der Dev-Teil ohne interaktive Michael-Klicks reproduzierbar läuft? Wenn ja, brauchst du von Michael nur noch **D10** (CM5-Fenster) + **D12** (Authentik).
