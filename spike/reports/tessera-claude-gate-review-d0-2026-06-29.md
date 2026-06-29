# Gate Review — Tessera Phase-0 / D0 (Bootstrap + Preflight)

> **OBSOLETE / ersetzt:** Dieses frühe D0-Gate wurde durch
> `reports/welle-b-gate-2026-06-29.md` und den anschließenden Welle-B-Fix
> überholt. Der aktuelle Stand ist: D5 bleibt PARTIAL, native `group_ids`
> schreibt REPLACE, D12 bleibt BLOCKED.

Stand 2026-06-29 · Modus: **Gate-/Auditmodus** · Geprüft: `tessera-d0-evidence-2026-06-29.{md,json}` gegen **D0-Exit-Gate v1 (12 Punkte)** + Spec `tessera-phase0-SPEC-2026-06-29.md`

## Entscheidung
**PASS MIT AUFLAGEN**

## Kurzbewertung
Der D0-Bootstrap ist solide und **ehrlich** evidenziert: harte Target-Isolation (pre + recreated geprüft), exakte Fresh-Baseline (genau der `system_generated`-Content-User — die Korrektur sitzt), REST-Onboarding + Token-Exchange (200, Werte redacted), Harness geladen (services 200), Recreate bewiesen, Re-Read vor Write. **10 der 12 Gate-Punkte voll belegt.** Zwei D0-Scope-Punkte sind aus der Evidence **nicht** verifizierbar — nicht weil sie fehlschlugen, sondern weil die Evidence sie nicht zeigt: das **Seed-Fixture-Inventar** (D3/D6/D7 hängen daran) und die **tatsächliche Ausführung von Restore-to-native** (D4/D5 — bisher Primitive verdrahtet + Recreate bewiesen). Beides blockiert den **Start** von D1–D9 nicht, muss aber im Spike-Report belegt sein, sonst sind D3/D6/D7 bzw. D4/D5 nicht belastbar.

## Kritische Punkte
(keine)

## Hohe Punkte
| Bereich | Problem | Auswirkung | Konkrete Korrektur |
|---|---|---|---|
| Seed-Evidence | D0-Evidence zeigt Onboarding, aber **nicht** das deterministische Seed-Inventar | D3/D6/D7 messen sonst zufällige Integrationsverfügbarkeit statt RBAC-Verhalten — Ergebnisse nicht belastbar | Seed-Fixture explizit evidenzieren: je Domain ≥1 erlaubte + 1 verbotene Entity, state-only ohne Registry, hidden vs disabled, ≥1 entity-component + 1 non-entity + 1 unsafe-custom Service — als Inventar-Liste (entity_id/Klasse/Flags, keine Secrets) im Spike-Report |

## Mittlere Punkte
| Bereich | Problem | Auswirkung | Konkrete Korrektur |
|---|---|---|---|
| Restore-Pfad | Gate-Punkt 11: Recreate bewiesen, aber **Restore-to-native nicht ausgeführt** evidenziert (nur `d4_union_restore`/`d5_restore_primitive` verdrahtet) | Rescue (D5) + Union-Restore (D4) sind die sicherheitskritischsten Pfade — „verdrahtet" ≠ „bewiesen" | Restore real ausführen + Re-Read-Beleg (Counts/Flags vor/nach) im Report |
| Snapshot-Artefakt | Pre-Write-Snapshot = `auth_baseline_reread`; ein expliziter Membership-Snapshot für Restore ist nicht separat ausgewiesen | bei Teilfehler unklar, worauf zurückgesetzt wird | sanitized Membership-Snapshot vor erstem Write als eigenes Evidence-Feld |

## Niedrige Punkte
| Bereich | Problem | Auswirkung | Konkrete Korrektur |
|---|---|---|---|
| `post_restart 401` | `post_restart_http_status: 401` ist unkommentiert | Leser könnte 401 als Fehler lesen | Einzeiler: 401 = erwartete Auth-Anforderung (kein Token im Roh-Probe); Service-Call selbst `ok:true` |

