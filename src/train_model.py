"""Phase 4 - Feature engineering par prefixes + entrainement de deux modeles XGBoost
sur le processus Purchase-to-Pay (BPI Challenge 2019) :
- classifieur : risque de retard (cas dans le quartile le plus lent)
- regresseur  : temps restant avant cloture du cas (en heures)

Trois corrections majeures par rapport a la version initiale (accuracy 48.8%,
soit sous le niveau du hasard) :

1. CENSURE TEMPORELLE. Le log s'arrete mi-janvier 2019 : les cas demarres juste
   avant la fin sont tronques, leur duree observee est artificiellement courte
   et ils etaient etiquetes ON_TIME a tort. Resultat : 59% de LATE en train
   contre 14% en test, donc un modele systematiquement a cote. On ne garde
   desormais que les cas (a) reellement clotures - derniere activite terminale -
   et (b) demarres au moins CENSORING_HORIZON_DAYS avant la fin effective du
   log, de sorte qu'un cas lent ait eu le temps de se terminer.

2. FEATURES. Aux 3 features numeriques initiales s'ajoutent l'historique du
   prefixe (activites deja realisees, rework, rythme et plus longue pause) et
   les attributs metier du cas (societe, categorie d'achat, type d'article...).

3. DEFINITION DU RETARD. Seuil calcule sur le seul jeu d'entrainement (plus de
   fuite de donnees) et fixe au 3e quartile : "en retard" = dans le quart des
   cas les plus lents, plus actionnable pour une PME que "plus lent que la
   moitie". Le desequilibre de classes qui en decoule est compense par
   scale_pos_weight.
"""

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBClassifier, XGBRegressor
import joblib

from src.discover_process import MODELS_DIR
from src.preprocess import CLEAN_EVENT_LOG_PATH, CASE_ID_COL, ACTIVITY_COL, TIMESTAMP_COL

AMOUNT_COL = "Cumulative net worth (EUR)"
VENDOR_COL = "case:Vendor"
ITEM_CATEGORY_COL = "case:Item Category"
DOC_TYPE_COL = "case:Document Type"
SPEND_CLASS_COL = "case:Spend classification text"
SPEND_AREA_COL = "case:Spend area text"
COMPANY_COL = "case:Company"
ITEM_TYPE_COL = "case:Item Type"
SOURCE_COL = "case:Source"
GR_BASED_COL = "case:GR-Based Inv. Verif."
GOODS_RECEIPT_COL = "case:Goods Receipt"

# --- Correction 1 : censure temporelle -------------------------------------
# Le log contient 7 evenements aberrants jusqu'en 2020 ; le quantile 99.9%
# donne la vraie fin d'observation (mi-janvier 2019).
EFFECTIVE_LOG_END_QUANTILE = 0.999
# p90 de la duree des cas clotures = 127 jours ; 150 laisse une marge pour
# qu'un cas lent ait pu se terminer avant la fin du log.
CENSORING_HORIZON_DAYS = 150
# Activites qui marquent une vraie fin de dossier Purchase-to-Pay : facture
# soldee, ou ligne de commande supprimee (abandon).
TERMINAL_ACTIVITIES = {"Clear Invoice", "Delete Purchase Order Item"}

# --- Correction 3 : definition du retard ------------------------------------
LATE_QUANTILE = 0.75

TOP_N_ACTIVITIES = 10
TOP_N_VENDORS = 15
TOP_N_ITEM_CATEGORIES = 10
TOP_N_GENERIC = 12
TEST_SIZE = 0.2

SAMPLE_N_CASES = 60_000
RANDOM_STATE = 42

CLASSIFIER_PATH = MODELS_DIR / "xgboost_classifier.pkl"
REGRESSOR_PATH = MODELS_DIR / "xgboost_regressor.pkl"
PREFIX_DATASET_PATH = MODELS_DIR / "prefix_dataset.parquet"

