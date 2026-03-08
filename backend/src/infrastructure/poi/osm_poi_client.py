from __future__ import annotations

import json
import logging
import math
import time
import copy
from dataclasses import dataclass
from urllib import parse, request

from src.domain.entities.route_point import RoutePoint

logger = logging.getLogger(__name__)

_poi_cache: dict[str, tuple[float, list["OsmPoiCandidate"]]] = {}
_POI_CACHE_TTL_S: float = 600.0  # 10 minutes


@dataclass
class OsmPoiCandidate:
    osm_id: str
    osm_type: str
    name: str | None
    latitude: float
    longitude: float
    tags: dict[str, str]


class OsmPoiClient:
    _OVERPASS_URLS: tuple[str, ...] = (
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
        "https://overpass.openstreetmap.ru/api/interpreter",
    )
    _DEFAULT_MARGIN_M = 1600
    _FALLBACK_MARGIN_M = 3000
    _MIN_REASONABLE_CANDIDATE_COUNT = 6

    # Keep only hiking-relevant objects to avoid urban noise.
    _OVERPASS_FILTERS: tuple[str, ...] = (
        '["tourism"="viewpoint"]',
        '["natural"="peak"]',
        '["natural"="waterfall"]',
        '["natural"="spring"]',
        '["natural"="water"]',
        '["natural"="wetland"]',
        '["waterway"]',
        '["water"]',
        '["water"="pond"]',
        '["water"="lake"]',
        '["landuse"="reservoir"]',
        '["natural"="coastline"]',
        '["natural"="wood"]',
        '["landuse"="forest"]',
        '["leisure"="park"]',
        '["leisure"="nature_reserve"]',
        '["boundary"="protected_area"]',
        '["tourism"="attraction"]',
        '["tourism"="museum"]',
        '["tourism"="gallery"]',
        '["tourism"="artwork"]',
        '["man_made"="tower"]',
        '["man_made"="obelisk"]',
        '["historic"]',
        '["historic"="castle"]',
        '["historic"="monument"]',
        '["historic"="ruins"]',
        '["historic"="archaeological_site"]',
        '["amenity"="place_of_worship"]',
        '["building"="church"]',
        '["building"="cathedral"]',
        '["building"="chapel"]',
        '["building"="castle"]',
        '["amenity"="drinking_water"]',
        '["amenity"="shelter"]',
        '["tourism"="picnic_site"]',
        '["amenity"="bench"]',
        '["amenity"="parking"]',
        '["tourism"="information"]',
    )

    def fetch_candidates_for_route(
        self,
        points: list[RoutePoint],
        *,
        margin_m: int = _DEFAULT_MARGIN_M,
    ) -> list[OsmPoiCandidate]:
        if len(points) == 0:
            return []

        min_lat = min(p.latitude for p in points)
        max_lat = max(p.latitude for p in points)
        min_lon = min(p.longitude for p in points)
        max_lon = max(p.longitude for p in points)

        lat_margin = margin_m / 111_320.0
        center_lat = (min_lat + max_lat) / 2.0
        lon_margin = margin_m / (111_320.0 * max(0.2, abs(math.cos(math.radians(center_lat)))))

        south = min_lat - lat_margin
        west = min_lon - lon_margin
        north = max_lat + lat_margin
        east = max_lon + lon_margin

        cache_key = self._make_cache_key(south=south, west=west, north=north, east=east, margin_m=margin_m)
        cached = _poi_cache.get(cache_key)
        if cached is not None:
            ts, candidates = cached
            age_s = time.time() - ts
            if age_s < _POI_CACHE_TTL_S:
                logger.info("poi: cache hit (age=%.0fs)", age_s)
                return copy.deepcopy(candidates)
            _poi_cache.pop(cache_key, None)

        primary = self._fetch_bbox_candidates(south=south, west=west, north=north, east=east)
        result = primary

        if len(primary) < self._MIN_REASONABLE_CANDIDATE_COUNT and margin_m < self._FALLBACK_MARGIN_M:
            fallback_margin = max(self._FALLBACK_MARGIN_M, margin_m * 2)
            fallback_bbox = self._expand_bbox(
                south=south,
                west=west,
                north=north,
                east=east,
                extra_margin_m=fallback_margin - margin_m,
            )
            fallback = self._fetch_bbox_candidates(
                south=fallback_bbox[0],
                west=fallback_bbox[1],
                north=fallback_bbox[2],
                east=fallback_bbox[3],
            )
            result = self._merge_deduplicate(primary, fallback)
            logger.info(
                "poi: fallback query used (primary=%d fallback=%d merged=%d)",
                len(primary),
                len(fallback),
                len(result),
            )
        else:
            logger.info("poi: primary query returned %d candidates", len(primary))

        if len(result) < self._MIN_REASONABLE_CANDIDATE_COUNT:
            around_candidates = self._fetch_candidates_around_route_points(points)
            if len(around_candidates) > 0:
                result = self._merge_deduplicate(result, around_candidates)
                logger.info(
                    "poi: around-route fallback added %d candidates (merged=%d)",
                    len(around_candidates),
                    len(result),
                )

        _poi_cache[cache_key] = (time.time(), copy.deepcopy(result))
        return result

    def _fetch_bbox_candidates(
        self,
        *,
        south: float,
        west: float,
        north: float,
        east: float,
    ) -> list[OsmPoiCandidate]:
        query = self._build_bbox_query(south=south, west=west, north=north, east=east)
        return self._fetch_from_query(query)

    def _make_cache_key(self, *, south: float, west: float, north: float, east: float, margin_m: int) -> str:
        return (
            f"{round(south, 4)}:{round(west, 4)}:{round(north, 4)}:{round(east, 4)}"
            f":{int(margin_m)}:poi-v2"
        )

    def _expand_bbox(
        self,
        *,
        south: float,
        west: float,
        north: float,
        east: float,
        extra_margin_m: int,
    ) -> tuple[float, float, float, float]:
        if extra_margin_m <= 0:
            return south, west, north, east

        center_lat = (south + north) / 2.0
        lat_margin = extra_margin_m / 111_320.0
        lon_margin = extra_margin_m / (111_320.0 * max(0.2, abs(math.cos(math.radians(center_lat)))))
        return (
            south - lat_margin,
            west - lon_margin,
            north + lat_margin,
            east + lon_margin,
        )

    def _merge_deduplicate(
        self,
        first: list[OsmPoiCandidate],
        second: list[OsmPoiCandidate],
    ) -> list[OsmPoiCandidate]:
        merged: dict[str, OsmPoiCandidate] = {}
        for candidate in [*first, *second]:
            key = (
                f"{candidate.osm_id}:{round(candidate.latitude, 6)}:{round(candidate.longitude, 6)}"
            )
            merged[key] = candidate
        return list(merged.values())

    def _build_bbox_query(self, *, south: float, west: float, north: float, east: float) -> str:
        bbox = f"({south:.6f},{west:.6f},{north:.6f},{east:.6f})"
        lines = ["[out:json][timeout:20];", "("]
        for osm_filter in self._OVERPASS_FILTERS:
            lines.append(f"  node{osm_filter}{bbox};")
            lines.append(f"  way{osm_filter}{bbox};")
            lines.append(f"  relation{osm_filter}{bbox};")
        lines.extend([");", "out center tags;"])
        return "\n".join(lines)

    def _fetch_candidates_around_route_points(self, points: list[RoutePoint]) -> list[OsmPoiCandidate]:
        sampled = self._sample_route_points(points, max_points=24)
        if len(sampled) == 0:
            return []

        lines = ["[out:json][timeout:20];", "("]
        for point in sampled:
            lat = f"{point.latitude:.6f}"
            lon = f"{point.longitude:.6f}"
            lines.append(f'  node(around:260,{lat},{lon})["tourism"="viewpoint"];')
            lines.append(f'  node(around:260,{lat},{lon})["natural"="peak"];')
            lines.append(f'  node(around:260,{lat},{lon})["natural"="water"];')
            lines.append(f'  node(around:260,{lat},{lon})["natural"="waterfall"];')
            lines.append(f'  node(around:260,{lat},{lon})["waterway"];')
            lines.append(f'  way(around:260,{lat},{lon})["natural"="water"];')
            lines.append(f'  way(around:260,{lat},{lon})["waterway"];')
        lines.extend([");", "out center tags;"])
        query = "\n".join(lines)

        return self._fetch_from_query(query)

    def _sample_route_points(self, points: list[RoutePoint], max_points: int) -> list[RoutePoint]:
        if len(points) <= max_points:
            return points
        step = max(1, len(points) // max_points)
        sampled = [points[i] for i in range(0, len(points), step)]
        if sampled[-1] != points[-1]:
            sampled.append(points[-1])
        return sampled[:max_points]

    def _fetch_from_query(self, query: str) -> list[OsmPoiCandidate]:
        payload = parse.urlencode({"data": query}).encode("utf-8")
        data: dict | None = None
        last_error: Exception | None = None
        for overpass_url in self._OVERPASS_URLS:
            req = request.Request(
                overpass_url,
                data=payload,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
                    "Accept": "application/json",
                    "User-Agent": "Randogen/0.1 (+poi-enrichment)",
                },
                method="POST",
            )
            try:
                with request.urlopen(req, timeout=25) as response:
                    raw = response.read().decode("utf-8")
                data = json.loads(raw)
                break
            except Exception as exc:
                last_error = exc
                logger.warning("OSM POI fetch failed via %s: %s", overpass_url, exc)
                continue
        if data is None:
            if last_error is not None:
                logger.warning("OSM POI fetch failed on all endpoints: %s", last_error)
            return []

        elements = data.get("elements", [])
        candidates: list[OsmPoiCandidate] = []
        for element in elements:
            tags = element.get("tags", {})
            if not isinstance(tags, dict):
                continue
            lat, lon = self._extract_lat_lon(element)
            if lat is None or lon is None:
                continue
            osm_type = str(element.get("type", "node"))
            osm_id = str(element.get("id", ""))
            if not osm_id:
                continue
            candidates.append(
                OsmPoiCandidate(
                    osm_id=f"{osm_type}:{osm_id}",
                    osm_type=osm_type,
                    name=self._normalize_name(tags.get("name")),
                    latitude=float(lat),
                    longitude=float(lon),
                    tags={str(k): str(v) for k, v in tags.items()},
                )
            )
        return candidates

    @staticmethod
    def _extract_lat_lon(element: dict) -> tuple[float | None, float | None]:
        if "lat" in element and "lon" in element:
            return element.get("lat"), element.get("lon")
        center = element.get("center")
        if isinstance(center, dict):
            return center.get("lat"), center.get("lon")
        return None, None

    @staticmethod
    def _normalize_name(name: object) -> str | None:
        if name is None:
            return None
        value = str(name).strip()
        return value if value else None
