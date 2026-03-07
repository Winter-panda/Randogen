from src.domain.entities.route_candidate import RouteCandidate
from src.domain.entities.route_point import RoutePoint
from src.domain.entities.user_search import UserSearch


class RouteGenerationService:
    def generate_mock_routes(self, search: UserSearch) -> list[RouteCandidate]:
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
