"""Async storage adapter for Tessera's phase-1 data."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, cast

from .const import CONFIG_STORAGE_KEY, POLICY_STORAGE_KEY, STORAGE_VERSION
from .schema import (
    TesseraConfigData,
    TesseraPolicyData,
    default_config_data,
    default_policy_data,
    validate_config_data,
    validate_policy_data,
)


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

    def __init__(self, hass: Any, store_factory: StoreFactory | None = None) -> None:
        """Initialize the Tessera storage adapter.

        Args:
            hass: Home Assistant instance passed to the HA storage helper.
            store_factory: Optional factory used by tests to avoid importing HA.
        """
        factory = store_factory or _homeassistant_store_factory
        self._config_store = factory(hass, STORAGE_VERSION, CONFIG_STORAGE_KEY)
        self._policy_store = factory(hass, STORAGE_VERSION, POLICY_STORAGE_KEY)

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
        await self._config_store.async_save(validate_config_data(data))

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
        await self._policy_store.async_save(validate_policy_data(data))


def _homeassistant_store_factory(hass: Any, version: int, key: str) -> StoreLike:
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
