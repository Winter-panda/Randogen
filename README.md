# Randogen

![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-early--development-orange)
![Version](https://img.shields.io/github/v/tag/Winter-panda/Randogen)
![Build](https://github.com/Winter-panda/Randogen/actions/workflows/build.yml/badge.svg)
![Tests](https://github.com/Winter-panda/Randogen/actions/workflows/tests.yml/badge.svg)
![Issues](https://img.shields.io/github/issues/Winter-panda/Randogen)
![Last commit](https://img.shields.io/github/last-commit/Winter-panda/Randogen)
![Repo size](https://img.shields.io/github/repo-size/Winter-panda/Randogen)

# Randogen

Générateur intelligent de randonnées et promenades à partir d'une
distance cible autour de la position de l'utilisateur.

Randogen permet à un utilisateur de définir une distance ou une durée,
puis de générer automatiquement plusieurs parcours possibles autour de
sa position.

Contrairement aux applications de tracking classiques, Randogen ne se
contente pas d'enregistrer une activité : il propose des randonnées
adaptées à l'intention de l'utilisateur.

## Objectif du projet

Permettre à un utilisateur de répondre rapidement à une question simple
:

> Quelle randonnée ou promenade puis-je faire maintenant autour de moi ?

L'application doit être capable de :

-   récupérer la position GPS
-   générer plusieurs parcours autour de l'utilisateur
-   approcher une distance cible
-   afficher les itinéraires sur une carte
-   proposer des parcours cohérents et agréables

## Cas d'utilisation

Exemples de requêtes possibles :

-   Je veux marcher **5 km**
-   Je veux une **balade de 45 minutes**
-   Je veux une **boucle nature**
-   Je veux éviter les **grosses montées**

L'application propose ensuite plusieurs itinéraires adaptés.

## Fonctionnalités prévues

### MVP

-   géolocalisation utilisateur
-   choix d'une distance cible
-   génération automatique de parcours
-   affichage des itinéraires sur carte
-   distance et durée estimée
-   sélection d'un parcours

### Évolutions possibles

-   prise en compte du dénivelé
-   difficulté du parcours
-   type de terrain
-   parcours avec chien
-   accessibilité poussette
-   sauvegarde de parcours
-   historique
-   partage d'itinéraires
-   intégration météo
-   points d'intérêt

## Architecture du projet

Le projet est organisé en plusieurs modules.

    Randogen
    │
    ├── apps/web
    ├── apps/mobile
    ├── apps/desktop
    ├── backend
    ├── packages/shared-types
    ├── packages/shared-ui
    ├── packages/engine-sdk
    ├── docs
    └── scripts

### Frontend (apps/web)

Application utilisateur.

Responsabilités :

-   interface
-   géolocalisation
-   affichage carte
-   affichage des parcours
-   interaction avec l'API

### Backend

API applicative.

Responsabilités :

-   recevoir les demandes de génération
-   orchestrer le moteur de routage
-   appliquer les règles métier
-   retourner les parcours générés

### Engine SDK (packages/engine-sdk)

Contrat unique `RouteEngine` pour mutualiser l'accès moteur entre web/mobile/desktop.

Responsabilités :

-   interface unifiée (`generateRoutes`, `fetchNearbyPois`, `getWeather`, `exportGpx`)
-   implémentation `RemoteEngine` (API FastAPI)
-   implémentation `LocalEngine` (fallback/cache progressif)

### Data

Données cartographiques utilisées pour générer les itinéraires.

Peut contenir :

-   routes
-   sentiers
-   chemins
-   données d'altitude

## Roadmap

### Phase 0

Cadrage du projet :

-   définition des fonctionnalités
-   choix technologiques
-   architecture

### Phase 1

Prototype du moteur de génération.

Objectif :

générer un premier parcours simple à partir :

-   d'une position
-   d'une distance cible

### Phase 2

Création de l'API backend :

-   endpoint de génération
-   structure des réponses
-   validation des paramètres

### Phase 3

MVP interface utilisateur :

-   saisie distance
-   géolocalisation
-   affichage carte
-   affichage des résultats

### Phase 4

Amélioration de la qualité des parcours :

-   scoring
-   diversité
-   filtrage des mauvais parcours

### Phase 5

Fonctionnalités avancées :

-   préférences utilisateur
-   dénivelé
-   historique
-   partage
-   optimisation des performances

## Structure du repository

    Randogen
    │
    ├── docs
    │   ├── vision-produit.md
    │   ├── roadmap.md
    │   ├── architecture.md
    │
    ├── apps
    │   ├── web
    │   ├── mobile
    │   └── desktop
    ├── backend
    ├── packages
    │   ├── shared-types
    │   ├── shared-ui
    │   └── engine-sdk
    ├── scripts
    │
    ├── README.md
    ├── LICENSE
    └── .gitignore

## Installation

Instructions d'installation en cours de rédaction.

## Portable App (branche `portable-app`)

- Plan 30 jours: `docs/portable-app/roadmap-30j.md`
- Bootstrap technique: `docs/portable-app/bootstrap.md`

## Démarrage local (Windows)

Backend :

```powershell
cd D:\Github\Randogen-portable
npm run backend:dev
```

Frontend web :

```powershell
cd D:\Github\Randogen-portable
$env:npm_config_cache = "D:\Github\Randogen-portable\.npm-cache"
# optionnel si backend sur un autre port
# $env:VITE_API_URL = "http://127.0.0.1:8010/api"
npm install
npm run dev:web
```

Mobile (Capacitor) :

```powershell
cd D:\Github\Randogen-portable
npm run mobile:sync
npm run mobile:android
```

Desktop (Tauri) :

```powershell
cd D:\Github\Randogen-portable
npm run desktop:dev
```

## Dépannage Windows

- Erreur `uv cache ... AppData\Local\uv\cache ... Access denied` :
  utiliser `UV_CACHE_DIR` pointant vers le projet (commande ci-dessus).
- Erreur `Error: spawn EPERM` avec Vite/esbuild :
  utiliser Node LTS 22 (`.nvmrc` = `22.13.1`). Node 24 provoque ce blocage dans cet environnement.

## Contribution

Les contributions sont les bienvenues.

Pour contribuer :

1.  Fork du repository
2.  Création d'une branche
3.  Commit des modifications
4.  Pull request

## Licence

Projet distribué sous licence MIT.

## Vision

Randogen vise à devenir un outil simple permettant de découvrir des
parcours autour de soi sans préparation préalable.

L'objectif est de rendre la randonnée et la promenade plus accessibles,
spontanées et adaptées aux contraintes de chacun.
