# Tessera Phase-0 Spike Report

Stand: 2026-06-29T12:50:45

Modus: Dev-only gegen `ha-tessera-dev`; keine Secrets/Token/Auth-Codes ausgegeben. Live-/`/Volumes/config`-Scans sind im Standardlauf bewusst deaktiviert und brauchen ein eigenes Gate.

## Gesamturteil

**PARTIAL / kein Enforce-Go.**

D0 ist gruen genug, um den dev-only Messlauf zu starten. D1, D2, D4, A2, A3 und B3 liefern positive Signale fuer den Auth-Store-Schreibpfad. D5 bleibt bewusst **PARTIAL**, weil kein echter `/config/.storage/auth`-Korruptions-/No-Admin-Lockout-Rescue bewiesen ist. D12 bleibt **BLOCKED**. D3/D6/D7/D8/D9 bleiben bewusst **PARTIAL**, weil WS, echte LLAT-Rotation, vollstaendige Leak-Matrix, Custom-Component-Runtime und Live/CM5-Gates in diesem Lauf nicht vollstaendig abgedeckt sind.

## DoD Matrix

| DoD | Verdict | Kurzbegruendung |
|---|---:|---|
| D0 | PASS | Preflight/onboarding/seed/harness gate |
| D1 | PASS | tessera group/policy/user restart survival |
| D2 | PASS | policy mutation checked before invalidate, after invalidate, and after restart |
| D3 | PARTIAL | internal + REST + service tested; WS not tested in this run |
| D4 | PASS | caller restores by supplying the full group set; HA group_ids writes are replace semantics |
| D5 | PARTIAL | real /config/.storage/auth corruption rescue is not proven in this run; no false PASS |
| D6 | PARTIAL | entity service allowed/forbidden and entity_id:all probed; response/non-entity matrix incomplete |
| D7 | PARTIAL | render_template probed; logbook/registry/history/WS leak matrix incomplete |
| D8 | PARTIAL | headless normal token probe and revocation; real LLAT rotation not performed |
| D9 | PARTIAL | live /Volumes/config scan skipped in standard dev run; runtime classification not complete |
| B3 | PASS | managed Tessera users are not members of HA system-users allow-all group |
| A2 | PASS | native async_update_user(group_ids) is REPLACE; caller full-superset contract proven |
| A3 | PASS | rescue restore rejects non-tessera group ids such as system-users |
| A4 | BLOCKED | D12 remains blocked/partial until op login and a real product claim hook exist |
| A5 | PASS | failure-redaction gate is measured; stale report marked obsolete |

## D0

- Harte Docker-Isolation: `True`
- Fresh-Baseline-Allowlist: `True`
- Onboarding abgeschlossen: `True`
- Exit-Code: `0`
- Harness-Service geladen: `True`
- 8-Service-Load-Check: `True`; registriert `['boot_rescue_status', 'ensure_group', 'flush_auth_store', 'invalidate_user', 'prepare_boot_rescue', 'probe_check_entity', 'probe_d2_three_way', 'probe_system_users_gate', 'restore', 'run_spike', 'set_group_policy', 'set_user_groups', 'snapshot']`
- Blocking-I/O-Warnungen aus `tessera_spike`: `0`
- Token-/Passwortwerte: nicht im Report enthalten.

Gate-Results:

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

## Seed-Fixture

