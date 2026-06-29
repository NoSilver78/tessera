# ADR 0002 — MVP v1 Scope
Stand 2026-06-29 · Status: **aktiv** · Ziel: schnell zu einem lauffähigen, ehrlichen v1 — Sicherheit nur dort hart, wo sie zählt.

## In v1 (Muss)
- **Rollen** + **dual-mode Mitgliedschaft: `by_user` (lokal) UND `by_group` (Authentik/OIDC)** — **OIDC ist v1-Pflicht** (Michael-Vorgabe).
- **Area × Rolle** (der ~90%-Fall) + **Entity-Override** (Ausnahmen).
- **Stufen view=read · operate=control** — echt durchgesetzt auf nativen HA-Policies.
- **Modi:** `off` / `monitor` / `enforce` + **Scharfschalten nur mit explizitem User-Confirm** in der UI.
- **Sauberes Uninstall / Reversibilität:** native Policies vollständig zurück; bei internem Fehler **fail-safe → `off`** (nie zusperren). Owner nie ausgesperrt; ≥1 Admin-Invariante.
- **Minimal-Admin-UI:** config_flow + Area×Rolle-Matrix + Apply/Rollback (kein Hochglanz-Panel).

## v1-kritischer Pfad (durch OIDC-Pflicht)
- **D12 — OIDC-`groups`-Claim-Seitenkanal** muss **bewiesen** sein (nicht mehr „v1-inert"). Braucht eine **Test-Authentik** (Client + Test-Gruppen gegen `auth.pilzbuche8.de`). → **Michael-Host-Paket**, blockt v1-Enforce.

## Bewusst NICHT in v1 (später)
- Label-/`entity_category`-Bulk-Selektoren · Hochglanz-Lit-Panel · die 15 Community-Features (Per-User-Dashboard-Gen, Gäste/Kids-Rollen, scoped-Token-Helfer …) · granulares per-Entity-`change` · harte untrusted-`view`-Vertraulichkeit (= Tier-2, außerhalb).

## Begründung
`by_user` + `by_group` + Area×Rolle + Monitor→Enforce + sauberes Uninstall ist das **kleinste ehrlich nützliche Produkt**. Der Rest ist additiv und verzögert v1 nur. OIDC bleibt drin, weil es Michaels Kern-Use-Case ist (Authentik-Gruppen → Rollen).
