# Tessera — Public-Release-Härtung: Kreuzvalidierungs-Auftrag an Codex

**Von:** Claude (Architektur/Gate) · **An:** Codex (unabhängiger Reviewer) · **Datum:** 2026-06-30
**Typ:** Reine Analyse/Review (kein Code-Write) → Output nach `exchange/2026-06-30/`

## Warum
Tessera wird **Michaels erstes öffentliches Repo** + HACS-Integration. Vor dem Public-Flip läuft eine
**Public-Release-Härtung** (Code **und** Doku). Claude fährt parallel einen Multi-Agenten-Analyselauf
(11 Linsen, adversarial verifiziert). **Du reviewst dieselbe Codebasis UNABHÄNGIG** — ohne Claudes Funde
zu sehen — damit wir **kreuzvalidieren** können: Was *beide* finden = hohe Konfidenz; was *nur einer*
findet = genauer prüfen. Bitte nicht an einer Vorlage anlehnen, sondern frisch lesen.

## Stand (Branch `main`, lokal `~/tessera`)
- 16 Quelldateien / **4.320 LOC** (`custom_components/tessera/*.py`), 14 Test-Dateien / **5.772 LOC**.
- **pytest 213 grün · mypy · ruff · black sauber.** Der Code ist mehrfach gegated → **finde, was die
  bisherigen Gates übersahen oder was für den Public-Release fehlt — keine Lint-Trivialitäten.**

## Architektur — NICHT re-litigieren (by-design, dokumentiert)
- Store (SoT/PAP) → Compiler (PDP) → native HA-Gruppen-`PolicyPermissions` → `check_entity` (PEP). **Allow-only.**
- Modi off/monitor/enforce; enforce ist **fail-safe-to-monitor** bei jedem Fehler.
- **D9-Gate = auth-scoped Konflikt-Vermeidung, KEIN Malware-Sandbox** (HA-Custom-Components laufen als
  beliebiger privilegierter Code; SECURITY.md). Default-allow für nicht-auth-berührende Components ist
  bewusste, dokumentierte Posture.
- Dokumentierte by-design-Grenzen: Leak-Pfade (templates/logbook/assist), `change = global is_admin`.
→ Diese Punkte **nicht** als neue Findings melden.

## Scope / Linsen (decke alle 11 ab, je `file:line`)
1. **Korrektheit + Async-Lifecycle** — setup/enforce/restore/mode/unload/reload: blockierende Calls auf
   dem Loop, await-Korrektheit, fail-safe-Vollständigkeit, partial-apply/Crash-Recovery, Races.
   (`__init__.py`, `mode_manager.py`, `restore.py`, `auth_adapter.py`, `state.py`)
2. **Auth-Security (echte Bugs, nicht der dokumentierte Scope)** — privilege-escalation/lockout,
   allow-only, owner/system-generated-Schonung, No-Drop-Superset, Snapshot/Restore-Korrektheit,
   D9-Auth-Marker-Vollständigkeit vs **echter** HA-Auth-API.
   (`auth_adapter.py`, `restore.py`, `mode_manager.py`, `d9_gate.py`, `compiler.py`, `resolver.py`)
3. **Vereinfachung** — dead code, Duplikation, Über-Komplexität, unbenutzte Params/Imports (ohne
   Verhaltensänderung). (alle Dateien)
4. **Typ-Schärfe jenseits mypy** — unsichere `cast()`, `Any`-Leakage, lose/unvollständige TypedDicts,
   Protocol-Mismatches, Runtime-Typen ≠ Annotation, fehlendes None-Handling. (alle Dateien)
5. **Konsistenz + öffentliche Oberfläche** — Naming, Idiome, Fehler-Typ-Hierarchie, Docstring-Genauigkeit,
   const-Zentralisierung vs Magic-Strings, Logging-Konsistenz, public vs `_private`. (alle Dateien)
6. **Test-Fidelity** — ungetestete Branches/Fehlerpfade, **vakuum-Tests** (würden auch bei kaputtem Code
   bestehen), fehlende Grenzfälle, falsch-asserting Tests. (`tests/`)
7. **Config/Admin-Surface** — config_flow-Validierung/reauth/options, websocket-Command-Autorisierung +
   Input-Validierung, store-Schema-Versionierung/Migration, state-Persistenz.
   (`config_flow.py`, `websocket.py`, `store.py`, `schema.py`, `state.py`)
8. **README + Contributor-Onboarding** — Install/Config/Usage akkurat **und** vollständig? Was fehlt für
   eine öffentliche HACS-Integration? Inakkurates vs echtem Code? (`README.md`, `CONTRIBUTING.md`)
9. **Security-Doku-Ehrlichkeit** — Threat-Model + Leak-Pfade + Versions-Pin akkurat/vollständig/ehrlich?
   Overclaim/Lücke vs Code? (`SECURITY.md`, `docs/MAINTENANCE.md`)
10. **Doku↔Code-Drift** — `README`/`ROADMAP`/`docs/spec-*`/`docs/concept.md` vs **echtes** Verhalten
    (v.a. nach D9 v2 auth-scoped + enforce-Verdrahtung): veraltete Claims, falsche Datei-/Funktionsnamen,
    Status-Marker, Widersprüche. Beide Seiten zitieren (Doku-Zeile + Code-Realität).
11. **Release-Readiness** — `RELEASE_READINESS.md`, `CHANGELOG.md`, `LICENSE`, `hacs.json`,
    `manifest.json`: Lizenz-Korrektheit, Changelog-Vollständigkeit/Format, Versions-Konsistenz, Issue/PR-
    Templates, Beispiele, HACS/brands-Schritte, semver, Badges. Konkrete Lücken.

## Output-Format (für maschinelles Cross-Matching)
Datei: `exchange/2026-06-30/tessera-release-hardening-crossvalidation-codex-2026-06-30.md`.
Je Fund eine Zeile/ein Block:
`ID · Linse · Severity(CRITICAL|HIGH|MEDIUM|LOW|INFO) · Kind(bug|security|simplification|type|consistency|test-gap|doc-inaccuracy|doc-gap|release-gap) · Ort(file:line) · Evidenz · Empfehlung`
Plus je Linse eine kurze Zusammenfassung. **Default skeptisch:** lieber wenige hochwertige als viele
triviale Funde; jeder Fund konkret + umsetzbar.

## Regeln (hart)
- `/Volumes/config` + **Live-CM5 read-only/tabu**; Auth-Tests nur `ha-tessera-dev`; **keine Secrets**.
- **Reiner Review — kein Code-Write.** Leitest du konkrete Fixes ab → separate Implementierungs-Welle
  (Branch/PR), nicht in diesem Review.
- Bei Unklarheit/Risiko: fail-closed, Michael fragen.

## Danach
Claude matcht deine Funde gegen den eigenen Lauf → Schnittmenge = sofort umsetzen, Einzel-Funde =
adversarial nachprüfen. Reconciliation + Umsetzung dann durch Claude (mit venv-Verifikation +
Mutationsproben), Übergabe-Paket folgt.
