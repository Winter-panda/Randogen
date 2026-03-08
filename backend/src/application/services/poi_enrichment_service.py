from __future__ import annotations

import math
from dataclasses import dataclass

from src.domain.entities.point_of_interest import PointOfInterest
from src.domain.entities.route_candidate import RouteCandidate
from src.domain.entities.route_point import RoutePoint
from src.domain.entities.user_search import UserSearch
from src.infrastructure.poi.osm_poi_client import OsmPoiCandidate, OsmPoiClient


@dataclass
class _ClassifiedPoi:
    category: str
    sub_category: str | None
    label: str


class PoiEnrichmentService:
    _ON_ROUTE_THRESHOLD_M = 80.0
    _MAX_ROUTE_DISTANCE_M = 220.0
    _MAX_ROUTE_DISTANCE_WATER_WAY_M = 2500.0
    _MAX_ROUTE_DISTANCE_NATURE_WAY_M = 1200.0
    _MAX_ROUTE_DISTANCE_VIEWPOINT_WAY_M = 800.0
    _MAX_ROUTE_DISTANCE_HERITAGE_WAY_M = 1200.0
    _DEDUP_DISTANCE_M = 35.0
    _MAX_POIS_PER_ROUTE = 15
    _MAX_HIGHLIGHTS = 5
    _CATEGORY_PRIORITY: tuple[str, ...] = (
        "viewpoint",
        "water",
        "summit",
        "heritage",
        "nature",
        "facility",
        "start_access",
    )

    _CATEGORY_WEIGHT: dict[str, float] = {
        "viewpoint": 1.00,
        "water": 0.90,
        "summit": 0.85,
        "heritage": 0.70,
        "nature": 0.60,
        "facility": 0.35,
        "start_access": 0.25,
    }

    def __init__(self, client: OsmPoiClient | None = None) -> None:
        self._client = client or OsmPoiClient()

    def enrich_route(self, route: RouteCandidate, search: UserSearch | None = None) -> RouteCandidate:
        if len(route.points) < 2:
            route.pois = []
            route.poi_score = 0.0
            route.poi_quantity_score = 0.0
            route.poi_diversity_score = 0.0
            route.poi_highlight_count = 0
            route.highlighted_poi_labels = []
            route.poi_highlights = []
            return route

        profile = self._parse_profile(route.route_type)
        candidates = self._client.fetch_candidates_for_route(route.points)
        if len(candidates) == 0:
            route.pois = []
            route.poi_score = 0.0
            route.poi_quantity_score = 0.0
            route.poi_diversity_score = 0.0
            route.poi_highlight_count = 0
            route.highlighted_poi_labels = []
            route.poi_highlights = []
            return route

        projected_route = self._project_route(route.points)
        pois: list[PointOfInterest] = []
        for candidate in candidates:
            classified = self._classify(candidate)
            if classified is None:
                continue

            min_distance_m, distance_from_start_m = self._distance_point_to_route(
                lat=candidate.latitude,
                lon=candidate.longitude,
                route_points=route.points,
                projected_route=projected_route,
            )
            max_distance_m = self._candidate_max_distance_m(
                candidate=candidate,
                category=classified.category,
            )
            if min_distance_m > max_distance_m:
                continue

            poi = PointOfInterest(
                id=f"osm:{candidate.osm_id}",
                name=candidate.name or classified.label,
                category=classified.category,
                sub_category=classified.sub_category,
                latitude=candidate.latitude,
                longitude=candidate.longitude,
                distance_to_route_m=round(min_distance_m, 1),
                distance_from_start_m=round(distance_from_start_m, 1) if distance_from_start_m is not None else None,
                score=0.0,
                tags=self._build_tags(
                    classified=classified,
                    distance_to_route_m=min_distance_m,
                    max_distance_m=max_distance_m,
                ),
            )
            poi.score = round(
                self._score_poi(
                    poi=poi,
                    profile=profile,
                    search=search,
                    max_distance_m=max_distance_m,
                ),
                3,
            )
            pois.append(poi)

        if len(pois) == 0:
            route.pois = []
            route.poi_score = 0.0
            route.poi_quantity_score = 0.0
            route.poi_diversity_score = 0.0
            route.poi_highlight_count = 0
            route.highlighted_poi_labels = []
            route.poi_highlights = []
            return route

        deduped = self._deduplicate(pois)
        deduped.sort(key=lambda p: (-p.score, p.distance_to_route_m, p.name.lower()))
        selected = self._select_diverse_pois(deduped)

        route.pois = selected
        route.poi_quantity_score = round(self._compute_quantity_score(selected), 3)
        route.poi_diversity_score = round(self._compute_diversity_score(selected), 3)
        route.poi_score = round(
            self._compute_route_poi_score(
                pois=selected,
                quantity_score=route.poi_quantity_score,
                diversity_score=route.poi_diversity_score,
            ),
            3,
        )
        route.highlighted_poi_labels = self._build_highlight_labels(selected)
        route.poi_highlights = self._build_route_highlights(selected)
        route.poi_highlight_count = len(route.highlighted_poi_labels)
        self._append_poi_explanatory_tags(route=route, profile=profile)
        return route

    def _select_diverse_pois(self, pois: list[PointOfInterest]) -> list[PointOfInterest]:
        if len(pois) <= self._MAX_POIS_PER_ROUTE:
            return pois

        selected: list[PointOfInterest] = []
        used_ids: set[str] = set()

        for category in self._CATEGORY_PRIORITY:
            best = next((poi for poi in pois if poi.category == category), None)
            if best is None or best.id in used_ids:
                continue
            selected.append(best)
            used_ids.add(best.id)
            if len(selected) >= self._MAX_POIS_PER_ROUTE:
                return selected

        for poi in pois:
            if poi.id in used_ids:
                continue
            selected.append(poi)
            used_ids.add(poi.id)
            if len(selected) >= self._MAX_POIS_PER_ROUTE:
                break

        return selected

    def _classify(self, candidate: OsmPoiCandidate) -> _ClassifiedPoi | None:
        tags = candidate.tags
        tourism = tags.get("tourism")
        natural = tags.get("natural")
        scenic = tags.get("scenic")
        amenity = tags.get("amenity")
        leisure = tags.get("leisure")
        waterway = tags.get("waterway")
        water = tags.get("water")
        landuse = tags.get("landuse")
        man_made = tags.get("man_made")
        historic = tags.get("historic")
        boundary = tags.get("boundary")
        building = tags.get("building")
        religion = tags.get("religion")

        if tourism == "viewpoint" or scenic == "yes" or man_made in {"tower", "obelisk"}:
            return _ClassifiedPoi("viewpoint", "viewpoint", "Point de vue")
        if natural == "peak":
            return _ClassifiedPoi("summit", "peak", "Sommet")
        if natural == "waterfall":
            return _ClassifiedPoi("water", "waterfall", "Cascade")
        if natural == "spring" or amenity == "drinking_water":
            return _ClassifiedPoi("facility", "drinking_water", "Fontaine")
        if (
            natural in {"water", "wetland"}
            or waterway
            or water in {"lake", "river", "reservoir", "pond", "canal"}
            or landuse == "reservoir"
        ):
            return _ClassifiedPoi("water", "water", "Lac / riviere")
        if natural == "wood" or landuse == "forest" or leisure in {"park", "nature_reserve"} or boundary == "protected_area":
            return _ClassifiedPoi("nature", natural or leisure or "nature", "Foret / parc")
        if historic == "castle" or building == "castle":
            return _ClassifiedPoi("heritage", "castle", "Chateau")
        if historic in {"monument", "ruins", "archaeological_site"}:
            return _ClassifiedPoi("heritage", historic, "Patrimoine")
        if amenity == "place_of_worship" or building in {"church", "cathedral", "chapel"}:
            sub = building or "place_of_worship"
            if religion:
                sub = f"{sub}:{religion}"
            return _ClassifiedPoi("heritage", sub, "Eglise / chapelle")
        if historic or tourism in {"attraction", "museum", "gallery", "artwork"}:
            return _ClassifiedPoi("heritage", historic or tourism, "Patrimoine")
        if amenity == "parking":
            return _ClassifiedPoi("start_access", "parking", "Parking depart")
        if amenity == "shelter":
            return _ClassifiedPoi("facility", "shelter", "Abri")
        if tourism == "picnic_site":
            return _ClassifiedPoi("facility", "picnic_site", "Pique-nique")
        if amenity == "bench":
            return _ClassifiedPoi("facility", "bench", "Banc")
        if tourism == "information":
            return _ClassifiedPoi("start_access", "information", "Depart")
        return None

    def _build_tags(
        self,
        *,
        classified: _ClassifiedPoi,
        distance_to_route_m: float,
        max_distance_m: float,
    ) -> list[str]:
        tags = [classified.category]
        if classified.sub_category:
            tags.append(classified.sub_category)
        tags.append("on_route" if distance_to_route_m <= self._ON_ROUTE_THRESHOLD_M else "near_route")
        if max_distance_m > self._MAX_ROUTE_DISTANCE_M:
            tags.append("coarse_geometry")
        return tags

    def _candidate_max_distance_m(self, *, candidate: OsmPoiCandidate, category: str) -> float:
        if candidate.osm_type in {"way", "relation"}:
            if category == "water":
                return self._MAX_ROUTE_DISTANCE_WATER_WAY_M
            if category == "nature":
                return self._MAX_ROUTE_DISTANCE_NATURE_WAY_M
            if category == "viewpoint":
                return self._MAX_ROUTE_DISTANCE_VIEWPOINT_WAY_M
            if category == "heritage":
                return self._MAX_ROUTE_DISTANCE_HERITAGE_WAY_M
        return self._MAX_ROUTE_DISTANCE_M

    def _score_poi(
        self,
        *,
        poi: PointOfInterest,
        profile: set[str],
        search: UserSearch | None,
        max_distance_m: float,
    ) -> float:
        category_weight = self._CATEGORY_WEIGHT.get(poi.category, 0.5)
        category_weight *= self._category_profile_multiplier(category=poi.category, profile=profile, search=search)
        if poi.distance_to_route_m <= self._ON_ROUTE_THRESHOLD_M:
            proximity = 1.0
        else:
            span = max_distance_m - self._ON_ROUTE_THRESHOLD_M
            proximity = max(0.0, 1.0 - ((poi.distance_to_route_m - self._ON_ROUTE_THRESHOLD_M) / max(1.0, span)))
        return (category_weight * 0.7) + (proximity * 0.3)

    def _compute_route_poi_score(
        self,
        *,
        pois: list[PointOfInterest],
        quantity_score: float,
        diversity_score: float,
    ) -> float:
        if len(pois) == 0:
            return 0.0
        top = pois[:3]
        quality_score = max(0.0, min(1.0, sum(p.score for p in top) / len(top)))
        return max(0.0, min(1.0, (quality_score * 0.50) + (diversity_score * 0.30) + (quantity_score * 0.20)))

    def _compute_quantity_score(self, pois: list[PointOfInterest]) -> float:
        return max(0.0, min(1.0, len(pois) / self._MAX_POIS_PER_ROUTE))

    def _compute_diversity_score(self, pois: list[PointOfInterest]) -> float:
        category_count = len({poi.category for poi in pois})
        if category_count <= 1:
            return 0.30
        if category_count == 2:
            return 0.70
        if category_count == 3:
            return 0.90
        return 1.00

    def _build_highlight_labels(self, pois: list[PointOfInterest]) -> list[str]:
        label_map = {
            "viewpoint": "Point de vue",
            "waterfall": "Cascade",
            "water": "Lac / riviere",
            "peak": "Sommet",
            "castle": "Chateau",
            "monument": "Monument",
            "ruins": "Ruines",
            "archaeological_site": "Site archeologique",
            "church": "Eglise",
            "cathedral": "Cathedrale",
            "chapel": "Chapelle",
            "heritage": "Patrimoine",
            "drinking_water": "Fontaine",
            "shelter": "Abri",
            "picnic_site": "Pique-nique",
            "bench": "Banc",
            "parking": "Parking depart",
        }

        labels: list[str] = []
        for poi in pois:
            key = poi.sub_category or poi.category
            label = label_map.get(key, poi.name)
            if label not in labels:
                labels.append(label)
            if len(labels) >= self._MAX_HIGHLIGHTS:
                break
        return labels

    def _build_route_highlights(self, pois: list[PointOfInterest]) -> list[str]:
        if len(pois) == 0:
            return []

        by_category: dict[str, int] = {}
        for poi in pois:
            by_category[poi.category] = by_category.get(poi.category, 0) + 1

        category_label = {
            "viewpoint": "point de vue",
            "water": "point d'eau",
            "summit": "sommet",
            "nature": "zone boisee",
            "heritage": "point patrimoine",
            "facility": "point pratique",
            "start_access": "acces depart",
        }

        ordered = sorted(by_category.items(), key=lambda item: item[1], reverse=True)
        parts = [
            f"{count} {category_label.get(category, category)}"
            for category, count in ordered[:3]
        ]

        highlights: list[str] = []
        if parts:
            highlights.append(", ".join(parts))

        categories = {category for category, _ in ordered}
        if "heritage" in categories and by_category.get("heritage", 0) >= 2:
            highlights.append("Parcours riche en patrimoine")
        if ("water" in categories and "viewpoint" in categories) or ("water" in categories and "nature" in categories):
            highlights.append("Balade variee avec eau et panorama")
        elif len(categories) >= 3:
            highlights.append("Parcours varie avec plusieurs points d'interet")

        return highlights[:3]

    def _append_poi_explanatory_tags(self, *, route: RouteCandidate, profile: set[str]) -> None:
        category_set = {poi.category for poi in route.pois}
        sub_category_set = {poi.sub_category for poi in route.pois if poi.sub_category}
        tags_to_add: list[str] = []

        if "viewpoint" in category_set or "summit" in category_set:
            tags_to_add.append("Beau point de vue")
        if "water" in category_set:
            tags_to_add.append("Passage en bord d'eau")
        if "heritage" in category_set:
            tags_to_add.append("Interet patrimonial")
        if "start_access" in category_set or "parking" in sub_category_set:
            tags_to_add.append("Depart pratique")
        if "promenade" in profile and {"water", "nature", "heritage", "facility"} & category_set:
            tags_to_add.append("Ideal promenade decouverte")

        for tag in tags_to_add:
            if tag not in route.tags:
                route.tags.append(tag)

    def _parse_profile(self, route_type: str) -> set[str]:
        return {
            token.strip().lower()
            for token in route_type.split("+")
            if token.strip()
        }

    def _category_profile_multiplier(
        self,
        *,
        category: str,
        profile: set[str],
        search: UserSearch | None,
    ) -> float:
        factor = 1.0

        if "nature" in profile:
            if category in {"water", "nature", "viewpoint"}:
                factor *= 1.20
        if "calme" in profile:
            if category in {"heritage", "start_access"}:
                factor *= 0.90
            if category in {"water", "nature"}:
                factor *= 1.10
        if "sentiers" in profile:
            factor *= 0.95
        if "promenade" in profile:
            if category in {"heritage", "facility", "water", "nature"}:
                factor *= 1.15
        if "sportif" in profile:
            if category in {"summit", "viewpoint", "water"}:
                factor *= 1.15
            if category == "facility":
                factor *= 0.85

        if search is not None:
            if search.prioritize_nature and category in {"nature", "water", "viewpoint"}:
                factor *= 1.20
            if search.prioritize_viewpoints and category in {"viewpoint", "summit"}:
                factor *= 1.25
            if search.prioritize_calm and category in {"nature", "water"}:
                factor *= 1.10
            if search.avoid_touristic and category in {"heritage", "start_access"}:
                factor *= 0.75

        return max(0.6, min(1.4, factor))

    def _deduplicate(self, pois: list[PointOfInterest]) -> list[PointOfInterest]:
        kept: list[PointOfInterest] = []
        for poi in sorted(pois, key=lambda p: (-p.score, p.distance_to_route_m)):
            duplicate_index: int | None = None
            for index, existing in enumerate(kept):
                same_name = poi.name.strip().lower() == existing.name.strip().lower()
                close = self._haversine_m(
                    poi.latitude,
                    poi.longitude,
                    existing.latitude,
                    existing.longitude,
                ) <= self._DEDUP_DISTANCE_M
                same_category_no_name = (
                    (not poi.name.strip() or not existing.name.strip())
                    and poi.category == existing.category
                    and close
                )
                if close and (same_name or same_category_no_name):
                    duplicate_index = index
                    break

            if duplicate_index is None:
                kept.append(poi)
                continue

            if poi.score > kept[duplicate_index].score:
                kept[duplicate_index] = poi
        return kept

    def _project_route(self, points: list[RoutePoint]) -> tuple[float, float, list[tuple[float, float]], list[float]]:
        ref_lat = points[0].latitude
        ref_lon = points[0].longitude
        projected = [self._to_xy_m(p.latitude, p.longitude, ref_lat, ref_lon) for p in points]

        cumulative = [0.0]
        total = 0.0
        for index in range(len(projected) - 1):
            ax, ay = projected[index]
            bx, by = projected[index + 1]
            total += math.hypot(bx - ax, by - ay)
            cumulative.append(total)
        return ref_lat, ref_lon, projected, cumulative

    def _distance_point_to_route(
        self,
        *,
        lat: float,
        lon: float,
        route_points: list[RoutePoint],
        projected_route: tuple[float, float, list[tuple[float, float]], list[float]],
    ) -> tuple[float, float | None]:
        ref_lat, ref_lon, route_xy, cumulative = projected_route
        px, py = self._to_xy_m(lat, lon, ref_lat, ref_lon)

        best_distance = float("inf")
        best_along: float | None = None

        for index in range(len(route_xy) - 1):
            ax, ay = route_xy[index]
            bx, by = route_xy[index + 1]
            seg_dx = bx - ax
            seg_dy = by - ay
            seg_len_sq = (seg_dx * seg_dx) + (seg_dy * seg_dy)
            if seg_len_sq == 0:
                dist = math.hypot(px - ax, py - ay)
                along = cumulative[index]
            else:
                t = ((px - ax) * seg_dx + (py - ay) * seg_dy) / seg_len_sq
                t = max(0.0, min(1.0, t))
                nearest_x = ax + (t * seg_dx)
                nearest_y = ay + (t * seg_dy)
                dist = math.hypot(px - nearest_x, py - nearest_y)
                along = cumulative[index] + (math.sqrt(seg_len_sq) * t)

            if dist < best_distance:
                best_distance = dist
                best_along = along

        # Fallback for degenerate routes.
        if not math.isfinite(best_distance):
            best_distance = self._haversine_m(
                lat,
                lon,
                route_points[0].latitude,
                route_points[0].longitude,
            )
            best_along = 0.0

        return best_distance, best_along

    @staticmethod
    def _to_xy_m(lat: float, lon: float, ref_lat: float, ref_lon: float) -> tuple[float, float]:
        earth_radius_m = 6_371_000.0
        x = math.radians(lon - ref_lon) * earth_radius_m * math.cos(math.radians(ref_lat))
        y = math.radians(lat - ref_lat) * earth_radius_m
        return x, y

    @staticmethod
    def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
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
