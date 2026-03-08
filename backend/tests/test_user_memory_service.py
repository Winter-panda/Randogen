import unittest

from src.application.services.user_memory_service import UserMemoryService
from src.domain.entities.route_candidate import RouteCandidate
from src.domain.entities.route_point import RoutePoint
from src.domain.entities.user_search import UserSearch


def _make_search(
    user_id: str,
    ambiance: str | None = None,
    terrain: str | None = None,
    effort: str | None = None,
    distance_km: float = 5.0,
) -> UserSearch:
    return UserSearch(
        user_id=user_id,
        latitude=48.85,
        longitude=2.35,
        target_distance_km=distance_km,
        route_count=3,
        ambiance=ambiance,
        terrain=terrain,
        effort=effort,
    )


def _make_route(
    route_id: str = "route-1",
    stable_id: str = "rte-test-1",
    points: list[RoutePoint] | None = None,
) -> RouteCandidate:
    return RouteCandidate(
        id=route_id,
        stable_route_id=stable_id,
        name="Parcours test",
        distance_km=5.0,
        estimated_duration_min=75,
        estimated_elevation_gain_m=110,
        score=0.8,
        route_type="equilibree",
        source="test",
        points=points or [],
    )


class UserMemoryServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.service = UserMemoryService()
        self.user_id = "unit-user"
        self.search = _make_search(self.user_id)
        self.route = _make_route()

    # --- History ---

    def test_record_generation_populates_history(self) -> None:
        self.service.record_generation(user_id=self.user_id, search=self.search, routes=[self.route])
        history = self.service.list_history(user_id=self.user_id)
        self.assertGreaterEqual(len(history), 1)
        self.assertEqual(history[0]["query"]["target_distance_km"], 5.0)

    def test_history_includes_result_route_ids(self) -> None:
        self.service.record_generation(user_id=self.user_id, search=self.search, routes=[self.route])
        history = self.service.list_history(user_id=self.user_id)
        self.assertIn("rte-test-1", history[0]["result_route_ids"])

    # --- Favorites ---

    def test_add_favorite_roundtrip(self) -> None:
        self.service.add_favorite(user_id=self.user_id, route=self.route)
        favorites = self.service.list_favorites(user_id=self.user_id)
        self.assertTrue(any(item["stable_route_id"] == "rte-test-1" for item in favorites))

    def test_remove_favorite(self) -> None:
        self.service.add_favorite(user_id=self.user_id, route=self.route)
        self.service.remove_favorite(user_id=self.user_id, stable_route_id="rte-test-1")
        favorites = self.service.list_favorites(user_id=self.user_id)
        self.assertFalse(any(item["stable_route_id"] == "rte-test-1" for item in favorites))

    def test_is_favorite_after_add(self) -> None:
        self.service.add_favorite(user_id=self.user_id, route=self.route)
        self.assertTrue(self.service.is_favorite(user_id=self.user_id, stable_route_id="rte-test-1"))

    def test_is_not_favorite_after_remove(self) -> None:
        self.service.add_favorite(user_id=self.user_id, route=self.route)
        self.service.remove_favorite(user_id=self.user_id, stable_route_id="rte-test-1")
        self.assertFalse(self.service.is_favorite(user_id=self.user_id, stable_route_id="rte-test-1"))

    # --- Seen recently ---

    def test_has_seen_recently_after_generation(self) -> None:
        self.service.record_generation(user_id=self.user_id, search=self.search, routes=[self.route])
        seen = self.service.has_seen_recently(user_id=self.user_id, stable_route_id="rte-test-1")
        self.assertTrue(seen)

    def test_has_not_seen_unknown_route(self) -> None:
        seen = self.service.has_seen_recently(user_id=self.user_id, stable_route_id="rte-unknown")
        self.assertFalse(seen)

    # --- Preference profile ---

    def test_preference_profile_no_data(self) -> None:
        profile = self.service.get_preference_profile(user_id="fresh-user-xyz")
        self.assertFalse(profile["has_data"])

    def test_preference_profile_returns_most_common_ambiance(self) -> None:
        uid = "pref-test-user"
        for _ in range(3):
            self.service.record_generation(
                user_id=uid,
                search=_make_search(uid, ambiance="nature"),
                routes=[_make_route("r1", "rte-p1")],
            )
        self.service.record_generation(
            user_id=uid,
            search=_make_search(uid, ambiance="calme"),
            routes=[_make_route("r2", "rte-p2")],
        )
        profile = self.service.get_preference_profile(user_id=uid)
        self.assertTrue(profile["has_data"])
        self.assertEqual(profile["suggested_ambiance"], "nature")

    def test_preference_profile_computes_average_distance(self) -> None:
        uid = "dist-test-user"
        for d in [4.0, 6.0]:
            self.service.record_generation(
                user_id=uid,
                search=_make_search(uid, distance_km=d),
                routes=[_make_route("r", f"rte-{d}")],
            )
        profile = self.service.get_preference_profile(user_id=uid)
        self.assertAlmostEqual(profile["average_distance_km"], 5.0)

    # --- Zone novelty ---

    def test_zone_novelty_zero_for_empty_history(self) -> None:
        route = _make_route(points=[RoutePoint(latitude=48.85, longitude=2.35, elevation_m=0.0)])
        penalty = self.service.compute_zone_novelty_factor(user_id="new-user", route=route)
        self.assertEqual(penalty, 0.0)

    def test_zone_novelty_zero_without_points(self) -> None:
        route = _make_route(points=[])
        penalty = self.service.compute_zone_novelty_factor(user_id=self.user_id, route=route)
        self.assertEqual(penalty, 0.0)

    # --- Build route summary with centroid ---

    def test_build_route_summary_includes_centroid(self) -> None:
        route = _make_route(
            points=[
                RoutePoint(latitude=48.00, longitude=2.00, elevation_m=0.0),
                RoutePoint(latitude=49.00, longitude=3.00, elevation_m=0.0),
            ]
        )
        summary = UserMemoryService._build_route_summary(route)
        self.assertAlmostEqual(summary["centroid_lat"], 48.5, places=1)
        self.assertAlmostEqual(summary["centroid_lon"], 2.5, places=1)

    def test_build_route_summary_centroid_none_without_points(self) -> None:
        route = _make_route(points=[])
        summary = UserMemoryService._build_route_summary(route)
        self.assertIsNone(summary["centroid_lat"])
        self.assertIsNone(summary["centroid_lon"])

    # --- add_favorite_by_summary ---

    def test_add_favorite_by_summary(self) -> None:
        uid = "fav-summary-user"
        summary = {
            "name": "Parcours résumé",
            "distance_km": 7.5,
            "estimated_duration_min": 90,
            "estimated_elevation_gain_m": 120,
            "difficulty": "moderee",
            "score": 0.75,
            "tags": ["Nature", "Calme"],
            "highlighted_poi_labels": ["Point de vue"],
        }
        result = self.service.add_favorite_by_summary(
            user_id=uid,
            stable_route_id="rte-summary-1",
            summary=summary,
        )
        self.assertEqual(result["stable_route_id"], "rte-summary-1")
        self.assertEqual(result["name"], "Parcours résumé")
        self.assertAlmostEqual(result["distance_km"], 7.5)
        self.assertIn("added_at", result)
        favorites = self.service.list_favorites(user_id=uid)
        self.assertTrue(any(f["stable_route_id"] == "rte-summary-1" for f in favorites))

    def test_add_favorite_by_summary_without_route_data(self) -> None:
        uid = "fav-empty-user"
        result = self.service.add_favorite_by_summary(
            user_id=uid,
            stable_route_id="rte-empty-1",
            summary={},
        )
        self.assertEqual(result["stable_route_id"], "rte-empty-1")
        self.assertEqual(result["name"], "")
        self.assertEqual(result["distance_km"], 0.0)

    # --- mark_seen_by_id ---

    def test_mark_seen_by_id_updates_existing(self) -> None:
        uid = "seen-update-user"
        self.service.record_generation(user_id=uid, search=_make_search(uid), routes=[_make_route("r", "rte-seen-1")])
        updated = self.service.mark_seen_by_id(user_id=uid, stable_route_id="rte-seen-1")
        self.assertTrue(updated)

    def test_mark_seen_by_id_returns_false_for_unknown(self) -> None:
        updated = self.service.mark_seen_by_id(user_id="fresh-user-abc", stable_route_id="rte-never-seen")
        self.assertFalse(updated)

    # --- Haversine ---

    def test_haversine_km_same_point(self) -> None:
        dist = UserMemoryService._haversine_km(48.85, 2.35, 48.85, 2.35)
        self.assertAlmostEqual(dist, 0.0, places=5)

    def test_haversine_km_known_distance(self) -> None:
        # Paris -> Lyon ≈ 392 km
        dist = UserMemoryService._haversine_km(48.8566, 2.3522, 45.7640, 4.8357)
        self.assertAlmostEqual(dist, 392.0, delta=5.0)


if __name__ == "__main__":
    unittest.main()
