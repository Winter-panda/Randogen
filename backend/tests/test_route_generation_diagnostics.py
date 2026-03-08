import unittest

from src.application.services.route_generation_service import RouteGenerationService
from src.domain.entities.point_of_interest import PointOfInterest
from src.domain.entities.route_candidate import RouteCandidate
from src.domain.entities.user_search import UserSearch


class RouteGenerationDiagnosticsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.service = RouteGenerationService()
        self.search = UserSearch(
            user_id="test-user",
            latitude=48.8566,
            longitude=2.3522,
            target_distance_km=6.0,
            route_count=3,
        )

    def _build_route(self, *, with_poi: bool) -> RouteCandidate:
        route = RouteCandidate(
            id="route-1",
            name="Parcours 1",
            distance_km=6.0,
            estimated_duration_min=90,
            estimated_elevation_gain_m=120,
            score=0.8,
            route_type="equilibree",
            source="test",
        )
        if with_poi:
            route.pois = [
                PointOfInterest(
                    id="poi-1",
                    name="Point de vue",
                    category="viewpoint",
                    sub_category="viewpoint",
                    latitude=48.857,
                    longitude=2.353,
                    distance_to_route_m=30.0,
                    distance_from_start_m=1200.0,
                    score=0.9,
                    tags=["on_route"],
                )
            ]
        return route

    def test_diagnostics_fallback_with_partial_generation(self) -> None:
        routes = [self._build_route(with_poi=True)]
        self.service._set_generation_diagnostics(
            search=self.search,
            routes=routes,
            used_mock_fallback=True,
        )

        diagnostics = self.service.get_last_generation_diagnostics()

        self.assertEqual(diagnostics.status, "fallback")
        self.assertTrue(diagnostics.technical_issue)
        self.assertEqual(diagnostics.generated_route_count, 1)
        self.assertEqual(diagnostics.requested_route_count, 3)
        self.assertTrue(any("fallback" in warning.lower() for warning in diagnostics.warnings))

    def test_diagnostics_low_data_when_no_pois(self) -> None:
        routes = [self._build_route(with_poi=False) for _ in range(3)]
        self.service._set_generation_diagnostics(
            search=self.search,
            routes=routes,
            used_mock_fallback=False,
        )

        diagnostics = self.service.get_last_generation_diagnostics()

        self.assertEqual(diagnostics.status, "low_data")
        self.assertTrue(diagnostics.low_data)
        self.assertFalse(diagnostics.used_mock_fallback)


if __name__ == "__main__":
    unittest.main()
