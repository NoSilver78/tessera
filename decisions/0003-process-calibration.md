# ADR 0003 — Prozess-Kalibrierung: schnell + sicher-wo-es-zählt
Stand 2026-06-29 · Status: **aktiv** · Anlass: Michael-Vorgabe „moderater KI-Aufwand, schnell vorankommen, Sicherheit nicht überziehen, Best-Practice-Code". Ergänzt den Kooperationsvertrag (gilt als v0.3-Delta).

## 1. Risiko-gestufte Gates (statt überall gleich streng)
- **Tier-1 (hartes Claude-Gate):** Enforce-Flip · Auth-Schreibpfad · Lockout/Recovery · Secrets · Release/HACS-Publish · Live-CM5-Berührung. **Hier kompromisslos.**
- **Tier-2 (leicht, großteils automatisiert):** UI, interne Struktur, Refactors, Doku. **CI prüft, Claude gate't nur an Meilensteinen** (Modulabschluss/E2E), nicht jeden Mikroschritt.

## 2. Code-Standards (Best-Practice, verbindlich)
- **Tooling:** `ruff` (lint) · `black` (format) · `mypy` (types, strict für `custom_components/tessera`) · `pytest` (+ HA-Fixtures).
- **Code:** vollständige **Type-Hints** · **Docstrings** (Google-Style, je public Funktion/Klasse) · **kein blocking I/O** im Event-Loop (Executor/HA-Store/async) · HA-Integration-Best-Practice (config_flow, DataUpdateCoordinator wo sinnvoll, korrekte entity/device-Registry-Nutzung) · sprechende Namen · „warum"-Kommentare nur wo nötig.
- **„Sauber" =** lesbar + typisiert + getestet + knapp dokumentiert + robust (Fehlerfälle behandelt, keine verschluckten Exceptions).

## 3. CI automatisiert die Routine-Qualität
GitHub Actions bei jedem Push/PR: `ruff` + `black --check` + `mypy` + `pytest`. **Die Maschine prüft Stil/Typen/Tests; menschliche Gates bleiben für Architektur + Security.** Merge nach `main` nur mit grüner CI + (bei Tier-1) grünem Gate.

## 4. Leichtere Doku-Pflicht
Process-/Decision-Log nur bei **substanziellen** Entscheidungen (Architektur/Security/Datenmodell), nicht jeder Runde. Code dokumentiert sich primär selbst (Docstrings) + ADRs für Richtungsentscheidungen.

## 5. Weniger Koordinations-Overhead
Codex baut in kleinen, CI-grünen Schritten; Claude gate't an **Meilensteinen**, nicht je Commit. Ping-Pong nur bei echten Architektur-/Security-Fragen.
