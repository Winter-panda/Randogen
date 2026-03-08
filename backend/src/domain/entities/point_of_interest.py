from dataclasses import dataclass, field


@dataclass
class PointOfInterest:
    id: str
    name: str
    category: str
    sub_category: str | None
    latitude: float
    longitude: float
    distance_to_route_m: float
    distance_from_start_m: float | None
    score: float = 0.0
    tags: list[str] = field(default_factory=list)
