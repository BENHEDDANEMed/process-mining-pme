"""Phase 4 - Evaluation des deux modeles XGBoost sur le jeu de test."""

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score, f1_score, confusion_matrix,
    mean_absolute_error, root_mean_squared_error,
)
import joblib

from src.train_model import (
    CLASSIFIER_PATH, REGRESSOR_PATH, PREFIX_DATASET_PATH,
    FEATURE_COLS_CAT, FEATURE_COLS_NUM, temporal_train_test_split,
)


def evaluate_classifier(test_df: pd.DataFrame) -> None:
    bundle = joblib.load(CLASSIFIER_PATH)
    pipeline, classes = bundle["pipeline"], bundle["classes"]
    class_to_idx = {c: i for i, c in enumerate(classes)}

    X_test = test_df[FEATURE_COLS_CAT + FEATURE_COLS_NUM]
    y_test = test_df["outcome"].map(class_to_idx)
    y_pred = pipeline.predict(X_test)

    acc = accuracy_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred, average="macro")
    cm = confusion_matrix(y_test, y_pred)

    print("=== Classifieur (issue du dossier) ===")
    print(f"Accuracy : {acc:.4f}")
    print(f"F1-score (macro) : {f1:.4f}")
    print(f"Classes : {classes}")
    print("Matrice de confusion :")
    print(pd.DataFrame(cm, index=classes, columns=classes))


def evaluate_regressor(test_df: pd.DataFrame) -> None:
    pipeline = joblib.load(REGRESSOR_PATH)

    X_test = test_df[FEATURE_COLS_CAT + FEATURE_COLS_NUM]
    y_test = test_df["remaining_hours"].clip(lower=0)
    y_pred = np.expm1(pipeline.predict(X_test)).clip(min=0)

    mae = mean_absolute_error(y_test, y_pred)
    rmse = root_mean_squared_error(y_test, y_pred)

    print("\n=== Regresseur (temps restant) ===")
    print(f"MAE  : {mae:.1f} h ({mae / 24:.1f} j)")
    print(f"RMSE : {rmse:.1f} h ({rmse / 24:.1f} j)")


def main() -> None:
    prefix_df = pd.read_parquet(PREFIX_DATASET_PATH)
    _, test_df = temporal_train_test_split(prefix_df)

    evaluate_classifier(test_df)
    evaluate_regressor(test_df)


if __name__ == "__main__":
    main()
