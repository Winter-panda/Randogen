# Randogen

![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-early--development-orange)
![Version](https://img.shields.io/github/v/tag/Winter-panda/Randogen)
![Build](https://github.com/Winter-panda/Randogen/actions/workflows/build.yml/badge.svg)
![Tests](https://github.com/Winter-panda/Randogen/actions/workflows/tests.yml/badge.svg)
![Issues](https://img.shields.io/github/issues/Winter-panda/Randogen)
![Last commit](https://img.shields.io/github/last-commit/Winter-panda/Randogen)
![Repo size](https://img.shields.io/github/repo-size/Winter-panda/Randogen)

Générateur intelligent de randonnées et promenades à partir d’une distance cible autour de la position de l’utilisateur.
# Objectif du projet

Permettre Ã  un utilisateur de rÃ©pondre rapidement Ã  une question simple :

> Quelle randonnÃ©e ou promenade puis-je faire maintenant autour de moi ?

L'application doit Ãªtre capable de :

- rÃ©cupÃ©rer la position GPS
- gÃ©nÃ©rer plusieurs parcours autour de l'utilisateur
- approcher une distance cible
- afficher les itinÃ©raires sur une carte
- proposer des parcours cohÃ©rents et agrÃ©ables

---

# Cas d'utilisation

Exemples de requÃªtes possibles :

- Je veux marcher **5 km**
- Je veux une **balade de 45 minutes**
- Je veux une **boucle nature**
- Je veux Ã©viter les **grosses montÃ©es**

Lâ€™application propose ensuite plusieurs itinÃ©raires adaptÃ©s.

---

# FonctionnalitÃ©s prÃ©vues

## MVP

- gÃ©olocalisation utilisateur
- choix d'une distance cible
- gÃ©nÃ©ration automatique de parcours
- affichage des itinÃ©raires sur carte
- distance et durÃ©e estimÃ©e
- sÃ©lection dâ€™un parcours

## Ã‰volutions possibles

- prise en compte du dÃ©nivelÃ©
- difficultÃ© du parcours
- type de terrain
- parcours avec chien
- accessibilitÃ© poussette
- sauvegarde de parcours
- historique
- partage d'itinÃ©raires
- intÃ©gration mÃ©tÃ©o
- points dâ€™intÃ©rÃªt

---

# Architecture du projet

Le projet est organisÃ© en plusieurs modules.

Randogen
â”‚
â”œâ”€â”€ frontend
â”‚
â”œâ”€â”€ backend
â”‚
â”œâ”€â”€ routing-engine
â”‚
â”œâ”€â”€ data
â”‚
â”œâ”€â”€ docs
â”‚
â”œâ”€â”€ scripts
â”‚
â””â”€â”€ infra


---

## Frontend

Application utilisateur.

ResponsabilitÃ©s :

- interface
- gÃ©olocalisation
- affichage carte
- affichage des parcours
- interaction avec l'API

---

## Backend

API applicative.

ResponsabilitÃ©s :

- recevoir les demandes de gÃ©nÃ©ration
- orchestrer le moteur de routage
- appliquer les rÃ¨gles mÃ©tier
- retourner les parcours gÃ©nÃ©rÃ©s

---

## Routing Engine

CÅ“ur algorithmique du projet.

ResponsabilitÃ©s :

- gÃ©nÃ©ration des parcours
- calcul des boucles
- scoring des itinÃ©raires
- filtrage des parcours incohÃ©rents

---

## Data

DonnÃ©es cartographiques utilisÃ©es pour gÃ©nÃ©rer les itinÃ©raires.

Peut contenir :

- routes
- sentiers
- chemins
- donnÃ©es d'altitude

---

# Roadmap

## Phase 0

Cadrage du projet

- dÃ©finition des fonctionnalitÃ©s
- choix technologiques
- architecture

---

## Phase 1

Prototype du moteur de gÃ©nÃ©ration

Objectif :

gÃ©nÃ©rer un premier parcours simple Ã  partir :

- d'une position
- d'une distance cible

---

## Phase 2

CrÃ©ation de l'API backend

- endpoint de gÃ©nÃ©ration
- structure des rÃ©ponses
- validation des paramÃ¨tres

---

## Phase 3

MVP interface utilisateur

- saisie distance
- gÃ©olocalisation
- affichage carte
- affichage des rÃ©sultats

---

## Phase 4

AmÃ©lioration de la qualitÃ© des parcours

- scoring
- diversitÃ©
- filtrage des mauvais parcours

---

## Phase 5

FonctionnalitÃ©s avancÃ©es

- prÃ©fÃ©rences utilisateur
- dÃ©nivelÃ©
- historique
- partage
- optimisation des performances

---

# Structure du repository

Randogen
â”‚
â”œâ”€â”€ docs
â”‚ â”œâ”€â”€ vision-produit.md
â”‚ â”œâ”€â”€ roadmap.md
â”‚ â”œâ”€â”€ architecture.md
â”‚
â”œâ”€â”€ frontend
â”‚
â”œâ”€â”€ backend
â”‚
â”œâ”€â”€ routing-engine
â”‚
â”œâ”€â”€ data
â”‚
â”œâ”€â”€ scripts
â”‚
â”œâ”€â”€ infra
â”‚
â”œâ”€â”€ README.md
â”œâ”€â”€ LICENSE
â””â”€â”€ .gitignore


---

# Installation (Ã  venir)

Instructions d'installation en cours de rÃ©daction.

---

# Contribution

Les contributions sont les bienvenues.

Pour contribuer :

1. Fork du repository
2. CrÃ©ation d'une branche
3. Commit des modifications
4. Pull request

---

# Licence

Projet distribuÃ© sous licence MIT.

---

# Vision

Randogen vise Ã  devenir un outil simple permettant de **dÃ©couvrir des parcours autour de soi sans prÃ©paration prÃ©alable**.

L'objectif est de rendre la randonnÃ©e et la promenade **plus accessibles, spontanÃ©es et adaptÃ©es aux contraintes de chacun**.



