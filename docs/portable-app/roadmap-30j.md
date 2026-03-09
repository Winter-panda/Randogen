# Portable App - Priorite 30 jours

## Semaine 1
- Monorepo `apps/*` + `packages/*`.
- `packages/engine-sdk` avec contrat `RouteEngine`.
- Implémentation `RemoteEngine` branchée sur l'API FastAPI existante.

## Semaine 2
- Intégration Capacitor (`apps/mobile`) avec GPS + carte.
- Intégration Tauri (`apps/desktop`) avec shell desktop.
- Validation UX multi-support avec le même frontend (`apps/web`).

## Semaine 3
- Stockage local (SQLite) pour historique/favoris/préférences.
- Cache POI local.
- Exports GPX/GeoJSON stabilisés sur mobile/desktop.

## Semaine 4
- Fallback hors réseau (cache local prioritaire).
- Offline partiel stable (pas d'écran vide).
- Packaging:
  - Android/iOS (stores),
  - Desktop (NSIS/DMG/AppImage).

## Critères de réussite
- 1 codebase UI.
- 3 cibles: web/mobile/desktop.
- Démarrage utilisateur "clic et ça marche".
- Dégradation propre hors réseau.
