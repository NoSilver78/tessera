# Tessera

Standalone **RBAC für Home Assistant** (HACS-Integration): pro **Rolle × Area/Entity** die Stufen *ansehen / bedienen / ändern*, echt durchgesetzt auf **nativen HA-`PolicyPermissions`** (kein Monkeypatch, kein Core-Fork), optional **Authentik/OIDC**. Unabhängig von Atrium.

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
**Phase-0-Spike: PASS MIT AUFLAGEN.** Der private Auth-Store-Schreibpfad funktioniert + überlebt HA-Restart (D1/D2/D4 PASS) → **Neubau bestätigt**. Round-2-Härtung läuft (Welle A: Instrument-Fix + Seed-Fixture). **Kein Enforce-Go**, bis Round-2 grün.

## Secrets
Keine Secrets im Repo (`.gitignore`). Credentials ausschließlich via 1Password. **Auth-Tests nur gegen die Dev-Instanz `ha-tessera-dev`, niemals die Live-Instanz.**
