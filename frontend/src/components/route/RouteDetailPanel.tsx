import { useEffect, useMemo } from "react";
import { CircleMarker, MapContainer, Polyline, Popup, TileLayer, useMap } from "react-leaflet";
import type { LatLngBoundsExpression, LatLngExpression } from "leaflet";
import type { RouteCandidate } from "../../types/route";
import { difficultyClass, formatDuration, formatRouteType, formatScore, tagClass } from "../../utils/labels";

interface RouteDetailPanelProps {
  route: RouteCandidate;
  onDownloadGpx: () => void;
  onDownloadGeoJson: () => void;
  onShare: () => void;
  onOpenExternal: () => void;
  exportMessage: string;
}

function toPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function breakdownLabel(key: string): string {
  const labels: Record<string, string> = {
    distance: "Distance",
    sentiers: "Sentiers",
    nature: "Nature",
    calme: "Calme",
    suitability: "Rando",
    denivele: "Dénivelé",
    poi: "POI",
    final: "Final"
  };
  return labels[key] ?? key;
}

function DetailMiniMap({ route }: { route: RouteCandidate }) {
  const map = useMap();

  useEffect(() => {
    const boundsPoints: [number, number][] = [
      ...route.points.map((p) => [p.latitude, p.longitude] as [number, number]),
      ...route.pois.map((p) => [p.latitude, p.longitude] as [number, number])
    ];
    if (boundsPoints.length > 0) {
      const bounds: LatLngBoundsExpression = boundsPoints;
      map.fitBounds(bounds, { padding: [20, 20] });
    }
  }, [map, route]);

  return null;
}

export default function RouteDetailPanel({
  route,
  onDownloadGpx,
  onDownloadGeoJson,
  onShare,
  onOpenExternal,
  exportMessage
}: RouteDetailPanelProps) {
  const onRoutePois = useMemo(
    () => route.pois.filter((poi) => poi.distance_to_route_m <= 80).sort((a, b) => (a.distance_from_start_m ?? 1e9) - (b.distance_from_start_m ?? 1e9)),
    [route.pois]
  );
  const nearbyPois = useMemo(
    () => route.pois.filter((poi) => poi.distance_to_route_m > 80).sort((a, b) => (a.distance_from_start_m ?? 1e9) - (b.distance_from_start_m ?? 1e9)),
    [route.pois]
  );

  const center: LatLngExpression = route.points.length > 0
    ? [route.points[0].latitude, route.points[0].longitude]
    : [48.8566, 2.3522];

  return (
    <section className="card route-detail-panel detail-card">
      <div className="selected-route-header">
        <div>
          <h2>Fiche parcours</h2>
          <div className="route-meta">
            <span><strong>{route.name}</strong></span>
            <span>ID : {route.stable_route_id ?? route.id}</span>
            <span>Distance : {route.distance_km} km</span>
            <span>Durée : {formatDuration(route.estimated_duration_min)}</span>
            <span>Dénivelé : {route.estimated_elevation_gain_m} m</span>
            <span>Score : {formatScore(route.score)}</span>
            <span>Type : {formatRouteType(route.route_type)}</span>
            <span className={difficultyClass(route.difficulty)}>{route.difficulty}</span>
          </div>
          {route.description && <p className="route-poi-summary">{route.description}</p>}
        </div>
        <button type="button" className="download-button" onClick={onDownloadGpx}>Télécharger GPX</button>
      </div>
      <div className="route-export-actions">
        <button type="button" className="download-button" onClick={onDownloadGeoJson}>Télécharger GeoJSON</button>
        <button type="button" className="download-button" onClick={onShare}>Partager</button>
        <button type="button" className="download-button" onClick={onOpenExternal}>Ouvrir dans une autre application</button>
      </div>
      {exportMessage && <p className="hint">{exportMessage}</p>}

      {route.tags.length > 0 && (
        <div className="route-tags">
          {route.tags.map((tag) => (
            <span key={tag} className={tagClass(tag)}>{tag}</span>
          ))}
        </div>
      )}

      {(route.explanation || (route.explanation_reasons && route.explanation_reasons.length > 0)) && (
        <div className="route-explanation">
          <h3>Pourquoi ce parcours ?</h3>
          {route.explanation && <p>{route.explanation}</p>}
          {route.explanation_reasons && route.explanation_reasons.length > 0 && (
            <ul>
              {route.explanation_reasons.slice(0, 3).map((reason) => (
                <li key={`detail-reason-${reason}`}>{reason}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {route.score_breakdown && (
        <div className="route-breakdown">
          {Object.entries(route.score_breakdown)
            .filter(([key]) => ["distance", "sentiers", "nature", "calme", "poi", "final"].includes(key))
            .map(([key, value]) => (
              <div key={`detail-breakdown-${key}`} className="route-breakdown-item">
                <span>{breakdownLabel(key)}</span>
                <strong>{Math.round(value * 100)}%</strong>
              </div>
            ))}
        </div>
      )}

      <div className="route-detail-map">
        <MapContainer center={center} zoom={13} scrollWheelZoom className="route-detail-map-container">
          <TileLayer attribution="&copy; OpenStreetMap contributors" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
          <DetailMiniMap route={route} />
          <Polyline positions={route.points.map((p) => [p.latitude, p.longitude] as [number, number])} pathOptions={{ color: "#2563eb", weight: 6 }} />
          {route.pois.map((poi) => (
            <CircleMarker
              key={`detail-poi-${poi.id}`}
              center={[poi.latitude, poi.longitude]}
              radius={poi.distance_to_route_m <= 80 ? 7 : 5}
              pathOptions={{
                color: "#ffffff",
                weight: 2,
                fillColor: poi.distance_to_route_m <= 80 ? "#0ea5e9" : "#6366f1",
                fillOpacity: 0.95
              }}
            >
              <Popup>
                <strong>{poi.name}</strong><br />
                Distance au tracé : {Math.round(poi.distance_to_route_m)} m
              </Popup>
            </CircleMarker>
          ))}
        </MapContainer>
      </div>

      <div className="route-poi-columns">
        <div className="route-poi-section route-poi-section-selected">
          <h3>POI sur le tracé ({onRoutePois.length})</h3>
          <ul>
            {onRoutePois.map((poi) => (
              <li key={`on-${poi.id}`}>
                <strong>{poi.name}</strong> ({Math.round(poi.distance_to_route_m)} m)
              </li>
            ))}
          </ul>
        </div>
        <div className="route-poi-section route-poi-section-selected">
          <h3>POI à proximité ({nearbyPois.length})</h3>
          <ul>
            {nearbyPois.map((poi) => (
              <li key={`near-${poi.id}`}>
                <strong>{poi.name}</strong> ({Math.round(poi.distance_to_route_m)} m)
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="indicators-grid">
        <div className="indicator-card"><strong>Sentiers</strong><span>{toPercent(route.trail_ratio)}</span></div>
        <div className="indicator-card"><strong>Routes</strong><span>{toPercent(route.road_ratio)}</span></div>
        <div className="indicator-card"><strong>Nature</strong><span>{toPercent(route.nature_score)}</span></div>
        <div className="indicator-card"><strong>Calme</strong><span>{toPercent(route.quiet_score)}</span></div>
        <div className="indicator-card"><strong>Rando</strong><span>{toPercent(route.hiking_suitability_score)}</span></div>
      </div>
    </section>
  );
}
