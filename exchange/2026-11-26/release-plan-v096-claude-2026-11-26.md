# Release-Plan v0.9.6 / v0.9.7 — Entscheidung

Claude · 2026-11-26 · Michael hat die Entscheidung ausdrücklich delegiert („reflektiere und
entscheide du"). **Freigabe zum Release bleibt laut [CONTRACT.md](../../CONTRACT.md) bei Michael** —
entschieden ist hier der *Inhalt* und die *Reihenfolge*, nicht die Veröffentlichung.

## Ausgangsbefund

```
git diff v0.9.5..origin/main -- custom_components/   →  leer
```

Acht Commits seit v0.9.5, **keine Zeile im ausgelieferten Code**: ein `.github`, ein `ROADMAP.md`,
ein `docs`, acht `exchange`. HACS lädt für eine Integration `custom_components/tessera/` — ein
Release heute wäre ein leerer Versionssprung.

## Entscheidung

1. **v0.9.6 = ausschließlich die HA-2026.12-Linie** (Guard-Menge + Belegkommentar + die
   Versionsstände, die die Aufgabe ohnehin mitzieht). Nach Variante A abgeschlossen am Release-Tag
   `2026.12.0`, voraussichtlich 2026-12-02.
2. **#73 darf nach `main` mergen, sobald Auflage 1 drin und das Gate grün ist — aber das löst kein
   Release aus.** Merge nach `main` und Release sind hier ausdrücklich zwei Dinge.
3. **v0.9.7 = #73 (auto-recompile) + der Fallback-Strang**, released **erst nach einem
   dokumentierten Lauf gegen `ha-tessera-dev`**.

## Warum nicht beides in v0.9.6

- **Termin-Kopplung.** v0.9.6 hat ein Datum. Bündelt man #73 dazu, entscheidet dessen Zustand
  darüber, ob die Linie rechtzeitig draußen ist — ein Feature bekommt die Dringlichkeit eines
  Termins geliehen, und der Termin bekommt das Risiko des Features.
- **Unterschiedlicher Schadensradius.** Die Guard-Erweiterung ist eine Konstante plus Kommentar;
  geht sie schief, *erlaubt* sie eine Linie zu früh. #73 verändert, **wann** native Writes
  passieren, automatisch, auf Registry-Events, ohne Admin-Aktion. Ein Fehler dort verschiebt
  Rechte still — genau die Klasse, gegen die dieses Projekt sonst paranoid ist.
- **Die Vorgeschichte von #73 spricht für einen Instanz-Lauf.** Sein eigener Gate-Befund war, dass
  der Mechanismus durch den `lambda`/`Debouncer`-Fehler **nie lief** — und das hat kein Unit-Test
  gefunden, sondern erst ein e2e-Test gegen echte HA-Interna. Ein Pfad mit dieser Historie gehört
  vor dem HACS-Store auf eine Instanz.
- **Der Dev-Lauf fehlt, und das ist Hausregel.** Die Checkbox ist in #73 selbst nicht angekreuzt;
  `CLAUDE.md` und `AGENTS.md` verlangen für auth-berührende Änderungen einen Lauf gegen
  `ha-tessera-dev`. Der HACS-Store ist der falsche erste Einsatzort — dort installieren Fremde.
- **Umkehrbarkeit.** Ist v0.9.6 falsch, verlieren Nutzer nichts. Ist #73 falsch, ändern sich Rechte
  auf laufenden Instanzen.

## Das Gegenargument, ausdrücklich notiert

Die Drift, die #73 behebt, ist eine echte **Über-Gewährung**, die heute auf jeder Instanz existiert:
eine Entity verlässt eine granted Area und behält `read`/`control`, bis jemand von Hand neu
kompiliert. In einem Rechteprodukt ist das kein Komfortthema, und es spricht für *früher*.

Entschärft wird es dreifach: es wirkt nur im `enforce`-Modus; das Projekt empfiehlt selbst
monitor-first und nennt `enforce` „noch nicht in der Praxis bewiesen"; und die Instanzzahl ist nach
Lage der Signale (2 Stars, 1 Fork, vier Issues) sehr klein. Zwei Wochen früher wiegen das Risiko
eines ungetesteten automatischen Schreibpfads nicht auf. **Wer diese Abwägung anders gewichtet, muss
#73 nicht beschleunigen, sondern den Dev-Lauf vorziehen** — das ist der Hebel, nicht das Release.

## Was das für die Stränge heißt

| Strang | Ziel-Release | Gate davor |
|---|---|---|
| HA 2026.12 | **v0.9.6** | Diff gegen das Release-Tag, CI grün, Nightly grün (schließt #76) |
| #73 Auflage 1 (Repairs-Meldung) | — (nur Merge) | Claude-Gate auf den Zusatz-Commit |
| #73 auto-recompile | **v0.9.7** | **Lauf gegen `ha-tessera-dev`, dokumentiert** |
| Stille HA-Fallbacks (4 Aufgaben) | **v0.9.7** | je PR gegated; braucht #73 gemergt |
| Niedrige Punkte (Rang 4) | v0.9.7 oder später | — |

## Prozess-Anmerkung (eigener Fehler)

`CONTRACT.md` §22 sagt für Tessera: Push „von **Task-Branch/Worktree** (nie direkte `main`-Arbeit)",
Merge nach `main` „nur mit grünem Gate + CI". Ich habe heute **sechsmal direkt auf `main` gepusht**
(die exchange-Dokumente und die ROADMAP) — jeweils auf Michaels Aufforderung, jeweils nur Doku,
jeweils mit Secret-Scan, aber dem Buchstaben der Regel widerspricht es. Richtig wäre: `docs/*`-Branch
→ PR → Merge, auch für Doku.

Zwei Dinge für Michael zum Entscheiden, nicht für Codex:

1. Entweder künftig auch Doku über PRs, **oder** eine ausdrückliche Ausnahme in `CONTRACT.md` für
   `exchange/` und `docs/`-only-Änderungen. Stillschweigend weitermachen ist die schlechteste der
   drei Möglichkeiten.
2. §22 sagt außerdem „ins **private** Repo". Das Repo ist seit dem Public-Flip öffentlich; die Zeile
   ist überholt und sollte auf die heutige Lage gezogen werden, damit sie nicht als Blankoscheck für
   „war ja mal privat" gelesen wird.
