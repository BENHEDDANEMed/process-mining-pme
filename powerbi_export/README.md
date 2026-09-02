# Import Power BI

Genere par `python -m src.export_powerbi`. Dans Power BI Desktop :
**Obtenir les donnees > Dossier** > pointer sur ce dossier `powerbi_export/` > **Combiner et transformer**
(ou importer chaque CSV individuellement via **Texte/CSV**).

## Tables

| Fichier | Grain | Role |
|---|---|---|
| `fact_cases.csv` | 1 ligne / cas (248 899) | Table de faits principale : duree, attributs metier, conformite |
| `fact_case_predictions.csv` | 1 ligne / cas echantillonne (~30 000, snapshot a 50% du cas) | Prediction ML (risque de retard, temps restant) vs realite |
| `dim_conformance.csv` | 1 ligne / cas | Detail token-based replay (deja inclus dans fact_cases, garde pour le detail) |
| `dim_bottlenecks.csv` | 1 ligne / transition d'activites | Temps d'attente moyen/median entre activites |
| `dim_rework.csv` | 1 ligne / activite | Taux de cas ou l'activite est repetee |
| `dim_resources.csv` | 1 ligne / ressource | Charge et duree moyenne des cas traites |
| `dim_variants.csv` | 1 ligne / variante | Frequence de chaque sequence d'activites |
| `kpi_overview.csv` | 1 ligne | KPI globaux (a utiliser en cartes/cards) |
| `kpi_recommendations.csv` | 1 ligne / recommandation | Recommandations metier generees |

## Relations a creer dans le modele Power BI

- `fact_cases[case_id]` (1) -> `fact_case_predictions[case_id]` (plusieurs, en pratique 1:1 car un seul
  snapshot par cas dans cet export) : cardinalite **un-vers-un** ou **un-vers-plusieurs** selon reglages.
- `fact_case_predictions[case_id]` -> `fact_cases[case_id]` : desactiver le filtrage croise inverse si besoin
  d'analyser les predictions independamment.
- `dim_conformance` a le meme grain que `fact_cases` (case_id) : peut etre fusionne ou laisse en table
  separee reliee sur `case_id`.
- `dim_bottlenecks`, `dim_rework`, `dim_resources`, `dim_variants`, `kpi_overview`, `kpi_recommendations`
  n'ont pas de cle commune avec `fact_cases` (ce sont des agregats deja calcules) : les utiliser en
  **tables independantes** pour des visuels dedies (pas de relation necessaire), ou les relier via une
  colonne d'activite si vous voulez croiser avec le detail des cas.

## Suggestions de visuels (mapping avec les 5 vues du dashboard Streamlit existant)

1. **Vue d'ensemble** : cartes depuis `kpi_overview`, histogramme de `fact_cases[duration_days]`,
   barres `dim_variants` (top 15 par `n_cases`).
2. **Processus** : table `dim_variants` triee par `n_cases` decroissant.
3. **Conformite & Performance** : histogramme `fact_cases[trace_fitness]`, barres `dim_bottlenecks`
   (`avg_wait_hours` par `from_activity`/`to_activity`), tables `dim_rework` et `dim_resources`.
4. **Prediction** : nuage de points `fact_case_predictions[actual_remaining_hours]` vs
   `predicted_remaining_hours`, matrice de confusion `actual_label` vs `predicted_label`.
5. **Recommandations** : table `kpi_recommendations`.

## Regenerer l'export

Apres tout changement des donnees ou reentrainement des modeles :

```bash
python -m src.export_powerbi
```
