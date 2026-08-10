"""Phase 4 - Feature engineering par prefixes + entrainement de deux modeles XGBoost :
- classifieur : issue finale du dossier (APPROVED / DECLINED / CANCELLED)
- regresseur  : temps restant avant cloture (en heures)
"""

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBClassifier, XGBRegressor
import joblib

from src.discover_process import MODELS_DIR
from src.preprocess import CLEAN_EVENT_LOG_PATH, CASE_ID_COL, ACTIVITY_COL, TIMESTAMP_COL

AMOUNT_COL = "case:AMOUNT_REQ"
TOP_N_ACTIVITIES = 10
TEST_SIZE = 0.2

OUTCOME_ACTIVITIES = {
    "A_APPROVED": "APPROVED",
    "A_DECLINED": "DECLINED",
    "A_CANCELLED": "CANCELLED",
}

CLASSIFIER_PATH = MODELS_DIR / "xgboost_classifier.pkl"
REGRESSOR_PATH = MODELS_DIR / "xgboost_regressor.pkl"
PREFIX_DATASET_PATH = MODELS_DIR / "prefix_dataset.parquet"

FEATURE_COLS_NUM = ["prefix_length", "elapsed_hours", "amount"]
FEATURE_COLS_CAT = ["current_activity"]


def _case_outcomes(df: pd.DataFrame) -> pd.Series:
    """Une seule issue par cas : la premiere activite terminale rencontree."""
    terminal = df[df[ACTIVITY_COL].isin(OUTCOME_ACTIVITIES)]
    first_terminal = terminal.sort_values(TIMESTAMP_COL).groupby(CASE_ID_COL).first()
    return first_terminal[ACTIVITY_COL].map(OUTCOME_ACTIVITIES)


def build_prefix_dataset(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values([CASE_ID_COL, TIMESTAMP_COL]).reset_index(drop=True)
    df[AMOUNT_COL] = pd.to_numeric(df[AMOUNT_COL], errors="coerce")

    top_activities = df[ACTIVITY_COL].value_counts().head(TOP_N_ACTIVITIES).index.tolist()

    grouped = df.groupby(CASE_ID_COL, sort=False)
    case_size = grouped[CASE_ID_COL].transform("size")
    prefix_length = grouped.cumcount() + 1
    case_start = grouped[TIMESTAMP_COL].transform("min")
    case_end = grouped[TIMESTAMP_COL].transform("max")

    outcomes = _case_outcomes(df)

    out = pd.DataFrame({
        "case_id": df[CASE_ID_COL],
        "case_start": case_start,
        "prefix_length": prefix_length,
        "elapsed_hours": (df[TIMESTAMP_COL] - case_start).dt.total_seconds() / 3600,
        "remaining_hours": (case_end - df[TIMESTAMP_COL]).dt.total_seconds() / 3600,
        "current_activity": df[ACTIVITY_COL].where(df[ACTIVITY_COL].isin(top_activities), "OTHER"),
        "amount": df[AMOUNT_COL],
        "outcome": df[CASE_ID_COL].map(outcomes),
    })

    # Exclut les cas a 1 seul evenement et le prefixe complet de chaque cas
    # (trivial : plus rien a predire).
    out = out[(case_size >= 2) & (prefix_length < case_size)].reset_index(drop=True)
    out = out.dropna(subset=["outcome", "amount"]).reset_index(drop=True)
    return out


def temporal_train_test_split(prefix_df: pd.DataFrame, test_size: float = TEST_SIZE):
    case_starts = prefix_df.groupby("case_id")["case_start"].first().sort_values()
    n_test_cases = int(len(case_starts) * test_size)

    train_cases = set(case_starts.index[:-n_test_cases])
    test_cases = set(case_starts.index[-n_test_cases:])
    assert train_cases.isdisjoint(test_cases), "Fuite de donnees : chevauchement train/test"

    train_df = prefix_df[prefix_df["case_id"].isin(train_cases)].copy()
    test_df = prefix_df[prefix_df["case_id"].isin(test_cases)].copy()
    return train_df, test_df


def build_pipeline(model) -> Pipeline:
    preprocessor = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore"), FEATURE_COLS_CAT),
        ("num", "passthrough", FEATURE_COLS_NUM),
    ])
    return Pipeline([("preprocess", preprocessor), ("model", model)])


def main() -> None:
    df = pd.read_parquet(CLEAN_EVENT_LOG_PATH)
    prefix_df = build_prefix_dataset(df)
    prefix_df.to_parquet(PREFIX_DATASET_PATH, index=False)
    print(f"Dataset de prefixes : {len(prefix_df)} lignes, {prefix_df['case_id'].nunique()} cas")

    train_df, test_df = temporal_train_test_split(prefix_df)
    print(f"Train : {len(train_df)} lignes / Test : {len(test_df)} lignes")

    feature_cols = FEATURE_COLS_CAT + FEATURE_COLS_NUM
    X_train, X_test = train_df[feature_cols], test_df[feature_cols]

    # --- Classification : issue du dossier ---
    y_train_clf = train_df["outcome"]
    y_test_clf = test_df["outcome"]

    clf_pipeline = build_pipeline(XGBClassifier(
        n_estimators=200, max_depth=6, learning_rate=0.1,
        eval_metric="mlogloss", random_state=42,
    ))
    classes = sorted(y_train_clf.unique())
    class_to_idx = {c: i for i, c in enumerate(classes)}
    clf_pipeline.fit(X_train, y_train_clf.map(class_to_idx))
    joblib.dump({"pipeline": clf_pipeline, "classes": classes}, CLASSIFIER_PATH)
    print(f"Classifieur sauvegarde : {CLASSIFIER_PATH}")

    # --- Regression : temps restant (log1p, distribution tres asymetrique) ---
    y_train_reg = np.log1p(train_df["remaining_hours"].clip(lower=0))
    reg_pipeline = build_pipeline(XGBRegressor(
        n_estimators=300, max_depth=6, learning_rate=0.1, random_state=42,
    ))
    reg_pipeline.fit(X_train, y_train_reg)
    joblib.dump(reg_pipeline, REGRESSOR_PATH)
    print(f"Regresseur sauvegarde : {REGRESSOR_PATH}")


if __name__ == "__main__":
    main()
