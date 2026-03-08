from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UserSearch:
    user_id: str
    latitude: float
    longitude: float
    target_distance_km: float
    route_count: int
    ambiance: str | None = None
    terrain: str | None = None
    effort: str | None = None
    prioritize_nature: bool = False
    prioritize_viewpoints: bool = False
    prioritize_calm: bool = False
    avoid_urban: bool = False
    avoid_roads: bool = False
    avoid_steep: bool = False
    avoid_touristic: bool = False
    adapt_to_weather: bool = True
    difficulty_pref: str | None = None
