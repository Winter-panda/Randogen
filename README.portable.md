# Randogen Portable

Projet multi-support derive de Randogen pour viser:

- Web (PWA)
- Android / iOS (Capacitor)
- Windows / macOS / Linux (Tauri)

## Arborescence

```text
randogen-portable/
  apps/
    web/
    mobile/
    desktop/
  packages/
    shared-types/
    engine-sdk/
  scripts/
    dev/
```

## Demarrage rapide

1. Lancer le backend Randogen principal (port 8010).
2. Installer les deps du web portable:
   `cd apps/web && npm install`
3. Lancer le web portable:
   `npm run dev -- --host 127.0.0.1 --port 5174`

## Etapes suivantes

- brancher `apps/web` sur `packages/shared-types`
- initialiser Capacitor dans `apps/mobile`
- initialiser Tauri dans `apps/desktop`
- migrer progressivement le moteur vers `packages/engine-sdk`
