# Documentation Complète du Projet : Process Mining PME

> **Plateforme de Process Mining adaptée aux besoins des PME**, validée expérimentalement sur un dataset public d'envergure industrielle (**BPI Challenge 2019** – Purchase-to-Pay) et connectée à un flux de données en temps réel (**API publique NYC 311**).

---

## Sommaire

1. [Vue d'Ensemble & Objectifs](#1-vue-densemble--objectifs)
2. [Stack Technique & Licences](#2-stack-technique--licences)
3. [Architecture Globale & Philosophie de Conception](#3-architecture-globale--philosophie-de-conception)
4. [Arborescence Détaillée du Répertoire](#4-arborescence-détaillée-du-répertoire)
5. [Pipelines de Données & Étapes de Traitement](#5-pipelines-de-données--étapes-de-traitement)
   - [5.1 Pipeline Principal : Traitement Batch (BPI Challenge 2019)](#51-pipeline-principal--traitement-batch-bpi-challenge-2019)
   - [5.2 Pipeline Machine Learning Prédictif](#52-pipeline-machine-learning-prédictif)
   - [5.3 Pipeline Flux Vivant (API NYC 311)](#53-pipeline-flux-vivant-api-nyc-311)
   - [5.4 Pipeline d'Automatisation & Orchestration](#54-pipeline-dautomatisation--orchestration)
   - [5.5 Pipeline d'Export & Modélisation Power BI](#55-pipeline-dexport--modélisation-power-bi)
6. [Détail des Modules Python (`src/`)](#6-détail-des-modules-python-src)
7. [Couche de Restitution & Dashboard Streamlit](#7-couche-de-restitution--dashboard-streamlit)
8. [Process Health Score](#8-process-health-score)
9. [Décisions Techniques, Biais Résolus & Bonnes Pratiques](#9-décisions-techniques-biais-résolus--bonnes-pratiques)
10. [Guide d'Exécution & Déploiement](#10-guide-dexécution--déploiement)
11. [Stratégie de Test & Validation](#11-stratégie-de-test--validation)

---

## 1. Vue d'Ensemble & Objectifs

### 1.1 Problématique Métier
Les PME disposent rarement d'équipes de data science dédiées ou de budgets pour acquérir des suites propriétaires de Process Mining (comme Celonis ou Signavio). Pourtant, elles subissent des inefficacités opérationnelles majeures :
- Goulots d'étranglement invisibles dans les flux de traitement.
- Retards récurrents de livraison ou de paiement.
- Taux élevé de retouche (*rework*) sur les commandes ou factures.
- Déviations non détectées par rapport aux procédures établies.

### 1.2 Objectif de la Plateforme
Cette solution fournit une infrastructure modulaire, reproductible et légère capable de :
1. **Reconstruire automatiquement les processus réels** à partir des journaux d'événements bruts (*Inductive Miner*).
2. **Vérifier la conformité** (*Conformance Checking*) entre le modèle théorique/découvert et la réalité terrain via le rejeu de jetons (*Token-Based Replay*).
3. **Quantifier la performance** : détection fine des goulots d'étranglement, calcul des délais d'attente, identification des boucles de rework et charge par ressource.
4. **Prédire le comportement futur des dossiers en cours** : évaluation du risque de retard et estimation du temps résiduel avant clôture via des algorithmes de gradient boosting (**XGBoost**).
5. **Générer des recommandations actionnables** pour les gestionnaires métier.
6. **Démontrer la connectivité temps réel** sur des flux d'événements continus (ticketing/support client).

---

## 2. Stack Technique & Licences

| Composant | Technologie / Librairie | Version | Rôle & Justification |
|---|---|---|---|
| **Langage** | Python | 3.13 | Socle d'exécution unifié pour l'ingénierie et l'IA. |
| **Process Mining** | PM4Py | 2.7.23.3 | Découverte de réseaux de Petri, conformance checking, token replay. |
| **Data Engineering** | Pandas | 3.0.5 | Manipulation vectorisée de DataFrames et persistance Parquet/CSV. |
| **Machine Learning** | Scikit-Learn | 1.9.0 | Préparation des pipelines, encodage et imputation. |
| **Modèles Prédictifs** | XGBoost | 3.0.5 | Classification binaire (retard) et régression (durée résiduelle). |
| **Dashboarding** | Streamlit | 1.61.1 | Interface web interactive multi-vues. |
| **Visualisation** | Plotly / Graphviz | 6.9.0 / 0.21 | Graphiques interactifs et rendu vectoriel des réseaux de Petri. |
| **Réseau / Flux** | Requests, PyYAML, Dotenv | Standard | Consommation d'API REST (Socrata), configuration YAML, variables d'environnement. |
| **Qualité & Tests** | Pytest | 9.1.1 | Suite de tests automatisés (36 tests unitaires/intégration). |
| **Conteneurisation** | Docker / Compose | - | Déploiement portable conteneurisé. |

### Note Légale & Licences
- **PM4Py** : Sous licence **AGPL v3** depuis 2024. Tout usage commercial propriétaire exige soit la publication du code source selon l'AGPL, soit l'acquisition d'une licence commerciale auprès de l'éditeur.
- **Dataset BPI Challenge 2019** : Données ouvertes sous licence **Creative Commons Attribution 4.0 International (CC BY 4.0)** (van Dongen, B.F., 4TU.ResearchData).

---

## 3. Architecture Globale & Philosophie de Conception

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SOURCES DE DONNÉES                                │
│                                                                             │
│  [Dataset Fictif/Recherche BPI 2019]        [API Publique NYC 311 (Socrata)]│
│  Log Purchase-to-Pay massif (.xes)          Flux d'incidents temps réel     │
└──────────────────────┬──────────────────────────────────────┬───────────────┘
                       │                                      │
                       ▼                                      ▼
             [src.extract_log]                         [src.live_source]
             [src.preprocess]                                 │
                       │                                      │
                       ▼                                      │
        ┌──────────────────────────────┐                      │
        │ COUCHE DE CONFIGURATION YAML │                      │
        │ config/bpi2019.yaml          │                      │
        │ config/nyc311.yaml           │                      │
        └──────────────┬───────────────┘                      │
                       │                                      │
                       ▼                                      ▼
        ┌─────────────────────────────────────────────────────────────┐
        │  MOTEUR ANALYTIQUE GÉNÉRIQUE AGNOSTIQUE (src/process_metrics)│
        │  - Variantes de traces                                      │
        │  - Délais de transition & goulots d'étranglement            │
        │  - Taux de rework                                           │
        │  - Charge et saturation des ressources                      │
        └──────────────┬──────────────────────────────────────┬───────┘
                       │                                      │
         ┌─────────────┴──────────────┐                       │
         ▼                            ▼                       ▼
[src.discover_process]      [src.train_model]       [src.live_analysis]
- Inductive Miner           - Détection censure     - Variantes vivantes
- Réseau de Petri (.pnml)   - 31 features préfixes  - Goulots d'étranglement
         │                  - XGBoost x2            - Fichiers d'instantanés
         ▼                            │                       │
[src.conformance_check]     [src.evaluate_model]              │
- Token-based replay                  │                       │
- Alignement fitness                  ▼                       ▼
         │                 [MODÈLES & ARTEFACTS]      [data/live/]
         └─────────────┬──────────────┘                       │
                       │                                      │
                       ├──────────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        RESTITUTION & EXPLOITATION                           │
│                                                                             │
│  1. Dashboard Streamlit (app.py - 6 vues interactives)                      │
│  2. Modélisation Décisionnelle (powerbi_export/ & powerbi_export_live/)     │
│  3. Rapports Métier Automatisés Markdown (reports/)                         │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Principes Directeurs
1. **Séparation Stricte entre Logique Métier et Données** :
   Le coeur analytique (`src/process_metrics.py`) ignore les noms spécifiques des colonnes de BPI2019 ou NYC 311. Il manipule des abstractions : `case_id`, `activity`, `timestamp`, `resource`. Le mapping est entièrement défini par un fichier YAML dans `config/`.
2. **Découplage Entraînement / Inférence** :
   L'entraînement des modèles ML et la découverte de processus s'exécutent hors conteneur. Le conteneur Docker ne fait que charger les artefacts sérialisés (`.pnml`, `.pkl`, `.parquet`) pour un démarrage instantané et une empreinte mémoire maîtrisée.
3. **Résilience et Reproductibilité** :
   Gestion des biais statistiques réels (censure temporelle, fuites de données), tri stable des timestamps pour les variantes, et gestion des proxies/antivirus d'entreprise (inspection SSL).

---

## 4. Arborescence Détaillée du Répertoire

```
process-mining-pme-v2/
├── .streamlit/
│   └── config.toml                 # Thème visuel du dashboard Streamlit
├── certs/                          # Répertoire réservé aux certificats d'autorité (ex. proxies SSL)
├── config/                         # Configuration YAML des processus analysés
│   ├── bpi2019.yaml                # Schéma et paramètres pour Purchase-to-Pay (BPI2019)
│   └── nyc311.yaml                 # Schéma et paramètres pour le ticketing (NYC 311)
├── data/
│   ├── legacy_bpi2012/             # Données de l'ancien dataset BPI 2012 (archivé après audit)
│   ├── live/                       # Instantanés dynamiques générés par l'API NYC 311
│   │   ├── nyc311_events.parquet   # Événements capturés lors du dernier appel API
│   │   ├── live_kpi_summary.json   # Synthèse des KPI calculés sur le flux vivant
│   │   └── live_process_model.pnml # Modèle de réseau de Petri découvert sur le flux
│   ├── processed/                  # Données transformées et optimisées
│   │   ├── event_log_raw.parquet   # Log brut extrait du XES (~251 000 cas)
│   │   └── event_log_clean.parquet # Log nettoyé et validé (~249 000 cas, 1.46M événements)
│   └── raw/                        # Répertoire des sources brutes (non versionné)
│       └── bpi_challenge_2019.xes  # Fichier XES d'origine (téléchargeable sur 4TU)
├── logs/
│   └── refresh.log                 # Journal d'exécution de l'orchestrateur de rafraîchissement
├── models/                         # Artefacts sérialisés du pipeline BPI2019
│   ├── conformance_report.csv      # Rapport d'alignement cas par cas (fitness, trace length)
│   ├── kpi_summary.json            # KPI globaux et recommandations générées
│   ├── performance_resources.csv   # Métriques d'activité et de charge par ressource
│   ├── performance_rework.csv      # Taux de répétition d'activités
│   ├── performance_transitions.csv # Délais d'attente moyens/médians entre transitions
│   ├── prefix_dataset.parquet      # Dataset de préfixes enrichi (31 features) pour le ML
│   ├── process_model.png           # Visualisation graphique exportée du réseau de Petri
│   ├── process_model.pnml          # Modèle Inductive Miner au format standard Petri Net XML
│   ├── xgboost_classifier.pkl      # Pipeline Scikit-Learn + XGBoost pour le risque de retard
│   └── xgboost_regressor.pkl       # Modèle XGBoost pour la prédiction du temps restant
├── nyc311/
│   ├── fetch_nyc311.py             # Script autonome de collecte API Socrata
│   └── nyc311_export/              # Exports spécifiques liés aux tickets 311
├── powerbi_export/                 # Schéma en étoile exporté pour Power BI (BPI 2019)
│   ├── README.md                   # Guide d'importation, relations et visuels Power BI
│   ├── fact_cases.csv              # Table de faits : 1 ligne / cas (248 899 lignes)
│   ├── fact_case_predictions.csv   # Table de faits : prédictions ML vs valeurs réelles
│   ├── dim_conformance.csv         # Table dimensionnelle : détail fitness / rejeu
│   ├── dim_bottlenecks.csv         # Table dimensionnelle : temps d'attente par transition
│   ├── dim_rework.csv              # Table dimensionnelle : taux de rework par activité
│   ├── dim_resources.csv           # Table dimensionnelle : volume et durée par intervenant
│   ├── dim_variants.csv            # Table dimensionnelle : séquences d'activités observées
│   ├── kpi_overview.csv            # Table à ligne unique pour affichage des cartes KPI
│   └── kpi_recommendations.csv     # Table des recommandations opérationnelles
├── powerbi_export_live/            # Schéma en étoile exporté pour Power BI (Flux vivant NYC 311)
│   ├── fact_cases.csv              # Table de faits des tickets NYC 311
│   ├── dim_bottlenecks.csv         # Goulots d'étranglement observés sur le flux
│   ├── dim_resources.csv           # Répartition par agence municipale
│   ├── dim_rework.csv              # Retouches éventuelles
│   ├── dim_variants.csv            # Variantes de traitement des tickets
│   └── kpi_overview.csv            # Vue synthétique des indicateurs live
├── reports/                        # Rapports d'analyse et audits au format Markdown
│   ├── dataset_audit_bpi2012.md    # Rapport d'évaluation préliminaire du dataset BPI 2012
│   ├── dataset_audit_bpi2019.md    # Rapport d'audit confirmant le choix de BPI 2019
│   ├── process_analysis.md         # Synthèse business du processus Purchase-to-Pay
│   └── live_process_analysis.md    # Rapport de process mining sur le flux vivant NYC 311
├── scripts/
│   └── register_refresh_task.ps1   # Script PowerShell d'enregistrement de tâche planifiée Windows
├── src/                            # Modules Python sources
│   ├── __init__.py
│   ├── audit_dataset.py            # Audit générique de la structure d'un log XES
│   ├── business_analysis.py        # Synthèse des KPI et génération de règles métier
│   ├── config.py                   # Parsing et validation des configurations YAML
│   ├── conformance_check.py        # Rejeu de traces sur réseau de Petri (token replay)
│   ├── discover_process.py         # Découverte de processus via Inductive Miner
│   ├── evaluate_model.py           # Évaluation rigoureuse des modèles prédictifs
│   ├── export_powerbi.py           # Génération des tables relationnelles Power BI (BPI2019)
│   ├── export_powerbi_live.py      # Génération des tables Power BI (NYC 311)
│   ├── extract_log.py              # Parsing XES vers format tabulaire Parquet
│   ├── live_analysis.py            # Analyse de process mining sur données live
│   ├── live_source.py              # Connecteur API Socrata pour NYC 311 (requêtes, SSL, nettoyage)
│   ├── performance_analysis.py     # Calcul des métriques de temps, transitions et rework
│   ├── preprocess.py               # Nettoyage, typage, tri et filtrage du log brut
│   ├── process_metrics.py          # Fonctions analytiques pures de process mining
│   ├── refresh.py                  # Orchestrateur d'actualisation de la plateforme
│   └── train_model.py              # Feature engineering de préfixes et entraînement XGBoost
├── tests/                          # Suite de tests unitaires et d'intégration
│   ├── conftest.py                 # Fixtures Pytest et journaux miniatures synthétiques
│   ├── test_config.py              # Tests du chargeur de configuration YAML
│   ├── test_process_metrics.py     # Tests unitaires des calculs de métriques de process mining
│   └── test_train_model.py         # Tests sur la censure temporelle et l'absence de data leak
├── app.py                          # Application principale Dashboard Streamlit
├── Dockerfile                      # Image Docker multi-composants (Streamlit + PM4Py)
├── docker-compose.yml              # Déclaration du service et montage des volumes
├── requirements.txt                # Dépendances Python verrouillées
├── avast-root.crt                  # Certificat optionnel local (exclu de Git via .gitignore)
└── README.md                       # Présentation synthétique du dépôt
```

---

## 5. Pipelines de Données & Étapes de Traitement

### 5.1 Pipeline Principal : Traitement Batch (BPI Challenge 2019)

Ce pipeline traite le journal d'événements Purchase-to-Pay de bout en bout :

```
[bpi_challenge_2019.xes]
        │
        ▼ (python -m src.extract_log)
[event_log_raw.parquet]
        │
        ▼ (python -m src.preprocess)
[event_log_clean.parquet]
   ┌────┴──────────────────────────────┐
   │                                   │
   ▼ (src.discover_process)            ▼ (src.performance_analysis)
[process_model.pnml]             [performance_transitions.csv]
   │                             [performance_rework.csv]
   ▼ (src.conformance_check)     [performance_resources.csv]
[conformance_report.csv]               │
   │                                   │
   └─────────────────┬─────────────────┘
                     ▼ (src.business_analysis)
             [kpi_summary.json]
             [reports/process_analysis.md]
```

1. **Extraction (`src.extract_log`)** :
   - Lit le fichier standard `bpi_challenge_2019.xes` via PM4Py.
   - Convertit les traces XML en structure tabulaire compressée `data/processed/event_log_raw.parquet`.
   - Volumétrie brute : 251 734 cas, 1 595 923 événements.

2. **Prétraitement & Nettoyage (`src.preprocess`)** :
   - Normalisation des noms de colonnes et horodatages en UTC.
   - Suppression des lignes corrompues ou sans identifiant de cas.
   - Tri temporel stable (`case_id`, `timestamp`) pour garantir l'idempotence des variantes.
   - Résultat nettoyé : **248 899 cas**, **1 460 254 événements**, **11 316 variantes**.

3. **Découverte de Processus (`src.discover_process`)** :
   - Utilisation de l'algorithme **Inductive Miner** (`pm4py.discover_petri_net_inductive`).
   - *Filtre anti-spaghetti* : Pour éviter un modèle illisible comportant 11 000 transitions, la découverte est appliquée sur les variantes les plus fréquentes couvrant **80% du volume total de cas**.
   - Génère `models/process_model.pnml` (réseau de Petri) et `models/process_model.png`.

4. **Vérification de Conformité (`src.conformance_check`)** :
   - Applique un rejeu de traces fondé sur les jetons (**Token-Based Replay**) entre l'ensemble des cas réels et le réseau de Petri découvert.
   - Calcule pour chaque cas : `trace_fitness` (degrés de conformité entre 0 et 1), nombre de jetons manquants (*missing*), consommés (*consumed*), restants (*remaining*).
   - Produit `models/conformance_report.csv`. Résultat : **fitness moyen de 0.981**, avec **13.8% de cas présentant des déviations**.

5. **Analyse de Performance (`src.performance_analysis`)** :
   - Calcule les durées de cycle complètes (durée médiane : 64.3 jours).
   - Calcule les temps de transition d'une activité à l'autre (`wait_hours`).
   - Identifie les goulots d'étranglement majeurs (ex: `Change Approval for Purchase Order` -> `Block Purchase Order Item`, attente moyenne de 3920.9 heures).
   - Mesure les taux de retouche (*rework*) par activité (ex: `Record Goods Receipt` présent plusieurs fois dans 4.8% des cas).
   - Évalue la distribution de la charge par ressource (ex: 278 158 événements automatisés sans utilisateur explicite `NONE`, suivi de `user_002` avec 165 817 actions).

6. **Synthèse Business (`src.business_analysis`)** :
   - Consolide l'ensemble des indicateurs dans `models/kpi_summary.json`.
   - Génère automatiquement des recommandations stratégiques chiffrées dans `reports/process_analysis.md`.

---

### 5.2 Pipeline Machine Learning Prédictif

Le pipeline prédictif résout deux cas d'usage critiques pour un gestionnaire :
- **Classification binaire** : Ce dossier risque-t-il d'être en retard ?
- **Régression** : Combien de temps reste-t-il avant la clôture finale du dossier ?

```
[event_log_clean.parquet]
        │
        ▼ (Filtrage censure temporelle : >= 150j & activité terminale)
[Cas clôturés non censurés]
        │
        ▼ (Split temporel Train/Test 80/20 selon start_time)
[Train Set]                           [Test Set]
        │                                     │
        ▼                                     ▼
[Construction des Préfixes]           [Construction des Préfixes]
(Étapes 1..k par cas)                 (Étapes 1..k par cas)
        │                                     │
        ▼ (Génération de 31 features)         ▼
[prefix_dataset_train]                [prefix_dataset_test]
        │                                     │
        ├─────────────────┐                   │
        ▼                 ▼                   │
[XGBoost Classifier] [XGBoost Regressor]      │
        │                 │                   │
        └────────┬────────┘                   │
                 ▼                            ▼
                 └───────────┬────────────────┘
                             ▼ (python -m src.evaluate_model)
                 [Métriques : AUC 0.878, MAE 17.4j]
```

#### Les 3 Corrections Majeures Apportées au Modèle
La version initiale du modèle obtenait 48.8% d'accuracy (inférieur au hasard). Le diagnostic a permis de redresser le modèle via 3 corrections :

1. **Correction de la Censure Temporelle (*Temporal Censoring*)** :
   - Dans un journal d'événements tronqué à une date $T_{\text{fin}}$, les cas initiés peu avant la fin semblent très courts car inachevés, et étaient étiquetés "à l'heure" par erreur.
   - *Solution* : Sélection stricte des cas vérifiant deux critères :
     * Le cas se termine formellement par une activité terminale (`Clear Invoice` ou `Delete Purchase Order Item`).
     * Le cas a débuté au moins **150 jours** avant la fin d'observation du journal.
   - Résultat : Taux de retard harmonisé entre train (29.2%) et test (27.0%).

2. **Enrichissement de l'Espace de Features (31 features contre 7)** :
   Au lieu de la seule activité courante et de l'horodatage, le préfixe extrait :
   - *Dynamique temporelle* : `elapsed_hours`, `hours_since_last_event`, `mean_hours_between_events`, `max_gap_hours`.
   - *Complexité du parcours* : `prefix_length`, `n_distinct_activities`, `n_rework`.
   - *Contexte calendaire* : `start_dayofweek`, `start_month`, `current_dayofweek`.
   - *Indicateurs de passage (flags)* : Indicateurs booléens pour chaque activité déjà exécutée dans la trace.
   - *Attributs métier* : `vendor`, `item_category`, `document_type`, `spend_area`, `company`, `amount_log`.

3. **Définition Robuste du Seuil de Retard** :
   - Détermination du seuil de retard calée sur le **3e quartile (75e percentile)** de la durée des cas appris **uniquement sur le jeu d'entraînement** (évitant tout *data leak* vers le test set). Le quartile le plus lent représente les cas pathologiques.
   - Prise en compte du déséquilibre de classe via le paramètre `scale_pos_weight` de XGBoost.
   - Cible de régression modélisée par $\log(1 + \text{remaining\_hours})$ pour absorber la forte asymétrie des durées.

#### Performances Finales Obtenues
- **Classifieur de Risque de Retard** : **ROC AUC = 0.878**, **Accuracy = 83.6%**, **Rappel (cas en retard) = 71.8%**.
- **Régresseur de Temps Restant** : **MAE = 17.4 jours** (soit **37.9% de réduction d'erreur** par rapport à une prédiction naïve par la médiane).

---

### 5.3 Pipeline Flux Vivant (API NYC 311)

Ce volet applique le moteur de Process Mining à un flux continu de réclamations citoyennes (tickets d'incidents urbains de la ville de New York via l'API Socrata) :

```
[API Publique Socrata (NYC 311)]
        │ (Interrogation HTTP avec filtrage fenêtre 14 jours, limit=20 000)
        ▼ (Fallback inspection SSL / avast-root.crt si nécessaire)
[src.live_source]
        │
        ▼ (Nettoyage & correction des anomalies chronologiques)
[data/live/nyc311_events.parquet]
        │
        ▼ (python -m src.live_analysis via src.process_metrics & config/nyc311.yaml)
[data/live/live_kpi_summary.json]
[reports/live_process_analysis.md]
[data/live/live_process_model.pnml]
        │
        ▼ (python -m src.export_powerbi_live)
[powerbi_export_live/*.csv]
```

#### Particularités Techniques & Qualité de Données Résolue
- **Fenêtre Temporelle Glissante** : Récupération des tickets créés au cours des **14 derniers jours**, avec conservation des tickets ouverts pour que le taux de clôture demeure une mesure dynamique réelle.
- **Détection d'une Incohérence Chronologique Source** :
  Le champ `resolution_action_updated_date` de Socrata correspond à la date de dernière modification de la fiche et non à une étape séquentielle. Dans 31% des cas, cette date précédait la création du ticket. `src/live_source.py` filtre automatiquement ces faux événements pour éviter des traces absurdes.
- **Résilience Réseau & Antivirus (Inspection SSL)** :
  Intégration d'un mécanisme de bascule automatique dans `build_session()` : si une erreur de certificat survient (antivirus type Avast réémettant des certificats locaux), le code recherche un certificat local `avast-root.crt` pour valider la chaîne de confiance sans désactiver la sécurité.

---

### 5.4 Pipeline d'Automatisation & Orchestration

Le script `src/refresh.py` orchestre la mise à jour périodique de la plateforme et écrit son suivi dans `logs/refresh.log` :

- **Périmètre Live (`--scope live`, par défaut)** :
  1. `src.live_source` : Appel API et construction du log Parquet.
  2. `src.live_analysis` : Calcul des métriques et mise à jour du modèle.
  *Durée d'exécution rapide (quelques secondes à 1 minute).*
- **Périmètre Complet (`--scope full`)** :
  1. Étapes Live (`src.live_source`, `src.live_analysis`).
  2. `src.export_powerbi_live` : Export Power BI du flux live.
  3. `src.conformance_check` : Réalignement conformité BPI 2019.
  4. `src.performance_analysis` : Recalcul goulots, rework, ressources.
  5. `src.business_analysis` : Synthèse KPI et recommandations.
  6. `src.export_powerbi` : Régénération des tables Power BI BPI 2019.

#### Planification Système
Le script PowerShell `scripts/register_refresh_task.ps1` configure une tâche planifiée dans le Gestionnaire de tâches Windows, programmée pour s'exécuter **une fois par jour**. L'API NYC publiant ses données avec 48h de consolidation, une fréquence plus rapprochée serait redondante.

---

### 5.5 Pipeline d'Export & Modélisation Power BI

Pour les organisations exploitant Power BI plutôt que Streamlit, les modules `src/export_powerbi.py` et `src/export_powerbi_live.py` génèrent des schémas relationnels optimisés en étoile :

```
                        ┌──────────────────┐
                        │ dim_conformance  │
                        └────────┬─────────┘
                                 │ 1:1 (case_id)
                                 ▼
┌─────────────────────────┐  (case_id)  ┌──────────────────────────────┐
│ fact_case_predictions   │◄───────────►│          fact_cases          │
│ (Snapshot ML à 50% cas) │   1:1 / 1:N │ (Durée, Statut, Attributs)   │
└─────────────────────────┘             └──────────────────────────────┘
                                          Tables d'agrégats analytiques :
                                          ├── dim_bottlenecks
                                          ├── dim_rework
                                          ├── dim_resources
                                          ├── dim_variants
                                          ├── kpi_overview
                                          └── kpi_recommendations
```

- **`fact_cases.csv`** : 248 899 lignes (1 ligne par cas), renseignant la durée en jours/heures, le statut de conformité, le fit score, les dimensions d'achat (fournisseur, catégorie, société).
- **`fact_case_predictions.csv`** : ~30 000 cas échantillonnés capturés à 50% de leur avancée, confrontant la probabilité de retard et le délai restant prédit à l'issue finale observée.

---

## 6. Détail des Modules Python (`src/`)

| Fichier | Entrées Principales | Sorties Principales | Responsabilité Précise |
|---|---|---|---|
| `config.py` | Fichiers YAML (`config/*.yaml`) | Objet `ProcessConfig` | Charge, valide et expose le schéma des colonnes et seuils de chaque processus. |
| `process_metrics.py` | DataFrame + `ProcessConfig` | DataFrames & Séries Pandas | Moteur de calcul pur : variantes, temps de transition, goulots, rework, charge ressources. |
| `audit_dataset.py` | Fichier `.xes` | Rapport Markdown | Analyse exploratoire d'un fichier XES brut (volume, attributs, variantes). |
| `extract_log.py` | `bpi_challenge_2019.xes` | `event_log_raw.parquet` | Parse le XML XES via PM4Py et l'écrit sous format tabulaire Parquet. |
| `preprocess.py` | `event_log_raw.parquet` | `event_log_clean.parquet` | Valide les types, nettoie les données et garantit un ordonnancement stable. |
| `discover_process.py` | `event_log_clean.parquet` | `process_model.pnml`, `.png` | Découvre le réseau de Petri via l'Inductive Miner (variantes à 80%). |
| `conformance_check.py` | Nettoyé + Réseau de Petri | `conformance_report.csv` | Rejoue les traces sur le réseau (Token-Based Replay) et calcule le fitness. |
| `performance_analysis.py` | `event_log_clean.parquet` | `performance_*.csv` | Calcule les statistiques d'attente, goulots, retouches et interventions ressources. |
| `business_analysis.py` | Rapports de performance | `kpi_summary.json`, `.md` | Dérive des règles d'alerte et recommandations à partir des métriques. |
| `train_model.py` | `event_log_clean.parquet` | `.pkl` (x2), `.parquet` | Gère la censure, crée les préfixes (31 features) et entraîne XGBoost. |
| `evaluate_model.py` | Modèles `.pkl` + Test Set | Métriques console | Évalue rigoureusement la classification (AUC, rappel) et la régression (MAE). |
| `export_powerbi.py` | Données + Modèles BPI | `powerbi_export/*.csv` | Génère les tables de faits et de dimensions pour Power BI Desktop. |
| `export_powerbi_live.py`| Événements live NYC 311 | `powerbi_export_live/*.csv`| Exporte le schéma en étoile du flux de ticketing live. |
| `live_source.py` | API REST Socrata | `nyc311_events.parquet` | Récupère, filtre et assainit le flux dynamique de tickets d'incidents. |
| `live_analysis.py` | `nyc311_events.parquet` | `live_kpi_summary.json` | Applique le process mining générique au flux live de tickets. |
| `refresh.py` | Arguments CLI (`--scope`) | `logs/refresh.log` | Orchestre séquentiellement les étapes d'actualisation de la plateforme. |

---

## 7. Couche de Restitution & Dashboard Streamlit

L'application `app.py` propose une interface web structurée en 6 vues complémentaires :

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       PROCESS MINING PME - DASHBOARD                        │
├──────────────┬───────────┬──────────────┬────────────┬──────────────┬───────┤
│ Vue          │ Processus │ Conformité & │ Prédiction │ Recommanda-  │ Flux  │
│ d'ensemble   │           │ Performance  │            │ tions        │ Vivant│
└──────────────┴───────────┴──────────────┴────────────┴──────────────┴───────┘
```

1. **Vue d'ensemble** :
   - Cartes KPI synthétiques : nombre de cas (248 899), durée moyenne (70.4 j), durée médiane (64.3 j), taux de déviation (13.8%), fitness global (0.981), rework moyen (0.4%).
   - Histogramme interactif de distribution des durées des cas (tronqué au 95e percentile).
   - Diagramme à barres des 15 activités les plus fréquentes.
2. **Processus** :
   - Visualisation vectorielle du réseau de Petri découvert (Places, Transitions, Arcs) via Graphviz.
   - Tableau du Top 10 des variantes de processus avec leurs volumes respectifs.
3. **Conformité & Performance** :
   - Histogramme de distribution des scores de fitness par cas.
   - Tableau d'audit des cas les plus déviants (aptes au ciblage opérationnel).
   - Diagramme horizontal des goulots d'étranglement majeurs (attente en heures).
   - Tableaux de rework par activité et de volumétrie traitée par intervenant.
4. **Prédiction** :
   - Sélection interactive d'un cas client et simulation pas-à-pas le long de son cycle de vie (slider de longueur de préfixe).
   - Affichage de l'état contextuel du dossier (durée écoulée, retouches, montant, fournisseur).
   - Jauge de probabilité de risque de retard (modèle de classification).
   - Estimation du temps restant avant clôture en heures et jours (modèle de régression).
5. **Recommandations** :
   - Synthèse textuelle des alertes opérationnelles déclenchées automatiquement.
   - Tableau de correspondance problème identifié $\leftrightarrow$ impact quantifié.
6. **Flux vivant (API)** :
   - Tableau de bord en direct sur les réclamations citoyennes NYC 311.
   - KPI du flux : tickets récupérés, taux de clôture dynamique, délai médian de résolution.
   - Types d'incidents les plus lents à traiter.
   - Courbe chronologique du volume de création quotidienne de tickets.

---

## 8. Process Health Score

### 8.1 Objectif

Le Process Health Score condense l'ensemble des analyses de la plateforme en **un
score unique de 0 à 100**, accompagné d'un statut lisible (EXCELLENT / GOOD /
WARNING / CRITICAL). Il répond à la question qu'un responsable de PME se pose en
premier — *« mon processus va-t-il bien, et par où je commence ? »* — sans exiger
la moindre connaissance du process mining.

C'est une **couche de synthèse, pas une couche de calcul** : le module
`src/process_health.py` ne calcule aucune métrique de process mining. Il relit les
KPI déjà produits par `business_analysis.py`, `performance_analysis.py`,
`process_metrics.py` et les prédictions de `train_model.py`.

### 8.2 Principe de conception : des métriques sans échelle

Un dossier d'achat BPI2019 dure 64 jours en médiane ; un ticket NYC 311 dure
9 minutes. Aucun seuil exprimé en heures ne peut donc servir les deux processus.
Chaque dimension est par conséquent réduite à un **ratio** interprétable
indépendamment du processus analysé, ce qui rend le score comparable d'un
processus à l'autre et conforme à l'architecture générique de la plateforme.

### 8.3 Les cinq dimensions

| Dimension | Mesure brute | KPI source | Sens |
|---|---|---|---|
| **Performance** | `p90 / médiane` des durées de cas | `process_metrics.summarize` | bas = mieux |
| **Conformance** | Taux de déviation au modèle découvert | `conformance_check` via `business_analysis` | bas = mieux |
| **Delay Risk** | Part des cas signalés à risque par le classifieur | `export_powerbi` -> `fact_case_predictions.csv` | bas = mieux |
| **Rework** | Taux de rework moyen | `performance_analysis.rework_rates` | bas = mieux |
| **Resource Load** | Part des événements traités par la ressource la plus chargée | `performance_analysis.resource_load` | bas = mieux |

### 8.4 Normalisation

`normalize_metric(value, best, worst, log_scale=False)` ramène chaque KPI sur
0-100. L'ordre de `best` et `worst` encode le sens de la métrique : nul besoin de
préciser ailleurs si « plus haut » ou « plus bas » vaut mieux. Toute valeur au-delà
des bornes est ramenée dans l'intervalle.

| Dimension | Borne 100 | Borne 0 | Échelle |
|---|---|---|---|
| Performance | ratio 2 | ratio 25 | logarithmique |
| Conformance | 0 % de déviation | 100 % | linéaire |
| Delay Risk | 0 % à risque | `2 x (1 - late_quantile)` = 50 % | linéaire |
| Rework | 0 % | 20 % | linéaire |
| Resource Load | 10 % des événements | 50 % | linéaire |

L'échelle logarithmique pour la performance traduit le fait qu'il s'agit d'un
rapport : passer de 2 à 4 y compte autant que de 10 à 20.

La borne de Delay Risk est **dérivée de la configuration** : le seuil de retard
étant défini au quantile `late_quantile` (0.75), une part de 25 % de cas à risque
correspond à la situation de référence attendue par construction.

La fonction est robuste par conception : `None`, `NaN`, `inf`, texte, division par
zéro et logarithme d'une valeur nulle renvoient tous `None` (dimension écartée)
plutôt qu'une exception ou un score fantaisiste.

### 8.5 Pondération

Définie dans le YAML de chaque processus (`config/*.yaml`) :

```yaml
health_score:
  weights:
    performance: 0.25
    conformance: 0.25
    delay_risk: 0.20
    rework: 0.15
    resource_load: 0.15
```

**Justification.** Performance et conformance pèsent le plus : ce sont les deux
piliers du process mining, mesurés directement sur le log complet. Le risque de
retard vient d'un modèle prédictif — donc d'une estimation, pas d'une mesure — et
pèse un cran en dessous. Rework et charge des ressources sont des signaux de
diagnostic secondaires : utiles pour expliquer un problème, rarement suffisants
pour le qualifier seuls.

### 8.6 Classification

| Score | Statut |
|---|---|
| 90 - 100 | EXCELLENT |
| 75 - 89 | GOOD |
| 60 - 74 | WARNING |
| 0 - 59 | CRITICAL |
| aucune dimension calculable | UNKNOWN |

### 8.7 Traitement des données indisponibles

Une dimension dont le KPI source est absent est **écartée** — jamais remplacée par
une valeur inventée. Les poids des dimensions restantes sont alors **renormalisés
à une somme de 1**, pour que le score reste sur 100.

Le flux NYC 311 en est l'illustration concrète : il ne dispose ni de conformance
checking ni de modèle de prédiction. Son score se calcule donc sur trois
dimensions, avec des poids ramenés de 0.55 à 1 :

```
score = perf x (0.25/0.55) + rework x (0.15/0.55) + resource x (0.15/0.55)
```

Le chemin des prédictions vient lui aussi du YAML (`artifacts.predictions`) et non
d'une constante : sans cette précaution, un processus dépourvu de modèle se verrait
attribuer les prédictions d'un autre dataset.

### 8.8 Interprétation métier

`interpret()` rédige une lecture en clair, **strictement déterministe** : chaque
phrase découle d'un seuil ou d'une valeur mesurée, aucun modèle de langage
n'intervient. Exemple de sortie réelle sur BPI2019 :

> Le processus est dans un etat GOOD (81/100). Le point faible est risque de retard
> (41/100), le modele signalant 29.5% de dossiers a risque pour une reference
> attendue de 25%. A l'inverse, performance reste solide (100/100).

### 8.9 Intégration Streamlit

Le score occupe le **haut de l'onglet « Vue d'ensemble »**, avant les KPI bruts :
score global encadré et coloré selon le statut, barres horizontales Plotly des
sous-scores, métriques « Point faible » / « Point fort », interprétation en clair,
puis un volet dépliant reprenant les **recommandations déjà générées** par
`business_analysis` — aucune nouvelle logique de recommandation n'a été créée.

### 8.10 Limites assumées

Le rapport `p90 / médiane` mesure la **régularité** des durées, pas la vitesse
absolue : un processus uniformément lent mais prévisible obtient un bon score sur
cette dimension. C'est volontaire — juger la vitesse absolue exigerait un objectif
de délai (SLA) que la plateforme ne connaît pas, et l'inventer reviendrait à
fabriquer une valeur. La lenteur absolue reste visible dans les KPI de la vue
d'ensemble ; le score, lui, signale l'irrégularité.

De même, une source qui code l'absence de ressource par un identifiant factice
(BPI2019 utilise `NONE`) le voit compté comme une ressource à part entière, ce qui
gonfle la concentration apparente. Aucun moyen générique ne permet de distinguer un
tel marqueur d'un acteur réel.

---

## 9. Décisions Techniques, Biais Résolus & Bonnes Pratiques

### 9.1 Agnosticisme Fonctionnel
Contrairement aux scripts de recherche traditionnels où les noms de colonnes sont codés en dur, la plateforme s'appuie sur une structure orientée configuration. Pour analyser un processus de gestion des congés RH ou de logistique interne, il suffit de créer `config/mon_processus.yaml` en précisant :
- La colonne identifiant de cas (`case_id`).
- La colonne de libellé d'action (`activity`).
- La colonne d'horodatage (`timestamp`).
- Les activités marquant la fin normale du processus (`terminal_activities`).

### 8.2 Découverte de Modèles Intelligible
Appliquer un algorithme de découverte (Alpha Miner ou Inductive Miner) sur 100% d'un jeu de 11 000 variantes engendre un modèle dit « plat de spaghetti », inexploitable par l'humain. Le module `discover_process.py` utilise les variantes représentant 80% de la masse critique des cas. Le modèle reste synthétique et fidèle, tandis que le conformance checking continue d'évaluer 100% des cas réels.

### 8.3 Évitement des Fuites de Données (*Data Leaks*)
- Le seuil séparant les cas "à l'heure" des cas "en retard" (75e percentile de durée) est **strictement calculé sur le jeu d'entraînement** et propagé comme paramètre fixe vers le jeu de test et le pipeline de production.
- Le split train/test est temporel : les cas ayant débuté en premier constituent le jeu d'entraînement, préservant la logique chronologique réelle.

### 8.4 Gestion des Certificats Réseau en Milieu Sécurisé
En environnement d'entreprise ou sur des postes équipés de suites de sécurité analysant les flux HTTPS (Avast, Kaspersky, Zscaler), les requêtes API Python échouent fréquemment (`CERTIFICATE_VERIFY_FAILED`). La fonction `build_session()` dans `src/live_source.py` gère ce cas : elle tente la connexion sécurisée classique via `certifi`, et en cas d'échec SSL, injecte le certificat racine local (`avast-root.crt`) préalablement exporté.

---

## 10. Guide d'Exécution & Déploiement

### 9.1 Exécution Locale Directe (Hors Docker)

#### Prérequis
- Python 3.11+ (idéalement Python 3.13)
- Graphviz installé et présent dans le `PATH` système (pour le rendu du réseau de Petri)

#### Installation de l'environnement virtuel
```powershell
# Cloner le dépôt et naviguer dans le dossier
cd process-mining-pme-v2

# Créer et activer l'environnement virtuel
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # Sous Windows PowerShell
# source .venv/bin/activate    # Sous Linux/macOS

# Installer les dépendances
pip install -r requirements.txt
```

#### Exécution du Pipeline Étape par Étape (BPI 2019)
```powershell
# 1. Extraction du XES brut vers Parquet (nécessite data/raw/bpi_challenge_2019.xes)
python -m src.extract_log

# 2. Nettoyage et typage
python -m src.preprocess

# 3. Découverte du modèle Inductive Miner (.pnml)
python -m src.discover_process

# 4. Vérification de conformité (rejeu de jetons)
python -m src.conformance_check

# 5. Calcul des métriques de performance et goulots
python -m src.performance_analysis

# 6. Synthèse des KPI et génération des recommandations
python -m src.business_analysis

# 7. Entraînement des modèles ML prédictifs (XGBoost)
python -m src.train_model

# 8. Évaluation sur le jeu de test
python -m src.evaluate_model
```

#### Exécution du Volet Flux Vivant (API NYC 311)
```powershell
# Optionnel : définir votre jeton Socrata dans un fichier .env (SOCRATA_APP_TOKEN=...)
python -m src.live_source     # Récupération des tickets récents
python -m src.live_analysis   # Process mining sur le flux vivant
```

#### Lancement du Dashboard Streamlit
```powershell
streamlit run app.py
```
*Le dashboard s'ouvre sur `http://localhost:8501`.*

#### Exports vers Power BI
```powershell
python -m src.export_powerbi       # Génère les CSV dans powerbi_export/
python -m src.export_powerbi_live  # Génère les CSV dans powerbi_export_live/
```

---

### 9.2 Déploiement via Docker

L'architecture conteneurisée exploite les artefacts déjà calculés montés en volumes partagés :

```powershell
# Construction de l'image et démarrage du conteneur
docker-compose up --build
```
L'application Streamlit devient accessible sur `http://localhost:8501`.

---

## 11. Stratégie de Test & Validation

La suite de tests automatisée est hébergée dans le dossier `tests/` et s'exécute via :

```powershell
python -m pytest tests/ -v
```

### Périmètre des 36 Tests Couverts
- **`test_config.py`** :
  - Validation du chargement de `bpi2019.yaml` et `nyc311.yaml`.
  - Rejet des configurations invalides (absence de colonnes obligatoires, types incorrects).
- **`test_process_metrics.py`** :
  - Calcul déterministe des variantes de traces sur des mini-logs de référence.
  - Calcul des délais de transition et détection des goulots.
  - Comptage des occurrences de retouche (*rework*).
  - Résistance aux événements simultanés grâce au tri stable.
- **`test_train_model.py`** :
  - Validation de la fonction de filtrage de censure temporelle (conservation des cas anciens clôturés, élimination des cas récents inachevés).
  - Vérification de l'étanchéité temporelle du train/test split.
  - Absence stricte de fuite d'information (*data leak*) dans la génération des 31 features de préfixe.
