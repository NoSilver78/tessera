"""Config flow for the Tessera integration."""

from __future__ import annotations

import logging
from copy import deepcopy
from typing import TYPE_CHECKING, Any, cast

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import DOMAIN, MODE_ENFORCE, MODE_MONITOR, MODE_OFF, MODES
from .monitor import compile_current, lint_current_preview, log_monitor_preview
from .resolver import AreaEntityResolver
from .schema import (
    PermissionLeaf,
    RoleData,
    TesseraConfigData,
    TesseraPolicyData,
    TesseraSchemaError,
    validate_config_data,
    validate_policy_data,
)
from .store import TesseraStore, mutation_lock

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({})
ACTION_SET_MODE = "set_mode"
ACTION_ADD_ROLE = "add_role"
ACTION_REMOVE_ROLE = "remove_role"
ACTION_ADD_AREA_GRANT = "add_area_grant"
ACTION_REMOVE_AREA_GRANT = "remove_area_grant"
# Separator for the ``area::role`` keys used by the remove-grant selector.
GRANT_SEPARATOR = "::"


def encode_grant(area_id: str, role_id: str) -> str:
    """Encode an area/role pair into a stable ``area::role`` selection key."""
    return f"{area_id}{GRANT_SEPARATOR}{role_id}"


def decode_grant(encoded_grant: str) -> tuple[str, str]:
    """Decode an ``area::role`` selection key into its area and role ids.

    Raises:
        TesseraSchemaError: If the key is not a well-formed ``area::role`` pair.
    """
    area_id, separator, role_id = encoded_grant.partition(GRANT_SEPARATOR)
    if not area_id or separator != GRANT_SEPARATOR or not role_id:
        raise TesseraSchemaError("area grant selection must use area::role")
    return area_id, role_id


def _role_options(config: TesseraConfigData) -> list[str]:
    """Return sorted role choices for forms."""
    return sorted(config["roles"])


def _area_grant_options(policy: TesseraPolicyData) -> list[str]:
    """Return stable grant choices encoded as area::role."""
    return [
        encode_grant(area_id, role_id)
        for area_id, role_map in sorted(policy["area_grants"].items())
        for role_id in sorted(role_map)
    ]


def set_mode(config: TesseraConfigData, mode: str) -> TesseraConfigData:
    """Return config with an updated mode after schema validation."""
    next_config = deepcopy(config)
    next_config["mode"] = mode
    return validate_config_data(next_config)


def add_role(
    config: TesseraConfigData,
    role_id: str,
    *,
    name: str = "",
    description: str = "",
) -> TesseraConfigData:
    """Return config with one role added or replaced."""
    next_config = deepcopy(config)
    if role_id in next_config["roles"]:
        raise TesseraSchemaError("role id already exists")
    role: RoleData = {}
    if name:
        role["name"] = name
    if description:
        role["description"] = description
    next_config["roles"][role_id] = role
    return validate_config_data(next_config)


def remove_role(
    config: TesseraConfigData, policy: TesseraPolicyData, role_id: str
) -> tuple[TesseraConfigData, TesseraPolicyData]:
    """Return config and policy with one role removed everywhere."""
    next_config = validate_config_data(config)
    next_policy = validate_policy_data(policy)
    next_config["roles"].pop(role_id, None)
    for membership in (
        next_config["membership"]["by_user"],
        next_config["membership"]["by_group"],
    ):
        empty_subjects: list[str] = []
        for subject, role_ids in membership.items():
            membership[subject] = [item for item in role_ids if item != role_id]
            if not membership[subject]:
                empty_subjects.append(subject)
        for subject in empty_subjects:
            membership.pop(subject, None)

    for grants in (
        next_policy["floor_grants"],
        next_policy["area_grants"],
        next_policy["entity_overrides"],
    ):
        empty_targets: list[str] = []
        for target_id, role_map in grants.items():
            role_map.pop(role_id, None)
            if not role_map:
                empty_targets.append(target_id)
        for target_id in empty_targets:
            grants.pop(target_id, None)

    return validate_config_data(next_config), validate_policy_data(next_policy)


def set_user_membership(
    config: TesseraConfigData, user_id: str, role_ids: list[str]
) -> TesseraConfigData:
    """Return config with one HA user's Tessera role membership updated."""
    next_config = validate_config_data(config)
    if not isinstance(user_id, str) or not user_id:
        raise TesseraSchemaError("membership user id must be a non-empty string")

    normalized_role_ids = sorted(set(role_ids))
    unknown_role_ids = [
        role_id
        for role_id in normalized_role_ids
        if role_id not in next_config["roles"]
    ]
    if unknown_role_ids:
        raise TesseraSchemaError("membership role must exist in config.roles")

    if normalized_role_ids:
        next_config["membership"]["by_user"][user_id] = normalized_role_ids
    else:
        next_config["membership"]["by_user"].pop(user_id, None)
    return validate_config_data(next_config)


