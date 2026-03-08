import { useMemo } from "react";
import type { RouteCandidate } from "../../types/route";
import { computeHighlights, difficultyClass, formatDuration, formatScore, tagClass } from "../../utils/labels";

interface RouteListProps {
  routes: RouteCandidate[];
  selectedRouteId: string | null;
  onSelectRoute: (routeId: string) => void;
}


function toPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export default function RouteList({
  routes,
  selectedRouteId,
  onSelectRoute
}: RouteListProps) {
  const highlights = useMemo(() => computeHighlights(routes), [routes]);

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
          const highlight = highlights.get(route.id);

          return (
            <article
              key={route.id}
              className={`route-item ${isSelected ? "route-item-selected" : ""}`}
            >
              <div className="route-item-header">
                <div className="route-item-title">
                  <h3>{route.name}</h3>
                  {highlight && (
                    <span className="route-highlight">{highlight}</span>
                  )}
                </div>
                <button type="button" onClick={() => onSelectRoute(route.id)}>
                  {isSelected ? "Sélectionné" : "Sélectionner"}
                </button>
              </div>

              <div className="route-meta">
                <span>Distance : {route.distance_km} km</span>
                <span>Durée : {formatDuration(route.estimated_duration_min)}</span>
                <span>Dénivelé : {route.estimated_elevation_gain_m} m</span>
                <span>Score : {formatScore(route.score)}</span>
                <span className={difficultyClass(route.difficulty)}>{route.difficulty}</span>
              </div>

              {route.tags.length > 0 && (
                <div className="route-tags">
                  {route.tags.map((tag) => (
                    <span key={tag} className={tagClass(tag)}>{tag}</span>
                  ))}
                </div>
              )}

              <div className="indicators-grid">
                <div className="indicator-card">
                  <strong>Sentiers</strong>
                  <span>{toPercent(route.trail_ratio)}</span>
                </div>
                <div className="indicator-card">
                  <strong>Routes</strong>
                  <span>{toPercent(route.road_ratio)}</span>
                </div>
                <div className="indicator-card">
                  <strong>Nature</strong>
                  <span>{toPercent(route.nature_score)}</span>
                </div>
                <div className="indicator-card">
                  <strong>Calme</strong>
                  <span>{toPercent(route.quiet_score)}</span>
                </div>
                <div className="indicator-card">
                  <strong>Rando</strong>
                  <span>{toPercent(route.hiking_suitability_score)}</span>
                </div>
              </div>

            </article>
          );
        })}
      </div>
    </section>
  );
}