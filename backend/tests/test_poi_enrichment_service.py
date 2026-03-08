import unittest

from src.application.services.poi_enrichment_service import PoiEnrichmentService
from src.domain.entities.point_of_interest import PointOfInterest
from src.domain.entities.route_point import RoutePoint
from src.infrastructure.poi.osm_poi_client import OsmPoiCandidate


def _make_candidate(
    osm_id: str,
    tags: dict,
    lat: float = 48.85,
    lon: float = 2.35,
    osm_type: str = "node",
) -> OsmPoiCandidate:
    return OsmPoiCandidate(
        osm_id=osm_id,
        osm_type=osm_type,
        latitude=lat,
        longitude=lon,
        name="",
        tags=tags,
    )


def _make_poi(
    poi_id: str,
    category: str,
    lat: float,
    lon: float,
    distance_m: float = 20.0,
    score: float = 0.8,
    name: str = "Test POI",
) -> PointOfInterest:
    return PointOfInterest(
        id=poi_id,
        name=name,
        category=category,
        sub_category=None,
        latitude=lat,
        longitude=lon,
        distance_to_route_m=distance_m,
        distance_from_start_m=None,
        score=score,
        tags=[],
    )


class ClassifyTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.service = PoiEnrichmentService()

    def test_viewpoint(self) -> None:
        candidate = _make_candidate("1", {"tourism": "viewpoint"})
        result = self.service._classify(candidate)
        self.assertIsNotNone(result)
        self.assertEqual(result.category, "viewpoint")

    def test_peak(self) -> None:
        candidate = _make_candidate("2", {"natural": "peak"})
        result = self.service._classify(candidate)
        self.assertIsNotNone(result)
        self.assertEqual(result.category, "summit")

    def test_waterfall(self) -> None:
        candidate = _make_candidate("3", {"natural": "waterfall"})
        result = self.service._classify(candidate)
        self.assertIsNotNone(result)
        self.assertEqual(result.category, "water")
        self.assertEqual(result.sub_category, "waterfall")

    def test_castle(self) -> None:
        candidate = _make_candidate("4", {"historic": "castle"})
        result = self.service._classify(candidate)
        self.assertIsNotNone(result)
        self.assertEqual(result.category, "heritage")
        self.assertEqual(result.sub_category, "castle")

    def test_church(self) -> None:
        candidate = _make_candidate("5", {"amenity": "place_of_worship", "building": "church"})
        result = self.service._classify(candidate)
        self.assertIsNotNone(result)
        self.assertEqual(result.category, "heritage")

    def test_parking(self) -> None:
        candidate = _make_candidate("6", {"amenity": "parking"})
        result = self.service._classify(candidate)
        self.assertIsNotNone(result)
        self.assertEqual(result.category, "start_access")

    def test_forest(self) -> None:
        candidate = _make_candidate("7", {"natural": "wood"})
        result = self.service._classify(candidate)
        self.assertIsNotNone(result)
        self.assertEqual(result.category, "nature")

    def test_unknown_tags_returns_none(self) -> None:
        candidate = _make_candidate("8", {"shop": "bakery"})
        result = self.service._classify(candidate)
        self.assertIsNone(result)

    def test_tower_is_viewpoint(self) -> None:
        candidate = _make_candidate("9", {"man_made": "tower"})
        result = self.service._classify(candidate)
        self.assertIsNotNone(result)
        self.assertEqual(result.category, "viewpoint")

    def test_lake(self) -> None:
        candidate = _make_candidate("10", {"water": "lake"})
        result = self.service._classify(candidate)
        self.assertIsNotNone(result)
        self.assertEqual(result.category, "water")


class DeduplicateTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.service = PoiEnrichmentService()

    def test_removes_nearby_same_name(self) -> None:
        pois = [
            _make_poi("a", "viewpoint", 48.8500, 2.3500, name="Panorama"),
            _make_poi("b", "viewpoint", 48.8500, 2.3501, name="Panorama"),  # ~7m away
        ]
        result = self.service._deduplicate(pois)
        self.assertEqual(len(result), 1)

    def test_keeps_distinct_locations(self) -> None:
        pois = [
            _make_poi("a", "viewpoint", 48.8500, 2.3500, name="Vue A"),
            _make_poi("b", "viewpoint", 48.8600, 2.3600, name="Vue B"),  # ~1.4 km away
        ]
        result = self.service._deduplicate(pois)
        self.assertEqual(len(result), 2)

    def test_keeps_highest_score_on_duplicate(self) -> None:
        pois = [
            _make_poi("a", "viewpoint", 48.8500, 2.3500, score=0.5, name="Vue"),
            _make_poi("b", "viewpoint", 48.8500, 2.3501, score=0.9, name="Vue"),
        ]
        result = self.service._deduplicate(pois)
        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(result[0].score, 0.9)

    def test_different_categories_not_deduped(self) -> None:
        # Distinct names so same_name is False; different categories so same_category_no_name is False
        pois = [
            _make_poi("a", "viewpoint", 48.8500, 2.3500, name="Belvedere"),
            _make_poi("b", "water", 48.8500, 2.3500, name="Riviere"),
        ]
        result = self.service._deduplicate(pois)
        self.assertEqual(len(result), 2)


class DiversityScoreTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.service = PoiEnrichmentService()

    def test_single_category_low_score(self) -> None:
        pois = [_make_poi(str(i), "viewpoint", 48.85, 2.35) for i in range(3)]
        score = self.service._compute_diversity_score(pois)
        self.assertAlmostEqual(score, 0.30)

    def test_two_categories(self) -> None:
        pois = [
            _make_poi("1", "viewpoint", 48.85, 2.35),
            _make_poi("2", "water", 48.85, 2.35),
        ]
        score = self.service._compute_diversity_score(pois)
        self.assertAlmostEqual(score, 0.70)

    def test_four_categories_max(self) -> None:
        pois = [
            _make_poi("1", "viewpoint", 48.85, 2.35),
            _make_poi("2", "water", 48.85, 2.35),
            _make_poi("3", "heritage", 48.85, 2.35),
            _make_poi("4", "nature", 48.85, 2.35),
        ]
        score = self.service._compute_diversity_score(pois)
        self.assertAlmostEqual(score, 1.00)


class HighlightLabelsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.service = PoiEnrichmentService()

    def test_viewpoint_label(self) -> None:
        pois = [_make_poi("1", "viewpoint", 48.85, 2.35)]
        pois[0].sub_category = "viewpoint"
        labels = self.service._build_highlight_labels(pois)
        self.assertIn("Point de vue", labels)

    def test_waterfall_label(self) -> None:
        poi = _make_poi("1", "water", 48.85, 2.35)
        poi.sub_category = "waterfall"
        labels = self.service._build_highlight_labels([poi])
        self.assertIn("Cascade", labels)

    def test_max_highlights_respected(self) -> None:
        pois = [_make_poi(str(i), "viewpoint", 48.85 + i * 0.01, 2.35) for i in range(10)]
        labels = self.service._build_highlight_labels(pois)
        self.assertLessEqual(len(labels), self.service._MAX_HIGHLIGHTS)


class MaxDistanceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.service = PoiEnrichmentService()

    def test_water_way_uses_large_threshold(self) -> None:
        candidate = _make_candidate("1", {"water": "lake"}, osm_type="way")
        max_d = self.service._candidate_max_distance_m(candidate=candidate, category="water")
        self.assertEqual(max_d, PoiEnrichmentService._MAX_ROUTE_DISTANCE_WATER_WAY_M)

    def test_node_uses_default_threshold(self) -> None:
        candidate = _make_candidate("2", {"tourism": "viewpoint"}, osm_type="node")
        max_d = self.service._candidate_max_distance_m(candidate=candidate, category="viewpoint")
        self.assertEqual(max_d, PoiEnrichmentService._MAX_ROUTE_DISTANCE_M)


class RouteProjectionTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.service = PoiEnrichmentService()

    def _make_route_points(self) -> list[RoutePoint]:
        return [
            RoutePoint(latitude=48.8500, longitude=2.3500, elevation_m=100.0),
            RoutePoint(latitude=48.8510, longitude=2.3510, elevation_m=105.0),
            RoutePoint(latitude=48.8520, longitude=2.3520, elevation_m=110.0),
        ]

    def test_projected_route_has_correct_length(self) -> None:
        points = self._make_route_points()
        _ref_lat, _ref_lon, projected, cumulative = self.service._project_route(points)
        self.assertEqual(len(projected), 3)
        self.assertEqual(len(cumulative), 3)
        self.assertEqual(cumulative[0], 0.0)
        self.assertGreater(cumulative[-1], 0.0)

    def test_point_on_route_has_zero_distance(self) -> None:
        points = self._make_route_points()
        projected = self.service._project_route(points)
        dist, _ = self.service._distance_point_to_route(
            lat=48.8500,
            lon=2.3500,
            route_points=points,
            projected_route=projected,
        )
        self.assertLess(dist, 1.0)  # < 1 metre


if __name__ == "__main__":
    unittest.main()
