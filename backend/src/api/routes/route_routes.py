from fastapi import APIRouter

from src.api.controllers.route_controller import RouteController
from src.application.dto.generate_route_request import GenerateRouteRequest
from src.application.dto.generate_route_response import GenerateRouteResponse

router = APIRouter(prefix="/routes", tags=["routes"])

controller = RouteController()


@router.post("/generate", response_model=GenerateRouteResponse)
def generate_routes(request: GenerateRouteRequest) -> GenerateRouteResponse:
    return controller.generate_routes(request)
