# Roadmap de développement — Application de génération de randonnées

## 1. Vision du projet

L’application a pour objectif de permettre à un utilisateur de :

- renseigner une distance ou une durée cible
- utiliser sa position actuelle
- générer automatiquement plusieurs propositions de randonnées ou promenades
- visualiser les parcours sur carte
- choisir un itinéraire adapté à ses préférences

Le cœur du projet repose sur la génération d’itinéraires pertinents autour de l’utilisateur.

---

# 2. Hypothèse de produit

## MVP visé

Pour une première version, l’application doit permettre de :

- récupérer la position utilisateur
- demander une distance cible
- générer plusieurs parcours proches de cette distance
- afficher les résultats sur carte
- donner quelques informations utiles :
  - distance
  - durée estimée
  - dénivelé approximatif
  - type de parcours

L’objectif du MVP n’est pas d’être parfait, mais de valider que :

- la génération est techniquement faisable
- les parcours proposés ont du sens
- l’expérience utilisateur est compréhensible et utile

---

# 3. Roadmap de développement

## Phase 0 — Cadrage et conception

### Objectifs

- définir précisément le besoin
- cadrer le MVP
- choisir les technologies
- identifier les contraintes techniques

### Livrables

- document de vision produit
- liste des fonctionnalités MVP
- choix de stack technique
- premiers schémas d’architecture
- définition des flux utilisateurs

### Tâches

- définir les cas d’usage principaux
- définir les entrées utilisateur :
  - distance
  - durée
  - difficulté
- définir les sorties attendues :
  - boucle
  - distance réelle
  - durée estimée
  - tracé carte
- lister les sources de données cartographiques
- identifier la logique de calcul des itinéraires
- définir les écrans principaux de l’application

---

## Phase 1 — Prototype technique du moteur de génération

### Objectifs

Créer un prototype backend capable de :

- prendre une position de départ
- prendre une distance cible
- générer 1 à 3 itinéraires plausibles

### Livrables

- service de génération d’itinéraires
- premier algorithme de calcul
- format JSON de réponse exploitable par une application mobile ou web

### Tâches

- récupérer les données cartographiques utiles
- modéliser les chemins sous forme de graphe
- développer un premier algorithme de génération de boucle
- calculer :
  - longueur totale
  - durée estimée
  - dénivelé simple
- retourner plusieurs propositions
- tester sur plusieurs zones :
  - ville
  - campagne
  - zone mixte

### Résultat attendu

À ce stade, on doit déjà pouvoir répondre à une requête du type :

> position X + distance 6 km => 3 parcours possibles

---

## Phase 2 — MVP backend

### Objectifs

Transformer le prototype en vrai backend exploitable.

### Livrables

- API backend stable
- endpoints documentés
- gestion des erreurs
- logique de calcul mieux structurée

### Tâches

- créer une API REST
- ajouter les endpoints principaux
- normaliser les réponses JSON
- gérer les paramètres utilisateur
- améliorer la génération pour éviter les parcours absurdes
- ajouter des règles métier :
  - éviter routes trop fréquentées
  - favoriser chemins piétons
  - tolérance autour de la distance demandée
- journaliser les traitements
- préparer le backend à être consommé par le front

### Endpoints MVP possibles

- `POST /route/generate`
- `GET /health`
- `GET /config`
- `GET /route/{id}`

---

## Phase 3 — MVP interface utilisateur

### Objectifs

Créer une première interface utilisable.

### Livrables

- application mobile ou web MVP
- écran de saisie
- écran de résultats
- écran carte

### Tâches

- créer l’écran d’accueil
- demander l’autorisation de géolocalisation
- permettre le choix de distance
- appeler l’API backend
- afficher plusieurs propositions
- afficher les informations principales
- intégrer une carte avec tracé
- permettre la sélection d’un parcours

### Écrans minimum

- écran d’accueil
- écran de recherche
- écran résultats
- écran détail parcours

---

## Phase 4 — Amélioration de la qualité des parcours

### Objectifs

Rendre les propositions plus naturelles, plus variées et plus utiles.

### Livrables

- algorithme amélioré
- score de qualité des parcours
- filtrage intelligent

### Tâches

- ajouter un score de pertinence
- éviter les demi-tours inutiles
- éviter les boucles artificielles
- favoriser les segments agréables
- améliorer la diversité des propositions
- pondérer selon :
  - type de voie
  - régularité du parcours
  - qualité paysagère si disponible
  - sécurité piétonne

