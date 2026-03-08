import { useMemo, useState } from "react";
import MapView from "../../components/map/MapView";
import RouteList from "../../components/route/RouteList";
import SearchForm from "../../components/search/SearchForm";
import AltitudeProfile from "../../components/route/AltitudeProfile";
import { generateRoutes } from "../../services/api/routeApi";
import { getCurrentPosition } from "../../services/geolocation/geolocation";
import type { AmbianceFilter, EffortFilter, RouteCandidate, TerrainFilter, UserPosition } from "../../types/route";
import { difficultyClass, formatDuration, formatFiltersLabel, formatRouteType, formatScore, tagClass } from "../../utils/labels";

function toPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}


function escapeXml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}

function buildGpx(route: RouteCandidate): string {
  const trackPoints = route.points
    .map(
      (point) =>
        `    <trkpt lat="${point.latitude}" lon="${point.longitude}">${(point.elevation_m ?? 0) !== 0 ? `
      <ele>${(point.elevation_m ?? 0).toFixed(1)}</ele>
    ` : ""}</trkpt>`
    )
    .join("\n");

  return `<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="Randogen" xmlns="http://www.topografix.com/GPX/1/1">
  <metadata>
    <name>${escapeXml(route.name)}</name>
    <desc>${escapeXml(`Parcours ${route.route_type} - ${route.distance_km} km`)}</desc>
  </metadata>
  <trk>
    <name>${escapeXml(route.name)}</name>
    <trkseg>
${trackPoints}
    </trkseg>
  </trk>
</gpx>
`;
}

function downloadRouteAsGpx(route: RouteCandidate): void {
  const gpxContent = buildGpx(route);
  const blob = new Blob([gpxContent], { type: "application/gpx+xml;charset=utf-8" });
  const url = URL.createObjectURL(blob);

  const safeName = route.name
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-zA-Z0-9-_]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
    .toLowerCase();

  const link = document.createElement("a");
  link.href = url;
  link.download = `${safeName || "parcours"}.gpx`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

export default function HomePage() {
  const [distanceKm, setDistanceKm] = useState<number>(5);
  const [routeCount, setRouteCount] = useState<number>(3);
  const [ambiance, setAmbiance] = useState<AmbianceFilter | null>(null);
  const [terrain, setTerrain] = useState<TerrainFilter | null>(null);
  const [effort, setEffort] = useState<EffortFilter | null>(null);
  const [position, setPosition] = useState<UserPosition | null>(null);
  const [routes, setRoutes] = useState<RouteCandidate[]>([]);
  const [selectedRouteId, setSelectedRouteId] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [message, setMessage] = useState<string>("Bienvenue dans Randogen.");
  const [error, setError] = useState<string>("");

  const selectedRoute = useMemo(
    () => routes.find((route) => route.id === selectedRouteId) ?? null,
    [routes, selectedRouteId]
  );

  const handleLocate = async () => {
    setLoading(true);
    setError("");

    try {
      const currentPosition = await getCurrentPosition();
      setPosition(currentPosition);
      setMessage(
        `Position récupérée : ${currentPosition.latitude.toFixed(6)}, ${currentPosition.longitude.toFixed(6)}`
      );
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "Erreur de géolocalisation.";
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerate = async () => {
    if (!position) {
      setError("Aucune position disponible. Clique d'abord sur Me localiser.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const response = await generateRoutes({
        latitude: position.latitude,
        longitude: position.longitude,
        target_distance_km: distanceKm,
        route_count: routeCount,
        ambiance,
        terrain,
        effort,
      });

      setRoutes(response.routes);
      setSelectedRouteId(response.routes.length > 0 ? response.routes[0].id : null);
      setMessage(`${response.routes.length} parcours générés (${formatFiltersLabel(ambiance, terrain, effort)}).`);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "Erreur lors de l'appel à l'API.";
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadGpx = () => {
    if (selectedRoute) downloadRouteAsGpx(selectedRoute);
  };

  return (
    <main className="page">
      <header className="hero">
        <h1>Randogen</h1>
        <p>Générateur intelligent de randonnées autour de l'utilisateur.</p>
      </header>

      <section className="card">
        <h2>État</h2>
        <p>{message}</p>
        {position && (
          <p>
            Latitude : <strong>{position.latitude.toFixed(6)}</strong> | Longitude :{" "}
            <strong>{position.longitude.toFixed(6)}</strong>
          </p>
        )}
        {error && <p className="error">{error}</p>}
      </section>

      {selectedRoute && (
        <section className="card">
          <div className="selected-route-header">
            <div>
              <h2>Parcours sélectionné</h2>
              <div className="route-meta">
                <span><strong>{selectedRoute.name}</strong></span>
                <span>Distance : {selectedRoute.distance_km} km</span>
                <span>Durée : {formatDuration(selectedRoute.estimated_duration_min)}</span>
                <span>Dénivelé : {selectedRoute.estimated_elevation_gain_m} m</span>
                <span>Score : {formatScore(selectedRoute.score)}</span>
                <span>Type : {formatRouteType(selectedRoute.route_type)}</span>
                <span className={difficultyClass(selectedRoute.difficulty)}>{selectedRoute.difficulty}</span>
              </div>
            </div>

            <button
              type="button"
              className="download-button"
              onClick={handleDownloadGpx}
            >
              Télécharger GPX
            </button>
          </div>

          {selectedRoute.tags.length > 0 && (
            <div className="route-tags">
              {selectedRoute.tags.map((tag) => (
                <span key={tag} className={tagClass(tag)}>{tag}</span>
              ))}
            </div>
          )}

          <div className="indicators-grid">
            <div className="indicator-card">
              <strong>Sentiers</strong>
              <span>{toPercent(selectedRoute.trail_ratio)}</span>
            </div>
            <div className="indicator-card">
              <strong>Routes</strong>
              <span>{toPercent(selectedRoute.road_ratio)}</span>
            </div>
            <div className="indicator-card">
              <strong>Nature</strong>
              <span>{toPercent(selectedRoute.nature_score)}</span>
            </div>
            <div className="indicator-card">
              <strong>Calme</strong>
              <span>{toPercent(selectedRoute.quiet_score)}</span>
            </div>
            <div className="indicator-card">
              <strong>Rando</strong>
              <span>{toPercent(selectedRoute.hiking_suitability_score)}</span>
            </div>
          </div>

          <AltitudeProfile points={selectedRoute.points} />
        </section>
      )}

      <SearchForm
        distanceKm={distanceKm}
        routeCount={routeCount}
        ambiance={ambiance}
        terrain={terrain}
        effort={effort}
        loading={loading}
        hasPosition={position !== null}
        onDistanceChange={setDistanceKm}
        onRouteCountChange={setRouteCount}
        onAmbianceChange={setAmbiance}
        onTerrainChange={setTerrain}
        onEffortChange={setEffort}
        onLocate={handleLocate}
        onGenerate={handleGenerate}
      />

      <MapView
        position={position}
        routes={routes}
        selectedRouteId={selectedRouteId}
        onSelectRoute={setSelectedRouteId}
      />

      <RouteList
        routes={routes}
        selectedRouteId={selectedRouteId}
        onSelectRoute={setSelectedRouteId}
      />
    </main>
  );
}