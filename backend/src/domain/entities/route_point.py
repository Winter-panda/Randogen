from dataclasses import dataclass


@dataclass(frozen=True)
class RoutePoint:
    latitude: float
    longitude: float
    elevation_m: float = 0.0
