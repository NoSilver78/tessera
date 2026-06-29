# D12 — Authentik bereit (für Codex)
Stand 2026-06-29 · Michael hat die Test-Authentik via Skript angelegt → Codex kann jetzt HA-Dev-Anbindung + D12-Probe machen.

## In Authentik angelegt (`auth.pilzbuche8.de`)
- Gruppen: `tessera-test-admin` · `tessera-test-eg` · `tessera-test-readonly`
- Test-User: `tessera-test-user` (Mitglied `tessera-test-eg` + `tessera-test-readonly`)
- OIDC-Provider + App **„Tessera Dev"** (slug `tessera-dev`), mit `groups`-Scope.

## Werte für die Anbindung
- **client_id** (öffentlich): `URFhXiLiMYgijIyhQlBVKIh6F4ZaYQHJmSpmsuTh`
- **Discovery:** `https://auth.pilzbuche8.de/application/o/tessera-dev/.well-known/openid-configuration`
- **client_secret:** 1Password `Pilzbuche8` → „**Authentik OIDC Tessera Dev (client_secret)**" (via `op`, **nie loggen**)
- **Test-User-Passwort:** 1Password `Pilzbuche8` → „**Authentik Tessera Test User**"
- **Redirect (in Authentik gesetzt):** `http://localhost:8124/auth/oidc/callback` — exakten `auth_oidc`-Callback bestätigen/ggf. anpassen.

## Aufgabe — D12-Probe auf `ha-tessera-dev`
1. OIDC-Anbindung (`auth_oidc` o. ä.) mit obigen Werten konfigurieren; `client_secret` via `op`.
2. Login als `tessera-test-user` via OIDC.
3. **Beweisen:** liest Tessera den `groups`-Claim **at/after login** (welcher Pfad — Token/userinfo/`auth_oidc`-Hook) → sieht `["tessera-test-eg", …]` → Mapping Gruppe → Rolle.
4. Evidence (secretfrei, PASS/PARTIAL/FAIL, Core-/`auth_oidc`-`file:line`) → PR/Report.

**Hinweis:** `auth.pilzbuche8.de` liegt hinter Cloudflare (blockt Nicht-Browser-User-Agents mit `error 1010`) — entweder Browser-UA-Header setzen **oder** Authentik intern im LAN ansprechen.
