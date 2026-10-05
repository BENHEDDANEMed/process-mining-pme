"""Phase 4 - Evaluation des deux modeles XGBoost sur le jeu de test.

L'accuracy seule est trompeuse quand les classes sont desequilibrees (75% de
cas a l'heure) : un modele qui repondrait toujours ON_TIME afficherait 75%
d'accuracy sans detecter le moindre retard. On rapporte donc aussi le ROC AUC,
le rappel sur la classe LATE et une comparaison a des baselines naives.
"""

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score, balanced_accuracy_score, f1_score, confusion_matrix,
    roc_auc_score, average_precision_score, precision_score, recall_score,
    mean_absolute_error, root_mean_squared_error,
)
import joblib

from src.train_model import (
    CLASSIFIER_PATH, REGRESSOR_PATH, PREFIX_DATASET_PATH, temporal_train_test_split,
)


def _feature_cols() -> list[str]:
    """Colonnes de features telles qu'enregistrees a l'entrainement.

    joblib.load deserialise ici des modeles produits localement par
    src/train_model.py, jamais un fichier d'origine externe.
    """
    bundle = joblib.load(CLASSIFIER_PATH)
    cols = bundle.get("feature_cols")
    if cols:
        return cols
    raise RuntimeError("Le classifieur ne contient pas feature_cols : relancer train_model.")


def evaluate_classifier(test_df: pd.DataFrame, feature_cols: list[str]) -> None:
    bundle = joblib.load(CLASSIFIER_PATH)
    pipeline, classes = bundle["pipeline"], bundle["classes"]
    threshold_h = bundle.get("late_threshold_hours")
    decision_threshold = bundle.get("decision_threshold", 0.5)
    class_to_idx = {c: i for i, c in enumerate(classes)}
    late = class_to_idx["LATE"]

    X_test = test_df[feature_cols]
    y_test = test_df["outcome"].map(class_to_idx)
    y_proba = pipeline.predict_proba(X_test)[:, late]
    y_pred_default = pipeline.predict(X_test)
    y_pred_tuned = np.where(y_proba >= decision_threshold, late, 1 - late)

    print("=== Classifieur (risque de retard) ===")
    if threshold_h:
        print(f"Seuil de retard : cas dont la duree depasse {threshold_h:.0f} h ({threshold_h / 24:.0f} j)")
    print(f"Part reelle de LATE dans le test : {(y_test == late).mean():.1%}")
    print()
    print(f"ROC AUC             : {roc_auc_score(y_test, y_proba):.4f}   (0.5 = hasard, ne depend pas du seuil)")
    print(f"PR AUC (moy. prec.) : {average_precision_score(y_test, y_proba):.4f}")
    print()

    for label, y_pred in [("Seuil par defaut (0.5)", y_pred_default),
                           ("Seuil retenu par validation (" + f"{decision_threshold:.3f})", y_pred_tuned)]:
        print(f"--- {label} ---")
        print(f"Accuracy            : {accuracy_score(y_test, y_pred):.4f}")
        print(f"Balanced accuracy   : {balanced_accuracy_score(y_test, y_pred):.4f}")
        print(f"F1 (macro)          : {f1_score(y_test, y_pred, average='macro'):.4f}")
        print(f"Precision (LATE)    : {precision_score(y_test, y_pred, pos_label=late):.4f}")
        print(f"Rappel (LATE)       : {recall_score(y_test, y_pred, pos_label=late):.4f}")
        print()

    print("Baselines de reference :")
    majority = np.full_like(y_test, y_test.mode()[0])
    print(f"  Toujours la classe majoritaire -> accuracy {accuracy_score(y_test, majority):.4f}, "
          f"rappel LATE {recall_score(y_test, majority, pos_label=late, zero_division=0):.4f}")
    print()

    cm = confusion_matrix(y_test, y_pred_tuned)
    print("Matrice de confusion au seuil retenu (lignes = reel, colonnes = predit) :")
    print(pd.DataFrame(cm, index=classes, columns=classes))


def evaluate_regressor(test_df: pd.DataFrame, train_df: pd.DataFrame, feature_cols: list[str]) -> None:
    pipeline = joblib.load(REGRESSOR_PATH)

    X_test = test_df[feature_cols]
    y_test = test_df["remaining_hours"].clip(lower=0)
    y_pred = np.expm1(pipeline.predict(X_test)).clip(min=0)

    mae = mean_absolute_error(y_test, y_pred)
    rmse = root_mean_squared_error(y_test, y_pred)

    print("\n=== Regresseur (temps restant) ===")
    print(f"MAE  : {mae:.1f} h ({mae / 24:.1f} j)")
    print(f"RMSE : {rmse:.1f} h ({rmse / 24:.1f} j)")

    naive = np.full_like(y_test, train_df["remaining_hours"].clip(lower=0).median(), dtype=float)
    mae_naive = mean_absolute_error(y_test, naive)
    gain = (1 - mae / mae_naive) * 100 if mae_naive else 0.0
    print(f"\nBaseline (mediane du train) : MAE {mae_naive:.1f} h ({mae_naive / 24:.1f} j)")
    print(f"Gain du modele sur la baseline : {gain:.1f}%")


def main() -> None:
    prefix_df = pd.read_parquet(PREFIX_DATASET_PATH)
    train_df, test_df = temporal_train_test_split(prefix_df)
    feature_cols = _feature_cols()

    evaluate_classifier(test_df, feature_cols)
    evaluate_regressor(test_df, train_df, feature_cols)


if __name__ == "__main__":
    main()
