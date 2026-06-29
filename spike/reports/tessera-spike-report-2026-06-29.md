# Tessera Phase-0 Spike Report

Stand: 2026-06-29T20:34:02

Modus: Dev-only gegen `ha-tessera-dev`; keine Secrets/Token/Auth-Codes ausgegeben. Live-/`/Volumes/config`-Scans sind im Standardlauf bewusst deaktiviert und brauchen ein eigenes Gate.

## Gesamturteil

**PARTIAL / kein Enforce-Go.**

D0 ist gruen genug, um den dev-only Messlauf zu starten. D1, D2, D3, D4, D6, D8, D9, D11, D13, D15, A2, A3 und B3 liefern belastbare Dev-Signale. D5 bewertet das gemessene S1/S1b-Recovery-Gate gegen managed REPLACE-Demotion, Setup-Exception-Unabhaengigkeit, Re-Read und Owner/Admin-Operate-Probe; S2 `/config/.storage/auth`-Korruption bleibt bewusst **observational only** und kein PASS-Hebel. D7 liefert eine ehrliche Leak-Matrix, bleibt aber wegen nicht verifizierbarer Registry-/History-/Logbook-Baselines **PARTIAL**. D12 bleibt **BLOCKED**. Welle D nimmt D9 nur als **fail-closed Klassifikationsmatrix** ab; Welle E nimmt Lifecycle-Gates nur fuer `ha-tessera-dev` ab. Weiter kein Enforce/Product-Go.

## DoD Matrix

