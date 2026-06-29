# Tessera D0 Evidence

Stand: 2026-06-29T13:45:50
Modus: ha-tessera-dev only; no /Volumes/config scan in the standard run; no token/password/auth-code values emitted.

Overall D0: **PASS**

## Gate Evidence

- Target isolation: `True`
- Fresh baseline: `True`
- Onboarding user status: `200`
- Token exchange status: `200` (values redacted)
- Harness installed/loaded: `True`
- Harness services: `['boot_rescue_status', 'ensure_group', 'flush_auth_store', 'invalidate_user', 'prepare_boot_rescue', 'probe_check_entity', 'probe_d2_three_way', 'probe_system_users_gate', 'restore', 'run_spike', 'set_group_policy', 'set_user_groups', 'snapshot']`
- Blocking-I/O matches: `0`
- Exit code: `0`
- Recreate proof: Docker container and volume were recreated after target-isolation check.

## Gate Results

```json
[
  {
    "gate": "target_isolation",
    "status": "PASS"
  },
  {
    "gate": "fresh_baseline",
    "status": "PASS"
  },
  {
    "detail": "measured HTTP/token evidence redaction, not hardcoded",
    "gate": "failure_redaction",
    "measurement": {
      "auth_code_value_not_stored": true,
      "bearer_like_values": 0,
      "checked": true,
      "clean": true,
      "jwt_like_values": 0,
      "token_body_values_not_stored": true,
      "token_exchange_values_redacted": true
    },
    "status": "PASS"
  },
  {
    "gate": "a1_8_services",
    "registered_services": [
      "boot_rescue_status",
      "ensure_group",
      "flush_auth_store",
      "invalidate_user",
      "prepare_boot_rescue",
      "probe_check_entity",
      "probe_d2_three_way",
      "probe_system_users_gate",
      "restore",
      "run_spike",
      "set_group_policy",
      "set_user_groups",
      "snapshot"
    ],
    "status": "PASS"
  },
  {
    "gate": "a1_no_blocking_io_warning",
    "match_count": 0,
    "status": "PASS"
  },
  {
    "entities": 6,
    "gate": "a2_seed_fixture",
    "status": "PASS"
  }
]
```

Full sanitized JSON: `evidence/tessera-d0-evidence-2026-06-29.json`
