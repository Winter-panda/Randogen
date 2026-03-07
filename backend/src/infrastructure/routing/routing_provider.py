from __future__ import annotations

from dataclasses import dataclass

from src.domain.entities.route_point import RoutePoint
from src.infrastructure.routing.ors_client import OrsClient, OrsClientError


@dataclass(frozen=True)
class RoutingResult:
    points: list[RoutePoint]
    distance_m: float
    duration_s: float


class RoutingProvider:
    def __init__(self, ors_client: OrsClient) -> None:
        self._ors_client = ors_client

    def is_available(self) -> bool:
        return self._ors_client.is_configured()

    def build_loop_route(
        self,
        start: RoutePoint,
        waypoint_a: RoutePoint,
        waypoint_b: RoutePoint,
    ) -> RoutingResult:
        ors_result = self._ors_client.get_directions_geojson(
            coordinates_lon_lat=[
                [start.longitude, start.latitude],
                [waypoint_a.longitude, waypoint_a.latitude],
                [waypoint_b.longitude, waypoint_b.latitude],
                [start.longitude, start.latitude],
            ]
        )

        return RoutingResult(
            points=ors_result.points,
            distance_m=ors_result.distance_m,
            duration_s=ors_result.duration_s,
        )


__all__ = ["RoutingProvider", "RoutingResult", "OrsClientError"]