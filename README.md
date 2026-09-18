# Projet 8 — Matchers scoring API

API FastAPI de mise en production du modèle de scoring du Projet6. Elle estime le
risque qu'un dossier gagné ne soit pas mené à son terme.

Pour la soutenance, ouvrir la [présentation HTML et son parcours de
démonstration](docs/presentation-soutenance.html). Elle renvoie vers l'API
publique, Streamlit local, la preuve SQLite et [l'audit du modèle et des
données](docs/model-data-audit.md).

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

Les 44 clés sont requises ; 17 valeurs peuvent être `null`, comme dans la base
du Projet6 et dans le pipeline d'imputation du modèle. Cinq variables de type
oui/non attendent des booléens JSON (`true` ou `false`), et les zéros de
`client_rang_dossier` et `montant_demande_eur` sont acceptés car ils figurent
dans le holdout. Un champ absent, un type incorrect ou une valeur invalide
reçoit `422`. Le modèle est chargé une fois au démarrage, puis réutilisé.
L'[audit du contrat et des données](docs/model-data-audit.md) vérifie que les
248 dossiers du holdout passent l'API avec les mêmes scores que dans le Projet6.

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

`API Render → logs structurés → export local → SQLite → Evidently → Streamlit`

Le disque de Render gratuit est éphémère : le stockage durable du PoC est donc
local. On exporte les logs Render, puis on les importe de façon idempotente dans
la base SQLite `data/monitoring/monitoring.db`. Les bases, exports et rapports
sont volontairement ignorés par Git.

Installer les dépendances du monitoring local dans le même environnement virtuel.
L'image Docker de l'API n'installe que `requirements.txt` :

```bash
.venv/bin/pip install -r requirements-monitoring.txt
```

Avant une analyse réelle, préparer une référence JSONL issue du Projet6 avec
une valeur `reference_source` identique sur toutes les lignes. La référence
générée ci-dessous est uniquement destinée à la démonstration.

```bash
mkdir -p data/monitoring
render logs -r srv-daddn7oae00c739qdfq0 -o json > data/monitoring/render-export.json
PYTHONPATH=src .venv/bin/python scripts/import_render_logs.py --input data/monitoring/render-export.json
PYTHONPATH=src .venv/bin/python scripts/analyze_monitoring.py --reference data/monitoring/reference_events.jsonl
PYTHONPATH=src .venv/bin/streamlit run scripts/monitoring_dashboard.py
```

Le rapport écrit `reports/monitoring/latest_report.json` et
`reports/monitoring/latest_report.md`, plus
`reports/monitoring/evidently_report.{json,html}` si la comparaison est possible.
Streamlit affiche les métriques opérationnelles, les résultats de drift et une
preuve relue directement dans SQLite (nombre de lignes, période et dernier ID).
Si de nouveaux événements ont été importés depuis le dernier rapport, le
dashboard avertit qu'il faut relancer l'analyse.
L'analyse mesure le taux d'erreur et la latence p95 sur tous les événements,
puis le drift uniquement sur les prédictions réussies. Evidently compare les
six variables suivies après exclusion des lignes incomplètes. Il faut au moins
10 lignes complètes dans chaque jeu ; sinon le statut est `insufficient_data`.
Les alertes locales sont : taux d'erreur > 5 %, latence p95 > 1000 ms, PSI ≥
0,20 pour une variable numérique et taux de catégorie inconnue ≥ 5 % pour une
variable catégorielle. Evidently utilise le test K-S pour les variables
numériques et la distance de Jensen–Shannon (seuil 0,10) pour les catégories,
afin de couvrir les catégories absentes de la référence. Ses résultats figurent
séparément dans le tableau de bord et le rapport HTML.

Pour une démonstration entièrement reproductible, sans donnée métier ni
personnelle :

```bash
PYTHONPATH=src .venv/bin/python scripts/generate_monitoring_demo.py
PYTHONPATH=src .venv/bin/python scripts/import_render_logs.py --input data/monitoring/render_demo_export.jsonl
PYTHONPATH=src .venv/bin/python scripts/analyze_monitoring.py --reference data/monitoring/reference_events.jsonl
PYTHONPATH=src .venv/bin/streamlit run scripts/monitoring_dashboard.py
```

La référence `synthetic_demo` provoque volontairement une alerte PSI sur
`heures_prevues` et une alerte de catégorie nouvelle sur `modalite`. Elle
prouve le pipeline de monitoring, pas une dérive réelle. Le résultat Evidently
met également en évidence le décalage de `heures_prevues` et de `modalite`.
Les autres variables restent utiles comme témoins. Leur absence de signal sur
ce petit jeu ne prouve pas une stabilité en production. Une conclusion réelle
exige une référence stable et gouvernée issue du Projet6, puis un volume de
production représentatif. Voir [la preuve de persistance et les résultats de la
démo](docs/monitoring-demo-evidence.md).

### Référence locale provenant du Projet6

Si le dépôt Projet6 est disponible dans le dossier voisin, construire une
référence avec ses 248 dossiers de validation temporelle. Le script reproduit
les filtres et le découpage enregistrés dans les métadonnées, puis exporte
uniquement les six variables suivies, sans identifiants ni labels. Le fichier
privé est ignoré par Git :

```bash
PYTHONPATH=src .venv/bin/python scripts/build_project6_reference.py \
  --modeling-base ../Projet6/data/processed/dossiers_gain_modeling_base.parquet \
  --output output/private_monitoring/project6_holdout_reference.jsonl
```

Cette référence est distincte du scénario synthétique ci-dessus. Après import
d'un export **réel** de logs Render dans SQLite, lancer l'analyse avec
`--reference output/private_monitoring/project6_holdout_reference.jsonl` et
indiquer un `--output-dir` distinct pour ne pas écraser le rapport de démo.
Il faut au moins dix prédictions complètes et représentatives dans chaque jeu.
Voir [l'audit du modèle et des données](docs/model-data-audit.md) : le modèle
est reproductible, mais le seuil métier produit beaucoup d'alertes sur le
holdout et la référence d'entraînement serait biaisée par les valeurs manquantes.

Pour contrôler manuellement la persistance après fermeture du script d'import :

```bash
python - <<'PY'
import sqlite3
with sqlite3.connect('data/monitoring/monitoring.db') as db:
    print(db.execute('SELECT COUNT(*), MIN(timestamp), MAX(timestamp) FROM prediction_events').fetchone())
PY
```

La référence réelle est un JSONL dont chaque ligne contient `status: success`,
les six `features` suivies et `reference_source` indiquant son origine. Les
événements de production proviennent uniquement de SQLite après import Render.
Le dashboard est local, sur `http://localhost:8501`; il lit le dernier rapport
généré et la base SQLite. Relancer l'analyse après un nouvel import pour mettre
à jour les résultats Evidently.

Les scripts acceptent `--database`, `--reference` et `--output-dir` pour utiliser
d'autres chemins. Le dashboard lit les variables `MONITORING_DATABASE_PATH` et
`MONITORING_REPORT_PATH` si les artefacts sont stockés ailleurs. Cela permet
aussi de lancer la démonstration dans un répertoire temporaire quand les anciens
répertoires locaux ne sont pas modifiables.

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
