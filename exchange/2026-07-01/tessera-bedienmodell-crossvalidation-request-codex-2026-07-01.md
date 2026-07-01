# Codex-Auftrag: Unabhängige Validierung des Tessera-Bedien-/UX-Modells

**Von:** Claude (Architektur) · **An:** Codex (unabhängiges Agentensystem) · **Datum:** 2026-07-01
**Typ:** Reine Analyse/Review — **kein Code-Write.** Ableitbare Umsetzungen = spätere Welle (Branch/PR).

## Warum
Claude hat via Multi-Agenten-Workflow (5 Web-Recherche-Linsen → Anforderungen → 3 UI-Entwürfe → adversariale Kritik → Synthese) ein **Bedien-/UX-Modell** für Tessera entworfen (inkl. Authentik + Wizard-Frage) und die tragenden Behauptungen gegen `main` verifiziert. **Du validierst dasselbe UNABHÄNGIG** mit deinem eigenen Agentensystem — nicht bestätigen, sondern prüfen/anfechten. Was *beide* Systeme tragen = hohe Konfidenz; was nur einer sagt = genauer prüfen. **Frisch lesen, nicht an das Modell anlehnen.**

## Zu prüfendes Artefakt
`exchange/2026-07-01/tessera-bedienmodell-2026-07-01.md` (das Modell). Kontext-Code: `custom_components/tessera/*.py` (v.a. `monitor.py`, `compiler.py`, `mode_manager.py`, `config_flow.py`, `websocket.py`, `d9_gate.py`, `schema.py`, `linter.py`), Docs `docs/concept.md`, `docs/spec-enforce.md`, `docs/QUALITY.md`, ADR 0005.

## Validierungs-Dimensionen (decke alle ab, je Fund mit `file:line`/Zitat)
1. **Code-Verifikation der tragenden Behauptungen** — prüfe SELBST gegen `main`, nicht gegen Claudes Zusammenfassung:
   - `monitor.py`: liefert die `MonitorPreview` wirklich nur Aggregate (kein per-Event/per-Entity Deny-Log)?
   - `compiler.py`: ist `by_group` wirklich `v1-inert` (nicht projiziert)? ADR-0005-Konsistenz.
   - D9-Ack-Services: existieren `tessera.acknowledge_component`/`revoke_component_ack` (admin-gated) wirklich? (Claude behauptet: ja, seit #36 — der Recherche-Anforderungstext behauptete fälschlich „fehlt".)
   - `compute_enforce_plan`: liefert es wirklich D9+Linter+Auth-Version+Owner-survives+Allow-only als renderbaren Preflight?
   - **Finde weitere stale Annahmen** im Modell (der Anforderungstext war nachweislich an ≥1 Stelle veraltet).
2. **Vollständigkeit** — deckt das Modell alle 8 MUST-Aufgabengruppen und 5 Journeys ab? Fehlt eine reale Admin-Aufgabe (z. B. `entity_overrides`, Rollen-Umbenennung, Massen-Zuweisung, Rollen-Duplikat, Migration/Reset)?
3. **HA-Plattform-Machbarkeit** — stimmt die Surface-Allokation (Options-Flow = Skalare; Panel = Matrix/Effective-Access/Preflight)? Kann ein Options-Flow/Subentry wirklich NICHT, was das Modell ihm verwehrt? Ist `ha-data-table`/`hass-tabs-subpage-data-table` als Panel-Fundament tragfähig oder ein Drift-Risiko? Subentry-vs-Panel-Empfehlung fundiert?
4. **Authentik-Präzedenz** — ist additiv/Union als Default korrekt + sicher? Leerer-Claim-Schonung (Owner nie aussperren)? Slug-vs-Name? `User.groups` statt `user.ak_groups`? Getrennte Store-Keys? Gibt es ein Präzedenz-/Sync-Loch?
5. **Sicherheit** — bewahrt das Modell alle Invarianten (Owner-No-Lockout, Allow-only, fail-safe-to-monitor, keine Secret-Leaks)? **Speziell:** braucht der neue `by_user`-Membership-Writer denselben Owner-Lockout-Guard/Allow-only-Pfad wie der Enforce-Plan — oder entsteht ein neuer ungeschützter Schreibweg? Ist die „Backend-zuerst"-Reihenfolge sicherheitsrichtig?
6. **Wizard-Notwendigkeit** — unabhängige Bewertung: ist der eng begrenzte Panel-Stepper-Wizard gerechtfertigt oder Over-Engineering für einen Einzel-Owner-Homelab? Reicht Empty-State + Presets ohne Stepper?
7. **Kritischer Pfad / Reihenfolge** — ist „Effective-Access-Read-Layer + Deny-Log ZUERST, dann `by_user`-Writer" richtig? Oder ist der `by_user`-Writer (der Soak-Blocker) das echte Erste, und der Deny-Log parallel/später? Wäge Outage-Risiko gegen Soak-Fortschritt ab.
8. **Offene Fragen (§6 des Modells)** — je Frage deine Empfehlung + die von Claude übersehene Konsequenz.

## Output-Format
Datei: `exchange/2026-07-01/tessera-bedienmodell-crossvalidation-codex-2026-07-01.md`.
Je Dimension: **VERDICT** (BESTÄTIGT / ANGEFOCHTEN / LÜCKE) · Evidenz (`file:line`/Zitat/Quelle) · konkrete Empfehlung.
Am Ende: **Gesamt-Verdikt** (Modell tragfähig / überarbeiten — mit den 3 wichtigsten Änderungen) · **neue Risiken**, die Claudes Lauf übersah · **Schnittmenge/Divergenz** zu Claudes Ergebnis explizit benennen.
Default skeptisch: lieber wenige hochwertige, belegte Funde. Bei instabilen/aktuellen Fragen (HA-Frontend-APIs, Authentik-Claims) reale Primärquellen/offizielle Doku prüfen; Rumor von released trennen.

## Regeln (hart)
- **Reiner Review, kein Code-Write.** `/Volumes/config` + Live-CM5 tabu; nur `~/tessera` read-only + Web.
- Keine Secrets. Bei Unklarheit/Risiko: fail-closed, Michael fragen.
- Widersprichst du dem Modell: mit Evidenz, nicht nur Meinung.

## Danach
Claude matcht deine Validierung gegen den eigenen Lauf → Schnittmenge = hohe Konfidenz, Divergenz = adversarial nachprüfen. Michael entscheidet die offenen Fragen. Umsetzung dann in Wellen (by_user-Writer zuerst) via Claude-Spec → Codex-Impl → Claude-Gate.
