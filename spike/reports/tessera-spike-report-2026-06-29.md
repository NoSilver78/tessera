# Tessera Phase-0 Spike Report

Stand: 2026-06-29T10:23:52

Modus: Dev-only gegen `ha-tessera-dev`; `/Volumes/config` nur read-only fuer D9-Statik; keine Secrets/Token/Auth-Codes ausgegeben.

## Gesamturteil

**PARTIAL / kein Enforce-Go.**

D0 ist gruen genug, um den dev-only Messlauf zu starten. D1, D2 und D4 liefern starke positive Signale fuer den Auth-Store-Schreibpfad. D3/D6/D7/D8/D9 bleiben bewusst **PARTIAL**, weil WS, echte LLAT-Rotation, vollstaendige Leak-Matrix, Custom-Component-Runtime und Live/CM5-Gates in diesem Lauf nicht vollstaendig abgedeckt sind.

## DoD Matrix

| DoD | Verdict | Kurzbegruendung |
|---|---:|---|
| D0 | PASS | Preflight/onboarding/seed/harness gate |
| D1 | PASS | tessera group/policy/user restart survival |
| D2 | PASS | policy-only change reflected after explicit cache invalidation without restart |
| D3 | PARTIAL | internal + REST + service tested; WS not tested in this run |
| D4 | PASS | full union and restore via public update_user |
| D5 | PARTIAL | restore primitive proved; corrupt-store boot rescue not executed in this run |
| D6 | PARTIAL | entity service allowed/forbidden and entity_id:all probed; response/non-entity matrix incomplete |
| D7 | PARTIAL | render_template probed; logbook/registry/history/WS leak matrix incomplete |
| D8 | PARTIAL | headless normal token probe and revocation; real LLAT rotation not performed |
| D9 | PARTIAL | static /Volumes/config custom-component scan; runtime classification not complete |

## D0

- Harte Docker-Isolation: `True`
- Fresh-Baseline-Allowlist: `True`
- Onboarding abgeschlossen: `True`
- Exit-Code: `0`
- Harness-Service geladen: `True`
- 8-Service-Load-Check: `True`; registriert `['ensure_group', 'flush_auth_store', 'invalidate_user', 'probe_check_entity', 'restore', 'run_spike', 'set_group_policy', 'set_user_groups', 'snapshot']`
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
    "detail": "HTTP evidence stores body type/keys only; values redacted",
    "gate": "failure_redaction",
    "status": "PASS"
  },
  {
    "gate": "a1_8_services",
    "registered_services": [
      "ensure_group",
      "flush_auth_store",
      "invalidate_user",
      "probe_check_entity",
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
    "device_id": "2a2f425d887118dde9aba4cb8427c782"
  },
  "entities": [
    {
      "area_id": null,
      "class": "device_area_allowed_light",
      "device_id": "2a2f425d887118dde9aba4cb8427c782",
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
      "device_id": "2a2f425d887118dde9aba4cb8427c782",
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
  "d1_pre_restart": {
    "group_created": true,
    "policy_written": true
  },
  "d2_policy_change_no_restart": {
    "allowed_read_after_policy_change": false,
    "forbidden_control_after_policy_change": true,
    "forbidden_read_after_policy_change": true
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
  "d5_restore_primitive": {
    "boot_rescue_corruption_tested": false,
    "public_async_update_user_restore_available": true
  }
}
```

Restart-Survival:

```json
{
  "group_survived_restart": true,
  "policy_survived_restart": true,
  "user_survived_restart": true
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
  "available": true,
  "components_count": 14,
  "http_or_ws_candidates": [
    "auth_oidc",
    "browser_mod",
    "hacs",
    "unifi_insights",
    "unifi_network_map"
  ],
  "path": "/Volumes/config/custom_components",
  "services_yaml_components": [
    "browser_mod",
    "dreame_vacuum",
    "epex_spot",
    "gruenbeck_cloud",
    "solarman",
    "solcast_solar",
    "unifi_insights",
    "unifi_network_map"
  ]
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
