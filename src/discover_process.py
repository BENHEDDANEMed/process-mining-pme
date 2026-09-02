"""Phase 2 - Decouverte du processus (Inductive Miner) et export du modele."""

from pathlib import Path

import pandas as pd
import pm4py

from src.preprocess import CLEAN_EVENT_LOG_PATH, CASE_ID_COL, ACTIVITY_COL, TIMESTAMP_COL
from pm4py.visualization.petri_net import visualizer as pn_visualizer

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"
PNML_PATH = MODELS_DIR / "process_model.pnml"
PNG_PATH = MODELS_DIR / "process_model.png"  

# BPI2019 compte >11 000 variantes : decouvrir un modele sur la totalite du
# log produit un "spaghetti model" illisible. On ne garde, pour la
# decouverte, que les TOP_K_VARIANTS variantes les plus frequentes - le
# conformance checking (phase 3), lui, continue de tourner sur le log complet
# nettoye pour mesurer fidelement les deviations reelles.
TOP_K_VARIANTS = 20


def load_clean_log() -> pd.DataFrame:
    df = pd.read_parquet(CLEAN_EVENT_LOG_PATH)
    return pm4py.format_dataframe(
        df,
        case_id=CASE_ID_COL,
        activity_key=ACTIVITY_COL,
        timestamp_key=TIMESTAMP_COL,
    )


def filter_for_discovery(df: pd.DataFrame, k: int = TOP_K_VARIANTS) -> pd.DataFrame:
    # pm4py.filter_variants_top_k leve une ArrowNotImplementedError sur les
    # colonnes de variantes (list<string>) issues du backend pyarrow de
    # pandas ; le meme filtrage est reproduit ici directement en pandas.
    case_variants = (
        df.sort_values(TIMESTAMP_COL)
        .groupby(CASE_ID_COL)[ACTIVITY_COL]
        .apply(tuple)
    )
    top_variants = set(case_variants.value_counts().head(k).index)
    kept_cases = case_variants[case_variants.isin(top_variants)].index
    return df[df[CASE_ID_COL].isin(kept_cases)].copy()


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

def export_image(net, im, fm, path: Path) -> None:
    gviz = pn_visualizer.apply(
        net, im, fm,
        parameters={pn_visualizer.Variants.WO_DECORATION.value.Parameters.FORMAT: "png"},
    )
    pn_visualizer.save(gviz, str(path))
    print(f"Image du modele sauvegardee : {path}")

def main() -> None:
    df = load_clean_log()
    df_discovery = filter_for_discovery(df)
    n_cases_full = df[CASE_ID_COL].nunique()
    n_cases_kept = df_discovery[CASE_ID_COL].nunique()
    print(
        f"Decouverte sur les {TOP_K_VARIANTS} variantes les plus frequentes : "
        f"{n_cases_kept}/{n_cases_full} cas conserves"
    )

    net, im, fm = discover_inductive(df_discovery)
    summarize(net, "Inductive Miner")
    pm4py.write_pnml(net, im, fm, str(PNML_PATH))
    print(f"Modele sauvegarde : {PNML_PATH}")
    export_image(net, im, fm, PNG_PATH)  # nouvelle ligne

    # Comparaison bonus avec Heuristic Miner (indicateur de complexite uniquement,
    # le modele exporte en Phase 3/4 reste celui de l'Inductive Miner)
    net_h, im_h, fm_h = discover_heuristic(df_discovery)
    summarize(net_h, "Heuristic Miner")


if __name__ == "__main__":
    main()
