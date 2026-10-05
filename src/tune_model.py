"""Recherche d'hyperparametres pour les deux modeles XGBoost (classifieur de
risque de retard, regresseur de temps restant), pour ameliorer accuracy /
precision / rappel / ROC AUC / MAE par rapport aux valeurs choisies a la main
dans train_model.py.

Recherche par validation croisee sur le train uniquement (RandomizedSearchCV) ;
le test (jamais vu pendant la recherche) sert a la comparaison finale contre
les modeles actuellement livres. Un modele n'est remplace que si le test
confirme un gain reel (pas de decision prise sur le score de validation croisee
seul, qui peut surestimer legerement).
"""

import time

import numpy as np
import pandas as pd
import joblib
from scipy.stats import randint, uniform
from sklearn.model_selection import RandomizedSearchCV
from sklearn.metrics import accuracy_score, mean_absolute_error, recall_score, roc_auc_score
from xgboost import XGBClassifier, XGBRegressor

from src.train_model import (
    CLASSIFIER_PATH,
    FEATURE_COLS_CAT,
    FEATURE_COLS_NUM,
    PREFIX_DATASET_PATH,
    REGRESSOR_PATH,
    RANDOM_STATE,
    build_pipeline,
    temporal_train_test_split,
)

N_ITER = 12
CV = 3

PARAM_DIST = {
    "model__n_estimators": randint(200, 700),
    "model__max_depth": randint(4, 10),
    "model__learning_rate": uniform(0.02, 0.18),
    "model__subsample": uniform(0.6, 0.4),
    "model__colsample_bytree": uniform(0.6, 0.4),
    "model__min_child_weight": randint(1, 10),
    "model__reg_lambda": uniform(0.5, 3.0),
    "model__gamma": uniform(0.0, 0.5),
}


def _feature_cols(df: pd.DataFrame) -> list[str]:
    flag_cols = [c for c in df.columns if c.startswith("done_")]
    return FEATURE_COLS_CAT + FEATURE_COLS_NUM + flag_cols


def temporal_cv_splits(df: pd.DataFrame, n_splits: int = 3):
    """Folds chaines (expanding window), groupes par cas et ordonnes par
    case_start -- comme temporal_train_test_split, mais en plusieurs folds.

    Un K-fold aleatoire (shuffle=True) melange les periodes : la recherche
    d'hyperparametres choisit alors des modeles qui excellent en IID sur le
    train mais generalisent moins bien vers le futur (le vrai probleme, celui
    que la censure temporelle corrige deja par ailleurs). Ici, chaque fold
    entraine sur le passe et valide sur une tranche plus recente, jamais vue.
    """
    df = df.reset_index(drop=True)
    case_starts = df.groupby("case_id")["case_start"].first().sort_values()
    case_chunks = np.array_split(case_starts.index.to_numpy(), n_splits + 1)
    positions_by_case = df.groupby("case_id").indices

    def positions_for(cases):
        if len(cases) == 0:
            return np.array([], dtype=int)
        return np.concatenate([positions_by_case[c] for c in cases])

    folds = []
    for i in range(n_splits):
        train_cases = np.concatenate(case_chunks[: i + 1])
        val_cases = case_chunks[i + 1]
        folds.append((positions_for(train_cases), positions_for(val_cases)))
    return folds


def tune_classifier(train_df: pd.DataFrame, feature_cols: list[str]):
    train_df = train_df.reset_index(drop=True)
    X = train_df[feature_cols]
    y = (train_df["outcome"] == "LATE").astype(int)
    scale_pos_weight = (y == 0).sum() / max((y == 1).sum(), 1)

    base = XGBClassifier(
        eval_metric="auc", scale_pos_weight=scale_pos_weight,
        random_state=RANDOM_STATE, n_jobs=-1,
    )
    search = RandomizedSearchCV(
        build_pipeline(base), PARAM_DIST, n_iter=N_ITER,
        scoring="roc_auc", cv=temporal_cv_splits(train_df, CV),
        random_state=RANDOM_STATE, n_jobs=1, verbose=1,
    )
    t0 = time.time()
    search.fit(X, y)
    print(f"Classifieur : recherche terminee en {time.time() - t0:.0f}s, "
          f"meilleur ROC AUC (CV train) = {search.best_score_:.4f}")
    print("Meilleurs parametres :", search.best_params_)
    return search.best_estimator_


