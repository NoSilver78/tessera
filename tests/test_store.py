"""Tests for Tessera storage roundtrips."""

from __future__ import annotations

import asyncio
from typing import Any

from custom_components.tessera.const import CONFIG_STORAGE_KEY, POLICY_STORAGE_KEY
from custom_components.tessera.schema import default_config_data, default_policy_data
from custom_components.tessera.store import TesseraStore


class MemoryStore:
    """In-memory replacement for Home Assistant's Store helper."""

    buckets: dict[str, dict[str, Any]] = {}

    def __init__(self, hass: object, version: int, key: str) -> None:
        """Create a memory-backed store bucket."""
        self.key = key

    async def async_load(self) -> dict[str, Any] | None:
        """Load the stored payload."""
        return self.buckets.get(self.key)

    async def async_save(self, data: dict[str, Any]) -> None:
        """Save the payload."""
        self.buckets[self.key] = data


def test_store_returns_defaults_when_empty() -> None:
    """Store loads schema-valid defaults when HA storage has no payload."""
    async def run() -> None:
        MemoryStore.buckets = {}
        store = TesseraStore(hass=object(), store_factory=MemoryStore)

        assert await store.async_load_config() == default_config_data()
        assert await store.async_load_policy() == default_policy_data()

    asyncio.run(run())


def test_store_roundtrips_config_and_policy() -> None:
    """Store validates, saves, and loads config and policy payloads."""
    async def run() -> None:
        MemoryStore.buckets = {}
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

    asyncio.run(run())


def test_store_rejects_invalid_empty_payload() -> None:
    """Store validates existing payloads instead of replacing them."""

    async def run() -> None:
        MemoryStore.buckets = {CONFIG_STORAGE_KEY: {}}
        store = TesseraStore(hass=object(), store_factory=MemoryStore)

        try:
            await store.async_load_config()
        except ValueError:
            return
        raise AssertionError("empty config payload should be rejected")

    asyncio.run(run())
