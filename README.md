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

## Stack technique

| Brique | Role |
|---|---|
| Python | Langage principal |
| PM4Py | Extraction, decouverte du processus, conformance checking, analyse de performance |
| Scikit-Learn | Pipeline de features, split train/test |
| XGBoost | Classification (risque de retard) et regression (temps restant) |
| Streamlit | Dashboard interactif (6 vues) |
| Docker | Conteneurisation, un seul conteneur |

### Licences

- **pm4py** est sous licence **AGPL v3** depuis 2024 : un usage commercial non
  open-source necessite une licence payante (voir https://processintelligence.solutions/pm4py#licensing).
- Le dataset **BPI Challenge 2019** est public (CC BY 4.0, 4TU Research Data), utilise ici a
  des fins pedagogiques et de validation experimentale de la plateforme.

### Decision d'architecture

Un seul conteneur Streamlit + PM4Py + XGBoost (pas de backend API separe : usage en
analyse de lot, pas de temps reel ni multi-clients). Les modeles (`process_model.pnml`,
`xgboost_classifier.pkl`, `xgboost_regressor.pkl`) sont **entraines hors du conteneur**
puis montes en volume ; le conteneur ne fait que les charger pour servir le dashboard.

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

## Volet complementaire : ingestion d'un flux de donnees vivant (API)

Le dataset BPI Challenge 2019 est un jeu de recherche **fige** : il demontre la
profondeur d'analyse, mais pas la capacite de la plateforme a traiter des donnees qui
se renouvellent. Un second volet interroge donc une **API publique reellement vivante**,
celle des reclamations NYC 311 (Socrata), ou des centaines de tickets sont enregistres
chaque heure.

Le processus modelise - ouverture -> traitement -> cloture d'une reclamation - est
structurellement identique a un service client ou un support technique de PME. La seule
difference avec un deploiement en entreprise est la source : ici une API publique,
en interne le systeme de ticketing maison.

```bash
python -m src.live_source     # appel API -> log d'evenements (data/live/)
python -m src.live_analysis   # process mining sur ce log -> reports/live_process_analysis.md
```

Les resultats apparaissent dans l'onglet **Flux vivant (API)** du dashboard. Relancer
`src.live_source` recupere de nouveaux tickets : les chiffres de cet onglet evoluent a
chaque appel, contrairement aux cinq autres.

### Cle d'API

L'API repond sans authentification, mais avec un quota reduit. Un `app_token` Socrata
gratuit (https://data.cityofnewyork.us/profile/edit/developer_settings) leve cette
limite ; le placer dans un fichier `.env` a la racine (non versionne) :

```
SOCRATA_APP_TOKEN=xxxxxxxx
```

### Poste avec antivirus interceptant le HTTPS (Avast, etc.)

Certains antivirus (Avast notamment) inspectent le trafic HTTPS en generant une autorite
de certification locale et en re-signant chaque connexion. Si `python -m src.live_source`
echoue avec une erreur SSL, c'est le cas de figure : exporter le certificat racine de
l'antivirus (dans Avast : *Menu > Parametres > Confidentialite/Protection > Inspection SSL*
ou equivalent selon la version) et le placer a la racine du projet sous le nom
`avast-root.crt`. Ce fichier est propre a chaque machine et volontairement exclu du depot
(voir `.gitignore`) : personne d'autre n'a besoin du meme fichier, et il ne fonctionnerait
pas sur un autre poste de toute facon. Sans antivirus de ce type, cette etape ne se
declenche jamais - `build_session()` (`src/live_source.py`) ne l'utilise qu'en repli, apres
avoir constate que la connexion standard echoue.

### Fenetre de recuperation

`python -m src.live_source` recupere les tickets crees dans les 14 derniers jours
(`DEFAULT_WINDOW_DAYS`), plafonnes a 20 000 (`DEFAULT_FETCH_LIMIT`) - une fenetre
temporelle explicite plutot qu'un "top N" dont le volume reel depend du rythme de
creation de tickets le jour de l'appel. Contrairement a un filtre qui ne garderait que
les tickets deja clotures, les tickets encore ouverts restent inclus : c'est ce qui
permet au taux de cloture (`closure_rate`) de rester un KPI significatif plutot que
trivialement egal a 100%.

### Un resultat de qualite de donnees

Le champ `resolution_action_updated_date` de l'API est un horodatage de **derniere
modification**, pas une etape garantie du cycle de vie : sur un instantane verifie le
2026-09-02, 31% de ses valeurs precedaient la creation meme du ticket. `to_event_log()`
(`src/live_source.py`) ecarte desormais ces evenements plutot que de produire des
variantes incoherentes du type `Resolution Action Updated -> Service Request Created`.
Le voir survenir quelques secondes *apres* `closed_date` reste en revanche normal (memes
transaction de cloture cote NYC) et n'est pas filtre. C'est un resultat en soi - le
process mining rend visible un defaut de qualite de donnees qu'un tableau de bord agrege
classique masquerait entierement.

## Une plateforme generique, pas un script sur un dataset

Le coeur de l'analyse (`src/process_metrics.py`) ne connait ni BPI2019 ni NYC 311 :
il raisonne en "cas", "activite" et "horodatage". Un fichier YAML dans `config/`
fait le lien entre ces concepts et les colonnes reelles d'un log donne.

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
C'est exactement ce que fait `config/nyc311.yaml` : les deux processus, aux colonnes et
aux activites totalement differentes, sont analyses par les memes fonctions.

```bash
python -m src.performance_analysis                 # processus par defaut
python -m src.performance_analysis --config nyc311 # autre processus, meme code
```

### Tests

```bash
python -m pytest tests/ -q     # 36 tests
```

Les tests portent en priorite sur ce qui avait deja casse : la censure temporelle, la
fuite de donnees entre train et test, et la robustesse du comptage de variantes a
l'ordre des lignes. Ils tournent sur des logs miniatures construits a la main, dont la
reponse attendue est connue a l'avance - jamais sur BPI2019 ni sur l'API.

## Automatisation

Un orchestrateur enchaine les etapes a rejouer periodiquement et journalise chaque
execution dans `logs/refresh.log` :

```bash
python -m src.refresh                # flux API + analyse du flux (rapide)
python -m src.refresh --scope full   # + export Power BI (NYC), conformite, performance, KPI, export Power BI (BPI2019)
```

Planification quotidienne sous Windows :

```powershell
.\scripts\register_refresh_task.ps1
```

**Frequence assumee : une fois par jour.** L'API NYC 311 publie ses donnees avec environ
48 h de decalage (verifie a l'execution) : rafraichir plus souvent ne rapporterait
aucune donnee nouvelle tout en consommant du quota. Le flux se renouvelle donc a un
rythme journalier, pas en temps reel.

L'entrainement des modeles ML n'est volontairement pas automatise : il est couteux et
n'a pas a etre refait a chaque rafraichissement. Le relancer manuellement lors d'une
reevaluation periodique - c'est aussi l'occasion de verifier que le seuil de retard et
la fenetre de censure restent pertinents sur les donnees recentes.

## Structure

```
process-mining-pme-v2/
├── data/
│   ├── raw/
│   │   └── bpi_challenge_2019.xes
│   ├── processed/
│   │   ├── event_log_raw.parquet
│   │   └── event_log_clean.parquet
│   ├── live/                    # Instantanes du flux API (regeneres a chaque appel)
│   └── legacy_bpi2012/          # dataset ecarte apres audit (conserve pour reference)
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
│   ├── process_analysis.md      # KPI + recommandations metier (BPI2019)
│   └── live_process_analysis.md # KPI + variantes du flux vivant (NYC 311)
├── config/                      # Un fichier YAML = un processus analysable
│   ├── bpi2019.yaml
│   └── nyc311.yaml
├── tests/                       # 36 tests pytest
├── scripts/
│   └── register_refresh_task.ps1  # Planification quotidienne (Windows)
├── logs/                        # Journal des rafraichissements
├── .streamlit/
│   └── config.toml              # Theme du dashboard
├── src/
│   ├── config.py                # Chargement de la configuration d'un processus
│   ├── process_metrics.py       # Metriques process mining, independantes du dataset
│   ├── refresh.py               # Orchestrateur des etapes periodiques
│   ├── audit_dataset.py         # Audit generique d'un event log XES
│   ├── extract_log.py           # Phase 1 - XES -> DataFrame
│   ├── preprocess.py            # Phase 1 - nettoyage + stats descriptives
│   ├── discover_process.py      # Phase 2 - Inductive Miner -> .pnml
│   ├── conformance_check.py     # Phase 3 - fitness / precision / cas deviants
│   ├── performance_analysis.py  # Phase 3 - goulots, rework, charge ressources
│   ├── business_analysis.py     # Phase 3 - KPI + recommandations metier
│   ├── train_model.py           # Phase 4 - feature engineering + XGBoost x2
│   ├── evaluate_model.py        # Phase 4 - metriques des 2 modeles
│   ├── export_powerbi.py        # Phase 5 - export CSV pour Power BI (BPI2019)
│   ├── export_powerbi_live.py   # Phase 5 - export CSV pour Power BI (NYC 311)
│   ├── live_source.py           # Volet API - ingestion du flux NYC 311
│   └── live_analysis.py         # Volet API - process mining sur le flux
├── powerbi_export/              # Tables CSV + README d'import Power BI (BPI2019)
├── powerbi_export_live/         # Tables CSV pour Power BI (NYC 311)
├── app.py                       # Phase 5 - dashboard Streamlit (6 vues)
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

streamlit run app.py
```

Export des donnees vers Power BI (alternative au dashboard Streamlit) :

```bash
python -m src.export_powerbi
```

Puis, dans Power BI Desktop : *Obtenir les donnees > Texte/CSV* pour chaque fichier de
`powerbi_export/`. Le detail des tables, des relations a creer et des visuels suggeres
est dans `powerbi_export/README.md`.

Meme export pour le flux vivant NYC 311 (necessite d'avoir execute `src.live_source`
au moins une fois) :

```bash
python -m src.export_powerbi_live
```

Produit `powerbi_export_live/` : `fact_cases.csv`, `dim_bottlenecks.csv`, `dim_rework.csv`,
`dim_resources.csv`, `dim_variants.csv`, `kpi_overview.csv`. Contrairement a
`export_powerbi.py` (specifique a BPI2019 : attributs Purchase-to-Pay, predictions ML),
ce script appelle directement `src/process_metrics.py` avec `config/nyc311.yaml` - aucune
metrique n'est reimplementee, seule la configuration change.

Audit prealable d'un dataset (optionnel, deja execute pour BPI2012 et BPI2019) :

```bash
python -m src.audit_dataset --xes data/raw/bpi_challenge_2019.xes --name bpi2019
```

## Utilisation (Docker)

Les etapes ci-dessus (jusqu'a `evaluate_model.py`) doivent avoir ete executees au moins
une fois en local pour generer `data/` et `models/`, ensuite :

```bash
docker-compose up --build
```

Dashboard accessible sur http://localhost:8501.

## Dashboard (6 vues)

1. **Vue d'ensemble** : KPI principaux, distribution des durees, activites frequentes.
2. **Processus** : modele decouvert (Inductive Miner), top variantes.
3. **Conformite & Performance** : fitness/precision, cas deviants, goulots d'etranglement,
   rework, charge par ressource.
4. **Prediction** : risque de retard et temps restant estime pour un cas donne.
5. **Recommandations** : problemes detectes, impact chiffre, recommandations d'amelioration.
6. **Flux vivant (API)** : meme chaine d'analyse appliquee a une source de donnees
   qui se renouvelle reellement (API publique NYC 311).

## Dataset

`BPI_Challenge_2019.xes` (van Dongen, B.F. (Boudewijn), 4TU.ResearchData, CC BY 4.0).
Le fichier `.xes` n'est pas commite dans ce depot (voir `.gitignore`) ; le telecharger
depuis 4TU Research Data et le placer dans `data/raw/bpi_challenge_2019.xes`.
