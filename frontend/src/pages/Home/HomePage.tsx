import { useState } from "react";
import RouteList from "../../components/route/RouteList";
import SearchForm from "../../components/search/SearchForm";
import { generateRoutes } from "../../services/api/routeApi";
import { getCurrentPosition } from "../../services/geolocation/geolocation";
import type { RouteCandidate, UserPosition } from "../../types/route";

export default function HomePage() {
  const [distanceKm, setDistanceKm] = useState<number>(5);
  const [routeCount, setRouteCount] = useState<number>(3);
  const [position, setPosition] = useState<UserPosition | null>(null);
  const [routes, setRoutes] = useState<RouteCandidate[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [message, setMessage] = useState<string>("Bienvenue dans Randogen.");
  const [error, setError] = useState<string>("");

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
        route_count: routeCount
      });

      setRoutes(response.routes);
      setMessage(`${response.routes.length} parcours générés.`);
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

      <SearchForm
        distanceKm={distanceKm}
        routeCount={routeCount}
        loading={loading}
        hasPosition={position !== null}
        onDistanceChange={setDistanceKm}
        onRouteCountChange={setRouteCount}
        onLocate={handleLocate}
        onGenerate={handleGenerate}
      />

      <RouteList routes={routes} />
    </main>
  );
}
