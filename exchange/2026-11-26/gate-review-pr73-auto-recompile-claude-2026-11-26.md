# Gate Review — PR #73 `feat(auto-recompile): recompile on registry and user changes, so grants cannot drift`

Claude · 2026-11-26 · Gate-/Auditmodus · Branch `feat/auto-recompile` → `main` · +893/−15 in 12 Dateien
· geprüft gegen die 16 Kriterien (`CLAUDE_WORKFLOW.md` §2) · zweites Review im Sinne von
[QUALITY.md](../../docs/QUALITY.md) **R7**

## Entscheidung

**PASS MIT AUFLAGEN**

## Kurzbewertung

Der PR schließt O1/O2 aus dem Gate vom 15.11. und schließt sie **richtig**: der kompilierte
`tessera:`-Zustand war eine Momentaufnahme der Registries und blieb gültig, bis jemand von Hand
nachkompilierte — Zugriff konnte also nach **oben** driften (Entity verlässt die Area und behält
`read`, eine neue Entity erbt per wiederverwendeter ID einen Grant, ein unter `enforce` neu
angelegter Nutzer behält HAs `system-users` = allow-all). Die Richtung der Wirkung ist damit
**verengend**, und das ist für ein Rechteprodukt die richtige Richtung.

Architekturtreue: der automatische Lauf geht durch **denselben** gegateten Pfad wie
`tessera.recompile` (`mutation_lock` → Modus-Handling → Fail-Safe), nicht an ihm vorbei. Kein
zweiter Schreibweg in die native Auth-Schicht, keine Änderung am Compiler, an `_assert_allow_only_policy`
oder an den Lockout-Prechecks. Modulgrenzen stimmen: `auto_recompile.py` kennt nur Events, Debouncer
und ein `recompile`-Callable — es weiß nichts über Stores, Policies oder Adapter.

Besonders anerkennen will ich die drei Funde, die der PR **selbst** mitbringt (Debouncer-Job-Typ,
Permissions-Cache, blockierter Lauf unter laufendem `enforce`) — jeder mit einem eigenen
Regressionstest, und der Cache-Fund ist der, der ohne e2e-Test gegen echtes HA nicht auffällt.
Die Tests sind nicht Dekoration: `test_auto_recompile_e2e.py` fährt echte Registries, echten
`AuthStore`, echten Bus und echten Debouncer.

Auf Auflagen setze ich den Gate wegen zwei Punkten, die beide **nicht** die Mechanik betreffen,
sondern das, was der Admin im Fehlerfall sieht bzw. nicht erfährt:

1. Der neue „blockiert, aber `enforce` bleibt"-Pfad meldet sich über die **Repairs-Meldung der
   Fail-Safe**, die wörtlich das Gegenteil behauptet.
2. Der Permissions-Cache-Fix hängt an `User.invalidate_cache` — über `getattr(..., None)`, also
   **lautlos**, wenn HA das umbenennt, und kein Contract-Test deckt es ab.

Nachgerechnet habe ich lokal auf dem Branch: `ruff` ✅, `black` ✅, `mypy --strict` ✅ (19 Dateien),
**424 passed, 5 skipped**, Secret-Scan über den Diff sauber. Die Zahlen des PR stimmen.

## Kritische Punkte

| Bereich | Problem | Auswirkung | Konkrete Korrektur |
|---|---|---|---|
| — | keine | — | — |

## Hohe Punkte