# --- Correction 2 : features -------------------------------------------------
FEATURE_COLS_NUM = [
    "prefix_length",
    "elapsed_hours",
    "amount_log",
    "n_distinct_activities",
    "n_rework",
    "hours_since_last_event",
    "mean_hours_between_events",
    "max_gap_hours",
    "start_dayofweek",
    "start_month",
    "current_dayofweek",
]
FEATURE_COLS_CAT = [
    "current_activity",
    "vendor",
    "item_category",
    "document_type",
    "spend_area",
    "company",
    "item_type",
    "source",
    "gr_based_inv_verif",
    "goods_receipt",
]
# Renseignee dynamiquement par build_prefix_dataset : indicateurs
# "activite X deja realisee dans ce cas".
FEATURE_COLS_FLAGS: list[str] = []


def _top_n_bucket(series: pd.Series, n: int) -> pd.Series:
    top = series.value_counts().head(n).index.tolist()
    return series.where(series.isin(top), "OTHER").fillna("UNKNOWN")


def _safe_cat(df: pd.DataFrame, col: str, n: int = TOP_N_GENERIC) -> pd.Series:
    if col not in df.columns:
        return pd.Series("UNKNOWN", index=df.index)
    return _top_n_bucket(df[col].astype("string"), n)


def select_uncensored_cases(df: pd.DataFrame) -> pd.DataFrame:
    """Ne garde que les cas clotures et demarres assez tot pour ne pas etre tronques."""
    log_end = df[TIMESTAMP_COL].quantile(EFFECTIVE_LOG_END_QUANTILE)
    cutoff = log_end - pd.Timedelta(days=CENSORING_HORIZON_DAYS)

    ordered = df.sort_values([CASE_ID_COL, TIMESTAMP_COL], kind="stable")
    grouped = ordered.groupby(CASE_ID_COL, sort=False)
    case_start = grouped[TIMESTAMP_COL].min()
    last_activity = grouped[ACTIVITY_COL].last()

    keep = case_start.index[
        (case_start <= cutoff) & last_activity.isin(TERMINAL_ACTIVITIES)
    ]
    n_before = df[CASE_ID_COL].nunique()
    out = df[df[CASE_ID_COL].isin(keep)].copy()
    print(
        f"Censure temporelle : fin de log effective {log_end:%Y-%m-%d}, "
        f"cas demarres apres {cutoff:%Y-%m-%d} ou non clotures ecartes "
        f"-> {out[CASE_ID_COL].nunique()}/{n_before} cas conserves"
    )
    return out


def sample_cases(df: pd.DataFrame, n: int = SAMPLE_N_CASES, seed: int = RANDOM_STATE) -> pd.DataFrame:
    case_ids = df[CASE_ID_COL].unique()
    if len(case_ids) <= n:
        return df
    rng = np.random.default_rng(seed)
    sampled = rng.choice(case_ids, size=n, replace=False)
    return df[df[CASE_ID_COL].isin(sampled)].copy()


