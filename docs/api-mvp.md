# API MVP - Randogen

Base URL: `http://127.0.0.1:8000/api`

## Sante
- `GET /health`

## Routes
- `POST /routes/generate`
  - Body (minimal):
    - `user_id: string`
    - `latitude: float`
    - `longitude: float`
    - `target_distance_km: float`
    - `route_count: int`
  - Body (prefs):
    - `ambiance`, `terrain`, `effort`
    - `prioritize_nature`, `prioritize_viewpoints`, `prioritize_calm`
    - `avoid_urban`, `avoid_roads`, `avoid_steep`, `avoid_touristic`
    - `adapt_to_weather`
  - Reponse:
    - `status`, `warnings`, `requested_route_count`, `generated_route_count`
    - `routes[]` (points, score, tags, POI, detail, explainability)

- `GET /routes/{stable_route_id}`
  - Retourne un parcours partage/detail.

- `GET /routes/{stable_route_id}/export.gpx`
- `GET /routes/{stable_route_id}/export.geojson`

## Memoire utilisateur (simple)
- `GET /routes/users/{user_id}/history`
- `GET /routes/users/{user_id}/favorites`
- `POST /routes/users/{user_id}/favorites/{stable_route_id}`
- `DELETE /routes/users/{user_id}/favorites/{stable_route_id}`
- `POST /routes/users/{user_id}/views/{stable_route_id}`

## Notes
- Documentation interactive FastAPI: `http://127.0.0.1:8000/docs`
- Les exports et le partage reposent sur `stable_route_id`.
