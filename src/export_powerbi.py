"""Phase 5 (modifications.md) - Export des donnees au format CSV pour Power BI.

Produit un dossier powerbi_export/ avec des tables pretes a l'import (Obtenir
les donnees > Dossier, dans Power BI Desktop) :

- fact_cases.csv             : 1 ligne par cas (duree, attributs metier, conformite)
- fact_case_predictions.csv  : echantillon de cas avec prediction ML vs realite
- dim_conformance.csv        : detail de conformite par cas (alias de conformance_report)
- dim_bottlenecks.csv        : temps d'attente moyen par transition d'activites
- dim_rework.csv             : taux de rework par activite
- dim_resources.csv          : charge par ressource
- dim_variants.csv           : frequence des variantes de processus
- kpi_overview.csv           : KPI globaux, 1 seule ligne (pour cartes/cards)
- kpi_recommendations.csv    : recommandations metier generees

Usage : python -m src.export_powerbi
"""

from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from src.preprocess import CLEAN_EVENT_LOG_PATH, CASE_ID_COL, ACTIVITY_COL, TIMESTAMP_COL
from src.performance_analysis import RESOURCE_COL
from src.business_analysis import CONFORMANCE_REPORT_PATH, KPI_SUMMARY_PATH
from src.train_model import (
    MODELS_DIR, VENDOR_COL, ITEM_CATEGORY_COL, DOC_TYPE_COL, SPEND_CLASS_COL, AMOUNT_COL,
    CLASSIFIER_PATH, REGRESSOR_PATH, PREFIX_DATASET_PATH,
)
import json

BASE_DIR = Path(__file__).resolve().parent.parent
EXPORT_DIR = BASE_DIR / "powerbi_export"

COMPANY_COL = "case:Company"
SOURCE_COL = "case:Source"


def export_fact_cases(df: pd.DataFrame) -> pd.DataFrame:
    per_case = df.groupby(CASE_ID_COL)[TIMESTAMP_COL].agg(["min", "max", "count"])
    per_case.columns = ["case_start", "case_end", "n_events"]
    per_case["duration_hours"] = (per_case["case_end"] - per_case["case_start"]).dt.total_seconds() / 3600
    per_case["duration_days"] = per_case["duration_hours"] / 24

    case_attrs_cols = {
        "vendor": VENDOR_COL, "company": COMPANY_COL, "item_category": ITEM_CATEGORY_COL,
        "document_type": DOC_TYPE_COL, "spend_classification": SPEND_CLASS_COL, "source": SOURCE_COL,
    }
    attrs = {}
    for out_name, col in case_attrs_cols.items():
        if col in df.columns:
            attrs[out_name] = df.groupby(CASE_ID_COL)[col].first()
    case_attrs = pd.DataFrame(attrs)

    amount_final = pd.to_numeric(df[AMOUNT_COL], errors="coerce").groupby(df[CASE_ID_COL]).last()
    case_attrs["amount_final"] = amount_final

    conformance = pd.read_csv(CONFORMANCE_REPORT_PATH).set_index("case_id")

    fact_cases = per_case.join(case_attrs).join(
        conformance[["trace_fitness", "is_fit", "missing_tokens", "remaining_tokens"]]
    ).reset_index().rename(columns={CASE_ID_COL: "case_id"})

    fact_cases.to_csv(EXPORT_DIR / "fact_cases.csv", index=False)
    return fact_cases


