# Übergabe an Codex — restliche offene Punkte aus den Gates #73/#74, und die Reihenfolge über alle Stränge

Claude · 2026-11-26 · Übergabemodus · schließt die Zuordnungslücke: alle Codex-Prompts aus den
beiden Gate Reviews haben jetzt einen Strang

## Reihenfolge über alle Stränge

Vier Übergabe-Notizen liegen inzwischen in diesem Verzeichnis. Was zuerst, und warum:

| Rang | Strang | Warum jetzt | Blockiert |
|---|---|---|---|
| **1** | [#73 Auflage 1](pr73-auflage1-handover-claude-2026-11-26.md) — Repairs-Meldung, **in** #73 | Michael hat entschieden: Meldung erst, dann Merge. Hält #73 offen | den Merge von #73 und damit Rang 3 |
| **2** | [HA 2026.12](ha-2026-12-codex-tasks-claude-2026-11-26.md) — Linie validieren, v0.9.6 | **Termin:** HA liefert voraussichtlich 2026-12-02. Issue #76 ist offen und wartet darauf, von einem grünen Lauf geschlossen zu werden | nichts, läuft parallel zu Rang 1 |
| **3** | [Stille HA-Fallbacks](silent-ha-fallbacks-handover-claude-2026-11-26.md) — 4 Aufgaben | größte Risikoreduktion, aber kein Termin | braucht #73 gemergt (der Patch schreibt `_invalidate_permission_cache` um) |
| **4** | **dieses Dokument** — die niedrigen Punkte | kosmetisch bis klein; nichts davon drängt | — |

Rang 1 und 2 können gleichzeitig laufen, sie berühren verschiedene Dateien.

## Rang 4: die niedrigen Punkte

Alle Prompts existieren schon, hier steht nur die Zuordnung. Nicht neu formulieren.

| # | Punkt | Prompt | Bündelung |
|---|---|---|---|
| 4a | Top-Level `permissions: contents: read` in `ci.yml` | [Gate #74](gate-review-pr74-upcoming-auto-issue-claude-2026-11-26.md), Aufgabe 1 | **ein** PR mit 4b — beide fassen nur `ci.yml` an |
| 4b | Issue-Titel neutral fassen (`… nightly upcoming-line check is red`) | [Gate #74](gate-review-pr74-upcoming-auto-issue-claude-2026-11-26.md), Aufgabe 2 | siehe 4a |
| 4c | GUIDE EN/DE: Verhalten bei blockiertem automatischem Recompile dokumentieren | [Gate #73](gate-review-pr73-auto-recompile-claude-2026-11-26.md), Aufgabe 3 | **mit Rang 1** erledigen, nicht danach — der Prompt verlangt ohnehin „erst nach Aufgabe 1", und der neue Repairs-Text soll zitiert werden |

### Zwei Punkte, für die ich *nicht* werbe

Sie stehen als „niedrig" im Gate zu #73, und ich halte sie weiter für vertretbar, wie sie sind:

- **Unbedingtes Leeren des Permissions-Caches bei jedem No-op-Bind.** Kostet Arbeit, erspart aber
  die Frage, ob in diesem Lauf irgendeine Policy geschrieben wurde. Die konservative Richtung ist
  hier die richtige — **nur angehen, wenn es messbar stört.**
- **`async_get_users()` pro Gruppe** in `async_upsert_group`. Bei einstelligen Rollenzahlen und
  zweistelligen Nutzerzahlen irrelevant.

Wenn jemand sie doch anfasst: eigener PR, nicht in eine der oberen Aufgaben einschmuggeln.

## Was absichtlich *keine* Codex-Aufgabe ist

- **`EVENT_USER_REMOVED` abhören**, um Waisen in `membership.by_user` aufzuräumen. Aufgefallen beim
  HA-Review am 25.10., aber das ist ein **Produktvorschlag**, kein Gate-Fund: die Bindings-Schicht
  erkennt Waisen heute schon, nur der Store wird nicht aufgeräumt. Gehört in den ROADMAP-Backlog
  und braucht vorher eine Entscheidung von Michael — nicht hier.
- **Die zweite Hälfte der #74-Auflage** (ein grüner Lauf schließt #76). Das erledigt sich mit Rang 2
  und ist dort als Definition of Done verankert; es ist keine eigene Aufgabe.
- **Der `hacs.json`-Mindestversions-Pin.** Bewusst nicht gesetzt, siehe ADR 0006 und
  `docs/MAINTENANCE.md` Schutzschicht 2. Nicht „nachziehen".

## Regeln, die für alle Ränge gelten

- Eine Aufgabe = ein PR auf `core/*`, push, `gh pr create`, PR-Body = Abschlussbericht. Ausnahme ist
  Rang 1, der ausdrücklich in #73 geht.
- Kein Merge nach `main` — Claude gate't.
- **Mutationsprobe** gehört in jeden Abschlussbericht, wo der Prompt eine nennt (QUALITY R6).
- Keine Richtungsentscheidung selbst treffen. Taucht etwas auf, das eine Empfehlung in Frage stellt:
  in `exchange/<datum>/` notieren und Michael fragen.
