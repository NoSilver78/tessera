"""Async storage adapter for Tessera's phase-1 data."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Protocol, cast

from .const import (
    CONFIG_STORAGE_KEY,
    POLICY_STORAGE_KEY,
    STATE_STORAGE_KEY,
    STORAGE_VERSION,
)
from .schema import (
    TesseraConfigData,
    TesseraPolicyData,
    default_config_data,
    default_policy_data,
    validate_config_data,
    validate_policy_data,
)
from .state import (
    TesseraStateData,
    TesseraStateError,
    default_state_data,
    snapshot_to_state_data,
    validate_state_data,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .auth_adapter import AuthRecoverySnapshot


class StoreLike(Protocol):
    """Small subset of Home Assistant's storage helper used by Tessera."""

    async def async_load(self) -> dict[str, Any] | None:
        """Load a payload from storage."""
        ...

    async def async_save(self, data: dict[str, Any]) -> None:
        """Persist a payload to storage."""
        ...


StoreFactory = Callable[[Any, int, str], StoreLike]


class TesseraStore:
    """Load and save Tessera's config and policy stores via HA storage."""

    def __init__(
        self, hass: HomeAssistant, store_factory: StoreFactory | None = None
    ) -> None:
        """Initialize the Tessera storage adapter.

        Args:
            hass: Home Assistant instance passed to the HA storage helper.
            store_factory: Optional factory used by tests to avoid importing HA.
        """
        factory = store_factory or _homeassistant_store_factory
        self._config_store = factory(hass, STORAGE_VERSION, CONFIG_STORAGE_KEY)
        self._policy_store = factory(hass, STORAGE_VERSION, POLICY_STORAGE_KEY)
        self._state_store = factory(hass, STORAGE_VERSION, STATE_STORAGE_KEY)
        self._state_lock = asyncio.Lock()

    async def async_load_config(self) -> TesseraConfigData:
        """Load Tessera configuration, returning defaults when absent.

        Returns:
            A schema-valid configuration payload.
        """
        data = await self._config_store.async_load()
        return validate_config_data(default_config_data() if data is None else data)

    async def async_save_config(self, data: TesseraConfigData) -> None:
        """Validate and save Tessera configuration.

        Args:
            data: Configuration payload to persist.
        """
        await self._config_store.async_save(
            cast(dict[str, Any], validate_config_data(data))
        )

    async def async_load_policy(self) -> TesseraPolicyData:
        """Load Tessera policy, returning defaults when absent.

        Returns:
            A schema-valid policy payload.
        """
        data = await self._policy_store.async_load()
        return validate_policy_data(default_policy_data() if data is None else data)

    async def async_save_policy(self, data: TesseraPolicyData) -> None:
        """Validate and save Tessera policy.

        Args:
            data: Policy payload to persist.
        """
        await self._policy_store.async_save(
            cast(dict[str, Any], validate_policy_data(data))
        )

    async def async_load_state(self) -> TesseraStateData:
        """Load secret-free recovery state, returning defaults when absent."""
        data = await self._state_store.async_load()
        return validate_state_data(
            cast(dict[str, Any], default_state_data()) if data is None else data
        )

    async def async_save_state(self, data: TesseraStateData) -> None:
        """Validate and save secret-free recovery state."""
        await self._state_store.async_save(
            cast(dict[str, Any], validate_state_data(cast(dict[str, Any], data)))
        )

    async def async_set_pre_install_snapshot(
        self, snapshot: AuthRecoverySnapshot
    ) -> TesseraStateData:
        """Persist the immutable pre-install snapshot exactly once."""
        async with self._state_lock:
            state = await self.async_load_state()
            if state["pre_install_snapshot"] is not None:
                raise TesseraStateError("pre_install_snapshot is immutable")
            state["pre_install_snapshot"] = snapshot_to_state_data(snapshot)
            await self.async_save_state(state)
            return state

    async def async_mark_apply_in_progress(
        self, snapshot: AuthRecoverySnapshot
    ) -> TesseraStateData:
        """Open the two-phase apply journal, setting the snapshot if absent."""
        async with self._state_lock:
            state = await self.async_load_state()
            if state["pre_install_snapshot"] is None:
                state["pre_install_snapshot"] = snapshot_to_state_data(snapshot)
            state["apply_in_progress"] = True
            await self.async_save_state(state)
            return state

    async def async_clear_apply_in_progress(self) -> TesseraStateData:
        """Clear the two-phase apply journal after a successful apply."""
        async with self._state_lock:
            state = await self.async_load_state()
            state["apply_in_progress"] = False
            await self.async_save_state(state)
            return state


def _homeassistant_store_factory(
    hass: HomeAssistant, version: int, key: str
) -> StoreLike:
    """Create a Home Assistant storage helper lazily.

    Args:
        hass: Home Assistant instance.
        version: Storage schema version.
        key: Storage key under ``.storage``.

    Returns:
        A Home Assistant ``Store`` instance.
    """
    from homeassistant.helpers.storage import Store

    return cast(StoreLike, Store(hass, version, key))