def add_area_grant(
    config: TesseraConfigData,
    policy: TesseraPolicyData,
    *,
    area_id: str,
    role_id: str,
    read: bool,
    control: bool,
) -> TesseraPolicyData:
    """Return policy with one schema-aware area grant added."""
    if role_id not in config["roles"]:
        raise TesseraSchemaError("area grant role must exist in config.roles")

    leaf: PermissionLeaf = {}
    if read or control:
        leaf["read"] = True
    if control:
        leaf["control"] = True
    if not leaf:
        raise TesseraSchemaError("area grant must enable read or control")

    next_policy = validate_policy_data(policy)
    next_policy["area_grants"].setdefault(area_id, {})[role_id] = leaf
    return validate_policy_data(next_policy)


def set_floor_grant(
    config: TesseraConfigData,
    policy: TesseraPolicyData,
    *,
    floor_id: str,
    role_id: str,
    read: bool,
    control: bool,
) -> TesseraPolicyData:
    """Return policy with one schema-aware floor grant set."""
    if role_id not in config["roles"]:
        raise TesseraSchemaError("floor grant role must exist in config.roles")

    next_policy = validate_policy_data(policy)
    if not read and not control:
        role_map = next_policy["floor_grants"].get(floor_id)
        if role_map is not None:
            role_map.pop(role_id, None)
            if not role_map:
                next_policy["floor_grants"].pop(floor_id, None)
        return validate_policy_data(next_policy)

    leaf: PermissionLeaf = {}
    if read or control:
        leaf["read"] = True
    if control:
        leaf["control"] = True
    next_policy["floor_grants"].setdefault(floor_id, {})[role_id] = leaf
    return validate_policy_data(next_policy)


def remove_floor_grant(
    policy: TesseraPolicyData, encoded_grant: str
) -> TesseraPolicyData:
    """Return policy with one encoded floor::role grant removed."""
    floor_id, role_id = decode_grant(encoded_grant)
    next_policy = validate_policy_data(policy)
    role_map = next_policy["floor_grants"].get(floor_id)
    if role_map is not None:
        role_map.pop(role_id, None)
        if not role_map:
            next_policy["floor_grants"].pop(floor_id, None)
    return validate_policy_data(next_policy)


def set_label_grant(
    config: TesseraConfigData,
    policy: TesseraPolicyData,
    *,
    label_id: str,
    role_id: str,
    read: bool,
    control: bool,
) -> TesseraPolicyData:
    """Return policy with one schema-aware label grant set."""
    if role_id not in config["roles"]:
        raise TesseraSchemaError("label grant role must exist in config.roles")

    next_policy = validate_policy_data(policy)
    if not read and not control:
        role_map = next_policy["label_grants"].get(label_id)
        if role_map is not None:
            role_map.pop(role_id, None)
            if not role_map:
                next_policy["label_grants"].pop(label_id, None)
        return validate_policy_data(next_policy)

    leaf: PermissionLeaf = {}
    if read or control:
        leaf["read"] = True
    if control:
        leaf["control"] = True
    next_policy["label_grants"].setdefault(label_id, {})[role_id] = leaf
    return validate_policy_data(next_policy)


def remove_label_grant(
    policy: TesseraPolicyData, encoded_grant: str
) -> TesseraPolicyData:
    """Return policy with one encoded label::role grant removed."""
    label_id, role_id = decode_grant(encoded_grant)
    next_policy = validate_policy_data(policy)
    role_map = next_policy["label_grants"].get(label_id)
    if role_map is not None:
        role_map.pop(role_id, None)
        if not role_map:
            next_policy["label_grants"].pop(label_id, None)
    return validate_policy_data(next_policy)


def remove_area_grant(
    policy: TesseraPolicyData, encoded_grant: str
) -> TesseraPolicyData:
    """Return policy with one encoded area::role grant removed."""
    area_id, role_id = decode_grant(encoded_grant)
    next_policy = validate_policy_data(policy)
    role_map = next_policy["area_grants"].get(area_id)
    if role_map is not None:
        role_map.pop(role_id, None)
        if not role_map:
            next_policy["area_grants"].pop(area_id, None)
    return validate_policy_data(next_policy)


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
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title="Tessera", data={})

        return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA)

    @staticmethod
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> TesseraOptionsFlow:
        """Create the Tessera options flow."""
        return TesseraOptionsFlow(config_entry)


