from dataclasses import dataclass, field

from src.domain.entities.point_of_interest import PointOfInterest
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
    stable_route_id: str = ""
    trail_ratio: float = 0.0
    road_ratio: float = 0.0
    nature_score: float = 0.0
    quiet_score: float = 0.0
    hiking_suitability_score: float = 0.0
    difficulty: str = "moderee"
    tags: list[str] = field(default_factory=list)
    points: list[RoutePoint] = field(default_factory=list)
    pois: list[PointOfInterest] = field(default_factory=list)
    poi_score: float = 0.0
    poi_quantity_score: float = 0.0
    poi_diversity_score: float = 0.0
    poi_highlight_count: int = 0
    highlighted_poi_labels: list[str] = field(default_factory=list)
    poi_highlights: list[str] = field(default_factory=list)
    score_breakdown: dict[str, float] = field(default_factory=dict)
    explanation: str = ""
    explanation_reasons: list[str] = field(default_factory=list)
    description: str = ""
    poi_on_route_count: int = 0
    poi_near_route_count: int = 0
    context_score_delta: float = 0.0
    context_warnings: list[str] = field(default_factory=list)
    seen_before: bool = False
