import { useState } from "react";
import type { AmbianceFilter, DifficultyPref, EffortFilter, TerrainFilter } from "../../types/route";
import { AMBIANCE_HINTS, EFFORT_HINTS, TERRAIN_HINTS } from "../../utils/labels";

interface SearchFormProps {
  distanceKm: number;
  routeCount: number;
  ambiance: AmbianceFilter | null;
  terrain: TerrainFilter | null;
  effort: EffortFilter | null;
  difficultyPref: DifficultyPref | null;
  prioritizeNature: boolean;
  prioritizeViewpoints: boolean;
  prioritizeCalm: boolean;
  avoidUrban: boolean;
  avoidRoads: boolean;
  avoidSteep: boolean;
  avoidTouristic: boolean;
  adaptToWeather: boolean;
  loading: boolean;
  hasPosition: boolean;
  onDistanceChange: (value: number) => void;
  onRouteCountChange: (value: number) => void;
  onAmbianceChange: (value: AmbianceFilter | null) => void;
  onTerrainChange: (value: TerrainFilter | null) => void;
  onEffortChange: (value: EffortFilter | null) => void;
  onDifficultyPrefChange: (value: DifficultyPref | null) => void;
  onPrioritizeNatureChange: (value: boolean) => void;
  onPrioritizeViewpointsChange: (value: boolean) => void;
  onPrioritizeCalmChange: (value: boolean) => void;
  onAvoidUrbanChange: (value: boolean) => void;
  onAvoidRoadsChange: (value: boolean) => void;
  onAvoidSteepChange: (value: boolean) => void;
  onAvoidTouristicChange: (value: boolean) => void;
  onAdaptToWeatherChange: (value: boolean) => void;
  onLocate: () => Promise<void> | void;
  onGenerate: () => Promise<void> | void;
}

function activeHint(ambiance: AmbianceFilter | null, terrain: TerrainFilter | null, effort: EffortFilter | null): string | null {
  if (ambiance) return AMBIANCE_HINTS[ambiance];
  if (terrain) return TERRAIN_HINTS[terrain];
  if (effort) return EFFORT_HINTS[effort];
  return null;
}