| DoD | Verdict | Kurzbegruendung |
|---|---:|---|
| D0 | PASS | Preflight/onboarding/seed/harness gate |
| D1 | PASS | tessera group/policy/user restart survival |
| D2 | PASS | policy mutation checked before invalidate, after invalidate, and after restart |
| D3 | PASS | internal + REST + WS + service entity-targeted consistency measured |
| D4 | PASS | caller restores by supplying the full group set; HA group_ids writes are replace semantics |
| D5 | PASS | managed REPLACE demotion boot-rescue requires measured restore, setup-exception independence, and no-admin-lockout |
| D6 | PASS | service matrix measured; entity-targeted path can pass while non-entity/system gaps stay documented |
| D7 | PARTIAL | full REST+WS leak matrix documented; leaks bound view-scope, not operate/control |
| D8 | PASS | real long-lived token lifecycle measured without storing token values |
| D9 | PASS | custom-component classification matrix exists; UNKNOWN_BLOCK_ENFORCE remains fail-closed for unverified inputs |
| D11 | PASS | unsupported HA version simulation refuses enforce before native auth write |
| D13 | PASS | simulated HACS update/downgrade rollback restores exact native auth fingerprint |
| D15 | PASS | off/monitor no-write, enforce full-superset native write, restore exact fingerprint |
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
    "device_id": "f786dfda04da844dd740fa5cba803a6a"
  },
  "entities": [
    {
      "area_id": null,
      "class": "device_area_allowed_light",
      "device_id": "f786dfda04da844dd740fa5cba803a6a",
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
      "device_id": "f786dfda04da844dd740fa5cba803a6a",
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
    "auth_store_corrupted": true,
    "auth_store_path": "/config/.storage/auth",
    "boot_rescue_corruption_tested": null,
    "corrupt_tessera_store_path": "/config/.storage/tessera.config",
    "drifted_groups_before_restart": [
      "tessera:extra"
    ],
    "expected_groups": [
      "tessera:extra",
      "tessera:test"
    ],
    "no_admin_lockout": null,
    "partial_reason": "D5 requires post-restart rescue, setup-exception independence, reread, and owner/admin operate probes",
    "prepared": true,
    "run_id": "de86cbe765fa4ec2b6f908247c5a6fe5",
    "setup_exception_trigger_path": "/config/tessera_spike_force_setup_exception.json",
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
          "tessera:extra",
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
    "admin_before_after_unchanged": {
      "groups": true,
      "is_active": true,
      "is_admin": true,
      "is_owner": true,
      "name": true
    },
    "admin_operate_probe": {
      "attempted": true,
      "authenticated_and_operated": true,
      "is_admin": true,
      "is_owner": false,
      "status": 200,
      "token_values_redacted": true,
      "user_name": "tessera-test-admin"
    },
    "auth_store_corrupted": true,
    "boot_rescue_corruption_tested": true,
    "corrupt_tessera_store_error": "JSONDecodeError",
    "corrupt_tessera_store_parse_failed": true,
    "corrupt_tessera_store_path": "/config/.storage/tessera.config",
    "d5_truthfulness": "PASS: managed REPLACE demotion was rescued before forced setup exception; reread and owner/admin operate probes passed",
    "errors": [],
    "managed_group_replace_drift_injected": true,
    "no_admin_lockout": true,
    "ok": true,
    "owner_before_after_unchanged": {
      "groups": true,
      "is_active": true,
      "is_admin": true,
      "is_owner": true,
      "name": true
    },
    "owner_operate_probe": {
      "attempted": true,
      "authenticated_and_operated": true,
      "is_admin": true,
      "is_owner": true,
      "status": 200,
      "token_values_redacted": true,
      "user_name": "test-owner"
    },
    "owner_system_unmanaged_never_touched": true,
    "post_boot_measured": true,
    "requested": true,
    "reread_results": [
      {
        "actual_group_ids": [
          "tessera:extra",
          "tessera:test"
        ],
        "exact_match": true,
        "expected_group_ids": [
          "tessera:extra",
          "tessera:test"
        ],
        "name": "tessera-rescue-user"
      }
    ],
    "reread_state_matches_intended": true,
    "rescue_independent_of_healthy_tessera": true,
    "rescue_restore_namespace_guarded": true,
    "restored_users": [
      {
        "actual_group_ids": [
          "tessera:extra",
          "tessera:test"
        ],
        "before_group_ids": [
          "tessera:extra"
        ],
        "exact_match": true,
        "expected_group_ids": [
          "tessera:extra",
          "tessera:test"
        ],
        "name": "tessera-rescue-user"
      }
    ],
    "run_id": "de86cbe765fa4ec2b6f908247c5a6fe5",
    "run_id_matches": true,
    "setup_exception_error_type": "RuntimeError",
    "setup_exception_requested": true,
    "setup_exception_simulated": true,
    "setup_exception_trigger_path": "/config/tessera_spike_force_setup_exception.json",
    "snapshot_present": true,
    "touched_only_snapshot_managed_users": true,
    "touched_user_names": [
      "tessera-rescue-user"
    ],
    "trigger_run_id": "de86cbe765fa4ec2b6f908247c5a6fe5",
    "used_public_async_update_user": true,
    "verdict": "PASS"
  }
}
```

D5 S2 Auth-Store-Korruption, **observational only**:

```json
{
  "auth_store_backup_created": true,
  "auth_store_corruption_injected": true,
  "auth_store_path": "/config/.storage/auth",
  "auth_store_restored_from_backup": true,
  "auth_store_size_before": 5570,
  "backup_path": "/config/.storage/auth.tessera_spike_backup",
  "backup_removed": true,
  "d5_pass_lever": false,
  "ha_boot_after_auth_corruption": true,
  "ha_boot_after_auth_corruption_error": null,
  "ha_boot_after_auth_corruption_status": 401,
  "ha_boot_after_auth_restore": true,
  "ha_boot_after_auth_restore_error": null,
  "ha_boot_after_auth_restore_status": 401,
  "pre_manipulation_target_isolation_errors": [],
  "pre_manipulation_target_isolation_ok": true,
  "s2_observational_only": true,
  "tested": true
}
```

## D3/D6/D7/D8 Runtime Probes

```json
{
  "d3_rest_ws_service": {
    "allowed_in_state_list": true,
    "allowed_single_status": 200,
    "consistent_entity_targeted": true,
    "forbidden_in_state_list": false,
    "forbidden_single_status": 401,
    "service_allowed_status": 200,
    "service_forbidden_status": 401,
    "state_list_status": 200,
    "tested": true,
    "ws": {
      "allowed_in_state_list": true,
      "forbidden_in_state_list": false,
      "get_states_success": true,
      "service_allowed_error": null,
      "service_allowed_success": true,
      "service_forbidden_error": {
        "code": "home_assistant_error",
        "message": "Unauthorized"
      },
      "service_forbidden_success": false,
      "tested": true
    },
    "ws_tested": true
  },
  "d6_service_matrix": {
    "documented_enforce_gaps": [
      "system_context_user_id_none",
      "non_entity_service"
    ],
    "entity_id_all_after": {
      "input_boolean.tessera_allowed_light": "off",
      "input_boolean.tessera_forbidden_light": "on"
    },
    "entity_id_all_before": {
      "input_boolean.tessera_allowed_light": "on",
      "input_boolean.tessera_forbidden_light": "on"
    },
    "entity_id_all_status": 200,
    "entity_service_allowed_status": 200,
    "entity_service_forbidden_status": 401,
    "entity_targeted_pass": true,
    "non_entity_service": {
      "body": {
        "body_type": "dict",
        "keys": [
          "changed_states",
          "service_response"
        ]
      },
      "service": "tessera_spike.snapshot",
      "status": 200,
      "verdict": "ENFORCE_BYPASS"
    },
    "non_entity_service_tested": true,
    "return_response_body": {
      "body_type": "dict",
      "keys": [
        "message"
      ]
    },
    "return_response_changed_states_tested": true,
    "return_response_status": 400,
    "system_context": {
      "after_state": "on",
      "before_state": "off",
      "changed": true,
      "context_user_id": null,
      "entity_id": "input_boolean.tessera_forbidden_light",
      "error": null,
      "not_tested_contexts": [
        "automation",
        "script",
        "assist"
      ],
      "service": "input_boolean.turn_on",
      "tested": true,
      "verdict": "ENFORCE_BYPASS"
    },
    "tested": true,
    "ws_service_allowed_success": true,
    "ws_service_forbidden_success": false,
    "ws_service_response_tested": true
  },
  "d7_leak_matrix": {
    "complete_matrix": false,
    "history_tested": true,
    "leaks": [
      {
        "allowed_entity_seen": true,
        "baseline_present": true,
        "body": {
          "body_type": "list",
          "entity_ids": [
            "binary_sensor.sun_solar_rising",
            "camera.tessera_seed_hidden_camera",
            "cover.tessera_seed_allowed_cover",
            "event.backup_automatic_backup",
            "input_boolean.tessera_allowed_light",
            "input_boolean.tessera_forbidden_light",
            "light.tessera_seed_allowed_light",
            "lock.tessera_seed_disabled_lock",
            "person.test_owner",
            "sensor.backup_backup_manager_state",
            "sensor.backup_last_attempted_automatic_backup",
            "sensor.backup_last_successful_automatic_backup",
            "sensor.backup_next_scheduled_automatic_backup",
            "sensor.sun_next_dawn",
            "sensor.sun_next_dusk",
            "sensor.sun_next_midnight",
            "sensor.sun_next_noon",
            "sensor.sun_next_rising",
            "sensor.sun_next_setting",
            "sensor.sun_solar_azimuth",
            "sensor.sun_solar_elevation",
            "sensor.tessera_seed_forbidden_sensor",
            "todo.shopping_list",
            "tts.google_translate_en_com"
          ],
          "entity_ids_truncated": false,
          "items": 24
        },
        "error": null,
        "forbidden_entity_seen": true,
        "leak_hint": true,
        "status": "ok",
        "transport": "ws",
        "vector": "config/entity_registry/list",
        "verdict": "LEAK"
      },
      {
        "allowed_entity_seen": false,
        "baseline_present": true,
        "body": {
          "body_type": "list",
          "items": 4
        },
        "error": null,
        "forbidden_entity_seen": false,
        "leak_hint": true,
        "status": "ok",
        "transport": "ws",
        "vector": "config/device_registry/list",
        "verdict": "LEAK"
      },
      {
        "allowed_entity_seen": false,
        "baseline_present": true,
        "body": {
          "body_type": "list",
          "items": 5
        },
        "error": null,
        "forbidden_entity_seen": false,
        "leak_hint": true,
        "status": "ok",
        "transport": "ws",
        "vector": "config/area_registry/list",
        "verdict": "LEAK"
      },
      {
        "allowed_entity_seen": false,
        "baseline_present": true,
        "body": {
          "body_type": "list",
          "entity_ids": [
            "input_boolean.tessera_forbidden_light"
          ],
          "entity_ids_truncated": false,
          "items": 1
        },
        "error": null,
        "forbidden_entity_seen": true,
        "leak_hint": true,
        "status": "ok",
        "transport": "ws",
        "vector": "logbook/get_events",
        "verdict": "LEAK"
      },
      {
        "allowed_entity_seen": false,
        "baseline_present": true,
        "body": {
          "body_type": "dict",
          "keys": [
            "event_keys",
            "event_received"
          ]
        },
        "error": null,
        "forbidden_entity_seen": false,
        "leak_hint": true,
        "status": "ok",
        "transport": "ws",
        "vector": "render_template",
        "verdict": "LEAK"
      }
    ],
    "logbook_rest_tested": true,
    "matrix": [
      {
        "allowed_entity_seen": false,
        "baseline_present": true,
        "body": {
          "body_type": "dict",
          "keys": [
            "raw"
          ]
        },
        "error": null,
        "forbidden_entity_seen": false,
        "leak_hint": false,
        "status": 401,
        "transport": "rest",
        "vector": "/api/template",
        "verdict": "BLOCKED"
      },
      {
        "allowed_entity_seen": false,
        "baseline_present": false,
        "body": {
          "body_type": "list",
          "items": 0
        },
        "error": null,
        "forbidden_entity_seen": false,
        "leak_hint": false,
        "status": 200,
        "transport": "rest",
        "vector": "/api/logbook",
        "verdict": "NOT_VERIFIABLE"
      },
      {
        "allowed_entity_seen": false,
        "baseline_present": true,
        "body": {
          "body_type": "list",
          "items": 0
        },
        "error": null,
        "forbidden_entity_seen": false,
        "leak_hint": false,
        "status": 200,
        "transport": "rest",
        "vector": "/api/history/period",
        "verdict": "ALLOW"
      },
      {
        "allowed_entity_seen": true,
        "baseline_present": true,
        "body": {
          "body_type": "list",
          "entity_ids": [
            "binary_sensor.sun_solar_rising",
            "camera.tessera_seed_hidden_camera",
            "cover.tessera_seed_allowed_cover",
            "event.backup_automatic_backup",
            "input_boolean.tessera_allowed_light",
            "input_boolean.tessera_forbidden_light",
            "light.tessera_seed_allowed_light",
            "lock.tessera_seed_disabled_lock",
            "person.test_owner",
            "sensor.backup_backup_manager_state",
            "sensor.backup_last_attempted_automatic_backup",
            "sensor.backup_last_successful_automatic_backup",
            "sensor.backup_next_scheduled_automatic_backup",
            "sensor.sun_next_dawn",
            "sensor.sun_next_dusk",
            "sensor.sun_next_midnight",
            "sensor.sun_next_noon",
            "sensor.sun_next_rising",
            "sensor.sun_next_setting",
            "sensor.sun_solar_azimuth",
            "sensor.sun_solar_elevation",
            "sensor.tessera_seed_forbidden_sensor",
            "todo.shopping_list",
            "tts.google_translate_en_com"
          ],
          "entity_ids_truncated": false,
          "items": 24
        },
        "error": null,
        "forbidden_entity_seen": true,
        "leak_hint": true,
        "status": "ok",
        "transport": "ws",
        "vector": "config/entity_registry/list",
        "verdict": "LEAK"
      },
      {
        "allowed_entity_seen": false,
        "baseline_present": true,
        "body": {
          "body_type": "list",
          "items": 4
        },
        "error": null,
        "forbidden_entity_seen": false,
        "leak_hint": true,
        "status": "ok",
        "transport": "ws",
        "vector": "config/device_registry/list",
        "verdict": "LEAK"
      },
      {
        "allowed_entity_seen": false,
        "baseline_present": true,
        "body": {
          "body_type": "list",
          "items": 5
        },
        "error": null,
        "forbidden_entity_seen": false,
        "leak_hint": true,
        "status": "ok",
        "transport": "ws",
        "vector": "config/area_registry/list",
        "verdict": "LEAK"
      },
      {
        "allowed_entity_seen": false,
        "baseline_present": false,
        "body": {
          "body_type": "list",
          "items": 0
        },
        "error": null,
        "forbidden_entity_seen": false,
        "leak_hint": false,
        "status": "ok",
        "transport": "ws",
        "vector": "config/floor_registry/list",
        "verdict": "NOT_VERIFIABLE"
      },
      {
        "allowed_entity_seen": false,
        "baseline_present": false,
        "body": {
          "body_type": "list",
          "items": 0
        },
        "error": null,
        "forbidden_entity_seen": false,
        "leak_hint": false,
        "status": "ok",
        "transport": "ws",
        "vector": "config/label_registry/list",
        "verdict": "NOT_VERIFIABLE"
      },
      {
        "allowed_entity_seen": false,
        "baseline_present": false,
        "body": {
          "body_type": "list",
          "items": 0
        },
        "error": null,
        "forbidden_entity_seen": false,
        "leak_hint": false,
        "status": "ok",
        "transport": "ws",
        "vector": "config/category_registry/list",
        "verdict": "NOT_VERIFIABLE"
      },
      {
        "allowed_entity_seen": false,
        "baseline_present": false,
        "body": {
          "body_type": "dict",
          "keys": []
        },
        "error": null,
        "forbidden_entity_seen": false,
        "leak_hint": false,
        "status": "ok",
        "transport": "ws",
        "vector": "history/history_during_period",
        "verdict": "NOT_VERIFIABLE"
      },
      {
        "allowed_entity_seen": false,
        "baseline_present": true,
        "body": {
          "body_type": "list",
          "entity_ids": [
            "input_boolean.tessera_forbidden_light"
          ],
          "entity_ids_truncated": false,
          "items": 1
        },
        "error": null,
        "forbidden_entity_seen": true,
        "leak_hint": true,
        "status": "ok",
        "transport": "ws",
        "vector": "logbook/get_events",
        "verdict": "LEAK"
      },
      {
        "allowed_entity_seen": false,
        "baseline_present": true,
        "body": {
          "body_type": "dict",
          "keys": [
            "event_keys",
            "event_received"
          ]
        },
        "error": null,
        "forbidden_entity_seen": false,
        "leak_hint": true,
        "status": "ok",
        "transport": "ws",
        "vector": "render_template",
        "verdict": "LEAK"
      }
    ],
    "not_verifiable": [
      {
        "allowed_entity_seen": false,
        "baseline_present": false,
        "body": {
          "body_type": "list",
          "items": 0
        },
        "error": null,
        "forbidden_entity_seen": false,
        "leak_hint": false,
        "status": 200,
        "transport": "rest",
        "vector": "/api/logbook",
        "verdict": "NOT_VERIFIABLE"
      },
      {
        "allowed_entity_seen": false,
        "baseline_present": false,
        "body": {
          "body_type": "list",
          "items": 0
        },
        "error": null,
        "forbidden_entity_seen": false,
        "leak_hint": false,
        "status": "ok",
        "transport": "ws",
        "vector": "config/floor_registry/list",
        "verdict": "NOT_VERIFIABLE"
      },
      {
        "allowed_entity_seen": false,
        "baseline_present": false,
        "body": {
          "body_type": "list",
          "items": 0
        },
        "error": null,
        "forbidden_entity_seen": false,
        "leak_hint": false,
        "status": "ok",
        "transport": "ws",
        "vector": "config/label_registry/list",
        "verdict": "NOT_VERIFIABLE"
      },
      {
        "allowed_entity_seen": false,
        "baseline_present": false,
        "body": {
          "body_type": "list",
          "items": 0
        },
        "error": null,
        "forbidden_entity_seen": false,
        "leak_hint": false,
        "status": "ok",
        "transport": "ws",
        "vector": "config/category_registry/list",
        "verdict": "NOT_VERIFIABLE"
      },
      {
        "allowed_entity_seen": false,
        "baseline_present": false,
        "body": {
          "body_type": "dict",
          "keys": []
        },
        "error": null,
        "forbidden_entity_seen": false,
        "leak_hint": false,
        "status": "ok",
        "transport": "ws",
        "vector": "history/history_during_period",
        "verdict": "NOT_VERIFIABLE"
      }
    ],
    "registry_ws_tested": true,
    "tested": true,
    "vectors": [
      "/api/history/period",
      "/api/logbook",
      "/api/template",
      "config/area_registry/list",
      "config/category_registry/list",
      "config/device_registry/list",
      "config/entity_registry/list",
      "config/floor_registry/list",
      "config/label_registry/list",
      "history/history_during_period",
      "logbook/get_events",
      "render_template"
    ]
  },
  "d8_headless_token": {
    "llat_allowed_in_state_list": true,
    "llat_created": true,
    "llat_forbidden_in_state_list": false,
    "llat_service_allowed_status": 200,
    "llat_service_forbidden_status": 401,
    "llat_token_type": "long_lived_access_token",
    "llat_values_redacted": true,
    "matches_ui_path": true,
    "normal_headless_access_token_probe": true,
    "post_revoke_status": 401,
    "refresh_token_revoked_after_probe": true,
    "revocation_effective": true,
    "tested": true
  }
}
```

Welle-C-Lesart: `D6.entity_targeted_pass` bewertet nur die nativen entity-targeted Service-Pfade. `non_entity_service` und `system_context` sind absichtlich als dokumentierte Enforce-Luecken sichtbar; sie duerfen kein stilles PASS fuer untrusted-view/control erzeugen. `D7` ist eine Dokumentationsmatrix: `LEAK`-Zellen sind kein Messfehler, sondern Scope-Grenzen fuer harte View-Vertraulichkeit.

## D9 Static Custom-Component Scan

```json
{
  "available": true,
  "components": [
    "browser_mod",
    "dreame_vacuum",
    "epex_spot",
    "gruenbeck_cloud",
    "solarman",
    "solcast_solar",
    "unifi_insights",
    "unifi_network_map"
  ],
  "components_count": 8,
  "input_source": "exchange/2026-06-29/tessera-welle-d-task-claude-2026-06-29.md plus prior read-only HACS inventory",
  "live_volumes_config_scanned": false,
  "reason": "Welle D uses the explicit relevant-component input list from the review handoff and does not scan /Volumes/config in this run",
  "skipped": false
}
```

## D9 Runtime-Klassifikation

```json
{
  "allow_count": 0,
  "classification_rules": {
    "ALLOW": "only for runtime-verified components without enforcement-relevant surface or with proven user-context checks",
    "DENY": "reserved for reproduced unsafe behavior",
    "TIER-2": "needs Zusatz-Enforcement / explicit non-production or supplemental controls",
    "UNKNOWN_BLOCK_ENFORCE": "fail-closed default whenever runtime verification is absent or incomplete"
  },
  "components_count": 8,
  "d9_gate_pass_fail_closed": true,
  "deny_count": 0,
  "dev_runtime_components": [
    {
      "actor": "dev runtime inventory, not production input ALLOW",
      "allowed_entity_result": null,
      "component": "tessera_spike",
      "component_id": "tessera_spike",
      "confidence": "dev-runtime-inventory",
      "context_user_id": "not_probed_per_service",
      "forbidden_entity_result": null,
      "input_source": "ha-tessera-dev /config/custom_components runtime inventory",
      "input_timestamp": "2026-06-29",
      "installed_in_dev": true,
      "permission_path": "unknown",
      "reason": "dev harness exposes non-entity services and is explicitly not a production allow candidate",
      "required_followup": "component-specific runtime probe required before production ALLOW",
      "response_leak": "not_probed",
      "runtime_services": [
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
      "runtime_verified": true,
      "service_type": "non-entity/mixed",
      "static_findings": {
        "http_or_panel_marker": true,
        "python_files": 1,
        "registers_services": true,
        "services_yaml": true,
        "websocket_marker": true
      },
      "surfaces": {
        "http_or_panel": true,
        "services": [
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
        "services_yaml": true,
        "websocket": true
      },
      "verdict": "TIER-2"
    }
  ],
  "dev_runtime_components_count": 1,
  "dev_runtime_tier2_count": 1,
  "enforce_blocked_by_unknown": true,
  "input_components": [
    {
      "actor": "restricted_non_admin/admin/system not runtime-probed for this input",
      "allowed_entity_result": null,
      "component": "browser_mod",
      "component_id": "browser_mod",
      "confidence": "high-fail-closed",
      "context_user_id": "unknown",
      "file_line": "exchange/2026-06-29/tessera-welle-d-task-claude-2026-06-29.md:10",
      "forbidden_entity_result": null,
      "input_source": "historical read-only custom_components review; no /Volumes/config scan in this run",
      "input_timestamp": "2026-06-29",
      "installed_in_dev": false,
      "permission_path": "unknown",
      "reason": "input component is not installed in ha-tessera-dev, so no runtime ALLOW is possible",
      "required_followup": "install same component/version in ha-tessera-dev and run service/http/ws/user-context probes before any ALLOW",
      "response_leak": "unknown",
      "runtime_services": [],
      "runtime_verified": false,
      "service_type": "unknown",
      "static_findings": {
        "http_or_panel_marker": null,
        "registers_services": null,
        "services_yaml": null,
        "websocket_marker": null
      },
      "surfaces": {
        "http_or_panel": null,
        "services": [],
        "services_yaml": null,
        "websocket": null
      },
      "verdict": "UNKNOWN_BLOCK_ENFORCE"
    },
    {
      "actor": "restricted_non_admin/admin/system not runtime-probed for this input",
      "allowed_entity_result": null,
      "component": "dreame_vacuum",
      "component_id": "dreame_vacuum",
      "confidence": "high-fail-closed",
      "context_user_id": "unknown",
      "file_line": "exchange/2026-06-29/tessera-welle-d-task-claude-2026-06-29.md:10",
      "forbidden_entity_result": null,
      "input_source": "historical read-only custom_components review; no /Volumes/config scan in this run",
      "input_timestamp": "2026-06-29",
      "installed_in_dev": false,
      "permission_path": "unknown",
      "reason": "input component is not installed in ha-tessera-dev, so no runtime ALLOW is possible",
      "required_followup": "install same component/version in ha-tessera-dev and run service/http/ws/user-context probes before any ALLOW",
      "response_leak": "unknown",
      "runtime_services": [],
      "runtime_verified": false,
      "service_type": "unknown",
      "static_findings": {
        "http_or_panel_marker": null,
        "registers_services": null,
        "services_yaml": null,
        "websocket_marker": null
      },
      "surfaces": {
        "http_or_panel": null,
        "services": [],
        "services_yaml": null,
        "websocket": null
      },
      "verdict": "UNKNOWN_BLOCK_ENFORCE"
    },
    {
      "actor": "restricted_non_admin/admin/system not runtime-probed for this input",
      "allowed_entity_result": null,
      "component": "epex_spot",
      "component_id": "epex_spot",
      "confidence": "high-fail-closed",
      "context_user_id": "unknown",
      "file_line": "exchange/2026-06-29/tessera-welle-d-task-claude-2026-06-29.md:10",
      "forbidden_entity_result": null,
      "input_source": "historical read-only custom_components review; no /Volumes/config scan in this run",
      "input_timestamp": "2026-06-29",
      "installed_in_dev": false,
      "permission_path": "unknown",
      "reason": "input component is not installed in ha-tessera-dev, so no runtime ALLOW is possible",
      "required_followup": "install same component/version in ha-tessera-dev and run service/http/ws/user-context probes before any ALLOW",
      "response_leak": "unknown",
      "runtime_services": [],
      "runtime_verified": false,
      "service_type": "unknown",
      "static_findings": {
        "http_or_panel_marker": null,
        "registers_services": null,
        "services_yaml": null,
        "websocket_marker": null
      },
      "surfaces": {
        "http_or_panel": null,
        "services": [],
        "services_yaml": null,
        "websocket": null
      },
      "verdict": "UNKNOWN_BLOCK_ENFORCE"
    },
    {
      "actor": "restricted_non_admin/admin/system not runtime-probed for this input",
      "allowed_entity_result": null,
      "component": "gruenbeck_cloud",
      "component_id": "gruenbeck_cloud",
      "confidence": "high-fail-closed",
      "context_user_id": "unknown",
      "file_line": "exchange/2026-06-29/tessera-welle-d-task-claude-2026-06-29.md:10",
      "forbidden_entity_result": null,
      "input_source": "historical read-only custom_components review; no /Volumes/config scan in this run",
      "input_timestamp": "2026-06-29",
      "installed_in_dev": false,
      "permission_path": "unknown",
      "reason": "input component is not installed in ha-tessera-dev, so no runtime ALLOW is possible",
      "required_followup": "install same component/version in ha-tessera-dev and run service/http/ws/user-context probes before any ALLOW",
      "response_leak": "unknown",
      "runtime_services": [],
      "runtime_verified": false,
      "service_type": "unknown",
      "static_findings": {
        "http_or_panel_marker": null,
        "registers_services": null,
        "services_yaml": null,
        "websocket_marker": null
      },
      "surfaces": {
        "http_or_panel": null,
        "services": [],
        "services_yaml": null,
        "websocket": null
      },
      "verdict": "UNKNOWN_BLOCK_ENFORCE"
    },
    {
      "actor": "restricted_non_admin/admin/system not runtime-probed for this input",
      "allowed_entity_result": null,
      "component": "solarman",
      "component_id": "solarman",
      "confidence": "high-fail-closed",
      "context_user_id": "unknown",
      "file_line": "exchange/2026-06-29/tessera-welle-d-task-claude-2026-06-29.md:10",
      "forbidden_entity_result": null,
      "input_source": "historical read-only custom_components review; no /Volumes/config scan in this run",
      "input_timestamp": "2026-06-29",
      "installed_in_dev": false,
      "permission_path": "unknown",
      "reason": "input component is not installed in ha-tessera-dev, so no runtime ALLOW is possible",
      "required_followup": "install same component/version in ha-tessera-dev and run service/http/ws/user-context probes before any ALLOW",
      "response_leak": "unknown",
      "runtime_services": [],
      "runtime_verified": false,
      "service_type": "unknown",
      "static_findings": {
        "http_or_panel_marker": null,
        "registers_services": null,
        "services_yaml": null,
        "websocket_marker": null
      },
      "surfaces": {
        "http_or_panel": null,
        "services": [],
        "services_yaml": null,
        "websocket": null
      },
      "verdict": "UNKNOWN_BLOCK_ENFORCE"
    },
    {
      "actor": "restricted_non_admin/admin/system not runtime-probed for this input",
      "allowed_entity_result": null,
      "component": "solcast_solar",
      "component_id": "solcast_solar",
      "confidence": "high-fail-closed",
      "context_user_id": "unknown",
      "file_line": "exchange/2026-06-29/tessera-welle-d-task-claude-2026-06-29.md:10",
      "forbidden_entity_result": null,
      "input_source": "historical read-only custom_components review; no /Volumes/config scan in this run",
      "input_timestamp": "2026-06-29",
      "installed_in_dev": false,
      "permission_path": "unknown",
      "reason": "input component is not installed in ha-tessera-dev, so no runtime ALLOW is possible",
      "required_followup": "install same component/version in ha-tessera-dev and run service/http/ws/user-context probes before any ALLOW",
      "response_leak": "unknown",
      "runtime_services": [],
      "runtime_verified": false,
      "service_type": "unknown",
      "static_findings": {
        "http_or_panel_marker": null,
        "registers_services": null,
        "services_yaml": null,
        "websocket_marker": null
      },
      "surfaces": {
        "http_or_panel": null,
        "services": [],
        "services_yaml": null,
        "websocket": null
      },
      "verdict": "UNKNOWN_BLOCK_ENFORCE"
    },
    {
      "actor": "restricted_non_admin/admin/system not runtime-probed for this input",
      "allowed_entity_result": null,
      "component": "unifi_insights",
      "component_id": "unifi_insights",
      "confidence": "high-fail-closed",
      "context_user_id": "unknown",
      "file_line": "exchange/2026-06-29/tessera-welle-d-task-claude-2026-06-29.md:10",
      "forbidden_entity_result": null,
      "input_source": "historical read-only custom_components review; no /Volumes/config scan in this run",
      "input_timestamp": "2026-06-29",
      "installed_in_dev": false,
      "permission_path": "unknown",
      "reason": "input component is not installed in ha-tessera-dev, so no runtime ALLOW is possible",
      "required_followup": "install same component/version in ha-tessera-dev and run service/http/ws/user-context probes before any ALLOW",
      "response_leak": "unknown",
      "runtime_services": [],
      "runtime_verified": false,
      "service_type": "unknown",
      "static_findings": {
        "http_or_panel_marker": null,
        "registers_services": null,
        "services_yaml": null,
        "websocket_marker": null
      },
      "surfaces": {
        "http_or_panel": null,
        "services": [],
        "services_yaml": null,
        "websocket": null
      },
      "verdict": "UNKNOWN_BLOCK_ENFORCE"
    },
    {
      "actor": "restricted_non_admin/admin/system not runtime-probed for this input",
      "allowed_entity_result": null,
      "component": "unifi_network_map",
      "component_id": "unifi_network_map",
      "confidence": "high-fail-closed",
      "context_user_id": "unknown",
      "file_line": "exchange/2026-06-29/tessera-welle-d-task-claude-2026-06-29.md:10",
      "forbidden_entity_result": null,
      "input_source": "historical read-only custom_components review; no /Volumes/config scan in this run",
      "input_timestamp": "2026-06-29",
      "installed_in_dev": false,
      "permission_path": "unknown",
      "reason": "input component is not installed in ha-tessera-dev, so no runtime ALLOW is possible",
      "required_followup": "install same component/version in ha-tessera-dev and run service/http/ws/user-context probes before any ALLOW",
      "response_leak": "unknown",
      "runtime_services": [],
      "runtime_verified": false,
      "service_type": "unknown",
      "static_findings": {
        "http_or_panel_marker": null,
        "registers_services": null,
        "services_yaml": null,
        "websocket_marker": null
      },
      "surfaces": {
        "http_or_panel": null,
        "services": [],
        "services_yaml": null,
        "websocket": null
      },
      "verdict": "UNKNOWN_BLOCK_ENFORCE"
    }
  ],
  "input_components_count": 8,
  "live_volumes_config_scanned": false,
  "runtime_custom_components_tested": true,
  "tier2_count": 0,
  "unknown_block_enforce_count": 8
}
```

D9-Lesart: `PASS` bedeutet hier **nicht** `ALLOW` fuer reale HACS-Komponenten. Es bedeutet: Die Matrix ist vorhanden, nutzt eine explizite Input-Provenienz statt `/Volumes/config`-Live-Scan und setzt fuer nicht runtime-verifizierte Service/HTTP/WS-Kandidaten konsequent `UNKNOWN_BLOCK_ENFORCE`. Solange `enforce_blocked_by_unknown` true ist, bleibt Enforce fail-closed blockiert.

## D11/D13/D15 Lifecycle-Gates

```json
{
  "d11_version_gate": {
    "auth_fingerprint_unchanged": true,
    "effective_mode": "monitor",
    "enforce_requested": true,
    "native_write_attempted": false,
    "native_write_blocked": true,
    "native_write_call_count": 0,
    "native_write_refused_before_call": true,
    "owner_admin_no_lockout": true,
    "repair_issue_created": true,
    "requested_mode": "enforce",
    "status": "PASS",
    "version_mismatch_detected": true
  },
  "d13_hacs_rollback": {
    "auth_fingerprint_changed_by_update": true,
    "native_write_attempted": true,
    "owner_admin_no_lockout": true,
    "rollback_restored_exact_fingerprint": true,
    "simulation_method": "in-process HACS update/downgrade simulation; no real HACS package install",
    "status": "PASS"
  },
  "d15_lifecycle": {
    "enforce_full_superset_written": true,
    "enforce_native_write_attempted": true,
    "enforce_native_write_blocked": false,
    "enforce_permission_probe": {
      "forbidden_control": true,
      "forbidden_read": true
    },
    "monitor_native_write_observed": false,
    "off_native_write_observed": false,
    "owner_admin_no_lockout": true,
    "restore_exact_fingerprint": true,
    "status": "PASS"
  }
}
```

Lifecycle-Lesart: `D11` belegt im Dev-Spike den fail-closed Version-Gate-Pfad per unsupported-version Lifecycle-Transition, Repairs-Issue und unveraendertem Auth-Fingerprint. `D13` ist eine HACS-Update/Downgrade-Simulation, kein echter HACS-Paketwechsel; PASS verlangt einen beobachteten Zwischen-Write und exakten Rollback. `D15` misst `off -> monitor -> enforce -> restore` in-process mit vollem Gruppen-Superset, Permission-Probe und exaktem Restore-Fingerprint. Alle drei bleiben Dev-Spike-Belege, kein Produkt-Enforce-Go.

## Core-Anker

- HA `auth_store.py`: private `_groups`, `_data_to_save()`, `_store.async_save()` sind der gemessene Schreibpfad.
- HA `auth/models.py`: `User.permissions` ist cached; `invalidate_cache()` ist fuer reine Policy-Mutation relevant.
- HA `auth/__init__.py`: `async_update_user(group_ids=...)` ist der oeffentliche Restore-/Binding-Pfad.
- HA `http/auth.py`: `Home Assistant Content` ist `system_generated` und bleibt unmanaged.

## Go/No-Go

- **Go fuer weitere Phase-0-Haertung:** ja.
- **Go fuer Tessera-Enforce/Product:** nein.
- **Naechste Pflicht:** echte HACS-/Upgrade-Probe ausserhalb der Simulation, D10/CM5-Benchmark, D12/OIDC und Produkt-/Release-Gates gesondert; kein Enforce/Product-Go aus diesem Spike.

## Artefakte

- D0 Evidence: `evidence/tessera-d0-evidence-2026-06-29.md`
- D0 JSON: `evidence/tessera-d0-evidence-2026-06-29.json`
- Spike JSON: `evidence/tessera-spike-result-2026-06-29.json`
