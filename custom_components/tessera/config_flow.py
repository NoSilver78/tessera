"""Config flow for the Tessera integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries

from .const import DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema({})


class TesseraConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Minimal config flow for Tessera phase-1 setup."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial user step.

        Args:
            user_input: Optional submitted form payload.

        Returns:
            A Home Assistant config-flow result.
        """
        if user_input is not None:
            return self.async_create_entry(title="Tessera", data={})

        return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA)
