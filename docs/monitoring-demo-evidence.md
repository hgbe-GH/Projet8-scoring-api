# Preuve de monitoring local — scénario synthétique

Le 17 septembre 2026, les scripts de démonstration ont généré 30 événements de
référence et 30 événements de production simulés. L'import a inséré 30 lignes
dans SQLite. Le script d'analyse a ensuite ouvert une nouvelle connexion à la
base, relu les événements et produit les rapports local et Evidently. Les fichiers
SQLite et les données événementielles restent hors Git.

## Preuve de stockage

Résultat de la requête agrégée sur `prediction_events` après l'import :

| Mesure | Valeur |
| --- | --- |
| Lignes persistées | 30 |
| Prédictions réussies | 30 |
| Premier timestamp | `2026-09-10T12:00:00+00:00` |
| Dernier timestamp | `2026-09-10T12:29:00+00:00` |
| Dernier `event_id` | `production-29` |

Une seconde exécution de l'import du même export a affiché
`Imported 0 new monitoring event(s).`, grâce à la clé primaire `event_id`.
La requête et les commandes de reproduction sont
dans le [README](../README.md#données-et-monitoring).

## Résultats principaux

| Mesure | Résultat | Lecture |
| --- | --- | --- |
| Appels / erreurs | 30 / 0 | Aucun échec dans la simulation. |
| Latence p95 | 25 ms | Valeur fixe générée pour la démonstration. |
| Evidently | 2 variables en drift sur 6 | `heures_prevues` et `modalite`. |
| `heures_prevues` | PSI 11,77 ; test K-S p ≈ 1,69 × 10⁻¹⁷ | Décalage volontaire des valeurs 15–35 vers 60–90. |
| `modalite` | 50 % de catégories nouvelles ; Jensen–Shannon ≈ 0,589 | `hybride` apparaît seulement en production. |

Les PSI de `montant_demande_eur` et `pct_financement_demande` dépassent aussi
0,20, tandis que les tests Evidently correspondants ne détectent pas de drift.
Les petits effectifs et les dix tranches du PSI rendent cette mesure instable ;
ces alertes demandent un examen sur un échantillon plus grand. `source_lead` et
`type_financement` ne montrent pas de signal dans ce jeu. Toutes ces données
sont synthétiques : elles vérifient le fonctionnement du pipeline, sans établir
une dérive réelle de la production Render.
