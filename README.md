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
du Projet6, les logs de prédiction ou des secrets. Chaque appel à `/predict`
produit un événement JSON structuré contenant un identifiant, le timestamp, le
statut HTTP, la latence, la version du modèle et, en cas de succès, les entrées
validées, le score et la décision. Les erreurs ne contiennent ni entrée brute
ni détail technique. L'événement est écrit dans `logs/predictions.jsonl` et
préfixé par `ML_EVENT ` dans les logs standards de Render.

### Flux local gratuit

`API Render → logs structurés → export local → SQLite → analyse`

Le disque de Render gratuit est éphémère : le stockage durable du PoC est donc
local. On exporte les logs Render, puis on les importe de façon idempotente dans
la base SQLite `data/monitoring/monitoring.db`. Les bases, exports et rapports
sont volontairement ignorés par Git.

```bash
render logs -r srv-daddn7oae00c739qdfq0 -o json > data/monitoring/render-export.json
PYTHONPATH=src python scripts/import_render_logs.py --input data/monitoring/render-export.json
PYTHONPATH=src python scripts/analyze_monitoring.py --reference data/monitoring/reference_events.jsonl
```

Le rapport écrit `reports/monitoring/latest_report.json` et
`reports/monitoring/latest_report.md`. Il mesure le taux d'erreur et la latence
p95 sur tous les événements, puis le drift uniquement sur les prédictions
réussies. Les alertes initiales sont : taux d'erreur > 5 %, latence p95 >
1000 ms, PSI ≥ 0,20 pour une variable numérique et taux de catégorie inconnue
≥ 5 % pour une variable catégorielle.

Pour une démonstration entièrement reproductible, sans donnée métier ni
personnelle :

```bash
PYTHONPATH=src python scripts/generate_monitoring_demo.py
PYTHONPATH=src python scripts/import_render_logs.py --input data/monitoring/render_demo_export.jsonl
PYTHONPATH=src python scripts/analyze_monitoring.py --reference data/monitoring/reference_events.jsonl
```

La référence `synthetic_demo` provoque volontairement une alerte PSI sur
`heures_prevues` et une alerte de catégorie nouvelle sur `modalite`. Elle
prouve le pipeline de monitoring, pas une dérive réelle. Une conclusion de
production exige une référence stable et gouvernée issue du Projet6.

Les entrées peuvent contenir des données personnelles. En contexte réel, il
faut appliquer le RGPD : minimisation des champs, durée de rétention définie,
contrôle des accès, chiffrement du stockage et procédure de suppression. Le
PoC ne publie ni logs ni base de données.

## CI/CD et déploiement

GitHub Actions exécute les tests, construit l'image Docker et lance le test de
fumée à chaque pull request et à chaque push sur `main`. Le déploiement cible
un service web Docker Render :

- API publique : `https://projet8-scoring-api.onrender.com`
- Contrôle de santé : `https://projet8-scoring-api.onrender.com/health`

Render construit le `Dockerfile` du dépôt et vérifie `/health` avant de rendre
une nouvelle version accessible. Le service est configuré sur la branche
`main` avec l'option « After CI Checks Pass » : Render ne déploie donc qu'après
le succès des deux jobs GitHub Actions.

L'offre gratuite Render met le service en veille après une période d'inactivité
et son disque est éphémère. Les événements `logs/predictions.jsonl` ne doivent
donc pas être considérés comme un stockage durable : l'étape de monitoring les
enverra vers un stockage persistant.
