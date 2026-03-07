import { useMemo, useState } from "react";
import MapView from "../../components/map/MapView";
import RouteList from "../../components/route/RouteList";
import SearchForm from "../../components/search/SearchForm";
import { generateRoutes } from "../../services/api/routeApi";
import { getCurrentPosition } from "../../services/geolocation/geolocation";
import type { HikeStyle, RouteCandidate, UserPosition } from "../../types/route";

function toPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export default function HomePage() {
  const [distanceKm, setDistanceKm] = useState<number>(5);
  const [routeCount, setRouteCount] = useState<number>(3);
  const [hikeStyle, setHikeStyle] = useState<HikeStyle>("equilibree");
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
        hike_style: hikeStyle
      });

      setRoutes(response.routes);
      setSelectedRouteId(response.routes.length > 0 ? response.routes[0].id : null);
      setMessage(`${response.routes.length} parcours générés (${hikeStyle}).`);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "Erreur lors de l'appel à l'API.";
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
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
          <h2>Parcours sélectionné</h2>
          <div className="route-meta">
            <span><strong>{selectedRoute.name}</strong></span>
            <span>Distance : {selectedRoute.distance_km} km</span>
            <span>Durée : {selectedRoute.estimated_duration_min} min</span>
            <span>Dénivelé : {selectedRoute.estimated_elevation_gain_m} m</span>
            <span>Score : {selectedRoute.score}</span>
            <span>Type : {selectedRoute.route_type}</span>
          </div>

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
        </section>
      )}

      <SearchForm
        distanceKm={distanceKm}
        routeCount={routeCount}
        hikeStyle={hikeStyle}
        loading={loading}
        hasPosition={position !== null}
        onDistanceChange={setDistanceKm}
        onRouteCountChange={setRouteCount}
        onHikeStyleChange={setHikeStyle}
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