def export_case_predictions() -> None:
    prefix_df = pd.read_parquet(PREFIX_DATASET_PATH)

    # Prend l'etat "mi-parcours" de chaque cas echantillonne : plus informatif
    # pour comparer prediction vs realite qu'une prediction en tout debut ou
    # tout fin de cas (ou il ne reste presque plus rien a predire).
    case_size = prefix_df.groupby("case_id")["prefix_length"].transform("max")
    prefix_df["progress_pct"] = prefix_df["prefix_length"] / (case_size + 1)
    mid_rows = (
        prefix_df.assign(dist=(prefix_df["progress_pct"] - 0.5).abs())
        .sort_values("dist")
        .groupby("case_id")
        .first()
        .reset_index()
    )

    # Le jeu de features est enregistre avec le modele a l'entrainement.
    clf_bundle = joblib.load(CLASSIFIER_PATH)
    pipeline, classes = clf_bundle["pipeline"], clf_bundle["classes"]
    X = mid_rows[clf_bundle["feature_cols"]]
    late_idx = classes.index("LATE") if "LATE" in classes else 0
    proba = pipeline.predict_proba(X)[:, late_idx]

    regressor = joblib.load(REGRESSOR_PATH)
    pred_remaining_hours = np.expm1(regressor.predict(X)).clip(min=0)

    out = mid_rows[[
        "case_id", "prefix_length", "progress_pct", "current_activity", "vendor",
        "item_category", "document_type", "elapsed_hours", "amount",
        "n_distinct_activities", "n_rework", "max_gap_hours",
        "outcome", "remaining_hours",
    ]].copy()
    out = out.rename(columns={"outcome": "actual_label", "remaining_hours": "actual_remaining_hours"})
    out["predicted_late_probability"] = proba
    out["predicted_label"] = np.where(proba >= 0.5, "LATE", "ON_TIME")
    out["predicted_remaining_hours"] = pred_remaining_hours

    out.to_csv(EXPORT_DIR / "fact_case_predictions.csv", index=False)


def export_dim_tables() -> None:
    pd.read_csv(CONFORMANCE_REPORT_PATH).to_csv(EXPORT_DIR / "dim_conformance.csv", index=False)
    pd.read_csv(MODELS_DIR / "performance_transitions.csv").to_csv(EXPORT_DIR / "dim_bottlenecks.csv", index=False)
    pd.read_csv(MODELS_DIR / "performance_rework.csv").to_csv(EXPORT_DIR / "dim_rework.csv", index=False)
    pd.read_csv(MODELS_DIR / "performance_resources.csv").rename(
        columns={RESOURCE_COL: "resource"}
    ).to_csv(EXPORT_DIR / "dim_resources.csv", index=False)


def export_dim_variants(df: pd.DataFrame) -> None:
    variants = (
        df.sort_values([CASE_ID_COL, TIMESTAMP_COL], kind="stable")
        .groupby(CASE_ID_COL)[ACTIVITY_COL]
        .apply(lambda acts: " -> ".join(acts))
        .value_counts()
        .reset_index()
    )
    variants.columns = ["variant", "n_cases"]
    variants["variant_id"] = range(1, len(variants) + 1)
    variants.to_csv(EXPORT_DIR / "dim_variants.csv", index=False)


def export_kpi_tables() -> None:
    kpis = json.loads(KPI_SUMMARY_PATH.read_text(encoding="utf-8"))

    overview = {k: v for k, v in kpis.items() if not isinstance(v, list)}
    pd.DataFrame([overview]).to_csv(EXPORT_DIR / "kpi_overview.csv", index=False)

    pd.DataFrame({"recommendation": kpis["recommendations"]}).to_csv(
        EXPORT_DIR / "kpi_recommendations.csv", index=False
    )


def main() -> None:
    EXPORT_DIR.mkdir(exist_ok=True)
    df = pd.read_parquet(CLEAN_EVENT_LOG_PATH)

    fact_cases = export_fact_cases(df)
    print(f"fact_cases.csv : {len(fact_cases)} cas")

    export_case_predictions()
    print("fact_case_predictions.csv : OK")

    export_dim_tables()
    print("dim_conformance.csv / dim_bottlenecks.csv / dim_rework.csv / dim_resources.csv : OK")

    export_dim_variants(df)
    print("dim_variants.csv : OK")

    export_kpi_tables()
    print("kpi_overview.csv / kpi_recommendations.csv : OK")

    print(f"\nExport termine dans : {EXPORT_DIR}")


if __name__ == "__main__":
    main()
