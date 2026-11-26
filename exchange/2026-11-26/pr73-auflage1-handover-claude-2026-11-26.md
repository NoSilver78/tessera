# Übergabe an Codex — Auflage 1 aus dem Gate zu PR #73, in #73 selbst

Claude · 2026-11-26 · Übergabemodus · **Entscheidung Michael (2026-11-26): Meldung erst, dann
Merge.** PR #73 bleibt bis dahin offen.

## Was zu tun ist

**Aufgabe 1 aus
[`gate-review-pr73-auto-recompile-claude-2026-11-26.md`](gate-review-pr73-auto-recompile-claude-2026-11-26.md)**
— eigener Repairs-Key für den blockierten automatischen Recompile. Der Prompt steht dort
vollständig; er wird hier **nicht** wiederholt, damit es eine Quelle bleibt.

Ein Unterschied zu allen anderen offenen Aufgaben: das wird **kein neuer PR**. Es geht als
zusätzlicher Commit auf **`feat/auto-recompile`**, also in den bestehenden PR #73.

## Warum in #73 und nicht danach

1. Die Fehlmeldung sitzt in genau dem Code-Pfad, den #73 neu einführt (`keep_enforce_on_block` in
   `_apply_enforce_mode`). Als Folge-PR wäre es ein Nachtrag an frischem Code, den niemand
   gebraucht hätte.
2. Von den zwei hohen Punkten ist das der mit **Betriebsrisiko**: der Admin liest „Tessera fell back
   to monitor mode", während `enforce` läuft und eine Drift unkorrigiert bleibt — die Richtung, in
   der man den Ist-Zustand *unterschätzt*. Das soll nicht erst mit dem nächsten PR verschwinden.
3. Claude schreibt es nicht selbst: der Pfad ist sicherheitsnah, und nach
   [QUALITY.md](../../docs/QUALITY.md) **R7** braucht so eine Änderung zwei unabhängige Reviews.
   Wer sie schreibt, kann nicht der unabhängige Reviewer sein.

## Zusätzlich im selben Commit erledigen

**`main` in den Branch mergen.** #73s acht grüne Checks stammen vom 15.11. gegen die Basis
`5e4240f` — also vor dem Merge von #74. Der Vorsprung von `main` betrifft nur `ci.yml`,
`docs/MAINTENANCE.md` und die exchange-Dokumente, und keine dieser Dateien wird von #73 angefasst
(`mergeable=MERGEABLE`, `status=CLEAN` geprüft). Der Merge ist also konfliktfrei und sorgt dafür,
dass CI einmal gegen den **aktuellen** Stand läuft, inklusive der mit #74 erweiterten `ci.yml`.

## Danach

1. Claude gate't den zusätzlichen Commit (Review + CI grün).
2. Dann Merge nach `main` — Squash, wie die bisherige Historie.
3. Erst **nach** diesem Merge wird der Fallback-Strang frei: der validierte Patch in
   [`silent-ha-fallbacks-patch-claude-2026-11-26.diff`](silent-ha-fallbacks-patch-claude-2026-11-26.diff)
   sitzt auf `feat/auto-recompile` und schreibt `_invalidate_permission_cache` um — eine Funktion,
   die es erst mit #73 gibt. Aufgabe 1 des Fallback-Strangs hängt also an diesem Merge.

## Nicht Teil dieser Aufgabe

- **Auflage 2** aus demselben Gate (Contract-Test für den Permissions-Cache) — die ist als Aufgabe 3
  im [Fallback-Strang](silent-ha-fallbacks-handover-claude-2026-11-26.md) übergeben und dort breiter
  gedacht (alle elf Fallbacks statt nur `invalidate_cache`). **Nicht** doppelt erledigen.
- Die zwei niedrigen Punkte aus dem Gate zu **#74** (Top-Level-`permissions` in `ci.yml`,
  neutralerer Issue-Titel) — noch keinem Strang zugeordnet, nicht dringend.
