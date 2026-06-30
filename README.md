# Tessera

Standalone **RBAC für Home Assistant** (HACS-Integration): pro **Rolle × Area/Entity** die Stufen *ansehen / bedienen / ändern*, **als Architektur-Ziel** echt durchgesetzt auf **nativen HA-`PolicyPermissions`** (kein Monkeypatch, kein Core-Fork; **Phase 1 = read-only Monitor, noch keine Durchsetzung — siehe unten**), optional **Authentik/OIDC**. Unabhängig von Atrium.

## Zwei-Agenten-Entwicklung
Tessera wird von **Claude** (Architektur / Gate / Audit — siehe [`CLAUDE.md`](CLAUDE.md)) und **Codex** (Implementierung — siehe [`AGENTS.md`](AGENTS.md)) gebaut, orchestriert von Michael. Der verbindliche Prozess steht in **[`CONTRACT.md`](CONTRACT.md)**, das Arbeitsmodell in [`CLAUDE_WORKFLOW.md`](CLAUDE_WORKFLOW.md).

## Repo-Karte
| Pfad | Inhalt |
|---|---|
| `docs/` | kanonische Wahrheit: `concept.md`, `spec-phase0.md`, `charter.md`, `requirements.md` (kein Datum im Namen — Stand via git) |
| `exchange/` | **Blackboard** — datierte Ping-Pong-Artefakte (`YYYY-MM-DD/<scope>-<kind>-<author>.md`) |
| `spike/` | Phase-0-Spike: `evidence/`, `reports/` (Gate-Reviews), `tools/tessera_spike/` (Mess-Harness) |
| `decisions/` | ADRs (Architecture Decision Records) |

## Status (2026-06-29)
**Phase-0-Spike: PASS MIT AUFLAGEN.** D1/D2/D4 signalisieren **positiv** — Auth-Store-Schreibpfad persistiert + überlebt Restart, Cache-Invalidierung (explizit) + Union/Restore funktionieren. **Recovery (D5) + Breite (M2/M4/M5/M6) noch offen** → **Schreibpfad-*Machbarkeit* signalisiert, Neubau plausibler Default; finale Architektur-/Enforce-Entscheidung erst nach kompletter Round-2-Rubrik.** Kein Enforce-Go.

## Funktionsumfang & Sicherheitsstand (Phase 1)
Tessera kennt drei Modi (Integration → Optionen → *Set mode*):
- **off** — Tessera tut nichts.
- **monitor** — kompiliert die Rollen-Policies zu einer **read-only Vorschau** (Matrix-Panel + Logs), **ohne** Home Assistant zu verändern.
- **enforce** — **aktuell ein Platzhalter: fällt auf die Monitor-Vorschau zurück und führt KEINE nativen `hass.auth`-Writes aus.** Echte Durchsetzung kommt erst in einer späteren Phase (nach Benchmark + Review).

Bedienung über das **Admin-Panel** „Tessera" in der Seitenleiste (`require_admin` — nur Administratoren) oder den Options-Flow der Integration. Der Dienst **`tessera.recompile`** erneuert die Monitor-Vorschau (kein nativer Write).

> **Sicherheits-Hinweis:** In Phase 1 setzt Tessera **keine** Berechtigungen real durch — es ist ein read-only Planungs-/Monitoring-Werkzeug, bis Enforce bewusst scharfgeschaltet wird.

## Secrets
Keine Secrets im Repo (`.gitignore`). Credentials ausschließlich via 1Password. **Auth-Tests nur gegen die Dev-Instanz `ha-tessera-dev`, niemals die Live-Instanz.**
