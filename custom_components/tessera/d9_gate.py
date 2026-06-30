"""Read-only D9 custom-component gate for future Tessera enforce mode."""

from __future__ import annotations

import ast
import asyncio
import hashlib
import json
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, TypedDict, cast

from .d9_classification import (
    CLASSIFICATIONS,
    D9_VERDICT_ALLOW,
    D9_VERDICT_DENY,
    D9_VERDICT_TIER_2,
    D9_VERDICT_UNKNOWN,
    D9ClassificationEntry,
    D9Verdict,
)
from .schema import D9AckData, TesseraConfigData

SOURCE_ACK = "ack"
SOURCE_CLASSIFICATION = "classification"
SOURCE_DEFAULT = "default"
SOURCE_SURFACE_VETO = "surface_veto"

SURFACE_HTTP = "http_view_or_panel"
SURFACE_COMPILED = "compiled_artifact"
SURFACE_DYNAMIC = "dynamic_or_unparseable_python"
SURFACE_SERVICE = "service"
SURFACE_WEBSOCKET = "websocket"

COMPILED_SURFACE_SUFFIXES = frozenset({".so", ".pyd", ".pyx"})
TEXT_SCAN_SUFFIXES = frozenset({".yaml", ".yml"})
TEXT_SCAN_FILENAMES = frozenset({"manifest.json"})
HTTP_MARKERS = frozenset({"HomeAssistantView", "panel", "register_view"})
SERVICE_MARKERS = frozenset({"async_register"})
WEBSOCKET_MARKERS = frozenset({"async_register_command", "websocket_command"})


class D9ComponentResult(TypedDict):
    """Per-component D9 verdict details."""

    verdict: D9Verdict
    version: str | None
    reason: str
    source: str
    content_hash: str | None


class D9GateResult(TypedDict):
    """D9 gate result consumed by future E3 enforce wiring."""

    by_component: dict[str, D9ComponentResult]
    blocking: list[str]
    enforce_blocked: bool


class _HassConfigLike(Protocol):
    """Tiny subset of ``hass.config`` needed by this read-only gate."""

    def path(self, *parts: str) -> str:
        """Return a path inside Home Assistant's config directory."""
        ...


class _ServicesLike(Protocol):
    """Tiny subset of HA's service registry used for runtime surface checks."""

    def async_services(self) -> Mapping[str, object]:
        """Return registered services by domain."""
        ...


class _HassLike(Protocol):
    """Tiny Home Assistant protocol used by D9."""

    config: _HassConfigLike
    services: _ServicesLike

    def async_add_executor_job(
        self, target: Callable[..., Any], *args: object
    ) -> Awaitable[Any]:
        """Run blocking work off the event loop."""
        ...


@dataclass(frozen=True)
class _DiskComponent:
    """Fresh on-disk custom-component scan result."""

    domain: str
    path: Path
    version: str | None
    content_hash: str
    surfaces: frozenset[str]


async def evaluate_d9_gate(
    hass: _HassLike,
    config: TesseraConfigData,
    *,
    self_domain: str | None = None,
) -> D9GateResult:
    """Evaluate installed custom components for E3 enforce blockers.

    The gate is dormant and read-only: it enumerates custom components, scans
    source markers in an executor, checks runtime service registrations, and
    returns a fail-closed report. It never writes native Home Assistant auth
    state and is intentionally not wired into mode handling yet.

    Args:
        hass: Home Assistant instance or test double.
        config: Validated Tessera config containing optional ``d9_acks``.
        self_domain: Tessera's own integration domain, excluded from evaluation
            so the trusted enforcer never vetoes its own legitimate surfaces.

    Returns:
        A deterministic D9 report. ``enforce_blocked`` is true when any custom
        component remains unknown, needs Tier-2 handling, or is explicitly
        denied.
    """
    root = Path(hass.config.path("custom_components"))
    disk_components = await _run_executor(hass, _scan_custom_components, root)
    loader_components = await _async_get_custom_components(hass)
    runtime_service_domains = _runtime_service_domains(hass)
    acks = config.get("d9_acks", {})

    by_component: dict[str, D9ComponentResult] = {}
    for domain in sorted(set(disk_components) | set(loader_components)):
        if domain == self_domain:
            # Tessera is the trusted enforcer itself; it must not veto its own
            # legitimate panel/service/websocket surfaces (would self-block enforce).
            continue
        disk = disk_components.get(domain)
        integration = loader_components.get(domain)
        version = _component_version(integration, disk)
        content_hash = disk.content_hash if disk is not None else None
        surfaces = set(disk.surfaces if disk is not None else frozenset())
        if domain in runtime_service_domains:
            surfaces.add(SURFACE_SERVICE)

        by_component[domain] = _classify_component(
            domain=domain,
            version=version,
            content_hash=content_hash,
            surfaces=frozenset(surfaces),
            ack=acks.get(domain),
        )

    blocking = [
        domain
        for domain, result in by_component.items()
        if result["verdict"] in {D9_VERDICT_DENY, D9_VERDICT_TIER_2, D9_VERDICT_UNKNOWN}
    ]
    return {
        "by_component": by_component,
        "blocking": blocking,
        "enforce_blocked": bool(blocking),
    }


