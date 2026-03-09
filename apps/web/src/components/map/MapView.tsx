import { useEffect, useMemo, useRef, useState } from "react";
import {
  CircleMarker,
  MapContainer,
  Marker,
  Polyline,
  Popup,
  TileLayer,
  useMap
} from "react-leaflet";
import type { LatLngBoundsExpression, LatLngExpression } from "leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import markerIconUrl from "leaflet/dist/images/marker-icon.png";
import markerShadowUrl from "leaflet/dist/images/marker-shadow.png";

import type { PointOfInterest, RouteCandidate, UserPosition } from "../../types/route";

type MapLayer = "standard" | "topo" | "ign";
type PoiFilter = "all" | "viewpoint" | "water" | "summit" | "nature" | "heritage" | "facility" | "start_access";
type PoiCategory = Exclude<PoiFilter, "all">;

interface DisplayedPoi {
  poi: PointOfInterest;
  latitude: number;
  longitude: number;
  isOnSelectedRoute: boolean;
}

interface LayerConfig {
  label: string;
  url: string;
  attribution: string;
  maxZoom: number;
}

const MAP_LAYERS: Record<MapLayer, LayerConfig> = {
  standard: {
    label: "Standard",
    url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    attribution: "&copy; OpenStreetMap contributors",
    maxZoom: 19,
  },
  topo: {
    label: "Topographique",
    url: "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
    attribution:
      "Map data: &copy; OpenStreetMap contributors, SRTM | Map style: &copy; OpenTopoMap (CC-BY-SA)",
    maxZoom: 17,
  },
  ign: {
    label: "IGN France",
    url: "https://wxs.ign.fr/pratique/geoportail/wmts?REQUEST=GetTile&SERVICE=WMTS&VERSION=1.0.0&STYLE=normal&TILEMATRIXSET=PM&FORMAT=image/png&LAYER=GEOGRAPHICALGRIDSYSTEMS.PLANV2&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}",
    attribution: "&copy; IGN France",
    maxZoom: 18,
  },
};

const POI_CATEGORY_META: Record<PoiFilter, { label: string; icon: string; color: string }> = {
  all: { label: "Tous", icon: "•", color: "#475569" },
  viewpoint: { label: "Panorama", icon: "👁️", color: "#7c3aed" },
  water: { label: "Eau", icon: "💧", color: "#0284c7" },
  summit: { label: "Sommet", icon: "⛰️", color: "#334155" },
  nature: { label: "Nature", icon: "🌲", color: "#15803d" },
  heritage: { label: "Patrimoine", icon: "🏛️", color: "#b45309" },
  facility: { label: "Services & restau", icon: "🍽️", color: "#0f766e" },
  start_access: { label: "Parkings", icon: "🅿️", color: "#1d4ed8" }
};

const POI_CATEGORY_PRIORITY: PoiCategory[] = [
  "viewpoint",
  "water",
  "summit",
  "nature",
  "heritage",
  "facility",
  "start_access",
];

const POI_MIN_VISIBLE_BY_CATEGORY: Record<PoiCategory, number> = {
  viewpoint: 4,
  water: 5,
  summit: 2,
  nature: 5,
  heritage: 5,
  facility: 5,
  start_access: 5,
};

const POI_MAX_VISIBLE_BY_CATEGORY: Record<PoiCategory, number> = {
  viewpoint: 45,
  water: 55,
  summit: 30,
  nature: 55,
  heritage: 55,
  facility: 55,
  start_access: 55,
};

const POI_MAX_VISIBLE_TOTAL = 220;

function sortPoiEntries(entries: DisplayedPoi[]): DisplayedPoi[] {
  return [...entries].sort((a, b) => {
    if (a.isOnSelectedRoute !== b.isOnSelectedRoute) {
      return a.isOnSelectedRoute ? -1 : 1;
    }
    if (a.poi.score !== b.poi.score) {
      return b.poi.score - a.poi.score;
    }
    if (a.poi.distance_to_route_m !== b.poi.distance_to_route_m) {
      return a.poi.distance_to_route_m - b.poi.distance_to_route_m;
    }
    return a.poi.name.localeCompare(b.poi.name, "fr");
  });
}

