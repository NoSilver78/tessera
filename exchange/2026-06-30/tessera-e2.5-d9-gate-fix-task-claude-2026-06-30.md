# Codex-Arbeitsauftrag — E2.5 D9-Gate: Gate-Auflagen einarbeiten (PR #20 → Fix-Spin)

Von **Claude** · 2026-06-30 · Quelle: Adversarial-Gate `wgs9ia58d` (**PASS MIT AUFLAGEN**, 16 Findings) · Report `reports/e25-d9-gate-review-2026-06-30.md`
**Branch:** weiter auf **`enforce/e2.5-d9-gate`** → **PR #20 aktualisieren** (nicht neu). **Non-scharf / read-only / dormant.** Security-relevant.

## 0. Worum es geht (Kontext)
`evaluate_d9_gate` ist der fail-closed Produkt-Gate, der vor jedem späteren Enforce-Write installierte Custom-Components klassifiziert. Der Kern ist korrekt (Hard-Veto vor Tabelle/Ack, content_hash-Anchor, DENY-non-ackable, dormant, CI grün/110). Das Gate hat aber **echte Härtungs- und Test-Lücken**, die VOR Merge zu schließen sind, weil E3 genau auf diesem Gate aufbaut. Bitte exakt die folgenden Punkte umsetzen — Reihenfolge MUSS → SOLL → NICE.

## 1. Hard-Regeln (was NICHT ändern)
- **Dormant bleiben:** `d9_gate` wird **nirgends verdrahtet** (kein Aufruf aus `__init__.py`/`config_flow.py`/`websocket.py`/`monitor.py`). **Kein nativer Write.**
- Nur diese Dateien anfassen: `custom_components/tessera/d9_gate.py`, `custom_components/tessera/d9_classification.py`, `custom_components/tessera/schema.py`, `tests/test_d9_gate.py`. (Doku-Nachzug in `docs/spec-e3-design.md` A.3 erlaubt.)
- Bestehende korrekte Eigenschaften **nicht** schwächen: Hard-Veto läuft **vor** Tabelle/Ack; ALLOW nur mit `(domain, version, content_hash)`-Match **und** `evidence_type`; DENY nie per Ack freischaltbar; Default `UNKNOWN_BLOCK_ENFORCE`.
- Python 3.13, ruff/black/mypy-strict grün, Google-Docstrings, HA-frei testbar.

---

## 2. MUSS (Merge-blockierend)