def compute_component_hash(component_path: Path) -> str:
    """Return Tessera's D9 content hash for one custom component.

    Args:
        component_path: Path to ``custom_components/<domain>``.

    Returns:
        SHA-256 over all stable component files, excluding ``__pycache__``,
        including relative filenames to prevent path-swap collisions.
    """
    digest = hashlib.sha256()
    for file_path in _iter_hash_files(component_path):
        relative = file_path.relative_to(component_path).as_posix()
        digest.update(relative.encode())
        digest.update(b"\0")
        digest.update(file_path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _classify_component(
    *,
    domain: str,
    version: str | None,
    content_hash: str | None,
    surfaces: frozenset[str],
    ack: D9AckData | None,
) -> D9ComponentResult:
    if surfaces:
        return _result(
            D9_VERDICT_UNKNOWN,
            version,
            content_hash,
            SOURCE_SURFACE_VETO,
            f"surface hard-veto: {', '.join(sorted(surfaces))}",
        )

    entry = _matching_classification(domain, version, content_hash)
    if entry is not None:
        if (
            entry.verdict in {D9_VERDICT_ALLOW, D9_VERDICT_TIER_2}
            and entry.evidence_type is None
        ):
            return _result(
                D9_VERDICT_UNKNOWN,
                version,
                content_hash,
                SOURCE_CLASSIFICATION,
                f"classification {entry.verdict} is missing evidence_type",
            )
        return _result(
            entry.verdict,
            version,
            content_hash,
            SOURCE_CLASSIFICATION,
            entry.reason,
        )

    if _ack_matches(ack, version, content_hash):
        return _result(
            D9_VERDICT_ALLOW,
            version,
            content_hash,
            SOURCE_ACK,
            "admin ack matched domain, version, and content hash",
        )

    return _result(
        D9_VERDICT_UNKNOWN,
        version,
        content_hash,
        SOURCE_DEFAULT,
        "no matching classification or ack",
    )


def _result(
    verdict: D9Verdict,
    version: str | None,
    content_hash: str | None,
    source: str,
    reason: str,
) -> D9ComponentResult:
    return {
        "verdict": verdict,
        "version": version,
        "content_hash": content_hash,
        "source": source,
        "reason": reason,
    }


def _matching_classification(
    domain: str, version: str | None, content_hash: str | None
) -> D9ClassificationEntry | None:
    if content_hash is None:
        return None
    for entry in CLASSIFICATIONS.get(domain, ()):
        if entry.content_hash == content_hash and _versions_equal(
            version, entry.version
        ):
            return entry
    return None


def _ack_matches(
    ack: D9AckData | None, version: str | None, content_hash: str | None
) -> bool:
    return (
        ack is not None
        and content_hash is not None
        and ack.get("content_hash") == content_hash
        and _versions_equal(version, ack.get("version"))
    )


def _versions_equal(current: str | None, expected: str | None) -> bool:
    if current is None or expected is None:
        return current is None and expected is None
    try:
        from awesomeversion import AwesomeVersion

        return AwesomeVersion(current) == AwesomeVersion(expected)
    except ModuleNotFoundError:
        # Production HA provides awesomeversion. This fallback keeps HA-free unit
        # tests runnable without silently weakening production behavior.
        return _normalize_version_segments(current) == _normalize_version_segments(
            expected
        )
    except Exception:  # pragma: no cover - awesomeversion-specific parse errors.
        return False


def _normalize_version_segments(version: str) -> tuple[str, ...]:
    segments = version.split(".")
    while segments and segments[-1] == "0":
        segments.pop()
    return tuple(segments)


async def _async_get_custom_components(hass: _HassLike) -> dict[str, object]:
    """Return Home Assistant's cached custom-component integrations."""
    from homeassistant import loader

    return cast(
        dict[str, object], await loader.async_get_custom_components(cast(Any, hass))
    )


async def _run_executor(
    hass: _HassLike, target: Callable[..., Any], *args: object
) -> Any:
    if hasattr(hass, "async_add_executor_job"):
        return await hass.async_add_executor_job(target, *args)
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, target, *args)