| Bereich | Problem | Auswirkung | Konkrete Korrektur |
|---|---|---|---|
| Fehlerbehandlung / Betriebsfähigkeit (7, 14, 13) | Der blockierte automatische Lauf ruft `_record_repair_issue(..., REPAIR_ENFORCE_FAIL_SAFE, reason="auto_recompile_blocked:…")`. Dessen Text (`strings.json` → `enforce_fail_safe`) lautet: **„Tessera fell back to monitor mode"** / „…and **persisted monitor mode**". In diesem Pfad bleibt der Modus aber **`enforce`**, und der letzte angewandte Zustand bleibt live — exakt das Gegenteil | Der Admin liest im Repairs-Center, Tessera erzwinge nichts mehr, während die Durchsetzung läuft; und er erfährt **nicht**, was tatsächlich gilt (letzter Stand aktiv, Drift bis zum Aufheben der Blockade unkorrigiert). Für ein Rechteprodukt ist das die gefährlichere Richtung der Falschmeldung: man unterschätzt den Ist-Zustand | Eigener Issue-Key, z. B. `REPAIR_ENFORCE_BLOCK_PENDING` → `enforce_block_pending`, in `strings.json` **und** `translations/en.json`. Titel/Text: „Tessera could not recompile — enforce stays on the last applied state", Reason-Platzhalter behalten. Im e2e-Test `test_a_blocked_auto_recompile_keeps_enforce_and_retries` zusätzlich den Issue-Key assertieren (heute prüft er Modus, Store und Gruppen, nicht die Meldung) |
| Security / Tests (8, 9, 15) | Der Cache-Fix ruft `getattr(user, "invalidate_cache", None)`. Verschwindet oder wandert die Methode, wird daraus ein **lautloses No-op** — kein Fehler, kein Log. Die Folge ist genau der Fehler, den dieser PR als „Critical" behebt: eine in place verengte Policy gewährt weiter, bis HA neu startet. `tests/test_ha_auth_contract.py` deckt `models.Group`, `AuthStore`-Interna und `PolicyPermissions` ab — **nicht** `User.invalidate_cache` und nicht, dass `User.permissions` gecacht ist | Das Schutznetz des Projekts (Guard + Contract-Tests pro Linie + Nightly) hat ein Loch genau dort, wo dieser Fix wirkt. Heute stabil: `auth/models.py` ist zwischen 2026.11.1 und 2026.12.0b0 byte-identisch, `invalidate_cache()` existiert und leert `permissions`/`is_admin` aus `__dict__` (geprüft) | In `tests/test_ha_auth_contract.py` ergänzen: `models.User` hat ein aufrufbares `invalidate_cache`; `User.permissions` ist ein `cached_property`; nach `invalidate_cache()` ist der Cache-Eintrag aus `__dict__` verschwunden. Läuft damit in der Matrix über alle validierten Linien **und** nightly gegen die kommende |

## Mittlere Punkte

| Bereich | Problem | Auswirkung | Konkrete Korrektur |
|---|---|---|---|
| — | keine | — | — |

## Niedrige Punkte

| Bereich | Problem | Auswirkung | Konkrete Korrektur |
|---|---|---|---|
| unnötige Komplexität / Effizienz (12) | `async_bind_full_superset` leert den Permissions-Cache **jedes** No-op-Binds, also bei jedem automatischen Lauf für jeden verwalteten Nutzer — auch wenn in diesem Lauf keine Policy geschrieben wurde | HA baut `permissions` je Nutzer neu auf; bei 2-Sekunden-Debounce und geschwätzigen Registries unnötige Arbeit. **Korrektheitsseitig die sichere Richtung** (nie veraltete Rechte ausliefern), daher nur niedrig | Optional: den Apply-Lauf mitführen lassen, ob eine `tessera:`-Policy tatsächlich geschrieben wurde, und nur dann invalidieren. Nur angehen, wenn es messbar stört — die konservative Variante passt zur Charta |
| Effizienz (12) | `async_upsert_group` ruft `self._hass.auth.async_get_users()` **pro Gruppe** und iteriert alle Nutzer | Bei N Rollen × M Nutzern N Durchläufe; in realistischen Größen (einstellige Rollen, zweistellige Nutzer) irrelevant | Optional: Nutzerliste einmal pro Apply holen und an die Adapter übergeben |
| Dokumentation (13) | `GUIDE.md`/`GUIDE.de.md` nennen die 2 Sekunden im Troubleshooting. Die neue Betriebseigenschaft „blockierter automatischer Lauf hält `enforce` und meldet via Repairs" steht nur im Code-Docstring | Admins finden das Verhalten erst, wenn sie es erleben | Im Guide-Abschnitt „was zu beachten ist" zwei Sätze ergänzen — sinnvollerweise zusammen mit dem neuen Repairs-Text aus Auflage 1 |

## Positive Beobachtungen

- **Der Debouncer-Fund ist der wertvollste Teil des PR.** Ein `lambda`, das eine Coroutine
  zurückgibt, wird von HAs `Debouncer` als Executor-Job eingeordnet und nie awaited — das Feature
  hätte **gar nicht** funktioniert und wäre im Betrieb als „tut nichts" aufgefallen, nicht als
  Fehler. Gefunden hat es der e2e-Test, und `test_init` hält jetzt den Job-Typ fest. Genau so soll
  ein Test wirken.
- **Der Event-Filter deckt den Resolver vollständig ab**, inklusive `parent_device_id` — die
  Child-Device-Vererbung aus v0.9.5 ist mitgedacht. Ein Area-Wechsel am Eltern-Gerät feuert über
  `area_id`, die Kinder erben mit.
