# Übergabe an Codex — stille Fallbacks auf HA-Interna

Claude · 2026-11-26 · Übergabemodus · Michael hat am 2026-11-26 „an Codex übergeben" entschieden

## Was zu tun ist

Vier Aufgaben, ausformuliert in
[`silent-ha-fallbacks-analyse-claude-2026-11-26.md`](silent-ha-fallbacks-analyse-claude-2026-11-26.md)
**§4** — bitte dort lesen, nicht hier kürzen. Reihenfolge ist nicht beliebig:

| # | Aufgabe | warum in dieser Reihenfolge |
|---|---|---|
| 1 | **Option B** — permissive `getattr`-Fallbacks auf HA-User-Attribute strikt lesen | nimmt die Gefahr weg; alles andere prüft nur |
| 2 | **Option F** — `_ha_contract.py`: Typ-Contract unter `TYPE_CHECKING` | zieht die Entdeckung vor HAs Release; braucht keine neue CI |
| 3 | **Option A** — Verhaltens-Contract für den Permissions-Cache | deckt ab, was eine Form-Prüfung nicht sieht |
| 4 | **Option D** — AST-Scanner gegen neue stille Fallbacks | erst nach 1, sonst ist die Allowlist voll Altlasten |

Aufgabe 3 ist identisch mit Aufgabe 2 aus dem
[Gate Review zu PR #73](gate-review-pr73-auto-recompile-claude-2026-11-26.md) — **einmal** erledigen,
nicht zweimal.

## Erwartung an die Übergabe

- **Eine Aufgabe = ein PR.** `core/*`-Branch, push, `gh pr create`, PR-Body = Abschlussbericht
  (geänderte Dateien · Zusammenfassung · Tests + Ergebnis · Risiken/Annahmen). Nichts nach `main`
  mergen — Claude gate't die PRs.
- **Mutationsprobe ist Pflicht** (QUALITY R6). Jede der vier Aufgaben nennt ihre eigene; das
  Ergebnis gehört in den Abschlussbericht. Eine grüne Suite ohne Mutationsprobe zählt hier nicht als
  Beweis, weil genau diese Fehlerklasse *lautlos* ist.
- **Keine Richtungsentscheidung treffen.** Taucht etwas auf, das die Empfehlung in Frage stellt
  (z. B. ein Double, das sich nicht ohne Logikänderung vervollständigen lässt): nicht umbauen,
  sondern in `exchange/<datum>/` notieren und Michael fragen.

## Der Patch ist Beleg, keine Vorgabe

[`silent-ha-fallbacks-patch-claude-2026-11-26.diff`](silent-ha-fallbacks-patch-claude-2026-11-26.diff)
ist der **validierte** Gesamtstand aller vier Optionen aus einem Wegwerf-Worktree auf
`feat/auto-recompile` (8 Dateien). Er existiert, damit nachprüfbar ist, dass die Empfehlung
durchläuft — nicht, damit jemand ihn blind anwendet.

Du darfst ihn als Referenz nutzen oder Teile übernehmen. Zwei Dinge dabei beachten:

1. Er sitzt auf **`feat/auto-recompile`** (PR #73), nicht auf `main`. Solange der PR offen ist,
   gehören die Änderungen in eigene Branches, nicht in #73.
2. Die Reihenfolge oben bleibt trotzdem gültig: vier PRs, nicht einer. Das hält die
   Mutationsproben einzeln prüfbar.

## Was schon gemessen ist (nicht erneut herleiten)

- Option B: nach dem Strikt-Machen zuerst **7 rote Tests**, alle in `tests/test_mode_manager.py`,
  Ursache ein `FakeUser` ohne `is_active`; **eine Zeile** behebt alle sieben. Danach
  **424 passed, 5 skipped** wie vorher, `ruff`/`black`/`mypy --strict` grün gegen HA **2026.8.2 und
  2026.11.1**. Umfang **+22/−27 in 5 Dateien**.
- Option F: mypy grün auf beiden Linien; Mutationsprobe liefert
  `"User" is missing following "_UserLike" protocol member`. **`Group.policy` ist
  `homeassistant.auth.permissions.types.PolicyType`** — `dict[str, object]` schlägt fehl, das ist
  verifiziert.
- Option A: `models.User(name=…, perm_lookup=None, groups=[], id=…)` baut **ohne `hass`-Fixture**;
  `permissions` landet in `__dict__`, `invalidate_cache()` entfernt es. 5 passed auf 2026.11.1.
- Option D: grün mit genau drei begründeten Allowlist-Einträgen
  (`resolver.py/child_devices`, `d9_gate.py/version`, `id` an drei Stellen).
- Gesamtstand aller vier: **427 passed, 5 skipped**.

## Nicht Teil dieser Übergabe

- Die **irreführende Repairs-Meldung** aus PR #73 (hoher Punkt 1 dort) — eigene Aufgabe, steht im
  Gate Review.
- Die Validierung von **HA 2026.12** — zeitkritisch (HA liefert voraussichtlich am 2. Dezember),
  aber eine andere Baustelle. Der Quellen-Diff liegt vor: `models.py` und `permissions/`
  byte-identisch zu 2026.11.1, `auth_store.py` nur Long-Lived-Token-Debouncing.