def _scan_custom_components(root: Path) -> dict[str, _DiskComponent]:
    if not root.is_dir():
        return {}

    components: dict[str, _DiskComponent] = {}
    for component_path in sorted(path for path in root.iterdir() if path.is_dir()):
        domain = component_path.name
        manifest = _load_manifest(component_path)
        version = manifest.get("version") if manifest is not None else None
        components[domain] = _DiskComponent(
            domain=domain,
            path=component_path,
            version=version if isinstance(version, str) else None,
            content_hash=compute_component_hash(component_path),
            surfaces=_detect_static_surfaces(component_path),
        )
    return components


def _load_manifest(component_path: Path) -> dict[str, object] | None:
    manifest_path = component_path / "manifest.json"
    if not manifest_path.is_file():
        return None
    try:
        data = json.loads(manifest_path.read_text())
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _detect_static_surfaces(component_path: Path) -> frozenset[str]:
    """Return static fail-closed D9 surface signals for one component.

    Python files are parsed with AST so aliases and simple string-based
    ``getattr`` markers are visible. HTTP/WS still have no HA runtime registry
    backstop here; dynamic registration built via ``exec``/``chr``-style string
    construction can evade static analysis. For executable Python, a table ALLOW
    therefore needs ``runtime_verified_allow`` evidence rather than relying on an
    empty static scan alone.
    """
    surfaces: set[str] = set()
    for file_path in _iter_hash_files(component_path):
        if _is_compiled_surface(file_path):
            surfaces.add(SURFACE_COMPILED)
            continue
        try:
            text = file_path.read_text(errors="ignore")
        except OSError:
            continue
        if file_path.suffix == ".py":
            surfaces.update(_detect_python_surfaces(text))
        elif (
            file_path.suffix in TEXT_SCAN_SUFFIXES
            or file_path.name in TEXT_SCAN_FILENAMES
        ):
            surfaces.update(_detect_text_surfaces(text))
    return frozenset(surfaces)


def _detect_python_surfaces(text: str) -> set[str]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return {SURFACE_DYNAMIC}

    markers: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            markers.add(node.attr)
        elif isinstance(node, ast.Name):
            markers.add(node.id)
        elif isinstance(node, ast.alias):
            markers.add(node.name.rsplit(".", 1)[-1])
            if node.asname is not None:
                markers.add(node.asname)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            markers.add(node.value)
    return _markers_to_surfaces(markers)


def _detect_text_surfaces(text: str) -> set[str]:
    return _markers_to_surfaces(
        marker
        for marker in HTTP_MARKERS | SERVICE_MARKERS | WEBSOCKET_MARKERS
        if marker in text
    )


def _markers_to_surfaces(markers: Iterable[str]) -> set[str]:
    marker_set = set(markers)
    surfaces: set[str] = set()
    if marker_set & SERVICE_MARKERS:
        surfaces.add(SURFACE_SERVICE)
    if marker_set & HTTP_MARKERS:
        surfaces.add(SURFACE_HTTP)
    if marker_set & WEBSOCKET_MARKERS:
        surfaces.add(SURFACE_WEBSOCKET)
    return surfaces


def _is_compiled_surface(file_path: Path) -> bool:
    if file_path.suffix in COMPILED_SURFACE_SUFFIXES:
        return True
    return file_path.suffix == ".pyc" and "__pycache__" not in file_path.parts


def _runtime_service_domains(hass: _HassLike) -> frozenset[str]:
    try:
        services = hass.services.async_services()
    except AttributeError:
        return frozenset()
    return frozenset(domain for domain, handlers in services.items() if handlers)


def _component_version(
    integration: object | None, disk: _DiskComponent | None
) -> str | None:
    if integration is not None:
        version = getattr(integration, "version", None)
        if version is not None:
            return str(version)
    return disk.version if disk is not None else None


def _iter_hash_files(component_path: Path) -> list[Path]:
    return sorted(
        path
        for path in component_path.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.relative_to(component_path).parts
    )
