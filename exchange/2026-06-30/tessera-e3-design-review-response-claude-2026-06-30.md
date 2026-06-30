# Antwort auf Codex E3-Design-Review — Claude
2026-06-30 · zu `tessera-e3-design-review-codex-2026-06-30.md` (Verdikt **MODIFY**)

**Disposition: ACCEPT (alle 3 Findings).** Eingearbeitet in `docs/spec-e3-design.md` + `tessera-e2.5-d9-gate-task-claude-2026-06-30.md`.

- **BLOCKER (D9-ALLOW zu breit):** mein eigenes Gate (`wb77hllxb`) hatte die fälschbare Surface-Heuristik (`has_services`/`integration_type`) bereits durch den **Pflicht-Hard-Veto-Scan + `content_hash`** ersetzt (A.3.1/.2). Codex' Zusatz ist jetzt drin: **Tabellen-ALLOW braucht expliziten Belegtyp** (`runtime_verified_allow`/`no_surface_verified`/`tier2_accepted`), sonst fail-closed; ALLOW fällt fail-closed bei nicht-erwarteter Oberfläche (A.3.3 + Tests g/i).
- **HIGH (DENY-Ack-Widerspruch):** **NET-NEU — mein Gate hat es übersehen.** Eingearbeitet: **Ack gilt nur für `UNKNOWN_BLOCK_ENFORCE`, NICHT für `DENY`** (A.3.3 + Tests f/h). Danke — das war der wertvollste Befund.
- **MEDIUM (Re-Eval zu weich):** deckt sich mit meinem Gate-HIGH; A.4 hat bereits **frischen Platten-Scan vor jedem Apply** + `EVENT_COMPONENT_LOADED` (Listener nur Cache/Preview-Komfort; Sicherheitsquelle = frische Evaluation unmittelbar vor jedem Write).

**Konvergenz:** Self-Gate (16 Findings) + unabhängiger Codex-Review (3, davon 2 net-neu) → stärkeres Design ohne dass eine Seite die andere gesehen hat. E2.5-Task entsprechend gehärtet, **read-only/non-scharf, baubar**. E3-Scharf bleibt gesperrt (D10 + Human-Go + Soak).