function spreadOverlappingPois(entries: DisplayedPoi[]): DisplayedPoi[] {
  if (entries.length <= 1) {
    return entries;
  }

  const byCell = new Map<string, DisplayedPoi[]>();
  for (const entry of entries) {
    const key = `${entry.poi.latitude.toFixed(5)}:${entry.poi.longitude.toFixed(5)}`;
    const group = byCell.get(key);
    if (group) {
      group.push(entry);
    } else {
      byCell.set(key, [entry]);
    }
  }

  const spread: DisplayedPoi[] = [];
  for (const group of byCell.values()) {
    if (group.length === 1) {
      spread.push(group[0]);
      continue;
    }

    const sorted = [...group].sort((a, b) => a.poi.id.localeCompare(b.poi.id, "en"));
    const total = sorted.length;
    for (let i = 0; i < total; i += 1) {
      const entry = sorted[i];
      const ring = Math.floor(i / 8);
      const angle = ((i % 8) / 8) * 2 * Math.PI;
      const radiusMeters = 8 + (ring * 8);
      const latRadius = radiusMeters / 111_320;
      const lonRadius = radiusMeters / (111_320 * Math.max(0.2, Math.cos((entry.poi.latitude * Math.PI) / 180)));
      spread.push({
        ...entry,
        latitude: entry.poi.latitude + (Math.sin(angle) * latRadius),
        longitude: entry.poi.longitude + (Math.cos(angle) * lonRadius),
      });
    }
  }

  return spread;
}

function selectVisiblePois(entries: DisplayedPoi[], poiFilter: PoiFilter): DisplayedPoi[] {
  if (entries.length <= 1) {
    return entries;
  }

  const maxTotal = POI_MAX_VISIBLE_TOTAL;

  if (poiFilter !== "all") {
    const sorted = sortPoiEntries(entries);
    return spreadOverlappingPois(sorted.slice(0, maxTotal));
  }

  const byCategory: Record<PoiCategory, DisplayedPoi[]> = {
    viewpoint: [],
    water: [],
    summit: [],
    nature: [],
    heritage: [],
    facility: [],
    start_access: [],
  };

  for (const entry of entries) {
    byCategory[entry.poi.category].push(entry);
  }
  for (const category of POI_CATEGORY_PRIORITY) {
    byCategory[category] = sortPoiEntries(byCategory[category]);
  }

  const selected: DisplayedPoi[] = [];
  const seen = new Set<string>();
  const indexByCategory: Record<PoiCategory, number> = {
    viewpoint: 0,
    water: 0,
    summit: 0,
    nature: 0,
    heritage: 0,
    facility: 0,
    start_access: 0,
  };
  const countByCategory: Record<PoiCategory, number> = {
    viewpoint: 0,
    water: 0,
    summit: 0,
    nature: 0,
    heritage: 0,
    facility: 0,
    start_access: 0,
  };

  const pushIfPossible = (category: PoiCategory): boolean => {
    const list = byCategory[category];
    while (indexByCategory[category] < list.length) {
      const candidate = list[indexByCategory[category]];
      indexByCategory[category] += 1;
      if (seen.has(candidate.poi.id)) {
        continue;
      }
      selected.push(candidate);
      seen.add(candidate.poi.id);
      countByCategory[category] += 1;
      return true;
    }
    return false;
  };

  for (const category of POI_CATEGORY_PRIORITY) {
    const targetMin = Math.min(POI_MIN_VISIBLE_BY_CATEGORY[category], byCategory[category].length);
    while (countByCategory[category] < targetMin && selected.length < maxTotal) {
      if (!pushIfPossible(category)) {
        break;
      }
    }
  }

  let progress = true;
  while (selected.length < maxTotal && progress) {
    progress = false;
    for (const category of POI_CATEGORY_PRIORITY) {
      if (selected.length >= maxTotal) {
        break;
      }
      if (countByCategory[category] >= POI_MAX_VISIBLE_BY_CATEGORY[category]) {
        continue;
      }
      if (pushIfPossible(category)) {
        progress = true;
      }
    }
  }

  return spreadOverlappingPois(selected);
}

