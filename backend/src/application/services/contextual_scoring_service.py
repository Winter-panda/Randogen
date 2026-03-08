from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.domain.entities.route_candidate import RouteCandidate
from src.domain.entities.user_search import UserSearch
from src.infrastructure.weather.open_meteo_client import OpenMeteoClient, WeatherSnapshot


@dataclass
class ContextAdjustment:
    score_delta: float
    warnings: list[str]
    tags: list[str]


class ContextualScoringService:
    def __init__(self, weather_client: OpenMeteoClient | None = None) -> None:
        self._weather_client = weather_client or OpenMeteoClient()

    def _now(self) -> datetime:
        """Retourne l'heure actuelle (injectable pour les tests)."""
        return datetime.now().astimezone()

    @staticmethod
    def _sunset_hour(month: int) -> int:
        """Heure approx. coucher du soleil (crepuscule civil) pour ~47N."""
        if month in {6, 7}:
            return 21
        if month in {5, 8}:
            return 20
        if month in {4, 9}:
            return 19
        if month in {3, 10}:
            return 18
        return 17

    @staticmethod
    def _sunrise_hour(month: int) -> int:
        """Heure approx. lever du soleil pour ~47N."""
        if month in {6, 7}:
            return 5
        if month in {5, 8}:
            return 6
        if month in {3, 4, 9, 10}:
            return 7
        return 8

    def adjust_route(self, *, route: RouteCandidate, search: UserSearch) -> ContextAdjustment:
        now = self._now()
        hour = now.hour
        month = now.month

        warnings: list[str] = []
        tags: list[str] = []
        delta = 0.0

        weather: WeatherSnapshot | None = None
        if search.adapt_to_weather:
            weather = self._weather_client.get_current_weather(
                latitude=search.latitude,
                longitude=search.longitude,
            )

        # -- Time-of-day feasibility
        sunrise = self._sunrise_hour(month)
        sunset = self._sunset_hour(month)
        est_h = route.estimated_duration_min / 60.0

        if hour < sunrise or hour >= sunset + 1:
            # Nuit : randonnee dangereuse sans eclairage
            delta -= 0.10
            warnings.append("Il fait nuit : randonnee deconseille sans eclairage.")
        elif hour < sunrise + 2:
            # Tres tot le matin : bon pour courtes/moderees
            if est_h <= 1.5:
                delta += 0.02
                tags.append("Ideal en sortie matinale")
            elif est_h >= 3.0:
                delta -= 0.01
        elif hour < 11:
            # Matin : meilleure fenetre pour les longues randos
            if est_h >= 2.0:
                delta += 0.02
                tags.append("Fenetre ideale du matin")
        elif hour >= 17 and route.estimated_duration_min >= 120:
            # Fin d'apres-midi : risque de finir de nuit
            hours_left = max(0.0, float(sunset - hour))
            if est_h > hours_left * 0.85:
                delta -= 0.05
                warnings.append("Ce parcours risque de finir apres la tombee de la nuit.")
            else:
                delta -= 0.02
        elif hour >= 16 and route.estimated_duration_min >= 90:
            hours_left = max(0.0, float(sunset - hour))
            if est_h > hours_left * 0.9:
                delta -= 0.04
                warnings.append("Delai serre : ce parcours finira a la tombee de la nuit.")
            else:
                delta -= 0.02

        # -- Weather-based adjustments
        is_warm_season = month in {5, 6, 7, 8, 9}

        # Midi ete : legere penalite pour parcours longs sans ombre (sans meteo live)
        if 11 <= hour <= 14 and is_warm_season and est_h >= 2.0 and weather is None and route.nature_score < 0.4:
            delta -= 0.01

        if weather is not None:
            if weather.temperature_c >= 28:
                if route.nature_score >= 0.6 or route.quiet_score >= 0.6:
                    delta += 0.03
                    tags.append("Mieux adapte a la chaleur")
                else:
                    delta -= 0.03
                warnings.append("Conditions chaudes, parcours ombrage recommande.")
            if weather.precipitation_mm >= 0.8 or weather.weather_code in {61, 63, 65, 80, 81, 82}:
                if route.trail_ratio >= 0.65:
                    delta -= 0.04
                    warnings.append("Conditions humides: sections potentiellement glissantes.")
                else:
                    delta -= 0.02
            if weather.wind_kmh >= 35 and {"viewpoint", "summit"} & {poi.category for poi in route.pois}:
                delta -= 0.02
        elif search.adapt_to_weather and is_warm_season and route.nature_score >= 0.7:
            delta += 0.01

        return ContextAdjustment(
            score_delta=round(max(-0.12, min(0.08, delta)), 3),
            warnings=self._deduplicate_keep_order(warnings)[:2],
            tags=self._deduplicate_keep_order(tags)[:2],
        )

    @staticmethod
    def _deduplicate_keep_order(values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            result.append(value)
        return result
