from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UserSearch:
    latitude: float
    longitude: float
    target_distance_km: float
    route_count: int
    ambiance: str | None = None
    terrain: str | None = None
    effort: str | None = None