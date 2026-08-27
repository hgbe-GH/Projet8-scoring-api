# Projet 8 — Matchers scoring API

API FastAPI de mise en production du modèle de scoring du Projet6. Elle estime le
risque qu'un dossier gagné ne soit pas mené à son terme.

## Prérequis

- Python 3.12
- Docker (pour l'exécution conteneurisée)

## Installation et lancement local

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
PYTHONPATH=src .venv/bin/uvicorn scoring_api.main:app --reload
```

L'API est alors disponible sur `http://127.0.0.1:8000` et sa documentation
Swagger sur `http://127.0.0.1:8000/docs`.

## Endpoints

- `GET /health` : vérifie que le modèle est chargé.
- `POST /predict` : accepte les 44 variables définies dans
  `models/matchers_option_a_metadata.json` et renvoie `risk_score`,
  `threshold`, `risk_flag`, `model_name` et `model_version`.

Les champs requis, types incorrects et valeurs invalides reçoivent une réponse
`422`. Le modèle est chargé une fois au démarrage, puis réutilisé.

## Tests

```bash
PYTHONPATH=src .venv/bin/pytest -v
```

## Docker

```bash
docker build -t projet8-scoring-api:local .
docker run --rm -p 8000:8000 projet8-scoring-api:local
```

Le test de fumée construit l'image et vérifie `/health` :

```bash
bash tests/test_container_smoke.sh
```

## Données et monitoring

Le dépôt versionne le modèle et ses métadonnées, mais jamais les données brutes
du Projet6, les logs de prédiction ou des secrets. Les événements locaux sont
écrits sous `logs/predictions.jsonl`, qui est ignoré par Git. Ils contiennent
les entrées validées, le score, la décision, la latence et la version du modèle
pour préparer l'analyse ultérieure de dérive.

## CI/CD et déploiement

GitHub Actions exécute les tests, construit l'image Docker et lance le test de
fumée à chaque pull request et à chaque push sur `main`. Le déploiement cible
un Hugging Face Space Docker après ajout de ces secrets dans le dépôt GitHub :

- `HF_TOKEN` : jeton d'accès Hugging Face avec droit d'écriture.
- `HF_SPACE_ID` : identifiant du Space au format `utilisateur/nom-du-space`.

Aucun secret ne doit être inscrit dans un fichier, une commande shell mémorisée
ou un commit.

