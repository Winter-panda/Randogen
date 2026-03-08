import unittest

from src.domain.entities.route_point import RoutePoint
from src.infrastructure.poi.osm_poi_client import OsmPoiCandidate, OsmPoiClient


class OsmPoiClientTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.client = OsmPoiClient()

    def test_expand_bbox_increases_surface(self) -> None:
        south, west, north, east = 48.0, 2.0, 48.01, 2.01
        expanded = self.client._expand_bbox(
            south=south,
            west=west,
            north=north,
            east=east,
            extra_margin_m=500,
        )

        self.assertLess(expanded[0], south)
        self.assertLess(expanded[1], west)
        self.assertGreater(expanded[2], north)
        self.assertGreater(expanded[3], east)

    def test_merge_deduplicate_keeps_unique_candidates(self) -> None:
        first = [
            OsmPoiCandidate(
                osm_id="node:1",
                osm_type="node",
                name="Point de vue",
                latitude=48.8566,
                longitude=2.3522,
                tags={"tourism": "viewpoint"},
            )
        ]
        second = [
            OsmPoiCandidate(
                osm_id="node:1",
                osm_type="node",
                name="Point de vue",
                latitude=48.8566,
                longitude=2.3522,
                tags={"tourism": "viewpoint"},
            ),
            OsmPoiCandidate(
                osm_id="node:2",
                osm_type="node",
                name="Cascade",
                latitude=48.857,
                longitude=2.353,
                tags={"natural": "waterfall"},
            ),
        ]

        merged = self.client._merge_deduplicate(first, second)

        self.assertEqual(len(merged), 2)
        merged_ids = {item.osm_id for item in merged}
        self.assertEqual(merged_ids, {"node:1", "node:2"})

    def test_make_cache_key_stable_for_same_bbox(self) -> None:
        points = [
            RoutePoint(latitude=48.8566, longitude=2.3522),
            RoutePoint(latitude=48.857, longitude=2.353),
        ]
        min_lat = min(p.latitude for p in points)
        max_lat = max(p.latitude for p in points)
        min_lon = min(p.longitude for p in points)
        max_lon = max(p.longitude for p in points)

        key_a = self.client._make_cache_key(
            south=min_lat,
            west=min_lon,
            north=max_lat,
            east=max_lon,
            margin_m=1200,
        )
        key_b = self.client._make_cache_key(
            south=min_lat,
            west=min_lon,
            north=max_lat,
            east=max_lon,
            margin_m=1200,
        )

        self.assertEqual(key_a, key_b)


if __name__ == "__main__":
    unittest.main()
