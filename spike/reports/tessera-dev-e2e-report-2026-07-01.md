# Tessera — Dev-E2E-Report (Enforce-Write-Zyklus + CXR-02 + #11)

**Datum:** 2026-07-01 · **Reviewer/Runner:** Claude · **Ziel:** `docs/DEV_E2E_PLAN.md` gegen `main` auf einer echten HA-Instanz beweisen.
**Instanz:** `ha-tessera-dev` (Docker, HA **2026.6.4** = `SUPPORTED_HA_AUTH_VERSION`), Wegwerf-Volume, kein `/Volumes/config`-Bind. **Live-CM5 / maison-atrium-dev unberührt.**
**Evidence:** `spike/evidence/tessera-dev-e2e-evidence-2026-07-01.json`.

## Methode
Frisches Onboarding (Owner-Token, nur Scratchpad — nie committed) → non-admin Test-User mit **realistischer `system-users`-Mitgliedschaft** (QUALITY.md R2) → Rolle `viewer` + Grant `viewer × living_room × read` (via Store-Seed, exaktes Schema aus `schema.py`) → Mode-Wechsel über den **echten Options-Flow** → CXR-02 über die **Matrix-WS**, #11 über die **Services**. Hart-Checks: Auth-Zustand in-memory über `config/auth/list` (autoritativ; die `.storage/auth`-Datei ist ~1 s debounced) + `tessera.state`.

## Ergebnis: ✅ PASS

| Schritt | Beweis |
|---|---|
| 1 Setup | Tessera lädt fehlerfrei auf frischem HA · Default `monitor` |
| 3 Monitor | Policy geladen, **kein** nativer Write — Tester bleibt `system-users`, keine `tessera:`-Groups |
| 4 Enforce | `tessera:viewer` mit **allow-only** Policy (`{read}` nur auf gegrantete Entity) · managed Tester in die restriktive Gruppe **verschoben** · Owner + `system_generated` unangetastet · Snapshot erfasst Original `[system-users]` **verbatim** · Journal sauber |
| 5a **CXR-02** | Matrix-`set_grant` read+control in enforce → native Policy **sofort** `{read,control}` (kein Reload); Gegenprobe read-only → sofort zurück |
| 5b **#11** | un-acked auth-berührende Dummy-Component **blockt** enforce (fail-safe → monitor) · Admin-`acknowledge_component` recorded (version+content_hash) · erneutes enforce **läuft durch** (Ack überstimmt Veto) · `revoke_component_ack` **blockt wieder** · unknown domain **fail-closed** (HomeAssistantError) |
| 6 Restore | `mode=off` → Tester zurück `[system-users]`, `tessera:viewer` entfernt, **`.storage/auth == baseline`** (voll-gleich) |
| 8 Idempotenz | Snapshot immutable — erfasst stets das Original, nie einen enforce-modifizierten Zustand |

## Zwei anfängliche Erwartungen korrigiert (beide by-design, am Code belegt)
1. **Managed Non-Admin behält NICHT `system-users`** — er wird bewusst in die restriktive `tessera:viewer` verschoben (`_target_group_ids_for_user` entfernt `GROUP_ID_USER`; nur `system-admin`/`system-read-only` bleiben erhalten). Das ist die Durchsetzung selbst (breite Default-Gruppe → allow-only). Restore stellt `system-users` wieder her.
2. **Snapshot erfasst nur managed Users** (Owner/`system_generated` übersprungen) — Restore überspringt sie ohnehin. `async_snapshot → snapshot_managed_user_groups`.

*(Beide Korrekturen kamen aus dem E2E selbst — realistische Verifikation schlägt Annahmen. Genau der QUALITY.md-Geist.)*

## Beobachtungen
- **INFO — fail-safe persistiert `monitor`:** Ein D9-Block (oder jeder unsichere Pfad) schreibt `mode=monitor` in die Config + legt ein Repairs-Issue an. Ein Ack allein re-aktiviert enforce nicht; der Admin setzt enforce nach dem Ack **bewusst** erneut. Sicherer, gewollter Flow.
- **LOW — stale native Zustand nach post-apply-Block:** War enforce einmal erfolgreich und wird eine spätere Re-Evaluation von D9 geblockt, fällt der Runtime auf monitor, **lässt aber die zuletzt angewandten (restriktiveren) `tessera:`-Groups stehen**, bis der Admin auflöst und einen sauberen enforce→off-Zyklus fährt. Kein Sicherheits-Downgrade (Zustand = last-good, restriktiver), aber eine kleine UX-Inkonsistenz (monitor angezeigt, native Groups vorhanden). **Empfehlung:** dokumentieren; kein Blocker.

## Fazit
Der **native Enforce-Schreib-Zyklus**, **CXR-02** (Live-Panel-Reapply) und die **#11-D9-Ack-Services** verhalten sich auf echtem HA 2026.6.4 korrekt; Restore ist byte-genau reversibel. Gate-2 (Reife) „dev-proven" ist damit für die aktuellen Features erfüllt. Offen bleibt der **Soak** (mehrtägig in monitor auf der Zielinstanz) vor `enforce`-als-Default sowie das Verteilungs-Gate (Public-Flip/Release).
