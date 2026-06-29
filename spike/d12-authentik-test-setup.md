# D12 — Test-Authentik für den OIDC-`groups`-Claim-Beweis
Stand 2026-06-29 · Status: **v1-kritisch** (OIDC ist v1-Pflicht, ADR 0002) · Blockt v1-Enforce von `by_group`

## Ziel
Beweisen, dass **Tessera den rohen `groups`-Claim aus Authentik lesen** und auf eine **Tessera-Rolle mappen** kann (parallel zu `auth_oidc`). Ohne diesen Beweis ist `by_group` nicht v1-fähig.

## Rollen
- **Michael:** Authentik konfigurieren (Web-UI `auth.pilzbuche8.de` → Admin) + **client_secret → 1Password** (nie in Repo/Chat).
- **Codex:** `ha-tessera-dev` an Authentik anbinden + D12-Probe fahren + Evidence (secretfrei).
- **Claude:** D12-Gate.

## Teil 1 — Authentik (Michael, Web-UI)
Spiegelt euer bestehendes **Grafana-SSO-Groups-Mapping**.

1. **Test-Gruppen** (Directory → Groups): `tessera-test-admin`, `tessera-test-eg`, `tessera-test-readonly` (die Namen erscheinen 1:1 im `groups`-Claim).
2. **Test-User** (Directory → Users): 1–2 Wegwerf-Test-User, jeweils Mitglied in je einer/mehreren Test-Gruppen. (Kein echtes Konto.)
3. **`groups`-Scope-Mapping** (Customization → Property Mappings → Scope Mapping) — falls nicht schon von Grafana vorhanden:
   - Scope name: `groups`
   - Expression: `return {"groups": [g.name for g in request.user.ak_groups.all()]}`
   *(Wenn Grafana bereits ein groups-Scope-Mapping nutzt: wiederverwenden, nicht doppeln.)*
4. **OAuth2/OpenID-Provider** (Applications → Providers → Create → OAuth2/OpenID):
   - Name: `Tessera Dev` · Client type: **Confidential**
   - Redirect URI: der von der HA-OIDC-Integration erwartete Callback (Codex nennt den exakten Pfad; bei `auth_oidc` typ. `http://localhost:8124/auth/oidc/callback`)
   - Scopes: `openid`, `profile`, `email`, **`groups`**
   - Client ID notieren · **Client Secret → 1Password Pilzbuche8** als „**Authentik OIDC Tessera Dev (client_secret)**".
5. **Application** (Applications → Applications → Create): Name `Tessera Dev`, Slug `tessera-dev`, Provider = obiger. Test-User/Gruppen zulassen.

→ Danach existiert die Discovery-URL: `https://auth.pilzbuche8.de/application/o/tessera-dev/.well-known/openid-configuration`

## Teil 2 — HA-Dev + Probe (Codex, `ha-tessera-dev`)
1. OIDC-Anbindung auf `ha-tessera-dev` (z. B. `auth_oidc`): Issuer/Discovery wie oben, Client-ID, **client_secret via `op read … | …stdin`** (nie loggen), Scope inkl. `groups`.
2. Login als Test-User (Mitglied `tessera-test-eg`) via OIDC.
3. **D12-Kernfrage beweisen:** Liest Tessera den `groups`-Claim **at/after login** (welcher Pfad — Token, userinfo, `auth_oidc`-Hook, gespeicherte Claims)? → sieht `["tessera-test-eg", …]` → mappt auf Tessera-Rolle.

## Evidence / DoD (D12)
- `groups`-Claim **lesbar** + Bezugspfad dokumentiert (`PASS`) ODER sauber begründet warum nicht (`PARTIAL/FAIL` → `by_group` v1-Risiko).
- Mapping **Gruppe → Rolle** funktioniert.
- **Keine Tokenwerte/Secrets/`client_secret`** in Logs/Evidence/Chat — Failure-Pfade redacten.
- Verdikt PASS/PARTIAL/FAIL + Bezug HA-Core/`auth_oidc`-`file:line`.

## Secrets (hart)
`client_secret` nur 1Password (`op`-stdin). OIDC-Access-/Refresh-/ID-Token-Werte nie loggen. Nur Dev-Instanz, nie Live-CM5.
