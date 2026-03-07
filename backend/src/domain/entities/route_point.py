from dataclasses import dataclass


@dataclass(frozen=True)
class RoutePoint:
    latitude: float
    longitude: float