## Positive Beobachtungen
- **Isolation doppelt geprüft** (`pre_existing_target` + `recreated_target`, beide `isolation_ok:true`): Volume-Mount `ha-tessera-dev-config:/config`, **kein** `/Volumes/config`-Bind, Port 8124, Image gepinnt. Genau das geforderte harte Gate.
- **Baseline exakt = `system_generated`-Korrektur** (1× „Home Assistant Content", system_generated, is_owner:false, system-read-only, credentials 0; 1 system-Token) — sauber allowlisted, kein Grob-Filter.
- **Secrets sauber:** `token_values_redacted:true`, `secret_policy` gesetzt, nur body_keys/Counts/Flags.
- **Re-Read vor Write** (`auth_baseline_reread`) umgesetzt.
- **Harness real geladen** (services 200) mit allen D1–D9-Probe-Keys verdrahtet (pre/post-restart).

## Nicht prüfbare Punkte
- **D1–D9-Ergebnisse** — kommen im Spike-Report; Harness hat sie verdrahtet + einen Pre/Post-Restart-Pass gefahren (Keys vorhanden), Werte/Verdikte stehen aus.
- **ACM-Schreibpfad-Beleg** (`set_auths.py`-Zeilen) — nicht Teil von D0.

## Konkrete Codex-Aufgaben zur Behebung

### Aufgabe 1 (hoch — Seed-Evidence)
```text
Implementiere ausschließlich die folgende Aufgabe.

Aufgabe:
Erweitere die Tessera-Spike-Evidence um ein explizites, deterministisches Seed-Inventar der Dev-Instanz ha-tessera-dev.

Betroffene Dateien/Module:
- externes D0-/Seed-Skript
- Seed-Evidence (Anhang zur D0-Evidence-JSON oder im Spike-Report)

Regeln:
- Keine Architekturänderungen, keine neuen Features außerhalb der Seed-Evidence.
- Nur ha-tessera-dev; /Volumes/config read-only.
- Keine Secrets/Tokenwerte; nur entity_id/domain/Klassen/Flags.

Erwartete Umsetzung:
- Logge je Domain >=1 erlaubte + 1 verbotene Entity, >=1 state-only Entity ohne Registry-Eintrag, hidden vs disabled getrennt, >=1 entity-component-Service + 1 non-entity-Service + den bewusst unsicheren Dev-only Custom-Service.
- Als Liste in der Evidence.

Tests/Linter:
- Re-Read der Registry bestätigt das Seed-Inventar; Assertion: jede geforderte Klasse >=1 vorhanden.

Definition of Done:
- Seed-Inventar in der Evidence sichtbar
- Assertion grün
- keine Scope-Ausweitung
- offene Risiken benannt

Nach Abschluss berichten: geänderte Dateien, Zusammenfassung, ausgeführte Checks+Ergebnis, offene Annahmen.
```

### Aufgabe 2 (mittel — Restore real ausführen)
```text
Implementiere ausschließlich die folgende Aufgabe.

Aufgabe:
Führe in D4/D5 den Restore-to-native real aus und evidenziere ihn (statt nur das Primitive zu verdrahten).

Betroffene Dateien/Module:
- tessera_spike-Harness (snapshot/restore-Services)
- Spike-Report/Evidence

Regeln:
- Keine Architekturänderungen; nur ha-tessera-dev; keine Secrets.
- Bestehende 8 Services beibehalten.

Erwartete Umsetzung:
- D4: User 2 Rollen -> group_ids volle Union prüfen -> 1 Rolle entfernen -> andere überlebt -> restore aus Snapshot -> Re-Read beweist Ausgangszustand.
- D5: Store-/Setup-Exception simulieren -> Boot-Rescue/Restore greift -> Mitgliedschaften via public async_update_user zurück -> Re-Read beweist System-Zustand.
- Evidence: Counts/Flags vor/nach, keine Werte.

Tests/Linter:
- Re-Read-Assertions vor/nach Restore.

Definition of Done:
- D4+D5 mit ausgeführtem Restore belegt (nicht nur verdrahtet)
- Re-Read-Assertions grün
- keine Scope-Ausweitung
- Risiken benannt

Nach Abschluss berichten: geänderte Dateien, Zusammenfassung, Checks+Ergebnis, offene Annahmen.
```

---
**Gate-Fazit:** D0-GREEN steht — D1–D9 dürfen **starten** (Isolation/Baseline/Onboarding/Harness/Recreate sind bewiesen). Die zwei Auflagen (Seed-Inventar, ausgeführter Restore) sind **bis zum Spike-Report** zu schließen, sonst sind die abhängigen Dimensionen nicht abnahmefähig. Nächstes Gate: der D1–D9-Spike-Report.