- **Unbekannte Event-Form ⇒ recompile** (`_changes_touch` gibt bei fehlendem/fremdem `changes`-Feld
  `True` zurück). Fail-safe in die richtige Richtung: lieber einmal zu viel rechnen als eine
  Änderung verpassen.
- **Kein Reentranz-Risiko beim Lock.** Ich habe das ganze Paket nach `async_reload`,
  `async_unload` und `add_update_listener` durchsucht: es gibt keinen Aufruf. Der `mutation_lock`
  um `async_unload_entry` kann sich also nicht selbst blockieren; er verzögert ein Unload höchstens
  um die Dauer eines Applys.
- **`keep_enforce_on_block` ist korrekt eingeschränkt** auf `previous_mode == MODE_ENFORCE`. Ein
  blockierter *Wechsel* nach `enforce` fällt weiterhin auf `monitor` zurück, nur ein **laufendes**
  `enforce` bleibt stehen. Manuelle Pfade behalten ihr Fail-Safe-Verhalten — der Default des neuen
  Parameters ist `False`.
- **Loop-Schutz ohne Sonderfall:** die No-op-Skips in beiden Adaptern feuern kein `user_updated`,
  das Leeren eines `cached_property` ebenfalls nicht (in HAs `models.py` verifiziert). Der
  Rückkopplungspfad endet nach einem Durchlauf; „ein neuer Nutzer kostet genau zwei Läufe" ist
  plausibel und getestet.
- `_auto_recompile` prüft den Modus **und** ob der Entry noch geladen ist, bevor es etwas tut; ein
  entladener Entry wird nicht angefasst.
- Vorhandene Tests sind nicht abgeschwächt worden; die Doubles haben einen Bus und
  `async_on_unload` dazubekommen (QUALITY R1 gewahrt).

## Nicht prüfbare Punkte

- **Lauf gegen `ha-tessera-dev`.** Der PR kreuzt diese Checkbox selbst **nicht** an. `CLAUDE.md`
  und `AGENTS.md` verlangen Auth-Tests gegen die Dev-Instanz; die e2e-Tests gegen HAs echte
  Registries, `AuthStore`, Bus und Debouncer sind stark, ersetzen aber keinen Lauf auf einer
  Instanz. **Vor** dem Scharfschalten auf der Live-Instanz nachzuholen (dort ist `enforce` ohnehin
  noch durch das D9-Ack von `auth_oidc` blockiert).
