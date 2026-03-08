from pydantic import BaseModel, Field


class RoutePointResponse(BaseModel):
    latitude: float = Field(..., description="Latitude du point")
    longitude: float = Field(..., description="Longitude du point")
    elevation_m: float = Field(default=0.0, description="Altitude en mètres")


class RouteCandidateResponse(BaseModel):
    id: str = Field(..., description="Identifiant du parcours")
    name: str = Field(..., description="Nom du parcours")
    distance_km: float = Field(..., description="Distance estimée en kilomètres")
    estimated_duration_min: int = Field(..., description="Durée estimée en minutes")
    estimated_elevation_gain_m: int = Field(..., description="Dénivelé positif estimé")
    score: float = Field(..., description="Score qualité du parcours")
    route_type: str = Field(..., description="Type de parcours")
    source: str = Field(..., description="Origine du calcul")
    trail_ratio: float = Field(..., description="Part estimée de sentiers")
    road_ratio: float = Field(..., description="Part estimée de routes")
    nature_score: float = Field(..., description="Score nature")
    quiet_score: float = Field(..., description="Score calme")
    hiking_suitability_score: float = Field(..., description="Score adaptation randonnée")
    difficulty: str = Field(default="modérée", description="Niveau de difficulté : facile, modérée, soutenue")
    tags: list[str] = Field(default_factory=list, description="Tags explicatifs du parcours")
    points: list[RoutePointResponse] = Field(
        default_factory=list,
        description="Points simplifiés du parcours",
    )


class GenerateRouteResponse(BaseModel):
    routes: list[RouteCandidateResponse] = Field(
        default_factory=list,
        description="Liste des parcours générés",
    )