"""Tests for Tessera storage roundtrips."""

from __future__ import annotations

from typing import Any, ClassVar

import pytest
from custom_components.tessera.const import CONFIG_STORAGE_KEY, POLICY_STORAGE_KEY
from custom_components.tessera.schema import default_config_data, default_policy_data
from custom_components.tessera.store import TesseraStore


class MemoryStore:
    """In-memory replacement for Home Assistant's Store helper."""

    buckets: ClassVar[dict[str, dict[str, Any]]] = {}

    def __init__(self, hass: object, version: int, key: str) -> None:
        """Create a memory-backed store bucket."""
        self.key = key

    async def async_load(self) -> dict[str, Any] | None:
        """Load the stored payload."""
        return self.buckets.get(self.key)

    async def async_save(self, data: dict[str, Any]) -> None:
        """Save the payload."""
        self.buckets[self.key] = data


@pytest.fixture(autouse=True)
def clear_memory_store() -> None:
    """Reset in-memory storage between tests."""
    MemoryStore.buckets = {}


@pytest.mark.asyncio
async def test_store_returns_defaults_when_empty() -> None:
    """Store loads schema-valid defaults when HA storage has no payload."""
    store = TesseraStore(hass=object(), store_factory=MemoryStore)

    assert await store.async_load_config() == default_config_data()
    assert await store.async_load_policy() == default_policy_data()


@pytest.mark.asyncio
async def test_store_roundtrips_config_and_policy() -> None:
    """Store validates, saves, and loads config and policy payloads."""
    store = TesseraStore(hass=object(), store_factory=MemoryStore)
    config = default_config_data()
    config["mode"] = "monitor"
    config["roles"] = {"viewer": {"name": "Viewer"}}
    config["membership"] = {
        "by_user": {"user-1": ["viewer"]},
        "by_group": {"authentik:tessera-viewer": ["viewer"]},
    }
    policy = default_policy_data()
    policy["area_grants"] = {"living_room": {"viewer": {"read": True}}}

    await store.async_save_config(config)
    await store.async_save_policy(policy)

    assert MemoryStore.buckets[CONFIG_STORAGE_KEY] == config
    assert MemoryStore.buckets[POLICY_STORAGE_KEY] == policy
    assert await store.async_load_config() == config
    assert await store.async_load_policy() == policy


@pytest.mark.asyncio
async def test_store_rejects_invalid_empty_payload() -> None:
    """Store validates existing payloads instead of replacing them."""
    MemoryStore.buckets = {CONFIG_STORAGE_KEY: {}}
    store = TesseraStore(hass=object(), store_factory=MemoryStore)

    with pytest.raises(ValueError):
        await store.async_load_config()
