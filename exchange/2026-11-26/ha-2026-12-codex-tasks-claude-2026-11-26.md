# Übergabe an Codex — HA 2026.12 validieren, Release vorbereiten

Claude · 2026-11-26 · Übergabemodus · **zeitkritisch:** HA 2026.12.0 erscheint voraussichtlich am
**2026-12-02**

## Lage

HA hat am 25.11. **`2026.12.0b0`** veröffentlicht; der Nightly-Job `HA upcoming line (pre-release)`
ist seit 26.11. 04:34 rot — bestimmungsgemäß, denn `test_installed_ha_line_is_validated` schlägt auf
einer nicht validierten Linie absichtlich fehl. Alle übrigen Jobs sind grün, inklusive der fünf
Contract-Linien 2026.7.1 bis 2026.11.1.

**Schritt 1 des Prozesses aus [docs/MAINTENANCE.md](../../docs/MAINTENANCE.md) ist schon erledigt**
— Diff `2026.11.1 → 2026.12.0b0` über den von den Adaptern berührten Subset, nicht erneut herleiten:

| Pfad | Ergebnis |
|---|---|
| `auth/models.py` | **byte-identisch** |
| `auth/permissions/` (alle 9 Dateien) | **byte-identisch** |
| `auth/auth_store.py` | geändert, 6 Hunks — ausschließlich Long-Lived-Token-Nutzungstracking: neues `async_log_long_lived_access_token_usage()`, `LONG_LIVED_ACCESS_TOKEN_USAGE_SAVE_DELAY = 60`, `_usage_save_timer`, Flush bei `EVENT_HOMEASSISTANT_STOP` |

Entscheidend: `_data_to_save()` hat **drei Zeilen Prolog** bekommen (bricht den Usage-Timer ab), die
Serialisierung darunter ist unverändert; `_groups`, `self._store` und `async_get_groups` kommen im
Diff **nicht vor**. Die berührte Teilmenge ist damit kompatibel.

## Richtungsentscheidung — getroffen von Michael am 2026-11-26: **Variante A**

`SUPPORTED_HA_AUTH_VERSION` nennt bisher immer eine **Release**-Version (2026.7.1, 2026.8.1,
2026.9.4, 2026.10.4, 2026.11.1), nie eine Beta. Die mit PR #74 eingeführte Regel sagt dagegen:
validieren und releasen **vor** HAs Liefertermin. Beides zugleich geht nicht:

| Variante | Inhalt | Preis |
|---|---|---|
| **A — auf das Release-Tag pinnen** (Empfehlung) | PR jetzt vollständig vorbereiten, Matrix fährt `2026.12.0b0`; am Release-Tag Diff gegen `2026.12.0` wiederholen, Pin auf `2026.12.0` setzen, gleichen Tag releasen | Nutzer, die am 2.12. sofort aktualisieren, stehen wenige Stunden ohne `enforce` |
| **B — auf die Beta pinnen** | `SUPPORTED_HA_AUTH_VERSION = "2026.12.0b0"`, Release vor dem 2.12. | Der „neueste validierte" Stand ist dann kein Release; weicht von der bisherigen Konvention ab |

**Entschieden: A.** Der Pin nennt weiterhin eine Release-Version; die Beta wird in der
CI-Matrix *gefahren*, aber nicht gepinnt. Damit bleibt das Diff-Protokoll eine Kette von
Release-Tags, und die Regel aus PR #74 („validieren und releasen vor HAs Liefertermin") ist
dadurch erfüllt, dass der PR am Liefertermin **fertig** ist und am selben Tag released wird —
nicht dadurch, dass eine Beta zur validierten Version erklärt wird.

Was das praktisch heißt: der Nightly wird schon mit diesem PR grün, weil
`test_installed_ha_line_is_validated` die installierte Linie gegen die **Menge** prüft und nicht
gegen den Pin. Nutzer, die am 2.12. in den ersten Stunden aktualisieren, sind kurz ohne `enforce` —
das ist der bewusst in Kauf genommene Preis.

B ist damit verworfen, bleibt aber oben dokumentiert, damit die Abwägung nachvollziehbar ist.

---

## Aufgabe 1 — HA 2026.12 in den Guard, Release v0.9.6 vorbereiten

