from typing import Literal

from pydantic import BaseModel, Field


class GenerateRouteRequest(BaseModel):
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
