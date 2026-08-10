"""Phase 3 - Verification de conformite (token-based replay) contre le modele decouvert."""

from pathlib import Path

import pandas as pd
import pm4py

from src.discover_process import MODELS_DIR, PNML_PATH, load_clean_log
from src.preprocess import CASE_ID_COL, ACTIVITY_COL, TIMESTAMP_COL

REPORT_PATH = MODELS_DIR / "conformance_report.csv"
TOP_N_DEVIANT = 20


def main() -> None:
    df = load_clean_log()
    net, im, fm = pm4py.read_pnml(str(PNML_PATH))

    fitness = pm4py.fitness_token_based_replay(
        df, net, im, fm,
        case_id_key=CASE_ID_COL, activity_key=ACTIVITY_COL, timestamp_key=TIMESTAMP_COL,
    )
    precision = pm4py.precision_token_based_replay(
        df, net, im, fm,
        case_id_key=CASE_ID_COL, activity_key=ACTIVITY_COL, timestamp_key=TIMESTAMP_COL,
    )
    diagnostics = pm4py.conformance_diagnostics_token_based_replay(
        df, net, im, fm,
        case_id_key=CASE_ID_COL, activity_key=ACTIVITY_COL, timestamp_key=TIMESTAMP_COL,
    )

    print(f"Fitness moyen (log): {fitness['log_fitness']:.4f}")
    print(f"Precision (log): {precision:.4f}")

    case_ids = df[[CASE_ID_COL]].drop_duplicates()[CASE_ID_COL].tolist()
    per_case = pd.DataFrame({
        "case_id": case_ids,
        "trace_fitness": [d["trace_fitness"] for d in diagnostics],
        "is_fit": [d["trace_is_fit"] for d in diagnostics],
        "missing_tokens": [d["missing_tokens"] for d in diagnostics],
        "remaining_tokens": [d["remaining_tokens"] for d in diagnostics],
    })
    per_case = per_case.sort_values("trace_fitness")
    per_case.to_csv(REPORT_PATH, index=False)

    n_deviant = (~per_case["is_fit"]).sum()
    print(f"Cas non conformes : {n_deviant} / {len(per_case)} ({n_deviant / len(per_case):.1%})")
    print(f"Top {TOP_N_DEVIANT} cas les plus deviants :")
    print(per_case.head(TOP_N_DEVIANT).to_string(index=False))
    print(f"Rapport complet sauvegarde : {REPORT_PATH}")


if __name__ == "__main__":
    main()
