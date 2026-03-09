from __future__ import annotations

import logging
import random
import time
import hashlib
import copy
import math
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

from src.application.services.poi_enrichment_service import PoiEnrichmentService
from src.application.services.contextual_scoring_service import ContextualScoringService
from src.application.services.user_memory_service import UserMemoryService
from src.domain.entities.point_of_interest import PointOfInterest
from src.domain.entities.route_candidate import RouteCandidate
from src.domain.entities.route_point import RoutePoint
from src.domain.entities.user_search import UserSearch
from src.infrastructure.config.settings import settings
from src.infrastructure.routing.ors_client import OrsClient, OrsClientError, OrsRateLimitError
from src.infrastructure.weather.open_meteo_client import OpenMeteoClient

# Module-level TTL cache: key -> (timestamp, results)
_route_cache: dict[str, tuple[float, list[RouteCandidate]]] = {}
_CACHE_TTL_S: float = 300.0  # 5 minutes
_shared_route_cache: dict[str, tuple[float, RouteCandidate]] = {}
_SHARED_ROUTE_TTL_S: float = 86_400.0  # 24h


@dataclass
class CandidateEvaluation:
    route: RouteCandidate
    score_value: float
    distance_error_ratio: float
    trail_preference_score: float
    road_share: float


@dataclass
class GenerationDiagnostics:
    status: str
    warnings: list[str]
    requested_route_count: int
    generated_route_count: int
    used_mock_fallback: bool
    technical_issue: bool
    low_data: bool


