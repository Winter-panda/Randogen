from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from urllib import error, request

from src.domain.entities.route_point import RoutePoint


@dataclass
class OrsRouteResult:
    points: list[RoutePoint]
    distance_m: float
    duration_s: float
    extras: dict[str, Any] = field(default_factory=dict)


class OrsClientError(Exception):
    pass


class OrsRateLimitError(OrsClientError):
    """Raised when ORS returns HTTP 429 — rate limit exceeded."""
    pass


class OrsClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        profile: str,
        timeout_s: int = 20,
    ) -> None:
        self._api_key = api_key.strip()
        self._base_url = base_url.rstrip("/")
        self._profile = profile
        self._timeout_s = timeout_s

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def get_round_trip_geojson(
        self,
        start_lon: float,
        start_lat: float,
        length_m: float,
        points: int,
        seed: int,
        profile_params: dict[str, Any] | None = None,
        avoid_features: list[str] | None = None,
    ) -> OrsRouteResult:
        if not self.is_configured():
            raise OrsClientError("ORS API key not configured.")

        url = f"{self._base_url}/v2/directions/{self._profile}/geojson"

        options: dict[str, Any] = {
            "round_trip": {
                "length": float(length_m),
                "points": int(points),
                "seed": int(seed),
            }
        }
        if avoid_features:
            options["avoid_features"] = avoid_features
        if profile_params:
            options["profile_params"] = profile_params

        payload: dict[str, Any] = {
            "coordinates": [[start_lon, start_lat]],
            "instructions": False,
            "elevation": True,
            "extra_info": [
                "surface",
                "waytype",
                "waycategory",
                "traildifficulty",
                "green",
                "noise",
                "suitability",
            ],
            "options": options,
        }

        return self._post_geojson(url, payload)

    def _post_geojson(self, url: str, payload: dict[str, Any]) -> OrsRouteResult:
        req = request.Request(
            url=url,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": self._api_key,
                "Content-Type": "application/json; charset=utf-8",
                "Accept": "application/json, application/geo+json",
            },
        )

        try:
            with request.urlopen(req, timeout=self._timeout_s) as response:
                raw = response.read().decode("utf-8")
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            if exc.code == 429:
                raise OrsRateLimitError(f"ORS rate limit exceeded (429): {details}") from exc
            raise OrsClientError(f"ORS HTTP error {exc.code}: {details}") from exc
        except error.URLError as exc:
            raise OrsClientError(f"ORS network error: {exc}") from exc
        except TimeoutError as exc:
            raise OrsClientError("ORS request timeout.") from exc

        try:
            data: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise OrsClientError("ORS returned invalid JSON.") from exc

        features = data.get("features")
        if not isinstance(features, list) or len(features) == 0:
            raise OrsClientError("ORS response does not contain any feature.")

        feature = features[0]
        geometry = feature.get("geometry", {})
        properties = feature.get("properties", {})

        coordinates = geometry.get("coordinates")
        if not isinstance(coordinates, list) or len(coordinates) == 0:
            raise OrsClientError("ORS response does not contain geometry coordinates.")

        summary = properties.get("summary", {})
        distance_m = float(summary.get("distance", 0.0))
        duration_s = float(summary.get("duration", 0.0))
        extras = properties.get("extras", {}) or {}

        points_list = [
            RoutePoint(
                latitude=float(coord[1]),
                longitude=float(coord[0]),
                elevation_m=float(coord[2]) if len(coord) >= 3 else 0.0,
            )
            for coord in coordinates
            if isinstance(coord, list) and len(coord) >= 2
        ]

        if len(points_list) == 0:
            raise OrsClientError("ORS returned an empty geometry.")

        return OrsRouteResult(
            points=points_list,
            distance_m=distance_m,
            duration_s=duration_s,
            extras=extras,
        )
