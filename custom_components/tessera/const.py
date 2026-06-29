"""Constants for the Tessera integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "tessera"

STORAGE_VERSION: Final = 1
CONFIG_STORAGE_KEY: Final = "tessera.config"
POLICY_STORAGE_KEY: Final = "tessera.policy"

MODE_OFF: Final = "off"
MODE_MONITOR: Final = "monitor"
MODE_ENFORCE: Final = "enforce"
MODES: Final = {MODE_OFF, MODE_MONITOR, MODE_ENFORCE}
