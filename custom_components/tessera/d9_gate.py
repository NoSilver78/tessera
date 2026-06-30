"""D9 custom-component gate for Tessera enforce mode (auth-scoped veto).

The gate classifies installed custom components before enforce activates. Only
components that can mutate the managed Home Assistant auth state, or that cannot
be statically analysed (compiled/dynamic), hard-veto enforce; an explicit admin
ack or a curated classification overrides the veto. Generic UI surfaces and
unknown components without auth-relevant surfaces are trusted by default.
"""

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
SURFACE_AUTH = "auth_store_mutation"

COMPILED_SURFACE_SUFFIXES = frozenset({".so", ".pyd", ".pyx"})
TEXT_SCAN_SUFFIXES = frozenset({".yaml", ".yml"})
TEXT_SCAN_FILENAMES = frozenset({"manifest.json"})
HTTP_MARKERS = frozenset({"HomeAssistantView", "panel", "register_view"})
SERVICE_MARKERS = frozenset({"async_register"})
WEBSOCKET_MARKERS = frozenset({"async_register_command", "websocket_command"})
# Markers that signal a component can MUTATE the Home Assistant auth state
# Tessera manages (users, group membership, credentials, tokens) — the real
# conflict/interference surface for native enforcement. These are exact public
# AuthManager / auth-provider names (introspected against the installed HA, so
# low false-positive). A static token scan cannot catch deliberate obfuscation;
# that is out of scope per the threat model (a malicious component already runs
# with full privileges), so the veto targets honest conflicting components.
AUTH_MUTATION_MARKERS = frozenset(
    {
        # User + group-membership lifecycle (AuthManager).
        "async_create_user",
        "async_create_system_user",
        "async_get_or_create_user",
        "async_update_user",
        "async_remove_user",
        "async_activate_user",
        "async_deactivate_user",
        # Credentials, MFA, and refresh/access tokens.
        "async_link_user",
        "async_remove_credentials",
        "async_update_user_credentials_data",
        "async_create_refresh_token",
        "async_remove_refresh_token",
        "async_set_expiry",
        "async_enable_user_mfa",
        "async_disable_user_mfa",
        # Custom auth-provider provisioning (UserMeta carries the assigned group).
        "async_user_meta_for_credentials",
        "UserMeta",
    }
)

# Attribute names whose direct assignment (``user.groups = [...]``) reassigns
# the membership Tessera compiles into PolicyPermissions. Detected only in a
# Store (write) context, so reads like ``for g in user.groups`` are not flagged.
AUTH_WRITE_ATTRS = frozenset({"groups"})

# D9 v2 — auth-scoped veto. Only these surfaces hard-veto enforce: a component
# that can mutate the managed auth state, or that cannot be statically analysed
# at all (compiled/dynamic). Generic HTTP/service/websocket surfaces do not
# threaten native enforcement and no longer block on their own; an explicit
# admin ack (or a curated classification with evidence) overrides the veto.
VETO_SURFACES = frozenset({SURFACE_AUTH, SURFACE_COMPILED, SURFACE_DYNAMIC})


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


class D9AckTarget(TypedDict):
    """Version/hash tuple an admin ack must pin."""

    version: str | None
    content_hash: str


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

    The gate is read-only: it enumerates custom components, scans source markers
    in an executor, checks runtime service registrations, and returns a report
    consumed by ``compute_enforce_plan``. It never writes native Home Assistant
    auth state itself. Only auth-mutating or un-analysable (compiled/dynamic)
    surfaces hard-veto; an explicit ack or curated classification overrides the
    veto, and components without such surfaces are trusted by default.

    Args:
        hass: Home Assistant instance or test double.
        config: Validated Tessera config containing optional ``d9_acks``.
        self_domain: Tessera's own integration domain, excluded from evaluation
            so the trusted enforcer never vetoes its own legitimate surfaces.

    Returns:
        A deterministic D9 report. ``enforce_blocked`` is true when any custom
        component is blocked: an un-acked auth-relevant/opaque surface, a Tier-2
        row, an explicit deny, or an evidence-inconsistent classification.
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


async def compute_component_ack_target(
    hass: _HassLike, domain: str
) -> D9AckTarget | None:
    """Return the version/hash tuple the D9 gate checks for ``domain``.

    The ack writer must pin the exact values the gate will later compare
    against. This intentionally reuses the gate's own disk scan, loader lookup,
    version resolution, and content-hash primitives. ``None`` means the
    component is not present on disk and therefore cannot be acknowledged.
    """
    root = Path(hass.config.path("custom_components"))
    disk_components = await _run_executor(hass, _scan_custom_components, root)
    disk = disk_components.get(domain)
    if disk is None:
        return None

    loader_components = await _async_get_custom_components(hass)
    integration = loader_components.get(domain)
    return {
        "version": _component_version(integration, disk),
        "content_hash": disk.content_hash,
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
    veto_surfaces = surfaces & VETO_SURFACES
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
        if (
            entry.verdict == D9_VERDICT_ALLOW
            and entry.evidence_type == "no_surface_verified"
            and veto_surfaces
        ):
            # Anti-forgery: a "no_surface_verified" anchor claims the component
            # has no surface, so a detected veto-surface contradicts it -> reject.
            # A "runtime_verified_allow" anchor instead asserts the runtime
            # behavior was verified *with* its surfaces, so it may carry them;
            # "tier2_accepted" returns TIER-2 and blocks regardless. All three
            # are hash-pinned, so a content change drops the anchor entirely.
            return _result(
                D9_VERDICT_UNKNOWN,
                version,
                content_hash,
                SOURCE_SURFACE_VETO,
                "classification asserts no_surface_verified but detected "
                f"{', '.join(sorted(veto_surfaces))}",
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

    if veto_surfaces:
        return _result(
            D9_VERDICT_UNKNOWN,
            version,
            content_hash,
            SOURCE_SURFACE_VETO,
            f"auth-relevant or opaque surface veto: {', '.join(sorted(veto_surfaces))}",
        )

    return _result(
        D9_VERDICT_ALLOW,
        version,
        content_hash,
        SOURCE_DEFAULT,
        "no auth-relevant surface and no blocking classification or ack",
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
    construction can evade static analysis. Curators SHOULD therefore prefer
    ``runtime_verified_allow`` over ``no_surface_verified`` for components with
    executable code, since an empty static scan alone can be obfuscated. The
    gate itself only enforces that a *detected* veto-surface contradicts a
    ``no_surface_verified`` anchor (see ``_classify_component``).
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
    surfaces: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            markers.add(node.attr)
            if isinstance(node.ctx, ast.Store) and node.attr in AUTH_WRITE_ATTRS:
                # Direct membership reassignment, e.g. ``user.groups = [...]``.
                surfaces.add(SURFACE_AUTH)
        elif isinstance(node, ast.Name):
            markers.add(node.id)
        elif isinstance(node, ast.alias):
            markers.add(node.name.rsplit(".", 1)[-1])
            if node.asname is not None:
                markers.add(node.asname)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            markers.add(node.value)
    surfaces |= _markers_to_surfaces(markers)
    return surfaces


def _detect_text_surfaces(text: str) -> set[str]:
    return _markers_to_surfaces(
        marker
        for marker in (
            HTTP_MARKERS | SERVICE_MARKERS | WEBSOCKET_MARKERS | AUTH_MUTATION_MARKERS
        )
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
    if marker_set & AUTH_MUTATION_MARKERS:
        surfaces.add(SURFACE_AUTH)
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