```text
Aufgabe: Die HA-Linie 2026.12 als validiert aufnehmen und das Release v0.9.6 vorbereiten.

Betroffene Dateien:
- custom_components/tessera/auth_adapter.py   (Guard-Konstanten + Belegkommentar)
- custom_components/tessera/manifest.json     (Version)
- tests/test_auth_adapter.py                  (die nicht validierte Linie im Test)
- .github/workflows/ci.yml                    (Contract-Matrix)
- docs/MAINTENANCE.md                         (Diff-Protokoll + Guard-Absatz)
- CHANGELOG.md                                (neuer Abschnitt)
- README.md, README.de.md, docs/GUIDE.md, docs/GUIDE.de.md (Linien + Versionsstände)

Regeln / was nicht ändern:
- Die Menge wird ERWEITERT, nicht verschoben: 2026.7 und 2026.8 bleiben drin (ADR 0006).
- Keine Logik anfassen. Nur Konstanten, Matrix, Tests, Doku.
- Den Diff aus der Lage-Tabelle oben NICHT neu herleiten; als Beleg in den Kommentar übernehmen.
- Kein hacs.json-homeassistant-Pin (ADR 0006, bewusste Entscheidung).
- Entschieden (Michael, 2026-11-26): SUPPORTED_HA_AUTH_VERSION bleibt in diesem PR auf
  "2026.11.1" und nennt nie eine Beta. Erst wenn 2026.12.0 erschienen ist, wird daraus
  "2026.12.0" (siehe Tests, letzter Punkt). Nicht vorziehen, nicht auf die Beta pinnen.

Erwartete Umsetzung:
- SUPPORTED_HA_AUTH_FEATURES wird {"2026.7","2026.8","2026.9","2026.10","2026.11","2026.12"}.
  Achtung: die Menge leitet ihren jüngsten Eintrag bisher aus SUPPORTED_HA_AUTH_FEATURE ab.
  Solange der Pin auf 2026.11.1 steht, muss "2026.12" explizit dazu — und der Kommentar sagt
  warum (Linie validiert, Pin folgt mit dem Release-Tag).
- Belegkommentar für 2026.11 -> 2026.12 im bestehenden Stil: models.py und permissions/
  byte-identisch, auth_store.py nur Long-Lived-Token-Debouncing, _data_to_save() nur
  Timer-Prolog, _groups/_store/async_get_groups unberührt; verifiziert 2026-11-26 gegen
  2026.12.0b0.
- tests/test_auth_adapter.py: in der Parametrisierung der NICHT validierten Linien steht heute
  "2026.12.0" — das wird jetzt gültig. Auf "2026.13.0" ziehen (dieselbe Stelle musste bei
  jeder Linie nachgezogen werden; nicht übersehen, sonst wird der Test rot).
- ci.yml: Matrix-Eintrag "2026.12.0b0" ergänzen (mit Variante A bewusst die Beta, damit CI die
  Linie wirklich fährt; beim Release-Tag auf "2026.12.0" ziehen).
- docs/MAINTENANCE.md: neue Zeile im Diff-Protokoll für 2026.12 (Spalten wie gehabt: Linie,
  Diff gegen, Ergebnis, Verifiziert) und der Guard-Absatz nennt 2026.12 mit.
- docs/MAINTENANCE.md zusätzlich: die Konvention festschreiben, damit sie nicht in einem
  exchange-Dokument hängt. Ein Satz im Abschnitt "Prozess pro HA-Release": der Pin
  SUPPORTED_HA_AUTH_VERSION nennt immer eine **Release**-Version; eine Beta wird in der
  Contract-Matrix gefahren, aber nicht gepinnt. Die Regel "vor HAs Liefertermin releasen" wird
  dadurch erfüllt, dass der PR am Liefertermin fertig ist (Entscheidung Michael, 2026-11-26).
- CHANGELOG.md: Abschnitt [0.9.6] mit Datum, Stil der Vorgänger, inklusive der Validierungs-
  belege und des Hinweises, dass der Nightly damit wieder grün wird.
- manifest.json auf 0.9.6.
- Versionsstände in der Doku: README.md:68 und README.de.md:70 nennen weiterhin v0.9.4,
  docs/GUIDE.md:10 und docs/GUIDE.de.md:10 tragen Badge version-0.9.4 — alle vier auf 0.9.6
  ziehen, zusammen mit den HA-Linien-Angaben (README "Tested HA lines", Guide-Badge
  2026.7.x--2026.12.x, Guide-Tabelle "the 2026.7-2026.12 lines", Version-Guard-Absätze EN/DE).

Tests:
- pytest, ruff, black, mypy --strict grün (lokal und in CI).
- Contract-Tests gegen ein installiertes HA 2026.12.0b0 grün — inklusive
  test_installed_ha_line_is_validated, das vorher genau hier rot war.
- Mutationsprobe (QUALITY R6): "2026.12" aus SUPPORTED_HA_AUTH_FEATURES entfernen -> der
  Contract-Test gegen 2026.12.0b0 muss rot werden. Ergebnis im Abschlussbericht.
- Prüfen, dass die Matrix-Jobs für 2026.7.1 bis 2026.11.1 unverändert grün bleiben.
- LETZTER SCHRITT, erst wenn 2026.12.0 erschienen ist (nicht vorziehen): Diff gegen das
  Release-Tag wiederholen (dieselben drei Pfade), SUPPORTED_HA_AUTH_VERSION auf "2026.12.0"
  setzen, Matrix-Eintrag auf "2026.12.0" ziehen, Belegkommentar und Diff-Protokoll auf das
  Release-Tag umstellen. Weicht der Diff vom Beta-Befund ab: NICHT mergen, Michael fragen.

Definition of Done: alle CI-Jobs grün; Guard-Menge enthält 2026.7 bis 2026.12; Belegkommentar
und Diff-Protokoll vorhanden; Nightly-Job gegen die Vorabversion grün; kein Versionsstand in
der Doku mehr auf 0.9.4/0.9.5; Mutationsprobe dokumentiert.

Abschlussbericht: geänderte Dateien, Diffstat, Testergebnisse je HA-Linie, Mutationsprobe,
Ausgabe von tessera.preflight auf einer 2026.12-Instanz falls verfügbar (sonst als nicht
prüfbar ausweisen).
```

