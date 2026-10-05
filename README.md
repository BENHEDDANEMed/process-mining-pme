# Process Mining PME

Plateforme de Process Mining adaptee aux besoins des PME, **validee experimentalement
sur un dataset public** : BPI Challenge 2019 (van Dongen, 4TU.ResearchData), un
processus **Purchase-to-Pay** (demande d'achat -> commande -> reception -> facture ->
paiement) d'une multinationale de la peinture/du revetement, ~249 000 cas et
~1,46 M d'evenements apres nettoyage.

Ce choix de dataset a fait l'objet d'un audit comparatif avec BPI Challenge 2012
(voir `reports/dataset_audit_bpi2012.md` et `reports/dataset_audit_bpi2019.md`) :
BPI2019 offre des attributs metier bien plus riches (fournisseur, categorie d'achat,
type de document...) et un scenario Purchase-to-Pay directement transposable a une PME.

Permet de :

1. Decouvrir automatiquement le vrai deroulement du processus a partir des logs (Inductive Miner).
2. Verifier si les cas reels respectent le modele decouvert (fitness / precision, token-based replay).
3. Mesurer la performance du processus : goulots d'etranglement, temps d'attente entre
   activites, taux de rework, charge par ressource.
4. Traduire ces mesures en KPI et recommandations metier exploitables (Business Analysis).
5. Predire, pour un dossier en cours : son risque de retard et le temps restant avant
   cloture, via deux modeles XGBoost.
6. Resumer toutes ces analyses en un **Process Health Score** unique (0-100), lisible
   sans connaissance du process mining.

## Stack technique

| Brique | Role |
|---|---|
| Python | Langage principal |
| PM4Py | Extraction, decouverte du processus, conformance checking, analyse de performance |
| Scikit-Learn | Pipeline de features, split train/test |
| XGBoost | Classification (risque de retard) et regression (temps restant) |
| FastAPI | API servant les KPI/predictions au dashboard |
| React (Vite) | Dashboard interactif (5 vues) |
| Docker | Conteneurisation, un seul conteneur (build multi-etapes) |

### Licences

