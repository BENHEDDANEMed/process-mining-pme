"""Phase 1 - Extraction du journal d'evenements BPI Challenge 2012 (XES -> DataFrame)."""

from pathlib import Path

import pandas as pd
import pm4py

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
XES_PATH = DATA_DIR / "bpi_challenge_2012.xes"
RAW_EVENT_LOG_PATH = DATA_DIR / "event_log_raw.parquet"


def extract_log(xes_path: Path = XES_PATH) -> pd.DataFrame:
    log = pm4py.read_xes(str(xes_path))
    df = pm4py.convert_to_dataframe(log)
    return df


def main() -> None:
    df = extract_log()
    df.to_parquet(RAW_EVENT_LOG_PATH, index=False)
    print(f"Log extrait : {len(df)} evenements, {df['case:concept:name'].nunique()} cas")
    print(f"Colonnes disponibles : {list(df.columns)}")
    print(f"Sauvegarde : {RAW_EVENT_LOG_PATH}")


if __name__ == "__main__":
    main()
