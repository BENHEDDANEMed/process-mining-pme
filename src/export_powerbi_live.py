"""Export Power BI du flux vivant NYC 311.

Contrairement a `export_powerbi.py` (dedie a BPI2019), ce script ne reimplemente
aucune metrique : il appelle `src/process_metrics.py` avec `config/nyc311.yaml`,
exactement comme `live_analysis.py`. C'est la demonstration, une fois de plus,
que la generalisation par configuration s'applique aussi a l'export - pas
seulement a l'analyse affichee dans le dashboard.

Produit, dans powerbi_export_live/ :
- fact_cases.csv       : 1 ligne par ticket (duree, attributs, cloture)
- dim_bottlenecks.csv  : temps d'attente moyen par transition d'activites
- dim_rework.csv       : taux de repetition d'une activite dans un cas
- dim_resources.csv    : charge par agence (colonne "resource" du config)
- dim_variants.csv     : frequence de chaque sequence d'activites
- kpi_overview.csv     : KPI globaux, 1 seule ligne

Prerequis : avoir execute `python -m src.live_source` au moins une fois.

Usage :
    python -m src.export_powerbi_live
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config import load_config
from src.live_source import EVENT_LOG_PATH
from src.process_metrics import (
    case_variants, closed_cases, completed_cases, resource_load,
    rework_rates, summarize, transition_waits,
)

BASE_DIR = Path(__file__).resolve().parent.parent
EXPORT_DIR = BASE_DIR / "powerbi_export_live"
CONFIG_NAME = "nyc311"


def load_live_log() -> pd.DataFrame:
    if not EVENT_LOG_PATH.exists():
        raise FileNotFoundError(
            f"{EVENT_LOG_PATH} introuvable. Executer d'abord : python -m src.live_source"
        )
    cfg = load_config(CONFIG_NAME)
    df = pd.read_parquet(EVENT_LOG_PATH)
    df[cfg.timestamp] = pd.to_datetime(df[cfg.timestamp], utc=True)
    return df


def export_fact_cases(df: pd.DataFrame, cfg) -> pd.DataFrame:
    per_case = df.groupby(cfg.case_id)[cfg.timestamp].agg(["min", "max", "count"])
    per_case.columns = ["case_start", "case_end", "n_events"]
    per_case["duration_hours"] = (per_case["case_end"] - per_case["case_start"]).dt.total_seconds() / 3600

    attrs = {}
    for col in cfg.categorical_attributes:
        if col in df.columns:
            attrs[col] = df.groupby(cfg.case_id)[col].first()
    case_attrs = pd.DataFrame(attrs)

    reached_terminal = df[cfg.case_id].isin(closed_cases(df, cfg))
    finished_on_terminal = df[cfg.case_id].isin(completed_cases(df, cfg))
    flags = pd.DataFrame({
        "reached_terminal_state": reached_terminal.groupby(df[cfg.case_id]).first(),
        "finished_on_terminal_state": finished_on_terminal.groupby(df[cfg.case_id]).first(),
    })

    fact_cases = (
        per_case.join(case_attrs).join(flags)
        .reset_index().rename(columns={cfg.case_id: "case_id"})
    )
    fact_cases.to_csv(EXPORT_DIR / "fact_cases.csv", index=False)
    return fact_cases


def export_dim_tables(df: pd.DataFrame, cfg) -> None:
    transition_waits(df, cfg).to_csv(EXPORT_DIR / "dim_bottlenecks.csv", index=False)
    rework_rates(df, cfg).to_csv(EXPORT_DIR / "dim_rework.csv", index=False)
    resource_load(df, cfg).to_csv(EXPORT_DIR / "dim_resources.csv", index=False)

    variants = case_variants(df, cfg).reset_index()
    variants.columns = ["variant_tuple", "n_cases"]
    variants["variant"] = variants["variant_tuple"].apply(lambda v: " -> ".join(v))
    variants["variant_id"] = range(1, len(variants) + 1)
    variants[["variant_id", "variant", "n_cases"]].to_csv(EXPORT_DIR / "dim_variants.csv", index=False)


def export_kpi_overview(df: pd.DataFrame, cfg) -> None:
    kpis = summarize(df, cfg)
    pd.DataFrame([kpis]).to_csv(EXPORT_DIR / "kpi_overview.csv", index=False)


def main() -> None:
    EXPORT_DIR.mkdir(exist_ok=True)
    cfg = load_config(CONFIG_NAME)
    df = load_live_log()

    fact_cases = export_fact_cases(df, cfg)
    print(f"fact_cases.csv : {len(fact_cases)} tickets")

    export_dim_tables(df, cfg)
    print("dim_bottlenecks.csv / dim_rework.csv / dim_resources.csv / dim_variants.csv : OK")

    export_kpi_overview(df, cfg)
    print("kpi_overview.csv : OK")

    print(f"\nExport termine dans : {EXPORT_DIR}")


if __name__ == "__main__":
    main()
