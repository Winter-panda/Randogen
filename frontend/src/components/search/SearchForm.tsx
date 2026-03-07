import { useState } from "react";
import type { HikeStyle } from "../../types/route";

interface SearchFormProps {
  distanceKm: number;
  routeCount: number;
  hikeStyle: HikeStyle;
  loading: boolean;
  hasPosition: boolean;
  onDistanceChange: (value: number) => void;
  onRouteCountChange: (value: number) => void;
  onHikeStyleChange: (value: HikeStyle) => void;
  onLocate: () => Promise<void> | void;
  onGenerate: () => Promise<void> | void;
}

export default function SearchForm(props: SearchFormProps) {
  const {
    distanceKm,
    routeCount,
    hikeStyle,
    loading,
    hasPosition,
    onDistanceChange,
    onRouteCountChange,
    onHikeStyleChange,
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

        <div className="field">
          <label htmlFor="hikeStyle">Type de randonnée</label>
          <select
            id="hikeStyle"
            value={hikeStyle}
            onChange={(event) => onHikeStyleChange(event.target.value as HikeStyle)}
          >
            <option value="equilibree">Équilibrée</option>
            <option value="sentiers">Sentiers</option>
            <option value="nature">Nature</option>
            <option value="calme">Calme</option>
          </select>
        </div>
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
