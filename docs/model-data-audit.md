# Audit du modèle et des données — 18 septembre 2026

## Périmètre et décision

L'audit a relu en lecture seule la base préparée et les artefacts du Projet6 local,
puis comparé le modèle servi par Projet8 aux prédictions de validation enregistrées.
**Le modèle n'a pas été remplacé : ses scores sont reproductibles.** La
relecture a en revanche révélé et corrigé un écart entre le contrat de l'API
et les données sur lesquelles ce modèle a été entraîné. Il faudrait de nouveaux
dossiers étiquetés et une validation temporelle indépendante pour mesurer un
gain réel avant de remplacer l'artefact du modèle.

## Vérifications reproductibles

| Contrôle | Résultat |
| --- | --- |
| Modèle et métadonnées Projet6 / Projet8 | Fichiers identiques octet par octet. |
| Population éligible, censure à 480 jours | 1 242 dossiers, dont 994 en entraînement et 248 en validation temporelle ; concorde avec les métadonnées. |
| Contrat d'entrée | 44 variables dans le même ordre que la base et le modèle. |
| Recalcul des 248 scores du holdout | Mêmes identifiants dans le même ordre ; différence maximale des probabilités : `0,0`. |
| Qualité de classement sur le holdout | ROC AUC `0,7764`, average precision `0,7741`, recalculées depuis les prédictions sauvegardées. |
| Étape intermédiaire, avant correction des zéros | 103 dossiers sur 248 acceptés après avoir corrigé les booléens et les valeurs null. |
| Contrat API après correction | 248 dossiers sur 248 acceptés ; différence maximale des scores API / Projet6 : `0,0`. |

### Correction du contrat d'entrée

Dans la base Projet6, cinq variables sont des **booléens**. L'API les recevait
comme chaînes (`"false"`), ce qui les plaçait dans une catégorie inconnue pour
le modèle. De plus, 17 variables peuvent être absentes : l'API rejetait
auparavant leurs valeurs `null`, alors que le pipeline du modèle contient des
imputations. Les 44 clés restent obligatoires, mais ces 17 valeurs peuvent
maintenant être `null`.

Enfin, `client_rang_dossier` et `montant_demande_eur` valent parfois zéro
dans le holdout ; ces zéros sont désormais acceptés. La correction a été
vérifiée dossier par dossier sur les 248 lignes de validation : toutes passent
la validation de l'API et produisent exactement les probabilités sauvegardées.
Le JSON de démonstration utilise aussi de vrais booléens.

La base d'entraînement contient encore quelques valeurs négatives historiques
sur `heures_prevues` (9 lignes), `montant_demande_eur` (18) et
`taux_horaire_demande_eur` (5). L'API continue de refuser ces valeurs
incohérentes. Leur traitement à la source doit être défini avant un prochain
réentraînement ; aucune ligne négative n'apparaît dans le holdout servi.

Le seuil métier `0,06` privilégie les faux négatifs, pénalisés cinq fois plus
que les faux positifs dans ce run. Sur les 248 dossiers de validation : 93 vrais
positifs, 153 faux positifs, 0 faux négatif et 2 vrais négatifs. Il signale donc
**246 dossiers sur 248**. Le coût défini pour ce run vaut `153`, contre `208`
au seuil `0,50`. Cette baisse du coût s'accompagne d'une charge d'alertes très
élevée : le drapeau doit être présenté comme une vigilance large, pas comme une
file de quelques dossiers prioritaires.

Le seuil a été choisi et évalué sur le même holdout dans le Projet6 : son coût
mesuré peut être optimiste. Un contrôle exploratoire séparant ce holdout en deux
moitiés chronologiques trouve, sur la seconde moitié, un coût de `71` au seuil
`0,06` contre `91` au seuil `0,30` choisi sur la première moitié. Cet effectif
reste trop petit pour fixer un nouveau seuil de production ; il confirme seulement
qu'un changement immédiat n'est pas étayé par ces données.

## Référence de monitoring issue du Projet6

Sur les 994 lignes d'entraînement, seules **115** ont les six variables de
monitoring complètes : `source_lead` manque sur 879 lignes. Une référence
construite en supprimant simplement les lignes incomplètes décrirait donc un
sous-groupe biaisé. Les **248 lignes du holdout temporel** possèdent toutes les
six variables et fournissent une référence récente, distincte de l'entraînement.

Le script [`build_project6_reference.py`](../scripts/build_project6_reference.py)
reproduit les filtres et le découpage du Projet6, vérifie les effectifs contre
les métadonnées, puis n'exporte que les six variables suivies, `status` et
`reference_source`. Il n'exporte ni identifiant, ni date individuelle, ni label,
ni score. Le fichier généré reste dans `output/private_monitoring/`, ignoré par
Git et accessible seulement à l'utilisateur local.

```bash
PYTHONPATH=src .venv/bin/python scripts/build_project6_reference.py \
  --modeling-base ../Projet6/data/processed/dossiers_gain_modeling_base.parquet \
  --output output/private_monitoring/project6_holdout_reference.jsonl
```

La référence réelle est prête **localement**. Elle ne doit être comparée qu'à
des événements de production Render réellement importés et en volume suffisant.
Le rapport Streamlit de démonstration actuel reste fondé sur deux jeux
synthétiques ; ses deux variables en drift ne décrivent pas la production.

## Travail restant pour une conclusion de production

1. Importer des événements Render représentatifs, avec provenance et période
   connues, dans la base SQLite locale.
2. Comparer ces événements à la référence Projet6 ci-dessus, contrôler les
   valeurs manquantes et réexaminer les alertes sur un échantillon plus grand.
3. Obtenir des labels ultérieurs avant toute décision de réentraînement ou de
   modification du seuil, puis mesurer séparément qualité et charge opérationnelle.
