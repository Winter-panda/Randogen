import type {
  GenerateRoutesRequest,
  GenerateRoutesResponse,
  PointOfInterest,
  WeatherData
} from "@randogen/shared-types";

export interface NearbyPoiOptions {
  radiusKm?: number;
  limit?: number;
  categories?: Array<
    "viewpoint" | "water" | "summit" | "nature" | "heritage" | "facility" | "start_access"
  >;
}

export interface RouteEngine {
  generateRoutes(payload: GenerateRoutesRequest): Promise<GenerateRoutesResponse>;
  fetchNearbyPois(lat: number, lon: number, options?: NearbyPoiOptions): Promise<PointOfInterest[]>;
  fetchWeather(lat: number, lon: number): Promise<WeatherData | null>;
  exportRouteGpx(stableRouteId: string, userId?: string): Promise<Blob>;
}
