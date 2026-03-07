from __future__ import annotations

import math

from src.domain.entities.route_candidate import RouteCandidate
from src.domain.entities.route_point import RoutePoint
from src.domain.entities.user_search import UserSearch
from src.infrastructure.config.settings import settings
from src.infrastructure.routing.ors_client import OrsClient, OrsClientError
from src.infrastructure.routing.routing_provider import RoutingProvider


class RouteGenerationService:
    def __init__(self) -> None:
        ors_client = OrsClient(
            api_key=settings.ors_api_key,
            base_url=settings.ors_base_url,
            profile=settings.ors_profile,
            timeout_s=settings.ors_request_timeout_s,
        )
        self._routing_provider = RoutingProvider(ors_client)

    def generate_routes(self, search: UserSearch) -> list[RouteCandidate]:
        if settings.enable_real_routing and self._routing_provider.is_available():
            real_routes = self._generate_real_routes(search)
            if len(real_routes) > 0:
                return real_routes

        return self._generate_mock_routes(search)

    def _generate_real_routes(self, search: UserSearch) -> list[RouteCandidate]:
        start = RoutePoint(latitude=search.latitude, longitude=search.longitude)

        candidates: list[RouteCandidate] = []
        waypoint_sets = self._build_candidate_waypoint_sets(search.target_distance_km)

        for index, waypoint_spec in enumerate(waypoint_sets[: search.route_count], start=1):
            waypoint_a = self._offset_point(
                start,
                bearing_deg=waypoint_spec[0],
                distance_m=waypoint_spec[1],
            )
            waypoint_b = self._offset_point(
                start,
                bearing_deg=waypoint_spec[2],
                distance_m=waypoint_spec[3],
            )

            try:
                routing_result = self._routing_provider.build_loop_route(
                    start=start,
                    waypoint_a=waypoint_a,
                    waypoint_b=waypoint_b,
                )
            except OrsClientError:
                continue

            route = RouteCandidate(
                id=f"route-{index}",
                name=f"Parcours {index}",
                distance_km=round(routing_result.distance_m / 1000, 2),
                estimated_duration_min=max(1, int(round(routing_result.duration_s / 60))),
                estimated_elevation_gain_m=0,
                score=self._compute_score(
                    target_distance_km=search.target_distance_km,
                    actual_distance_km=routing_result.distance_m / 1000,
                ),
                route_type="loop",
                source=f"openrouteservice:{settings.ors_profile}",
                points=routing_result.points,
            )
            candidates.append(route)

        return candidates

    def _build_candidate_waypoint_sets(
        self,
        target_distance_km: float,
    ) -> list[tuple[float, float, float, float]]:
        base_radius_m = max(400.0, target_distance_km * 250.0)

        return [
            (20.0, base_radius_m, 145.0, base_radius_m * 1.05),
            (60.0, base_radius_m * 0.95, 210.0, base_radius_m * 1.08),
            (110.0, base_radius_m * 1.02, 300.0, base_radius_m * 0.92),
            (160.0, base_radius_m * 0.88, 330.0, base_radius_m * 1.12),
            (250.0, base_radius_m * 1.10, 40.0, base_radius_m * 0.90),
        ]

    def _offset_point(
        self,
        origin: RoutePoint,
        bearing_deg: float,
        distance_m: float,
    ) -> RoutePoint:
        earth_radius_m = 6_371_000.0
        bearing_rad = math.radians(bearing_deg)

        lat1 = math.radians(origin.latitude)
        lon1 = math.radians(origin.longitude)
        angular_distance = distance_m / earth_radius_m

        lat2 = math.asin(
            math.sin(lat1) * math.cos(angular_distance)
            + math.cos(lat1) * math.sin(angular_distance) * math.cos(bearing_rad)
        )

        lon2 = lon1 + math.atan2(
            math.sin(bearing_rad) * math.sin(angular_distance) * math.cos(lat1),
            math.cos(angular_distance) - math.sin(lat1) * math.sin(lat2),
        )

        return RoutePoint(
            latitude=round(math.degrees(lat2), 6),
            longitude=round(math.degrees(lon2), 6),
        )

    def _compute_score(
        self,
        target_distance_km: float,
        actual_distance_km: float,
    ) -> float:
        if target_distance_km <= 0:
            return 0.5

        error_ratio = abs(actual_distance_km - target_distance_km) / target_distance_km
        score = max(0.1, 1.0 - error_ratio)
        return round(score, 2)

    def _generate_mock_routes(self, search: UserSearch) -> list[RouteCandidate]:
        routes: list[RouteCandidate] = []

        for index in range(search.route_count):
            offset = 0.005 * (index + 1)

            points = [
                RoutePoint(latitude=search.latitude, longitude=search.longitude),
                RoutePoint(latitude=search.latitude + offset, longitude=search.longitude),
                RoutePoint(
                    latitude=search.latitude + offset,
                    longitude=search.longitude + offset,
                ),
                RoutePoint(latitude=search.latitude, longitude=search.longitude + offset),
                RoutePoint(latitude=search.latitude, longitude=search.longitude),
            ]

            route = RouteCandidate(
                id=f"route-{index + 1}",
                name=f"Parcours {index + 1}",
                distance_km=round(search.target_distance_km * (0.95 + index * 0.03), 2),
                estimated_duration_min=int(search.target_distance_km * 12 + index * 5),
                estimated_elevation_gain_m=30 + (index * 25),
                score=round(0.72 + (index * 0.08), 2),
                route_type="loop",
                source="mock-generator",
                points=points,
            )
            routes.append(route)

        return routes