- **pm4py** est sous licence **AGPL v3** depuis 2024 : un usage commercial non
  open-source necessite une licence payante (voir https://processintelligence.solutions/pm4py#licensing).
- Le dataset **BPI Challenge 2019** est public (CC BY 4.0, 4TU Research Data), utilise ici a
  des fins pedagogiques et de validation experimentale de la plateforme.

### Decision d'architecture

Un seul conteneur : API FastAPI + dashboard React buildé, servis par le meme
processus (pas de CORS, pas de service separe). Les modeles (`process_model.pnml`,
`xgboost_classifier.pkl`, `xgboost_regressor.pkl`) sont **entraines hors du conteneur**
puis montes en volume ; le conteneur ne fait que les charger pour servir l'API.

### Positionnement

Le dataset public BPI2019 sert a demontrer et valider la plateforme, pas a la presenter
comme issue directement d'une PME. Une PME utilisant cette plateforme sur ses propres
donnees pourrait :

1. importer ses donnees d'evenements ;
2. reconstruire automatiquement ses processus ;
3. comprendre leur fonctionnement reel ;
4. identifier les ecarts et les inefficacites ;
5. mesurer les performances ;
6. detecter les situations problematiques ;
7. predire certains risques ;
8. obtenir des recommandations exploitables.

## Machine Learning

Deux modeles XGBoost entraines sur des prefixes de cas (l'etat d'un dossier a chaque
etape de son deroulement) :

| Modele | Cible | Resultat sur le jeu de test |
|---|---|---|
| Classifieur | Risque de retard (duree totale > 108 j, soit le quartile le plus lent) | ROC AUC **0.878**, accuracy **83.6%**, rappel sur les cas en retard **71.8%** |
| Regresseur | Temps restant avant cloture | MAE **17.4 jours**, soit **37.9%** de mieux qu'une prediction naive par la mediane |

### Trois corrections determinantes

La premiere version de ces modeles plafonnait a 48.8% d'accuracy, soit *sous* le niveau
du hasard sur un probleme binaire. Le diagnostic a revele un biais de donnees, pas un
manque de puissance du modele :

1. **Censure temporelle.** Le log s'arrete mi-janvier 2019. Les cas demarres juste avant
   cette date etaient tronques : leur duree observee, artificiellement courte, les faisait
   etiqueter "a l'heure" a tort. Le jeu d'entrainement contenait ainsi 59% de cas en
   retard contre 14% dans le jeu de test - un ecart de distribution qui condamnait le
   modele. Sont desormais retenus les seuls cas (a) reellement clotures, c'est-a-dire
   se terminant sur une activite terminale (`Clear Invoice`, `Delete Purchase Order Item`),
   et (b) demarres au moins 150 jours avant la fin du log. Train et test affichent
   maintenant des taux de retard comparables (29.2% contre 27.0%).

2. **Features.** Le modele ne disposait que de l'activite courante, du rang de l'evenement,
   du temps ecoule et du montant. S'y ajoutent l'historique du prefixe (activites deja
   realisees sous forme d'indicateurs, nombre d'activites distinctes, rework, delai depuis
   le dernier evenement, rythme moyen, plus longue pause) et les attributs metier du
   dossier (societe, categorie d'achat, type d'article, source, verification sur reception).
   Total : 31 features contre 7.

3. **Definition du retard.** Le seuil etait calcule sur l'ensemble des donnees - une fuite
   d'information du test vers l'entrainement - et fixe a la mediane. Il est desormais
   appris sur le seul jeu d'entrainement et place au 3e quartile : "en retard" designe le
   quart des dossiers les plus lents, une cible plus actionnable pour une PME que
   "plus lent que la moitie". Le desequilibre de classes qui en resulte est compense par
   `scale_pos_weight`.

L'evaluation rapporte le ROC AUC et le rappel sur la classe en retard en plus de
l'accuracy : sur un jeu a 73% de cas a l'heure, un modele repondant toujours "a l'heure"
atteindrait 73% d'accuracy sans detecter le moindre retard.

## Une plateforme generique, pas un script sur un dataset

Le coeur de l'analyse (`src/process_metrics.py`) ne connait pas les colonnes de
BPI2019 en dur : il raisonne en "cas", "activite" et "horodatage". Un fichier
YAML dans `config/` fait le lien entre ces concepts et les colonnes reelles
d'un log donne.

```yaml
# config/bpi2019.yaml (extrait)
columns:
  case_id: "case:concept:name"
  activity: "concept:name"
  timestamp: "time:timestamp"
terminal_activities:
  - "Clear Invoice"
  - "Delete Purchase Order Item"
```

Consequence pour une PME : brancher un nouveau processus - tickets support, commandes,
dossiers RH - se fait en ecrivant une dizaine de lignes de YAML, **sans toucher au code**.
La plateforme est validee ici sur un seul processus (BPI2019), mais aucune fonction
d'analyse ne depend de son schema de colonnes particulier.

```bash
python -m src.performance_analysis   # processus par defaut (bpi2019)
```

### Tests

```bash
python -m pytest tests/ -q     # 76 tests
```

Les tests portent en priorite sur ce qui avait deja casse : la censure temporelle, la
fuite de donnees entre train et test, et la robustesse du comptage de variantes a
l'ordre des lignes. Ils tournent sur des logs miniatures construits a la main, dont la
reponse attendue est connue a l'avance - jamais sur BPI2019 directement.

## Regeneration des analyses

Un script enchaine conformite, performance, KPI metier et export Power BI en une
commande, pratique apres une modification du journal nettoye ou de la configuration :

```bash
python -m src.refresh
```

L'entrainement des modeles ML n'est volontairement pas inclus : il est couteux et
n'a pas a etre refait a chaque regeneration. Le relancer manuellement
(`python -m src.train_model`) lors d'une reevaluation periodique.

## Process Health Score

Toutes les analyses precedentes se resument en **un score unique de 0 a 100** et un
statut (EXCELLENT / GOOD / WARNING / CRITICAL), affiche en tete de la vue d'ensemble.
C'est une couche de **synthese**, pas de calcul : `src/process_health.py` relit les KPI
deja produits, il n'en recalcule aucun.

```bash
python -m src.process_health                    # processus par defaut
```

| Dimension | Mesure | Poids |
|---|---|---|
| Performance | rapport p90 / mediane des durees (regularite) | 25% |
| Conformance | taux de deviation au modele decouvert | 25% |
| Risque de retard | part des cas signales par le classifieur | 20% |
| Rework | taux de rework moyen | 15% |
| Charge ressources | part des evenements de la ressource la plus chargee | 15% |

**Des metriques sans echelle.** Un futur processus branche via son propre YAML pourrait
avoir des durees de cas sans rapport avec celles de BPI2019 : aucun seuil en heures ne
peut donc servir tous les processus. Chaque dimension est un *ratio*, ce qui rend le
score comparable d'un processus a l'autre.

**Dimensions manquantes.** Une dimension dont le KPI source est absent est ecartee -
jamais remplacee par une valeur inventee - et les poids restants sont renormalises a 1.
Un processus sans conformance checking ni modele de prediction verrait par exemple son
score porter sur les trois dimensions restantes, avec leurs poids ramenes a 1. Le chemin
des predictions vient du YAML (`artifacts.predictions`) et non d'une constante, pour
qu'un processus sans modele n'herite pas des predictions d'un autre dataset.

Les poids et les seuils sont configurables par processus dans `config/*.yaml`. Le detail
complet (normalisation, justification des poids, limites) est documente dans le rapport de
stage associe a ce projet, non inclus dans ce depot.

**Limite assumee** : le rapport p90/mediane mesure la *regularite* des durees, pas la
vitesse absolue - un processus uniformement lent mais previsible obtient un bon score
sur cette dimension. Juger la vitesse absolue exigerait un objectif de delai (SLA) que
la plateforme ne connait pas, et l'inventer reviendrait a fabriquer une valeur.

## Structure

```
process-mining-pme-v2/
├── data/
│   ├── raw/
│   │   └── bpi_challenge_2019.xes
│   └── processed/
│       ├── event_log_raw.parquet
│       └── event_log_clean.parquet
├── models/
│   ├── process_model.pnml
│   ├── conformance_report.csv
│   ├── performance_transitions.csv
│   ├── performance_rework.csv
│   ├── performance_resources.csv
│   ├── kpi_summary.json
│   ├── prefix_dataset.parquet
│   ├── xgboost_classifier.pkl
│   └── xgboost_regressor.pkl
├── reports/
│   ├── dataset_audit_bpi2012.md
│   ├── dataset_audit_bpi2019.md
│   └── process_analysis.md      # KPI + recommandations metier (BPI2019)
├── config/                      # Un fichier YAML = un processus analysable
│   └── bpi2019.yaml
├── tests/                       # 76 tests pytest
├── logs/                        # Journal des regenerations
├── backend/
│   └── api.py                   # API FastAPI (sert le dashboard React + KPI/predictions)
├── frontend/                    # Dashboard React (Vite + Tailwind + Recharts)
│   └── src/
│       ├── views/                # Vue d'ensemble, Processus, Conformite, Prediction, Recommandations
│       └── components/           # Card, StatCard, HBarChart, Histogram, Table...
├── src/
│   ├── config.py                # Chargement de la configuration d'un processus
│   ├── process_metrics.py       # Metriques process mining, independantes du dataset
│   ├── process_health.py        # Process Health Score (synthese des KPI existants)
│   ├── refresh.py               # Regenere conformite/performance/KPI/export en une commande
│   ├── audit_dataset.py         # Audit generique d'un event log XES
│   ├── extract_log.py           # Phase 1 - XES -> DataFrame
│   ├── preprocess.py            # Phase 1 - nettoyage + stats descriptives
│   ├── discover_process.py      # Phase 2 - Inductive Miner -> .pnml
│   ├── conformance_check.py     # Phase 3 - fitness / precision / cas deviants
│   ├── performance_analysis.py  # Phase 3 - goulots, rework, charge ressources
│   ├── business_analysis.py     # Phase 3 - KPI + recommandations metier
│   ├── train_model.py           # Phase 4 - feature engineering + XGBoost x2
│   ├── evaluate_model.py        # Phase 4 - metriques des 2 modeles
│   └── export_powerbi.py        # Phase 5 - export CSV pour Power BI
├── powerbi_export/              # Tables CSV + README d'import Power BI
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

## Utilisation (hors Docker)

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt

python -m src.extract_log
python -m src.preprocess
python -m src.discover_process
python -m src.conformance_check
python -m src.performance_analysis
python -m src.business_analysis
python -m src.train_model
python -m src.evaluate_model

# Dashboard : build le frontend une fois, puis lance l'API qui le sert
cd frontend && npm install && npm run build && cd ..
uvicorn backend.api:app --port 8000
```

Dashboard accessible sur http://localhost:8000.

En developpement, `cd frontend && npm run dev` lance un serveur Vite a chaud sur
http://localhost:5173, avec un proxy vers `uvicorn backend.api:app --port 8000`
pour les appels `/api/*` (voir `frontend/vite.config.js`).

Export des donnees vers Power BI (alternative au dashboard) :

```bash
python -m src.export_powerbi
```

Puis, dans Power BI Desktop : *Obtenir les donnees > Texte/CSV* pour chaque fichier de
`powerbi_export/`. Le detail des tables, des relations a creer et des visuels suggeres
est dans `powerbi_export/README.md`.

Audit prealable d'un dataset (optionnel, deja execute pour BPI2012 et BPI2019) :

```bash
python -m src.audit_dataset --xes data/raw/bpi_challenge_2019.xes --name bpi2019
```

## Utilisation (Docker)

```bash
docker-compose up --build
```

Dashboard accessible sur http://localhost:8000.

Le conteneur ne fait que *charger* des artefacts deja calcules (`models/`, `data/processed/`),
il ne les entraine pas : l'entrainement est une operation ponctuelle et couteuse, volontairement
laissee hors du conteneur.

- **Si ces artefacts sont fournis** (cas d'une livraison packagee) : la commande ci-dessus
  suffit, rien d'autre a executer.
- **Si le depot a ete clone sans eux** (ils sont exclus par `.gitignore` car volumineux) :
  executer d'abord le pipeline local decrit plus haut, jusqu'a `src.evaluate_model`.

## Dashboard (6 onglets)

1. **Vue d'ensemble** : Process Health Score, KPI principaux, distribution des durees,
   activites frequentes.
2. **Processus > Decouverte** : modele decouvert (Inductive Miner), top variantes.
3. **Processus > Variantes** : table des 20 variantes les plus frequentes (frequence, duree,
   rework, conformite), detail d'une variante et lien vers les cas concernes.
4. **Conformite & Performance** : fitness, cas deviants, goulots d'etranglement,
   rework, charge par ressource.
5. **Prediction > Cas courant** : risque de retard et temps restant estime pour un cas et une
   etape donnes, avec explication SHAP de chaque facteur et analyse des causes probables.
6. **Prediction > Monitoring** : repartition du portefeuille par niveau de risque et
   trajectoire du risque d'un cas a travers ses etapes.
7. **Explorateur de cas** : recherche d'un dossier precis, detail et chronologie des evenements.
8. **Recommandations** : problemes detectes, impact chiffre, recommandations d'amelioration.

## Dataset

`BPI_Challenge_2019.xes` (van Dongen, B.F. (Boudewijn), 4TU.ResearchData, CC BY 4.0).
Le fichier `.xes` n'est pas commite dans ce depot (voir `.gitignore`) ; le telecharger
depuis 4TU Research Data et le placer dans `data/raw/bpi_challenge_2019.xes`.
