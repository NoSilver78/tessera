# Gate Review — PR #74 `ci(upcoming): open a tracking issue when the next HA line goes red`

Claude · 2026-11-26 · Gate-/Auditmodus · Branch `ci/upcoming-auto-issue` → `main` · +83/−1 in 2 Dateien
· geprüft gegen die 16 Kriterien (`CLAUDE_WORKFLOW.md` §2)

## Entscheidung

**PASS MIT AUFLAGEN**

## Kurzbewertung

Der PR schließt eine echte Betriebslücke, und zwar die, die sich gerade **heute** wieder gezeigt
hat: HA hat am 25.11. `2026.12.0b0` veröffentlicht, der Nightly ist am 26.11. um 04:34 rot geworden —
und sichtbar ist das nur auf dem Actions-Tab. Beim Übergang auf 2026.11 ist genau das tagelang
untergegangen, bis ein Nutzer es gemeldet hat (Issue #71). Die Lösung ist klein, job-scoped und
sauber konditioniert: nur ein **fehlgeschlagener Check** öffnet ein Issue, ein gescheiterter
Install (PyPI, kaputtes Beta-Wheel) nicht.

Handwerklich ist der Workflow in Ordnung. Drei Dinge, die ich erwartet und **nicht** gefunden habe
(alle geprüft, nicht vermutet):

- Das Heredoc ist korrekt — die YAML-Blockskalar-Dedenting setzt `EOF` auf Spalte 0.
- `gh issue list --label <unbekannt>` liefert Exit 0 und leer (lokal gegen dieses Repo verifiziert),
  der Close-Schritt läuft also auch, bevor das Label je existiert hat.
- Werte erreichen das Skript über `env`, nicht per `${{ }}`-Interpolation in die Shell — kein
  Injection-Pfad über Versionsstrings.

Was den Gate auf Auflagen setzt: der Pfad, auf den es ankommt, ist **noch nie gelaufen**. Das sagt
der PR selbst offen, und es ist kein Vorwurf — nur verifizierbar ist es erst nach dem Merge. Günstig
ist, dass der Beweis gerade bereitliegt: der Nightly ist rot, ein Dispatch nach dem Merge muss also
das Issue anlegen.

## Kritische Punkte

| Bereich | Problem | Auswirkung | Konkrete Korrektur |
|---|---|---|---|
| — | keine | — | — |

## Hohe Punkte

| Bereich | Problem | Auswirkung | Konkrete Korrektur |
|---|---|---|---|
| — | keine | — | — |

## Mittlere Punkte

| Bereich | Problem | Auswirkung | Konkrete Korrektur |
|---|---|---|---|
| Betriebsfähigkeit (14, 16) | Der Melde- und der Close-Pfad sind nie ausgeführt worden; der Job läuft nur per `schedule`/`workflow_dispatch`, also nicht im PR-CI | Ein Tippfehler im `gh`-Aufruf fällt erst in der Nacht auf, in der das Signal gebraucht wird | Direkt nach dem Merge **einen `workflow_dispatch` fahren**: der Nightly ist wegen `2026.12.0b0` rot, es muss also ein `ha-upcoming`-Issue entstehen. Danach die Linie validieren und einen zweiten Dispatch fahren — der muss das Issue schließen. Ergebnis in dieses Review nachtragen |

## Niedrige Punkte

| Bereich | Problem | Auswirkung | Konkrete Korrektur |
|---|---|---|---|
| Security (8) | `ci.yml` hat **keine** Top-Level-`permissions`; `validate.yml` hat `contents: read`. Der Repo-Default ist heute `read` (`actions/permissions/workflow` geprüft), die Jobs `quality`/`contract` laufen also read-only — aber nur, solange die Repo-Einstellung so bleibt | Eine spätere Umstellung des Repo-Defaults auf `write` würde beide Jobs stillschweigend hochziehen | `permissions:\n  contents: read` am Anfang von `ci.yml` ergänzen (Parität zu `validate.yml`); das job-scoped `issues: write` im `upcoming`-Job bleibt |
| Dokumentation (13) | Der Issue-Titel lautet immer „upcoming line not validated yet". Rot kann aber auch heißen: die Linie ist bekannt, der private Subset hat sich **bewegt** | Im zweiten Fall führt der Titel in die falsche Richtung; der Body unterscheidet beide Fälle korrekt | Titel neutral fassen, z. B. `HA ${HA_VERSION}: nightly upcoming-line check is red`, und die Unterscheidung dem Body lassen |
| Wartbarkeit (11) | Das Close-Schritt-`for` schließt **alle** offenen `ha-upcoming`-Issues | Bei mehreren (Race zweier Läufe) korrekt aufgeräumt, aber ein von Hand geöffnetes Issue mit diesem Label würde mitgeschlossen | So lassen; falls es je stört, auf Issues mit Autor `github-actions[bot]` einschränken |

## Positive Beobachtungen

- **Die Bedingung ist richtig herum gedacht.** `failure() && (contract == 'failure' || mypy == 'failure')`
  trennt Produktsignal von Infrastrukturrauschen. Ein gescheiterter Install führt zu `skipped` in
  beiden Checks und damit zu **keinem** Issue — genau die Unterscheidung, die einen
  Frühwarn-Kanal glaubwürdig hält.
- `mypy` läuft jetzt auch nach roten Contract-Tests (`!cancelled() && steps.version.outcome == 'success'`),
  das Issue nennt also **beide** Checks statt nur des ersten.
- Dedupliziert statt zu spammen: vorhandenes Issue bekommt Kommentar + aktualisierten Titel.
- Die Doku-Ergänzung in `docs/MAINTENANCE.md` bleibt nicht beim Mechanismus stehen, sondern zieht
  die **Betriebsregel** nach: Diff und Release **vor** HAs Liefertermin. Das ist die Lehre aus
  2026.11, nicht nur ein Feature.
- Secrets: keine. Tokenwert ist `github.token`, job-scoped, nur `issues: write`.

## Nicht prüfbare Punkte

- **Ob `gh issue create` im Actions-Kontext mit diesem Token durchgeht** — lokal nicht
  nachstellbar; mit `issues: write` zu erwarten, aber erst der Dispatch beweist es (siehe Auflage).
- **Rendering des Issue-Bodys** (Markdown-Tabelle, absoluter MAINTENANCE-Link). Der PR nennt einen
  lokalen Dry-Run mit gestubbtem `gh`; ich habe den Body nicht gerendert gesehen.
- **Verhalten bei zwei gleichzeitigen Läufen** (Schedule + Dispatch): theoretisch zwei Issues. Nicht
  reproduziert, Auswirkung gering.

## Konkrete Codex-Aufgaben zur Behebung

### Aufgabe 1

```text
Aufgabe: Top-Level-Permissions in .github/workflows/ci.yml ergänzen.

Betroffene Dateien: .github/workflows/ci.yml

Regeln / was nicht ändern:
- Das job-scoped `permissions:` im Job `upcoming` (contents: read, issues: write) bleibt
  unverändert.
- Keine weiteren Jobs oder Schritte anfassen.

Erwartete Umsetzung:
- Direkt nach dem `on:`-Block ein Top-Level `permissions:` mit `contents: read` einfügen,
  mit einer Kommentarzeile, die sagt warum: unabhängig vom Repo-Default (heute read, per
  Einstellung umstellbar), Parität zu validate.yml.

Tests:
- `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"` läuft durch.
- Die Job-Liste bleibt quality/contract/upcoming, das job-scoped permissions des upcoming-Jobs
  bleibt unverändert (beides im Abschlussbericht zeigen).

Definition of Done: YAML parst, Diff betrifft nur ci.yml, kein Verhalten der Jobs geändert.

Abschlussbericht: geänderte Dateien, Diff des permissions-Blocks, Parse-Ergebnis.
```

### Aufgabe 2

```text
Aufgabe: Issue-Titel des ha-upcoming-Trackings neutral fassen.

Betroffene Dateien: .github/workflows/ci.yml

Regeln / was nicht ändern:
- Body, Label, Dedup-Logik und Close-Schritt bleiben wie sie sind.
- Der Titel muss die HA-Version weiter enthalten (die Dedup-Logik aktualisiert ihn).

Erwartete Umsetzung:
- title="HA ${HA_VERSION}: nightly upcoming-line check is red" (oder gleichwertig neutral),
  damit der Fall „Subset hat sich bewegt" nicht als „noch nicht validiert" gelesen wird.

Tests:
- YAML parst; im Abschlussbericht die neue Titelzeile zeigen.

Definition of Done: YAML parst, nur die Titelzeile geändert.

Abschlussbericht: geänderte Zeile, Parse-Ergebnis.
```
