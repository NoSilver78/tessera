## What & why
<!-- Summary of the change and the motivation. Link the related issue if any. -->

## Checklist
- [ ] `pytest` green (with `pytest-asyncio` + `pytest-homeassistant-custom-component` installed)
- [ ] `ruff check .` and `black --check .` clean
- [ ] `mypy custom_components/tessera` clean
- [ ] No secrets/tokens in code, tests, or logs
- [ ] Auth-touching changes were tested against a **dev** instance only — never a live HA
- [ ] Tests cover happy path + relevant error/edge cases (existing tests not weakened)
- [ ] Docs updated if behavior or the security posture changed (README / SECURITY / CHANGELOG)

## Security impact
<!-- Does this change who can see/do what, or touch the auth-store write path?
     If yes, describe the lockout/allow-only/owner-safety reasoning. -->
