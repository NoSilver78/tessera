# D10 — CM5 `.storage/auth` Scale-Benchmark (2026-06-30)

**Verdikt: PASS.** Letztes offenes Rubrik-Item (Michael-Paket) — read-only, secret-safe charakterisiert.

## Methode (secret-safe)
Read-only-Skript gegen `/Volumes/config/.storage/auth` (37,7 KB). Ausgabe = **nur** Struktur-Zähler / Größen / Kategorie-Namen — **keine** Namen, IDs, Hashes, Token-Werte oder Policy-Werte. Die Token-Felder `token`/`jwt_key` wurden nur als *Schema-Feldname* zur Verifikation gelesen, nie ihr Inhalt. (Skript im Scratchpad, bewusst nicht committet, da es den Secret-Pfad liest.)

## Metriken (secret-frei)
```json
{
  "file_size_bytes": 37698,
  "storage_version": 1,
  "users": {"total": 7, "system_generated": 2, "owner": 1, "active": 7, "managed_candidates": 4},
  "group_membership": {
    "group_ids_per_user_min": 1, "group_ids_per_user_max": 1,
    "in_system_admin": 3, "in_system_users": 3, "in_system_read_only": 1,
    "managed_in_system_users": 3, "managed_in_system_admin": 1
  },
  "groups": {"total": 3, "system": 3, "custom": 0, "policy_kinds": {"none": 3}},
  "refresh_tokens": {
    "total": 38, "by_type": {"normal": 32, "long_lived_access_token": 4, "system": 2},
    "llat_by_owner_category": {"owner": 3, "admin": 1}
  },
  "credentials": {"total": 6, "by_provider": {"homeassistant": 4, "auth_oidc": 2}}
}
```

## Analyse → Enforce-Relevanz
- **Scale trivial:** 7 User (2 system_generated, 1 owner), **4 managed candidates** — davon **3 reguläre** (in `system-users` = allow-all) + 1 Admin. Enforce-Schreibsequenz = N `tessera:<role>`-Gruppen anlegen + **3 reguläre User rebinden**. Ziel „<1 s / N Policies + ~7 Rebinds" **komfortabel erfüllt**.
- **`group_ids` pro User = 1** (jeder in genau einer Gruppe) → REPLACE-Superset-Write ist einfach (`[system-users]` → `[tessera:role…]`).
- **3 managed User in `system-users`** = die exakten Targets, die raus müssen (§6.3-CRITICAL: system-users force-injiziert allow-all) — real bestätigt.
- **0 Custom-Gruppen, 3 System-Gruppen** (policy in Storage `none` — HA injiziert zur Laufzeit) → Tessera legt die `tessera:role`-Gruppen **frisch** an (privater `_store._groups`-Write-Pfad, E1-Adapter).
- **No-Lockout solide:** 1 Owner (Bypass) + 3 `system-admin`-Mitglieder → reichlich Recovery-Pfade.
- **LLAT-Audit (Konzept-Checkliste „4 LLATs — god-tokens?"): ENTWARNT.** 4 LLATs → **3 owner + 1 admin, 0 managed-non-admin.** Kein Non-Admin-LLAT → **kein headless-Bypass** eines confined Users über erzwungene Pfade. Die Sorge ist in dieser Installation gegenstandslos.
- **OIDC live:** 2 `auth_oidc`-Credentials (Authentik) → der `by_group`-Pfad hat 2 reale User, bleibt aber **v1-inert** (ADR 0005).

## Pre-Enforce-Notiz (klein, nicht blockierend)
- **`device_ids`/`except`-Schwelle** (D10-Ursprungszweck, `spec-phase1-core.md:33`): hängt an der **Policy-Größe pro Rolle** (entity_ids-Dicts über ~2661 Entities), nicht an der User-Zahl. Erst messbar, sobald Rollen definiert sind → bei E3 die kompilierte Policy-Größe je Rolle prüfen (bounded, unkritisch bei dieser Scale).

## Rubrik-Stand
Mit **D10-PASS** ist die **v1-Enforce-Rubrik vollständig grün** (D1–D15 + D10). **E3 bleibt dennoch gated:** Build in panel-gegateten Schritten (nach E2.5) + **Human-Go + Soak** — D10-PASS hebt nur die letzte *Rubrik*-Voraussetzung, nicht die Scharf-Schalt-Disziplin.
