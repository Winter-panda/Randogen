import type {
  FavoriteItem,
  GenerateRoutesRequest,
  GenerateRoutesResponse,
  HistoryItem,
  PoiCategoryFilter,
  PointOfInterest,
  PreferenceProfile,
  RouteCandidate,
  WeatherData
} from "../../types/route";

function isNativeAndroidRuntime(): boolean {
  const maybeCapacitor = (globalThis as { Capacitor?: { isNativePlatform?: () => boolean } }).Capacitor;
  if (!maybeCapacitor?.isNativePlatform?.()) {
    return false;
  }
  if (typeof navigator === "undefined") {
    return false;
  }
  return /Android/i.test(navigator.userAgent);
}

function resolveApiBaseUrl(): string {
  const fromEnv = import.meta.env.VITE_API_URL;
  if (fromEnv && fromEnv.trim().length > 0) {
    return fromEnv;
  }
  // Android emulator maps host loopback to 10.0.2.2, not 127.0.0.1.
  if (isNativeAndroidRuntime()) {
    return "http://10.0.2.2:8010/api";
  }
  return "http://127.0.0.1:8010/api";
}

const API_BASE_URL = resolveApiBaseUrl();
const USER_ID_STORAGE_KEY = "randogen_user_id_v1";
const ALLOWED_POI_CATEGORIES: ReadonlyArray<PointOfInterest["category"]> = [
  "viewpoint",
  "water",
  "summit",
  "nature",
  "heritage",
  "facility",
  "start_access"
];

const MOJIBAKE_PATTERN = /[ÃÂ�□Æâ]/;
const MOJIBAKE_REPLACEMENTS: ReadonlyArray<[string, string]> = [
  ["Ã©", "é"],
  ["Ã¨", "è"],
  ["Ãª", "ê"],
  ["Ã«", "ë"],
  ["Ã ", "à"],
  ["Ã¢", "â"],
  ["Ã®", "î"],
  ["Ã´", "ô"],
  ["Ã¹", "ù"],
  ["Ã»", "û"],
  ["Ã§", "ç"],
  ["Å“", "œ"],
  ["Â°", "°"],
  ["Â", ""],
  ["â€™", "'"],
  ["â€œ", "\""],
  ["â€\u009d", "\""],
  ["â€“", "-"],
  ["â€”", "-"],
  ["â€¦", "..."],
];

