from dataclasses import dataclass


@dataclass(frozen=True)
class UserSearch:
    latitude: float
    longitude: float
    target_distance_km: float
    route_count: int
    hike_style: str = "equilibree"