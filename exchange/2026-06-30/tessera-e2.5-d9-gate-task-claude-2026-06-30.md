# Codex-Aufgabe — E2.5: D9-Produkt-Gate (read-only, non-scharf)
Von Claude · 2026-06-30 · Quelle: **`docs/spec-e3-design.md` Teil A** (adversarial-gegated `wb77hllxb`, gehärtet) · **Branch `enforce/e2.5-d9-gate` (von `main`) → PR** · **kein nativer Write** (dormant wie E1/E2) · **security-relevant** (fail-closed Gate)

## Problem
Vor jedem Enforce-Write (E3, `spec-e3-enforce.md` §2 Schritt 3) muss ein **D9-Gate** prüfen, ob installierte Custom-Components eine **user-token-erreichbare** Bypass-Oberfläche haben (nicht-entity-Services / HTTP-Views / WS-Commands) und Enforce **fail-closed** blockieren. Bisher existiert die Klassifikation nur im Spike (Dev-Harness). Das Produkt braucht einen eigenen, gehärteten Mechanismus.

## Aufgabe (genau nach `spec-e3-design.md` Teil A.2–A.6)
1. **`custom_components/tessera/d9_gate.py`** — `async def evaluate_d9_gate(hass, config) -> D9GateResult` (read-only; schreibt nichts nativ; **dormant — NICHT in die Mode-Verarbeitung verdrahten**). Ergebnis `{by_component: {domain: {verdict, version, reason, source}}, blocking: list[str], enforce_blocked: bool}`.
2. **Surface-Erkennung = PFLICHT-Hard-Veto:** statischer Marker-Scan des `custom_components/<domain>/`-Quellcodes via `async_add_executor_job` auf `async_register`(+`services`), `HomeAssistantView`/`register_view`/`panel`, `websocket_command`/`async_register_command` **plus** Runtime `hass.services.async_services().get(domain)`. **Jedes** positive Signal ⇒ Zwangs-`UNKNOWN_BLOCK_ENFORCE`, **VOR** Tabelle/Ack. `has_services`/`integration_type`/manifest-deps **NIE** für ALLOW (alle fälschbar/blind — s. Gate-Befund).
3. **Trust-Anchor `(domain, version, content_hash)`:** `content_hash` = sha256 über sortierte `*.py`/`*.yaml`/`manifest.json` der Komponente (off-loop). ALLOW nur, wenn alle drei matchen **und** kein Surface-Veto. Versions-Vergleich via `AwesomeVersion(...)` (None-fähig), nie roh-`str`.
4. **Frischer Platten-Scan** des `custom_components/`-Verzeichnisses pro Aufruf — **nicht** allein das prozesslebenslang gecachte `async_get_custom_components`-Dict.
5. **`custom_components/tessera/d9_classification.py`** — gebündelte Tabelle (`domain → {version, content_hash} → Verdikt`), v1 minimal/leer. **Schema** `config.d9_acks` (`{domain: {version, content_hash, accepted_at}}`) ergänzen + validieren.
6. **Default `UNKNOWN_BLOCK_ENFORCE`.**

## Regeln / was NICHT
- **Kein nativer Write, keine Mode-Verdrahtung** (dormant; E3 konsumiert es später). Nur `hass.config.path("custom_components")` — **kein** `/Volumes/config`-Scan. **Kein blocking I/O** im Event-Loop (alles via Executor). **NICHT** vom Spike-`_classify_custom_components` ableiten (frisch gegen die echte Loader-API).
- Python 3.13, ruff/black/mypy-strict grün, Google-Docstrings. **HA-frei testbar** (`async_get_custom_components` + Marker-Scan mockbar).

## DoD (Adversarial-Tests Pflicht, `spec-e3-design.md` A.6)
- Tests: (a) Komponente mit runtime-registrierten Services **ohne** `services.yaml` ⇒ UNKNOWN; (b) `integration_type="entity"` + View/WS-Marker ⇒ UNKNOWN; (c) gleiche `version`, geänderter `content_hash` ⇒ Ack erlischt ⇒ UNKNOWN; (d) unbekannte Komponente ⇒ UNKNOWN; (e) saubere Komponente (kein Surface) mit Tabellen-Hash-Match ⇒ ALLOW; (f) `version=None` sauber behandelt.
- Alle bestehenden Tests grün · CI grün · **PR mit Bericht** → **Adversarial-Panel** (kann eine unsichere Komponente ein ALLOW erschleichen? greift das Hard-Veto vor Tabelle/Ack?).