```json
{
  "areas": [
    {
      "area_id": "tessera_living",
      "name": "Tessera Living"
    },
    {
      "area_id": "tessera_kitchen",
      "name": "Tessera Kitchen"
    }
  ],
  "complete_for_welle_a": true,
  "device": {
    "area_id": "tessera_living",
    "config_entry_id_present": true,
    "device_id": "90c197f4fd7c9a9ae31cafd37a8dee49"
  },
  "entities": [
    {
      "area_id": null,
      "class": "device_area_allowed_light",
      "device_id": "90c197f4fd7c9a9ae31cafd37a8dee49",
      "disabled_by": null,
      "domain": "light",
      "entity_id": "light.tessera_seed_allowed_light",
      "hidden_by": null
    },
    {
      "area_id": "tessera_kitchen",
      "class": "direct_area_forbidden_sensor",
      "device_id": null,
      "disabled_by": null,
      "domain": "sensor",
      "entity_id": "sensor.tessera_seed_forbidden_sensor",
      "hidden_by": null
    },
    {
      "area_id": null,
      "class": "device_area_allowed_cover",
      "device_id": "90c197f4fd7c9a9ae31cafd37a8dee49",
      "disabled_by": null,
      "domain": "cover",
      "entity_id": "cover.tessera_seed_allowed_cover",
      "hidden_by": null
    },
    {
      "area_id": "tessera_kitchen",
      "class": "hidden_direct_area_camera",
      "device_id": null,
      "disabled_by": null,
      "domain": "camera",
      "entity_id": "camera.tessera_seed_hidden_camera",
      "hidden_by": "user"
    },
    {
      "area_id": "tessera_living",
      "class": "disabled_direct_area_lock",
      "device_id": null,
      "disabled_by": "user",
      "domain": "lock",
      "entity_id": "lock.tessera_seed_disabled_lock",
      "hidden_by": null
    },
    {
      "area_id": null,
      "class": "state_only_without_registry",
      "device_id": null,
      "disabled_by": null,
      "domain": "sensor",
      "entity_id": "sensor.tessera_state_only",
      "hidden_by": null
    }
  ],
  "fixture_version": 2,
  "non_entity_services": [
    {
      "class": "intentionally_non_entity_dev_service",
      "service": "tessera_spike.snapshot",
      "values_redacted": true
    }
  ]
}
```

## D1-D5 Auth-Store / Recovery Kern

```json
{
  "a2_native_write_replace_contract": {
    "after_subset_write": [
      "tessera:test"
    ],
    "after_superset_write": [
      "tessera:extra",
      "tessera:test"
    ],
    "api": "hass.auth.async_update_user(group_ids=...)",
    "before_groups": [
      "tessera:test",
      "tessera:extra"
    ],
    "caller_passes_full_superset": true,
    "claim_correction": "group_ids is REPLACE; no-lockout depends on caller supplying the complete intended group set",
    "native_write_is_replace": true,
    "safe_full_superset": [
      "tessera:extra",
      "tessera:test"
    ],
    "subset_write": [
      "tessera:test"
    ]
  },
  "a3_rescue_namespace_guard": {
    "malicious_group_ids_rejected": [
      "system-users"
    ],
    "rescue_restore_namespace_guarded": true,
    "would_restore_system_users": false
  },
  "b3_system_users_gate_pre_restart": {
    "enforce_managed_users": [
      {
        "credentials_count": 0,
        "groups": [
          "tessera:d2"
        ],
        "is_active": true,
        "is_admin": false,
        "is_owner": false,
        "name": "tessera-d2-user",
        "refresh_token_classes": [],
        "refresh_token_count": 0,
        "system_generated": false
      },
      {
        "credentials_count": 0,
        "groups": [
          "tessera:extra",
          "tessera:test"
        ],
        "is_active": true,
        "is_admin": false,
        "is_owner": false,
        "name": "tessera-replace-user",
        "refresh_token_classes": [],
        "refresh_token_count": 0,
        "system_generated": false
      },
      {
        "credentials_count": 0,
        "groups": [
          "tessera:extra"
        ],
        "is_active": true,
        "is_admin": false,
        "is_owner": false,
        "name": "tessera-rescue-user",
        "refresh_token_classes": [],
        "refresh_token_count": 0,
        "system_generated": false
      },
      {
        "credentials_count": 0,
        "groups": [
          "tessera:test"
        ],
        "is_active": true,
        "is_admin": false,
        "is_owner": false,
        "name": "tessera-test-user",
        "refresh_token_classes": [],
        "refresh_token_count": 0,
        "system_generated": false
      }
    ],
    "excluded_system_fixture_users": [
      "tessera-test-admin",
      "tessera-test-ro"
    ],
    "expected_managed_users": [
      "tessera-d2-user",
      "tessera-replace-user",
      "tessera-rescue-user",
      "tessera-test-user"
    ],
    "expected_managed_users_present": true,
    "missing_expected_managed_users": [],
    "offenders": [],
    "ok": true,
    "system_generated_users_ignored": 1,
    "system_users_group_id": "system-users"
  },
  "d1_pre_restart": {
    "group_created": true,
    "policy_written": true
  },
  "d2_policy_change_no_restart": {
    "allowed_read_after_policy_change": false,
    "forbidden_control_after_policy_change": true,
    "forbidden_read_after_policy_change": true
  },
  "d2_three_way": {
    "after_explicit_invalidate": {
      "allowed_read": false,
      "forbidden_control": true,
      "forbidden_read": true
    },
    "after_policy_mutation_without_invalidate": {
      "allowed_read": true,
      "forbidden_control": false,
      "forbidden_read": false
    },
    "before_mutation": {
      "allowed_read": true,
      "forbidden_control": false,
      "forbidden_read": false
    },
    "expected": {
      "after_invalidate_allows_forbidden_entity": true,
      "without_invalidate_keeps_old_cache": true
    },
    "group_id": "tessera:d2",
    "persisted_for_restart_check": true,
    "user": {
      "credentials_count": 0,
      "groups": [
        "tessera:d2"
      ],
      "is_active": true,
      "is_admin": false,
      "is_owner": false,
      "name": "tessera-d2-user",
      "refresh_token_classes": [],
      "refresh_token_count": 0,
      "system_generated": false
    }
  },
  "d3_internal_check_entity": {
    "allowed_control": true,
    "allowed_read": true,
    "forbidden_control": false,
    "forbidden_read": false
  },
  "d4_union_restore": {
    "original_groups": [
      "tessera:test"
    ],
    "restored_groups": [
      "tessera:test"
    ],
    "union_groups": [
      "tessera:test",
      "tessera:extra"
    ]
  },
  "d5_boot_rescue_prepare": {
    "auth_store_corrupted": false,
    "auth_store_path": "/config/.storage/auth",
    "boot_rescue_corruption_tested": false,
    "corrupt_tessera_store_path": "/config/.storage/tessera.config",
    "drifted_groups_before_restart": [
      "tessera:extra"
    ],
    "expected_groups": [
      "tessera:test"
    ],
    "no_admin_lockout": null,
    "partial_reason": "real /config/.storage/auth corruption is not attempted in this run; D5 must not be reported as PASS",
    "prepared": true,
    "snapshot_path": "/config/tessera_spike_rescue_snapshot.json",
    "trigger_path": "/config/tessera_spike_rescue_trigger.json",
    "user_name": "tessera-rescue-user",
    "verdict": "PARTIAL"
  },
  "d5_restore_primitive": {
    "boot_rescue_corruption_tested": false,
    "native_write_is_replace": true,
    "public_async_update_user_restore_available": true,
    "safe_restore_requires_full_group_set": true
  }
}
```

