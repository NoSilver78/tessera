# Codex-Aufgabe — E2.5 D9-Gate: Gate-Auflagen (PR #20 → Fix-Spin)
Von Claude · 2026-06-30 · Quelle: Adversarial-Gate `wgs9ia58d` (**PASS MIT AUFLAGEN**, 16 Findings) · **gleiche Branch `enforce/e2.5-d9-gate` → PR #20 aktualisieren** · non-scharf/read-only/dormant · security-relevant

## Verdikt
**PASS MIT AUFLAGEN.** Kern korrekt (fail-closed Default, Hard-Veto-Reihenfolge, content_hash-Anchor inkl. Pfad, DENY-non-ackable, dormant, CI grün/110, Tests substanziell). Aber reale Härtungs- + Test-Lücken — **vor Merge zu schließen**, weil E3 auf diesem Gate aufbaut.

## MUSS
1. **Versions-Dimension testen (HIGH — `_versions_equal`-always-True überlebt heute ALLE Tests):** jeder Test nutzt identische Versionen beidseitig → die Versions-Achse des Trust-Anchors ist nirgends getestet. Neuer Test: Tabellen/Ack-Eintrag auf version `1.0.0` mit KORREKTEM content_hash, aber Disk-manifest auf `2.0.0` → assert `verdict==UNKNOWN`, `source=="default"`. Plus None-vs-String-Kante (Ack `version=None` gegen Disk `1.0.0` → UNKNOWN).
2. **TIER-2-Invariante schließen (MEDIUM, aber Invariante):** ein Tabellen-`TIER-2` ohne `evidence_type` rutscht heute durch (Beleg-Gate `evidence_type is None→UNKNOWN` feuert NUR für ALLOW; TIER-2 nicht in `blocking`). Fix: **v1 nur `DENY/ALLOW/UNKNOWN`** im produktiven Pfad — TIER-2 entweder (a) in `blocking` UND in den Beleg-Gate (`verdict in {ALLOW, TIER-2} and evidence_type is None → UNKNOWN`), oder (b) ganz aus dem produktiven Verdict-Pfad. + Test (unbelegt TIER-2 → blockiert).

## SOLL
3. **HTTP/WS-Surface-Evasion (HIGH-Kontext):** der Substring-Grep ist für View/WS (ohne Service-Runtime-Backstop) durch obfuskierte/dynamische Registrierung (getattr/alias/chr) evadierbar — End-to-End reproduziert (HTTP-View-Bypass + Ack → ALLOW). Fix: **AST-basierte Erkennung** statt Substring (Aufruf-/Attributnamen `register_view`/`HomeAssistantView`/`async_register_command`/`websocket_command` über den Parse-Baum) — fängt getattr/alias. **Und** ehrlich dokumentieren (Docstring + `spec-e3-design.md` A.3): HTTP/WS-Detection ist statisch ohne Runtime-Backstop → `evidence_type=runtime_verified_allow` ist der eigentliche Trust-Beleg für ausführbaren Python-Code, **nicht** ein leeres Grep-Ergebnis.
4. **content_hash-Vollständigkeit (MEDIUM):** Hash über ALLE Dateien des Komponentenverzeichnisses (nicht nur .py/.yaml/manifest.json) — sonst sind .so/.pyc/.pyx / `exec(open('payload.txt'))` nach einem Ack frei mutierbar ohne den Pin zu brechen. Zusätzlich: Vorhandensein nicht-erfasster ausführbarer Artefakte (.so/.pyd/.pyc) als eigenes Surface→UNKNOWN-Signal.
5. **Freshness-Test (MEDIUM):** ein Test, der den **Loader-Pfad** real treibt (Loader liefert Integration mit `.version`, Disk präsent → assert Merge + Version-Precedence) + ein Stale-Cache-Freshness-Test (frischer Disk-Scan gewinnt gegen veralteten Cache). Heute wird Mutation „nur-Loader-Cache" nur inzident per KeyError gekillt, nicht durch eine Freshness-Assertion.
6. **`_versions_equal` Prod/Test-Parität (MEDIUM):** AwesomeVersion vs. Tuple-Split-Fallback divergieren (`1.0` vs `1.0.0`). Fallback an AwesomeVersion-Semantik angleichen ODER die Divergenz explizit dokumentieren + testen.
7. **`_ack_matches` defensiv (MEDIUM):** `ack.get("content_hash")`/`ack.get("version")` + bail-to-False statt direktem `ack["…"]` (von der Schema-Invariante entkoppeln, kein KeyError-Risiko).
8. **`_require_sha256_hex` härten (LOW):** `re.fullmatch(r"[0-9a-f]{64}", value)` (nur lowercase) + content_hash bei Validierung `.lower()`-normalisieren (compute_component_hash liefert lowercase hexdigest → Konsistenz; ein uppercase-Ack matcht sonst nie).

## NICE / DOC
9. Hash-**Stabilitäts**- + **Path-Swap**-Test (zwei Komponenten, identische Bytes unter getauschten Dateinamen → verschiedener Hash, da relative Pfade mit-gehasht).
10. `accepted_at` als **Audit-only** in E2.5 dokumentieren (Ablauf/Breakglass-Expiry erst beim E3-Apply, Teil C / C2 — nicht in E2.5 erzwingen).

## Regeln / DoD
- Nur `d9_gate.py` / `d9_classification.py` / `schema.py` + `tests/test_d9_gate.py`. **Dormant bleiben** (kein nativer Write, nicht verdrahten). Python 3.13, ruff/black/mypy-strict grün, HA-frei testbar.
- Alle alten + neuen Tests grün · CI grün · **PR #20 aktualisieren** → **Re-Gate** (greift der Versions-Test? schließt TIER-2 die Invariante? evadiert die AST-Erkennung getattr/alias noch?).
