# Tessera D12 Authentik Probe

Stand: 2026-06-29T11:56:16

Verdict: **BLOCKED**

## Kurzbefund

Die D12-Probe ist als secret-redacted IdP-Probe implementiert, konnte lokal aber nicht mit echten Authentik-Credentials laufen, weil die 1Password-CLI nicht angemeldet war: `op whoami` lieferte `account is not signed in`.

## Bewertung

- Kein Secret wurde gelesen oder geschrieben.
- Es gibt keinen D12-PASS und keinen D12-PARTIAL-Livebeleg in diesem Lauf.
- `by_group` bleibt fuer Enforce nicht freigegeben.
- Nach `op signin` kann der Lauf mit `spike/tools/tessera_spike/d12_authentik_probe.py --allow-partial ...` wiederholt werden.

Sanitized JSON: `spike/evidence/tessera-d12-authentik-evidence-2026-06-29.json`
