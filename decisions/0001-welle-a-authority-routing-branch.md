# ADR 0001 — Welle-A: Autorität · Routing · Branch · Push
Stand 2026-06-29 · Status: **aktiv** (bis Vertrag v0.2 → v1.0) · Anlass: Codex Migration-Re-Gate (**PASS MIT AUFLAGEN**)

## Kontext
`CONTRACT.md` ist **in Verhandlung** (v0.2, Codex-`ACCEPT` ausstehend), wird aber von `AGENTS.md`/`CLAUDE.md`/`README.md` bereits als Prozess referenziert. Codex' Re-Gate verlangt vor dem ersten Welle-A-Schreiblauf eindeutige Übergangsregeln.

## Entscheidung
1. **Autorität für Welle A:** Die **Round-2 Work-Order v2** (Claude, von Codex `ACCEPT`) **+ dieser ADR** sind maßgeblich, bis der Vertrag **v0.2 → v1.0** final ist. Migrierte **Alt-Reports = Historie** — ihre überholte „Neubau/Risikokern-bewiesen"-Sprache ist **keine** Freigabe.
2. **Branch:** Welle-A-Code auf kurzlebigem Branch/Worktree **`welle-a/harness-hardening`**. `main` bleibt **nur gegated/grün** — Merge erst **nach A-Mini-Gate** + Secret-/Statuscheck.
3. **Routing (verbindlich, Runner MUSS folgen):** Evidence → `spike/evidence/` · Gate-/Spike-Reports → `spike/reports/` · Ping-Pong/Reviews → `exchange/YYYY-MM-DD/`. **`outputs/` ist eingefroren/Legacy — KEIN Schreibziel mehr** (jetzt in `.gitignore`).
4. **Push:** Privater-Repo-Push (Mac via `gh`) **nach grünem Gate erlaubt**, **kein `--force`**. **Public/outward/HACS/Live = nur mit Michael-Freigabe.**
5. **Gesperrt:** Enforce / Produkt / HACS-Publish / Public / Live bis Round-2-Rubrik komplett.

## Konsequenz
**Welle A startet (Codex, auf `welle-a/harness-hardening`) mit:** (1) Routing-Fix im Runner (kein `outputs/`-Write mehr) + (2) Failure-Redaction der Auth-/Onboarding-Fehlerpfade → dann (3) Instrument-Härtung (8 Services · blocking-I/O raus · Seed-Fixture) → **A-Mini-Gate** (Claude) → Merge nach `main` + Push.
