from dataclasses import dataclass, field

from src.domain.entities.route_point import RoutePoint


@dataclass
class RouteCandidate:
    id: str
    name: str
    distance_km: float
    estimated_duration_min: int
    estimated_elevation_gain_m: int
    score: float
    route_type: str
    source: str
    points: list[RoutePoint] = field(default_factory=list)
