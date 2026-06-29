# Tessera — Overnight-Arbeitslog + Plan (2026-06-29 Abend → 30 früh)
Autonom-Direktive (Michael): „mach weiter bis morgen früh · best-practice · kritisch · Ergebnisse validieren · Entscheidungen+Pläne reflektieren". Rollen: **Codex implementiert**, **Claude gated/auditiert/plant** (Agentensystem nur für Claudes Seite).

## ⚠️ Leitplanke (die wichtigste autonome Entscheidung — kritisch begründet)
**Ich schalte Enforce (E3) NICHT autonom scharf.** E3 aktiviert native `hass.auth`-Writes auf der Live-Logik = echte RBAC-Durchsetzung auf einem Zuhause. Best-practice für ein Sicherheitsprodukt verlangt: (a) **D10** (CM5-`.storage/auth`-Benchmark, bei Michael — offen) als Voraussetzung, (b) **Human-in-the-loop** für den Scharf-Schritt + eine Soak-Phase. → Ich **bereite E3 vor** (Spec/Task), **merge es aber nicht autonom**. Alles Dormant-/Compile-only-Niveau (E2, Hardening, Audit) ist autonom validierbar + mergebar nach Panel-PASS.

## Plan (non-scharf, validierbar) — adaptiv
1. **E2 fertigstellen** (Re-Gate `wopvj4300` läuft → merge bei PASS, sonst Fix-Relay an Codex).
2. **Hardening-Cleanup** (offene nicht-blockierende Auflagen, je 1 Task → Panel/Review → merge): D5 `auth_store_corrupted`-Rename + Seed-De-Literalisierung (`d5-gate`) · E1 Boundary-Test-Härtung (`e1-gate` nice-to-have) · Welle-C-Report-Drift (`welle-c-gate` A1).
3. **Foundation-Check** (E1-Adapter + E2-Linter integriert) — gezielt, **nicht** redundant-teuer (per-PR-Panels haben schon validiert); nur wenn Integrations-Risiko sichtbar.
4. **E3/E4/E5-Spec verfeinern** (ready für D10) — Planung, kein Merge.
5. **Reflexion/Risiken** laufend hier festhalten.

## Gate-Disziplin (unverändert)
Jede Codex-PR → Adversarial-Panel (enforce-kritisch) bzw. Eigen-Review (trivial). **Kein unehrliches Grün; FAIL → Re-Spin.** Bisher **5 Defekte gefangen** (D5/D12/D11/E1/E2). Bei Modell-Flake: kritische Claims selbst gegen Code+Evidence verifizieren.

## Pacing
Event-getrieben (Monitor `bknqcotob` auf PRs + Workflow-Completions) + Heartbeat (~30 min) für proaktive Schritte bei Codex-Idle. **Keine Busywork** — finite, hochwertige Schritte; sonst lange Idle-Ticks + warten.

## Log
- **~Abend:** E2-Re-Gate-Panel gestartet (`wopvj4300`); Codex' Fix (`41a7384`, rollenscharfe Read-Suppression via `issubset`) sieht in Eigen-Sicht korrekt aus, CI grün — Panel bestätigt adversarial.

- **E2 PASS + gemerged** (Re-Gate `wopvj4300`, problemCount=1=low-test-coverage-Overclaim; 2 lasttragende Claims sauber, A/B-reproduziert). **False-Green-Check:** CI installiert `homeassistant` → Linter-Tests laufen real (**83 passed**, +9); die „silent-skip"-Auflage ist nur lokale Dev-Bequemlichkeit. **6. Defekt-Klasse gefangen + behoben** (per-Entity- statt rollenscharfe Read-Suppression).
- **Nächster Schritt:** Test-Hygiene-Cleanup (E1-Boundary-Test-Härtung + lokale Test-Kollektierbarkeit) an Codex; parallel verfeinere ich die E3-Spec (kein Scharf-Merge).

- **Test-Hygiene-Task raus** (`enforce/e1-test-harden`): E1-Boundary-Test gegen `except Exception`-Swallow härten (Zugriffs-Registrierung statt Raise-Propagation) — die Dormant-Safety-Wache robust machen. Trivial-Gate.
- **E3-Spec verfeinert** (`docs/spec-e3-enforce.md`): Mode-Manager + Schreib-Sequenz mit 7 harten Gates (Version→Compile→D9→Linter→Superset-Write→Cache→Snapshot), Restore, Invarianten, offene Design-Fragen für die D10/Morgen-Runde. **Kein Scharf-Merge** — wartet auf D10 + Human-Go.
