# Randogen

Randogen est un generateur de boucles randonnee/promenade autour de la position utilisateur.

Promesse produit:
"Dis-moi ce que tu veux faire maintenant, Randogen te propose une vraie boucle adaptee autour de toi."

## Statut
- MVP v1 demonstrable (frontend + backend local).
- Focus: generation credible, lisibilite, detail parcours, export.

## Demarrage rapide

### Backend
```powershell
cd d:\Github\Randogen\backend
.\.venv\Scripts\python.exe -m uvicorn src.main.app:app --host 127.0.0.1 --port 8000 --reload
```

### Frontend
```powershell
cd d:\Github\Randogen\frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

### URLs utiles
- App: `http://127.0.0.1:5173`
- Health: `http://127.0.0.1:8000/health`
- Swagger: `http://127.0.0.1:8000/docs`

## Perimetre MVP v1 (fige)
- Generation de plusieurs boucles.
- Filtres ambiance / terrain / effort.
- Scoring lisible + raisons du classement.
- Carte + comparaison de parcours.
- POI (eau, panorama, patrimoine, nature, services, acces).
- Fiche detail parcours.
- Export GPX/GeoJSON.
- Partage par `stable_route_id`.
- Suivi GPS reel sur parcours selectionne.
- Historique/favoris simple.
- Robustesse minimale (cache/fallback/warnings).

Details: [MVP v1](d:/Github/Randogen/docs/mvp-v1.md)

## API MVP
Documentation rapide des endpoints:
[API MVP](d:/Github/Randogen/docs/api-mvp.md)

## Checklist qualite
Checklist de validation avant demo:
[Release checklist v1](d:/Github/Randogen/docs/release-checklist-v1.md)

## Architecture
Vue d'ensemble:
[Architecture](d:/Github/Randogen/docs/architecture.md)

## Licence
MIT