## Aufgabe 2 — den wiederkehrenden Versions-Rückfall beenden

Nicht zeitkritisch, aber derselbe Fehler zum dritten Mal: v0.9.3 hat ihn im CHANGELOG notiert
(„Projektstatus nannte weiterhin v0.9.0"), v0.9.4 hat ihn behoben, **v0.9.5 hat ihn erneut gemacht** —
alle vier Doku-Stellen stehen heute auf 0.9.4, während `manifest.json` 0.9.5 trägt. Das ist
mechanisch prüfbar, also sollte es nicht am Gedächtnis hängen.

```text
Aufgabe: CI-Check, der die Versionsnennungen in der Doku gegen manifest.json prüft.

Betroffene Dateien: tests/test_version_consistency.py (neu)

Regeln / was nicht ändern:
- Kein Produktionscode, keine Workflow-Änderung (die Suite läuft in CI schon).
- Erst nach Aufgabe 1 erledigen, sonst ist der Test sofort rot.
- Keine Versionsnummern im Test hartkodieren: manifest.json ist die Quelle.

Erwartete Umsetzung:
- manifest.json["version"] lesen.
- In README.md, README.de.md, docs/GUIDE.md, docs/GUIDE.de.md alle Vorkommen von
  v?\d+\.\d+\.\d+ einsammeln, die wie eine Tessera-Version aussehen (HA-Versionen der Form
  2026.x.y ausschließen), und verlangen, dass jede gleich der Manifest-Version ist.
- Die Fehlermeldung nennt Datei, Zeile, gefundene und erwartete Version.
- Docstring erklärt den Anlass: dreimal derselbe Rückfall, zuletzt in v0.9.5.

Tests:
- Test grün nach Aufgabe 1.
- Mutationsprobe: in einer der vier Dateien eine Version auf 0.9.0 setzen -> rot mit
  Datei:Zeile.

Definition of Done: grün, Mutationsprobe dokumentiert, keine Hartkodierung der Version.

Abschlussbericht: neue Datei, Testausgabe, Mutationsprobe.
```

## Was nicht Teil dieser Übergabe ist

- Die vier Aufgaben aus
  [`silent-ha-fallbacks-handover-claude-2026-11-26.md`](silent-ha-fallbacks-handover-claude-2026-11-26.md)
  — eigener Strang, eigene PRs.
- Die Auflagen aus den beiden Gate Reviews zu #73 und #74.
- Ein Merge nach `main`. Jede Aufgabe = ein PR auf einem `core/*`-Branch, Claude gate't.
