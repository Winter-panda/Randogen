import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from src.application.services.contextual_scoring_service import ContextualScoringService
from src.domain.entities.route_candidate import RouteCandidate
from src.domain.entities.user_search import UserSearch
from src.infrastructure.weather.open_meteo_client import WeatherSnapshot


class _FakeWeatherClient:
    def __init__(self, snapshot: WeatherSnapshot | None) -> None:
        self.snapshot = snapshot

    def get_current_weather(self, *, latitude: float, longitude: float) -> WeatherSnapshot | None:
        return self.snapshot


def _fake_now(hour: int, month: int = 7) -> datetime:
    return datetime(2026, month, 20, hour, 0, tzinfo=timezone.utc)


class ContextualScoringServiceTestCase(unittest.TestCase):
    def _route(self, *, duration_min: int = 130, trail_ratio: float = 0.75) -> RouteCandidate:
        return RouteCandidate(
            id="r1",
            name="Parcours",
            distance_km=8.0,
            estimated_duration_min=duration_min,
            estimated_elevation_gain_m=180,
            score=0.8,
            route_type="nature",
            source="test",
            trail_ratio=trail_ratio,
            nature_score=0.72,
            quiet_score=0.58,
        )

    def _search(self, *, adapt_to_weather: bool = True) -> UserSearch:
        return UserSearch(
            user_id="test-user",
            latitude=48.85,
            longitude=2.35,
            target_distance_km=8.0,
            route_count=3,
            adapt_to_weather=adapt_to_weather,
        )

    def test_penalizes_long_route_late_day(self) -> None:
        # Novembre (sunset=17h) : a 17h avec 130min, la rando finit dans le noir
        service = ContextualScoringService(weather_client=_FakeWeatherClient(None))
        with patch.object(service, "_now", return_value=_fake_now(hour=17, month=11)):
            adjustment = service.adjust_route(route=self._route(duration_min=130), search=self._search())
        self.assertLess(adjustment.score_delta, 0.0)
        self.assertTrue(any("tombee de la nuit" in w for w in adjustment.warnings))

    def test_no_penalty_short_route_late_day(self) -> None:
        service = ContextualScoringService(weather_client=_FakeWeatherClient(None))
        # Use adapt_to_weather=False to isolate time-of-day logic only
        with patch.object(service, "_now", return_value=_fake_now(hour=18)):
            adjustment = service.adjust_route(
                route=self._route(duration_min=60),
                search=self._search(adapt_to_weather=False),
            )
        # Short route (60 min) at hour 18 has no time-of-day penalty
        self.assertEqual(adjustment.score_delta, 0.0)

    def test_hot_weather_adds_heat_warning(self) -> None:
        weather = WeatherSnapshot(temperature_c=31.0, precipitation_mm=0.0, wind_kmh=10.0, weather_code=1)
        service = ContextualScoringService(weather_client=_FakeWeatherClient(weather))
        with patch.object(service, "_now", return_value=_fake_now(hour=11)):
            adjustment = service.adjust_route(route=self._route(), search=self._search())
        self.assertTrue(any("Conditions chaudes" in w for w in adjustment.warnings))

    def test_rain_penalizes_trail_route(self) -> None:
        weather = WeatherSnapshot(temperature_c=15.0, precipitation_mm=2.0, wind_kmh=10.0, weather_code=61)
        service = ContextualScoringService(weather_client=_FakeWeatherClient(weather))
        with patch.object(service, "_now", return_value=_fake_now(hour=10)):
            adjustment = service.adjust_route(route=self._route(trail_ratio=0.80), search=self._search())
        self.assertLess(adjustment.score_delta, 0.0)

    def test_no_weather_adjustment_when_disabled(self) -> None:
        # Utiliser 14h (pas de bonus matin, pas de penalite soir) pour isoler l'effet meteo
        weather = WeatherSnapshot(temperature_c=31.0, precipitation_mm=3.0, wind_kmh=50.0, weather_code=65)
        service = ContextualScoringService(weather_client=_FakeWeatherClient(weather))
        with patch.object(service, "_now", return_value=_fake_now(hour=14)):
            adjustment = service.adjust_route(
                route=self._route(), search=self._search(adapt_to_weather=False)
            )
        # Aucun avertissement meteo car adapt_to_weather=False ; pas de bonus/penalite temporel a 14h
        self.assertEqual(adjustment.warnings, [])
        self.assertEqual(adjustment.score_delta, 0.0)

    def test_score_delta_capped(self) -> None:
        weather = WeatherSnapshot(temperature_c=35.0, precipitation_mm=5.0, wind_kmh=60.0, weather_code=82)
        service = ContextualScoringService(weather_client=_FakeWeatherClient(weather))
        with patch.object(service, "_now", return_value=_fake_now(hour=18)):
            adjustment = service.adjust_route(route=self._route(duration_min=180, trail_ratio=0.90), search=self._search())
        self.assertGreaterEqual(adjustment.score_delta, -0.12)
        self.assertLessEqual(adjustment.score_delta, 0.08)


if __name__ == "__main__":
    unittest.main()
