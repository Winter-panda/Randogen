export interface RoutePoint {
  latitude: number;
  longitude: number;
}

export interface RouteCandidate {
  id: string;
  name: string;
  distance_km: number;
  estimated_duration_min: number;
  estimated_elevation_gain_m: number;
  score: number;
  route_type: string;
  source: string;
  points: RoutePoint[];
}

export interface GenerateRoutesResponse {
  routes: RouteCandidate[];
}

export interface GenerateRoutesRequest {
  latitude: number;
  longitude: number;
  target_distance_km: number;
  route_count: number;
}

export interface UserPosition {
  latitude: number;
  longitude: number;
}
