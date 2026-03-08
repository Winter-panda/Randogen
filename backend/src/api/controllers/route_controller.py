from src.application.dto.generate_route_request import GenerateRouteRequest
from src.application.dto.generate_route_response import (
    GenerateRouteResponse,
    PoiResponse,
    RouteCandidateResponse,
    RoutePointResponse,
)
from src.application.services.route_generation_service import RouteGenerationService
from src.application.services.user_memory_service import UserMemoryService
from src.application.usecases.generate_routes import GenerateRoutesUseCase
from src.domain.entities.route_candidate import RouteCandidate


class RouteController:
    def __init__(self) -> None:
        self._generate_routes_usecase = GenerateRoutesUseCase()
        self._route_generation_service = RouteGenerationService()
        self._user_memory_service = UserMemoryService()

    def generate_routes(
        self,
        request: GenerateRouteRequest,
    ) -> GenerateRouteResponse:
        return self._generate_routes_usecase.execute(request)

    def get_shared_route(self, stable_route_id: str) -> RouteCandidateResponse | None:
        route = self._route_generation_service.get_shared_route(stable_route_id)
        if route is None:
            return None
        return self._to_route_candidate_response(route)

    def export_route_gpx(self, stable_route_id: str) -> str | None:
        return self._route_generation_service.export_route_gpx(stable_route_id)

    def export_route_geojson(self, stable_route_id: str) -> dict | None:
        return self._route_generation_service.export_route_geojson(stable_route_id)

    def get_preference_profile(self, user_id: str) -> dict:
        return self._user_memory_service.get_preference_profile(user_id=user_id)

    def list_history(self, user_id: str) -> list[dict]:
        return self._user_memory_service.list_history(user_id=user_id)

    def list_favorites(self, user_id: str) -> list[dict]:
        return self._user_memory_service.list_favorites(user_id=user_id)

    def add_favorite(self, user_id: str, stable_route_id: str, summary: dict | None = None) -> dict:
        """Enregistre un favori.
        Priorité : cache serveur > données client fournies > entrée minimale.
        N'échoue jamais si stable_route_id est valide.
        """
        route = self._route_generation_service.get_shared_route(stable_route_id)
        if route is not None:
            return self._user_memory_service.add_favorite(user_id=user_id, route=route)
        # Cache manquant (ex. redémarrage serveur) : utiliser les données client
        fallback_summary = summary or {}
        return self._user_memory_service.add_favorite_by_summary(
            user_id=user_id,
            stable_route_id=stable_route_id,
            summary=fallback_summary,
        )

    def remove_favorite(self, user_id: str, stable_route_id: str) -> None:
        self._user_memory_service.remove_favorite(user_id=user_id, stable_route_id=stable_route_id)

    def mark_viewed(self, user_id: str, stable_route_id: str) -> bool:
        route = self._route_generation_service.get_shared_route(stable_route_id)
        if route is not None:
            self._user_memory_service.mark_route_viewed(user_id=user_id, route=route)
            return True
        # Cache manquant : mettre à jour last_seen_at si déjà connu, sinon ignorer silencieusement
        self._user_memory_service.mark_seen_by_id(user_id=user_id, stable_route_id=stable_route_id)
        return True

    def mark_exported(self, user_id: str, stable_route_id: str, export_format: str) -> bool:
        route = self._route_generation_service.get_shared_route(stable_route_id)
        if route is None:
            return True  # Non bloquant
        self._user_memory_service.mark_route_exported(
            user_id=user_id,
            route=route,
            export_format=export_format,
        )
        return True

    def _to_route_candidate_response(self, candidate: RouteCandidate) -> RouteCandidateResponse:
        return RouteCandidateResponse(
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
