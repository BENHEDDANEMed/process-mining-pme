"""Phase 1 - Extraction du journal d'evenements BPI Challenge 2019 (XES -> DataFrame).

Dataset : Purchase-to-Pay (van Dongen, 4TU.ResearchData), retenu apres audit
comparatif avec BPI Challenge 2012 (voir reports/dataset_audit_bpi2012.md et
reports/dataset_audit_bpi2019.md).
"""

from pathlib import Path

import pandas as pd
import pm4py

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DATA_DIR = BASE_DIR / "data" / "raw"
PROCESSED_DATA_DIR = BASE_DIR / "data" / "processed"

XES_PATH = RAW_DATA_DIR / "bpi_challenge_2019.xes"
RAW_EVENT_LOG_PATH = PROCESSED_DATA_DIR / "event_log_raw.parquet"


def extract_log(xes_path: Path = XES_PATH) -> pd.DataFrame:
    log = pm4py.read_xes(str(xes_path))
    df = pm4py.convert_to_dataframe(log)
    return df


def main() -> None:
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    df = extract_log()
    df.to_parquet(RAW_EVENT_LOG_PATH, index=False)
    print(f"Log extrait : {len(df)} evenements, {df['case:concept:name'].nunique()} cas")
    print(f"Colonnes disponibles : {list(df.columns)}")
    print(f"Sauvegarde : {RAW_EVENT_LOG_PATH}")


if __name__ == "__main__":
    main()
