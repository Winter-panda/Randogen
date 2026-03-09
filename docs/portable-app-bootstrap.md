# Bootstrap Portable App

Ce document decrit le squelette `portable-app` pour separer la version
stable de Randogen et la version multi-support (web/mobile/desktop).

## Cible

- projet stable: `D:\Github\Randogen`
- projet portable: `D:\Github\Randogen-portable`

## Script d'initialisation

Depuis le repo principal:

```powershell
cd D:\Github\Randogen
powershell -ExecutionPolicy Bypass -File .\scripts\maintenance\init-portable-app.ps1
```

Options utiles:

```powershell
# Choisir un autre chemin
powershell -ExecutionPolicy Bypass -File .\scripts\maintenance\init-portable-app.ps1 `
  -ProjectPath "D:\Github\Randogen-portable"

# Ne pas utiliser git worktree
powershell -ExecutionPolicy Bypass -File .\scripts\maintenance\init-portable-app.ps1 `
  -UseWorktree:$false

# Eviter de recopier frontend vers apps/web
powershell -ExecutionPolicy Bypass -File .\scripts\maintenance\init-portable-app.ps1 `
  -SkipFrontendCopy
```

## Arborescence generee

```text
Randogen-portable/
  apps/
    web/                 # frontend recopie depuis Randogen/frontend
    mobile/              # shell Capacitor
    desktop/             # shell Tauri
  packages/
    shared-types/        # types communs (copie de frontend/src/types/route.ts)
    engine-sdk/          # contrat moteur (RemoteEngine + LocalEngine stub)
  scripts/
    dev/
      start-web.ps1
  package.json
  tsconfig.base.json
  README.portable.md
```

## Demarrage immediate (portable web)

1. Lancer le backend depuis le projet principal (port 8010).
2. Lancer le frontend portable:

```powershell
cd D:\Github\Randogen-portable\apps\web
npm install
npm run dev -- --host 127.0.0.1 --port 5174
```

## Etapes suivantes recommandes

1. Brancher `apps/web` sur `@randogen/shared-types`.
2. Initialiser Capacitor (`apps/mobile`).
3. Initialiser Tauri (`apps/desktop`).
4. Migrer l'acces API vers `@randogen/engine-sdk`.
5. Ajouter fallback offline progressif (cache POI, tuiles, historique local).
