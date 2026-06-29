# Welle-C-Gate (PR #9, D3/D6/D7/D8) — 2026-06-29
Adversariales Re-Gate-Panel (6 Skeptiker), **problemCount=0**. Gemerged als `cc374df`.

## Entscheidung: PASS
Welle C als ehrliche Messung der Runtime-/Leak-Matrix abgenommen. Kein `claimHolds=false` auf D3/D8, kein `falsePass`, kein Streu-Grün, keine Regression (Produkt-Tree-Hash main==welle-c identisch, enforce-frei).

- **D3 — PASS real.** Verdikt = interne `check_entity` (READ+CONTROL × allowed/forbidden) AND 11-fache Konjunktion echter REST+WS-Status. WS ist echtes aiohttp-I/O (kein Stub). Asymmetrie gemessen (200 vs 401, server-origin `Unauthorized`), restringierter Token. Nicht-tautologisch.
- **D6 — PASS ehrlich gescoped.** `entity_targeted_pass` real gemessen; beide realen Bypässe als `ENFORCE_BYPASS` ausgewiesen (nie „safe"). Kein falsches PASS.
- **D7 — PARTIAL ehrlich.** `complete_matrix=false` erzwingt PARTIAL; Registry/render_template-Leaks real gemessen (`leak_hint=bool(result)`, `forbidden_entity_seen`); LEAK wird vor NOT_VERIFIABLE geprüft → maskiert nie einen Leak.
- **D8 — PASS real.** Echtes LLAT (create→headless→revoke→Replay `401`); Token-Werte redigiert (0 Bearer-Treffer).
- **D5** strukturell nie PASS · **Isolation** sauber.

## ⭐ Architektur-Befunde für v1-Enforce (das eigentliche Ergebnis)
Diese drei sind **empirisch bestätigt** und steuern das Enforce-Design (→ später eigener Enforce-ADR):

1. **`check_entity` ist NICHT der vollständige Enforce-Punkt.** Zwei reale Bypässe: (a) `Context(user_id=None)` — System-/Automations-Kontext schreibt an `check_entity` vorbei (off→on trotz Verbot, Status 200); (b) **non-entity-Services** haben kein Entity-Target zum Prüfen. → v1-Enforce darf sich **nicht allein** auf entitäts-getargetete Checks stützen.
2. **`view` leakt — view ist keine Confidentiality-Boundary.** Registry-Reads (entity/device/area) + `render_template` liefern dem restringierten User verbotene Entities/Ergebnisse. → v1 zielt auf **`operate/control` als durchsetzbare Grenze**; `view` = Best-Effort-Sichtbarkeitsfilter, **nicht** als Vertraulichkeitsgrenze verkaufen.
3. **`Context(user_id=None)` braucht eine explizite v1-Policy-Entscheidung** (System/Automation-Identität): eigene Enforce-Behandlung **oder** bewusst dokumentierter Trust-Boundary-Ausschluss — nicht still als PASS durchrutschen.

## Auflage (nicht-blockierend, mit Welle D mitnehmen)
- **A1 — Report re-rendern:** die „Gesamturteil"-Prosa (`spike/reports/...:11`) ist stale ggü. dem gehärteten Template (D7 noch unter „belastbare Signale" gelistet). Reiner Narrativ-Drift; die bindende DoD-Tabelle zeigt korrekt `D7|PARTIAL`. Re-Render vor v1-Enforce-Sign-off.

## Rubrik-Stand (v1-Enforce-Go)
D1/D2/D4 ✅ · D3/D6 ✅ (entity-targeted) · **D7/D8 dokumentierte Leak-Matrix ✅** · D5 ⏳ PARTIAL (echter Rescue offen) · D9 ⏳ (Welle D) · D12 ⛔ BLOCKED · D11/D13/D15 noch offen. **Enforce-Go weiterhin gated.**
