from __future__ import annotations

import json
import logging
import math
import time
import copy
from dataclasses import dataclass
from urllib import error as url_error
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
        "https://lz4.overpass-api.de/api/interpreter",
        "https://z.overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
        "https://overpass.openstreetmap.ru/api/interpreter",
    )
    _DEFAULT_MARGIN_M = 1800
    _FALLBACK_MARGIN_M = 3200
    _MIN_REASONABLE_CANDIDATE_COUNT = 6
    _QUERY_TIMEOUT_S = 14
    _MAX_CANDIDATES_PER_PASS = 220
    _FILTER_CHUNK_SIZE = 14
    _ROUTE_FETCH_BUDGET_S = 9.0
    _NEARBY_FETCH_BUDGET_S = 18.0
    _MIN_OVERPASS_INTERVAL_S = 0.55
    _DEFAULT_ENDPOINT_BACKOFF_S = 150.0
    _MAX_ENDPOINT_ATTEMPTS_PER_QUERY = 3
    _CACHE_FALLBACK_MAX_AGE_S = 45 * 60
    # Bump these versions to invalidate the in-memory cache after filter changes.
    _BBOX_CACHE_VERSION = "poi-v10"
    _AROUND_CACHE_VERSION = "poi-v9"

    # Filters are processed in chunks of _FILTER_CHUNK_SIZE.
    # IMPORTANT: keep one representative of each major family in chunk 1
    # so we still return mixed POIs when upstream endpoints are slow.
    _OVERPASS_FILTERS: tuple[str, ...] = (
        # --- chunk 1: mixed core categories (always fetched first) ---
        '["tourism"="viewpoint"]',
        '["natural"="peak"]',
        '["natural"="water"]',
        '["water"="lake"]',
        '["water"="pond"]',
        '["natural"="wood"]',
        '["landuse"="forest"]',
        '["leisure"="park"]',
        '["leisure"="garden"]',
        '["landuse"="recreation_ground"]',
        '["historic"]',
        '["amenity"="parking"]',
        '["amenity"="restaurant"]',
        '["amenity"="cafe"]',
        '["amenity"="parking_entrance"]',
        '["amenity"="place_of_worship"]',
        '["building"="church"]',
        # --- chunk 2: water/nature details ---
        '["natural"="waterfall"]',
        '["water"="reservoir"]',
        '["landuse"="reservoir"]',
        '["waterway"="riverbank"]',
        '["natural"="wetland"]',
        '["leisure"="nature_reserve"]',
        '["boundary"="protected_area"]',
        # --- chunk 3: heritage details ---
        '["historic"="castle"]',
        '["historic"="monument"]',
        '["historic"="ruins"]',
        '["historic"="archaeological_site"]',
        '["building"="cathedral"]',
        '["building"="chapel"]',
        '["building"="castle"]',
        '["tourism"="attraction"]',
        '["tourism"="museum"]',
        '["tourism"="gallery"]',
        '["tourism"="artwork"]',
        '["man_made"="tower"]',
        '["man_made"="obelisk"]',
        # --- chunk 4: service/access details ---
        '["natural"="spring"]',
        '["amenity"="drinking_water"]',
        '["amenity"="shelter"]',
        '["tourism"="picnic_site"]',
        '["amenity"="bench"]',
        '["amenity"="fast_food"]',
        '["amenity"="bar"]',
        '["amenity"="pub"]',
    )

    def __init__(self) -> None:
        self._last_fetch_error: str | None = None
        self._next_overpass_request_at: float = 0.0
        self._endpoint_backoff_until: dict[str, float] = {}

    def get_last_fetch_error(self) -> str | None:
        return self._last_fetch_error

    def fetch_candidates_for_route(
        self,
        points: list[RoutePoint],
        *,
        margin_m: int = _DEFAULT_MARGIN_M,
    ) -> list[OsmPoiCandidate]:
        if len(points) == 0:
            return []
        started_at = time.perf_counter()

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
        stale_candidates: list[OsmPoiCandidate] = []
        if cached is not None:
            ts, candidates = cached
            age_s = time.time() - ts
            if age_s < _POI_CACHE_TTL_S:
                logger.info("poi: cache hit (age=%.0fs)", age_s)
                self._last_fetch_error = None
                return copy.deepcopy(candidates)
            stale_candidates = copy.deepcopy(candidates)

        primary = self._fetch_bbox_candidates(
            south=south,
            west=west,
            north=north,
            east=east,
            deadline_s=started_at + self._ROUTE_FETCH_BUDGET_S,
        )
        result = primary

        if (
            len(primary) < self._MIN_REASONABLE_CANDIDATE_COUNT
            and margin_m < self._FALLBACK_MARGIN_M
            and (time.perf_counter() - started_at) < self._ROUTE_FETCH_BUDGET_S
        ):
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
                deadline_s=started_at + self._ROUTE_FETCH_BUDGET_S,
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

        if (
            len(result) < self._MIN_REASONABLE_CANDIDATE_COUNT
            and (time.perf_counter() - started_at) < self._ROUTE_FETCH_BUDGET_S
        ):
            around_candidates = self._fetch_candidates_around_route_points(
                points,
                deadline_s=started_at + self._ROUTE_FETCH_BUDGET_S,
            )
            if len(around_candidates) > 0:
                result = self._merge_deduplicate(result, around_candidates)
                logger.info(
                    "poi: around-route fallback added %d candidates (merged=%d)",
                    len(around_candidates),
                    len(result),
                )

        if len(result) == 0:
            cache_fallback = self._collect_cached_candidates_for_bbox(
                south=south,
                west=west,
                north=north,
                east=east,
                max_age_s=self._CACHE_FALLBACK_MAX_AGE_S,
            )
            if len(cache_fallback) > 0:
                logger.info(
                    "poi: using recent cache fallback in bbox (%d candidates)",
                    len(cache_fallback),
                )
                result = cache_fallback

        if len(result) == 0 and len(stale_candidates) > 0:
            logger.info("poi: using stale cache fallback (%d candidates)", len(stale_candidates))
            self._last_fetch_error = None
            _poi_cache[cache_key] = (time.time(), copy.deepcopy(stale_candidates))
            return stale_candidates

        if len(result) > 0:
            self._last_fetch_error = None
        _poi_cache[cache_key] = (time.time(), copy.deepcopy(result))
        return result

    def fetch_candidates_around_location(
        self,
        *,
        latitude: float,
        longitude: float,
        radius_m: int = 5000,
    ) -> list[OsmPoiCandidate]:
        radius_m = max(200, min(10_000, int(radius_m)))
        cache_key = f"around:{round(latitude, 3)}:{round(longitude, 3)}:{radius_m}:{self._AROUND_CACHE_VERSION}"
        cached = _poi_cache.get(cache_key)
        stale_candidates: list[OsmPoiCandidate] = []
        if cached is not None:
            ts, candidates = cached
            age_s = time.time() - ts
            if age_s < _POI_CACHE_TTL_S:
                logger.info("poi around: cache hit (age=%.0fs)", age_s)
                self._last_fetch_error = None
                return copy.deepcopy(candidates)
            stale_candidates = copy.deepcopy(candidates)

        result: list[OsmPoiCandidate] = []
        deadline_s = time.perf_counter() + self._NEARBY_FETCH_BUDGET_S
        for filters in self._iter_filter_chunks():
            if time.perf_counter() >= deadline_s:
                break
            query = self._build_around_query(
                latitude=latitude,
                longitude=longitude,
                radius_m=radius_m,
                filters=filters,
            )
            chunk = self._fetch_from_query(query, deadline_s=deadline_s)
            if len(chunk) > 0:
                result = self._merge_deduplicate(result, chunk)
            elif self._last_fetch_error and self._is_fatal_connection_error(self._last_fetch_error):
                break
        if len(result) == 0:
            cache_fallback = self._collect_cached_candidates_around_location(
                latitude=latitude,
                longitude=longitude,
                radius_m=radius_m,
                max_age_s=self._CACHE_FALLBACK_MAX_AGE_S,
            )
            if len(cache_fallback) > 0:
                logger.info(
                    "poi around: using recent cache fallback (%d candidates)",
                    len(cache_fallback),
                )
                result = cache_fallback

        if len(result) == 0 and len(stale_candidates) > 0:
            logger.info("poi around: using stale cache fallback (%d candidates)", len(stale_candidates))
            self._last_fetch_error = None
            _poi_cache[cache_key] = (time.time(), copy.deepcopy(stale_candidates))
            return stale_candidates

        if len(result) > 0:
            self._last_fetch_error = None

        if len(result) > self._MAX_CANDIDATES_PER_PASS:
            result = result[:self._MAX_CANDIDATES_PER_PASS]

        _poi_cache[cache_key] = (time.time(), copy.deepcopy(result))
        return result

    def _fetch_bbox_candidates(
        self,
        *,
        south: float,
        west: float,
        north: float,
        east: float,
        deadline_s: float | None = None,
    ) -> list[OsmPoiCandidate]:
        result: list[OsmPoiCandidate] = []
        for filters in self._iter_filter_chunks():
            if deadline_s is not None and time.perf_counter() >= deadline_s:
                break
            query = self._build_bbox_query(
                south=south,
                west=west,
                north=north,
                east=east,
                filters=filters,
            )
            chunk = self._fetch_from_query(query, deadline_s=deadline_s)
            if len(chunk) > 0:
                result = self._merge_deduplicate(result, chunk)
            elif self._last_fetch_error and self._is_fatal_connection_error(self._last_fetch_error):
                break
        if len(result) > 0:
            self._last_fetch_error = None
        if len(result) > self._MAX_CANDIDATES_PER_PASS:
            result = result[:self._MAX_CANDIDATES_PER_PASS]
        return result

    def _make_cache_key(self, *, south: float, west: float, north: float, east: float, margin_m: int) -> str:
        return (
            f"{round(south, 4)}:{round(west, 4)}:{round(north, 4)}:{round(east, 4)}"
            f":{int(margin_m)}:{self._BBOX_CACHE_VERSION}"
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

    def _iter_filter_chunks(self) -> list[tuple[str, ...]]:
        filters = self._OVERPASS_FILTERS
        chunked: list[tuple[str, ...]] = []
        for index in range(0, len(filters), self._FILTER_CHUNK_SIZE):
            chunked.append(filters[index:index + self._FILTER_CHUNK_SIZE])
        return chunked

    def _build_bbox_query(
        self,
        *,
        south: float,
        west: float,
        north: float,
        east: float,
        filters: tuple[str, ...] | None = None,
    ) -> str:
        bbox = f"({south:.6f},{west:.6f},{north:.6f},{east:.6f})"
        lines = [f"[out:json][timeout:{self._QUERY_TIMEOUT_S}];", "("]
        selected_filters = filters or self._OVERPASS_FILTERS
        for osm_filter in selected_filters:
            lines.append(f"  node{osm_filter}{bbox};")
            lines.append(f"  way{osm_filter}{bbox};")
            lines.append(f"  relation{osm_filter}{bbox};")
        lines.extend([");", "out center tags;"])
        return "\n".join(lines)

    def _build_around_query(
        self,
        *,
        latitude: float,
        longitude: float,
        radius_m: int,
        filters: tuple[str, ...] | None = None,
    ) -> str:
        lat = f"{latitude:.6f}"
        lon = f"{longitude:.6f}"
        lines = [f"[out:json][timeout:{self._QUERY_TIMEOUT_S}];", "("]
        selected_filters = filters or self._OVERPASS_FILTERS
        for osm_filter in selected_filters:
            lines.append(f"  node(around:{radius_m},{lat},{lon}){osm_filter};")
            lines.append(f"  way(around:{radius_m},{lat},{lon}){osm_filter};")
            lines.append(f"  relation(around:{radius_m},{lat},{lon}){osm_filter};")
        lines.extend([");", "out center tags;"])
        return "\n".join(lines)

    def _fetch_candidates_around_route_points(
        self,
        points: list[RoutePoint],
        *,
        deadline_s: float | None = None,
    ) -> list[OsmPoiCandidate]:
        sampled = self._sample_route_points(points, max_points=24)
        if len(sampled) == 0:
            return []

        lines = [f"[out:json][timeout:{self._QUERY_TIMEOUT_S}];", "("]
        for point in sampled:
            lat = f"{point.latitude:.6f}"
            lon = f"{point.longitude:.6f}"
            lines.append(f'  node(around:320,{lat},{lon})["tourism"="viewpoint"];')
            lines.append(f'  node(around:320,{lat},{lon})["natural"="peak"];')
            lines.append(f'  node(around:320,{lat},{lon})["natural"="water"];')
            lines.append(f'  node(around:320,{lat},{lon})["natural"="waterfall"];')
            lines.append(f'  node(around:320,{lat},{lon})["waterway"];')
            lines.append(f'  node(around:320,{lat},{lon})["historic"];')
            lines.append(f'  node(around:320,{lat},{lon})["amenity"="place_of_worship"];')
            lines.append(f'  node(around:320,{lat},{lon})["building"~"church|chapel|cathedral|castle"];')
            lines.append(f'  way(around:320,{lat},{lon})["natural"="water"];')
            lines.append(f'  way(around:320,{lat},{lon})["waterway"];')
            lines.append(f'  way(around:320,{lat},{lon})["historic"];')
            lines.append(f'  way(around:320,{lat},{lon})["amenity"="place_of_worship"];')
            lines.append(f'  way(around:320,{lat},{lon})["building"~"church|chapel|cathedral|castle"];')
            lines.append(f'  relation(around:320,{lat},{lon})["historic"];')
            lines.append(f'  relation(around:320,{lat},{lon})["natural"="water"];')
            lines.append(f'  relation(around:320,{lat},{lon})["waterway"];')
        lines.extend([");", "out center tags;"])
        query = "\n".join(lines)

        return self._fetch_from_query(query, deadline_s=deadline_s)

    def _sample_route_points(self, points: list[RoutePoint], max_points: int) -> list[RoutePoint]:
        if len(points) <= max_points:
            return points
        step = max(1, len(points) // max_points)
        sampled = [points[i] for i in range(0, len(points), step)]
        if sampled[-1] != points[-1]:
            sampled.append(points[-1])
        return sampled[:max_points]

    def _fetch_from_query(self, query: str, *, deadline_s: float | None = None) -> list[OsmPoiCandidate]:
        if deadline_s is not None and time.perf_counter() >= deadline_s:
            self._last_fetch_error = "budget de requête POI dépassé"
            return []

        payload = parse.urlencode({"data": query}).encode("utf-8")
        data: dict | None = None
        last_error: Exception | None = None
        available_urls = self._available_overpass_urls()
        if len(available_urls) == 0:
            self._last_fetch_error = "trop de requetes vers Overpass, nouvelle tentative dans quelques instants"
            return []

        attempts = 0
        for overpass_url in available_urls:
            if attempts >= self._MAX_ENDPOINT_ATTEMPTS_PER_QUERY:
                break

            if deadline_s is not None:
                remaining_s = deadline_s - time.perf_counter()
                if remaining_s <= 1.0:
                    break
            else:
                remaining_s = self._QUERY_TIMEOUT_S + 5

            attempts += 1
            self._wait_for_request_slot()
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
                request_timeout_s = max(2.0, min(self._QUERY_TIMEOUT_S + 5, remaining_s))
                with request.urlopen(req, timeout=request_timeout_s) as response:
                    raw = response.read().decode("utf-8")
                data = json.loads(raw)
                self._last_fetch_error = None
                break
            except Exception as exc:
                last_error = exc
                if self._is_rate_limited_error(exc):
                    backoff_s = self._retry_after_seconds(exc) or self._DEFAULT_ENDPOINT_BACKOFF_S
                    self._endpoint_backoff_until[overpass_url] = time.time() + backoff_s
                    logger.warning(
                        "OSM POI fetch rate-limited via %s (429), cooling down %.0fs",
                        overpass_url,
                        backoff_s,
                    )
                    continue

                logger.warning("OSM POI fetch failed via %s: %s", overpass_url, exc)
                if self._is_fatal_connection_error(exc):
                    break
                continue
            finally:
                self._next_overpass_request_at = time.perf_counter() + self._MIN_OVERPASS_INTERVAL_S
        if data is None:
            if last_error is not None:
                logger.warning("OSM POI fetch failed on all endpoints: %s", last_error)
                self._last_fetch_error = self._human_readable_error(last_error)
            elif deadline_s is not None and time.perf_counter() >= deadline_s:
                self._last_fetch_error = "budget de requête POI dépassé"
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

    def _collect_cached_candidates_for_bbox(
        self,
        *,
        south: float,
        west: float,
        north: float,
        east: float,
        max_age_s: float,
    ) -> list[OsmPoiCandidate]:
        now = time.time()
        candidates: list[OsmPoiCandidate] = []
        for ts, cached_candidates in _poi_cache.values():
            if now - ts > max_age_s:
                continue
            for candidate in cached_candidates:
                if south <= candidate.latitude <= north and west <= candidate.longitude <= east:
                    candidates.append(candidate)
        if len(candidates) == 0:
            return []
        merged = self._merge_deduplicate([], candidates)
        if len(merged) > self._MAX_CANDIDATES_PER_PASS:
            return merged[:self._MAX_CANDIDATES_PER_PASS]
        return merged

    def _collect_cached_candidates_around_location(
        self,
        *,
        latitude: float,
        longitude: float,
        radius_m: int,
        max_age_s: float,
    ) -> list[OsmPoiCandidate]:
        lat_margin = radius_m / 111_320.0
        lon_margin = radius_m / (111_320.0 * max(0.2, abs(math.cos(math.radians(latitude)))))
        south = latitude - lat_margin
        north = latitude + lat_margin
        west = longitude - lon_margin
        east = longitude + lon_margin
        return self._collect_cached_candidates_for_bbox(
            south=south,
            west=west,
            north=north,
            east=east,
            max_age_s=max_age_s,
        )

    def _available_overpass_urls(self) -> list[str]:
        now = time.time()
        urls: list[str] = []
        for overpass_url in self._OVERPASS_URLS:
            backoff_until = self._endpoint_backoff_until.get(overpass_url, 0.0)
            if backoff_until <= now:
                urls.append(overpass_url)
        return urls

    def _wait_for_request_slot(self) -> None:
        wait_s = self._next_overpass_request_at - time.perf_counter()
        if wait_s > 0:
            time.sleep(min(wait_s, self._MIN_OVERPASS_INTERVAL_S))

    @staticmethod
    def _is_rate_limited_error(error: Exception | str) -> bool:
        if isinstance(error, url_error.HTTPError):
            return error.code == 429
        text = str(error).lower()
        return "429" in text or "too many requests" in text

    @staticmethod
    def _retry_after_seconds(error: Exception | str) -> float | None:
        if not isinstance(error, url_error.HTTPError):
            return None
        retry_after = error.headers.get("Retry-After")
        if retry_after is None:
            return None
        try:
            return max(5.0, min(float(retry_after), 600.0))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _is_fatal_connection_error(error: Exception | str) -> bool:
        text = str(error).lower()
        return (
            "winerror 10013" in text
            or "permission denied" in text
            or "forbidden by its access permissions" in text
        )

    @staticmethod
    def _human_readable_error(error: Exception | str) -> str:
        text = str(error).lower()
        if "timed out" in text or "timeout" in text:
            return "délai d'attente dépassé (service Overpass surchargé)"
        if "connection refused" in text or "connexion refusée" in text:
            return "connexion refusée par le serveur Overpass"
        if "name or service not known" in text or "getaddrinfo" in text:
            return "impossible de résoudre l'adresse du serveur Overpass"
        if "403" in text or "forbidden" in text:
            return "accès refusé par le serveur Overpass (403)"
        if "429" in text or "too many" in text:
            return "trop de requêtes vers le serveur Overpass (429)"
        if "500" in text or "502" in text or "503" in text:
            return "le serveur Overpass est temporairement indisponible"
        return "service de points d'intérêt temporairement indisponible"

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