interface MapViewProps {
  position: UserPosition | null;
  routes: RouteCandidate[];
  nearbyPois: PointOfInterest[];
  selectedRouteId: string | null;
  hoveredRouteId: string | null;
  onSelectRoute: (routeId: string) => void;
  onHoverRoute: (routeId: string | null) => void;
}

const defaultCenter: LatLngExpression = [48.8566, 2.3522];

const routeColors = [
  "#2563eb",
  "#16a34a",
  "#dc2626",
  "#9333ea",
  "#ea580c",
];

const userIcon = L.icon({
  iconUrl: markerIconUrl,
  shadowUrl: markerShadowUrl,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
});

function MapViewportController({
  position,
  routes,
  visibleNearbyPois,
  selectedRoutePois,
  selectedRoutePoints,
  selectedRouteId,
}: {
  position: UserPosition | null;
  routes: RouteCandidate[];
  visibleNearbyPois: PointOfInterest[];
  selectedRoutePois: PointOfInterest[];
  selectedRoutePoints: Array<[number, number]>;
  selectedRouteId: string | null;
}) {
  const map = useMap();
  const lastFocusedRouteIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (!selectedRouteId || selectedRoutePoints.length < 2) {
      lastFocusedRouteIdRef.current = null;
      return;
    }

    if (lastFocusedRouteIdRef.current === selectedRouteId) {
      return;
    }

    const routeBounds: LatLngBoundsExpression = selectedRoutePoints;
    map.fitBounds(routeBounds, { padding: [35, 35], maxZoom: 16 });
    lastFocusedRouteIdRef.current = selectedRouteId;
  }, [map, selectedRouteId, selectedRoutePoints]);

  useEffect(() => {
    if (selectedRouteId && selectedRoutePoints.length > 1) {
      return;
    }

    const boundsPoints: [number, number][] = [];
    if (position) {
      boundsPoints.push([position.latitude, position.longitude]);
    }
    // When no route is selected, include all routes in viewport
    if (!selectedRouteId && routes.length > 0) {
      for (const route of routes) {
        for (const point of route.points) {
          boundsPoints.push([point.latitude, point.longitude]);
        }
      }
    }
    for (const poi of visibleNearbyPois) {
      boundsPoints.push([poi.latitude, poi.longitude]);
    }
    for (const poi of selectedRoutePois) {
      boundsPoints.push([poi.latitude, poi.longitude]);
    }
    for (const point of selectedRoutePoints) {
      boundsPoints.push(point);
    }

    if (boundsPoints.length > 1) {
      const bounds: LatLngBoundsExpression = boundsPoints;
      map.fitBounds(bounds, { padding: [35, 35] });
      return;
    }

    if (boundsPoints.length === 1) {
      map.setView(boundsPoints[0], 14);
    }
  }, [map, position, routes, selectedRouteId, selectedRoutePois, selectedRoutePoints, visibleNearbyPois]);

  return null;
}