def build_prefix_dataset(df: pd.DataFrame) -> pd.DataFrame:
    global FEATURE_COLS_FLAGS

    df = df.sort_values([CASE_ID_COL, TIMESTAMP_COL], kind="stable").reset_index(drop=True)
    df[AMOUNT_COL] = pd.to_numeric(df[AMOUNT_COL], errors="coerce")

    top_activities = df[ACTIVITY_COL].value_counts().head(TOP_N_ACTIVITIES).index.tolist()

    grouped = df.groupby(CASE_ID_COL, sort=False)
    case_size = grouped[CASE_ID_COL].transform("size")
    prefix_length = grouped.cumcount() + 1
    case_start = grouped[TIMESTAMP_COL].transform("min")
    case_end = grouped[TIMESTAMP_COL].transform("max")

    # Historique du prefixe : tout est cumulatif dans l'ordre chronologique, donc
    # aucune information posterieure a l'evenement courant n'est utilisee.
    prev_ts = grouped[TIMESTAMP_COL].shift(1)
    gap_hours = ((df[TIMESTAMP_COL] - prev_ts).dt.total_seconds() / 3600).fillna(0.0)
    max_gap = gap_hours.groupby(df[CASE_ID_COL]).cummax()

    is_first_occurrence = ~df.duplicated(subset=[CASE_ID_COL, ACTIVITY_COL], keep="first")
    n_distinct = is_first_occurrence.groupby(df[CASE_ID_COL]).cumsum()

    elapsed_hours = (df[TIMESTAMP_COL] - case_start).dt.total_seconds() / 3600

    out = pd.DataFrame({
        "case_id": df[CASE_ID_COL],
        "case_start": case_start,
        "prefix_length": prefix_length,
        "elapsed_hours": elapsed_hours,
        "remaining_hours": (case_end - df[TIMESTAMP_COL]).dt.total_seconds() / 3600,
        "current_activity": df[ACTIVITY_COL].where(df[ACTIVITY_COL].isin(top_activities), "OTHER"),
        "amount": df[AMOUNT_COL],
        "amount_log": np.log1p(df[AMOUNT_COL].clip(lower=0)),
        "n_distinct_activities": n_distinct,
        "n_rework": prefix_length - n_distinct,
        "hours_since_last_event": gap_hours,
        "mean_hours_between_events": elapsed_hours / prefix_length,
        "max_gap_hours": max_gap,
        "start_dayofweek": case_start.dt.dayofweek,
        "start_month": case_start.dt.month,
        "current_dayofweek": df[TIMESTAMP_COL].dt.dayofweek,
        "vendor": _safe_cat(df, VENDOR_COL, TOP_N_VENDORS),
        "item_category": _safe_cat(df, ITEM_CATEGORY_COL, TOP_N_ITEM_CATEGORIES),
        "document_type": _safe_cat(df, DOC_TYPE_COL),
        "spend_area": _safe_cat(df, SPEND_AREA_COL),
        "company": _safe_cat(df, COMPANY_COL),
        "item_type": _safe_cat(df, ITEM_TYPE_COL),
        "source": _safe_cat(df, SOURCE_COL),
        "gr_based_inv_verif": _safe_cat(df, GR_BASED_COL, 4),
        "goods_receipt": _safe_cat(df, GOODS_RECEIPT_COL, 4),
    })

    # Indicateurs "cette activite a deja eu lieu dans le cas" : pour un
    # Purchase-to-Pay, savoir si la reception ou la facture est deja passee est
    # bien plus informatif que la seule activite courante.
    flag_cols = []
    for act in top_activities:
        col = "done_" + "".join(ch if ch.isalnum() else "_" for ch in act.lower())[:40]
        out[col] = (df[ACTIVITY_COL] == act).groupby(df[CASE_ID_COL]).cummax().astype(int)
        flag_cols.append(col)
    FEATURE_COLS_FLAGS = flag_cols

    # Exclut les cas a 1 seul evenement et le prefixe complet de chaque cas
    # (trivial : plus rien a predire).
    out = out[(case_size >= 2) & (prefix_length < case_size)].reset_index(drop=True)
    out = out.dropna(subset=["amount"]).reset_index(drop=True)
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


def case_total_hours(part: pd.DataFrame) -> pd.Series:
    """Duree totale du cas, reconstituee depuis n'importe quel prefixe."""
    totals = part["elapsed_hours"] + part["remaining_hours"]
    return totals.groupby(part["case_id"]).transform("max")


def add_late_labels(train_df: pd.DataFrame, test_df: pd.DataFrame):
    """Etiquette LATE/ON_TIME avec un seuil appris sur le seul jeu d'entrainement."""
    train_totals = case_total_hours(train_df)
    threshold = float(
        train_totals.groupby(train_df["case_id"]).first().quantile(LATE_QUANTILE)
    )

    train_df["outcome"] = np.where(train_totals > threshold, "LATE", "ON_TIME")
    test_df["outcome"] = np.where(case_total_hours(test_df) > threshold, "LATE", "ON_TIME")
    return train_df, test_df, threshold


