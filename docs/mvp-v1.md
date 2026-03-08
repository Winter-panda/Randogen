# MVP v1 - Randogen (Version Demonstrable)

## Promesse produit
"Dis-moi ce que tu veux faire maintenant, Randogen te propose une vraie boucle adaptee autour de toi."

## Perimetre fige v1
- Generation de plusieurs boucles autour de la position utilisateur.
- Filtres utilisateur: ambiance, terrain, effort.
- Scoring lisible et explicable (distance, sentiers, nature, calme, POI, contexte).
- Affichage carte + comparaison de parcours.
- Fiche detail d'un parcours.
- POI (eau, panorama, patrimoine, nature, services, acces) avec labels highlights.
- Export GPX et GeoJSON.
- Partage par lien (stable route id).
- Suivi GPS reel en direct sur parcours selectionne.
- Historique/favoris simple (memoire locale backend par `user_id`).
- Robustesse minimale: cache routes/POI, fallback, warnings de generation.

## Hors perimetre v1 (backlog)
- Comptes utilisateurs avances.
- Social/communautaire.
- Recommandation ML avancee.
- Personnalisation ultra-fine multi-profil.
- Offline complet.

## Definition de "Termine" v1
- Une personne externe peut:
  1. se localiser,
  2. generer 3 boucles,
  3. comprendre pourquoi elles sont classees,
  4. ouvrir le detail,
  5. exporter en GPX,
  6. suivre sa position en direct sur la carte.
- Aucun crash bloquant sur erreurs reseau classiques (ORS/Overpass/meteo).
- Interface lisible sur desktop et mobile.