### Résultat attendu

Les propositions ne doivent pas seulement être “possibles”, elles doivent être “crédibles”.

---

## Phase 5 — Fonctionnalités avancées

### Objectifs

Enrichir l’expérience utilisateur.

### Fonctionnalités possibles

- choix du niveau de difficulté
- prise en compte du dénivelé
- filtre promenade / randonnée / trail
- parcours avec chien
- accessibilité poussette
- estimation plus fine du temps
- sauvegarde des parcours favoris
- historique
- partage d’itinéraire
- points d’intérêt
- météo
- mode hors ligne

---

## Phase 6 — Industrialisation

### Objectifs

Préparer une vraie mise en production.

### Livrables

- CI/CD
- monitoring
- tests automatisés
- sécurité minimum
- documentation

### Tâches

- tests unitaires
- tests d’intégration
- tests de charge
- gestion de configuration
- logs applicatifs
- suivi des erreurs
- optimisation des performances
- documentation développeur
- documentation API

---

# 4. Priorisation conseillée

## Priorité absolue

- géolocalisation
- saisie de distance
- génération de parcours
- affichage carte
- détail distance / durée

## Priorité forte

- qualité des boucles
- dénivelé
- diversité des propositions
- stabilité API

## Priorité secondaire

- comptes utilisateurs
- favoris
- partage
- historique
- personnalisation avancée

---

# 5. Découpage technique du projet

## Bloc 1 — Frontend

Responsabilités :

- interface utilisateur
- géolocalisation
- affichage carte
- affichage résultats
- interaction avec l’API

## Bloc 2 — Backend API

Responsabilités :

- recevoir les demandes de génération
- orchestrer les calculs
- retourner les parcours
- appliquer les règles métier

## Bloc 3 — Moteur de routage

Responsabilités :

- calcul de trajets sur le graphe
- génération de boucles
- optimisation distance / qualité

## Bloc 4 — Données cartographiques

Responsabilités :

- fournir routes, chemins, sentiers
- fournir informations de praticabilité
- éventuellement fournir altitude et contexte

---

# 6. Arborescence logique du projet

Voici une proposition d’arborescence pour un projet structuré proprement.

## Version monorepo

```text
randonnee-app/
│
├── README.md
├── LICENSE
├── .gitignore
├── docs/
│   ├── vision-produit.md
│   ├── roadmap.md
│   ├── architecture.md
│   ├── algorithme-generation.md
│   ├── api-spec.md
│   └── maquettes/
│
├── frontend/
│   ├── README.md
│   ├── public/
│   └── src/
│       ├── app/
│       ├── assets/
│       ├── components/
│       │   ├── common/
│       │   ├── map/
│       │   ├── route/
│       │   └── search/
│       ├── pages/
│       │   ├── Home/
│       │   ├── Search/
│       │   ├── Results/
│       │   └── RouteDetail/
│       ├── services/
│       │   ├── api/
│       │   ├── geolocation/
│       │   └── map/
│       ├── hooks/
│       ├── store/
│       ├── types/
│       ├── utils/
│       └── tests/
│
├── backend/
│   ├── README.md
│   └── src/
│       ├── api/
│       │   ├── controllers/
│       │   ├── routes/
│       │   └── middlewares/
│       ├── application/
│       │   ├── dto/
│       │   ├── services/
│       │   └── usecases/
│       ├── domain/
│       │   ├── entities/
│       │   ├── models/
│       │   ├── repositories/
│       │   └── rules/
│       ├── infrastructure/
│       │   ├── config/
│       │   ├── logging/
│       │   ├── persistence/
│       │   ├── cartography/
│       │   └── routing/
│       ├── tests/
│       │   ├── unit/
│       │   ├── integration/
│       │   └── fixtures/
│       └── main/
│
├── routing-engine/
│   ├── README.md
│   ├── src/
│   │   ├── graph/
│   │   ├── generators/
│   │   ├── scorers/
│   │   ├── elevation/
│   │   ├── filters/
│   │   ├── models/
│   │   └── tests/
│   └── data/
│
├── data/
│   ├── raw/
│   ├── processed/
│   ├── samples/
│   └── elevation/
│
├── scripts/
│   ├── import-data/
│   ├── preprocess/
│   ├── generate-sample-routes/
│   └── maintenance/
│
├── infra/
│   ├── docker/
│   ├── compose/
│   ├── ci/
│   └── deployment/
│
└── tools/
    ├── benchmarks/
    ├── debug/
    └── simulators/