function fixMojibakeText(value: string): string {
  if (!value) return value;

  let fixed = value;
  if (MOJIBAKE_PATTERN.test(fixed)) {
    for (let i = 0; i < 2; i += 1) {
      let changed = false;
      for (const [from, to] of MOJIBAKE_REPLACEMENTS) {
        if (fixed.includes(from)) {
          fixed = fixed.split(from).join(to);
          changed = true;
        }
      }
      if (!changed) break;
    }
  }

  return fixed
    .replace(/[\uFFFD□]/g, "")
    .replace(/[\u0000-\u001F\u007F]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function sanitizeDifficulty(value: string): string {
  const cleaned = fixMojibakeText(value).toLowerCase();
  if (cleaned.includes("fac")) return "facile";
  if (cleaned.includes("sout")) return "soutenue";
  if (cleaned.includes("mod")) return "moderee";
  return "moderee";
}

function sanitizePoiCategory(value: string): PointOfInterest["category"] {
  const normalized = fixMojibakeText(value).toLowerCase().trim();
  if ((ALLOWED_POI_CATEGORIES as ReadonlyArray<string>).includes(normalized)) {
    return normalized as PointOfInterest["category"];
  }
  if (normalized.includes("view")) return "viewpoint";
  if (normalized.includes("water") || normalized.includes("eau")) return "water";
  if (normalized.includes("summit") || normalized.includes("peak")) return "summit";
  if (normalized.includes("herit")) return "heritage";
  if (normalized.includes("access") || normalized.includes("start") || normalized.includes("parking")) {
    return "start_access";
  }
  if (normalized.includes("facility") || normalized.includes("service") || normalized.includes("amenity")) {
    return "facility";
  }
  return "nature";
}

function sanitizePoi(poi: PointOfInterest): PointOfInterest {
  return {
    ...poi,
    name: fixMojibakeText(poi.name),
    category: sanitizePoiCategory(poi.category),
    sub_category: poi.sub_category ? fixMojibakeText(poi.sub_category) : poi.sub_category,
    tags: (poi.tags ?? []).map((tag) => fixMojibakeText(tag)).filter((tag) => tag.length > 0)
  };
}

function buildTagsFromMetrics(route: RouteCandidate): string[] {
  const tags: string[] = [];

  if (route.trail_ratio >= 0.7) tags.push("Sentiers dominants");
  else if (route.trail_ratio >= 0.4) tags.push("Bon mix sentiers");

  if (route.road_ratio < 0.05) tags.push("Sans route");
  else if (route.road_ratio < 0.2) tags.push("Tres peu de routes");
  else if (route.road_ratio >= 0.6) tags.push("Passage routier");

  if (route.nature_score >= 0.7) tags.push("Tres nature");
  else if (route.nature_score >= 0.5) tags.push("Cadre verdoyant");

  if (route.quiet_score >= 0.7) tags.push("Tres calme");
  else if (route.quiet_score >= 0.5) tags.push("Ambiance tranquille");

  if (route.hiking_suitability_score >= 0.7) tags.push("Ideal randonnee");

  const gainPerKm = route.distance_km > 0 ? route.estimated_elevation_gain_m / route.distance_km : 0;
  if (gainPerKm >= 80) tags.push("Tres vallonne");
  else if (gainPerKm >= 35) tags.push("Quelques deniveles");
  else tags.push("Terrain plat");

  return tags;
}

function sanitizeRoute(route: RouteCandidate): RouteCandidate {
  const cleanedTags = route.tags.map((tag) => fixMojibakeText(tag)).filter((tag) => tag.length > 0);
  const hasBrokenTags = cleanedTags.some((tag) => /[ÃÂ�□Æâ]/.test(tag));
  const cleanedHighlights = (route.highlighted_poi_labels ?? [])
    .map((label) => fixMojibakeText(label))
    .filter((label) => label.length > 0);
  const cleanedNarrative = (route.poi_highlights ?? [])
    .map((line) => fixMojibakeText(line))
    .filter((line) => line.length > 0);
  const cleanedExplanation = route.explanation ? fixMojibakeText(route.explanation) : "";
  const cleanedDescription = route.description ? fixMojibakeText(route.description) : "";
  const cleanedExplanationReasons = (route.explanation_reasons ?? [])
    .map((reason) => fixMojibakeText(reason))
    .filter((reason) => reason.length > 0);
  const cleanedContextWarnings = (route.context_warnings ?? [])
    .map((warning) => fixMojibakeText(warning))
    .filter((warning) => warning.length > 0);

  const cleanedPois: PointOfInterest[] = (route.pois ?? []).map((poi) => sanitizePoi(poi));

  return {
    ...route,
    name: fixMojibakeText(route.name),
    route_type: fixMojibakeText(route.route_type),
    difficulty: sanitizeDifficulty(route.difficulty),
    tags: hasBrokenTags || cleanedTags.length === 0 ? buildTagsFromMetrics(route) : cleanedTags,
    pois: cleanedPois,
    highlighted_poi_labels: cleanedHighlights,
    poi_highlights: cleanedNarrative,
    explanation: cleanedExplanation,
    explanation_reasons: cleanedExplanationReasons,
    description: cleanedDescription,
    stable_route_id: route.stable_route_id ?? route.id,
    context_warnings: cleanedContextWarnings,
    seen_before: Boolean(route.seen_before)
  };
}

export function getOrCreateUserId(): string {
  const existing = window.localStorage.getItem(USER_ID_STORAGE_KEY);
  if (existing && existing.trim().length > 0) {
    return existing;
  }
  const generated = `u-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
  window.localStorage.setItem(USER_ID_STORAGE_KEY, generated);
  return generated;
}

export async function generateRoutes(
  payload: GenerateRoutesRequest
): Promise<GenerateRoutesResponse> {
  const response = await fetch(`${API_BASE_URL}/routes/generate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    throw new Error(`Erreur API (${response.status})`);
  }

  const data = (await response.json()) as GenerateRoutesResponse;
  return {
    ...data,
    status: data.status ?? "ok",
    warnings: (data.warnings ?? []).map((item) => fixMojibakeText(item)).filter((item) => item.length > 0),
    requested_route_count: data.requested_route_count ?? data.routes.length,
    generated_route_count: data.generated_route_count ?? data.routes.length,
    routes: data.routes.map((route) => sanitizeRoute(route))
  };
}

export async function getSharedRoute(stableRouteId: string): Promise<RouteCandidate> {
  const response = await fetch(`${API_BASE_URL}/routes/${encodeURIComponent(stableRouteId)}`);
  if (!response.ok) {
    throw new Error("Parcours partagé introuvable");
  }
  const data = (await response.json()) as RouteCandidate;
  return sanitizeRoute(data);
}

export async function downloadRouteGpx(stableRouteId: string): Promise<Blob> {
  const userId = getOrCreateUserId();
  const response = await fetch(`${API_BASE_URL}/routes/${encodeURIComponent(stableRouteId)}/export.gpx?user_id=${encodeURIComponent(userId)}`);
  if (!response.ok) {
    throw new Error("Export GPX impossible");
  }
  return await response.blob();
}

export async function downloadRouteGeoJson(stableRouteId: string): Promise<Blob> {
  const userId = getOrCreateUserId();
  const response = await fetch(`${API_BASE_URL}/routes/${encodeURIComponent(stableRouteId)}/export.geojson?user_id=${encodeURIComponent(userId)}`);
  if (!response.ok) {
    throw new Error("Export GeoJSON impossible");
  }
  return await response.blob();
}

export function buildShareUrl(stableRouteId: string): string {
  const url = new URL(window.location.href);
  url.searchParams.set("route", stableRouteId);
  return url.toString();
}

export async function listHistory(userId: string): Promise<HistoryItem[]> {
  const response = await fetch(`${API_BASE_URL}/routes/users/${encodeURIComponent(userId)}/history`);
  if (!response.ok) {
    throw new Error("Historique indisponible");
  }
  const data = (await response.json()) as { items: HistoryItem[] };
  return data.items ?? [];
}

export async function listFavorites(userId: string): Promise<FavoriteItem[]> {
  const response = await fetch(`${API_BASE_URL}/routes/users/${encodeURIComponent(userId)}/favorites`);
  if (!response.ok) {
    throw new Error("Favoris indisponibles");
  }
  const data = (await response.json()) as { items: FavoriteItem[] };
  return data.items ?? [];
}

export async function addFavorite(userId: string, stableRouteId: string, route?: RouteCandidate): Promise<void> {
  const body = route ? JSON.stringify({
    name: route.name,
    distance_km: route.distance_km,
    estimated_duration_min: route.estimated_duration_min,
    estimated_elevation_gain_m: route.estimated_elevation_gain_m,
    difficulty: route.difficulty,
    score: route.score,
    tags: route.tags.slice(0, 6),
    highlighted_poi_labels: (route.highlighted_poi_labels ?? []).slice(0, 3),
  }) : undefined;
  const response = await fetch(
    `${API_BASE_URL}/routes/users/${encodeURIComponent(userId)}/favorites/${encodeURIComponent(stableRouteId)}`,
    {
      method: "POST",
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body,
    },
  );
  if (!response.ok) {
    throw new Error("Impossible d'ajouter aux favoris");
  }
}

export async function removeFavorite(userId: string, stableRouteId: string): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/routes/users/${encodeURIComponent(userId)}/favorites/${encodeURIComponent(stableRouteId)}`,
    { method: "DELETE" },
  );
  if (!response.ok) {
    throw new Error("Impossible de retirer le favori");
  }
}

export async function markRouteViewed(userId: string, stableRouteId: string): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/routes/users/${encodeURIComponent(userId)}/views/${encodeURIComponent(stableRouteId)}`,
    { method: "POST" },
  );
  if (!response.ok) {
    throw new Error("Impossible de marquer le parcours comme vu");
  }
}

