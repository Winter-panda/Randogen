export const AMBIANCE_LABELS: Record<string, string> = {
  equilibree: "Équilibrée",
  sentiers: "Sentiers",
  nature: "Nature",
  calme: "Calme",
};

export const TERRAIN_LABELS: Record<string, string> = {
  plat: "Terrain plat",
  vallonne: "Vallonné",
};

export const EFFORT_LABELS: Record<string, string> = {
  promenade: "Promenade",
  sportif: "Sportif",
};

export const BIOME_LABELS: Record<string, string> = {
  foret: "Forêt",
  campagne: "Campagne",
  cotier: "Chemins côtiers",
  montagne: "Montagne",
  bord_eau: "Bord d'eau",
  patrimoine: "Patrimoine",
};

export const AMBIANCE_HINTS: Record<string, string> = {
  equilibree: "Mix équilibré de sentiers et de routes",
  sentiers: "Privilégie les chemins et sentiers naturels",
  nature: "Cadre verdoyant, forêts et espaces ouverts",
  calme: "Évite les zones bruyantes et très fréquentées",
};

export const TERRAIN_HINTS: Record<string, string> = {
  plat: "Peu de dénivelé, idéal pour une sortie facile",
  vallonne: "Relief marqué avec montées et descentes",
};

export const EFFORT_HINTS: Record<string, string> = {
  promenade: "Allure tranquille, respect de la distance cible",
  sportif: "Effort soutenu, dénivelé et suitability favorisés",
};

export const BIOME_HINTS: Record<string, string> = {
  foret: "Favorise les zones boisées et sentiers en nature dense",
  campagne: "Privilégie les zones ouvertes, calmes et peu urbaines",
  cotier: "Favorise les parcours à proximité de l'eau",
  montagne: "Privilégie le relief, les points hauts et les panoramas",
  bord_eau: "Favorise lacs, rivières, étangs et portions proches de l'eau",
  patrimoine: "Privilégie les points d'intérêt historiques et monuments",
};

export function formatRouteType(routeType: string): string {
  if (!routeType || routeType === "libre") return "Libre";
  const map: Record<string, string> = {
    ...AMBIANCE_LABELS,
    ...TERRAIN_LABELS,
    ...EFFORT_LABELS,
    ...BIOME_LABELS,
  };
  return routeType
    .split(" + ")
    .map((part) => map[part.trim()] ?? part)
    .join(" · ");
}

export function formatFiltersLabel(
  ambiance: string | null,
  terrain: string | null,
  effort: string | null,
  biomePreference: string | null = null
): string {
  const parts: string[] = [];
  if (ambiance) parts.push(AMBIANCE_LABELS[ambiance] ?? ambiance);
  if (terrain) parts.push(TERRAIN_LABELS[terrain] ?? terrain);
  if (effort) parts.push(EFFORT_LABELS[effort] ?? effort);
  if (biomePreference) parts.push(BIOME_LABELS[biomePreference] ?? biomePreference);
  return parts.join(" · ") || "libre";
}

export function tagClass(tag: string): string {
  if (tag.startsWith("Idéal :")) return "route-tag route-tag-ideal";
  if (tag === "Idéal randonnée") return "route-tag route-tag-calm";
  if (tag.includes("Route") || tag.includes("route") || tag.includes("routier")) return "route-tag route-tag-road";
  if (tag.includes("calme") || tag.includes("tranquille")) return "route-tag route-tag-calm";
  if (tag.includes("vallonné") || tag.includes("plat") || tag.includes("dénivelé")) return "route-tag route-tag-elevation";
  return "route-tag";
}

export function formatScore(score: number): string {
  return `${Math.round(score * 10)}/10`;
}

export function difficultyClass(difficulty: string): string {
  if (difficulty === "facile") return "difficulty difficulty-easy";
  if (difficulty === "soutenue") return "difficulty difficulty-hard";
  return "difficulty difficulty-moderate";
}

export function formatDuration(minutes: number): string {
  if (minutes < 60) return `${minutes} min`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m === 0 ? `${h}h` : `${h}h${String(m).padStart(2, "0")}`;
}

// --- Comparative highlights across a set of routes ---

export type HighlightLabel =
  | "Meilleur nature"
  | "Le plus calme"
  | "Le plus sportif"
  | "Le plus plat"
  | "Plus de sentiers"
  | "Le plus précis";

interface ScoredRoute {
  id: string;
  score: number;
  nature_score: number;
  quiet_score: number;
  trail_ratio: number;
  estimated_elevation_gain_m: number;
  distance_km: number;
}

export function computeHighlights(routes: ScoredRoute[]): Map<string, HighlightLabel> {
  if (routes.length <= 1) return new Map();

  const assigned = new Map<string, HighlightLabel>();
  const taken = new Set<string>();

  function assignBest(
    label: HighlightLabel,
    score: (r: ScoredRoute) => number,
    minThreshold: number
  ) {
    const candidates = routes.filter((r) => !taken.has(r.id));
    if (candidates.length === 0) return;
    const best = candidates.reduce((a, b) => (score(a) >= score(b) ? a : b));
    if (score(best) >= minThreshold) {
      assigned.set(best.id, label);
      taken.add(best.id);
    }
  }

  assignBest("Meilleur nature", (r) => r.nature_score, 0.45);
  assignBest("Le plus calme", (r) => r.quiet_score, 0.45);
  assignBest(
    "Le plus sportif",
    (r) => (r.distance_km > 0 ? r.estimated_elevation_gain_m / r.distance_km : 0),
    30
  );
  assignBest(
    "Le plus plat",
    (r) => (r.distance_km > 0 ? 1 - r.estimated_elevation_gain_m / r.distance_km / 100 : 1),
    0.7
  );
  assignBest("Plus de sentiers", (r) => r.trail_ratio, 0.35);
  assignBest("Le plus précis", (r) => r.score, 0.4);

  return assigned;
}
