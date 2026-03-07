import type { RouteCandidate } from "../../types/route";

interface RouteListProps {
  routes: RouteCandidate[];
  selectedRouteId: string | null;
  onSelectRoute: (routeId: string) => void;
}

function roundCoordinate(value: number): number {
  return Math.round(value * 1000000) / 1000000;
}

export default function RouteList({
  routes,
  selectedRouteId,
  onSelectRoute
}: RouteListProps) {
  if (routes.length === 0) {
    return (
      <section className="card">
        <h2>Résultats</h2>
        <p>Aucun parcours généré pour le moment.</p>
      </section>
    );
  }

  return (
    <section className="card">
      <h2>Résultats</h2>

      <div className="route-list">
        {routes.map((route) => {
          const isSelected = selectedRouteId === route.id;

          return (
            <article
              key={route.id}
              className={`route-item ${isSelected ? "route-item-selected" : ""}`}
            >
              <div className="route-item-header">
                <h3>{route.name}</h3>
                <button type="button" onClick={() => onSelectRoute(route.id)}>
                  {isSelected ? "Sélectionné" : "Sélectionner"}
                </button>
              </div>

              <div className="route-meta">
                <span>Distance : {route.distance_km} km</span>
                <span>Durée : {route.estimated_duration_min} min</span>
                <span>Dénivelé : {route.estimated_elevation_gain_m} m</span>
                <span>Score : {route.score}</span>
                <span>Type : {route.route_type}</span>
                <span>Source : {route.source}</span>
              </div>

              <details open={isSelected}>
                <summary>Voir les points du parcours</summary>
                <pre className="points-block">
{JSON.stringify(
  route.points.map((point) => ({
    latitude: roundCoordinate(point.latitude),
    longitude: roundCoordinate(point.longitude)
  })),
  null,
  2
)}
                </pre>
              </details>
            </article>
          );
        })}
      </div>
    </section>
  );
}