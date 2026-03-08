import { useEffect, useMemo, useState } from "react";
import MapView from "../../components/map/MapView";
import RouteList from "../../components/route/RouteList";
import SearchForm from "../../components/search/SearchForm";
import AltitudeProfile from "../../components/route/AltitudeProfile";
import RouteDetailPanel from "../../components/route/RouteDetailPanel";
import {
  addFavorite,
  buildShareUrl,
  downloadRouteGeoJson,
  downloadRouteGpx,
  fetchWeather,
  generateRoutes,
  getOrCreateUserId,
  getSharedRoute,
  getUserPreferenceProfile,
  listFavorites,
  listHistory,
  markRouteViewed,
  removeFavorite,
} from "../../services/api/routeApi";
import {
  getCurrentPosition,
  startPositionWatch
} from "../../services/geolocation/geolocation";
import type {
  AmbianceFilter,
  BiomePreference,
  DifficultyPref,
  EffortFilter,
  FavoriteItem,
  HistoryItem,
  PreferenceProfile,
  RouteCandidate,
  TerrainFilter,
  UserPosition,
  WeatherData,
} from "../../types/route";
import { formatDuration, formatFiltersLabel } from "../../utils/labels";


function escapeXml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
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

function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

function safeFilename(route: RouteCandidate, ext: string): string {
  const safeName = route.name
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-zA-Z0-9-_]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
    .toLowerCase();
  return `${safeName || "parcours"}.${ext}`;
}

function buildExactRouteGeoJsonUrl(route: RouteCandidate): string {
  const features: Array<Record<string, unknown>> = [
    {
      type: "Feature",
      geometry: {
        type: "LineString",
        coordinates: route.points.map((point) => [point.longitude, point.latitude]),
      },
      properties: {
        name: route.name,
        distance_km: route.distance_km,
      },
    },
  ];

  for (const poi of route.pois ?? []) {
    features.push({
      type: "Feature",
      geometry: {
        type: "Point",
        coordinates: [poi.longitude, poi.latitude],
      },
      properties: {
        name: poi.name,
        category: poi.category,
      },
    });
  }

  const geoJson = {
    type: "FeatureCollection",
    features,
  };
  return `https://geojson.io/#data=data:application/json,${encodeURIComponent(JSON.stringify(geoJson))}`;
}