export default function MapView({
  position,
  routes,
  nearbyPois,
  selectedRouteId,
  hoveredRouteId,
  onSelectRoute,
  onHoverRoute,
}: MapViewProps) {
  const [activeLayer, setActiveLayer] = useState<MapLayer>("topo");
  const [showPois, setShowPois] = useState<boolean>(true);
  const [poiFilter, setPoiFilter] = useState<PoiFilter>("all");
  const center: LatLngExpression = position
    ? [position.latitude, position.longitude]
    : defaultCenter;

  const layer = MAP_LAYERS[activeLayer];
  const selectedRoute = routes.find((route) => route.id === selectedRouteId) ?? null;
  const selectedRoutePolyline = useMemo<Array<[number, number]>>(
    () =>
      selectedRoute
        ? selectedRoute.points.map((point) => [point.latitude, point.longitude] as [number, number])
        : [],
    [selectedRoute]
  );
  const selectedRoutePois = selectedRoute?.pois ?? [];
  const mergedPoiEntries = useMemo<DisplayedPoi[]>(() => {
    const merged = new Map<string, DisplayedPoi>();
    for (const poi of nearbyPois) {
      merged.set(poi.id, {
        poi,
        latitude: poi.latitude,
        longitude: poi.longitude,
        isOnSelectedRoute: false,
      });
    }
    for (const poi of selectedRoutePois) {
      merged.set(poi.id, {
        poi,
        latitude: poi.latitude,
        longitude: poi.longitude,
        isOnSelectedRoute: true,
      });
    }
    return Array.from(merged.values());
  }, [nearbyPois, selectedRoutePois]);
  const poiCategoryCounts = useMemo<Record<PoiCategory, number>>(() => {
    const counts: Record<PoiCategory, number> = {
      viewpoint: 0,
      water: 0,
      summit: 0,
      nature: 0,
      heritage: 0,
      facility: 0,
      start_access: 0,
    };
    for (const entry of mergedPoiEntries) {
      counts[entry.poi.category] += 1;
    }
    return counts;
  }, [mergedPoiEntries]);
  const filteredPoiEntries = useMemo(
    () => mergedPoiEntries.filter((entry) => poiFilter === "all" || entry.poi.category === poiFilter),
    [mergedPoiEntries, poiFilter]
  );
  const displayedPois = useMemo(
    () => selectVisiblePois(filteredPoiEntries, poiFilter),
    [filteredPoiEntries, poiFilter]
  );
  const visibleRoutePois = useMemo(
    () => selectedRoutePois.filter((poi) => poiFilter === "all" || poi.category === poiFilter),
    [selectedRoutePois, poiFilter]
  );
  const visibleNearbyPois = useMemo(
    () => nearbyPois.filter((poi) => poiFilter === "all" || poi.category === poiFilter),
    [nearbyPois, poiFilter]
  );
  const selectedRoutePoiIds = useMemo(
    () => new Set(selectedRoutePois.map((poi) => poi.id)),
    [selectedRoutePois]
  );
  const routesToRender = useMemo(
    () => (selectedRouteId ? routes.filter((route) => route.id === selectedRouteId || route.id === hoveredRouteId) : routes),
    [routes, selectedRouteId, hoveredRouteId]
  );
  const poiIcons = useMemo(() => {
    const makeIcon = (icon: string, color: string, variant: "default" | "route") =>
      L.divIcon({
        className: "poi-marker-icon",
        html: `<span class="poi-marker-chip ${variant === "route" ? "poi-marker-chip-route" : ""}" style="--poi-color:${color}">${icon}</span>`,
        iconSize: variant === "route" ? [30, 30] : [28, 28],
        iconAnchor: variant === "route" ? [15, 15] : [14, 14],
        popupAnchor: [0, -14]
      });
    const categories: PoiCategory[] = ["viewpoint", "water", "summit", "nature", "heritage", "facility", "start_access"];
    const regular = {} as Record<PoiCategory, L.DivIcon>;
    const highlighted = {} as Record<PoiCategory, L.DivIcon>;
    for (const category of categories) {
      regular[category] = makeIcon(POI_CATEGORY_META[category].icon, POI_CATEGORY_META[category].color, "default");
      highlighted[category] = makeIcon(POI_CATEGORY_META[category].icon, POI_CATEGORY_META[category].color, "route");
    }
    return {
      regular,
      highlighted,
    };
  }, []);

  return (
    <section className="card map-card">
      <div className="map-header">
        <h2>Carte</h2>
        <div className="map-layer-switcher">
          {(Object.keys(MAP_LAYERS) as MapLayer[]).map((key) => (
            <button
              key={key}
              type="button"
              className={`map-layer-btn ${activeLayer === key ? "map-layer-btn-active" : ""}`}
              onClick={() => setActiveLayer(key)}
            >
              {MAP_LAYERS[key].label}
            </button>
          ))}
        </div>
      </div>

      <div className="map-poi-controls">
        <button
          type="button"
          className={`map-layer-btn ${showPois ? "map-layer-btn-active" : ""}`}
          onClick={() => setShowPois((value) => !value)}
        >
          {showPois ? "Masquer POI" : "Afficher POI"}
        </button>

        <div className="map-layer-switcher">
          {(Object.keys(POI_CATEGORY_META) as PoiFilter[]).map((key) => (
            <button
              key={key}
              type="button"
              className={`map-layer-btn ${poiFilter === key ? "map-layer-btn-active" : ""}`}
              onClick={() => setPoiFilter(key)}
            >
              {POI_CATEGORY_META[key].label}
              {" "}
              (
              {key === "all"
                ? mergedPoiEntries.length
                : poiCategoryCounts[key as PoiCategory]}
              )
            </button>
          ))}
        </div>
        <span className="map-poi-count">
          Affichés : {displayedPois.length}
        </span>
      </div>

      <div className="map-wrapper">
        <MapContainer center={center} zoom={13} scrollWheelZoom={true} className="map-container">
          <TileLayer
            key={activeLayer}
            attribution={layer.attribution}
            url={layer.url}
            maxZoom={layer.maxZoom}
          />

          <MapViewportController
            position={position}
            routes={routes}
            visibleNearbyPois={showPois ? visibleNearbyPois : []}
            selectedRoutePois={showPois ? visibleRoutePois : []}
            selectedRoutePoints={selectedRoutePolyline}
            selectedRouteId={selectedRouteId}
          />

          {position && (
            <>
              <Marker position={[position.latitude, position.longitude]} icon={userIcon}>
                <Popup>Votre position</Popup>
              </Marker>

              <CircleMarker
                center={[position.latitude, position.longitude]}
                radius={10}
                pathOptions={{
                  color: "#1d4ed8",
                  fillColor: "#60a5fa",
                  fillOpacity: 0.35
                }}
              />
            </>
          )}

          {routesToRender.map((route, index) => {
            const color = routeColors[index % routeColors.length];
            const isSelected = selectedRouteId === route.id;
            const isHovered = hoveredRouteId === route.id;
            const hasSelection = selectedRouteId !== null;
            const polylinePositions: LatLngExpression[] = route.points.map((point) => [
              point.latitude,
              point.longitude,
            ]);
            return (
              <Polyline
                key={route.id}
                positions={polylinePositions}
                pathOptions={{
                  color: hasSelection && !isSelected && !isHovered ? "#9ca3af" : color,
                  weight: isSelected ? 8 : isHovered ? 7 : 5,
                  opacity: hasSelection && !isSelected && !isHovered ? 0.35 : isHovered ? 1 : 0.9,
                }}
                eventHandlers={{
                  click: () => onSelectRoute(route.id),
                  mouseover: () => onHoverRoute(route.id),
                  mouseout: () => onHoverRoute(null),
                }}
              >
                <Popup>
                  <strong>{route.name}</strong>
                  <br />
                  Distance : {route.distance_km} km
                  <br />
                  Durée : {route.estimated_duration_min} min
                  <br />
                  Dénivelé : {route.estimated_elevation_gain_m} m
                  <br />
                  Score : {route.score}
                </Popup>
              </Polyline>
            );
          })}

          {showPois && displayedPois.map((entry) => (
            <Marker
              key={entry.poi.id}
              position={[entry.latitude, entry.longitude]}
              icon={entry.isOnSelectedRoute ? poiIcons.highlighted[entry.poi.category] : poiIcons.regular[entry.poi.category]}
              zIndexOffset={entry.isOnSelectedRoute ? 1200 : 700}
            >
              <Popup>
                <strong>{POI_CATEGORY_META[entry.poi.category].icon} {entry.poi.name}</strong>
                <br />
                Type : {POI_CATEGORY_META[entry.poi.category].label}
                <br />
                {selectedRoutePoiIds.has(entry.poi.id)
                  ? `Distance au tracé : ${Math.round(entry.poi.distance_to_route_m)} m`
                  : `Distance à vous : ${Math.round(entry.poi.distance_to_route_m)} m`}
                <br />
                {selectedRoutePoiIds.has(entry.poi.id) ? "Sur le parcours sélectionné" : "POI proche (rayon 5 km)"}
                <br />
                Score POI : {Math.round(entry.poi.score * 100)}%
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      </div>
    </section>
  );
}
