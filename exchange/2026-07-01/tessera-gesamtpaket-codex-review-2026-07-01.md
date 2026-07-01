# Tessera Gesamtpaket Review - Codex - 2026-07-01

Status: REVIEW / AUFLAGEN
Quelle: `exchange/2026-07-01/00_tessera-gesamtpaket-codex-2026-07-01.md`, `spike/reports/tessera-multitenant-isolation-feasibility-2026-07-01.md`
Scope: read-only Review der neuen Gating-Logik nach Tessera-Vertrag. Keine Code-Aenderungen, kein Live-/Config-Write.
Secret-Status: keine Secrets gelesen oder berichtet.

## Kurzverdikt

Das neue NO-GO fuer echte Mandantentrennung auf einer einzelnen HA-Instanz ist mit Tesseras eigener Sicherheits- und Scope-Dokumentation konsistent. Es passt zu `SECURITY.md`, `docs/spec-enforce.md` und `docs/concept.md`: Tessera ist Household-/Intra-Instanz-RBAC, keine harte Confidentiality-Grenze fuer untrusted Tenants.

Aber: Das Gesamtpaket darf in der aktuellen Form noch nicht als widerspruchsfreie Gate-Quelle verwendet werden. Es enthaelt stale/konfliktierende Owner-Gate-Formulierungen und markiert T2 etwas zu breit als READY.

## Findings

### 1. Gesamtpaket hat widerspruechliches Owner-/Gate-Wording

Verdikt: AUFLAGEN

Evidenz:

- `00_tessera-gesamtpaket-codex-2026-07-01.md:5` sagt, der uebergeordnete Gate sei entschieden, Scope sei geklaert, aber die Owner-Entscheidung zur Architektur stehe noch aus.
- `00_tessera-gesamtpaket-codex-2026-07-01.md:13` sagt zugleich, der Isolationsgrad sei als Haushalt geklaert und der urspruengliche echte Mehrparteienfall sei revidiert.
- `00_tessera-gesamtpaket-codex-2026-07-01.md:25` nennt die Isolations-Machbarkeit noch `pending`.
- `00_tessera-gesamtpaket-codex-2026-07-01.md:50` sagt erneut, die Owner-Entscheidung zur Architektur sei ausstehend.

Risiko:

Ein Codex- oder Claude-Folgeschritt koennte aus derselben Datei zwei unterschiedliche Steuerbefehle ableiten: entweder `Haushalt geklaert, T1/T2 starten` oder `Architekturentscheidung offen, 3b/3c nicht bauen`. Das ist bei einem Sicherheits-Gate zu viel Ambiguitaet.

Empfehlung:

Das Paket vor Verwendung als SoT korrigieren: entweder `Owner hat Haushalt/Ein-Instanz akzeptiert` oder `Owner-Go noch offen`. Die Artefakt-Tabelle muss `Isolations-Machbarkeit` von `pending` auf `entschieden/report liegt vor` setzen, falls das Gate wirklich entschieden ist.

### 2. T2 ist isolation-unblocked, aber nicht vollstaendig spec-final

Verdikt: AUFLAGEN

Evidenz:

- `00_tessera-gesamtpaket-codex-2026-07-01.md:39` markiert T2 als READY/ungated und beschreibt Preflight-DTO mit PASS/BLOCK-Feldern.
- `00_tessera-gesamtpaket-codex-2026-07-01.md:53` haelt gleichzeitig die Doku-Code-Divergenz offen: User ohne wirksame Rolle, Code default role vs. Konzept enforce-refusal.
- `docs/concept.md:443` fordert fuer bestimmte Faelle enforce refusal bei User ohne wirksame Rolle bzw. nur `by_group` ohne Provider.
- `custom_components/tessera/mode_manager.py:400` ff. bildet Bindings aktuell aus `membership.by_user`; ohne gueltige Rolle landet der User bei der Default-Rolle.
- `tests/test_mode_manager.py:840` ff. pinnt das Default-Rollen-Verhalten.

