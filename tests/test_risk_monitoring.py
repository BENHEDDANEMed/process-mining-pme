"""Tests du monitoring des predictions (bucketing, vue d'ensemble, trajectoire)."""

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from src.config import RiskThresholds
from src.risk_monitoring import bucket_risk, case_risk_trajectory, mid_progress_rows, monitoring_overview


@pytest.fixture
def cfg_seuils(cfg):
    return replace(cfg, risk_thresholds=RiskThresholds(low_max=0.40, high_min=0.70))


def test_bucket_risk_classe_selon_les_seuils(cfg_seuils):
    proba = pd.Series([0.0, 0.40, 0.41, 0.70, 0.71, 1.0])
    buckets = bucket_risk(proba, cfg_seuils)

    assert list(buckets) == ["LOW", "LOW", "MEDIUM", "MEDIUM", "HIGH", "HIGH"]


def test_bucket_risk_respecte_des_seuils_personnalises(cfg):
    seuils_larges = replace(cfg, risk_thresholds=RiskThresholds(low_max=0.10, high_min=0.90))
    buckets = bucket_risk(pd.Series([0.5]), seuils_larges)

    assert list(buckets) == ["MEDIUM"]


def test_mid_progress_rows_choisit_l_etape_la_plus_proche_de_50_pourcent():
    prefix_df = pd.DataFrame({
        "case_id": ["a", "a", "a", "a"],
        "prefix_length": [1, 2, 3, 4],
    })
    # n_steps = 4 (max prefix_length) -> progress_pct = prefix_length / 5 = 0.2/0.4/0.6/0.8
    # le plus proche de 0.5 est prefix_length=3 (0.6, distance 0.1) vs prefix_length=2 (0.4, distance 0.1)
    # egalite : verifie juste que le resultat est l'un des deux, et qu'une seule ligne est gardee par cas.
    result = mid_progress_rows(prefix_df)

    assert len(result) == 1
    assert result.iloc[0]["prefix_length"] in (2, 3)


def test_mid_progress_rows_sur_un_dataset_vide():
    empty = pd.DataFrame(columns=["case_id", "prefix_length"])
    assert mid_progress_rows(empty).empty


def test_monitoring_overview_compte_les_buckets_et_le_sla(cfg_seuils):
    df = pd.DataFrame({
        "predicted_late_probability": [0.1, 0.5, 0.9],
        "predicted_remaining_hours": [10.0, 20.0, 30.0],
        "elapsed_hours": [0.0, 0.0, 1000.0],
    })
    overview = monitoring_overview(df, cfg_seuils, late_threshold_hours=100.0)

    assert overview["total_cases"] == 3
    assert overview["counts"] == {"LOW": 1, "MEDIUM": 1, "HIGH": 1}
    assert overview["avg_remaining_hours_by_bucket"]["LOW"] == pytest.approx(10.0)
    assert overview["sla_at_risk_count"] == 1  # seul le 3e (1000+30 > 100)


def test_monitoring_overview_sur_un_dataset_vide(cfg_seuils):
    empty = pd.DataFrame(columns=["predicted_late_probability", "predicted_remaining_hours", "elapsed_hours"])
    overview = monitoring_overview(empty, cfg_seuils, late_threshold_hours=100.0)

    assert overview["total_cases"] == 0
    assert overview["counts"] == {"LOW": 0, "MEDIUM": 0, "HIGH": 0}


def test_case_risk_trajectory_appelle_predict_proba_une_seule_fois():
    calls = []

    class _CountingPipeline:
        def predict_proba(self, X):
            calls.append(len(X))
            return np.tile([0.9, 0.1], (len(X), 1))

    case_rows = pd.DataFrame({
        "prefix_length": [3, 1, 2],
        "elapsed_hours": [30.0, 10.0, 20.0],
        "amount": [1, 2, 3],
    })
    trajectory = case_risk_trajectory(_CountingPipeline(), ["ON_TIME", "LATE"], case_rows, feature_cols=["amount"])

    assert calls == [3]  # un seul appel, sur les 3 lignes a la fois
    assert list(trajectory["prefix_length"]) == [1, 2, 3]  # trie par etape
    assert list(trajectory["proba_late"]) == pytest.approx([0.1, 0.1, 0.1])
