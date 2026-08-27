# Projet 8 — API de scoring et socle MLOps

## Objectif

Mettre en production le modèle de scoring du Projet 6 pour l'entreprise fictive
« Prêt à Dépenser ». L'API doit évaluer, au moment de la demande, le risque qu'un
dossier gagné ne soit pas mené à son terme. Le système doit être testable,
conteneurisé, déployable et observable.

## Périmètre de cette première itération

- Exposer le modèle champion `xgboost_search` dans une API FastAPI.
- Réutiliser le pipeline sérialisé de Projet 6, y compris son prétraitement.
- Accepter un unique dossier à la fois avec les 44 variables connues du modèle.
- Retourner une probabilité de risque et une décision métier fondée sur le seuil
  `0.06` enregistré dans les métadonnées.
- Fournir tests, image Docker, workflow CI/CD et documentation de démarrage.

Les données sources de Projet 6 ne font pas partie de ce dépôt. Seuls le modèle,
ses métadonnées et des exemples synthétiques non identifiants y sont autorisés.

## Architecture

```text
client HTTP
    │ POST /predict
    ▼
FastAPI / Pydantic ── validation et erreurs 422
    │
    ▼
service de prédiction ── modèle chargé une fois au démarrage
    │
    ├── journal JSON : entrée pseudonymisée, résultat, latence, erreur éventuelle
    ▼
pipeline scikit-learn/XGBoost sérialisé
    │
    ▼
réponse : score, seuil, décision, version du modèle
```

Le modèle et `metadata.json` seront copiés depuis `Projet6/models/` dans
`models/`. Le chargeur de modèle sera créé pendant la durée de vie de l'application
et réutilisé par toutes les requêtes : aucun chargement à la requête.

## Contrat HTTP

- `GET /health` retourne l'état de préparation de l'API et la version du modèle.
- `POST /predict` reçoit un objet JSON comportant les 44 variables listées dans
  `models/matchers_option_a_metadata.json`.
- Tous les champs sont requis dans cette première version, afin qu'un appel
  incomplet soit refusé explicitement plutôt que silencieusement imputé.
- Les compteurs sont des entiers positifs ou nuls ; les montants, heures prévues
  et taux horaires sont positifs. Les chaînes catégorielles sont non vides.
- Une erreur de type, de champ manquant ou de valeur hors domaine retourne une
  réponse `422` structurée de FastAPI. Une indisponibilité du modèle retourne
  `503`; une erreur d'inférence imprévue retourne `500` sans exposer de détail
  technique au client.

La réponse réussie (`200`) contient au minimum :

```json
{
  "risk_score": 0.18,
  "threshold": 0.06,
  "risk_flag": true,
  "model_name": "xgboost_search",
  "model_version": "2026-06-15"
}
```

## Organisation du dépôt

```text
src/scoring_api/       application, schémas, service de modèle, journalisation
tests/                 tests unitaires et d'intégration HTTP
models/                modèle et métadonnées, sans données brutes
notebooks/             analyse de logs et de data drift
docs/                  décisions et guides
.github/workflows/     pipeline GitHub Actions
Dockerfile             image exécutable de l'API
requirements.txt       dépendances d'exécution et de test
README.md              lancement, contrat API et déploiement
```

## Tests et qualité

Les tests sont écrits avant le code de production. Ils couvrent :

1. l'état de santé de l'application ;
2. une prédiction valide avec une charge synthétique ;
3. un champ obligatoire absent ;
4. un type incorrect ;
5. une valeur numérique invalide ;
6. le chargement unique du modèle ;
7. la journalisation de la latence et du résultat.

## Conteneurisation et CI/CD

L'image Docker utilise Python slim, installe les dépendances figées et lance
Uvicorn. Elle n'embarque ni secret ni données métier.

Le workflow GitHub Actions se déclenche à chaque pull request et push sur `main` :

1. installation des dépendances et exécution de `pytest` ;
2. construction de l'image Docker seulement si les tests réussissent ;
3. vérification de démarrage de l'image et de `/health` ;
4. déploiement vers un Hugging Face Space Docker lors d'un push sur `main`, avec
   `HF_TOKEN` et `HF_SPACE_ID` stockés dans les secrets GitHub.

Sans ces deux secrets, l'étape de déploiement est volontairement bloquée avec un
message explicite : il ne sera jamais remplacé par un jeton en clair dans Git.

## Monitoring et étapes ultérieures

Chaque prédiction produira un événement JSON avec horodatage, version du modèle,
variables non identifiantes ou hachées, score, décision, durée et statut. Un
notebook comparera les distributions de production à une référence de Projet 6,
et suivra au minimum distribution des scores, latence et taux d'erreurs. Toute
exportation de logs respectera la minimisation des données et le RGPD.

## Historique Git prévu

1. `chore: initialize scoring API repository and design`
2. `feat: add versioned scoring model contract`
3. `feat: expose scoring prediction API`
4. `test: cover API validation and inference`
5. `build: containerize scoring API`
6. `ci: add test build and deployment workflow`
7. `feat: add production logging and drift analysis`
