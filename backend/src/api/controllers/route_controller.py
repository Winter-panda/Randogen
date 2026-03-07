from src.application.dto.generate_route_request import GenerateRouteRequest
from src.application.dto.generate_route_response import GenerateRouteResponse
from src.application.usecases.generate_routes import GenerateRoutesUseCase


class RouteController:
    def __init__(self) -> None:
        self._generate_routes_usecase = GenerateRoutesUseCase()

    def generate_routes(
        self,
        request: GenerateRouteRequest,
    ) -> GenerateRouteResponse:
        return self._generate_routes_usecase.execute(request)
