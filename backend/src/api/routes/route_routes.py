import logging

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

from src.api.controllers.route_controller import RouteController
from src.application.dto.generate_route_request import GenerateRouteRequest, RouteSummaryRequest
from src.application.dto.generate_route_response import (
    GenerateRouteResponse,
    PoiResponse,
    RouteCandidateResponse,
)
from src.infrastructure.weather.open_meteo_client import OpenMeteoClient

router = APIRouter(prefix="/routes", tags=["routes"])

controller = RouteController()
_weather_client = OpenMeteoClient()


@router.get("/weather")
def get_weather(lat: float = Query(...), lon: float = Query(...)) -> JSONResponse:
    snapshot = _weather_client.get_current_weather(latitude=lat, longitude=lon)
    if snapshot is None:
        raise HTTPException(status_code=503, detail="Meteo indisponible")
    return JSONResponse(content={
        "temperature_c": snapshot.temperature_c,
        "precipitation_mm": snapshot.precipitation_mm,
        "wind_kmh": snapshot.wind_kmh,
        "weather_code": snapshot.weather_code,
    })


@router.post("/generate", response_model=GenerateRouteResponse)
def generate_routes(request: GenerateRouteRequest) -> GenerateRouteResponse:
    return controller.generate_routes(request)


@router.get("/pois/nearby", response_model=list[PoiResponse])
def get_nearby_pois(
    lat: float = Query(..., ge=-90.0, le=90.0),
    lon: float = Query(..., ge=-180.0, le=180.0),
    radius_km: float = Query(default=5.0, ge=0.2, le=10.0),
    categories: list[str] | None = Query(default=None),
    limit: int = Query(default=250, ge=1, le=300),
) -> list[PoiResponse]:
    allowed_categories = {
        "viewpoint",
        "water",
        "summit",
        "nature",
        "heritage",
        "facility",
        "start_access",
    }
    normalized_categories = [
        value.strip().lower()
        for value in (categories or [])
        if isinstance(value, str) and value.strip().lower() in allowed_categories
    ]
    pois = controller.get_nearby_pois(
        latitude=lat,
        longitude=lon,
        radius_km=radius_km,
        categories=normalized_categories,
        limit=limit,
    )
    if len(pois) == 0:
        provider_error = controller.get_last_poi_provider_error()
        if provider_error:
            logger.info("Nearby POIs unavailable: %s", provider_error)
    return pois


@router.get("/users/{user_id}/preferences")
def get_preferences(user_id: str) -> JSONResponse:
    return JSONResponse(content=controller.get_preference_profile(user_id))


@router.get("/users/{user_id}/history")
def get_history(user_id: str) -> JSONResponse:
    return JSONResponse(content={"items": controller.list_history(user_id)})


@router.get("/users/{user_id}/favorites")
def get_favorites(user_id: str) -> JSONResponse:
    return JSONResponse(content={"items": controller.list_favorites(user_id)})


@router.post("/users/{user_id}/favorites/{stable_route_id}")
def add_favorite(user_id: str, stable_route_id: str, body: RouteSummaryRequest | None = None) -> JSONResponse:
    summary = body.model_dump() if body else None
    favorite = controller.add_favorite(user_id, stable_route_id, summary)
    return JSONResponse(content={"item": favorite})


@router.delete("/users/{user_id}/favorites/{stable_route_id}")
def remove_favorite(user_id: str, stable_route_id: str) -> JSONResponse:
    controller.remove_favorite(user_id, stable_route_id)
    return JSONResponse(content={"ok": True})


@router.post("/users/{user_id}/views/{stable_route_id}")
def mark_viewed(user_id: str, stable_route_id: str) -> JSONResponse:
    controller.mark_viewed(user_id, stable_route_id)
    return JSONResponse(content={"ok": True})


@router.get("/{stable_route_id}", response_model=RouteCandidateResponse)
def get_shared_route(stable_route_id: str) -> RouteCandidateResponse:
    route = controller.get_shared_route(stable_route_id)
    if route is None:
        raise HTTPException(status_code=404, detail="Parcours introuvable ou expire")
    return route


@router.get("/{stable_route_id}/export.gpx")
def export_route_gpx(stable_route_id: str, user_id: str | None = Query(default=None)) -> Response:
    gpx = controller.export_route_gpx(stable_route_id)
    if gpx is None:
        raise HTTPException(status_code=404, detail="Export GPX indisponible")
    if user_id:
        controller.mark_exported(user_id=user_id, stable_route_id=stable_route_id, export_format="gpx")
    return Response(content=gpx, media_type="application/gpx+xml")


@router.get("/{stable_route_id}/export.geojson")
def export_route_geojson(stable_route_id: str, user_id: str | None = Query(default=None)) -> JSONResponse:
    geojson = controller.export_route_geojson(stable_route_id)
    if geojson is None:
        raise HTTPException(status_code=404, detail="Export GeoJSON indisponible")
    if user_id:
        controller.mark_exported(user_id=user_id, stable_route_id=stable_route_id, export_format="geojson")
    return JSONResponse(content=geojson)