### M1 — Versions-Dimension des Trust-Anchors testen *(HIGH — heute komplett ungetestet)*
**Problem:** In `tests/test_d9_gate.py` benutzt **jeder** Tabellen-/Ack-Test identische Versionen auf beiden Seiten (Disk-Version == Tabellen-/Ack-Version, beide `"1.0.0"` oder beide `None`). Dadurch **überlebt eine Mutation, die `_versions_equal` (`d9_gate.py`) hart auf `return True` setzt, ALLE 11 Tests.** Die Versions-Achse des Anchors ist nirgends abgesichert. (Der Docstring von `test_ack_expires_when_content_hash_changes` behauptet „bound to domain, version, and content hash", testet aber nur den Hash.)

**Fix — zwei neue Tests:**
1. `test_table_version_mismatch_is_unknown`: Komponente mit `manifest.version = "2.0.0"` schreiben; `CLASSIFICATIONS` monkeypatchen mit einem Eintrag `version="1.0.0"`, `content_hash=compute_component_hash(component)` (also **korrekter** Hash, aber **falsche** Version), `verdict=ALLOW`, `evidence_type="no_surface_verified"`. → assert `verdict == UNKNOWN_BLOCK_ENFORCE` **und** `source == "default"` (kein Match, weil Version differiert). *Dieser Test failt, sobald `_versions_equal` immer True liefert.*
2. `test_ack_version_none_vs_string_is_unknown`: Komponente mit `manifest.version = "1.0.0"`; Ack mit `version=None` + korrektem `content_hash`. → assert `verdict == UNKNOWN_BLOCK_ENFORCE`, `source == "default"` (None-vs-String darf nicht matchen — pinnt den `None`-Asymmetrie-Zweig von `_versions_equal`).

### M2 — `TIER-2`-Invariante schließen *(MEDIUM, aber Invarianten-Loch)*
**Problem:** `D9_VERDICT_TIER_2` existiert (`d9_classification.py`), aber (a) das `blocking`-Set in `evaluate_d9_gate` (`d9_gate.py`) enthält nur `{DENY, UNKNOWN}` → **TIER-2 blockt Enforce NICHT**, und (b) der Beleg-Gate `if entry.verdict == ALLOW and entry.evidence_type is None: → UNKNOWN` (`_classify_component`) feuert **nur für ALLOW**. Folge: ein Tabellen-Eintrag `verdict=TIER-2` **ohne** `evidence_type` lässt eine Komponente **ohne jeden Beleg** durch Enforce.

**Fix (beides):**
1. In `evaluate_d9_gate` TIER-2 **ins `blocking`-Set** aufnehmen: `result["verdict"] in {D9_VERDICT_DENY, D9_VERDICT_UNKNOWN, D9_VERDICT_TIER_2}`. Semantik: TIER-2 = „braucht Zusatz-Controls, in v1 kein Auto-ALLOW" → blockt, bis ein expliziter höherwertiger Pfad existiert.
2. Den Beleg-Gate in `_classify_component` auf TIER-2 ausweiten: `if entry.verdict in {D9_VERDICT_ALLOW, D9_VERDICT_TIER_2} and entry.evidence_type is None: → UNKNOWN`.

**Tests:** `test_tier2_blocks_enforce` (TIER-2-Eintrag mit Beleg + Match → `domain in blocking`, `enforce_blocked is True`) und `test_tier2_without_evidence_is_unknown` (TIER-2 ohne `evidence_type` → `verdict == UNKNOWN`, `source == "classification"`).

---

## 3. SOLL (vor Merge)

### S1 — HTTP/WS-Surface-Detection von Substring-Grep auf AST umstellen + ehrlich dokumentieren *(HIGH-Kontext)*
**Problem:** `_detect_static_surfaces` (`d9_gate.py`) erkennt View/WS **nur per Substring** (`"HomeAssistantView" in text` …). Anders als SERVICE (Runtime-Backstop via `hass.services.async_services()`) gibt es für HTTP/WS **keinen** Runtime-Abgleich. Eine Komponente, die `register_view`/`async_register_command` über `getattr`, aliasierte Importe oder String-Konstruktion baut, **evadiert den Grep vollständig** (End-to-End reproduziert: HTTP-View-Bypass + Admin-Ack → `verdict=ALLOW`).

**Fix:**
1. `_detect_static_surfaces` für `.py`-Dateien auf **AST** umstellen (`import ast`):
   - `ast.parse(text)`; bei `SyntaxError` → **fail-closed**: Datei als Surface werten (nicht-parsebarer Python-Code ist verdächtig).
   - Über `ast.walk` referenzierte Namen sammeln: `ast.Attribute.attr`, `ast.Name.id`, `ast.alias.name`/`asname`, **und** String-`ast.Constant`-Werte (fängt das einfache `getattr(x, "register_view")`).
   - Marker-Mengen: `{"register_view", "HomeAssistantView", "panel"}` → `SURFACE_HTTP`; `{"websocket_command", "async_register_command"}` → `SURFACE_WEBSOCKET`; `{"async_register"}` (Service-Registrierung) → `SURFACE_SERVICE`.
   - `.yaml`/`manifest.json` weiter als Text behandeln (kein AST).
2. **Ehrliche Doku** (Docstring von `_detect_static_surfaces` + `docs/spec-e3-design.md` A.3): HTTP/WS-Detection ist statisch (AST) **ohne** Runtime-Route/WS-Registry-Backstop; durch `exec`/`chr()`-konstruierte dynamische Registrierung **statisch nicht** vollständig fangbar. Daher ist der eigentliche Trust-Beleg für ausführbaren Python-Code `evidence_type="runtime_verified_allow"`, **nicht** ein leeres Scan-Ergebnis.

**Tests:** `test_aliased_view_import_is_surface` (`from ...http import HomeAssistantView as HV` → AST findet `HomeAssistantView` am Import → `surface_veto`/UNKNOWN); `test_getattr_string_marker_is_surface` (`getattr(hass.http, "register_view")` → String-Konstante gefangen → UNKNOWN); `test_unparseable_py_is_surface` (kaputtes `.py` → `SyntaxError` → fail-closed UNKNOWN).

### S2 — content_hash-Vollständigkeit + Compiled-Artefakt-Signal *(MEDIUM)*
**Problem:** `_iter_hash_files`/`compute_component_hash` decken nur `.py`/`.yaml`/`manifest.json`. Ausführbarer/ladbarer Code in `.so`/`.pyd`/`.pyx`/`.pyc` oder via `exec(open("payload.txt").read())` ist (a) für den Surface-Scan unsichtbar **und** (b) **nicht** im content_hash → nach einem Ack beliebig mutierbar, ohne den Pin zu brechen.

**Fix:**
1. `_iter_hash_files`: **alle** Dateien des Komponentenverzeichnisses hashen (`rglob("*")`, `is_file()`), **außer** `__pycache__/` (sonst instabiler Hash durch regenerierte `.pyc`). Relative Pfade weiter mit-hashen (Path-Swap-Schutz bleibt).
2. **Compiled-Artefakt = Surface:** Vorhandensein von `.so`/`.pyd`/`.pyx` **oder** einer `.pyc` außerhalb `__pycache__` → neues Surface-Signal (z.B. `SURFACE_COMPILED = "compiled_artifact"`) → UNKNOWN.

**Tests:** `test_hash_covers_non_source_files` (zusätzliche `.txt`/`.bin` ändert den Hash); `test_compiled_artifact_is_surface` (eine `.so` im Verzeichnis → `surface_veto`/UNKNOWN); `test_pycache_excluded_from_hash` (eine Datei unter `__pycache__/` ändert den Hash **nicht**).

### S3 — Freshness-/Loader-Pfad real testen *(MEDIUM)*
**Problem:** Die autouse-Fixture `_mock_loader` liefert in **jedem** Test `{}`, daher läuft Discovery ausschließlich über den Disk-Scan. Der Loader/Disk-Merge und die Version-Precedence in `_component_version` (`d9_gate.py`) sind **unexerziert**; die „nur-Loader-Cache"-Mutation wird nur inzident per `KeyError` gekillt, nicht durch eine Freshness-Assertion.

**Fix — zwei Tests (mit überschriebenem Loader-Mock):**
1. `test_loader_path_merges_and_version_precedence`: `_async_get_custom_components` liefert für eine Domain (die **auch** auf Disk liegt) ein Fake-Integration-Objekt mit `.version="9.9.9"`; Disk-manifest hat `"1.0.0"`. → assert `by_component[domain]["version"] == "9.9.9"` (Loader-Precedence) und die Komponente wird klassifiziert (Merge funktioniert). Zusätzlich eine **nur im Loader** (nicht auf Disk) vorhandene Domain → wird evaluiert mit `content_hash is None` → UNKNOWN.
2. `test_fresh_disk_hash_beats_stale_table`: Komponente auf Disk; `CLASSIFICATIONS`-Eintrag pinnt einen **alten** `content_hash` (z.B. `"0"*64`) bei passender Version. → assert UNKNOWN/`default` (frischer Disk-Hash ≠ gepinnter alter Hash → kein Match) — beweist, dass der frische Disk-Scan gewinnt.

### S4 — `_versions_equal` Prod/Test-Parität *(MEDIUM)*
**Problem:** Prod nutzt `AwesomeVersion` (`AwesomeVersion("1.0") == AwesomeVersion("1.0.0")` → True), der HA-freie Fallback nutzt `tuple(s.split("."))` (`("1","0") != ("1","0","0")`). Beide Pfade divergieren bei `"1.0"` vs `"1.0.0"`.
**Fix:** Im Fallback beide Seiten gleich normalisieren (trailing `"0"`-Segmente strippen), sodass die Semantik AwesomeVersion spiegelt. **Test:** `test_versions_equal_trailing_zero_parity` (`"1.0"` vs `"1.0.0"` → equal in beiden Pfaden).

### S5 — `_ack_matches` defensiv entkoppeln *(MEDIUM)*
**Problem:** `_ack_matches` liest `ack["content_hash"]`/`ack["version"]` direkt → an die Schema-Invariante gekoppelt (KeyError-Risiko bei künftigen Schema-Änderungen).
**Fix:** `ack.get("content_hash")`/`ack.get("version")` verwenden, bei fehlendem `content_hash` → `return False`.

### S6 — `_require_sha256_hex` härten *(LOW, aber stiller never-match-Bug)*
**Problem:** `_require_sha256_hex` (`schema.py`) prüft `len == 64` + `int(value, 16)` → akzeptiert **Großbuchstaben**. `compute_component_hash` liefert aber lowercase `hexdigest()` → ein uppercase-Ack passiert die Validierung, **matcht aber nie** (stiller Fehlschlag).
**Fix:** `re.fullmatch(r"[0-9a-f]{64}", value)` (nur lowercase) **und** den Wert bei der Validierung mit `.lower()` normalisiert speichern. **Test:** Schema-Reject (oder -Normalisierung) für uppercase-Hash (im bestehenden parametrisierten `test_config_schema_rejects_invalid_d9_acks` ergänzen, mit `match`).

---

## 4. NICE / DOC
- **N1** `test_compute_hash_is_stable` (zweimal gleich) + `test_path_swap_changes_hash` (zwei Komponenten, identische Datei-Bytes unter getauschten Namen → verschiedener Hash).
- **N2** `accepted_at` als **Audit-only in E2.5** dokumentieren (Docstring + A.3): Acks laufen in E2.5 **nicht** ab, Re-Validierung ist hash-getrieben; Ablauf/Breakglass-Expiry erst beim E3-Apply (Teil C / C2). Keine Zeit-Logik in E2.5 einbauen.

## 5. Definition of Done
- M1, M2, S1–S6 umgesetzt; N1/N2 erledigt oder bewusst als „nicht gemacht" im Bericht vermerkt.
- **Alle** bestehenden + neuen Tests grün; `ruff check .`, `black --check .`, `mypy custom_components/tessera`, `pytest` grün; **CI grün**.
- **Selbstcheck (Mutationsproben):** `_versions_equal`→`return True` failt jetzt mind. M1; TIER-2-ohne-Beleg failt jetzt M2; AST-Erkennung fängt den aliasierten Import.
- **PR #20 aktualisieren** (gleiche Branch) + **Abschlussbericht** (was geändert, welche Tests neu, welche Mutationen jetzt gefangen). → Claude fährt das **Re-Gate**.
