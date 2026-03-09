# Checklist Qualite - MVP v1

## Produit
- [ ] La promesse produit est compréhensible en moins de 10 secondes.
- [ ] L'utilisateur peut choisir un parcours sans aide technique.
- [ ] Les differences entre parcours sont visibles (distance, denivele, atouts).

## Backend
- [ ] `POST /api/routes/generate` retourne 1..N parcours (ou warnings explicites).
- [ ] `GET /api/routes/{stable_route_id}` fonctionne apres generation.
- [ ] Exports:
  - [ ] `GET /api/routes/{stable_route_id}/export.gpx`
  - [ ] `GET /api/routes/{stable_route_id}/export.geojson`
- [ ] Endpoints memoire utilisateur:
  - [ ] `GET /api/routes/users/{user_id}/history`
  - [ ] `GET /api/routes/users/{user_id}/favorites`
  - [ ] `POST /api/routes/users/{user_id}/favorites/{stable_route_id}`
  - [ ] `DELETE /api/routes/users/{user_id}/favorites/{stable_route_id}`
  - [ ] `POST /api/routes/users/{user_id}/views/{stable_route_id}`
- [ ] Logs utiles: tentatives, rejets, fallback, warnings.

## Frontend
- [ ] Recherche, carte et resultats restent lisibles sur mobile.
- [ ] Fiche detail accessible depuis une carte resultat.
- [ ] Etats clairs: chargement, erreur, vide, generation partielle.
- [ ] Suivi GPS reel actif sur parcours selectionne.

## Donnees/POI
- [ ] Eau/panoramas/patrimoine visibles sur les parcours pertinents.
- [ ] Labels highlights stables et compréhensibles.
- [ ] Le nombre de POI affiches ne surcharge pas la vue.

## Stabilite
- [ ] Pas d'erreur console bloquante sur parcours nominal.
- [ ] Build frontend OK (`npm run typecheck:web`).
- [ ] Health backend OK (`GET /health`).
