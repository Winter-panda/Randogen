from typing import Literal

from pydantic import BaseModel, Field


class RouteSummaryRequest(BaseModel):
    """Résumé d'un parcours envoyé par le client pour les opérations favorites/vues."""
    name: str = Field(default="")
    distance_km: float = Field(default=0.0, ge=0)
    estimated_duration_min: int = Field(default=0, ge=0)
    estimated_elevation_gain_m: int = Field(default=0, ge=0)
    difficulty: str = Field(default="moderee")
    score: float = Field(default=0.0, ge=0, le=1)
    tags: list[str] = Field(default_factory=list)
    highlighted_poi_labels: list[str] = Field(default_factory=list)


class GenerateRouteRequest(BaseModel):
    user_id: str = Field(default="anonymous", min_length=1, max_length=100, description="Identifiant utilisateur")
    latitude: float = Field(..., ge=-90, le=90, description="Latitude utilisateur")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude utilisateur")
    target_distance_km: float = Field(
        ...,
        gt=0,
        le=100,
        description="Distance cible en kilomètres",
    )
    route_count: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Nombre de parcours à générer",
    )
    ambiance: Literal["equilibree", "sentiers", "nature", "calme"] | None = Field(
        default=None,
        description="Ambiance souhaitée : equilibree, sentiers, nature, calme",
    )
    terrain: Literal["plat", "vallonne"] | None = Field(
        default=None,
        description="Type de terrain : plat, vallonne",
    )
    effort: Literal["promenade", "sportif"] | None = Field(
        default=None,
        description="Niveau d'effort : promenade, sportif",
    )
    prioritize_nature: bool = Field(default=False, description="Privilegier la nature")
    prioritize_viewpoints: bool = Field(default=False, description="Privilegier les points de vue")
    prioritize_calm: bool = Field(default=False, description="Privilegier les lieux calmes")
    avoid_urban: bool = Field(default=False, description="Eviter les zones urbaines")
    avoid_roads: bool = Field(default=False, description="Eviter les routes")
    avoid_steep: bool = Field(default=False, description="Eviter fort denivele")
    avoid_touristic: bool = Field(default=False, description="Eviter points touristiques")
    adapt_to_weather: bool = Field(default=True, description="Adapter la recommandation au contexte meteo")
    difficulty_pref: Literal["facile", "moderee", "difficile"] | None = Field(
        default=None,
        description="Preference de difficulte : facile, moderee, difficile",
    )