def tune_regressor(train_df: pd.DataFrame, feature_cols: list[str]):
    train_df = train_df.reset_index(drop=True)
    X = train_df[feature_cols]
    y = np.log1p(train_df["remaining_hours"].clip(lower=0))

    base = XGBRegressor(random_state=RANDOM_STATE, n_jobs=-1)
    search = RandomizedSearchCV(
        build_pipeline(base), PARAM_DIST, n_iter=N_ITER,
        scoring="neg_mean_absolute_error", cv=temporal_cv_splits(train_df, CV),
        random_state=RANDOM_STATE, n_jobs=1, verbose=1,
    )
    t0 = time.time()
    search.fit(X, y)
    print(f"Regresseur : recherche terminee en {time.time() - t0:.0f}s, "
          f"meilleur MAE log-space (CV train) = {-search.best_score_:.4f}")
    print("Meilleurs parametres :", search.best_params_)
    return search.best_estimator_


def main() -> None:
    prefix_df = pd.read_parquet(PREFIX_DATASET_PATH)
    train_df, test_df = temporal_train_test_split(prefix_df)
    feature_cols = _feature_cols(prefix_df)
    X_test = test_df[feature_cols]

    # joblib.load : modeles produits localement par train_model.py, jamais une
    # source externe (meme trust boundary que backend/api.py).
    # --- Classifieur ---
    baseline_bundle = joblib.load(CLASSIFIER_PATH)
    baseline_clf, classes = baseline_bundle["pipeline"], baseline_bundle["classes"]
    late_idx = classes.index("LATE")
    y_test_clf = test_df["outcome"].map({c: i for i, c in enumerate(classes)})

    base_proba = baseline_clf.predict_proba(X_test)[:, late_idx]
    base_pred = baseline_clf.predict(X_test)
    base_auc = roc_auc_score(y_test_clf, base_proba)
    base_acc = accuracy_score(y_test_clf, base_pred)
    base_recall = recall_score(y_test_clf, base_pred, pos_label=late_idx)

    tuned_clf = tune_classifier(train_df, feature_cols)
    tuned_proba = tuned_clf.predict_proba(X_test)[:, late_idx]
    tuned_pred = tuned_clf.predict(X_test)
    tuned_auc = roc_auc_score(y_test_clf, tuned_proba)
    tuned_acc = accuracy_score(y_test_clf, tuned_pred)
    tuned_recall = recall_score(y_test_clf, tuned_pred, pos_label=late_idx)

    print("\n=== Classifieur : avant / apres (test, jamais vu pendant la recherche) ===")
    print(f"ROC AUC     : {base_auc:.4f} -> {tuned_auc:.4f}")
    print(f"Accuracy    : {base_acc:.4f} -> {tuned_acc:.4f}")
    print(f"Rappel LATE : {base_recall:.4f} -> {tuned_recall:.4f}")

    if tuned_auc > base_auc:
        joblib.dump(
            {"pipeline": tuned_clf, "classes": classes,
             "late_threshold_hours": baseline_bundle.get("late_threshold_hours"),
             "feature_cols": feature_cols},
            CLASSIFIER_PATH,
        )
        print("-> ROC AUC ameliore : classifieur remplace.")
    else:
        print("-> Pas d'amelioration du ROC AUC : modele actuel conserve.")

    # --- Regresseur ---
    baseline_reg = joblib.load(REGRESSOR_PATH)
    y_test_reg = test_df["remaining_hours"].clip(lower=0)
    base_mae = mean_absolute_error(y_test_reg, np.expm1(baseline_reg.predict(X_test)).clip(min=0))

    tuned_reg = tune_regressor(train_df, feature_cols)
    tuned_mae = mean_absolute_error(y_test_reg, np.expm1(tuned_reg.predict(X_test)).clip(min=0))

    print("\n=== Regresseur : avant / apres (test) ===")
    print(f"MAE (h) : {base_mae:.1f} -> {tuned_mae:.1f}")

    if tuned_mae < base_mae:
        joblib.dump(tuned_reg, REGRESSOR_PATH)
        print("-> MAE ameliore : regresseur remplace.")
    else:
        print("-> Pas d'amelioration du MAE : modele actuel conserve.")


if __name__ == "__main__":
    main()
