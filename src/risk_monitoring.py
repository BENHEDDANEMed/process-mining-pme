"""Monitoring des predictions : classement en buckets de risque, vue
d'ensemble agregee, et trajectoire de risque d'un cas a travers ses etapes.

Ce projet n'a ni flux d'evenements en direct ni base de donnees : le dataset
est un historique fige (voir README). "Suivre l'evolution du risque d'un cas
dans le temps" est donc honnetement reinterprete comme la progression du
risque predit A TRAVERS LES ETAPES DU CAS lui-meme (`case_risk_trajectory`),
pas un historique calendaire fabrique -- l'API expose cette nuance
explicitement plutot que de la laisser silencieuse.
"""

from __future__ import annotations

import pandas as pd

from src.config import ProcessConfig

RISK_LABELS = ["LOW", "MEDIUM", "HIGH"]


def bucket_risk(proba: pd.Series, cfg: ProcessConfig) -> pd.Series:
    """LOW en dessous de `low_max`, HIGH au-dessus de `high_min`, MEDIUM entre les deux."""
    thresholds = cfg.risk_thresholds
    return pd.cut(
        proba,
        bins=[-float("inf"), thresholds.low_max, thresholds.high_min, float("inf")],
        labels=RISK_LABELS,
    ).astype(str)


def mid_progress_rows(prefix_df: pd.DataFrame) -> pd.DataFrame:
    """Pour chaque cas, la ligne dont la progression (prefix_length / n_steps)
    est la plus proche de 50% -- plus informatif pour comparer prediction vs
    realite qu'un etat tout au debut ou tout a la fin d'un cas (ou il ne reste
    presque plus rien a predire). Logique partagee avec src/export_powerbi.py,
    qui construit fact_case_predictions.csv a partir de cette meme fonction.
    """
    if prefix_df.empty:
        return prefix_df

    case_size = prefix_df.groupby("case_id")["prefix_length"].transform("max")
    with_progress = prefix_df.assign(progress_pct=prefix_df["prefix_length"] / (case_size + 1))
    return (
        with_progress.assign(dist=(with_progress["progress_pct"] - 0.5).abs())
        .sort_values("dist")
        .groupby("case_id")
        .first()
        .reset_index()
    )


def monitoring_overview(df: pd.DataFrame, cfg: ProcessConfig, late_threshold_hours: float) -> dict:
    """Vue d'ensemble : effectifs par bucket, temps restant moyen par bucket,
    et nombre de cas dont le delai deja ecoule + le temps restant predit
    depasserait le seuil de retard (`late_threshold_hours`, du bundle du
    classifieur) -- une approximation du SLA, pas une donnee contractuelle.
    """
    if df.empty:
        return {
            "total_cases": 0,
            "counts": {label: 0 for label in RISK_LABELS},
            "avg_remaining_hours_by_bucket": {label: None for label in RISK_LABELS},
            "sla_at_risk_count": 0,
        }

    buckets = bucket_risk(df["predicted_late_probability"], cfg)
    counts = buckets.value_counts().reindex(RISK_LABELS, fill_value=0)
    avg_remaining = df["predicted_remaining_hours"].groupby(buckets).mean().reindex(RISK_LABELS)
    sla_at_risk = (df["elapsed_hours"] + df["predicted_remaining_hours"]) > late_threshold_hours

    return {
        "total_cases": int(len(df)),
        "counts": {label: int(counts[label]) for label in RISK_LABELS},
        "avg_remaining_hours_by_bucket": {
            label: (float(avg_remaining[label]) if pd.notna(avg_remaining[label]) else None) for label in RISK_LABELS
        },
        "sla_at_risk_count": int(sla_at_risk.sum()),
    }


def case_risk_trajectory(pipeline, classes: list[str], case_rows: pd.DataFrame, feature_cols: list[str]) -> pd.DataFrame:
    """Probabilite de retard a CHAQUE etape connue d'un cas -- un seul appel
    batche a predict_proba sur toutes ses lignes, jamais un appel par etape."""
    late_idx = classes.index("LATE")
    ordered = case_rows.sort_values("prefix_length")
    proba = pipeline.predict_proba(ordered[feature_cols])[:, late_idx]
    return pd.DataFrame({
        "prefix_length": ordered["prefix_length"].to_numpy(),
        "elapsed_hours": ordered["elapsed_hours"].to_numpy(),
        "proba_late": proba,
    })
