# Tessera — Dev-E2E-Prüfplan

> ⚠️ **NUR gegen `ha-tessera-dev:8124`. NIEMALS Live-CM5.** Default-Mode bleibt `monitor` bis Schritt 4.
> Rollen: **[C]** = Claude (Verifikation/Inspektion), **[M]** = Michael (alles mit Login/Passwort/UI-Bestätigung), **[C+M]** = gemeinsam.

Ziel: der erste **echte** Enforce-Schreib-Zyklus beweisen — schreiben, durchsetzen, sauber zurücknehmen, Crash-überstehen — auf einer Wegwerf-Instanz, bevor Soak/Dogfood/Release folgen.

## Schritt 0 — Sicherheitsnetz + Beobachtungsweg *(zuerst klären)*
- **[M]** Backup: `.storage/auth` (+ `auth_provider.homeassistant`) der Dev-Instanz kopieren → harter Rollback möglich.
- **[M]** Eine **Owner/Admin-Session offen halten** (eingeloggter Tab) = Lockout-Rettung.
- **[C+M]** Escape-Hatch festlegen: `mode=off` (löst Restore) · Integration entfernen · Boot-Rescue · `.storage/auth`-Backup zurück + HA-Neustart.
- **[C+M] Beobachtungsweg klären (Blocker für die Verifikation):** Wie inspiziere ich den Auth-Store + `tessera.state` der Dev-Instanz? (a) HA-MCP gegen Dev, (b) Datei-/Shell-Zugriff auf den Container, (c) du liest mir `.storage/auth`/State vor bzw. Screenshots. **→ ohne einen dieser Wege kann ich die Hart-Checks nicht selbst machen.**

## Schritt 1 — Install + Setup  **[M install, C verify]**
- Tessera vom `main`-Stand auf `ha-tessera-dev` (HACS-Custom **oder** Copy nach `custom_components/tessera/`), HA-Neustart, Integration „Tessera" hinzufügen.
- **Erwartung:** lädt fehlerfrei · Default-Mode `monitor` · Panel „Tessera" in der Seitenleiste.
- **Verifikation [C]:** `.storage/auth` **unverändert** (kein `tessera:*`-Group) · Log sauber.

## Schritt 2 — Policy + Test-User  **[M]**
- 1 **Nicht-Admin-Test-User** (z. B. `e2e-tester`) · 1 Rolle `viewer` · 1 Area (z. B. `wohnzimmer`) · 1 Grant `viewer × wohnzimmer × view` · Mitgliedschaft `by_user: e2e-tester → viewer`.
- **Erwartung:** Store enthält die Policy · noch **kein** nativer Write (monitor).

## Schritt 3 — Monitor-Verifikation (read-only-Garantie)  **[C]**
- `tessera.recompile` / Panel ansehen.
- **Erwartung:** Matrix zeigt `viewer × wohnzimmer` · kompilierte Vorschau listet die erwarteten `entity_id`s (inkl. area-loser Direkt-Entities) · Linter ok.
- **Hart-Check:** `.storage/auth` **weiterhin unverändert** — Monitor schreibt **nicht**. (Zentrale Monitor-Garantie.)

## Schritt 4 — Enforce-Aktivierung (der scharfe Moment)  **[M setzt, C verifiziert]**
- `mode=enforce` (Options-Flow).
- **Erwartete Sequenz (E3.5):** Version-Gate → Compile → D9-Gate → Linter → **Snapshot (einmalig)** → Journal-mark → **nativer Write** → Journal-clear.
- **Verifikation [C]:**
  1. `tessera:viewer`-Group existiert, `PolicyPermissions` **exakt** = `{"entities":{"entity_ids":{<wohnzimmer-entities>:{"read":true}}}}` (**allow-only**).
  2. `e2e-tester` ist Mitglied von `tessera:viewer` (+ seine Ursprungsgruppen — **No-Drop-Superset**).
  3. **Owner/Admin + `system_generated` unverändert.**
  4. `tessera.state`: `pre_install_snapshot` gesetzt (immutable) · `apply_in_progress=false` (Journal sauber geschlossen).
  5. `last_apply_result.status == "applied"` · **keine** Repairs/fail-safe-Issues.

## Schritt 5 — Durchsetzung wirkt wirklich?  **[M login, C+M bewerten]**
- **[M]** Als `e2e-tester` einloggen (separater Browser/Token — **Claude loggt sich NICHT ein, gibt keine Passwörter ein**).
- **Erwartung:** `e2e-tester` sieht/bedient **nur** die `wohnzimmer`-view-Entities; alles andere verwehrt (allow-only).
- **Ehrlich:** die dokumentierten Leak-Pfade (`render_template`/Logbook/Assist) sind hier **nicht** abgedeckt — wir prüfen die native `check_entity`-Ebene.

## Schritt 6 — Restore via `mode=off`  **[M setzt, C verifiziert]**
- `mode=off`.
- **Verifikation [C]:**
  1. `.storage/auth` **== pre-install** (Vergleich gegen Schritt-0-Backup): keine `tessera:*`-Groups · `e2e-tester`-Gruppen wie vor Schritt 4 · **keine Orphans**.
  2. **Owner/Admin intakt.**
  3. `tessera.state`: Journal sauber.

## Schritt 7 — Crash-Recovery *(optional, aber wertvoll)*  **[C+M]**
- Offenes Journal simulieren: `apply_in_progress=true` in `tessera.state` (+ ggf. ein Teil-Write) → HA-Neustart.
- **Erwartung:** Startup-Recovery erkennt das offene Journal → Restore auf pre-install → Journal-clear → Mode fail-safe auf `monitor`.
- **Verifikation [C]:** nach Neustart **kein Half-State** · Owner/Admin intakt.

## Schritt 8 — Idempotenz + Re-Enforce  **[M setzt, C verifiziert]**
- Erneut `enforce`: `pre_install_snapshot` wird **nicht** überschrieben (immutable) · gleiche Policy → konsistent, kein Schaden.

## Schritt 9 — Soak  **[M+C beobachten]**
- `enforce` über Stunden/Tage laufen lassen, HA-Reloads/Updates beobachten: **kein Drift**, keine fail-safe-Issues, Durchsetzung bleibt. → danach erst **Dogfood auf CM5** (separater Extra-Go) → Release.

## Abbruch/Rollback — jederzeit
`mode=off` → Restore. Notfall: Schritt-0-`.storage/auth`-Backup zurück + HA-Neustart. Die offene Owner-Session ist der Lockout-Schutz.
