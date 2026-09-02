"""Phase 3 - Analyse de performance : goulots d'etranglement, temps d'attente
entre activites, rework, charge par ressource.

Ce module ne contient plus de logique de calcul : celle-ci vit dans
`src/process_metrics.py`, ou elle est ecrite de facon generique et partagee
avec l'analyse du flux vivant (`src/live_analysis.py`). Ici, on se contente de
charger le log, d'appliquer ces metriques via la configuration du processus,
et d'ecrire les rapports.

Usage :
    python -m src.performance_analysis                # processus par defaut (bpi2019)
    python -m src.performance_analysis --config nyc311
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src.config import DEFAULT_CONFIG, ProcessConfig, load_config
from src.preprocess import CLEAN_EVENT_LOG_PATH
from src.process_metrics import rework_rates, resource_load, transition_waits

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"

# Conserve pour compatibilite avec les modules qui importaient ce nom.
RESOURCE_COL = "org:resource"

TRANSITIONS_REPORT_PATH = MODELS_DIR / "performance_transitions.csv"
REWORK_REPORT_PATH = MODELS_DIR / "performance_rework.csv"
RESOURCE_REPORT_PATH = MODELS_DIR / "performance_resources.csv"

TOP_N_DISPLAY = 10


def compute_transition_waits(df: pd.DataFrame, cfg: ProcessConfig | None = None) -> pd.DataFrame:
    return transition_waits(df, cfg or load_config())


def compute_rework(df: pd.DataFrame, cfg: ProcessConfig | None = None) -> pd.DataFrame:
    return rework_rates(df, cfg or load_config())


def compute_resource_load(df: pd.DataFrame, cfg: ProcessConfig | None = None) -> pd.DataFrame:
    return resource_load(df, cfg or load_config())


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyse de performance d'un processus")
    parser.add_argument("--config", default=DEFAULT_CONFIG, help="Nom du processus (voir config/)")
    args = parser.parse_args()

    cfg = load_config(args.config)
    print(f"Processus analyse : {cfg.label}")

    df = pd.read_parquet(CLEAN_EVENT_LOG_PATH)
    MODELS_DIR.mkdir(exist_ok=True)

    transitions = transition_waits(df, cfg)
    transitions.to_csv(TRANSITIONS_REPORT_PATH, index=False)
    significant = transitions[transitions["count"] >= cfg.analysis.min_transition_count]
    print(
        f"\nTop {TOP_N_DISPLAY} goulots d'etranglement "
        f"(attente moyenne la plus elevee, >= {cfg.analysis.min_transition_count} occurrences) :"
    )
    print(significant.head(TOP_N_DISPLAY).to_string(index=False))

    rework = rework_rates(df, cfg)
    rework.to_csv(REWORK_REPORT_PATH, index=False)
    print(f"\nTop {TOP_N_DISPLAY} activites avec le plus de rework :")
    print(rework.head(TOP_N_DISPLAY).to_string(index=False))

    resources = resource_load(df, cfg)
    resources.to_csv(RESOURCE_REPORT_PATH, index=False)
    print(f"\nTop {TOP_N_DISPLAY} ressources les plus sollicitees :")
    print(resources.head(TOP_N_DISPLAY).to_string(index=False))

    print(f"\nSauvegarde : {TRANSITIONS_REPORT_PATH}")
    print(f"Sauvegarde : {REWORK_REPORT_PATH}")
    print(f"Sauvegarde : {RESOURCE_REPORT_PATH}")


if __name__ == "__main__":
    main()