- **Verhalten unter Dauerlast.** HAs `Debouncer` verlängert den Timer bei weiteren Aufrufen nicht
  (er merkt sich „am Ende noch einmal"), eine Ereignisflut kann den Recompile also nicht
  aushungern — gelesen, nicht gemessen. Ein Soak mit laufender Integration-Reload-Schleife wäre der
  Beweis.
- **Realer Schreibzyklus bei blockiertem Plan auf einer Instanz.** Der Pfad ist e2e getestet, aber
  nicht auf einer Instanz mit echtem D9-Veto beobachtet.
- **R7 (zwei unabhängige Reviews).** Der PR beschreibt einen eigenen adversarialen Durchgang; dieses
  Gate ist das zweite Review. Dass der erste Durchgang unabhängig war, kann ich nicht verifizieren —
  die drei Funde und ihre Regressionstests sprechen dafür.

## Konkrete Codex-Aufgaben zur Behebung

### Aufgabe 1

```text
Aufgabe: Eigene Repairs-Meldung für den blockierten automatischen Recompile.

Betroffene Dateien:
- custom_components/tessera/__init__.py
- custom_components/tessera/strings.json
- custom_components/tessera/translations/en.json
- tests/test_auto_recompile_e2e.py

Regeln / was nicht ändern:
- Das Verhalten bleibt wie es ist: Modus bleibt `enforce`, der letzte angewandte Zustand bleibt,
  der nächste Change versucht es erneut. NUR die Meldung wird korrekt.
- `REPAIR_ENFORCE_FAIL_SAFE` und dessen Text bleiben für die echten Fail-Safe-Pfade unverändert.
- Keine weiteren Issue-Keys anfassen, `restore_fail_safe` nicht berühren.

Erwartete Umsetzung:
- Neue Konstante `REPAIR_ENFORCE_BLOCK_PENDING = "enforce_block_pending"` neben der bestehenden.
- Im `keep_enforce_on_block`-Zweig von `_apply_enforce_mode` diesen Key verwenden; `reason`
  bleibt `auto_recompile_blocked:<block_reason>`.
- In strings.json und translations/en.json einen `issues.enforce_block_pending`-Eintrag:
  title "Tessera could not recompile — enforce stays active"
  description "Tessera could not re-apply entry {entry_id} and kept the last applied enforce
  state. Permissions stay as last applied until the block clears; a later change retries.
  Reason: {reason}."
  (Text darf abweichen, muss aber sagen: enforce laeuft weiter, letzter Stand gilt, Drift
  moeglich bis die Blockade weg ist.)

Tests:
- In test_a_blocked_auto_recompile_keeps_enforce_and_retries zusätzlich assertieren, dass genau
  (REPAIR_ENFORCE_BLOCK_PENDING, "auto_recompile_blocked:linter") aufgezeichnet wird und NICHT
  REPAIR_ENFORCE_FAIL_SAFE.
- Mutationsprobe (QUALITY R6): den Key im Produktionscode zurück auf REPAIR_ENFORCE_FAIL_SAFE
  drehen — der Test muss rot werden. Ergebnis im Abschlussbericht nennen.
- Prüfen, dass kein bestehender Test auf REPAIR_ENFORCE_FAIL_SAFE in diesem Pfad baut.

Definition of Done: ruff, black, mypy --strict und die volle Suite grün; beide Übersetzungsdateien
tragen den neuen Key; Mutationsprobe dokumentiert.

Abschlussbericht: geänderte Dateien, neuer Text, Testergebnis, Mutationsprobe.
```

### Aufgabe 2

```text
Aufgabe: Den Permissions-Cache-Mechanismus durch einen Contract-Test absichern.

Betroffene Dateien: tests/test_ha_auth_contract.py

Regeln / was nicht ändern:
- Keine Produktionsdatei anfassen.
- Stil und Aufbau der vorhandenen Contract-Tests übernehmen (importorskip, Docstring, der die
  Konsequenz eines Bruchs benennt).
- Keine hass-Fixture verwenden: die Datei läuft in der nackten Per-Linie-Umgebung der CI-Matrix.

Erwartete Umsetzung:
- Neuer Test test_installed_user_model_still_offers_the_permission_cache_drop:
  * homeassistant.auth.models.User hat ein aufrufbares Attribut `invalidate_cache`.
  * `permissions` ist auf der Klasse ein cached_property (z. B. über
    type(...).__dict__["permissions"] prüfen, nicht über eine Instanz raten).
  * Eine User-Instanz bauen (wie test_installed_group_model_matches_the_adapter_group_protocol
    es für Group tut), `permissions` einmal lesen, danach invalidate_cache() aufrufen, und
    assertieren, dass der Cache-Eintrag aus __dict__ verschwunden ist.
- Docstring sagt, warum: auth_adapter ruft invalidate_cache ueber getattr auf, ein Wegfall waere
  ein lautloses No-op, und die Folge waere eine in place verengte Policy, die weiter gewaehrt.

Tests:
- Lauf gegen das lokale .venv (HA 2026.8.2) und, falls verfügbar, gegen 2026.11.1 und
  2026.12.0b0 — in allen Fällen grün.
- Mutationsprobe: im Test `invalidate_cache` auf einen Fantasienamen ändern → Test muss rot.

Definition of Done: der Test läuft in der Contract-Matrix mit (keine Workflow-Änderung nötig,
die Datei ist dort schon gelistet); ruff, black und die volle Suite grün.

Abschlussbericht: neuer Test, Lauf-Ergebnisse je HA-Version, Mutationsprobe.
```

### Aufgabe 3

```text
Aufgabe: Guide um das Verhalten bei blockiertem automatischem Recompile ergänzen.

Betroffene Dateien: docs/GUIDE.md, docs/GUIDE.de.md

Regeln / was nicht ändern:
- Erst nach Aufgabe 1 erledigen, damit der Repairs-Text zitiert werden kann.
- Keine anderen Abschnitte umbauen; zwei bis drei Sätze genügen.

Erwartete Umsetzung:
- Im Abschnitt „things to watch out for" / „Was zu beachten ist": automatische Recompiles laufen
  debounced (~2 s) nach Registry- und Nutzer-Änderungen; kann ein automatischer Lauf den Plan
  nicht anwenden (Linter-Konflikt, D9-Veto), bleibt `enforce` mit dem letzten angewandten Stand
  aktiv, es erscheint ein Repairs-Hinweis, und der nächste Change versucht es erneut. Bis die
  Blockade behoben ist, können Grants dem aktuellen Registry-Stand hinterherhängen.

Tests: keine (Doku). Prüfen: Links/Anker gültig, EN und DE inhaltlich gleich.

Definition of Done: beide Guides aktualisiert, Zeilenlänge im Rahmen der Datei.

Abschlussbericht: geänderte Abschnitte in EN und DE.
```
