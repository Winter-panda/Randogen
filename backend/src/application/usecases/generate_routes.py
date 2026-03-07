from src.application.dto.generate_route_request import GenerateRouteRequest
from src.application.dto.generate_route_response import (
    GenerateRouteResponse,
    RouteCandidateResponse,
    RoutePointResponse,
)
from src.application.services.route_generation_service import RouteGenerationService
from src.domain.entities.user_search import UserSearch


class GenerateRoutesUseCase:
    def __init__(self) -> None:
        self._route_generation_service = RouteGenerationService()

    def execute(self, request: GenerateRouteRequest) -> GenerateRouteResponse:
        search = UserSearch(
            latitude=request.latitude,
            longitude=request.longitude,
            target_distance_km=request.target_distance_km,
            route_count=request.route_count,
            hike_style=request.hike_style,
        )

        candidates = self._route_generation_service.generate_routes(search)

        routes = [
            RouteCandidateResponse(
                id=candidate.id,
                name=candidate.name,
                distance_km=candidate.distance_km,
                estimated_duration_min=candidate.estimated_duration_min,
                estimated_elevation_gain_m=candidate.estimated_elevation_gain_m,
                score=candidate.score,
                route_type=candidate.route_type,
                source=candidate.source,
                trail_ratio=candidate.trail_ratio,
                road_ratio=candidate.road_ratio,
                nature_score=candidate.nature_score,
                quiet_score=candidate.quiet_score,
                hiking_suitability_score=candidate.hiking_suitability_score,
                points=[
                    RoutePointResponse(
                        latitude=point.latitude,
                        longitude=point.longitude,
                    )
                    for point in candidate.points
                ],
            )
            for candidate in candidates
        ]

        return GenerateRouteResponse(routes=routes)