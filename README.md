# Process Mining PME

Plateforme legere de process mining destinee aux PME, appliquee au dataset public
**BPI Challenge 2012** (demandes de pret personnel, banque neerlandaise, ~13 000 cas,
~164 000 evenements apres nettoyage).

Permet de :
1. Decouvrir automatiquement le vrai deroulement du processus a partir des logs (Inductive Miner).
2. Verifier si les cas reels respectent le modele decouvert (fitness / precision, token-based replay).
3. Predire, pour un dossier en cours : son issue probable (approuve / refuse / annule) et le temps
   restant avant cloture, via deux modeles XGBoost.

## Stack technique

| Brique | Role |
|---|---|
| Python | Langage principal |
| PM4Py | Extraction, decouverte du processus, conformance checking |
| Scikit-Learn | Pipeline de features, split train/test |
| XGBoost | Classification (issue) et regression (temps restant) |
| Streamlit | Dashboard interactif (4 vues) |
| Docker | Conteneurisation, un seul conteneur |

### Licences

- **pm4py** est sous licence **AGPL v3** depuis 2024 : un usage commercial non
  open-source necessite une licence payante (voir https://processintelligence.solutions/pm4py#licensing).
- Le dataset **BPI Challenge 2012** est public (4TU Research Data), utilise ici a
  des fins pedagogiques.

### Decision d'architecture

Un seul conteneur Streamlit + PM4Py + XGBoost (pas de backend API separe : usage en
analyse de lot, pas de temps reel ni multi-clients). Les modeles (`process_model.pnml`,
`xgboost_classifier.pkl`, `xgboost_regressor.pkl`) sont **entraines hors du conteneur**
puis montes en volume ; le conteneur ne fait que les charger pour servir le dashboard.

## Structure

```
process-mining-pme-v2/
├── data/
│   └── bpi_challenge_2012.xes
├── models/
│   ├── process_model.pnml
│   ├── xgboost_classifier.pkl
│   └── xgboost_regressor.pkl
├── src/
│   ├── extract_log.py       # Phase 1 - XES -> DataFrame
│   ├── preprocess.py        # Phase 1 - nettoyage + stats descriptives
│   ├── discover_process.py  # Phase 2 - Inductive Miner -> .pnml
│   ├── conformance_check.py # Phase 3 - fitness / precision / cas deviants
│   ├── train_model.py       # Phase 4 - feature engineering + XGBoost x2
│   └── evaluate_model.py    # Phase 4 - metriques des 2 modeles
├── app.py                   # Phase 5 - dashboard Streamlit
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
python -m src.train_model
python -m src.evaluate_model

streamlit run app.py
```

## Utilisation (Docker)

Les etapes ci-dessus (jusqu'a `train_model.py`) doivent avoir ete executees au moins
une fois en local pour generer `data/` et `models/`, ensuite :

```bash
docker-compose up --build
```

Dashboard accessible sur http://localhost:8501.

## Dataset

BPI_Challenge_2012.xes (van Dongen, B.F. (Boudewijn), 4TU.ResearchData). Le fichier
`.xes` n'est pas commite dans ce depot (voir `.gitignore`) ; le telecharger depuis
4TU Research Data et le placer dans `data/bpi_challenge_2012.xes`.