export async function getUserPreferenceProfile(userId: string): Promise<PreferenceProfile> {
  const response = await fetch(`${API_BASE_URL}/routes/users/${encodeURIComponent(userId)}/preferences`);
  if (!response.ok) {
    throw new Error("Profil de préférences indisponible");
  }
  return (await response.json()) as PreferenceProfile;
}

export async function fetchWeather(lat: number, lon: number): Promise<WeatherData> {
  const response = await fetch(`${API_BASE_URL}/routes/weather?lat=${lat}&lon=${lon}`);
  if (!response.ok) {
    throw new Error("Météo indisponible");
  }
  const data = (await response.json()) as Partial<WeatherData>;
  if (
    typeof data?.temperature_c !== "number"
    || typeof data?.precipitation_mm !== "number"
    || typeof data?.wind_kmh !== "number"
    || typeof data?.weather_code !== "number"
  ) {
    throw new Error("Météo indisponible");
  }
  return data as WeatherData;
}

export async function fetchNearbyPois(
  lat: number,
  lon: number,
  options?: {
    radiusKm?: number;
    categories?: PoiCategoryFilter[];
    limit?: number;
  }
): Promise<PointOfInterest[]> {
  const params = new URLSearchParams();
  params.set("lat", String(lat));
  params.set("lon", String(lon));
  params.set("radius_km", String(options?.radiusKm ?? 5));
  params.set("limit", String(options?.limit ?? 250));
  for (const category of options?.categories ?? []) {
    params.append("categories", category);
  }

  const response = await fetch(`${API_BASE_URL}/routes/pois/nearby?${params.toString()}`);
  if (!response.ok) {
    let detail = "POI indisponibles";
    try {
      const data = (await response.json()) as { detail?: string };
      if (typeof data.detail === "string" && data.detail.trim().length > 0) {
        detail = data.detail.trim();
      }
    } catch {
      // ignore malformed error payload
    }
    throw new Error(detail);
  }
  const data = await response.json();
  if (!Array.isArray(data)) {
    throw new Error("Format POI invalide");
  }
  return data.map((poi) => sanitizePoi(poi as PointOfInterest));
}
