from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

from src.domain.entities.route_candidate import RouteCandidate
from src.domain.entities.route_point import RoutePoint
from src.domain.entities.user_search import UserSearch
from src.infrastructure.config.settings import settings
from src.infrastructure.routing.ors_client import OrsClient, OrsClientError, OrsRateLimitError

# Module-level TTL cache: key → (timestamp, results)
_route_cache: dict[str, tuple[float, list[RouteCandidate]]] = {}
_CACHE_TTL_S: float = 300.0  # 5 minutes


@dataclass
class CandidateEvaluation:
    route: RouteCandidate
    score_value: float
    distance_error_ratio: float
    trail_preference_score: float
    road_share: float


class RouteGenerationService:
    def __init__(self) -> None:
        self._ors_client = OrsClient(
            api_key=settings.ors_api_key,
            base_url=settings.ors_base_url,
            profile=settings.ors_profile,
            timeout_s=settings.ors_request_timeout_s,
        )

    def generate_routes(self, search: UserSearch) -> list[RouteCandidate]:
        logger.info(
            "generate_routes: enable_real_routing=%s is_configured=%s",
            settings.enable_real_routing,
            self._ors_client.is_configured(),
        )
        if settings.enable_real_routing and self._ors_client.is_configured():
            cache_key = self._make_cache_key(search)
            cached = _route_cache.get(cache_key)
            if cached is not None:
                ts, routes = cached
                if time.time() - ts < _CACHE_TTL_S:
                    logger.info("generate_routes: cache hit (age=%.0fs)", time.time() - ts)
                    return routes
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
                _route_cache[cache_key] = (time.time(), real_routes)
                return real_routes

        logger.warning("generate_routes: falling back to mock routes")
        return self._generate_mock_routes(search)

    @staticmethod
    def _make_cache_key(search: UserSearch) -> str:
        return (
            f"{search.latitude:.5f}:{search.longitude:.5f}"
            f":{search.target_distance_km}:{search.route_count}"
            f":{search.ambiance}:{search.terrain}:{search.effort}"
        )

    def _generate_real_round_trip_routes(self, search: UserSearch) -> list[RouteCandidate]:
        evaluations: list[CandidateEvaluation] = []

        style = self._build_combined_style(search.ambiance, search.terrain, search.effort)
        attempts = min(max(search.route_count * 2, settings.route_candidate_search_count), 12)
        target_length_m = search.target_distance_km * 1000.0

        request_nonce = int(time.time_ns() % 1_000_000_000)
        rng = random.Random(request_nonce)

        rate_limit_errors = 0
        other_errors = 0

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
                continue

            max_gain_per_km = style.get("max_elevation_gain_per_km")
            if max_gain_per_km is not None and actual_distance_km > 0:
                if elevation_gain_m / actual_distance_km > max_gain_per_km:
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
                route_type=self._build_route_type_label(search.ambiance, search.terrain, search.effort),
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
            "generate_routes: loop done — %d evaluations, %d rate-limit errors, %d other errors",
            len(evaluations),
            rate_limit_errors,
            other_errors,
        )

        if len(evaluations) == 0:
            return []

        evaluations.sort(
            key=lambda item: (
                -item.score_value,
                -item.trail_preference_score,
                item.road_share,
                item.distance_error_ratio,
                item.route.distance_km,
            )
        )

        return self._select_routes(evaluations, search.route_count, style["max_road_share"])

    def _select_routes(
        self,
        evaluations: list[CandidateEvaluation],
        count: int,
        max_road_share: float,
    ) -> list[RouteCandidate]:
        """Two-pass selection: prefer routes under max_road_share, fill remaining with best available.
        Routes too similar (Jaccard ≥ threshold) to an already-selected route are skipped."""
        selected: list[RouteCandidate] = []
        selected_grids: list[frozenset[str]] = []
        used_signatures: set[str] = set()
        threshold = settings.route_duplicate_similarity_threshold

        def _try_add(evaluation: CandidateEvaluation, road_share_limit: float) -> bool:
            if evaluation.road_share > road_share_limit:
                return False
            signature = self._build_route_signature(evaluation.route)
            if signature in used_signatures:
                return False
            grid = self._build_route_grid(evaluation.route)
            for existing_grid in selected_grids:
                if self._jaccard_similarity(grid, existing_grid) >= threshold:
                    return False
            used_signatures.add(signature)
            selected_grids.append(grid)
            route = evaluation.route
            route.id = f"route-{len(selected) + 1}"
            route.name = f"Parcours {len(selected) + 1}"
            selected.append(route)
            return True

        # Pass 1 — strict: respect the style's road share limit
        for evaluation in evaluations:
            if len(selected) >= count:
                break
            _try_add(evaluation, max_road_share)

        # Pass 2 — relaxed: fill missing slots with the best remaining candidates
        # (happens in dense urban areas where ideal trails are unavailable)
        if len(selected) < count:
            logger.info(
                "Only %d/%d routes passed strict road-share filter (%.0f%%), relaxing for remaining slots.",
                len(selected),
                count,
                max_road_share * 100,
            )
            for evaluation in evaluations:
                if len(selected) >= count:
                    break
                _try_add(evaluation, 1.0)

        return selected

    def _build_route_grid(self, route: RouteCandidate) -> frozenset[str]:
        """Return the set of ~200m grid cells the route passes through.
        Used for Jaccard-based similarity detection."""
        cells: set[str] = set()
        for point in route.points:
            # 0.002° ≈ 222m latitude, ≈ 140m longitude at mid-latitudes
            lat_cell = int(point.latitude * 500)
            lon_cell = int(point.longitude * 500)
            cells.add(f"{lat_cell}:{lon_cell}")
        return frozenset(cells)

    def _jaccard_similarity(self, grid_a: frozenset[str], grid_b: frozenset[str]) -> float:
        """Jaccard index between two grid-cell sets: |A∩B| / |A∪B|."""
        if not grid_a and not grid_b:
            return 1.0
        if not grid_a or not grid_b:
            return 0.0
        intersection = len(grid_a & grid_b)
        union = len(grid_a | grid_b)
        return intersection / union

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
                "elevation_target": "flat",
                "max_distance_error_ratio": 0.50,
                "max_road_share": 0.80,
                "max_elevation_gain_per_km": 25.0,
            },
        }

        return configs.get(normalized, configs["equilibree"])

    def _build_combined_style(
        self,
        ambiance: str | None,
        terrain: str | None,
        effort: str | None,
    ) -> dict[str, Any]:
        active = [self._get_style_config(k) for k in [ambiance, terrain, effort] if k is not None]
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
    ) -> str:
        parts = [p for p in [ambiance, terrain, effort] if p is not None]
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
            # 0m/km → 1.0, 50m/km → 0.0
            return round(max(0.0, min(1.0, 1.0 - gain_per_km / 50.0)), 2)
        if target == "hilly":
            # 0m/km → 0.0, 100m/km → 1.0
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
                route_type=self._build_route_type_label(search.ambiance, search.terrain, search.effort),
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

        return routes

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
        # 100m elevation ≈ 1km effective distance
        effective_km = distance_km + elevation_gain_m / 100.0
        # Technical trails add roughness
        terrain_factor = 1.0 + trail_ratio * 0.20
        difficulty_score = effective_km * terrain_factor

        if difficulty_score < 7:
            return "facile"
        if difficulty_score < 15:
            return "modérée"
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
            tags.append("Très peu de routes")
        elif road_ratio >= 0.6:
            tags.append("Passage routier")

        # Nature
        if nature_score >= 0.7:
            tags.append("Très nature")
        elif nature_score >= 0.5:
            tags.append("Cadre verdoyant")

        # Calme
        if quiet_score >= 0.7:
            tags.append("Très calme")
        elif quiet_score >= 0.5:
            tags.append("Ambiance tranquille")

        # Suitability
        if suitability_score >= 0.7:
            tags.append("Idéal randonnée")

        # Précision de la distance
        if distance_score >= 0.95:
            tags.append("Distance exacte")
        elif distance_score >= 0.85:
            tags.append("Très proche")

        # Dénivelé
        gain_per_km = (elevation_gain_m / distance_km) if distance_km > 0 else 0.0
        if gain_per_km >= 80:
            tags.append("Très vallonné")
        elif gain_per_km >= 35:
            tags.append("Quelques dénivelés")
        else:
            tags.append("Terrain plat")

        # Best-profile designation — "Idéal pour X"
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
            "sentiers": "Idéal : sentiers",
            "nature": "Idéal : nature",
            "calme": "Idéal : calme",
            "sportif": "Idéal : sportif",
            "promenade": "Idéal : promenade",
        }

        best_profile = max(profile_fits, key=lambda k: profile_fits[k])
        best_score = profile_fits[best_profile]
        # Only add the designation if the route clearly fits a profile (threshold 0.5)
        if best_score >= 0.5:
            tags.append(label_map[best_profile])

        return tags