class TesseraOptionsFlow(config_entries.OptionsFlow):
    """Options flow for monitor-mode Tessera basics."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow state."""
        self._config_entry = config_entry
        self._store: TesseraStore | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Choose the basic configuration action."""
        if user_input is not None:
            return await self.async_step_action(user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("action"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                ACTION_SET_MODE,
                                ACTION_ADD_ROLE,
                                ACTION_REMOVE_ROLE,
                                ACTION_ADD_AREA_GRANT,
                                ACTION_REMOVE_AREA_GRANT,
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                            translation_key="action",
                        )
                    )
                }
            ),
        )

    async def async_step_action(
        self, user_input: dict[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Route the selected action to its form."""
        action = user_input["action"]
        if action == ACTION_SET_MODE:
            return await self.async_step_set_mode()
        if action == ACTION_ADD_ROLE:
            return await self.async_step_add_role()
        if action == ACTION_REMOVE_ROLE:
            return await self.async_step_remove_role()
        if action == ACTION_ADD_AREA_GRANT:
            return await self.async_step_add_area_grant()
        if action == ACTION_REMOVE_AREA_GRANT:
            return await self.async_step_remove_area_grant()
        return self.async_abort(reason="unknown_action")

    async def async_step_set_mode(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Persist the Tessera mode."""
        async with mutation_lock(self.hass):
            config, policy = await self._load()
            if user_input is not None:
                try:
                    config = set_mode(config, cast(str, user_input["mode"]))
                    return await self._save_preview_finish(config, policy)
                except (KeyError, TesseraSchemaError):
                    return self._form_set_mode(config, {"base": "invalid"})

            return self._form_set_mode(config)

    async def async_step_add_role(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Add or update a Tessera role."""
        async with mutation_lock(self.hass):
            config, policy = await self._load()
            if user_input is not None:
                try:
                    config = add_role(
                        config,
                        cast(str, user_input["role_id"]),
                        name=cast(str, user_input.get("name", "")),
                        description=cast(str, user_input.get("description", "")),
                    )
                    return await self._save_preview_finish(config, policy)
                except (KeyError, TesseraSchemaError):
                    return self._form_add_role({"base": "invalid"})

            return self._form_add_role()

    async def async_step_remove_role(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Remove a role and its grants."""
        async with mutation_lock(self.hass):
            config, policy = await self._load()
            if user_input is not None:
                try:
                    config, policy = remove_role(
                        config, policy, cast(str, user_input["role_id"])
                    )
                    return await self._save_preview_finish(config, policy)
                except (KeyError, TesseraSchemaError):
                    return self._form_remove_role(config, {"base": "invalid"})

            return self._form_remove_role(config)

    async def async_step_add_area_grant(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Add an Area x Role grant."""
        async with mutation_lock(self.hass):
            config, policy = await self._load()
            if user_input is not None:
                try:
                    policy = add_area_grant(
                        config,
                        policy,
                        area_id=cast(str, user_input["area_id"]),
                        role_id=cast(str, user_input["role_id"]),
                        read=cast(bool, user_input["read"]),
                        control=cast(bool, user_input["control"]),
                    )
                    return await self._save_preview_finish(config, policy)
                except (KeyError, TesseraSchemaError):
                    return self._form_add_area_grant(config, {"base": "invalid"})

            return self._form_add_area_grant(config)

    async def async_step_remove_area_grant(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Remove an Area x Role grant."""
        async with mutation_lock(self.hass):
            config, policy = await self._load()
            if user_input is not None:
                try:
                    policy = remove_area_grant(policy, cast(str, user_input["grant"]))
                    return await self._save_preview_finish(config, policy)
                except (KeyError, TesseraSchemaError):
                    return self._form_remove_area_grant(policy, {"base": "invalid"})

            return self._form_remove_area_grant(policy)

    async def _load(self) -> tuple[TesseraConfigData, TesseraPolicyData]:
        """Load config and policy stores."""
        store = self._get_store()
        return await store.async_load_config(), await store.async_load_policy()

    async def _save_preview_finish(
        self, config: TesseraConfigData, policy: TesseraPolicyData
    ) -> config_entries.ConfigFlowResult:
        """Persist stores, refresh the loaded entry, and finish the options flow."""
        store = self._get_store()
        await store.async_save_config(config)
        await store.async_save_policy(policy)
        if not await _refresh_loaded_entry(
            self.hass, self._config_entry.entry_id, store
        ):
            await _compile_preview(
                self.hass,
                self._config_entry.entry_id,
                store,
                config=config,
                policy=policy,
            )
        return self.async_create_entry(title="", data={})

    def _get_store(self) -> TesseraStore:
        """Return the options-flow store."""
        if self._store is None:
            self._store = TesseraStore(self.hass)
        return self._store

    def _form_set_mode(
        self, config: TesseraConfigData, errors: dict[str, str] | None = None
    ) -> config_entries.ConfigFlowResult:
        return self.async_show_form(
            step_id=ACTION_SET_MODE,
            data_schema=vol.Schema(
                {vol.Required("mode", default=config["mode"]): vol.In(sorted(MODES))}
            ),
            errors=errors,
        )

    def _form_add_role(
        self, errors: dict[str, str] | None = None
    ) -> config_entries.ConfigFlowResult:
        return self.async_show_form(
            step_id=ACTION_ADD_ROLE,
            data_schema=vol.Schema(
                {
                    vol.Required("role_id"): str,
                    vol.Optional("name", default=""): str,
                    vol.Optional("description", default=""): str,
                }
            ),
            errors=errors,
        )

    def _form_remove_role(
        self, config: TesseraConfigData, errors: dict[str, str] | None = None
    ) -> config_entries.ConfigFlowResult:
        if not _role_options(config):
            return self.async_show_form(
                step_id=ACTION_REMOVE_ROLE,
                data_schema=vol.Schema({}),
                errors=errors or {"base": "no_roles"},
            )
        return self.async_show_form(
            step_id=ACTION_REMOVE_ROLE,
            data_schema=vol.Schema(
                {vol.Required("role_id"): vol.In(_role_options(config))}
            ),
            errors=errors,
        )

    def _form_add_area_grant(
        self, config: TesseraConfigData, errors: dict[str, str] | None = None
    ) -> config_entries.ConfigFlowResult:
        if not _role_options(config):
            return self.async_show_form(
                step_id=ACTION_ADD_AREA_GRANT,
                data_schema=vol.Schema({}),
                errors=errors or {"base": "no_roles"},
            )
        return self.async_show_form(
            step_id=ACTION_ADD_AREA_GRANT,
            data_schema=vol.Schema(
                {
                    vol.Required("area_id"): selector.AreaSelector(),
                    vol.Required("role_id"): vol.In(_role_options(config)),
                    vol.Optional("read", default=True): bool,
                    vol.Optional("control", default=False): bool,
                }
            ),
            errors=errors,
        )

    def _form_remove_area_grant(
        self, policy: TesseraPolicyData, errors: dict[str, str] | None = None
    ) -> config_entries.ConfigFlowResult:
        if not _area_grant_options(policy):
            return self.async_show_form(
                step_id=ACTION_REMOVE_AREA_GRANT,
                data_schema=vol.Schema({}),
                errors=errors or {"base": "no_area_grants"},
            )
        return self.async_show_form(
            step_id=ACTION_REMOVE_AREA_GRANT,
            data_schema=vol.Schema(
                {vol.Required("grant"): vol.In(_area_grant_options(policy))}
            ),
            errors=errors,
        )


async def _compile_preview(
    hass: HomeAssistant,
    entry_id: str,
    store: TesseraStore,
    *,
    config: TesseraConfigData,
    policy: TesseraPolicyData,
) -> None:
    """Refresh the read-only monitor preview after an options change."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    entry_data = domain_data.setdefault(entry_id, {"store": store})
    entry_data["store"] = store
    if config["mode"] == MODE_OFF:
        entry_data.pop("compiled", None)
        entry_data.pop("preview", None)
        return
    if config["mode"] == MODE_ENFORCE:
        LOGGER.warning(
            "Tessera enforce mode saved for unloaded entry %s; enforce applies "
            "on next setup/reload",
            entry_id,
        )
    if config["mode"] in {MODE_MONITOR, MODE_ENFORCE}:
        resolver = AreaEntityResolver.from_hass(hass)
        compiled = await compile_current(store, resolver, config=config, policy=policy)
        lint_report = lint_current_preview(config, policy, resolver, compiled)
        entry_data["compiled"] = compiled
        entry_data["lint"] = lint_report
        entry_data["preview"] = log_monitor_preview(
            compiled, mode=config["mode"], lint_report=lint_report
        )


async def _refresh_loaded_entry(
    hass: HomeAssistant, entry_id: str, store: TesseraStore
) -> bool:
    """Run central mode handling for a live entry after options changed."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    entry_data = domain_data.get(entry_id)
    if not isinstance(entry_data, dict):
        return False
    entry_data["store"] = store
    from . import _compile_for_mode_safely

    await _compile_for_mode_safely(hass, entry_id, entry_data)
    return True
