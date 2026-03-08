from __future__ import annotations

import copy
import json
import logging
import time
from dataclasses import dataclass
from urllib import error, parse, request

logger = logging.getLogger(__name__)

_weather_cache: dict[str, tuple[float, "WeatherSnapshot"]] = {}
_WEATHER_CACHE_TTL_S = 900.0  # 15 minutes


@dataclass
class WeatherSnapshot:
    temperature_c: float
    precipitation_mm: float
    wind_kmh: float
    weather_code: int


class OpenMeteoClient:
    _BASE_URL = "https://api.open-meteo.com/v1/forecast"

    def __init__(self, timeout_s: int = 8) -> None:
        self._timeout_s = timeout_s

    def get_current_weather(self, *, latitude: float, longitude: float) -> WeatherSnapshot | None:
        cache_key = f"{round(latitude, 2)}:{round(longitude, 2)}"
        cached = _weather_cache.get(cache_key)
        if cached is not None:
            ts, snapshot = cached
            if (time.time() - ts) < _WEATHER_CACHE_TTL_S:
                return copy.deepcopy(snapshot)
            _weather_cache.pop(cache_key, None)

        query = parse.urlencode(
            {
                "latitude": f"{latitude:.5f}",
                "longitude": f"{longitude:.5f}",
                "current": "temperature_2m,precipitation,weather_code,wind_speed_10m",
            }
        )
        url = f"{self._BASE_URL}?{query}"
        req = request.Request(url, headers={"Accept": "application/json", "User-Agent": "Randogen/0.1"})

        try:
            with request.urlopen(req, timeout=self._timeout_s) as response:
                payload = response.read().decode("utf-8")
            data = json.loads(payload)
            current = data.get("current", {})
            snapshot = WeatherSnapshot(
                temperature_c=float(current.get("temperature_2m", 0.0)),
                precipitation_mm=float(current.get("precipitation", 0.0)),
                wind_kmh=float(current.get("wind_speed_10m", 0.0)),
                weather_code=int(current.get("weather_code", 0)),
            )
            _weather_cache[cache_key] = (time.time(), copy.deepcopy(snapshot))
            return snapshot
        except (error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            logger.warning("weather: unable to fetch current weather: %s", exc)
            return None
