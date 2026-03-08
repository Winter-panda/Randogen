from pydantic import BaseModel, Field


class RoutePointResponse(BaseModel):
    latitude: float = Field(..., description="Latitude du point")
    longitude: float = Field(..., description="Longitude du point")
    elevation_m: float = Field(default=0.0, description="Altitude en metres")


class PoiResponse(BaseModel):
    id: str = Field(..., description="Identifiant du point d'interet")
    name: str = Field(..., description="Nom du point d'interet")
    category: str = Field(..., description="Categorie normalisee")
    sub_category: str | None = Field(default=None, description="Sous-categorie")
    latitude: float = Field(..., description="Latitude du point d'interet")
    longitude: float = Field(..., description="Longitude du point d'interet")
    distance_to_route_m: float = Field(..., description="Distance minimale au trace en metres")
    distance_from_start_m: float | None = Field(default=None, description="Distance depuis le depart")
    score: float = Field(default=0.0, description="Score de pertinence du POI")
    tags: list[str] = Field(default_factory=list, description="Etiquettes techniques")


class RouteCandidateResponse(BaseModel):
    id: str = Field(..., description="Identifiant du parcours")
    stable_route_id: str = Field(default="", description="Identifiant stable du parcours")
    name: str = Field(..., description="Nom du parcours")
    distance_km: float = Field(..., description="Distance estimee en kilometres")
    estimated_duration_min: int = Field(..., description="Duree estimee en minutes")
    estimated_elevation_gain_m: int = Field(..., description="Denivele positif estime")
    score: float = Field(..., description="Score qualite du parcours")
    route_type: str = Field(..., description="Type de parcours")
    source: str = Field(..., description="Origine du calcul")
    trail_ratio: float = Field(..., description="Part estimee de sentiers")
    road_ratio: float = Field(..., description="Part estimee de routes")
    nature_score: float = Field(..., description="Score nature")
    quiet_score: float = Field(..., description="Score calme")
    hiking_suitability_score: float = Field(..., description="Score adaptation randonnee")
    difficulty: str = Field(default="moderee", description="Niveau de difficulte : facile, moderee, soutenue")
    tags: list[str] = Field(default_factory=list, description="Tags explicatifs du parcours")
    points: list[RoutePointResponse] = Field(
        default_factory=list,
        description="Points simplifies du parcours",
    )
    pois: list[PoiResponse] = Field(
        default_factory=list,
        description="Points d'interet proches du parcours",
    )
    poi_score: float = Field(default=0.0, description="Score POI global du parcours")
    poi_quantity_score: float = Field(default=0.0, description="Score quantite POI")
    poi_diversity_score: float = Field(default=0.0, description="Score diversite POI")
    poi_highlight_count: int = Field(default=0, description="Nombre de highlights POI")
    highlighted_poi_labels: list[str] = Field(
        default_factory=list,
        description="Labels POI mis en avant pour l'utilisateur",
    )
    poi_highlights: list[str] = Field(
        default_factory=list,
        description="Resumes textuels POI du parcours",
    )
    score_breakdown: dict[str, float] = Field(
        default_factory=dict,
        description="Detail des composantes du score",
    )
    explanation: str = Field(default="", description="Phrase de synthese du choix")
    explanation_reasons: list[str] = Field(
        default_factory=list,
        description="Raisons principales du classement",
    )
    description: str = Field(default="", description="Description detaillee du parcours")
    poi_on_route_count: int = Field(default=0, description="Nombre de POI sur le trace")
    poi_near_route_count: int = Field(default=0, description="Nombre de POI proches")
    context_score_delta: float = Field(default=0.0, description="Ajustement contextuel du score")
    context_warnings: list[str] = Field(default_factory=list, description="Avertissements contextuels")
    seen_before: bool = Field(default=False, description="Indique si le parcours a deja ete vu recemment")


class GenerateRouteResponse(BaseModel):
    status: str = Field(
        default="ok",
        description="Etat global de la generation: ok, partial, fallback, low_data, error",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Avertissements non bloquants sur la qualite ou les services externes",
    )
    requested_route_count: int = Field(default=0, description="Nombre de parcours demandes")
    generated_route_count: int = Field(default=0, description="Nombre de parcours effectivement generes")
    routes: list[RouteCandidateResponse] = Field(
        default_factory=list,
        description="Liste des parcours generes",
    )
