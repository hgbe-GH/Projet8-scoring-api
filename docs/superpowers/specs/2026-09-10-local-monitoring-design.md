# Monitoring local — conception

## Objectif

Conserver, hors du disque éphémère de Render, les événements de production de
l'API de scoring. Permettre une analyse locale et reproductible de la fiabilité
opérationnelle et d'une première dérive des données.

## Périmètre

Cette étape couvre la collecte de chaque appel `POST /predict`, le stockage
SQLite local, l'import des événements exportés depuis Render et l'analyse
automatique. Elle ne crée ni base cloud, ni secret, ni tableau de bord distant.

## Architecture retenue

```text
POST /predict sur Render
  -> événement JSON structuré dans la sortie standard Render
  -> export local des logs Render (JSONL)
  -> script d'import local et idempotent
  -> data/monitoring/monitoring.db (SQLite, ignoré par Git)
  -> script d'analyse
  -> reports/monitoring/latest_report.{json,md}
```

L'API conserve également le fichier JSONL local existant pour faciliter les
tests et l'exécution hors Render. La sortie standard devient la source exportée
depuis Render ; SQLite devient la source locale durable d'analyse.

## Contrat d'événement

Chaque événement porte `schema_version`, `event_id` (UUID), `timestamp`,
`event_type`, `status`, `http_status`, `latency_ms` et `model_version`.

Pour une prédiction réussie, l'événement ajoute `features`, `risk_score` et
`risk_flag`. Les `features` sont les entrées déjà validées par Pydantic. Pour
une erreur de validation (`422`) ou une erreur interne (`500`), l'événement ne
contient pas de corps de requête ni de détail technique : seulement le statut,
le code HTTP et la latence. Cette séparation limite la conservation de données
non validées ou de messages internes.

La latence est mesurée sur l'intégralité du traitement HTTP de `/predict`,
validation comprise. La génération d'un log ne doit jamais transformer une
réponse de prédiction correcte en erreur.

## Stockage local

`data/monitoring/monitoring.db` contient une table `prediction_events` avec
une clé primaire `event_id`. L'import est idempotent : relancer le script sur
le même export ne crée aucun doublon. Les exports bruts et la base SQLite sont
ignorés par Git. Seuls le schéma, les scripts et les données de démonstration
non sensibles sont versionnés.

L'import accepte un fichier JSONL issu de Render. Il sélectionne uniquement
les lignes de sortie standard dont le message commence par le marqueur stable
`ML_EVENT `. Les autres messages système Render sont ignorés.

## Référence et drift

Les données sources du Projet 6 ne sont pas présentes dans ce dépôt. Une
référence synthétique, générée de manière reproductible et clairement étiquetée
`synthetic_demo`, est donc utilisée exclusivement pour démontrer le pipeline.
Elle ne permet pas de conclure sur la dérive réelle du modèle.

L'analyse compare cette référence avec les événements de production importés
ou avec un jeu de production simulé. Elle calcule :

- PSI sur `heures_prevues`, `montant_demande_eur` et
  `pct_financement_demande` ; un PSI supérieur ou égal à `0.20` est signalé ;
- taux de catégories absentes de la référence pour `modalite`, `source_lead`
  et `type_financement` ; un taux supérieur ou égal à `5 %` est signalé ;
- volume d'appels, taux d'erreur, latence médiane et latence p95 ; une latence
  p95 supérieure à `1 000 ms` ou un taux d'erreur supérieur à `5 %` est
  signalé.

Une absence de données suffisantes n'est jamais interprétée comme « pas de
drift » : le rapport indique `insufficient_data` avec la raison.

## Scripts et résultats attendus

- `scripts/import_render_logs.py` : importe un fichier JSONL Render vers
  SQLite ;
- `scripts/generate_monitoring_demo.py` : produit une référence et un export
  simulé non sensibles pour une démonstration reproductible ;
- `scripts/analyze_monitoring.py` : lit SQLite, calcule les métriques et écrit
  un rapport JSON et Markdown ;
- `reports/monitoring/latest_report.{json,md}` : artefacts générés, ignorés
  par Git sauf un exemple statique éventuel sous `docs/`.

## Tests et documentation

Les tests doivent vérifier le contrat d'événement, l'absence de détail sensible
pour les erreurs, l'import sans doublon, le calcul d'un PSI détectant une
dérive manifeste, la détection de catégorie inconnue et le rapport des métriques
opérationnelles. Le README doit contenir les commandes d'export, d'import,
démonstration et analyse, ainsi que le schéma du flux et les limites RGPD.

## Limites et sécurité

Les entrées peuvent contenir des données métier sensibles. Le PoC impose donc
un stockage local sous contrôle de l'utilisateur, sans publication des exports
ou de la base. En production, une analyse RGPD, une politique de rétention,
un chiffrement et une solution de stockage gérée seraient nécessaires. Les
logs Render ne sont pas considérés comme une archive durable ; ils ne servent
que de relais vers l'export local.
