export interface RoutePoint {
  latitude: number;
  longitude: number;
  elevation_m?: number;
}

export interface PointOfInterest {
  id: string;
  name: string;
  category: "viewpoint" | "water" | "summit" | "nature" | "heritage" | "facility" | "start_access";
  sub_category: string | null;
  latitude: number;
  longitude: number;
  distance_to_route_m: number;
  distance_from_start_m?: number | null;
  score: number;
  tags: string[];
}

export interface RouteCandidate {
  id: string;
  stable_route_id?: string;
  name: string;
  distance_km: number;
  estimated_duration_min: number;
  estimated_elevation_gain_m: number;
  score: number;
  route_type: string;
  source: string;
  trail_ratio: number;
  road_ratio: number;
  nature_score: number;
  quiet_score: number;
  hiking_suitability_score: number;
  difficulty: string;
  tags: string[];
  points: RoutePoint[];
  pois: PointOfInterest[];
  poi_score: number;
  poi_quantity_score?: number;
  poi_diversity_score?: number;
  poi_highlight_count?: number;
  highlighted_poi_labels: string[];
  poi_highlights?: string[];
  score_breakdown?: Record<string, number>;
  explanation?: string;
  explanation_reasons?: string[];
  description?: string;
  poi_on_route_count?: number;
  poi_near_route_count?: number;
  context_score_delta?: number;
  context_warnings?: string[];
  seen_before?: boolean;
}

export interface GenerateRoutesResponse {
  status: "ok" | "partial" | "fallback" | "low_data" | "error";
  warnings: string[];
  requested_route_count: number;
  generated_route_count: number;
  routes: RouteCandidate[];
}

export type AmbianceFilter = "equilibree" | "sentiers" | "nature" | "calme";
export type TerrainFilter = "plat" | "vallonne";
export type EffortFilter = "promenade" | "sportif";
export type DifficultyPref = "facile" | "moderee" | "difficile";

export interface GenerateRoutesRequest {
  user_id: string;
  latitude: number;
  longitude: number;
  target_distance_km: number;
  route_count: number;
  ambiance: AmbianceFilter | null;
  terrain: TerrainFilter | null;
  effort: EffortFilter | null;
  prioritize_nature: boolean;
  prioritize_viewpoints: boolean;
  prioritize_calm: boolean;
  avoid_urban: boolean;
  avoid_roads: boolean;
  avoid_steep: boolean;
  avoid_touristic: boolean;
  adapt_to_weather: boolean;
  difficulty_pref: DifficultyPref | null;
}

export interface HistoryItem {
  timestamp: string;
  query: {
    latitude: number;
    longitude: number;
    target_distance_km: number;
    route_count: number;
    ambiance: string | null;
    terrain: string | null;
    effort: string | null;
  };
  result_route_ids: string[];
}

export interface FavoriteItem {
  stable_route_id: string;
  name: string;
  distance_km: number;
  estimated_duration_min: number;
  estimated_elevation_gain_m: number;
  difficulty: string;
  score: number;
  tags: string[];
  highlighted_poi_labels: string[];
  added_at: string;
}

export interface WeatherData {
  temperature_c: number;
  precipitation_mm: number;
  wind_kmh: number;
  weather_code: number;
}

export interface UserPosition {
  latitude: number;
  longitude: number;
}

export interface PreferenceProfile {
  has_data: boolean;
  search_count: number;
  suggested_ambiance: AmbianceFilter | null;
  suggested_terrain: TerrainFilter | null;
  suggested_effort: EffortFilter | null;
  average_distance_km: number | null;
  ambiance_counts: Record<string, number>;
  terrain_counts: Record<string, number>;
  effort_counts: Record<string, number>;
}
