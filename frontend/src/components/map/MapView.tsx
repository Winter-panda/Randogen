import { useEffect } from "react";
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

import type { RouteCandidate, UserPosition } from "../../types/route";

interface MapViewProps {
  position: UserPosition | null;
  routes: RouteCandidate[];
  selectedRouteId: string | null;
  onSelectRoute: (routeId: string) => void;
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
  selectedRouteId
}: {
  position: UserPosition | null;
  routes: RouteCandidate[];
  selectedRouteId: string | null;
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

      const bounds: LatLngBoundsExpression = boundsPoints;
      map.fitBounds(bounds, { padding: [30, 30] });
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
  }, [map, position, routes, selectedRouteId]);

  return null;
}

export default function MapView({
  position,
  routes,
  selectedRouteId,
  onSelectRoute
}: MapViewProps) {
  const center: LatLngExpression = position
    ? [position.latitude, position.longitude]
    : defaultCenter;

  return (
    <section className="card">
      <h2>Carte</h2>

      <div className="map-wrapper">
        <MapContainer center={center} zoom={13} scrollWheelZoom={true} className="map-container">
          <TileLayer
            attribution='&copy; OpenStreetMap contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          <MapViewportController
            position={position}
            routes={routes}
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

          {routes.map((route, index) => {
            const color = routeColors[index % routeColors.length];
            const isSelected = selectedRouteId === route.id;
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
                  color: hasSelection && !isSelected ? "#9ca3af" : color,
                  weight: isSelected ? 8 : 5,
                  opacity: hasSelection && !isSelected ? 0.5 : 0.9
                }}
                eventHandlers={{
                  click: () => onSelectRoute(route.id)
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
        </MapContainer>
      </div>

      <div className="map-legend">
        {routes.map((route, index) => {
          const color = routeColors[index % routeColors.length];
          const isSelected = selectedRouteId === route.id;

          return (
            <button
              key={route.id}
              type="button"
              className={`legend-item-button ${isSelected ? "selected" : ""}`}
              onClick={() => onSelectRoute(route.id)}
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
