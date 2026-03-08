# Architecture (MVP v1)

## Frontend (`frontend/`)
- React + TypeScript + Leaflet.
- Responsabilites:
  - collecte des preferences utilisateur,
  - appel API generation,
  - affichage carte/resultats/detail,
  - export/partage, suivi GPS reel.

## Backend (`backend/src/`)
- FastAPI.
- Couches:
  - `api/` routes + controllers,
  - `application/` usecases + services,
  - `domain/` entites metier,
  - `infrastructure/` ORS, Overpass, meteo, config.

## Services metier principaux
- `route_generation_service`:
  - generation de candidats,
  - scoring global,
  - anti-duplication,
  - enrichissement POI,
  - diagnostics/fallback.
- `poi_enrichment_service`:
  - classification POI,
  - distance trace -> POI,
  - dedup/diversite/highlights.
- `contextual_scoring_service`:
  - ajustements heure/meteo/saison.
- `user_memory_service`:
  - historique/favoris/vus (memoire simple fichier JSON).

## Integrations externes
- OpenRouteService (generation de boucles).
- Overpass/OpenStreetMap (POI).
- Open-Meteo (contexte meteo, bonus/malus legers).

## Flux principal
1. Frontend envoie `POST /api/routes/generate`.
2. Backend genere/scrore/enrichit des `RouteCandidate`.
3. Backend renvoie routes + warnings + status.
4. Frontend affiche comparaison, carte et detail.
