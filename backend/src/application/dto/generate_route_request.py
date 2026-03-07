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
    hike_style: Literal["equilibree", "sentiers", "nature", "calme"] = Field(
        default="equilibree",
        description="Type de randonnée : equilibree, sentiers, nature, calme",
    )
