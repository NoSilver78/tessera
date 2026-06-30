"""Curated D9 custom-component classifications for Tessera.

The bundled table is intentionally empty in v1. Runtime/product deployments can
only get an ALLOW from an entry that pins the domain, version, content hash, and
an explicit evidence type.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

D9_VERDICT_ALLOW: Final = "ALLOW"
D9_VERDICT_DENY: Final = "DENY"
D9_VERDICT_TIER_2: Final = "TIER-2"
D9_VERDICT_UNKNOWN: Final = "UNKNOWN_BLOCK_ENFORCE"

D9Verdict = Literal["ALLOW", "DENY", "TIER-2", "UNKNOWN_BLOCK_ENFORCE"]
D9EvidenceType = Literal[
    "runtime_verified_allow", "no_surface_verified", "tier2_accepted"
]


@dataclass(frozen=True)
class D9ClassificationEntry:
    """One pinned D9 classification row for a custom component."""

    version: str | None
    content_hash: str
    verdict: D9Verdict
    reason: str
    evidence_type: D9EvidenceType | None = None


CLASSIFICATIONS: Final[dict[str, tuple[D9ClassificationEntry, ...]]] = {}