Restart-Survival:

```json
{
  "b3_system_users_gate_post_restart": {
    "enforce_managed_users": [
      {
        "credentials_count": 0,
        "groups": [
          "tessera:d2"
        ],
        "is_active": true,
        "is_admin": false,
        "is_owner": false,
        "name": "tessera-d2-user",
        "refresh_token_classes": [],
        "refresh_token_count": 0,
        "system_generated": false
      },
      {
        "credentials_count": 0,
        "groups": [
          "tessera:extra",
          "tessera:test"
        ],
        "is_active": true,
        "is_admin": false,
        "is_owner": false,
        "name": "tessera-replace-user",
        "refresh_token_classes": [],
        "refresh_token_count": 0,
        "system_generated": false
      },
      {
        "credentials_count": 0,
        "groups": [
          "tessera:test"
        ],
        "is_active": true,
        "is_admin": false,
        "is_owner": false,
        "name": "tessera-rescue-user",
        "refresh_token_classes": [],
        "refresh_token_count": 0,
        "system_generated": false
      },
      {
        "credentials_count": 0,
        "groups": [
          "tessera:test"
        ],
        "is_active": true,
        "is_admin": false,
        "is_owner": false,
        "name": "tessera-test-user",
        "refresh_token_classes": [],
        "refresh_token_count": 0,
        "system_generated": false
      }
    ],
    "excluded_system_fixture_users": [
      "tessera-test-admin",
      "tessera-test-ro"
    ],
    "expected_managed_users": [
      "tessera-d2-user",
      "tessera-replace-user",
      "tessera-rescue-user",
      "tessera-test-user"
    ],
    "expected_managed_users_present": true,
    "missing_expected_managed_users": [],
    "offenders": [],
    "ok": true,
    "system_generated_users_ignored": 1,
    "system_users_group_id": "system-users"
  },
  "d1_restart_survival": {
    "group_survived_restart": true,
    "policy_survived_restart": true,
    "user_survived_restart": true
  },
  "d2_three_way_after_restart": {
    "allowed_read": false,
    "forbidden_control": true,
    "forbidden_read": true,
    "tested": true,
    "user": {
      "credentials_count": 0,
      "groups": [
        "tessera:d2"
      ],
      "is_active": true,
      "is_admin": false,
      "is_owner": false,
      "name": "tessera-d2-user",
      "refresh_token_classes": [],
      "refresh_token_count": 0,
      "system_generated": false
    }
  },
  "d5_boot_rescue_after_restart": {
    "auth_store_corrupted": false,
    "boot_rescue_corruption_tested": false,
    "corrupt_tessera_store_error": "JSONDecodeError",
    "corrupt_tessera_store_parse_failed": true,
    "corrupt_tessera_store_path": "/config/.storage/tessera.config",
    "d5_truthfulness": "PARTIAL: startup restore was exercised against Tessera sidecar corruption, not real /config/.storage/auth corruption",
    "errors": [],
    "no_admin_lockout": null,
    "ok": true,
    "requested": true,
    "rescue_restore_namespace_guarded": true,
    "restored_users": [
      {
        "actual_group_ids": [
          "tessera:test"
        ],
        "exact_match": true,
        "expected_group_ids": [
          "tessera:test"
        ],
        "name": "tessera-rescue-user"
      }
    ],
    "snapshot_present": true,
    "used_public_async_update_user": true
  }
}
```

