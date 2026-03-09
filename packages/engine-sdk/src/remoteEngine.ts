import type {
  GenerateRoutesRequest,
  GenerateRoutesResponse,
  PointOfInterest,
  WeatherData
} from "@randogen/shared-types";
import type { NearbyPoiOptions, RouteEngine } from "./types";

export class RemoteEngine implements RouteEngine {
  constructor(private readonly apiBaseUrl: string) {}

  async generateRoutes(payload: GenerateRoutesRequest): Promise<GenerateRoutesResponse> {
    const response = await fetch(`${this.apiBaseUrl}/routes/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error(`generateRoutes failed (${response.status})`);
    return (await response.json()) as GenerateRoutesResponse;
  }

  async fetchNearbyPois(lat: number, lon: number, options?: NearbyPoiOptions): Promise<PointOfInterest[]> {
    const params = new URLSearchParams();
    params.set("lat", String(lat));
    params.set("lon", String(lon));
    params.set("radius_km", String(options?.radiusKm ?? 5));
    params.set("limit", String(options?.limit ?? 250));
    for (const category of options?.categories ?? []) params.append("categories", category);
    const response = await fetch(`${this.apiBaseUrl}/routes/pois/nearby?${params.toString()}`);
    if (!response.ok) throw new Error(`fetchNearbyPois failed (${response.status})`);
    return (await response.json()) as PointOfInterest[];
  }

  async fetchWeather(lat: number, lon: number): Promise<WeatherData | null> {
    const response = await fetch(`${this.apiBaseUrl}/routes/weather?lat=${lat}&lon=${lon}`);
    if (!response.ok) return null;
    return (await response.json()) as WeatherData;
  }

  async exportRouteGpx(stableRouteId: string, userId?: string): Promise<Blob> {
    const suffix = userId ? `?user_id=${encodeURIComponent(userId)}` : "";
    const response = await fetch(`${this.apiBaseUrl}/routes/${encodeURIComponent(stableRouteId)}/export.gpx${suffix}`);
    if (!response.ok) throw new Error(`exportRouteGpx failed (${response.status})`);
    return await response.blob();
  }
}
