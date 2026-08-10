"""Phase 2 - Decouverte du processus (Inductive Miner) et export du modele."""

from pathlib import Path

import pandas as pd
import pm4py

from src.preprocess import CLEAN_EVENT_LOG_PATH, CASE_ID_COL, ACTIVITY_COL, TIMESTAMP_COL

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"
PNML_PATH = MODELS_DIR / "process_model.pnml"


def load_clean_log() -> pd.DataFrame:
    df = pd.read_parquet(CLEAN_EVENT_LOG_PATH)
    return pm4py.format_dataframe(
        df,
        case_id=CASE_ID_COL,
        activity_key=ACTIVITY_COL,
        timestamp_key=TIMESTAMP_COL,
    )


def discover_inductive(df: pd.DataFrame):
    return pm4py.discover_petri_net_inductive(
        df, case_id_key=CASE_ID_COL, activity_key=ACTIVITY_COL, timestamp_key=TIMESTAMP_COL
    )


def discover_heuristic(df: pd.DataFrame):
    return pm4py.discover_petri_net_heuristics(
        df, case_id_key=CASE_ID_COL, activity_key=ACTIVITY_COL, timestamp_key=TIMESTAMP_COL
    )


def summarize(net, name: str) -> None:
    print(f"[{name}] places={len(net.places)} transitions={len(net.transitions)} arcs={len(net.arcs)}")


def main() -> None:
    df = load_clean_log()

    net, im, fm = discover_inductive(df)
    summarize(net, "Inductive Miner")
    pm4py.write_pnml(net, im, fm, str(PNML_PATH))
    print(f"Modele sauvegarde : {PNML_PATH}")

    # Comparaison bonus avec Heuristic Miner (indicateur de complexite uniquement,
    # le modele exporte en Phase 3/4 reste celui de l'Inductive Miner)
    net_h, im_h, fm_h = discover_heuristic(df)
    summarize(net_h, "Heuristic Miner")


if __name__ == "__main__":
    main()