Risiko:

Ein Preflight-DTO kann nicht final behaupten, welche User PASS/BLOCK sind, solange die grundlegende Semantik fuer `keine wirksame Rolle` offen ist. Das ist besonders relevant fuer Authentik/`by_group`, weil missing/empty Claims sonst wie Default-Deny oder wie Block behandelt werden koennen.

Empfehlung:

T2 darf als von der Tenant-Isolation entkoppelt gelten, aber sein PASS/BLOCK-Vertrag bleibt `MODIFY`, bis die Default-Rolle-vs-enforce-refusal-Entscheidung getroffen und in Code, Tests und Konzept vereinheitlicht ist.

### 3. NO-GO fuer echte Single-Instance-Tenant-Isolation ist konsistent

Verdikt: BESTAETIGT

Evidenz:

- `spike/reports/tessera-multitenant-isolation-feasibility-2026-07-01.md:5-11` kommt zum NO-GO fuer echte Isolation auf einer HA-Instanz.
- `SECURITY.md:38-40` dokumentiert Leak-Pfade und sagt, Tessera sei keine vollstaendige Daten-Isolation.
- `docs/spec-enforce.md:10` sagt, `operate/control` sei die Grenze; `view` leakt und ist keine Confidentiality-Boundary.
- `docs/spec-enforce.md:31-32` listet hard-view-isolation / 2 Instanzen + `remote_homeassistant` als out-of-scope/post-v1.
- `docs/concept.md:58` setzt harte view-Vertraulichkeit fuer untrusted Subjekte explizit in Tier-2 ausserhalb dieses Produkts.
- `docs/concept.md:600` formuliert das Produktversprechen als getestete Pfade plus dokumentierte Rest-Leaks, nicht als harte Tenant-Vertraulichkeit.

Einschraenkung:

Der neue Machbarkeitsreport belegt HA-Line-Anker gegen 2025.1.4, waehrend Tessera aktuell 2026.6.4 als getestete Version nennt (`SECURITY.md:72-76`). Das entwertet die Architekturfolgerung nicht, weil Tesseras eigene Doku dieselbe Scope-Grenze bereits traegt. Es bedeutet aber: Die konkreten HA-Datei-/Zeilenanker sind konservative Architektur-Evidenz, nicht exakte 2026.6.4-Line-Proofs.

Empfehlung:

NO-GO als Scope-Entscheidung akzeptieren: Tessera nicht als Mandantentrennung vermarkten. Fuer echte fremde Parteien: getrennte HA-Instanzen / Prozessgrenze. Fuer Haushalt/Intra-Instanz: Tessera weiterbauen, aber die bekannten View-Leaks prominent in README/SECURITY/UI halten.

## Backlog-Auswirkung

- T1 `by_user`-Membership-Writer: weiterhin sinnvoller erster PR-Scope, mit den bestehenden Sicherheitsauflagen.
- T2 Effective/Preflight: isolation-unblocked, aber nur nach Klaerung der Default-Rolle-vs-refusal-Semantik spec-final.
- T3 Authentik/`by_group`: bleibt strikt gated; keine Aktivierung ohne Claim-Hook, Effective-Union, Linter/Preflight-Union, missing/empty-Claim-Tests und D12.
- T4 Ein-Instanz-Leak-Haertung fuer echte Tenant-Isolation: entfaellt, wenn Owner den Household-/Ein-Instanz-Scope bestaetigt.

## Schluss

Codex bestaetigt die Richtung, aber empfiehlt eine kleine Gate-Cleanup-Runde am Gesamtpaket, bevor es als kanonischer Einstiegspunkt genutzt wird. Wichtigster Fix: Owner-/Isolationsstatus eindeutig machen und T2 als `isolation-unblocked, spec-final nach Default-Rollen-Entscheidung` markieren.
