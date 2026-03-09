import { useMemo } from "react";
import type { RouteCandidate } from "../../types/route";
import { computeHighlights, difficultyClass, formatDuration, tagClass } from "../../utils/labels";

interface RouteListProps {
  routes: RouteCandidate[];
  selectedRouteId: string | null;
  hoveredRouteId: string | null;
  onSelectRoute: (routeId: string) => void;
  onHoverRoute: (routeId: string | null) => void;
  onViewDetails: (routeId: string) => void;
  favoriteRouteIds: string[];
  onToggleFavorite: (stableRouteId: string, isFavorite: boolean) => void;
}

export default function RouteList({
  routes,
  selectedRouteId,
  hoveredRouteId,
  onSelectRoute,
  onHoverRoute,
  onViewDetails,
  favoriteRouteIds,
  onToggleFavorite,
}: RouteListProps) {
  const highlights = useMemo(() => computeHighlights(routes), [routes]);

  if (routes.length === 0) {
    return (
      <section className="card results-card">
        <h2>Résultats</h2>
        <p className="empty-state">Aucun parcours pour l'instant. Lance une recherche pour comparer plusieurs options.</p>
      </section>
    );
  }

  return (
    <section className="card results-card">
      <h2>Résultats ({routes.length})</h2>

      <div className="route-list">
        {routes.map((route, index) => {
          const isSelected = selectedRouteId === route.id;
          const isHovered = hoveredRouteId === route.id;
          const highlight = highlights.get(route.id);
          const topPoiBadges = route.highlighted_poi_labels.slice(0, 2);
          const primaryTags = route.tags.slice(0, 3);
          const stableRouteId = (route.stable_route_id ?? "").trim();
          const canFavorite = stableRouteId.length > 0;
          const isFavorite = canFavorite && favoriteRouteIds.includes(stableRouteId);

          return (
            <article
              key={route.id}
              className={`route-item route-item-animated ${isSelected ? "route-item-selected" : ""} ${isHovered ? "route-item-hovered" : ""}`}
              style={{ animationDelay: `${Math.min(index, 6) * 90}ms` }}
              onMouseEnter={() => onHoverRoute(route.id)}
              onMouseLeave={() => onHoverRoute(null)}
            >
              {/* Header: name + star */}
              <div className="route-card-header">
                <div className="route-card-title-block">
                  <h3 className="route-card-name">{route.name}</h3>
                  {highlight && <span className="route-highlight">{highlight}</span>}
                </div>
                <button
                  type="button"
                  className={`route-star-btn ${isFavorite ? "route-star-btn-active" : ""}`}
                  disabled={!canFavorite}
                  title={isFavorite ? "Retirer des favoris" : "Ajouter aux favoris"}
                  onClick={() => { if (canFavorite) onToggleFavorite(stableRouteId, isFavorite); }}
                >
                  {isFavorite ? "★" : "☆"}
                </button>
              </div>

              {/* Stats row */}
              <div className="route-stats-row">
                <span className="route-stat">↔ {route.distance_km} km</span>
                <span className="route-stat">⏱ {formatDuration(route.estimated_duration_min)}</span>
                <span className="route-stat">↑ {route.estimated_elevation_gain_m} m</span>
                <span className={difficultyClass(route.difficulty)}>{route.difficulty}</span>
                {route.seen_before && <span className="route-seen-pill">Déjà vu</span>}
              </div>

              {/* Tags */}
              {primaryTags.length > 0 && (
                <div className="route-tags">
                  {primaryTags.map((tag) => (
                    <span key={tag} className={tagClass(tag)}>{tag}</span>
                  ))}
                </div>
              )}

              {/* POI badges */}
              {topPoiBadges.length > 0 && (
                <div className="route-poi-badges">
                  {topPoiBadges.map((label) => (
                    <span key={`${route.id}-${label}`} className="route-poi-badge">{label}</span>
                  ))}
                </div>
              )}

              {/* Explanation */}
              {route.explanation && <p className="route-why-inline">{route.explanation}</p>}

              {/* Context warnings */}
              {route.context_warnings && route.context_warnings.length > 0 && (
                <div className="route-context-warnings">
                  {route.context_warnings.map((warning) => (
                    <p key={`${route.id}-${warning}`}>{warning}</p>
                  ))}
                </div>
              )}

              {/* Footer: detail + select */}
              <div className="route-card-footer">
                <button
                  type="button"
                  className="route-detail-link"
                  onClick={() => onViewDetails(route.id)}
                >
                  Voir détails →
                </button>
                <button
                  type="button"
                  className="route-primary-btn"
                  onClick={() => onSelectRoute(route.id)}
                >
                  {isSelected ? "✓ Sélectionné" : "Sélectionner"}
                </button>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