export default function SearchForm(props: SearchFormProps) {
  const {
    distanceKm, routeCount, ambiance, terrain, effort, difficultyPref,
    prioritizeNature, prioritizeViewpoints, prioritizeCalm,
    avoidUrban, avoidRoads, avoidSteep, avoidTouristic, adaptToWeather,
    loading, hasPosition,
    onDistanceChange, onRouteCountChange, onAmbianceChange, onTerrainChange,
    onEffortChange, onDifficultyPrefChange,
    onPrioritizeNatureChange, onPrioritizeViewpointsChange, onPrioritizeCalmChange,
    onAvoidUrbanChange, onAvoidRoadsChange, onAvoidSteepChange, onAvoidTouristicChange,
    onAdaptToWeatherChange, onLocate, onGenerate,
  } = props;

  const [distanceInput, setDistanceInput] = useState<string>(String(distanceKm));
  const [routeCountInput, setRouteCountInput] = useState<string>(String(routeCount));
  const [advancedOpen, setAdvancedOpen] = useState<boolean>(false);

  const handleDistanceBlur = () => {
    const parsed = Number(distanceInput);
    if (!Number.isNaN(parsed) && parsed > 0 && parsed <= 100) {
      onDistanceChange(parsed);
      setDistanceInput(String(parsed));
    } else {
      setDistanceInput(String(distanceKm));
    }
  };

  const handleRouteCountBlur = () => {
    const parsed = Number(routeCountInput);
    if (!Number.isNaN(parsed) && parsed >= 1 && parsed <= 10) {
      onRouteCountChange(parsed);
      setRouteCountInput(String(parsed));
    } else {
      setRouteCountInput(String(routeCount));
    }
  };

  const advancedCount = [
    prioritizeNature, prioritizeViewpoints, prioritizeCalm,
    avoidUrban, avoidRoads, avoidSteep, avoidTouristic,
  ].filter(Boolean).length + (adaptToWeather ? 0 : 1);

  const hint = activeHint(ambiance, terrain, effort);

  const difficultyLabel: Record<DifficultyPref, string> = {
    facile: "Facile",
    moderee: "Modérée",
    difficile: "Difficile",
  };

  return (
    <section className="card search-card">
      <h2>Recherche</h2>

      {/* Distance + localiser */}
      <div className="sf-top-row">
        <button
          type="button"
          className={`sf-locate-btn ${hasPosition ? "sf-locate-btn-ok" : ""}`}
          onClick={onLocate}
          disabled={loading}
          title="Obtenir ma position GPS"
        >
          {hasPosition ? "📍 Localisé" : "📍 Me localiser"}
        </button>
        <div className="sf-distance-field">
          <label htmlFor="sf-distance">Distance</label>
          <div className="sf-distance-input-row">
            <input
              id="sf-distance"
              type="number"
              min="1"
              max="100"
              step="0.5"
              value={distanceInput}
              onChange={(e) => setDistanceInput(e.target.value)}
              onBlur={handleDistanceBlur}
            />
            <span className="sf-unit">km</span>
          </div>
        </div>
        <div className="sf-distance-field">
          <label htmlFor="sf-count">Parcours</label>
          <div className="sf-distance-input-row">
            <input
              id="sf-count"
              type="number"
              min="1"
              max="10"
              step="1"
              value={routeCountInput}
              onChange={(e) => setRouteCountInput(e.target.value)}
              onBlur={handleRouteCountBlur}
            />
          </div>
        </div>
      </div>

      {/* Main filters: selects */}
      <div className="sf-selects-grid">
        <div className="sf-select-field">
          <label htmlFor="sf-ambiance">Ambiance</label>
          <select
            id="sf-ambiance"
            className="sf-select"
            value={ambiance ?? ""}
            onChange={(e) => onAmbianceChange((e.target.value as AmbianceFilter) || null)}
          >
            <option value="">Toutes</option>
            <option value="equilibree">Équilibrée</option>
            <option value="sentiers">Sentiers</option>
            <option value="nature">Nature</option>
            <option value="calme">Calme</option>
          </select>
        </div>

        <div className="sf-select-field">
          <label htmlFor="sf-terrain">Terrain</label>
          <select
            id="sf-terrain"
            className="sf-select"
            value={terrain ?? ""}
            onChange={(e) => onTerrainChange((e.target.value as TerrainFilter) || null)}
          >
            <option value="">Tous</option>
            <option value="plat">Plat</option>
            <option value="vallonne">Vallonné</option>
          </select>
        </div>

        <div className="sf-select-field">
          <label htmlFor="sf-effort">Effort</label>
          <select
            id="sf-effort"
            className="sf-select"
            value={effort ?? ""}
            onChange={(e) => onEffortChange((e.target.value as EffortFilter) || null)}
          >
            <option value="">Tous</option>
            <option value="promenade">Promenade</option>
            <option value="sportif">Sportif</option>
          </select>
        </div>

        <div className="sf-select-field">
          <label htmlFor="sf-difficulty">Difficulté</label>
          <select
            id="sf-difficulty"
            className={`sf-select ${difficultyPref ? `sf-select-diff-${difficultyPref}` : ""}`}
            value={difficultyPref ?? ""}
            onChange={(e) => onDifficultyPrefChange((e.target.value as DifficultyPref) || null)}
          >
            <option value="">Toutes</option>
            <option value="facile">🟢 Facile</option>
            <option value="moderee">🟠 Modérée</option>
            <option value="difficile">🔴 Difficile</option>
          </select>
        </div>
      </div>

      {/* Hint line */}
      {(hint || difficultyPref) && (
        <p className="sf-hint-line">
          {hint && <span>{hint}</span>}
          {difficultyPref && <span>Difficulté sélectionnée : <strong>{difficultyLabel[difficultyPref]}</strong></span>}
        </p>
      )}

      {/* Advanced options toggle */}
      <button
        type="button"
        className="sf-advanced-toggle"
        onClick={() => setAdvancedOpen((v) => !v)}
        aria-expanded={advancedOpen}
      >
        <span className="sf-advanced-arrow">{advancedOpen ? "▾" : "▸"}</span>
        Options avancées
        {advancedCount > 0 && <span className="sf-advanced-badge">{advancedCount}</span>}
      </button>

      {advancedOpen && (
        <div className="sf-advanced-panel">
          <div className="sf-advanced-group">
            <span className="sf-advanced-label">Je veux</span>
            <div className="sf-toggle-row">
              {[
                { label: "🌿 Nature", value: prioritizeNature, onChange: onPrioritizeNatureChange },
                { label: "🏔 Points de vue", value: prioritizeViewpoints, onChange: onPrioritizeViewpointsChange },
                { label: "🤫 Calme", value: prioritizeCalm, onChange: onPrioritizeCalmChange },
                { label: "🌤 Adapter météo", value: adaptToWeather, onChange: onAdaptToWeatherChange },
              ].map(({ label, value, onChange }) => (
                <button
                  key={label}
                  type="button"
                  className={`sf-toggle ${value ? "sf-toggle-on" : ""}`}
                  onClick={() => onChange(!value)}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          <div className="sf-advanced-group">
            <span className="sf-advanced-label">J'évite</span>
            <div className="sf-toggle-row">
              {[
                { label: "🏙 Zones urbaines", value: avoidUrban, onChange: onAvoidUrbanChange },
                { label: "🛣 Routes", value: avoidRoads, onChange: onAvoidRoadsChange },
                { label: "⛰ Fort dénivelé", value: avoidSteep, onChange: onAvoidSteepChange },
                { label: "📸 Touristique", value: avoidTouristic, onChange: onAvoidTouristicChange },
              ].map(({ label, value, onChange }) => (
                <button
                  key={label}
                  type="button"
                  className={`sf-toggle ${value ? "sf-toggle-avoid" : ""}`}
                  onClick={() => onChange(!value)}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Generate button */}
      <button
        type="button"
        className="sf-generate-btn"
        onClick={onGenerate}
        disabled={loading || !hasPosition}
      >
        {loading
          ? <><span className="sf-spinner" /> Génération en cours…</>
          : !hasPosition
            ? "Localisez-vous d'abord"
            : "Générer des parcours"}
      </button>
    </section>
  );
}
