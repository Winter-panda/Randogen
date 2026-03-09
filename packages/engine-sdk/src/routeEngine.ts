import type {
  GenerateRoutesRequest,
  GenerateRoutesResponse,
  PoiCategoryFilter,
  PointOfInterest,
  WeatherData,
} from "@randogen/shared-types/route";

export interface NearbyPoisOptions {
  radiusKm?: number;
  categories?: PoiCategoryFilter[];
  limit?: number;
}

export interface ExportGpxOptions {
  userId?: string;
}

export interface RouteEngine {
  generateRoutes(payload: GenerateRoutesRequest): Promise<GenerateRoutesResponse>;
  fetchNearbyPois(
    latitude: number,
    longitude: number,
    options?: NearbyPoisOptions
  ): Promise<PointOfInterest[]>;
  getWeather(latitude: number, longitude: number): Promise<WeatherData>;
  exportGpx(stableRouteId: string, options?: ExportGpxOptions): Promise<Blob>;
}
