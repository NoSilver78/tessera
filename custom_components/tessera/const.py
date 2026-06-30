"""Constants for the Tessera integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "tessera"

# Storage schema version. Bumping this requires a migration path in store.py.
STORAGE_VERSION: Final = 1
# Persistent ``.storage/`` keys, versioned by STORAGE_VERSION.
CONFIG_STORAGE_KEY: Final = "tessera.config"
POLICY_STORAGE_KEY: Final = "tessera.policy"
STATE_STORAGE_KEY: Final = "tessera.state"

# Operating modes. These are the only accepted values; they are validated via
# ``schema.MODES``. ``enforce`` is inert in phase 1 (monitor-preview only, no
# native Home Assistant auth writes) — see docs/spec-e3-enforce.md.
MODE_OFF: Final = "off"
MODE_MONITOR: Final = "monitor"
MODE_ENFORCE: Final = "enforce"
# Immutable set used as an allow-list; frozenset prevents accidental mutation.
MODES: Final = frozenset({MODE_OFF, MODE_MONITOR, MODE_ENFORCE})
