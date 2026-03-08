import { useState } from "react";
import type { AmbianceFilter, EffortFilter, TerrainFilter } from "../../types/route";
import { AMBIANCE_HINTS, EFFORT_HINTS, TERRAIN_HINTS } from "../../utils/labels";

interface SearchFormProps {
  distanceKm: number;
  routeCount: number;
  ambiance: AmbianceFilter | null;
  terrain: TerrainFilter | null;
  effort: EffortFilter | null;
  loading: boolean;
  hasPosition: boolean;
  onDistanceChange: (value: number) => void;
  onRouteCountChange: (value: number) => void;
  onAmbianceChange: (value: AmbianceFilter | null) => void;
  onTerrainChange: (value: TerrainFilter | null) => void;
  onEffortChange: (value: EffortFilter | null) => void;
  onLocate: () => Promise<void> | void;
  onGenerate: () => Promise<void> | void;
}

const AMBIANCE_OPTIONS: { value: AmbianceFilter; label: string }[] = [
  { value: "equilibree", label: "Équilibrée" },
  { value: "sentiers", label: "Sentiers" },
  { value: "nature", label: "Nature" },
  { value: "calme", label: "Calme" },
];

const TERRAIN_OPTIONS: { value: TerrainFilter; label: string }[] = [
  { value: "plat", label: "Plat" },
  { value: "vallonne", label: "Vallonné" },
];

const EFFORT_OPTIONS: { value: EffortFilter; label: string }[] = [
  { value: "promenade", label: "Promenade" },
  { value: "sportif", label: "Sportif" },
];

function activeHint(
  ambiance: AmbianceFilter | null,
  terrain: TerrainFilter | null,
  effort: EffortFilter | null
): string | null {
  if (ambiance) return AMBIANCE_HINTS[ambiance];
  if (terrain) return TERRAIN_HINTS[terrain];
  if (effort) return EFFORT_HINTS[effort];
  return null;
}

export default function SearchForm(props: SearchFormProps) {
  const {
    distanceKm,
    routeCount,
    ambiance,
    terrain,
    effort,
    loading,
    hasPosition,
    onDistanceChange,
    onRouteCountChange,
    onAmbianceChange,
    onTerrainChange,
    onEffortChange,
    onLocate,
    onGenerate
  } = props;

  const [distanceInput, setDistanceInput] = useState<string>(String(distanceKm));
  const [routeCountInput, setRouteCountInput] = useState<string>(String(routeCount));

  const handleDistanceBlur = () => {
    const parsed = Number(distanceInput);
    if (!Number.isNaN(parsed) && parsed > 0 && parsed <= 100) {
      onDistanceChange(parsed);
      setDistanceInput(String(parsed));
      return;
    }
    setDistanceInput(String(distanceKm));
  };

  const handleRouteCountBlur = () => {
    const parsed = Number(routeCountInput);
    if (!Number.isNaN(parsed) && parsed >= 1 && parsed <= 10) {
      onRouteCountChange(parsed);
      setRouteCountInput(String(parsed));
      return;
    }
    setRouteCountInput(String(routeCount));
  };

  const hint = activeHint(ambiance, terrain, effort);

  return (
    <section className="card">
      <h2>Recherche</h2>

      <div className="form-grid">
        <div className="field">
          <label htmlFor="distanceKm">Distance cible (km)</label>
          <input
            id="distanceKm"
            type="number"
            min="1"
            max="100"
            step="0.5"
            value={distanceInput}
            onChange={(event) => setDistanceInput(event.target.value)}
            onBlur={handleDistanceBlur}
          />
        </div>

        <div className="field">
          <label htmlFor="routeCount">Nombre de parcours</label>
          <input
            id="routeCount"
            type="number"
            min="1"
            max="10"
            step="1"
            value={routeCountInput}
            onChange={(event) => setRouteCountInput(event.target.value)}
            onBlur={handleRouteCountBlur}
          />
        </div>
      </div>

      <div className="filter-group">
        <div className="filter-row">
          <span className="filter-label">Ambiance</span>
          <div className="pill-group">
            <button
              type="button"
              className={`pill ${ambiance === null ? "pill-active" : ""}`}
              onClick={() => onAmbianceChange(null)}
            >
              Toutes
            </button>
            {AMBIANCE_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                className={`pill ${ambiance === opt.value ? "pill-active" : ""}`}
                onClick={() => onAmbianceChange(ambiance === opt.value ? null : opt.value)}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        <div className="filter-row">
          <span className="filter-label">Terrain</span>
          <div className="pill-group">
            <button
              type="button"
              className={`pill ${terrain === null ? "pill-active" : ""}`}
              onClick={() => onTerrainChange(null)}
            >
              Tous
            </button>
            {TERRAIN_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                className={`pill ${terrain === opt.value ? "pill-active" : ""}`}
                onClick={() => onTerrainChange(terrain === opt.value ? null : opt.value)}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        <div className="filter-row">
          <span className="filter-label">Effort</span>
          <div className="pill-group">
            <button
              type="button"
              className={`pill ${effort === null ? "pill-active" : ""}`}
              onClick={() => onEffortChange(null)}
            >
              Tous
            </button>
            {EFFORT_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                className={`pill ${effort === opt.value ? "pill-active" : ""}`}
                onClick={() => onEffortChange(effort === opt.value ? null : opt.value)}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {hint && (
          <p className="filter-hint-bar">{hint}</p>
        )}
      </div>

      <div className="actions">
        <button type="button" onClick={onLocate} disabled={loading}>
          Me localiser
        </button>

        <button
          type="button"
          onClick={onGenerate}
          disabled={loading || !hasPosition}
        >
          Générer des parcours
        </button>
      </div>

      {!hasPosition && (
        <p className="hint">
          Commence par cliquer sur <strong>Me localiser</strong>.
        </p>
      )}
    </section>
  );
}
