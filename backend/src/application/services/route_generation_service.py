from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
import random
import time

logger = logging.getLogger(__name__)

from src.domain.entities.route_candidate import RouteCandidate
from src.domain.entities.route_point import RoutePoint
from src.domain.entities.user_search import UserSearch
from src.infrastructure.config.settings import settings
from src.infrastructure.routing.ors_client import OrsClient, OrsClientError


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
        if settings.enable_real_routing and self._ors_client.is_configured():
            real_routes = self._generate_real_round_trip_routes(search)
            if len(real_routes) > 0:
                return real_routes

        return self._generate_mock_routes(search)

    def _generate_real_round_trip_routes(self, search: UserSearch) -> list[RouteCandidate]:
        evaluations: list[CandidateEvaluation] = []

        style = self._get_style_config(search.hike_style)
        attempts = max(search.route_count * 5, settings.route_candidate_search_count * 2)
        target_length_m = search.target_distance_km * 1000.0

        request_nonce = int(time.time_ns() % 1_000_000_000)
        rng = random.Random(request_nonce)

        for index in range(attempts):
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
            except OrsClientError as exc:
                logger.warning("ORS request failed (attempt %d): %s", index, exc)
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

            final_score = self._combine_scores(
                distance_score=distance_score,
                trail_score=trail_score,
                green_score=green_score,
                quiet_score=quiet_score,
                suitability_score=suitability_score,
                style=style,
            )

            if distance_error_ratio > style["max_distance_error_ratio"]:
                continue

            if road_share > style["max_road_share"]:
                continue

            if final_score < settings.route_min_score:
                continue

            route = RouteCandidate(
                id=f"route-{index + 1}",
                name=f"Parcours {index + 1}",
                distance_km=round(actual_distance_km, 2),
                estimated_duration_min=max(1, int(round(result.duration_s / 60))),
                estimated_elevation_gain_m=0,
                score=final_score,
                route_type=search.hike_style,
                source=f"openrouteservice-roundtrip:{settings.ors_profile}",
                trail_ratio=self._compute_trail_ratio(result.extras),
                road_ratio=round(road_share, 2),
                nature_score=round(green_score, 2),
                quiet_score=round(quiet_score, 2),
                hiking_suitability_score=round(suitability_score, 2),
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

        selected: list[RouteCandidate] = []
        used_signatures: set[str] = set()

        for evaluation in evaluations:
            signature = self._build_route_signature(evaluation.route)
            if signature in used_signatures:
                continue

            used_signatures.add(signature)
            route = evaluation.route
            route.id = f"route-{len(selected) + 1}"
            route.name = f"Parcours {len(selected) + 1}"
            selected.append(route)

            if len(selected) >= search.route_count:
                break

        return selected

    def _get_style_config(self, hike_style: str) -> dict[str, float]:
        normalized = (hike_style or "equilibree").strip().lower()

        configs = {
            "equilibree": {
                "distance_weight": 0.45,
                "trail_weight": 0.25,
                "green_weight": 0.15,
                "quiet_weight": 0.10,
                "suitability_weight": 0.05,
                "max_distance_error_ratio": 0.50,
                "max_road_share": 0.65,
            },
            "sentiers": {
                "distance_weight": 0.30,
                "trail_weight": 0.45,
                "green_weight": 0.10,
                "quiet_weight": 0.10,
                "suitability_weight": 0.05,
                "max_distance_error_ratio": 0.60,
                "max_road_share": 0.40,
            },
            "nature": {
                "distance_weight": 0.30,
                "trail_weight": 0.25,
                "green_weight": 0.25,
                "quiet_weight": 0.15,
                "suitability_weight": 0.05,
                "max_distance_error_ratio": 0.60,
                "max_road_share": 0.50,
            },
            "calme": {
                "distance_weight": 0.35,
                "trail_weight": 0.20,
                "green_weight": 0.15,
                "quiet_weight": 0.25,
                "suitability_weight": 0.05,
                "max_distance_error_ratio": 0.60,
                "max_road_share": 0.55,
            },
        }

        return configs.get(normalized, configs["equilibree"])

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
        style: dict[str, float],
    ) -> float:
        total = (
            distance_score * style["distance_weight"]
            + trail_score * style["trail_weight"]
            + green_score * style["green_weight"]
            + quiet_score * style["quiet_weight"]
            + suitability_score * style["suitability_weight"]
        )
        return round(max(0.1, min(1.0, total)), 2)

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
        if len(route.points) == 0:
            return route.id

        sampled_indexes = [
            0,
            len(route.points) // 4,
            len(route.points) // 2,
            (3 * len(route.points)) // 4,
            len(route.points) - 1,
        ]

        sampled = []
        for index in sampled_indexes:
            point = route.points[index]
            sampled.append(f"{round(point.latitude, 4)}:{round(point.longitude, 4)}")

        return "|".join(sampled)

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
                route_type=search.hike_style,
                source="mock-generator",
                trail_ratio=0.25,
                road_ratio=0.75,
                nature_score=0.30,
                quiet_score=0.30,
                hiking_suitability_score=0.40,
                points=points,
            )
            routes.append(route)

        return routes