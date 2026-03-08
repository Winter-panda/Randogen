import { useEffect, useState } from "react";
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
  facility: { label: "Services", icon: "🧭", color: "#0f766e" },
  start_access: { label: "Accès", icon: "🅿️", color: "#1d4ed8" }
};

interface MapViewProps {
  position: UserPosition | null;
  routes: RouteCandidate[];
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
  "#ea580c"
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
  selectedRouteId,
  selectedRoutePois
}: {
  position: UserPosition | null;
  routes: RouteCandidate[];
  selectedRouteId: string | null;
  selectedRoutePois: PointOfInterest[];
}) {
  const map = useMap();

  useEffect(() => {
    const selectedRoute = routes.find((route) => route.id === selectedRouteId);

    if (selectedRoute && selectedRoute.points.length > 0) {
      const boundsPoints: [number, number][] = selectedRoute.points.map((point) => [
        point.latitude,
        point.longitude
      ]);

      if (position) {
        boundsPoints.push([position.latitude, position.longitude]);
      }
      for (const poi of selectedRoutePois) {
        boundsPoints.push([poi.latitude, poi.longitude]);
      }

      const bounds: LatLngBoundsExpression = boundsPoints;
      map.flyToBounds(bounds, { padding: [30, 30], duration: 0.45 });
      return;
    }

    if (routes.length > 0) {
      const boundsPoints: [number, number][] = routes.flatMap((route) =>
        route.points.map((point) => [point.latitude, point.longitude] as [number, number])
      );

      if (position) {
        boundsPoints.push([position.latitude, position.longitude]);
      }

      if (boundsPoints.length > 0) {
        const bounds: LatLngBoundsExpression = boundsPoints;
        map.fitBounds(bounds, { padding: [30, 30] });
      }

      return;
    }

    if (position) {
      map.setView([position.latitude, position.longitude], 14);
    }
  }, [map, position, routes, selectedRouteId, selectedRoutePois]);

  return null;
}

export default function MapView({
  position,
  routes,
  selectedRouteId,
  hoveredRouteId,
  onSelectRoute,
  onHoverRoute
}: MapViewProps) {
  const [activeLayer, setActiveLayer] = useState<MapLayer>("topo");
  const [showPois, setShowPois] = useState<boolean>(true);
  const [poiFilter, setPoiFilter] = useState<PoiFilter>("all");
  const center: LatLngExpression = position
    ? [position.latitude, position.longitude]
    : defaultCenter;

  const layer = MAP_LAYERS[activeLayer];
  const selectedRoute = routes.find((route) => route.id === selectedRouteId) ?? null;
  const selectedRoutePois = selectedRoute?.pois ?? [];
  const visiblePois = selectedRoutePois.filter((poi) => poiFilter === "all" || poi.category === poiFilter);

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
            </button>
          ))}
        </div>
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
            selectedRouteId={selectedRouteId}
            selectedRoutePois={visiblePois}
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

          {routes.map((route, index) => {
            const color = routeColors[index % routeColors.length];
            const isSelected = selectedRouteId === route.id;
            const isHovered = hoveredRouteId === route.id;
            const hasSelection = selectedRouteId !== null;

            const polylinePositions: LatLngExpression[] = route.points.map((point) => [
              point.latitude,
              point.longitude
            ]);

            return (
              <Polyline
                key={route.id}
                positions={polylinePositions}
                pathOptions={{
                  color: hasSelection && !isSelected && !isHovered ? "#9ca3af" : color,
                  weight: isSelected ? 8 : isHovered ? 7 : 5,
                  opacity: hasSelection && !isSelected && !isHovered ? 0.35 : isHovered ? 1 : 0.9
                }}
                eventHandlers={{
                  click: () => onSelectRoute(route.id),
                  mouseover: () => onHoverRoute(route.id),
                  mouseout: () => onHoverRoute(null)
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

          {showPois && selectedRouteId !== null && visiblePois.map((poi) => (
            <CircleMarker
              key={poi.id}
              center={[poi.latitude, poi.longitude]}
              radius={8}
              pathOptions={{
                color: "#ffffff",
                weight: 2,
                fillColor: POI_CATEGORY_META[poi.category].color,
                fillOpacity: 0.95
              }}
            >
              <Popup>
                <strong>{POI_CATEGORY_META[poi.category].icon} {poi.name}</strong>
                <br />
                Type : {POI_CATEGORY_META[poi.category].label}
                <br />
                Distance au tracé : {Math.round(poi.distance_to_route_m)} m
                <br />
                Score POI : {Math.round(poi.score * 100)}%
              </Popup>
            </CircleMarker>
          ))}
        </MapContainer>
      </div>

      <div className="map-legend">
        {routes.map((route, index) => {
          const color = routeColors[index % routeColors.length];
          const isSelected = selectedRouteId === route.id;
          const isHovered = hoveredRouteId === route.id;

          return (
            <button
              key={route.id}
              type="button"
              className={`legend-item-button ${isSelected ? "selected" : ""} ${isHovered ? "hovered" : ""}`}
              onClick={() => onSelectRoute(route.id)}
              onMouseEnter={() => onHoverRoute(route.id)}
              onMouseLeave={() => onHoverRoute(null)}
            >
              <span className="legend-color" style={{ backgroundColor: color }} />
              <span>{route.name}</span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
