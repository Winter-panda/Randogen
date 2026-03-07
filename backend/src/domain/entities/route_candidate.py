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
    trail_ratio: float = 0.0
    road_ratio: float = 0.0
    nature_score: float = 0.0
    quiet_score: float = 0.0
    hiking_suitability_score: float = 0.0
    points: list[RoutePoint] = field(default_factory=list)