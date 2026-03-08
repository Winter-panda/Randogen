from src.application.dto.generate_route_request import GenerateRouteRequest
from src.application.dto.generate_route_response import (
    GenerateRouteResponse,
    PoiResponse,
    RouteCandidateResponse,
    RoutePointResponse,
)
from src.application.services.route_generation_service import RouteGenerationService
from src.application.services.user_memory_service import UserMemoryService
from src.domain.entities.user_search import UserSearch


class GenerateRoutesUseCase:
    def __init__(self) -> None:
        self._route_generation_service = RouteGenerationService()
        self._user_memory_service = UserMemoryService()

    def execute(self, request: GenerateRouteRequest) -> GenerateRouteResponse:
        search = UserSearch(
            user_id=request.user_id,
            latitude=request.latitude,
            longitude=request.longitude,
            target_distance_km=request.target_distance_km,
            route_count=request.route_count,
            ambiance=request.ambiance,
            terrain=request.terrain,
            effort=request.effort,
            biome_preference=request.biome_preference,
            prioritize_nature=request.prioritize_nature,
            prioritize_viewpoints=request.prioritize_viewpoints,
            prioritize_calm=request.prioritize_calm,
            avoid_urban=request.avoid_urban,
            avoid_roads=request.avoid_roads,
            avoid_steep=request.avoid_steep,
            avoid_touristic=request.avoid_touristic,
            adapt_to_weather=request.adapt_to_weather,
            difficulty_pref=request.difficulty_pref,
        )

        candidates = self._route_generation_service.generate_routes(search)
        self._user_memory_service.record_generation(
            user_id=search.user_id,
            search=search,
            routes=candidates,
        )
        diagnostics = self._route_generation_service.get_last_generation_diagnostics()

        routes = [
            RouteCandidateResponse(
                id=candidate.id,
                stable_route_id=candidate.stable_route_id,
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
                difficulty=candidate.difficulty,
                tags=candidate.tags,
                points=[
                    RoutePointResponse(
                        latitude=point.latitude,
                        longitude=point.longitude,
                        elevation_m=point.elevation_m,
                    )
                    for point in candidate.points
                ],
                pois=[
                    PoiResponse(
                        id=poi.id,
                        name=poi.name,
                        category=poi.category,
                        sub_category=poi.sub_category,
                        latitude=poi.latitude,
                        longitude=poi.longitude,
                        distance_to_route_m=poi.distance_to_route_m,
                        distance_from_start_m=poi.distance_from_start_m,
                        score=poi.score,
                        tags=poi.tags,
                    )
                    for poi in candidate.pois
                ],
                poi_score=candidate.poi_score,
                poi_quantity_score=candidate.poi_quantity_score,
                poi_diversity_score=candidate.poi_diversity_score,
                poi_highlight_count=candidate.poi_highlight_count,
                highlighted_poi_labels=candidate.highlighted_poi_labels,
                poi_highlights=candidate.poi_highlights,
                score_breakdown=candidate.score_breakdown,
                explanation=candidate.explanation,
                explanation_reasons=candidate.explanation_reasons,
                description=candidate.description,
                poi_on_route_count=candidate.poi_on_route_count,
                poi_near_route_count=candidate.poi_near_route_count,
                context_score_delta=candidate.context_score_delta,
                context_warnings=candidate.context_warnings,
                seen_before=candidate.seen_before,
            )
            for candidate in candidates
        ]

        return GenerateRouteResponse(
            status=diagnostics.status,
            warnings=diagnostics.warnings,
            requested_route_count=diagnostics.requested_route_count,
            generated_route_count=diagnostics.generated_route_count,
            routes=routes,
        )