export default function HomePage() {
  const [distanceKm, setDistanceKm] = useState<number>(5);
  const [routeCount, setRouteCount] = useState<number>(3);
  const [ambiance, setAmbiance] = useState<AmbianceFilter | null>(null);
  const [terrain, setTerrain] = useState<TerrainFilter | null>(null);
  const [effort, setEffort] = useState<EffortFilter | null>(null);
  const [biomePreference, setBiomePreference] = useState<BiomePreference | null>(null);
  const [prioritizeNature, setPrioritizeNature] = useState<boolean>(false);
  const [prioritizeViewpoints, setPrioritizeViewpoints] = useState<boolean>(false);
  const [prioritizeCalm, setPrioritizeCalm] = useState<boolean>(false);
  const [avoidUrban, setAvoidUrban] = useState<boolean>(false);
  const [avoidRoads, setAvoidRoads] = useState<boolean>(false);
  const [avoidSteep, setAvoidSteep] = useState<boolean>(false);
  const [avoidTouristic, setAvoidTouristic] = useState<boolean>(false);
  const [adaptToWeather, setAdaptToWeather] = useState<boolean>(true);
  const [difficultyPref, setDifficultyPref] = useState<DifficultyPref | null>(null);
  const [position, setPosition] = useState<UserPosition | null>(null);
  const [routes, setRoutes] = useState<RouteCandidate[]>([]);
  const [selectedRouteId, setSelectedRouteId] = useState<string | null>(null);
  const [hoveredRouteId, setHoveredRouteId] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [message, setMessage] = useState<string>("Bienvenue dans Randogen.");
  const [error, setError] = useState<string>("");
  const [warnings, setWarnings] = useState<string[]>([]);
  const [exportMessage, setExportMessage] = useState<string>("");
  const [liveTracking, setLiveTracking] = useState<boolean>(false);
  const [trackingEnabled, setTrackingEnabled] = useState<boolean>(true);
  const [userId, setUserId] = useState<string>("");
  const [historyItems, setHistoryItems] = useState<HistoryItem[]>([]);
  const [favoriteItems, setFavoriteItems] = useState<FavoriteItem[]>([]);
  const [showDetailPanel, setShowDetailPanel] = useState<boolean>(false);
  const [secondaryTab, setSecondaryTab] = useState<"history" | "favorites">("history");
  const [preferenceProfile, setPreferenceProfile] = useState<PreferenceProfile | null>(null);
  const [weather, setWeather] = useState<WeatherData | null>(null);

  const resolveUserId = (): string => {
    const resolved = (userId || getOrCreateUserId()).trim();
    if (!userId && resolved) {
      setUserId(resolved);
    }
    return resolved;
  };

  const selectedRoute = useMemo(
    () => routes.find((route) => route.id === selectedRouteId) ?? null,
    [routes, selectedRouteId]
  );

  useEffect(() => {
    const id = getOrCreateUserId();
    setUserId(id);
    void listHistory(id).then(setHistoryItems).catch(() => undefined);
    void listFavorites(id).then(setFavoriteItems).catch(() => undefined);
    void getUserPreferenceProfile(id).then((profile) => {
      if (profile.has_data) setPreferenceProfile(profile);
    }).catch(() => undefined);
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const sharedRouteId = params.get("route");
    if (!sharedRouteId || !userId) return;

    setLoading(true);
    setError("");
    setWarnings([]);
    setMessage("Chargement du parcours partage...");
    getSharedRoute(sharedRouteId)
      .then((route) => {
      setRoutes([route]);
      setSelectedRouteId(route.id);
      setHoveredRouteId(null);
      setMessage(`Parcours partagé chargé (${route.name}).`);
        return markRouteViewed(userId, route.stable_route_id ?? route.id);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Impossible de charger le parcours partagé.");
      })
      .finally(() => setLoading(false));
  }, [userId]);

  useEffect(() => {
    if (!userId || !selectedRoute) return;
    const stableRouteId = selectedRoute.stable_route_id ?? selectedRoute.id;
    void markRouteViewed(userId, stableRouteId).catch(() => undefined);
  }, [selectedRouteId, selectedRoute, userId]);

  useEffect(() => {
    if (!selectedRouteId || !trackingEnabled) {
      setLiveTracking(false);
      return;
    }

    const onPosition = (nextPosition: UserPosition) => {
      setPosition(nextPosition);
      setLiveTracking(true);
    };

    const onError = (message: string) => {
      setLiveTracking(false);
      setWarnings((current) => (current.includes(message) ? current : [...current, message]));
    };

    const stopWatch = startPositionWatch(onPosition, onError);

    return () => {
      stopWatch();
      setLiveTracking(false);
    };
  }, [selectedRouteId, trackingEnabled]);

  useEffect(() => {
    if (!position) return;
    fetchWeather(position.latitude, position.longitude)
      .then(setWeather)
      .catch(() => undefined);
  }, [position]);

  const handleLocate = async () => {
    setLoading(true);
    setError("");
    setWarnings([]);
    setMessage("Geolocalisation en cours...");

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

  const handleApplyProfile = () => {
    if (!preferenceProfile?.has_data) return;
    if (preferenceProfile.suggested_ambiance) setAmbiance(preferenceProfile.suggested_ambiance);
    if (preferenceProfile.suggested_terrain) setTerrain(preferenceProfile.suggested_terrain);
    if (preferenceProfile.suggested_effort) setEffort(preferenceProfile.suggested_effort);
    if (preferenceProfile.suggested_biome) setBiomePreference(preferenceProfile.suggested_biome);
    if (preferenceProfile.average_distance_km) setDistanceKm(preferenceProfile.average_distance_km);
  };

  const handleGenerate = async () => {
    if (!position) {
      setError("Aucune position disponible. Clique d'abord sur Me localiser.");
      return;
    }

    setLoading(true);
    setError("");
    setWarnings([]);
    setMessage("Generation des parcours en cours...");

    try {
      const resolvedUserId = resolveUserId();
      const response = await generateRoutes({
        user_id: resolvedUserId,
        latitude: position.latitude,
        longitude: position.longitude,
        target_distance_km: distanceKm,
        route_count: routeCount,
        ambiance,
        terrain,
        effort,
        biome_preference: biomePreference,
        prioritize_nature: prioritizeNature,
        prioritize_viewpoints: prioritizeViewpoints,
        prioritize_calm: prioritizeCalm,
        avoid_urban: avoidUrban,
        avoid_roads: avoidRoads,
        avoid_steep: avoidSteep,
        avoid_touristic: avoidTouristic,
        adapt_to_weather: adaptToWeather,
        difficulty_pref: difficultyPref,
      });

      setRoutes(response.routes);
      setSelectedRouteId(response.routes.length > 0 ? response.routes[0].id : null);
      setHoveredRouteId(null);
      setShowDetailPanel(false);
      setWarnings(response.warnings ?? []);
      void listHistory(resolvedUserId).then(setHistoryItems).catch(() => undefined);
      void listFavorites(resolvedUserId).then(setFavoriteItems).catch(() => undefined);
      const baseMessage = `${response.routes.length} parcours generes (${formatFiltersLabel(ambiance, terrain, effort, biomePreference)}).`;
      if (response.status === "fallback") {
        setMessage(`${baseMessage} Generation de secours activee.`);
      } else if (response.status === "partial") {
        setMessage(`${baseMessage} Resultat partiel.`);
      } else if (response.status === "low_data") {
        setMessage(`${baseMessage} Zone avec peu de donnees.`);
      } else {
        setMessage(baseMessage);
      }
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "Erreur lors de l'appel à l'API.";
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadGpx = async () => {
    if (!selectedRoute) return;
    setExportMessage("");
    try {
      const stableId = selectedRoute.stable_route_id ?? selectedRoute.id;
      const blob = await downloadRouteGpx(stableId);
      downloadBlob(blob, safeFilename(selectedRoute, "gpx"));
      setExportMessage("Export GPX téléchargé.");
    } catch {
      const localBlob = new Blob([buildGpx(selectedRoute)], { type: "application/gpx+xml;charset=utf-8" });
      downloadBlob(localBlob, safeFilename(selectedRoute, "gpx"));
      setExportMessage("Export backend indisponible, GPX local téléchargé.");
    }
  };

  const handleToggleFavorite = async (stableRouteId: string, isFavorite: boolean) => {
    const resolvedUserId = resolveUserId();
    try {
      if (isFavorite) {
        await removeFavorite(resolvedUserId, stableRouteId);
      } else {
        const route = routes.find((r) => (r.stable_route_id ?? "") === stableRouteId);
        await addFavorite(resolvedUserId, stableRouteId, route);
      }
      const favorites = await listFavorites(resolvedUserId);
      setFavoriteItems(favorites);
      const history = await listHistory(resolvedUserId);
      setHistoryItems(history);
      setExportMessage(isFavorite ? "Favori retire." : "Parcours ajoute aux favoris.");
    } catch (err) {
      setExportMessage(err instanceof Error ? err.message : "Erreur favoris.");
    }
  };

  const handleDownloadGeoJson = async () => {
    if (!selectedRoute) return;
    setExportMessage("");
    try {
      const stableId = selectedRoute.stable_route_id ?? selectedRoute.id;
      const blob = await downloadRouteGeoJson(stableId);
      downloadBlob(blob, safeFilename(selectedRoute, "geojson"));
      setExportMessage("Export GeoJSON téléchargé.");
    } catch {
      setExportMessage("Export GeoJSON impossible pour ce parcours.");
    }
  };

  const handleShare = async () => {
    if (!selectedRoute) return;
    const stableId = (selectedRoute.stable_route_id ?? "").trim();
    if (!stableId) {
      setExportMessage("Partage indisponible pour ce parcours (identifiant manquant).");
      return;
    }
    const url = buildShareUrl(stableId);
    try {
      if (navigator.share) {
        await navigator.share({
          title: selectedRoute.name,
          text: "Parcours Randogen",
          url,
        });
        setExportMessage("Lien de partage envoye.");
        return;
      }
      await navigator.clipboard.writeText(url);
      setExportMessage("Lien de partage copie.");
    } catch {
      setExportMessage(`Lien de partage: ${url}`);
    }
  };

  const handleOpenExternal = () => {
    if (!selectedRoute || selectedRoute.points.length === 0) return;
    const start = selectedRoute.points[0];
    const geoUrl = `geo:${start.latitude},${start.longitude}?q=${start.latitude},${start.longitude}`;
    const webUrl = buildExactRouteGeoJsonUrl(selectedRoute);
    const isMobile = /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent);
    if (isMobile) {
      window.location.assign(geoUrl);
      window.setTimeout(() => {
        window.open(webUrl, "_blank", "noopener,noreferrer");
      }, 1200);
      setExportMessage("Tentative d'ouverture dans l'application de navigation...");
      return;
    }
    window.open(webUrl, "_blank", "noopener,noreferrer");
    setExportMessage("Ouverture externe avec le trace exact du parcours.");
  };

  function weatherIcon(code: number): string {
    if (code === 0) return "☀️";
    if (code <= 2) return "🌤";
    if (code === 3) return "☁️";
    if (code <= 48) return "🌫";
    if (code <= 55) return "🌦";
    if (code <= 65) return "🌧";
    if (code <= 75) return "❄️";
    if (code <= 82) return "🌧";
    return "⛈";
  }

  function weatherLabel(w: WeatherData): string {
    const parts: string[] = [`${w.temperature_c.toFixed(1)}°C`];
    if (w.precipitation_mm >= 0.2) parts.push(`${w.precipitation_mm.toFixed(1)} mm`);
    if (w.wind_kmh >= 20) parts.push(`${Math.round(w.wind_kmh)} km/h`);
    return parts.join(" · ");
  }

  function getTimeContext(): { icon: string; label: string; cls: string } {
    const h = new Date().getHours();
    const m = new Date().getMonth() + 1;
    const sunset = m >= 6 && m <= 7 ? 21 : m === 5 || m === 8 ? 20 : m === 4 || m === 9 ? 19 : m === 3 || m === 10 ? 18 : 17;
    const sunrise = m >= 6 && m <= 7 ? 5 : m === 5 || m === 8 ? 6 : m >= 3 && m <= 10 ? 7 : 8;
    if (h < sunrise || h >= sunset + 1) return { icon: "🌙", label: "Nuit — randonnée déconseillée", cls: "time-ctx-night" };
    if (h < sunrise + 2) return { icon: "🌅", label: "Aube — idéal pour une sortie courte", cls: "time-ctx-dawn" };
    if (h < 11) return { icon: "☀️", label: "Matin — fenêtre idéale", cls: "time-ctx-morning" };
    if (h < 14) return { icon: "🌞", label: "Milieu de journée — restez à l'ombre", cls: "time-ctx-noon" };
    if (h < 16) return { icon: "🌤", label: "Après-midi — bonne fenêtre", cls: "time-ctx-afternoon" };
    if (h < sunset) return { icon: "🌇", label: "Fin d'après-midi — préférez les courts parcours", cls: "time-ctx-lateday" };
    return { icon: "🌆", label: "Soirée — parcours très courts uniquement", cls: "time-ctx-evening" };
  }

  const timeCtx = getTimeContext();

  return (
    <main className="page">
      <header className="hero">
        <span className="hero-icon">🥾</span>
        <div className="hero-text">
          <h1>Randogen</h1>
          <p>Générateur intelligent de randonnées autour de vous.</p>
        </div>
        <span className={`time-ctx-badge ${timeCtx.cls}`} title="Contexte temporel">
          {timeCtx.icon} {timeCtx.label}
        </span>
      </header>

      <div className="status-bar">
        <span className="status-msg">{message}</span>
        {position && (
          <span className="status-pos">
            {position.latitude.toFixed(4)}, {position.longitude.toFixed(4)}
          </span>
        )}
        {weather && (
          <span className="status-weather">
            {weatherIcon(weather.weather_code)} {weatherLabel(weather)}
          </span>
        )}
        {liveTracking && <span className="status-gps">● GPS actif</span>}
        {error && <span className="status-error">{error}</span>}
        {warnings.map((warning) => (
          <span key={warning} className="status-warn">{warning}</span>
        ))}
        {selectedRouteId && (
          <button
            type="button"
            className="status-track-btn"
            onClick={() => setTrackingEnabled((value) => !value)}
          >
            {trackingEnabled ? "Stopper suivi GPS" : "Démarrer suivi GPS"}
          </button>
        )}
      </div>

      <div className="app-main">
        <aside className="left-column">
          <SearchForm
            distanceKm={distanceKm}
            routeCount={routeCount}
            ambiance={ambiance}
            terrain={terrain}
            effort={effort}
            biomePreference={biomePreference}
            prioritizeNature={prioritizeNature}
            prioritizeViewpoints={prioritizeViewpoints}
            prioritizeCalm={prioritizeCalm}
            avoidUrban={avoidUrban}
            avoidRoads={avoidRoads}
            avoidSteep={avoidSteep}
            avoidTouristic={avoidTouristic}
            adaptToWeather={adaptToWeather}
            difficultyPref={difficultyPref}
            loading={loading}
            hasPosition={position !== null}
            onDistanceChange={setDistanceKm}
            onRouteCountChange={setRouteCount}
            onAmbianceChange={setAmbiance}
            onTerrainChange={setTerrain}
            onEffortChange={setEffort}
            onBiomePreferenceChange={setBiomePreference}
            onDifficultyPrefChange={setDifficultyPref}
            onPrioritizeNatureChange={setPrioritizeNature}
            onPrioritizeViewpointsChange={setPrioritizeViewpoints}
            onPrioritizeCalmChange={setPrioritizeCalm}
            onAvoidUrbanChange={setAvoidUrban}
            onAvoidRoadsChange={setAvoidRoads}
            onAvoidSteepChange={setAvoidSteep}
            onAvoidTouristicChange={setAvoidTouristic}
            onAdaptToWeatherChange={setAdaptToWeather}
            onLocate={handleLocate}
            onGenerate={handleGenerate}
          />

          {loading && routes.length === 0 && (
            <section className="card">
              <h2>Chargement</h2>
              <div className="skeleton-grid">
                <div className="skeleton-card" />
                <div className="skeleton-card" />
                <div className="skeleton-card" />
              </div>
            </section>
          )}

          <RouteList
            routes={routes}
            selectedRouteId={selectedRouteId}
            hoveredRouteId={hoveredRouteId}
            onSelectRoute={setSelectedRouteId}
            onHoverRoute={setHoveredRouteId}
            onViewDetails={(routeId) => {
              setSelectedRouteId(routeId);
              setShowDetailPanel(true);
            }}
            favoriteRouteIds={favoriteItems.map((item) => item.stable_route_id)}
            onToggleFavorite={handleToggleFavorite}
          />
        </aside>

        <section className="right-column">
          <MapView
            position={position}
            routes={routes}
            selectedRouteId={selectedRouteId}
            hoveredRouteId={hoveredRouteId}
            onSelectRoute={(routeId) => {
              setSelectedRouteId(routeId);
              setShowDetailPanel(false);
            }}
            onHoverRoute={setHoveredRouteId}
          />

          {selectedRoute && showDetailPanel && (
            <>
              <RouteDetailPanel
                route={selectedRoute}
                onDownloadGpx={handleDownloadGpx}
                onDownloadGeoJson={handleDownloadGeoJson}
                onShare={handleShare}
                onOpenExternal={handleOpenExternal}
                exportMessage={exportMessage}
              />
              <section className="card">
                <AltitudeProfile points={selectedRoute.points} />
              </section>
            </>
          )}
        </section>
      </div>

      <section className="card secondary-panel">
        <div className="secondary-header">
          <h2>Espace personnel</h2>
          <div className="secondary-tabs">
            <button
              type="button"
              className={`secondary-tab ${secondaryTab === "history" ? "secondary-tab-active" : ""}`}
              onClick={() => setSecondaryTab("history")}
            >
              Historique
            </button>
            <button
              type="button"
              className={`secondary-tab ${secondaryTab === "favorites" ? "secondary-tab-active" : ""}`}
              onClick={() => setSecondaryTab("favorites")}
            >
              Favoris
            </button>
          </div>
        </div>

        {secondaryTab === "history" && (
          <>
            {historyItems.length === 0 && <p className="empty-state">Aucune recherche enregistrée.</p>}
            {historyItems.length > 0 && (
              <div className="history-list">
                {historyItems.slice(0, 8).map((item) => (
                  <div key={`${item.timestamp}-${item.result_route_ids.join("-")}`} className="history-item">
                    <strong>
                      {new Date(item.timestamp).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" })}
                    </strong>
                    {" — "}
                    {item.query.target_distance_km} km
                    {item.query.ambiance ? `, ${item.query.ambiance}` : ""}
                    {item.query.terrain ? `, ${item.query.terrain}` : ""}
                    {item.query.biome_preference ? `, ${item.query.biome_preference}` : ""}
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        {secondaryTab === "favorites" && (
          <>
            {favoriteItems.length === 0 && <p className="empty-state">Aucun favori pour le moment.</p>}
            {favoriteItems.length > 0 && (
              <div className="fav-list">
                {favoriteItems.slice(0, 10).map((item) => (
                  <div key={item.stable_route_id} className="fav-card">
                    <div className="fav-card-info">
                      <span className="fav-card-name">{item.name || "Parcours sans nom"}</span>
                      <div className="fav-card-stats">
                        {item.distance_km > 0 && <span>↔ {item.distance_km} km</span>}
                        {item.estimated_duration_min > 0 && (
                          <span>⏱ {formatDuration(item.estimated_duration_min)}</span>
                        )}
                        {item.estimated_elevation_gain_m > 0 && (
                          <span>↑ {item.estimated_elevation_gain_m} m</span>
                        )}
                      </div>
                    </div>
                    <button
                      type="button"
                      className="route-star-btn route-star-btn-active"
                      title="Retirer des favoris"
                      onClick={() => handleToggleFavorite(item.stable_route_id, true)}
                    >
                      ★
                    </button>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </section>

      {preferenceProfile?.has_data && (
        <section className="card profile-suggestion-card">
          <div className="profile-suggestion-header">
            <h2>Profil suggéré</h2>
            <span className="profile-suggestion-meta">Basé sur {preferenceProfile.search_count} recherche{preferenceProfile.search_count > 1 ? "s" : ""}</span>
          </div>
          <div className="profile-suggestion-body">
            {preferenceProfile.suggested_ambiance && (
              <span className="profile-chip">Ambiance : <strong>{preferenceProfile.suggested_ambiance}</strong></span>
            )}
            {preferenceProfile.suggested_terrain && (
              <span className="profile-chip">Terrain : <strong>{preferenceProfile.suggested_terrain}</strong></span>
            )}
            {preferenceProfile.suggested_effort && (
              <span className="profile-chip">Effort : <strong>{preferenceProfile.suggested_effort}</strong></span>
            )}
            {preferenceProfile.suggested_biome && (
              <span className="profile-chip">Biome : <strong>{preferenceProfile.suggested_biome}</strong></span>
            )}
            {preferenceProfile.average_distance_km && (
              <span className="profile-chip">Distance moy. : <strong>{preferenceProfile.average_distance_km} km</strong></span>
            )}
          </div>
          <button type="button" className="download-button" onClick={handleApplyProfile}>
            Appliquer ce profil
          </button>
        </section>
      )}
    </main>
  );
}