## D3/D6/D7/D8 Runtime Probes

```json
{
  "d3_rest_ws_service": {
    "allowed_in_state_list": true,
    "allowed_single_status": 200,
    "forbidden_in_state_list": false,
    "forbidden_single_status": 401,
    "service_allowed_status": 200,
    "service_forbidden_status": 401,
    "state_list_status": 200,
    "tested": true,
    "ws_tested": false
  },
  "d6_service_matrix": {
    "entity_id_all_status": 200,
    "entity_service_allowed_status": 200,
    "entity_service_forbidden_status": 401,
    "non_entity_service_tested": false,
    "return_response_changed_states_tested": false,
    "tested": true
  },
  "d7_leak_matrix": {
    "history_tested": false,
    "logbook_rest_tested": false,
    "registry_ws_tested": false,
    "render_template_body_type": "dict",
    "render_template_status": 401,
    "tested": true
  },
  "d8_headless_token": {
    "llat_created": false,
    "normal_headless_access_token_probe": true,
    "refresh_token_revoked_after_probe": true,
    "tested": true
  }
}
```

## D9 Static Custom-Component Scan

```json
{
  "available": false,
  "components_count": null,
  "http_or_ws_candidates": [],
  "reason": "standard dev spike does not touch /Volumes/config; live static scans require an explicit separate review gate",
  "services_yaml_components": [],
  "skipped": true
}
```

## Core-Anker

- HA `auth_store.py`: private `_groups`, `_data_to_save()`, `_store.async_save()` sind der gemessene Schreibpfad.
- HA `auth/models.py`: `User.permissions` ist cached; `invalidate_cache()` ist fuer reine Policy-Mutation relevant.
- HA `auth/__init__.py`: `async_update_user(group_ids=...)` ist der oeffentliche Restore-/Binding-Pfad.
- HA `http/auth.py`: `Home Assistant Content` ist `system_generated` und bleibt unmanaged.

## Go/No-Go

- **Go fuer weitere Phase-0-Haertung:** ja.
- **Go fuer Tessera-Enforce/Product:** nein.
- **Naechste Pflicht:** WS-Testmatrix, echter LLAT-Lifecycle, Boot-Rescue mit absichtlich korruptem Tessera-Store, non-entity/custom service classification runtime, unsupported-version gate, D10/CM5-Benchmark und D12/OIDC gesondert.

## Artefakte

- D0 Evidence: `evidence/tessera-d0-evidence-2026-06-29.md`
- D0 JSON: `evidence/tessera-d0-evidence-2026-06-29.json`
- Spike JSON: `evidence/tessera-spike-result-2026-06-29.json`
