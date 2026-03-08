from __future__ import annotations

import copy
import json
import math
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src.domain.entities.route_candidate import RouteCandidate
from src.domain.entities.user_search import UserSearch

_memory_lock = threading.Lock()
_memory_data: dict[str, Any] | None = None


class UserMemoryService:
    def __init__(self) -> None:
        self._store_path = Path(__file__).resolve().parents[3] / "data" / "user_memory.json"

    def record_generation(self, *, user_id: str, search: UserSearch, routes: list[RouteCandidate]) -> None:
        normalized_user = self._normalize_user_id(user_id)
        with _memory_lock:
            data = self._load_locked()
            user = self._ensure_user_locked(data, normalized_user)
            now = self._now_iso()

            history_entry = {
                "timestamp": now,
                "query": {
                    "latitude": search.latitude,
                    "longitude": search.longitude,
                    "target_distance_km": search.target_distance_km,
                    "route_count": search.route_count,
                    "ambiance": search.ambiance,
                    "terrain": search.terrain,
                    "effort": search.effort,
                    "biome_preference": search.biome_preference,
                },
                "result_route_ids": [route.stable_route_id for route in routes if route.stable_route_id],
            }
            user["history"].insert(0, history_entry)
            user["history"] = user["history"][:50]

            for route in routes:
                if route.stable_route_id:
                    self._upsert_seen_route_locked(user=user, route=route, event="generated")

            self._save_locked(data)

    def mark_route_viewed(self, *, user_id: str, route: RouteCandidate) -> None:
        if not route.stable_route_id:
            return
        with _memory_lock:
            data = self._load_locked()
            user = self._ensure_user_locked(data, self._normalize_user_id(user_id))
            self._upsert_seen_route_locked(user=user, route=route, event="viewed")
            self._save_locked(data)

    def mark_route_exported(self, *, user_id: str, route: RouteCandidate, export_format: str) -> None:
        if not route.stable_route_id:
            return
        with _memory_lock:
            data = self._load_locked()
            user = self._ensure_user_locked(data, self._normalize_user_id(user_id))
            self._upsert_seen_route_locked(user=user, route=route, event=f"export:{export_format}")
            self._save_locked(data)

    def add_favorite(self, *, user_id: str, route: RouteCandidate) -> dict[str, Any]:
        if not route.stable_route_id:
            raise ValueError("Route stable id is required for favorites.")
        with _memory_lock:
            data = self._load_locked()
            user = self._ensure_user_locked(data, self._normalize_user_id(user_id))
            favorite = self._build_route_summary(route)
            favorite["added_at"] = self._now_iso()
            user["favorites"][route.stable_route_id] = favorite
            self._save_locked(data)
            return copy.deepcopy(favorite)

    def add_favorite_by_summary(self, *, user_id: str, stable_route_id: str, summary: dict[str, Any]) -> dict[str, Any]:
        """Enregistre un favori directement depuis les données client (sans besoin du cache serveur)."""
        if not stable_route_id:
            raise ValueError("stable_route_id is required for favorites.")
        with _memory_lock:
            data = self._load_locked()
            user = self._ensure_user_locked(data, self._normalize_user_id(user_id))
            favorite = {
                "stable_route_id": stable_route_id,
                "name": str(summary.get("name", "")),
                "distance_km": float(summary.get("distance_km", 0.0)),
                "estimated_duration_min": int(summary.get("estimated_duration_min", 0)),
                "estimated_elevation_gain_m": int(summary.get("estimated_elevation_gain_m", 0)),
                "difficulty": str(summary.get("difficulty", "moderee")),
                "score": float(summary.get("score", 0.0)),
                "tags": list(summary.get("tags", []))[:6],
                "highlighted_poi_labels": list(summary.get("highlighted_poi_labels", []))[:3],
                "added_at": self._now_iso(),
            }
            user["favorites"][stable_route_id] = favorite
            self._save_locked(data)
            return copy.deepcopy(favorite)

    def mark_seen_by_id(self, *, user_id: str, stable_route_id: str) -> bool:
        """Met à jour last_seen_at si la route est déjà dans seen_routes (sans besoin du cache serveur)."""
        with _memory_lock:
            data = self._load_locked()
            user = self._ensure_user_locked(data, self._normalize_user_id(user_id))
            now = self._now_iso()
            for item in user["seen_routes"]:
                if item.get("stable_route_id") == stable_route_id:
                    item["last_seen_at"] = now
                    item["last_event"] = "viewed"
                    self._save_locked(data)
                    return True
        return False

    def remove_favorite(self, *, user_id: str, stable_route_id: str) -> None:
        with _memory_lock:
            data = self._load_locked()
            user = self._ensure_user_locked(data, self._normalize_user_id(user_id))
            user["favorites"].pop(stable_route_id, None)
            self._save_locked(data)

    def list_history(self, *, user_id: str) -> list[dict[str, Any]]:
        with _memory_lock:
            data = self._load_locked()
            user = self._ensure_user_locked(data, self._normalize_user_id(user_id))
            return copy.deepcopy(user["history"])

    def list_favorites(self, *, user_id: str) -> list[dict[str, Any]]:
        with _memory_lock:
            data = self._load_locked()
            user = self._ensure_user_locked(data, self._normalize_user_id(user_id))
            favorites = list(user["favorites"].values())
            favorites.sort(key=lambda item: item.get("added_at", ""), reverse=True)
            return copy.deepcopy(favorites)

    def has_seen_recently(self, *, user_id: str, stable_route_id: str, within_hours: int = 72) -> bool:
        with _memory_lock:
            data = self._load_locked()
            user = self._ensure_user_locked(data, self._normalize_user_id(user_id))
            cutoff = datetime.now(timezone.utc) - timedelta(hours=within_hours)
            for item in user["seen_routes"]:
                if item.get("stable_route_id") != stable_route_id:
                    continue
                when = self._parse_iso(item.get("last_seen_at"))
                if when is not None and when >= cutoff:
                    return True
            return False

    def is_favorite(self, *, user_id: str, stable_route_id: str) -> bool:
        with _memory_lock:
            data = self._load_locked()
            user = self._ensure_user_locked(data, self._normalize_user_id(user_id))
            return stable_route_id in user["favorites"]

    def _upsert_seen_route_locked(self, *, user: dict[str, Any], route: RouteCandidate, event: str) -> None:
        now = self._now_iso()
        for item in user["seen_routes"]:
            if item.get("stable_route_id") == route.stable_route_id:
                item["last_seen_at"] = now
                item["last_event"] = event
                return

        summary = self._build_route_summary(route)
        summary["last_seen_at"] = now
        summary["last_event"] = event
        user["seen_routes"].insert(0, summary)
        user["seen_routes"] = user["seen_routes"][:120]

    @staticmethod
    def _build_route_summary(route: RouteCandidate) -> dict[str, Any]:
        centroid_lat: float | None = None
        centroid_lon: float | None = None
        if route.points:
            centroid_lat = round(sum(p.latitude for p in route.points) / len(route.points), 6)
            centroid_lon = round(sum(p.longitude for p in route.points) / len(route.points), 6)
        return {
            "stable_route_id": route.stable_route_id,
            "name": route.name,
            "distance_km": route.distance_km,
            "estimated_duration_min": route.estimated_duration_min,
            "estimated_elevation_gain_m": route.estimated_elevation_gain_m,
            "difficulty": route.difficulty,
            "score": route.score,
            "tags": route.tags[:6],
            "highlighted_poi_labels": route.highlighted_poi_labels[:3],
            "centroid_lat": centroid_lat,
            "centroid_lon": centroid_lon,
        }

    def get_preference_profile(self, *, user_id: str) -> dict[str, Any]:
        """Analyse l'historique pour retourner le profil de préférences inféré."""
        with _memory_lock:
            data = self._load_locked()
            user = self._ensure_user_locked(data, self._normalize_user_id(user_id))
            history = list(user["history"])

        if not history:
            return {"has_data": False, "search_count": 0}

        ambiance_counts: dict[str, int] = {}
        terrain_counts: dict[str, int] = {}
        effort_counts: dict[str, int] = {}
        distances: list[float] = []

        for item in history[:20]:
            query = item.get("query", {})
            ambiance = query.get("ambiance")
            if ambiance:
                ambiance_counts[ambiance] = ambiance_counts.get(ambiance, 0) + 1
            terrain = query.get("terrain")
            if terrain:
                terrain_counts[terrain] = terrain_counts.get(terrain, 0) + 1
            effort = query.get("effort")
            if effort:
                effort_counts[effort] = effort_counts.get(effort, 0) + 1
            d = query.get("target_distance_km")
            if isinstance(d, (int, float)) and d > 0:
                distances.append(float(d))

        suggested_ambiance = max(ambiance_counts, key=ambiance_counts.__getitem__) if ambiance_counts else None
        suggested_terrain = max(terrain_counts, key=terrain_counts.__getitem__) if terrain_counts else None
        suggested_effort = max(effort_counts, key=effort_counts.__getitem__) if effort_counts else None
        avg_distance = round(sum(distances) / len(distances), 1) if distances else None

        return {
            "has_data": True,
            "search_count": len(history),
            "suggested_ambiance": suggested_ambiance,
            "suggested_terrain": suggested_terrain,
            "suggested_effort": suggested_effort,
            "average_distance_km": avg_distance,
            "ambiance_counts": ambiance_counts,
            "terrain_counts": terrain_counts,
            "effort_counts": effort_counts,
        }

    def compute_zone_novelty_factor(
        self,
        *,
        user_id: str,
        route: RouteCandidate,
        within_hours: int = 168,
    ) -> float:
        """Retourne une pénalité [0..0.06] si le centroïde du parcours est proche de routes récentes."""
        if not route.points:
            return 0.0

        centroid_lat = sum(p.latitude for p in route.points) / len(route.points)
        centroid_lon = sum(p.longitude for p in route.points) / len(route.points)

        with _memory_lock:
            data = self._load_locked()
            user = self._ensure_user_locked(data, self._normalize_user_id(user_id))
            seen_routes = list(user["seen_routes"])

        cutoff = datetime.now(timezone.utc) - timedelta(hours=within_hours)
        min_distance_km = float("inf")

        for item in seen_routes:
            if item.get("stable_route_id") == route.stable_route_id:
                continue
            when = self._parse_iso(item.get("last_seen_at"))
            if when is None or when < cutoff:
                continue
            prev_lat = item.get("centroid_lat")
            prev_lon = item.get("centroid_lon")
            if prev_lat is None or prev_lon is None:
                continue
            dist_km = self._haversine_km(centroid_lat, centroid_lon, float(prev_lat), float(prev_lon))
            if dist_km < min_distance_km:
                min_distance_km = dist_km

        if not math.isfinite(min_distance_km):
            return 0.0
        if min_distance_km < 1.0:
            return 0.06
        if min_distance_km < 3.0:
            return 0.03
        if min_distance_km < 6.0:
            return 0.01
        return 0.0

    @staticmethod
    def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        r = 6_371.0
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        d_phi = math.radians(lat2 - lat1)
        d_lambda = math.radians(lon2 - lon1)
        a = math.sin(d_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2.0) ** 2
        return r * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    @staticmethod
    def _normalize_user_id(user_id: str | None) -> str:
        value = (user_id or "anonymous").strip()
        return value[:100] or "anonymous"

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _parse_iso(value: object) -> datetime | None:
        if not isinstance(value, str) or not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    def _load_locked(self) -> dict[str, Any]:
        global _memory_data
        if _memory_data is not None:
            return _memory_data

        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        if not self._store_path.exists():
            _memory_data = {"users": {}}
            return _memory_data

        try:
            raw = self._store_path.read_text(encoding="utf-8")
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                parsed = {"users": {}}
        except (OSError, json.JSONDecodeError):
            parsed = {"users": {}}
        parsed.setdefault("users", {})
        _memory_data = parsed
        return _memory_data

    def _save_locked(self, data: dict[str, Any]) -> None:
        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        self._store_path.write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")

    @staticmethod
    def _ensure_user_locked(data: dict[str, Any], user_id: str) -> dict[str, Any]:
        users = data.setdefault("users", {})
        user = users.setdefault(
            user_id,
            {
                "history": [],
                "favorites": {},
                "seen_routes": [],
            },
        )
        user.setdefault("history", [])
        user.setdefault("favorites", {})
        user.setdefault("seen_routes", [])
        return user
