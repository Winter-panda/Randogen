from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib import error, request

from src.domain.entities.route_point import RoutePoint


@dataclass
class OrsRouteResult:
    points: list[RoutePoint]
    distance_m: float
    duration_s: float


class OrsClientError(Exception):
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

    def get_directions_geojson(
        self,
        coordinates_lon_lat: list[list[float]],
    ) -> OrsRouteResult:
        if not self.is_configured():
            raise OrsClientError("ORS API key not configured.")

        if len(coordinates_lon_lat) < 2:
            raise OrsClientError("At least 2 coordinates are required.")

        url = f"{self._base_url}/v2/directions/{self._profile}/geojson"

        payload = {
            "coordinates": coordinates_lon_lat,
            "instructions": False,
            "elevation": False,
        }

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
            raise OrsClientError(
                f"ORS HTTP error {exc.code}: {details}"
            ) from exc
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

        points = [
            RoutePoint(latitude=float(coord[1]), longitude=float(coord[0]))
            for coord in coordinates
            if isinstance(coord, list) and len(coord) >= 2
        ]

        if len(points) == 0:
            raise OrsClientError("ORS returned an empty geometry.")

        return OrsRouteResult(
            points=points,
            distance_m=distance_m,
            duration_s=duration_s,
        )