# Bootstrap Portable-App (immediat)

## Arborescence cible

```text
apps/
  web/        # React (UI unique)
  mobile/     # Capacitor Android/iOS
  desktop/    # Tauri Windows/macOS/Linux
packages/
  shared-types/
  shared-ui/
  engine-sdk/
backend/
docs/portable-app/
```

## Commandes de demarrage

```bash
# dependances workspace
npm install

# web
npm run dev:web

# mobile (apres "cap add android/ios" une premiere fois)
npm run mobile:sync
npm run mobile:android

# desktop (prerequis rustup/cargo)
npm run desktop:dev
```

## Contrat moteur unique

- `RouteEngine.generateRoutes`
- `RouteEngine.fetchNearbyPois`
- `RouteEngine.getWeather`
- `RouteEngine.exportGpx`

Implementations:

- `RemoteEngine`: API FastAPI existante.
- `LocalEngine`: fallback/cache local progressif (memoire, puis SQLite).

## Prochaine iteration recommandee

1. Ajouter `packages/storage-sqlite` (historique/favoris/preferences).
2. Persister le cache POI + meteo par zone.
3. Basculer automatiquement `RemoteEngine -> LocalEngine` en cas de perte reseau.
4. Ajouter packs regionaux offline pour le routage complet.
