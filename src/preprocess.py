"""Phase 1 - Nettoyage du journal d'evenements et statistiques descriptives."""

import pandas as pd

from src.extract_log import RAW_EVENT_LOG_PATH, PROCESSED_DATA_DIR

CLEAN_EVENT_LOG_PATH = PROCESSED_DATA_DIR / "event_log_clean.parquet"

CASE_ID_COL = "case:concept:name"
ACTIVITY_COL = "concept:name"
TIMESTAMP_COL = "time:timestamp"
LIFECYCLE_COL = "lifecycle:transition"

MIN_EVENTS_PER_CASE = 2

# BPI2019 contient quelques timestamps aberrants (ex: 1948) issus d'erreurs de
# saisie dans le systeme source ; toute date hors de la periode reelle de
# collecte du log (2011-2020) est ecartee avant tout calcul de duree.
MIN_VALID_DATE = pd.Timestamp("2010-01-01", tz="UTC")
MAX_VALID_DATE = pd.Timestamp("2020-12-31", tz="UTC")


def clean_log(df: pd.DataFrame) -> pd.DataFrame:
    df = df.dropna(subset=[CASE_ID_COL, ACTIVITY_COL, TIMESTAMP_COL])

    # BPI2012 journalise START/SCHEDULE/COMPLETE pour les activites humaines ;
    # ne garder que les transitions COMPLETE evite de gonfler artificiellement
    # le graphe de process discovery avec des etats intermediaires.
    if LIFECYCLE_COL in df.columns:
        df = df[df[LIFECYCLE_COL] == "COMPLETE"].copy()

    df[TIMESTAMP_COL] = pd.to_datetime(df[TIMESTAMP_COL], utc=True)
    df = df[(df[TIMESTAMP_COL] >= MIN_VALID_DATE) & (df[TIMESTAMP_COL] <= MAX_VALID_DATE)]

    # BPI2019 contient ~8% de lignes strictement dupliquees (meme cas, meme
    # activite, meme timestamp, memes attributs) : probablement des doubles
    # ecritures dans le systeme source, a retirer avant tout calcul de KPI.
    df = df.drop_duplicates()

    df = df.sort_values([CASE_ID_COL, TIMESTAMP_COL])

    case_sizes = df.groupby(CASE_ID_COL)[ACTIVITY_COL].transform("size")
    df = df[case_sizes >= MIN_EVENTS_PER_CASE].reset_index(drop=True)

    return df


def describe(df: pd.DataFrame) -> dict:
    per_case = df.groupby(CASE_ID_COL)[TIMESTAMP_COL].agg(["min", "max"])
    durations = per_case["max"] - per_case["min"]

    variants = (
        df.groupby(CASE_ID_COL)[ACTIVITY_COL]
        .apply(lambda acts: tuple(acts))
        .value_counts()
    )

    return {
        "n_events": len(df),
        "n_cases": df[CASE_ID_COL].nunique(),
        "n_variants": len(variants),
        "avg_duration_hours": durations.dt.total_seconds().mean() / 3600,
        "median_duration_hours": durations.dt.total_seconds().median() / 3600,
    }


def main() -> None:
    df_raw = pd.read_parquet(RAW_EVENT_LOG_PATH)
    df_clean = clean_log(df_raw)
    df_clean.to_parquet(CLEAN_EVENT_LOG_PATH, index=False)

    stats = describe(df_clean)
    print(f"Evenements bruts : {len(df_raw)} -> nettoyes : {stats['n_events']}")
    print(f"Nombre de cas : {stats['n_cases']}")
    print(f"Nombre de variantes uniques : {stats['n_variants']}")
    print(f"Duree moyenne d'un cas : {stats['avg_duration_hours']:.1f} h")
    print(f"Duree mediane d'un cas : {stats['median_duration_hours']:.1f} h")
    print(f"Sauvegarde : {CLEAN_EVENT_LOG_PATH}")


if __name__ == "__main__":
    main()
