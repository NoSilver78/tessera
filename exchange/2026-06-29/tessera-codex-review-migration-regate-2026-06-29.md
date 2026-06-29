# Gate Review - Tessera Migration Re-Gate

Datum: 2026-06-29
Autor: Codex
Modus: read-only Review + Subagenten-Gegenpruefung; geschrieben als neues Review-Artefakt. Keine Aenderung an `/Volumes/config`, kein Push, keine Secrets ausgegeben.

## Entscheidung

PASS MIT AUFLAGEN

## Kurzbewertung

Die Migration nach `~/tessera` ist als neuer Arbeitsort grundsaetzlich tragfaehig: Repo existiert, Worktree ist clean (`main...origin/main`), die alte Historie wurde in `exchange/2026-06-29/` migriert, `README.md` beschreibt den Status korrekt als `PASS MIT AUFLAGEN` ohne Enforce-Go, und `.gitignore` deckt die zentralen Secret-/HA-Runtime-Pfade ab.

Nicht freigeben wuerde ich aber den naechsten Welle-A-Schreiblauf, bevor drei kleine Prozess-/Routing-Punkte geklaert sind. Der wichtigste technische Widerspruch: Die Migration sagt, ab jetzt in `~/tessera` und Reports nach `exchange/2026-06-29/`; das Runner-Skript schreibt intern aber weiter nach `spike/outputs`. Damit koennte Welle A sofort neue, nicht-kanonische Artefakte erzeugen.

## Kritische Punkte

| Bereich | Problem | Auswirkung | Konkrete Korrektur |
|---|---|---|---|
| - | Keine kritischen Punkte gefunden. | - | - |

## Hohe Punkte

| Bereich | Problem | Auswirkung | Konkrete Korrektur |
|---|---|---|---|
| Artefakt-Routing | `outputs/tessera-MIGRATION-notice-2026-06-29.md:7-11` verlegt Arbeit/Reports nach `~/tessera/exchange/2026-06-29/`; `AGENTS.md:12-13` nennt `spike/{evidence,reports,tools}`; `spike/tools/tessera_spike/d0_preflight_spike.py:11` und `:34-35` schreiben weiter nach `outputs/`. | Welle A kann neue Evidence/Reports an falscher Stelle erzeugen. Das unterlaeuft Reviewbarkeit und Secret-Hygiene, weil `outputs/` im Repo nicht als gefroren/ignoriert abgesichert ist. | Vor Welle A eine eindeutige Routing-Regel festlegen und im Runner umsetzen: Evidence nach `spike/evidence/`, Gate-/Spike-Reports nach `spike/reports/`, Ping-Pong-/Antwortdokumente nach `exchange/YYYY-MM-DD/`. Alternativ `outputs/` explizit als legacy ignored/frozen markieren und nie mehr als Schreibziel nutzen. |
| Prozessvertrag | `CONTRACT.md:2` ist noch `Entwurf v0.1 ... zur Aushandlung`, waehrend `AGENTS.md:3`, `CLAUDE.md:3` und `README.md:5-6` ihn bereits als verbindlichen Prozess behandeln. | Agenten koennen sich auf unterschiedliche Autoritaeten berufen; gerade bei Welle A entsteht Drift bei Reports, Branches und Push-Verhalten. | `CONTRACT.md` vor Welle A auf accepted/current setzen oder ein kurzes `CONTRACT-STATUS`/ADR schreiben: Round-2 Work-Order v2 gilt fuer Welle A temporaer als Override, bis Vertrag v0.2 gemergt ist. |
| Branch-/Main-Schutz | Repo steht aktuell auf `main`; `CONTRACT.md:28` und `:50` verlangen Branch-/Worktree-Isolation und `main` nur gegated/gruen. Welle-A-Branch ist nicht benannt. | Erste echte Aenderungen koennten direkt auf `main` passieren und den Gate-Prozess formal brechen. | Vor dem ersten Write einen kurzlebigen Branch/Worktree z. B. `welle-a/harness-hardening` verwenden. Commit/Push erst nach A-Mini-Gate und Secret-/Statuscheck. |

## Mittlere Punkte

| Bereich | Problem | Auswirkung | Konkrete Korrektur |
|---|---|---|---|
| Historische Autoritaet | Migrierte Alt-Reports enthalten teils ueberholte Formulierungen wie staerkere Neubau-/Risikokern-Sprache, waehrend `tessera-claude-round2-workorder-v2-2026-06-29.md` und `tessera-codex-accept-round2-workorder-v2-2026-06-29.md` diese bewusst korrigieren. | Spaetere Agenten koennten Archivdokumente als aktuelle Freigabe misslesen. | In `exchange/2026-06-29/` oder README einen kleinen Index/Superseded-Hinweis setzen: massgeblich fuer naechste Arbeit ist Round-2 Work-Order v2 + Codex ACCEPT; alte Reports sind Historie. |
| Push-Regel | Migration Notice `:15` erlaubt Claude Commit+Push via `gh`; `CONTRACT.md:61` regelt nur Outward/Enforce/Release und Michaels Freigabe. | Private-Repo-Push ist praktisch gewollt, aber noch nicht sauber vom Produkt-/Public-/Live-Go abgegrenzt. | Im Vertrag klar trennen: private Repo Push nach gruenem Gate erlaubt; public/outward/HACS/Live nur mit Michael-Freigabe. Kein Force-Push. |
| Secret-Failure-Pfade | Erfolgreiche Evidence ist redacted, aber `d0_preflight_spike.py:733-747` kann bei Onboarding-/Token-Fehlern Response-Bodies in Exceptions werfen. | Ein kuenftiger Auth-/LLAT-Fehler koennte sensible Werte in Logs/Evidence bringen. | In Welle A Failure-Redaction vor Exception-Ausgabe implementieren; niemals `auth_code`, Access-/Refresh-/LLAT-Werte oder rohe Auth-Response-Bodies loggen. |
| `.gitignore` Betriebsreste | `.gitignore:1-36` deckt Kernpfade gut ab, aber nicht `outputs/`, HA-Logs, Raw-Dumps, Archive/Backups, Traces/HARs. | Bei Messlaeufen koennen unabsichtlich operative Rohartefakte im Repo landen. | Ergänzen: `outputs/`, `*.log`, `*.har`, `*.trace`, `*.tar`, `*.tar.gz`, `*.zip`, `backup*/`, `raw*/`, sofern solche Artefakte nicht bewusst versioniert werden sollen. |