class RouteGenerationService:
    def __init__(self) -> None:
        self._ors_client = OrsClient(
            api_key=settings.ors_api_key,
            base_url=settings.ors_base_url,
            profile=settings.ors_profile,
            timeout_s=settings.ors_request_timeout_s,
        )
        self._poi_enrichment_service = PoiEnrichmentService()
        self._contextual_scoring_service = ContextualScoringService(
            weather_client=OpenMeteoClient(timeout_s=settings.weather_request_timeout_s)
        )
        self._user_memory_service = UserMemoryService()
        self._last_real_generation_stats: dict[str, Any] = {
            "evaluations": 0,
            "rate_limit_errors": 0,
            "other_errors": 0,
        }
        self._last_generation_diagnostics = GenerationDiagnostics(
            status="ok",
            warnings=[],
            requested_route_count=0,
            generated_route_count=0,
            used_mock_fallback=False,
            technical_issue=False,
            low_data=False,
        )

    def generate_routes(self, search: UserSearch) -> list[RouteCandidate]:
        self._last_real_generation_stats = {
            "evaluations": 0,
            "rate_limit_errors": 0,
            "other_errors": 0,
        }
        logger.info(
            "generate_routes: enable_real_routing=%s is_configured=%s",
            settings.enable_real_routing,
            self._ors_client.is_configured(),
        )
        used_mock_fallback = False
        if settings.enable_real_routing and self._ors_client.is_configured():
            cache_key = self._make_cache_key(search)
            cached = _route_cache.get(cache_key)
            if cached is not None:
                ts, routes = cached
                if time.time() - ts < _CACHE_TTL_S:
                    logger.info("generate_routes: cache hit (age=%.0fs)", time.time() - ts)
                    cached_routes = copy.deepcopy(routes)
                    self._set_generation_diagnostics(search=search, routes=cached_routes, used_mock_fallback=False)
                    return cached_routes
                del _route_cache[cache_key]

            t0 = time.perf_counter()
            real_routes = self._generate_real_round_trip_routes(search)
            elapsed = time.perf_counter() - t0
            logger.info(
                "generate_routes: real routes found = %d in %.2fs",
                len(real_routes),
                elapsed,
            )
            if len(real_routes) > 0:
                _route_cache[cache_key] = (time.time(), copy.deepcopy(real_routes))
                self._set_generation_diagnostics(search=search, routes=real_routes, used_mock_fallback=False)
                return real_routes

        logger.warning("generate_routes: falling back to mock routes")
        used_mock_fallback = True
        mock_routes = self._generate_mock_routes(search)
        self._set_generation_diagnostics(
            search=search,
            routes=mock_routes,
            used_mock_fallback=used_mock_fallback,
        )
        return mock_routes

    @staticmethod
    def _make_cache_key(search: UserSearch) -> str:
        desired_poi_key = ",".join(sorted({value.strip().lower() for value in search.desired_poi_categories if value}))
        return (
            f"{search.user_id}:"
            f"{search.latitude:.5f}:{search.longitude:.5f}"
            f":{search.target_distance_km}:{search.route_count}"
            f":{search.ambiance}:{search.terrain}:{search.effort}:{search.biome_preference}"
            f":{desired_poi_key}"
            f":{int(search.prioritize_nature)}:{int(search.prioritize_viewpoints)}:{int(search.prioritize_calm)}"
            f":{int(search.avoid_urban)}:{int(search.avoid_roads)}:{int(search.avoid_steep)}:{int(search.avoid_touristic)}"
            f":{int(search.adapt_to_weather)}"
            ":poi-v5"
        )

    def _generate_real_round_trip_routes(self, search: UserSearch) -> list[RouteCandidate]:
        evaluations: list[CandidateEvaluation] = []

        style = self._build_combined_style(
            search.ambiance,
            search.terrain,
            search.effort,
            search.biome_preference,
        )
        attempts = min(max(search.route_count * 2, settings.route_candidate_search_count), 12)
        target_length_m = search.target_distance_km * 1000.0

        request_nonce = int(time.time_ns() % 1_000_000_000)
        rng = random.Random(request_nonce)

        rate_limit_errors = 0
        other_errors = 0
        rejected_reasons: dict[str, int] = {
            "distance_tolerance": 0,
            "elevation_limit": 0,
            "invalid_geometry": 0,
        }

        for index in range(attempts):
            # Early exit: enough candidates already pass the strict filter
            strict_passing = sum(
                1 for e in evaluations if e.road_share <= style["max_road_share"]
            )
            if strict_passing >= search.route_count * 2:
                logger.info(
                    "generate_routes: early exit at attempt %d (%d strict candidates)",
                    index,
                    strict_passing,
                )
                break

            varied_length_m = self._compute_candidate_length_m(
                target_length_m=target_length_m,
                index=index,
                rng=rng,
            )
            round_trip_points = rng.choice([2, 3, 4])
            seed = request_nonce + rng.randint(1, 999999) + (index * 97)

            try:
                result = self._ors_client.get_round_trip_geojson(
                    start_lon=search.longitude,
                    start_lat=search.latitude,
                    length_m=varied_length_m,
                    points=round_trip_points,
                    seed=seed,
                )
            except OrsRateLimitError as exc:
                rate_limit_errors += 1
                logger.warning("ORS rate limit (attempt %d, total=%d): %s", index, rate_limit_errors, exc)
                time.sleep(1.5)
                if rate_limit_errors >= 3:
                    logger.error("Too many ORS rate limit errors (%d), aborting generation.", rate_limit_errors)
                    break
                continue
            except OrsClientError as exc:
                other_errors += 1
                logger.warning("ORS request failed (attempt %d): %s", index, exc)
                time.sleep(0.3)
                continue

            if len(result.points) < 2:
                rejected_reasons["invalid_geometry"] += 1
                continue

            actual_distance_km = result.distance_m / 1000.0
            distance_error_ratio = self._compute_distance_error_ratio(
                target_distance_km=search.target_distance_km,
                actual_distance_km=actual_distance_km,
            )

            distance_score = self._compute_distance_score(
                target_distance_km=search.target_distance_km,
                actual_distance_km=actual_distance_km,
            )
            trail_score = self._score_trails(result.extras)
            green_score = self._score_green(result.extras)
            quiet_score = self._score_quiet(result.extras)
            suitability_score = self._score_suitability(result.extras)
            road_share = self._score_road_share(result.extras)
            elevation_gain_m = self._compute_elevation_gain_m(result.points)
            elevation_score = self._score_elevation(
                elevation_gain_m=elevation_gain_m,
                distance_km=actual_distance_km,
                target=style.get("elevation_target", "neutral"),
            )

            final_score = self._combine_scores(
                distance_score=distance_score,
                trail_score=trail_score,
                green_score=green_score,
                quiet_score=quiet_score,
                suitability_score=suitability_score,
                elevation_score=elevation_score,
                style=style,
            )

            if distance_error_ratio > style["max_distance_error_ratio"]:
                rejected_reasons["distance_tolerance"] += 1
                continue

            max_gain_per_km = style.get("max_elevation_gain_per_km")
            if max_gain_per_km is not None and actual_distance_km > 0:
                if elevation_gain_m / actual_distance_km > max_gain_per_km:
                    rejected_reasons["elevation_limit"] += 1
                    continue

            trail_ratio = self._compute_trail_ratio(result.extras)
            duration_min = self._estimate_duration_min(actual_distance_km, elevation_gain_m, trail_ratio)
            difficulty = self._compute_difficulty(actual_distance_km, elevation_gain_m, trail_ratio)
            route = RouteCandidate(
                id=f"route-{index + 1}",
                name=f"Parcours {index + 1}",
                distance_km=round(actual_distance_km, 2),
                estimated_duration_min=duration_min,
                estimated_elevation_gain_m=elevation_gain_m,
                score=final_score,
                route_type=self._build_route_type_label(
                    search.ambiance,
                    search.terrain,
                    search.effort,
                    search.biome_preference,
                ),
                source=f"openrouteservice-roundtrip:{settings.ors_profile}",
                trail_ratio=trail_ratio,
                road_ratio=round(road_share, 2),
                nature_score=round(green_score, 2),
                quiet_score=round(quiet_score, 2),
                hiking_suitability_score=round(suitability_score, 2),
                difficulty=difficulty,
                tags=self._compute_tags(
                    trail_ratio=trail_ratio,
                    road_ratio=road_share,
                    nature_score=green_score,
                    quiet_score=quiet_score,
                    suitability_score=suitability_score,
                    elevation_gain_m=elevation_gain_m,
                    distance_km=actual_distance_km,
                    trail_score=trail_score,
                    distance_score=distance_score,
                ),
                points=self._deduplicate_points(result.points),
            )

            evaluations.append(
                CandidateEvaluation(
                    route=route,
                    score_value=final_score,
                    distance_error_ratio=distance_error_ratio,
                    trail_preference_score=trail_score,
                    road_share=road_share,
                )
            )

        logger.info(
            "generate_routes: loop done - %d evaluations, %d rate-limit errors, %d other errors",
            len(evaluations),
            rate_limit_errors,
            other_errors,
        )
        logger.info("generate_routes: rejected candidates reasons = %s", rejected_reasons)
        self._last_real_generation_stats = {
            "evaluations": len(evaluations),
            "rate_limit_errors": rate_limit_errors,
            "other_errors": other_errors,
        }

        if len(evaluations) == 0:
            return []

        if search.biome_preference:
            evaluations.sort(
                key=lambda item: (
                    -self._compute_biome_affinity(route=item.route, biome=search.biome_preference),
                    -item.score_value,
                    -item.trail_preference_score,
                    item.road_share,
                    item.distance_error_ratio,
                    item.route.distance_km,
                )
            )
        else:
            evaluations.sort(
                key=lambda item: (
                    -item.score_value,
                    -item.trail_preference_score,
                    item.road_share,
                    item.distance_error_ratio,
                    item.route.distance_km,
                )
            )

        selected = self._select_routes(
            evaluations,
            search.route_count,
            style["max_road_share"],
            search.biome_preference,
        )
        return self._attach_pois_to_routes(selected, search)

    def _select_routes(
        self,
        evaluations: list[CandidateEvaluation],
        count: int,
        max_road_share: float,
        biome_preference: str | None = None,
    ) -> list[RouteCandidate]:
        """Multi-pass selection:
        - pass 1: strict road-share + strict biome fit (if biome selected)
        - pass 2: relaxed road-share + medium biome fit
        - pass 3: best remaining candidates (guarantee route_count when possible)
        Routes too similar (Jaccard >= threshold) to an already-selected route are skipped."""
        selected: list[RouteCandidate] = []
        selected_grids: list[frozenset[str]] = []
        used_signatures: set[str] = set()
        threshold = settings.route_duplicate_similarity_threshold
        strict_biome_min = self._biome_min_affinity(biome_preference, strict=True)
        relaxed_biome_min = self._biome_min_affinity(biome_preference, strict=False)

        def _try_add(
            evaluation: CandidateEvaluation,
            road_share_limit: float,
            biome_min_affinity: float | None,
        ) -> bool:
            if evaluation.road_share > road_share_limit:
                return False
            if biome_preference and biome_min_affinity is not None:
                affinity = self._compute_biome_affinity(route=evaluation.route, biome=biome_preference)
                if affinity < biome_min_affinity:
                    return False
            signature = self._build_route_signature(evaluation.route)
            if signature in used_signatures:
                return False
            grid = self._build_route_grid(evaluation.route)
            for idx, existing_grid in enumerate(selected_grids):
                if self._jaccard_similarity(grid, existing_grid) >= threshold:
                    return False
                if self._route_shape_similarity(evaluation.route, selected[idx]) >= 0.88:
                    return False
            used_signatures.add(signature)
            selected_grids.append(grid)
            route = evaluation.route
            route.id = f"route-{len(selected) + 1}"
            route.name = f"Parcours {len(selected) + 1}"
            selected.append(route)
            return True

        # Pass 1 - strict: respect the style's road share limit
        for evaluation in evaluations:
            if len(selected) >= count:
                break
            _try_add(evaluation, max_road_share, strict_biome_min)

        # Pass 2 - relaxed road-share and biome match.
        if len(selected) < count:
            relaxed_road_share = min(1.0, max(max_road_share, 0.65))
            logger.info(
                "Only %d/%d routes passed strict filters, trying relaxed biome/road matching.",
                len(selected),
                count,
            )
            for evaluation in evaluations:
                if len(selected) >= count:
                    break
                _try_add(evaluation, relaxed_road_share, relaxed_biome_min)

        # Pass 3 - relaxed: fill missing slots with the best remaining candidates
        # (happens in dense urban areas where ideal trails are unavailable)
        if len(selected) < count:
            logger.info(
                "Only %d/%d routes passed strict/relaxed filters (road %.0f%%), relaxing fully for remaining slots.",
                len(selected),
                count,
                max_road_share * 100,
            )
            for evaluation in evaluations:
                if len(selected) >= count:
                    break
                _try_add(evaluation, 1.0, None)

        return selected

    def _build_route_grid(self, route: RouteCandidate) -> frozenset[str]:
        """Return the set of ~200m grid cells the route passes through.
        Used for Jaccard-based similarity detection."""
        cells: set[str] = set()
        for point in route.points:
            # 0.002 deg ~= 222m latitude, ~= 140m longitude at mid-latitudes
            lat_cell = int(point.latitude * 500)
            lon_cell = int(point.longitude * 500)
            cells.add(f"{lat_cell}:{lon_cell}")
        return frozenset(cells)

    def _jaccard_similarity(self, grid_a: frozenset[str], grid_b: frozenset[str]) -> float:
        """Jaccard index between two grid-cell sets: |A n B| / |A u B|."""
        if not grid_a and not grid_b:
            return 1.0
        if not grid_a or not grid_b:
            return 0.0
        intersection = len(grid_a & grid_b)
        union = len(grid_a | grid_b)
        return intersection / union

    def _route_shape_similarity(self, a: RouteCandidate, b: RouteCandidate) -> float:
        if len(a.points) < 2 or len(b.points) < 2:
            return 0.0
        sampled_a = self._sample_route_points(a.points, 16)
        sampled_b = self._sample_route_points(b.points, 16)
        count = min(len(sampled_a), len(sampled_b))
        if count == 0:
            return 0.0
        avg_distance_m = sum(
            self._haversine_m(
                sampled_a[i].latitude,
                sampled_a[i].longitude,
                sampled_b[i].latitude,
                sampled_b[i].longitude,
            )
            for i in range(count)
        ) / count
        return max(0.0, min(1.0, 1.0 - (avg_distance_m / 350.0)))

    def _sample_route_points(self, points: list[RoutePoint], max_points: int) -> list[RoutePoint]:
        if len(points) <= max_points:
            return points
        step = max(1, len(points) // max_points)
        sampled = [points[i] for i in range(0, len(points), step)]
        if sampled[-1] != points[-1]:
            sampled.append(points[-1])
        return sampled[:max_points]

    def _haversine_m(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        earth_radius_m = 6_371_000.0
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        d_phi = math.radians(lat2 - lat1)
        d_lambda = math.radians(lon2 - lon1)
        a = (
            math.sin(d_phi / 2.0) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2.0) ** 2
        )
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        return earth_radius_m * c

    def _get_style_config(self, hike_style: str) -> dict[str, float]:
        normalized = (hike_style or "equilibree").strip().lower()

        configs: dict[str, Any] = {
            "equilibree": {
                "distance_weight": 0.45,
                "trail_weight": 0.25,
                "green_weight": 0.15,
                "quiet_weight": 0.10,
                "suitability_weight": 0.05,
                "elevation_weight": 0.00,
                "poi_weight": 0.05,
                "max_distance_error_ratio": 0.50,
                "max_road_share": 0.65,
            },
            "sentiers": {
                "distance_weight": 0.30,
                "trail_weight": 0.45,
                "green_weight": 0.10,
                "quiet_weight": 0.10,
                "suitability_weight": 0.05,
                "elevation_weight": 0.00,
                "poi_weight": 0.03,
                "max_distance_error_ratio": 0.60,
                "max_road_share": 0.20,
            },
            "nature": {
                "distance_weight": 0.30,
                "trail_weight": 0.25,
                "green_weight": 0.25,
                "quiet_weight": 0.15,
                "suitability_weight": 0.05,
                "elevation_weight": 0.00,
                "poi_weight": 0.08,
                "max_distance_error_ratio": 0.60,
                "max_road_share": 0.25,
            },
            "calme": {
                "distance_weight": 0.35,
                "trail_weight": 0.20,
                "green_weight": 0.15,
                "quiet_weight": 0.25,
                "suitability_weight": 0.05,
                "elevation_weight": 0.00,
                "poi_weight": 0.04,
                "max_distance_error_ratio": 0.60,
                "max_road_share": 0.25,
            },
            "plat": {
                "distance_weight": 0.40,
                "trail_weight": 0.15,
                "green_weight": 0.10,
                "quiet_weight": 0.10,
                "suitability_weight": 0.05,
                "elevation_weight": 0.20,
                "poi_weight": 0.04,
                "elevation_target": "flat",
                "max_distance_error_ratio": 0.50,
                "max_road_share": 0.70,
                "max_elevation_gain_per_km": 35.0,
            },
            "vallonne": {
                "distance_weight": 0.30,
                "trail_weight": 0.20,
                "green_weight": 0.15,
                "quiet_weight": 0.10,
                "suitability_weight": 0.05,
                "elevation_weight": 0.20,
                "poi_weight": 0.06,
                "elevation_target": "hilly",
                "max_distance_error_ratio": 0.60,
                "max_road_share": 0.50,
            },
            "sportif": {
                "distance_weight": 0.25,
                "trail_weight": 0.20,
                "green_weight": 0.10,
                "quiet_weight": 0.05,
                "suitability_weight": 0.10,
                "elevation_weight": 0.30,
                "poi_weight": 0.06,
                "elevation_target": "hilly",
                "max_distance_error_ratio": 0.60,
                "max_road_share": 0.50,
            },
            "promenade": {
                "distance_weight": 0.45,
                "trail_weight": 0.10,
                "green_weight": 0.15,
                "quiet_weight": 0.15,
                "suitability_weight": 0.05,
                "elevation_weight": 0.10,
                "poi_weight": 0.08,
                "elevation_target": "flat",
                "max_distance_error_ratio": 0.50,
                "max_road_share": 0.80,
                "max_elevation_gain_per_km": 25.0,
            },
            "foret": {
                "distance_weight": 0.20,
                "trail_weight": 0.30,
                "green_weight": 0.35,
                "quiet_weight": 0.10,
                "suitability_weight": 0.05,
                "elevation_weight": 0.00,
                "poi_weight": 0.08,
                "max_distance_error_ratio": 0.65,
                "max_road_share": 0.22,
            },
            "campagne": {
                "distance_weight": 0.28,
                "trail_weight": 0.20,
                "green_weight": 0.24,
                "quiet_weight": 0.17,
                "suitability_weight": 0.06,
                "elevation_weight": 0.05,
                "poi_weight": 0.06,
                "max_distance_error_ratio": 0.65,
                "max_road_share": 0.35,
            },
            "cotier": {
                "distance_weight": 0.26,
                "trail_weight": 0.18,
                "green_weight": 0.19,
                "quiet_weight": 0.10,
                "suitability_weight": 0.05,
                "elevation_weight": 0.07,
                "poi_weight": 0.15,
                "max_distance_error_ratio": 0.70,
                "max_road_share": 0.45,
            },
            "montagne": {
                "distance_weight": 0.20,
                "trail_weight": 0.20,
                "green_weight": 0.15,
                "quiet_weight": 0.05,
                "suitability_weight": 0.10,
                "elevation_weight": 0.30,
                "poi_weight": 0.10,
                "elevation_target": "hilly",
                "max_distance_error_ratio": 0.70,
                "max_road_share": 0.45,
            },
            "bord_eau": {
                "distance_weight": 0.24,
                "trail_weight": 0.18,
                "green_weight": 0.20,
                "quiet_weight": 0.10,
                "suitability_weight": 0.05,
                "elevation_weight": 0.08,
                "poi_weight": 0.15,
                "max_distance_error_ratio": 0.70,
                "max_road_share": 0.45,
            },
            "patrimoine": {
                "distance_weight": 0.30,
                "trail_weight": 0.14,
                "green_weight": 0.10,
                "quiet_weight": 0.15,
                "suitability_weight": 0.06,
                "elevation_weight": 0.05,
                "poi_weight": 0.20,
                "max_distance_error_ratio": 0.70,
                "max_road_share": 0.60,
            },
        }

        return configs.get(normalized, configs["equilibree"])

    def _build_combined_style(
        self,
        ambiance: str | None,
        terrain: str | None,
        effort: str | None,
        biome_preference: str | None = None,
    ) -> dict[str, Any]:
        active = [
            self._get_style_config(k)
            for k in [ambiance, terrain, effort, biome_preference]
            if k is not None
        ]
        if not active:
            return self._get_style_config("equilibree")

        weight_keys = [
            "distance_weight", "trail_weight", "green_weight",
            "quiet_weight", "suitability_weight", "elevation_weight",
        ]

        merged: dict[str, Any] = {}
        for k in weight_keys:
            merged[k] = sum(c.get(k, 0.0) for c in active) / len(active)

        total = sum(merged[k] for k in weight_keys)
        if total > 0:
            for k in weight_keys:
                merged[k] = round(merged[k] / total, 4)

        merged["poi_weight"] = round(
            sum(c.get("poi_weight", 0.05) for c in active) / len(active),
            4,
        )

        merged["max_distance_error_ratio"] = min(c["max_distance_error_ratio"] for c in active)
        merged["max_road_share"] = min(c["max_road_share"] for c in active)

        for c in active:
            if "elevation_target" in c:
                merged["elevation_target"] = c["elevation_target"]
                break

        gain_limits = [c["max_elevation_gain_per_km"] for c in active if "max_elevation_gain_per_km" in c]
        if gain_limits:
            merged["max_elevation_gain_per_km"] = min(gain_limits)

        return merged

    def _build_route_type_label(
        self,
        ambiance: str | None,
        terrain: str | None,
        effort: str | None,
        biome_preference: str | None = None,
    ) -> str:
        parts = [p for p in [ambiance, terrain, effort, biome_preference] if p is not None]
        return " + ".join(parts) if parts else "libre"

    def _compute_candidate_length_m(self, target_length_m: float, index: int, rng: random.Random) -> float:
        factors = [1.00, 0.92, 1.08, 0.85, 1.15, 0.78, 1.22, 0.70, 1.30, 0.96]
        base_factor = factors[index % len(factors)]
        jitter = rng.uniform(-0.08, 0.08)
        return max(800.0, target_length_m * (base_factor + jitter))

    def _compute_distance_error_ratio(self, target_distance_km: float, actual_distance_km: float) -> float:
        if target_distance_km <= 0:
            return 1.0
        return abs(actual_distance_km - target_distance_km) / target_distance_km

    def _compute_distance_score(self, target_distance_km: float, actual_distance_km: float) -> float:
        error_ratio = self._compute_distance_error_ratio(
            target_distance_km=target_distance_km,
            actual_distance_km=actual_distance_km,
        )
        return round(max(0.1, 1.0 - error_ratio), 2)

    def _combine_scores(
        self,
        distance_score: float,
        trail_score: float,
        green_score: float,
        quiet_score: float,
        suitability_score: float,
        elevation_score: float,
        style: dict[str, float],
    ) -> float:
        total = (
            distance_score * style["distance_weight"]
            + trail_score * style["trail_weight"]
            + green_score * style["green_weight"]
            + quiet_score * style["quiet_weight"]
            + suitability_score * style["suitability_weight"]
            + elevation_score * style.get("elevation_weight", 0.0)
        )
        return round(max(0.1, min(1.0, total)), 2)

    def _score_elevation(self, elevation_gain_m: float, distance_km: float, target: str) -> float:
        if distance_km <= 0:
            return 0.5
        gain_per_km = elevation_gain_m / distance_km
        if target == "flat":
            # 0m/km -> 1.0, 50m/km -> 0.0
            return round(max(0.0, min(1.0, 1.0 - gain_per_km / 50.0)), 2)
        if target == "hilly":
            # 0m/km -> 0.0, 100m/km -> 1.0
            return round(max(0.0, min(1.0, gain_per_km / 100.0)), 2)
        return 0.5  # neutral

    def _compute_trail_ratio(self, extras: dict[str, Any]) -> float:
        summary = self._get_summary(extras, "waytype")
        return round(self._summary_amount(summary, {4, 5, 6, 7}), 2)

    def _score_trails(self, extras: dict[str, Any]) -> float:
        summary = self._get_summary(extras, "waytype")
        preferred = self._summary_amount(summary, {4, 5, 7})
        acceptable = self._summary_amount(summary, {6})
        penalized = self._summary_amount(summary, {1, 2, 3, 8, 9, 10})
        score = 0.5 + (preferred * 0.7) + (acceptable * 0.15) - (penalized * 0.8)
        return round(max(0.1, min(1.0, score)), 2)

    def _score_road_share(self, extras: dict[str, Any]) -> float:
        summary = self._get_summary(extras, "waytype")
        road_share = self._summary_amount(summary, {1, 2, 3})
        return round(max(0.0, min(1.0, road_share)), 2)

    def _score_green(self, extras: dict[str, Any]) -> float:
        summary = self._get_summary(extras, "green")
        return round(max(0.1, min(1.0, self._weighted_level_score(summary, 10))), 2)

    def _score_quiet(self, extras: dict[str, Any]) -> float:
        summary = self._get_summary(extras, "noise")
        noisy = self._weighted_level_score(summary, 10)
        quiet = 1.0 - noisy
        return round(max(0.1, min(1.0, quiet)), 2)

    def _score_suitability(self, extras: dict[str, Any]) -> float:
        summary = self._get_summary(extras, "suitability")
        return round(max(0.1, min(1.0, self._weighted_level_score(summary, 10))), 2)

    def _get_summary(self, extras: dict[str, Any], key: str) -> list[dict[str, float]]:
        node = extras.get(key, {})
        summary = node.get("summary", [])
        if isinstance(summary, list):
            return summary
        return []

    def _summary_amount(self, summary: list[dict[str, float]], accepted_values: set[int]) -> float:
        total = 0.0
        for item in summary:
            try:
                value = int(item.get("value", -1))
                amount_percent = float(item.get("amount", 0.0))
            except (TypeError, ValueError):
                continue

            if value in accepted_values:
                total += amount_percent / 100.0
        return total

    def _weighted_level_score(self, summary: list[dict[str, float]], max_level: int) -> float:
        weighted = 0.0
        total = 0.0

        for item in summary:
            try:
                value = float(item.get("value", 0.0))
                amount_percent = float(item.get("amount", 0.0))
            except (TypeError, ValueError):
                continue

            share = amount_percent / 100.0
            weighted += (value / max_level) * share
            total += share

        if total <= 0:
            return 0.5

        return weighted / total

    def _compute_elevation_gain_m(self, points: list[RoutePoint]) -> int:
        gain = 0.0
        for i in range(1, len(points)):
            diff = points[i].elevation_m - points[i - 1].elevation_m
            if diff > 0:
                gain += diff
        return int(round(gain))

    def _deduplicate_points(self, points: list[RoutePoint]) -> list[RoutePoint]:
        if len(points) <= 1:
            return points

        result: list[RoutePoint] = [points[0]]

        for point in points[1:]:
            previous = result[-1]
            if (
                round(previous.latitude, 6) == round(point.latitude, 6)
                and round(previous.longitude, 6) == round(point.longitude, 6)
            ):
                continue
            result.append(point)

        return result

    def _build_route_signature(self, route: RouteCandidate) -> str:
        """Build a geographic signature using 10 evenly-spaced points at 3-decimal precision.
        Two routes sharing this signature are considered duplicates."""
        n = len(route.points)
        if n == 0:
            return route.id

        sample_count = min(10, n)
        step = max(1, n // sample_count)
        sampled = []
        for i in range(0, n, step):
            point = route.points[i]
            sampled.append(f"{round(point.latitude, 3)}:{round(point.longitude, 3)}")
        # Always include the last point
        last = route.points[-1]
        last_sig = f"{round(last.latitude, 3)}:{round(last.longitude, 3)}"
        if not sampled or sampled[-1] != last_sig:
            sampled.append(last_sig)

        dist_bucket = int(route.distance_km * 2)  # 500m buckets
        return f"{dist_bucket}|{'|'.join(sampled)}"

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

            mock_distance_km = search.target_distance_km * (0.95 + index * 0.03)
            mock_elevation_m = 30 + (index * 25)
            route = RouteCandidate(
                id=f"route-{index + 1}",
                name=f"Parcours {index + 1}",
                distance_km=round(mock_distance_km, 2),
                estimated_duration_min=self._estimate_duration_min(mock_distance_km, mock_elevation_m, 0.25),
                estimated_elevation_gain_m=mock_elevation_m,
                score=round(0.72 + (index * 0.08), 2),
                route_type=self._build_route_type_label(
                    search.ambiance,
                    search.terrain,
                    search.effort,
                    search.biome_preference,
                ),
                source="mock-generator",
                trail_ratio=0.25,
                road_ratio=0.75,
                nature_score=0.30,
                quiet_score=0.30,
                hiking_suitability_score=0.40,
                difficulty=self._compute_difficulty(mock_distance_km, mock_elevation_m, 0.25),
                tags=self._compute_tags(
                    trail_ratio=0.25,
                    road_ratio=0.75,
                    nature_score=0.30,
                    quiet_score=0.30,
                    suitability_score=0.40,
                    elevation_gain_m=mock_elevation_m,
                    distance_km=mock_distance_km,
                    trail_score=0.3,
                    distance_score=0.9,
                ),
                points=points,
            )
            routes.append(route)

        return self._attach_pois_to_routes(routes, search)

    def _attach_pois_to_routes(self, routes: list[RouteCandidate], search: UserSearch) -> list[RouteCandidate]:
        shared_candidates = self._poi_enrichment_service.prefetch_candidates_for_routes(routes)
        if len(shared_candidates) > 0:
            logger.info(
                "poi: shared candidate pool %d for %d routes",
                len(shared_candidates),
                len(routes),
            )
        for route in routes:
            try:
                self._poi_enrichment_service.enrich_route(
                    route,
                    search,
                    candidates=shared_candidates if len(shared_candidates) > 0 else None,
                )
                style = self._build_combined_style(
                    search.ambiance,
                    search.terrain,
                    search.effort,
                    search.biome_preference,
                )
                poi_weight = float(style.get("poi_weight", 0.05))
                pre_preference_score = route.score
                route.score = self._apply_user_preference_adjustments(
                    route=route,
                    search=search,
                    poi_weight=poi_weight,
                )
                if search.biome_preference:
                    biome_affinity = self._compute_biome_affinity(route=route, biome=search.biome_preference)
                    if biome_affinity >= 0.62:
                        biome_label_map = {
                            "foret": "Biome : forêt",
                            "campagne": "Biome : campagne",
                            "cotier": "Biome : côtier",
                            "montagne": "Biome : montagne",
                            "bord_eau": "Biome : bord d'eau",
                            "patrimoine": "Biome : patrimoine",
                        }
                        biome_tag = biome_label_map.get(search.biome_preference)
                        if biome_tag and biome_tag not in route.tags:
                            route.tags.append(biome_tag)
                if search.desired_poi_categories:
                    poi_match = self._compute_poi_category_match(
                        route=route,
                        desired_categories=search.desired_poi_categories,
                    )
                    if poi_match >= 1.0:
                        if "POI demandes couverts" not in route.tags:
                            route.tags.append("POI demandes couverts")
                    elif poi_match >= 0.5:
                        if "POI demandes partiellement couverts" not in route.tags:
                            route.tags.append("POI demandes partiellement couverts")
                if settings.enable_weather_context and search.adapt_to_weather:
                    context_adjustment = self._contextual_scoring_service.adjust_route(
                        route=route,
                        search=search,
                    )
                    route.context_score_delta = context_adjustment.score_delta
                    route.context_warnings = context_adjustment.warnings
                    for tag in context_adjustment.tags:
                        if tag not in route.tags:
                            route.tags.append(tag)
                    route.score = round(max(0.1, min(1.0, route.score + route.context_score_delta)), 2)
                else:
                    route.context_score_delta = 0.0
                    route.context_warnings = []
                route.score_breakdown = self._build_score_breakdown(
                    route=route,
                    search=search,
                    base_score=pre_preference_score,
                    poi_weight=poi_weight,
                )
                route.explanation_reasons = self._build_explanation_reasons(route)
                route.explanation = self._build_explanation_sentence(route)
                route.description = self._build_route_description(route)
                route.stable_route_id = self._build_stable_route_id(route)
                route.seen_before = self._user_memory_service.has_seen_recently(
                    user_id=search.user_id,
                    stable_route_id=route.stable_route_id,
                    within_hours=72,
                )
                if route.seen_before:
                    route.score = round(max(0.1, route.score - 0.04), 2)
                    if "Deja vu recemment" not in route.tags:
                        route.tags.append("Deja vu recemment")
                zone_penalty = self._user_memory_service.compute_zone_novelty_factor(
                    user_id=search.user_id,
                    route=route,
                )
                if zone_penalty > 0:
                    route.score = round(max(0.1, route.score - zone_penalty), 2)
                    if zone_penalty >= 0.04 and "Zone recemment exploree" not in route.tags:
                        route.tags.append("Zone recemment exploree")
                if search.difficulty_pref:
                    diff = route.difficulty.lower() if route.difficulty else "moderee"
                    pref = search.difficulty_pref.lower()
                    _DIFF_RANK = {"facile": 0, "moderee": 1, "difficile": 2, "soutenue": 3}
                    diff_rank = _DIFF_RANK.get(diff, 1)
                    pref_rank = _DIFF_RANK.get(pref, 1)
                    gap = abs(diff_rank - pref_rank)
                    if gap == 0:
                        route.score = round(min(1.0, route.score + 0.05), 2)
                    elif gap == 1:
                        route.score = round(max(0.05, route.score - 0.04), 2)
                    else:
                        route.score = round(max(0.05, route.score - 0.09), 2)
                ordered_pois = sorted(
                    route.pois,
                    key=lambda p: (
                        p.distance_from_start_m if p.distance_from_start_m is not None else 999_999.0,
                        p.distance_to_route_m,
                    ),
                )
                route.pois = ordered_pois
                route.poi_on_route_count = sum(1 for poi in ordered_pois if poi.distance_to_route_m <= 80.0)
                route.poi_near_route_count = len(ordered_pois) - route.poi_on_route_count
                self._register_shared_route(route)
            except Exception as exc:
                logger.warning("Unable to enrich route %s with POIs: %s", route.id, exc)
                route.pois = []
                route.poi_score = 0.0
                route.poi_quantity_score = 0.0
                route.poi_diversity_score = 0.0
                route.poi_highlight_count = 0
                route.highlighted_poi_labels = []
                route.poi_highlights = []
                route.score_breakdown = {}
                route.explanation = ""
                route.explanation_reasons = []
                route.description = ""
                route.stable_route_id = ""
                route.poi_on_route_count = 0
                route.poi_near_route_count = 0
                route.context_score_delta = 0.0
                route.context_warnings = []
                route.seen_before = False
                # Keep a stable share/export id even when POI enrichment fails.
                route.stable_route_id = self._build_stable_route_id(route)
                self._register_shared_route(route)
        routes.sort(key=lambda r: (-r.score, r.distance_km))
        return routes

    def _set_generation_diagnostics(
        self,
        *,
        search: UserSearch,
        routes: list[RouteCandidate],
        used_mock_fallback: bool,
    ) -> None:
        warnings: list[str] = []
        generated_count = len(routes)
        requested_count = search.route_count

        technical_issue = False
        low_data = False
        status = "ok"

        if used_mock_fallback:
            status = "fallback"
            technical_issue = True
            warnings.append("Service de routage externe indisponible: fallback local utilise.")

        if generated_count == 0:
            status = "error"
            warnings.append("Aucun parcours valide n'a pu etre genere.")
        elif generated_count < requested_count:
            if status == "ok":
                status = "partial"
            warnings.append(f"Generation partielle: {generated_count}/{requested_count} parcours seulement.")

        total_pois = sum(len(route.pois) for route in routes)
        avg_pois = (total_pois / generated_count) if generated_count > 0 else 0.0
        if generated_count > 0 and avg_pois < 1.0:
            low_data = True
            if status == "ok":
                status = "low_data"
            warnings.append("Zone pauvre en POI: resultats limites mais exploitables.")

        poi_provider_error = self.get_last_poi_provider_error()
        if poi_provider_error:
            technical_issue = True
            if status == "ok":
                status = "partial"
            warnings.append(
                "Service POI indisponible temporairement (Overpass/API externe). "
                f"Detail: {poi_provider_error}"
            )

        if search.biome_preference and generated_count > 0:
            affinities = [
                self._compute_biome_affinity(route=route, biome=search.biome_preference)
                for route in routes
            ]
            best_affinity = max(affinities)
            expected_affinity = self._biome_min_affinity(search.biome_preference, strict=True) or 0.55
            if best_affinity < expected_affinity:
                warnings.append(
                    f"Biome '{self._biome_display_label(search.biome_preference)}' peu present autour de vous; "
                    "resultats affiches sur les options les plus proches."
                )

        desired_poi_categories = [
            value.strip().lower()
            for value in search.desired_poi_categories
            if isinstance(value, str) and value.strip()
        ]
        if desired_poi_categories and generated_count > 0:
            available_categories: set[str] = set()
            for route in routes:
                available_categories.update({poi.category for poi in route.pois})
            missing = [value for value in desired_poi_categories if value not in available_categories]
            if missing:
                missing_labels = [self._poi_category_label(value) for value in missing]
                warnings.append(
                    "POI demandes peu disponibles autour de vous: "
                    + ", ".join(sorted(missing_labels))
                    + "."
                )

        if not used_mock_fallback:
            rate_limit_errors = int(self._last_real_generation_stats.get("rate_limit_errors", 0))
            other_errors = int(self._last_real_generation_stats.get("other_errors", 0))
            if rate_limit_errors > 0 or other_errors > 0:
                warnings.append(
                    f"Instabilite API detectee (ratelimit={rate_limit_errors}, autres_erreurs={other_errors})."
                )
                technical_issue = True

        for route in routes:
            for warning in route.context_warnings:
                if warning not in warnings:
                    warnings.append(warning)

        self._last_generation_diagnostics = GenerationDiagnostics(
            status=status,
            warnings=warnings,
            requested_route_count=requested_count,
            generated_route_count=generated_count,
            used_mock_fallback=used_mock_fallback,
            technical_issue=technical_issue,
            low_data=low_data,
        )
        logger.info(
            "generation diagnostics: status=%s generated=%d requested=%d warnings=%s",
            status,
            generated_count,
            requested_count,
            warnings,
        )

    def get_last_generation_diagnostics(self) -> GenerationDiagnostics:
        diagnostics = self._last_generation_diagnostics
        return GenerationDiagnostics(
            status=diagnostics.status,
            warnings=list(diagnostics.warnings),
            requested_route_count=diagnostics.requested_route_count,
            generated_route_count=diagnostics.generated_route_count,
            used_mock_fallback=diagnostics.used_mock_fallback,
            technical_issue=diagnostics.technical_issue,
            low_data=diagnostics.low_data,
        )

    def get_shared_route(self, stable_route_id: str) -> RouteCandidate | None:
        self._cleanup_shared_routes()
        cached = _shared_route_cache.get(stable_route_id)
        if cached is None:
            return None
        ts, route = cached
        if time.time() - ts > _SHARED_ROUTE_TTL_S:
            _shared_route_cache.pop(stable_route_id, None)
            return None
        return copy.deepcopy(route)

    def get_last_poi_provider_error(self) -> str | None:
        return self._poi_enrichment_service.get_last_provider_error()

    def discover_nearby_pois(
        self,
        *,
        latitude: float,
        longitude: float,
        radius_km: float = 5.0,
        categories: list[str] | None = None,
        limit: int = 250,
    ) -> list[PointOfInterest]:
        bounded_radius_km = max(0.5, min(10.0, float(radius_km)))
        radius_m = int(round(bounded_radius_km * 1000.0))
        return self._poi_enrichment_service.discover_nearby_pois(
            latitude=latitude,
            longitude=longitude,
            radius_m=radius_m,
            categories=categories or [],
            limit=limit,
        )

    def export_route_gpx(self, stable_route_id: str) -> str | None:
        route = self.get_shared_route(stable_route_id)
        if route is None:
            return None

        def _escape(value: str) -> str:
            return (
                value.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&apos;")
            )

        trk_points = []
        for point in route.points:
            ele_block = f"<ele>{(point.elevation_m or 0.0):.1f}</ele>" if (point.elevation_m or 0.0) != 0.0 else ""
            trk_points.append(f'      <trkpt lat="{point.latitude}" lon="{point.longitude}">{ele_block}</trkpt>')

        wpt_points = []
        for poi in route.pois:
            wpt_points.append(
                "\n".join(
                    [
                        f'  <wpt lat="{poi.latitude}" lon="{poi.longitude}">',
                        f"    <name>{_escape(poi.name)}</name>",
                        f"    <type>{_escape(poi.category)}</type>",
                        f"    <desc>distance trace: {int(round(poi.distance_to_route_m))} m</desc>",
                        "  </wpt>",
                    ]
                )
            )

        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<gpx version="1.1" creator="Randogen" xmlns="http://www.topografix.com/GPX/1/1">\n'
            "  <metadata>\n"
            f"    <name>{_escape(route.name)}</name>\n"
            f"    <desc>{_escape(route.description or route.explanation)}</desc>\n"
            "  </metadata>\n"
            + ("\n".join(wpt_points) + "\n" if len(wpt_points) > 0 else "")
            + "  <trk>\n"
            f"    <name>{_escape(route.name)}</name>\n"
            "    <trkseg>\n"
            + "\n".join(trk_points)
            + "\n    </trkseg>\n"
            "  </trk>\n"
            "</gpx>\n"
        )

    def export_route_geojson(self, stable_route_id: str) -> dict[str, Any] | None:
        route = self.get_shared_route(stable_route_id)
        if route is None:
            return None

        coordinates = [
            [point.longitude, point.latitude, (point.elevation_m or 0.0)]
            for point in route.points
        ]
        poi_features = [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [poi.longitude, poi.latitude],
                },
                "properties": {
                    "id": poi.id,
                    "name": poi.name,
                    "category": poi.category,
                    "sub_category": poi.sub_category,
                    "distance_to_route_m": poi.distance_to_route_m,
                    "score": poi.score,
                },
            }
            for poi in route.pois
        ]
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": coordinates},
                    "properties": {
                        "id": route.id,
                        "stable_route_id": route.stable_route_id,
                        "name": route.name,
                        "distance_km": route.distance_km,
                        "estimated_duration_min": route.estimated_duration_min,
                        "estimated_elevation_gain_m": route.estimated_elevation_gain_m,
                        "difficulty": route.difficulty,
                        "score": route.score,
                        "description": route.description,
                    },
                },
                *poi_features,
            ],
        }

    def _apply_user_preference_adjustments(
        self,
        *,
        route: RouteCandidate,
        search: UserSearch,
        poi_weight: float,
    ) -> float:
        base_weight = max(0.0, 1.0 - poi_weight)
        score = (route.score * base_weight) + (route.poi_score * poi_weight)

        categories = {poi.category for poi in route.pois}
        biome_affinity = self._compute_biome_affinity(route=route, biome=search.biome_preference)
        gain_per_km = (
            route.estimated_elevation_gain_m / route.distance_km
            if route.distance_km > 0
            else 0.0
        )
        urban_index = (route.road_ratio * 0.65) + ((1.0 - route.quiet_score) * 0.35)

        if search.prioritize_nature:
            score += 0.03 * route.nature_score
            if {"nature", "water", "viewpoint"} & categories:
                score += 0.02
        if search.prioritize_viewpoints:
            if {"viewpoint", "summit"} & categories:
                score += 0.04
            else:
                score -= 0.02
        if search.prioritize_calm:
            score += 0.04 * route.quiet_score

        if search.avoid_urban:
            score -= max(0.0, urban_index - 0.40) * 0.10
        if search.avoid_roads:
            score -= max(0.0, route.road_ratio - 0.20) * 0.12
        if search.avoid_steep:
            score -= max(0.0, gain_per_km - 35.0) / 600.0
        if search.avoid_touristic:
            touristic_count = sum(
                1
                for poi in route.pois
                if poi.category in {"heritage", "start_access"}
            )
            score -= min(0.08, touristic_count * 0.015)
        if search.biome_preference:
            # Biome preference is a primary ranking signal when explicitly chosen.
            if biome_affinity >= 0.75:
                score += 0.12
            elif biome_affinity >= 0.62:
                score += 0.07
            elif biome_affinity >= 0.50:
                score += 0.02
            elif biome_affinity >= 0.38:
                score -= 0.08
            else:
                score -= 0.16
        desired_poi_categories = {
            value.strip().lower()
            for value in search.desired_poi_categories
            if isinstance(value, str) and value.strip()
        }
        if desired_poi_categories:
            matched = len(desired_poi_categories & categories)
            coverage = matched / len(desired_poi_categories)
            if coverage >= 1.0:
                score += 0.14
            elif coverage >= 0.66:
                score += 0.09
            elif coverage >= 0.34:
                score += 0.03
            else:
                score -= 0.18

        # Guardrails: keep feasibility-first ranking while still differentiating profiles.
        return round(max(0.1, min(1.0, score)), 2)

    def _biome_min_affinity(self, biome: str | None, *, strict: bool) -> float | None:
        normalized = (biome or "").strip().lower()
        if not normalized:
            return None

        strict_thresholds = {
            "foret": 0.60,
            "campagne": 0.55,
            "cotier": 0.52,
            "montagne": 0.58,
            "bord_eau": 0.54,
            "patrimoine": 0.50,
        }
        relaxed_thresholds = {
            "foret": 0.48,
            "campagne": 0.44,
            "cotier": 0.40,
            "montagne": 0.46,
            "bord_eau": 0.42,
            "patrimoine": 0.38,
        }
        table = strict_thresholds if strict else relaxed_thresholds
        return table.get(normalized, 0.50 if strict else 0.40)

    def _biome_display_label(self, biome: str | None) -> str:
        normalized = (biome or "").strip().lower()
        labels = {
            "foret": "forêt",
            "campagne": "campagne",
            "cotier": "côtier",
            "montagne": "montagne",
            "bord_eau": "bord d'eau",
            "patrimoine": "patrimoine",
        }
        return labels.get(normalized, normalized or "biome")

    def _poi_category_label(self, category: str) -> str:
        labels = {
            "viewpoint": "panorama",
            "water": "eau",
            "summit": "sommet",
            "nature": "nature",
            "heritage": "patrimoine",
            "facility": "services",
            "start_access": "acces",
        }
        return labels.get(category, category)

    def _compute_poi_category_match(
        self,
        *,
        route: RouteCandidate,
        desired_categories: list[str],
    ) -> float:
        desired = {
            value.strip().lower()
            for value in desired_categories
            if isinstance(value, str) and value.strip()
        }
        if not desired:
            return 0.0
        available = {poi.category for poi in route.pois}
        matched = len(desired & available)
        return matched / max(1, len(desired))

    def _compute_biome_affinity(self, *, route: RouteCandidate, biome: str | None) -> float:
        normalized = (biome or "").strip().lower()
        if not normalized:
            return 0.5

        category_counts: dict[str, int] = {}
        for poi in route.pois:
            category_counts[poi.category] = category_counts.get(poi.category, 0) + 1

        def cat_signal(category: str, cap: float = 2.0) -> float:
            return max(0.0, min(1.0, category_counts.get(category, 0) / cap))

        water_signal = cat_signal("water", cap=2.0)
        nature_poi_signal = cat_signal("nature", cap=2.0)
        viewpoint_signal = max(cat_signal("viewpoint", cap=2.0), cat_signal("summit", cap=2.0))
        heritage_signal = cat_signal("heritage", cap=2.0)

        gain_per_km = (
            route.estimated_elevation_gain_m / route.distance_km
            if route.distance_km > 0
            else 0.0
        )
        hilly_signal = max(0.0, min(1.0, gain_per_km / 70.0))
        flat_signal = 1.0 - hilly_signal
        urban_index = (route.road_ratio * 0.65) + ((1.0 - route.quiet_score) * 0.35)
        rural_signal = max(0.0, min(1.0, 1.0 - urban_index))
        road_penalty = max(0.0, route.road_ratio - 0.25)
        urban_penalty = max(0.0, urban_index - 0.55)

        def _clamp(value: float) -> float:
            return max(0.0, min(1.0, value))

        affinities: dict[str, float] = {
            "foret": _clamp(
                route.nature_score * 0.50
                + route.trail_ratio * 0.22
                + route.quiet_score * 0.10
                + nature_poi_signal * 0.18
                - road_penalty * 0.90
                - urban_penalty * 0.75
            ),
            "campagne": _clamp(
                rural_signal * 0.35
                + route.quiet_score * 0.20
                + flat_signal * 0.20
                + route.nature_score * 0.20
                + route.trail_ratio * 0.10
                - max(0.0, route.road_ratio - 0.40) * 0.30
            ),
            "cotier": _clamp(
                water_signal * 0.70
                + viewpoint_signal * 0.20
                + rural_signal * 0.10
            ),
            "montagne": _clamp(
                hilly_signal * 0.45
                + viewpoint_signal * 0.30
                + route.trail_ratio * 0.15
                + route.nature_score * 0.10
            ),
            "bord_eau": _clamp(
                water_signal * 0.80
                + route.nature_score * 0.10
                + route.quiet_score * 0.10
            ),
            "patrimoine": _clamp(
                heritage_signal * 0.70
                + rural_signal * 0.15
                + route.quiet_score * 0.15
            ),
        }

        affinity = affinities.get(normalized, 0.5)
        return round(max(0.0, min(1.0, affinity)), 3)

    def _build_score_breakdown(
        self,
        *,
        route: RouteCandidate,
        search: UserSearch,
        base_score: float,
        poi_weight: float,
    ) -> dict[str, float]:
        distance_score = self._compute_distance_score(
            target_distance_km=search.target_distance_km,
            actual_distance_km=route.distance_km,
        )
        elevation_score = self._score_elevation(
            elevation_gain_m=route.estimated_elevation_gain_m,
            distance_km=route.distance_km,
            target="flat" if search.terrain == "plat" else ("hilly" if search.terrain == "vallonne" else "neutral"),
        )
        biome_affinity = self._compute_biome_affinity(route=route, biome=search.biome_preference)
        biome_breakdown_value = biome_affinity if search.biome_preference else 0.0
        poi_match = self._compute_poi_category_match(
            route=route,
            desired_categories=search.desired_poi_categories,
        )
        return {
            "distance": round(distance_score, 3),
            "sentiers": round(route.trail_ratio, 3),
            "nature": round(route.nature_score, 3),
            "calme": round(route.quiet_score, 3),
            "suitability": round(route.hiking_suitability_score, 3),
            "denivele": round(elevation_score, 3),
            "poi": round(route.poi_score, 3),
            "poi_match": round(poi_match, 3),
            "biome": round(biome_breakdown_value, 3),
            "poi_weight": round(poi_weight, 3),
            "context": round(route.context_score_delta, 3),
            "repetition": round(-0.04 if route.seen_before else 0.0, 3),
            "base": round(base_score, 3),
            "final": round(route.score, 3),
        }

    def _build_explanation_reasons(self, route: RouteCandidate) -> list[str]:
        reasons: list[tuple[str, float]] = []
        breakdown = route.score_breakdown

        if breakdown.get("distance", 0.0) >= 0.85:
            reasons.append(("Tres proche de la distance demandee", breakdown["distance"]))
        if route.road_ratio <= 0.2:
            reasons.append(("Peu de routes", 1.0 - route.road_ratio))
        if route.trail_ratio >= 0.6:
            reasons.append(("Majoritairement sur sentiers", route.trail_ratio))
        if route.nature_score >= 0.65:
            reasons.append(("Ambiance nature marquee", route.nature_score))
        if route.quiet_score >= 0.65:
            reasons.append(("Parcours plutot calme", route.quiet_score))
        if route.poi_score >= 0.55 and len(route.highlighted_poi_labels) > 0:
            reasons.append((f"Presence de POI: {', '.join(route.highlighted_poi_labels[:2])}", route.poi_score))
        if breakdown.get("poi_match", 0.0) >= 0.66:
            reasons.append(("Correspond aux POI recherches", breakdown["poi_match"]))
        if breakdown.get("biome", 0.0) >= 0.65:
            reasons.append(("Correspond bien au biome souhaite", breakdown["biome"]))
        if route.difficulty == "facile":
            reasons.append(("Niveau accessible", 0.55))

        reasons.sort(key=lambda item: item[1], reverse=True)
        return [text for text, _ in reasons[:3]]

    def _build_explanation_sentence(self, route: RouteCandidate) -> str:
        reasons = route.explanation_reasons[:3]
        if len(reasons) == 0:
            return "Parcours retenu pour son bon equilibre global."
        if len(reasons) == 1:
            return f"Parcours choisi car {reasons[0].lower()}."
        if len(reasons) == 2:
            return f"Parcours choisi pour {reasons[0].lower()} et {reasons[1].lower()}."
        return (
            "Parcours choisi pour "
            f"{reasons[0].lower()}, {reasons[1].lower()} et {reasons[2].lower()}."
        )

    def _build_route_description(self, route: RouteCandidate) -> str:
        poi_part = ""
        if route.poi_on_route_count > 0:
            poi_part = f" {route.poi_on_route_count} POI directement sur le trace."
        elif route.poi_near_route_count > 0:
            poi_part = f" {route.poi_near_route_count} POI a proximite."
        return (
            f"Boucle de {route.distance_km:.2f} km en {route.estimated_duration_min} min, "
            f"denivele {route.estimated_elevation_gain_m} m, difficulte {route.difficulty}."
            f"{poi_part}"
        )

    def _build_stable_route_id(self, route: RouteCandidate) -> str:
        if len(route.points) == 0:
            return route.id
        points_key = "|".join(
            f"{round(point.latitude, 5)}:{round(point.longitude, 5)}"
            for point in route.points[:: max(1, len(route.points) // 24)]
        )
        raw = f"{route.distance_km:.2f}|{route.route_type}|{points_key}"
        digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
        return f"rte-{digest}"

    def _register_shared_route(self, route: RouteCandidate) -> None:
        self._cleanup_shared_routes()
        if route.stable_route_id:
            _shared_route_cache[route.stable_route_id] = (time.time(), copy.deepcopy(route))

    def _cleanup_shared_routes(self) -> None:
        now = time.time()
        expired = [route_id for route_id, (ts, _) in _shared_route_cache.items() if now - ts > _SHARED_ROUTE_TTL_S]
        for route_id in expired:
            _shared_route_cache.pop(route_id, None)

    def _style_from_route_type(self, route_type: str) -> dict[str, Any]:
        parts = [token.strip() for token in route_type.split("+") if token.strip()]
        ambiance = parts[0] if len(parts) > 0 else None
        terrain = parts[1] if len(parts) > 1 else None
        effort = parts[2] if len(parts) > 2 else None
        biome_preference = parts[3] if len(parts) > 3 else None
        return self._build_combined_style(
            ambiance=ambiance,
            terrain=terrain,
            effort=effort,
            biome_preference=biome_preference,
        )

    def _estimate_duration_min(
        self,
        distance_km: float,
        elevation_gain_m: int | float,
        trail_ratio: float,
    ) -> int:
        """Naismith's rule adapted for hiking:
        - 4.5 km/h base speed, slower on technical trails
        - +1h per 600m of positive elevation gain"""
        trail_slow_factor = 1.0 + trail_ratio * 0.15
        effective_speed_kmh = 4.5 / trail_slow_factor
        walking_min = (distance_km / effective_speed_kmh) * 60.0
        elevation_min = (elevation_gain_m / 600.0) * 60.0
        return max(5, int(round(walking_min + elevation_min)))

    def _compute_difficulty(
        self,
        distance_km: float,
        elevation_gain_m: int | float,
        trail_ratio: float,
    ) -> str:
        """Three-level difficulty based on effective distance (Gorge metric)."""
        # 100m elevation ~= 1km effective distance
        effective_km = distance_km + elevation_gain_m / 100.0
        # Technical trails add roughness
        terrain_factor = 1.0 + trail_ratio * 0.20
        difficulty_score = effective_km * terrain_factor

        if difficulty_score < 7:
            return "facile"
        if difficulty_score < 15:
            return "moderee"
        return "soutenue"

    def _compute_tags(
        self,
        trail_ratio: float,
        road_ratio: float,
        nature_score: float,
        quiet_score: float,
        suitability_score: float,
        elevation_gain_m: int | float,
        distance_km: float,
        trail_score: float = 0.5,
        distance_score: float = 0.5,
    ) -> list[str]:
        tags: list[str] = []

        # Surface
        if trail_ratio >= 0.7:
            tags.append("Sentiers dominants")
        elif trail_ratio >= 0.4:
            tags.append("Bon mix sentiers")

        if road_ratio < 0.05:
            tags.append("Sans route")
        elif road_ratio < 0.2:
            tags.append("Tres peu de routes")
        elif road_ratio >= 0.6:
            tags.append("Passage routier")

        # Nature
        if nature_score >= 0.7:
            tags.append("Tres nature")
        elif nature_score >= 0.5:
            tags.append("Cadre verdoyant")

        # Calme
        if quiet_score >= 0.7:
            tags.append("Tres calme")
        elif quiet_score >= 0.5:
            tags.append("Ambiance tranquille")

        # Suitability
        if suitability_score >= 0.7:
            tags.append("Ideal randonnee")

        # Precision de la distance
        if distance_score >= 0.95:
            tags.append("Distance exacte")
        elif distance_score >= 0.85:
            tags.append("Tres proche")

        # Denivele
        gain_per_km = (elevation_gain_m / distance_km) if distance_km > 0 else 0.0
        if gain_per_km >= 80:
            tags.append("Tres vallonne")
        elif gain_per_km >= 35:
            tags.append("Quelques deniveles")
        else:
            tags.append("Terrain plat")

        # Best-profile designation - "Ideal pour X"
        # Score this route against each named profile using its key characteristics
        flat_score = max(0.0, min(1.0, 1.0 - gain_per_km / 50.0))
        hilly_score = max(0.0, min(1.0, gain_per_km / 100.0))

        profile_fits: dict[str, float] = {
            "sentiers": trail_score * 0.55 + nature_score * 0.20 + quiet_score * 0.15 + suitability_score * 0.10,
            "nature": nature_score * 0.45 + quiet_score * 0.25 + trail_score * 0.20 + suitability_score * 0.10,
            "calme": quiet_score * 0.55 + nature_score * 0.20 + trail_score * 0.15 + flat_score * 0.10,
            "sportif": hilly_score * 0.45 + suitability_score * 0.30 + trail_score * 0.15 + distance_score * 0.10,
            "promenade": flat_score * 0.40 + quiet_score * 0.30 + nature_score * 0.20 + distance_score * 0.10,
        }

        label_map = {
            "sentiers": "Ideal : sentiers",
            "nature": "Ideal : nature",
            "calme": "Ideal : calme",
            "sportif": "Ideal : sportif",
            "promenade": "Ideal : promenade",
        }

        best_profile = max(profile_fits, key=lambda k: profile_fits[k])
        best_score = profile_fits[best_profile]
        # Only add the designation if the route clearly fits a profile (threshold 0.5)
        if best_score >= 0.5:
            tags.append(label_map[best_profile])

        return tags