def build_pipeline(model) -> Pipeline:
    preprocessor = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=20), FEATURE_COLS_CAT),
        ("num", "passthrough", FEATURE_COLS_NUM + FEATURE_COLS_FLAGS),
    ])
    return Pipeline([("preprocess", preprocessor), ("model", model)])


def main() -> None:
    df = pd.read_parquet(CLEAN_EVENT_LOG_PATH)
    df = select_uncensored_cases(df)
    df = sample_cases(df)
    print(f"Cas utilises pour l'entrainement : {df[CASE_ID_COL].nunique()}")

    prefix_df = build_prefix_dataset(df)
    train_df, test_df = temporal_train_test_split(prefix_df)
    train_df, test_df, threshold = add_late_labels(train_df, test_df)
    prefix_df = pd.concat([train_df, test_df], ignore_index=True)
    prefix_df.to_parquet(PREFIX_DATASET_PATH, index=False)

    print(f"Dataset de prefixes : {len(prefix_df)} lignes, {prefix_df['case_id'].nunique()} cas")
    print(f"Seuil de retard (q{LATE_QUANTILE:.2f} du train) : {threshold:.0f} h ({threshold / 24:.0f} j)")
    print(f"Train : {len(train_df)} lignes ({(train_df['outcome'] == 'LATE').mean():.1%} LATE)")
    print(f"Test  : {len(test_df)} lignes ({(test_df['outcome'] == 'LATE').mean():.1%} LATE)")

    feature_cols = FEATURE_COLS_CAT + FEATURE_COLS_NUM + FEATURE_COLS_FLAGS
    print(f"Nombre de features : {len(feature_cols)}")
    X_train, X_test = train_df[feature_cols], test_df[feature_cols]

    # --- Classification : risque de retard ---
    classes = ["ON_TIME", "LATE"]
    class_to_idx = {c: i for i, c in enumerate(classes)}
    y_train_clf = train_df["outcome"].map(class_to_idx)

    n_neg, n_pos = int((y_train_clf == 0).sum()), int((y_train_clf == 1).sum())
    scale_pos_weight = n_neg / max(n_pos, 1)

    clf_pipeline = build_pipeline(XGBClassifier(
        n_estimators=400, max_depth=7, learning_rate=0.08,
        subsample=0.8, colsample_bytree=0.8, min_child_weight=5,
        reg_lambda=1.5, scale_pos_weight=scale_pos_weight,
        eval_metric="auc", random_state=RANDOM_STATE, n_jobs=-1,
    ))
    clf_pipeline.fit(X_train, y_train_clf)
    joblib.dump(
        {"pipeline": clf_pipeline, "classes": classes,
         "late_threshold_hours": threshold, "feature_cols": feature_cols},
        CLASSIFIER_PATH,
    )
    print(f"Classifieur sauvegarde : {CLASSIFIER_PATH}")

    # --- Regression : temps restant (log1p, distribution tres asymetrique) ---
    y_train_reg = np.log1p(train_df["remaining_hours"].clip(lower=0))
    reg_pipeline = build_pipeline(XGBRegressor(
        n_estimators=500, max_depth=7, learning_rate=0.08,
        subsample=0.8, colsample_bytree=0.8, min_child_weight=5,
        reg_lambda=1.5, random_state=RANDOM_STATE, n_jobs=-1,
    ))
    reg_pipeline.fit(X_train, y_train_reg)
    joblib.dump(reg_pipeline, REGRESSOR_PATH)
    print(f"Regresseur sauvegarde : {REGRESSOR_PATH}")


if __name__ == "__main__":
    main()