## Niedrige Punkte

| Bereich | Problem | Auswirkung | Konkrete Korrektur |
|---|---|---|---|
| Namenskonvention | `CONTRACT.md:47` verlangt `<scope>-<kind>-<author>-YYYY-MM-DD.md`, vorhandene Dateien nutzen z. B. `workorder` statt `work-order` und Zusatzteile wie `round2`. | Leichte Such-/Sortierunschärfe, aber aktuell nicht blockierend. | Nicht rückwirkend umbenennen. Ab jetzt entweder Konvention lockern oder strikt anwenden. |
| Monitor-Pfade | Der bisherige Heartbeat-Monitor beobachtet weiter die alten `outputs/`-Pfade, Migration verlangt aber `~/tessera/exchange/2026-06-29/`. | Neue Review-Anforderungen im Repo koennen uebersehen werden. | Monitor-Instruktion auf `~/tessera/exchange/**`, `spike/reports/`, `spike/evidence/` erweitern; alten `outputs/`-Ordner nur noch als Archiv behandeln. |

## Positive Beobachtungen

- `README.md:16-17` stellt den Projektstatus sauber dar: Phase-0 `PASS MIT AUFLAGEN`, D5/Breite offen, kein Enforce-Go.
- `README.md:19-20`, `AGENTS.md:15-17`, `CONTRACT.md:52-56` halten die Kernregel konsistent: keine Secrets, Auth-Tests nur `ha-tessera-dev`, `/Volumes/config` read-only.
- Worktree war beim Check clean: `## main...origin/main`.
- Die zentralen migrierten Round-2-Artefakte liegen in `exchange/2026-06-29/`, inklusive `tessera-claude-round2-workorder-v2-2026-06-29.md` und `tessera-codex-accept-round2-workorder-v2-2026-06-29.md`.
- Zwei unabhaengige Subagenten kamen beide zu `MODIFY/PASS MIT AUFLAGEN`, nicht zu `REJECT`: die Migration ist brauchbar, aber vor dem ersten Schreib-/Messlauf nicht ganz geschlossen.

## Nicht prüfbare Punkte

- Remote-Branch-Protection, GitHub Rulesets und private Repo Permissions wurden nicht per Netzwerk/GitHub-API geprueft.
- Ob Claude bereits einen aktualisierten Vertrag lokal/remote vorbereitet hat, wurde nicht geprueft; sichtbar im Checkout ist weiterhin `CONTRACT.md` als v0.1-Entwurf.
- Keine Live-Pruefung von `ha-tessera-dev` in diesem Gate; es ging um Migration/Prozesszustand.

## Konkrete Codex-Aufgaben zur Behebung

### Aufgabe 1 - Artefakt-Routing vor Welle A schliessen

```text
Arbeite in `~/tessera` auf einem kurzlebigen Branch/Worktree `welle-a/harness-hardening`. Aendere das Tessera-Spike-Tool so, dass keine neuen Artefakte mehr nach `outputs/` geschrieben werden. Evidence gehoert nach `spike/evidence/`, Gate-/Spike-Reports nach `spike/reports/`, Ping-Pong-/Review-Dokumente nach `exchange/YYYY-MM-DD/`. Aktualisiere Docstring/Konstanten, fuehre einen trockenen Pfad-/No-Secret-Check aus und berichte die neuen Zielpfade. Keine Aenderung an `/Volumes/config`, keine Tokenwerte, kein Push ohne Gate.
```

### Aufgabe 2 - Vertragsstatus und Welle-A-Prozess eindeutig machen

```text
Aktualisiere `CONTRACT.md` bzw. ein kurzes ADR/Status-Dokument so, dass klar ist: Der Vertrag ist current/accepted oder Round-2 Work-Order v2 ist der temporaere Welle-A-Override. Definiere fuer Welle A exakt: Branch/Worktree-Name, Reportpfad, Evidencepfad, Gate-Review-Pfad, wer private Repo Commits/Pushes ausfuehrt, und dass Enforce/Public/HACS/Live weiter gesperrt bleiben. Keine neuen Produktfeatures.
```

### Aufgabe 3 - Secret-/Failure-Hygiene haerten

```text
Haerte die Auth-/Onboarding-Fehlerpfade im Spike-Tool: Exceptions und Logs duerfen keine rohen Auth-Response-Bodies, `auth_code`, Access-/Refresh-/LLAT-Werte oder Passwoerter enthalten. Fuehre danach einen Secret-Scan ueber geaenderte Dateien und erzeugte Artefakte aus. Ergaenze `.gitignore` fuer legacy/operative Rohartefakte wie `outputs/`, Logs, HAR/Trace, Archive/Backups und Raw-Dumps, sofern nicht bewusst versioniert.
```

## Gate-Entscheidung

PASS MIT AUFLAGEN.

Migration als Arbeitsbasis akzeptieren, aber Welle A erst starten, wenn Artefakt-Routing, Vertragsstatus/Branch-Regel und Failure-Redaction geschlossen sind. Kein Enforce-, Produkt-, HACS-, Public- oder Live-Go.
