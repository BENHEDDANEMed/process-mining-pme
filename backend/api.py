"""API FastAPI pour le dashboard React.

Remplace le dashboard Streamlit (app.py) : memes fichiers sources (models/,
data/processed/), memes fonctions d'analyse (src/), juste une couche de
restitution differente. Aucune metrique n'est recalculee ici.

Usage :
    uvicorn backend.api:app --port 8000
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pm4py
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.case_explorer import build_case_table, event_timeline, search_cases
from src.config import DEFAULT_CONFIG, load_config
from src.model_explain import ExplainUnavailable, explain_prediction, outcome_comparison
from src.process_health import calculate_process_health, load_delay_risk_rate
from src.process_metrics import (
    assign_variant_ids_from_sequences,
    case_rework_counts,
    case_sequences,
    variant_table_from_sequences,
)
from src.risk_monitoring import bucket_risk, case_risk_trajectory, mid_progress_rows, monitoring_overview
from src.train_model import FEATURE_COLS_CAT, FEATURE_COLS_NUM

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "processed"
MODELS_DIR = BASE_DIR / "models"
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"

CASE_ID_COL = "case:concept:name"
ACTIVITY_COL = "concept:name"
TIMESTAMP_COL = "time:timestamp"

app = FastAPI()
_cfg = load_config(DEFAULT_CONFIG)


def _records(df: pd.DataFrame) -> list[dict]:
    """DataFrame -> liste de dict JSON-safe (numpy.int64/bool_ cassent json.dumps)."""
    return json.loads(df.to_json(orient="records"))


@lru_cache(maxsize=1)
def _event_log() -> pd.DataFrame:
    df = pd.read_parquet(DATA_DIR / "event_log_clean.parquet")
    df[TIMESTAMP_COL] = pd.to_datetime(df[TIMESTAMP_COL], utc=True)
    return df


@lru_cache(maxsize=1)
def _case_durations_days() -> pd.Series:
    df = _event_log()
    per_case = df.groupby(CASE_ID_COL)[TIMESTAMP_COL].agg(["min", "max"])
    return (per_case["max"] - per_case["min"]).dt.total_seconds() / 3600 / 24


@lru_cache(maxsize=1)
def _petri_net():
    return pm4py.read_pnml(str(MODELS_DIR / "process_model.pnml"))


@lru_cache(maxsize=1)
def _variants_df() -> pd.DataFrame:
    # Coeur du cout de /api/process (~25s sur 1.46M evenements) : identique
    # a ce que faisait deja app.py, mais sans le @st.cache_data de Streamlit
    # pour l'amortir. lru_cache(maxsize=1) fait le meme travail en stdlib.
    df = _event_log()
    return (
        df.sort_values([CASE_ID_COL, TIMESTAMP_COL], kind="stable")
        .groupby(CASE_ID_COL)[ACTIVITY_COL]
        .apply(lambda acts: " -> ".join(acts))
        .value_counts()
        .rename_axis("variant")
        .reset_index(name="n_cases")
    )


@lru_cache(maxsize=1)
def _conformance_df() -> pd.DataFrame:
    return pd.read_csv(MODELS_DIR / "conformance_report.csv")


@lru_cache(maxsize=1)
def _transitions_df() -> pd.DataFrame:
    return pd.read_csv(MODELS_DIR / "performance_transitions.csv")


@lru_cache(maxsize=1)
def _rework_df() -> pd.DataFrame:
    return pd.read_csv(MODELS_DIR / "performance_rework.csv")


@lru_cache(maxsize=1)
def _resources_df() -> pd.DataFrame:
    return pd.read_csv(MODELS_DIR / "performance_resources.csv")


def _clean_key(col: str) -> str:
    """'case:GR-Based Inv. Verif.' -> 'gr_based_inv_verif' : cle JSON lisible,
    generique (ne connait aucun nom de colonne particulier)."""
    return col.replace("case:", "").strip().lower().replace(" ", "_").replace(".", "").replace("-", "_")


@lru_cache(maxsize=1)
def _case_sequences() -> pd.Series:
    # Calcul le plus couteux du module (tri + agregation par groupe sur
    # ~249k cas) : mis en cache une seule fois et partage par les deux
    # fonctions ci-dessous, qui sinon le recalculeraient chacune independamment.
    return case_sequences(_event_log(), _cfg)


@lru_cache(maxsize=1)
def _case_variant_ids() -> pd.Series:
    return assign_variant_ids_from_sequences(_case_sequences())


@lru_cache(maxsize=1)
def _variant_table_df() -> pd.DataFrame:
    return variant_table_from_sequences(_case_sequences())


@lru_cache(maxsize=1)
def _case_rework_counts() -> pd.Series:
    return case_rework_counts(_event_log(), _cfg)


_EMPTY_PREDICTIONS = pd.DataFrame(columns=["case_id", "predicted_late_probability", "predicted_label", "predicted_remaining_hours"])


@lru_cache(maxsize=1)
def _case_latest_predictions() -> pd.DataFrame:
    """Derniere prediction connue (etape la plus avancee) pour chaque cas de
    l'echantillon ML (~60k cas sur les ~249k au total) : un seul appel batche
    a predict_proba/predict, jamais un calcul par cas.

    Un modele absent/casse ne doit pas faire tomber tout l'explorateur de cas
    ou les variantes (qui n'ont besoin des predictions qu'en enrichissement,
    pas comme donnee obligatoire) : degrade en l'absence de prediction pour
    tous les cas plutot que de laisser l'exception remonter en 500.
    """
    try:
        prefix_df = _prefix_dataset()
        latest = prefix_df.sort_values("prefix_length").groupby("case_id").tail(1).reset_index(drop=True)
        if latest.empty:
            return _EMPTY_PREDICTIONS

        bundle = _classifier()
        pipeline, classes = bundle["pipeline"], bundle["classes"]
        late_idx = classes.index("LATE")
        decision_threshold = bundle.get("decision_threshold", 0.5)
        features = latest[bundle["feature_cols"]]
        proba = pipeline.predict_proba(features)[:, late_idx]
        remaining_hours = np.expm1(_regressor_model().predict(features))

        return pd.DataFrame({
            "case_id": latest["case_id"].to_numpy(),
            "predicted_late_probability": proba,
            "predicted_label": np.where(proba >= decision_threshold, "LATE", "ON_TIME"),
            "predicted_remaining_hours": remaining_hours,
        })
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(f"Predictions indisponibles pour l'explorateur de cas/variantes : {exc}")
        return _EMPTY_PREDICTIONS


@lru_cache(maxsize=1)
def _mid_progress_dataset() -> pd.DataFrame:
    return mid_progress_rows(_prefix_dataset())


_EMPTY_MONITORING = pd.DataFrame(columns=["case_id", "prefix_length", "elapsed_hours", "predicted_late_probability", "predicted_remaining_hours"])


@lru_cache(maxsize=1)
def _monitoring_snapshot() -> pd.DataFrame:
    """Predictions batchees UNE fois pour chaque cas de l'echantillon ML, a son
    etape mi-parcours : base de tout le monitoring, jamais recalculee par requete."""
    mid = _mid_progress_dataset()
    if mid.empty:
        return _EMPTY_MONITORING
    try:
        bundle = _classifier()
        pipeline, classes = bundle["pipeline"], bundle["classes"]
        late_idx = classes.index("LATE")
        features = mid[bundle["feature_cols"]]
        proba = pipeline.predict_proba(features)[:, late_idx]
        remaining_hours = np.expm1(_regressor_model().predict(features))
        return mid.assign(predicted_late_probability=proba, predicted_remaining_hours=remaining_hours)
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(f"Monitoring indisponible : {exc}")
        return _EMPTY_MONITORING


@lru_cache(maxsize=1)
def _variant_aggregates() -> pd.DataFrame:
    """Statistiques par variante (duree, rework, conformite), indexees par
    variant_id -- agregation cachee une seule fois, pas a chaque requete."""
    return _case_table().groupby("variant_id").agg(
        n_cases=("case_id", "size"),
        avg_duration_hours=("duration_hours", "mean"),
        median_duration_hours=("duration_hours", "median"),
        avg_n_events=("n_events", "mean"),
        rework_rate=("rework_count", lambda s: float((s > 0).mean())),
        conformance_rate=("is_fit", "mean"),
    )


@lru_cache(maxsize=1)
def _case_table() -> pd.DataFrame:
    table = build_case_table(_event_log(), _cfg).rename(columns={CASE_ID_COL: "case_id"})
    table = table.rename(columns={c: _clean_key(c) for c in _cfg.categorical_attributes})
    table["variant_id"] = table["case_id"].map(_case_variant_ids())
    table["rework_count"] = table["case_id"].map(_case_rework_counts())

    conf = _conformance_df()[["case_id", "trace_fitness", "is_fit"]]
    table = table.merge(conf, on="case_id", how="left")
    table = table.merge(_case_latest_predictions(), on="case_id", how="left")
    return table


def _kpis() -> dict:
    return json.loads((MODELS_DIR / "kpi_summary.json").read_text(encoding="utf-8"))


def _histogram(values: pd.Series, bins: int, value_range: tuple[float, float] | None = None, decimals: int = 0):
    counts, edges = np.histogram(values, bins=bins, range=value_range)
    return [{"label": round(float(edges[i]), decimals), "count": int(counts[i])} for i in range(len(counts))]


@app.get("/api/overview")
def overview():
    df = _event_log()
    kpis = _kpis()
    health = calculate_process_health(kpis, _cfg, load_delay_risk_rate(_cfg))

    durations_days = _case_durations_days()
    p95 = durations_days.quantile(0.95)
    duration_histogram = _histogram(durations_days[durations_days <= p95], bins=30)

    top_activities = _records(df[ACTIVITY_COL].value_counts().head(15).rename_axis("label").reset_index(name="value"))

    return {
        "kpis": kpis,
        "health": health,
        "recommendations": kpis.get("recommendations") or [],
        "duration_histogram": duration_histogram,
        "top_activities": top_activities,
    }


@app.get("/api/process")
def process():
    net, im, fm = _petri_net()
    variants = _records(_variants_df().head(10))

    return {
        "places": len(net.places),
        "transitions": len(net.transitions),
        "arcs": len(net.arcs),
        "image_url": "/api/process/image",
        "top_variants": variants,
    }


@app.get("/api/process/image")
def process_image():
    return FileResponse(MODELS_DIR / "process_model.png")


@app.get("/api/conformance")
def conformance():
    conf = _conformance_df()
    transitions = _transitions_df()
    rework = _rework_df()
    resources = _resources_df()

    deviants = _records(conf.sort_values("trace_fitness").head(50))
    bottlenecks = _records(transitions[transitions["count"] >= _cfg.analysis.min_transition_count].head(15))

    return {
        "fitness_mean": float(conf["trace_fitness"].mean()),
        "non_conformant": int((~conf["is_fit"]).sum()),
        "total": int(len(conf)),
        "fitness_histogram": _histogram(conf["trace_fitness"], bins=50, value_range=(0, 1), decimals=2),
        "deviants": deviants,
        "bottlenecks": bottlenecks,
        "rework": _records(rework.head(10)),
        "resources": _records(resources.head(10)),
    }


@app.get("/api/recommendations")
def recommendations():
    kpis = _kpis()
    problems = []
    for b in kpis.get("top_bottlenecks", []):
        problems.append(
            {
                "probleme": f"Goulot d'étranglement : {b['from']} -> {b['to']}",
                "impact": f"{b['avg_wait_hours']:.1f} h d'attente moyenne sur {b['count']} occurrences".replace(".", ","),
            }
        )
    for r in kpis.get("top_rework_activities", []):
        problems.append(
            {
                "probleme": f"Rework sur '{r['activity']}'",
                "impact": f"{r['rework_rate']:.1%} des cas repassent par cette activité".replace(".", ","),
            }
        )
    return {"recommendations": kpis.get("recommendations") or [], "problems": problems}


# --- Prediction : chargement paresseux (modeles lourds) ---------------------
_prefix_df: pd.DataFrame | None = None
_clf_bundle: dict | None = None
_regressor = None


def _prefix_dataset() -> pd.DataFrame:
    global _prefix_df
    if _prefix_df is None:
        _prefix_df = pd.read_parquet(MODELS_DIR / "prefix_dataset.parquet")
    return _prefix_df


def _classifier() -> dict:
    # joblib.load runs unpickling, but these files are produced locally by
    # src/train_model.py (never user-uploaded or fetched externally) - same
    # trust boundary as the Streamlit dashboard this replaces.
    global _clf_bundle
    if _clf_bundle is None:
        _clf_bundle = joblib.load(MODELS_DIR / "xgboost_classifier.pkl")
    return _clf_bundle


def _regressor_model():
    global _regressor
    if _regressor is None:
        _regressor = joblib.load(MODELS_DIR / "xgboost_regressor.pkl")
    return _regressor


@app.get("/api/prediction/cases")
def prediction_cases(q: str = "", limit: int = 50):
    # ponytail: ~60k cases in the sample -> a plain <select> can't hold them
    # all, so search server-side instead of shipping the full list to the client.
    ids = _prefix_dataset()["case_id"].unique()
    if q:
        ids = [c for c in ids if q in c]
    return sorted(ids)[:limit]


@app.get("/api/prediction/{case_id}")
def prediction_case_info(case_id: str):
    rows = _prefix_dataset()
    rows = rows[rows["case_id"] == case_id]
    bundle = _classifier()
    return {
        "n_steps": int(rows["prefix_length"].max()),
        "late_threshold_days": round((bundle.get("late_threshold_hours") or 0) / 24),
    }


@app.get("/api/prediction/{case_id}/{step}")
def prediction_step(case_id: str, step: int):
    rows = _prefix_dataset()
    case_rows = rows[rows["case_id"] == case_id].sort_values("prefix_length")
    row = case_rows.iloc[step - 1]

    bundle = _classifier()
    pipeline, classes = bundle["pipeline"], bundle["classes"]
    features = row[bundle["feature_cols"]].to_frame().T
    proba = pipeline.predict_proba(features)[0]
    late_idx = classes.index("LATE")
    decision_threshold = bundle.get("decision_threshold", 0.5)
    predicted_label = "LATE" if proba[late_idx] >= decision_threshold else "ON_TIME"

    pred_log = _regressor_model().predict(features)[0]
    predicted_remaining_hours = float(np.expm1(pred_log))

    return {
        "state": {
            "Activité courante": row["current_activity"],
            "Fournisseur (vendor)": row["vendor"],
            "Catégorie d'article": row["item_category"],
            "Type de document": row["document_type"],
            "Étape (longueur de préfixe)": int(row["prefix_length"]),
            "Temps écoulé (h)": f"{row['elapsed_hours']:.1f}".replace(".", ","),
            "Activités distinctes traversées": int(row["n_distinct_activities"]),
            "Répétitions (rework)": int(row["n_rework"]),
            "Plus longue pause (h)": f"{row['max_gap_hours']:.1f}".replace(".", ","),
            "Montant": f"{row['amount']:,.0f}".replace(",", " "),
        },
        "proba": {classes[i]: float(p) for i, p in enumerate(proba)},
        "predicted_label": predicted_label,
        "decision_threshold": decision_threshold,
        "late_threshold_days": round((bundle.get("late_threshold_hours") or 0) / 24),
        "actual_label": row.get("outcome", "N/A"),
        "predicted_remaining_hours": predicted_remaining_hours,
        "actual_remaining_hours": float(row["remaining_hours"]),
    }


@app.get("/api/variants")
def variants(top_n: int = 20):
    table = _variant_table_df()
    total_cases = int(table["n_cases"].sum())

    grouped = _variant_aggregates()
    sequence_by_id = dict(zip(table["variant_id"], table["sequence"]))

    rows = []
    for variant_id in table.head(top_n)["variant_id"]:
        if variant_id not in grouped.index:
            continue
        g = grouped.loc[variant_id]
        rows.append({
            "variant_id": int(variant_id),
            "sequence": list(sequence_by_id[variant_id]),
            "n_cases": int(g["n_cases"]),
            "frequency_pct": round(100 * g["n_cases"] / total_cases, 1) if total_cases else 0.0,
            "avg_duration_hours": float(g["avg_duration_hours"]),
            "median_duration_hours": float(g["median_duration_hours"]),
            "avg_n_events": float(g["avg_n_events"]),
            "rework_rate": float(g["rework_rate"]),
            "conformance_rate": float(g["conformance_rate"]) if pd.notna(g["conformance_rate"]) else None,
        })

    other_n_cases = total_cases - sum(r["n_cases"] for r in rows)
    if other_n_cases > 0:
        rows.append({
            "variant_id": -1, "sequence": None, "n_cases": other_n_cases,
            "frequency_pct": round(100 * other_n_cases / total_cases, 1) if total_cases else 0.0,
            "avg_duration_hours": None, "median_duration_hours": None,
            "avg_n_events": None, "rework_rate": None, "conformance_rate": None,
        })

    return {"variants": rows, "total_cases": total_cases, "total_variants": int(len(table))}


@app.get("/api/cases")
def cases_list(q: str = "", limit: int = 50, offset: int = 0, variant_id: int | None = None):
    search_columns = ["case_id"] + [_clean_key(c) for c in _cfg.categorical_attributes]
    table = search_cases(_case_table(), search_columns, q)
    if variant_id is not None:
        table = table[table["variant_id"] == variant_id]

    total = len(table)
    page = table.iloc[max(offset, 0):max(offset, 0) + max(limit, 0)]
    return {"cases": _records(page), "total": int(total), "limit": limit, "offset": offset}


@app.get("/api/cases/{case_id}")
def case_detail(case_id: str):
    table = _case_table()
    row = table[table["case_id"] == case_id]
    if row.empty:
        raise HTTPException(status_code=404, detail="Cas introuvable")

    timeline = event_timeline(_event_log(), _cfg, case_id)
    case_record = _records(row)[0]
    prediction = None
    if case_record.get("predicted_label") is not None:
        prediction = {
            "predicted_label": case_record["predicted_label"],
            "predicted_late_probability": case_record["predicted_late_probability"],
            "predicted_remaining_hours": case_record["predicted_remaining_hours"],
        }

    return {
        "case": case_record,
        "timeline": _records(timeline),
        "deviation_note": (
            "Repérage de surface (activité déjà vue dans ce cas / peu fréquente dans le log) — "
            "la conformité stricte (fitness) n'est disponible qu'au niveau du cas entier, "
            "pas événement par événement."
        ),
        "prediction": prediction,
    }


@app.get("/api/prediction/{case_id}/{step}/explain")
def prediction_explain(case_id: str, step: int):
    rows = _prefix_dataset()
    case_rows = rows[rows["case_id"] == case_id].sort_values("prefix_length")
    if case_rows.empty or step < 1 or step > len(case_rows):
        raise HTTPException(status_code=404, detail="Cas ou étape introuvable")

    bundle = _classifier()
    features = case_rows.iloc[[step - 1]][bundle["feature_cols"]]

    classifier_explanation = None
    regressor_explanation = None
    reason = None
    try:
        classifier_explanation = explain_prediction(bundle["pipeline"], features, FEATURE_COLS_CAT)
        regressor_explanation = explain_prediction(_regressor_model(), features, FEATURE_COLS_CAT)
    except (ExplainUnavailable, KeyError, ValueError, AttributeError, FileNotFoundError) as exc:
        reason = str(exc)

    return {
        "available": classifier_explanation is not None,
        "reason": reason,
        "classifier": classifier_explanation,
        "regressor": regressor_explanation,
    }


@app.get("/api/root-cause")
def root_cause(top_n: int = 8):
    prefix_df = _prefix_dataset()
    if prefix_df.empty or "outcome" not in prefix_df.columns:
        return {"available": False, "comparisons": [], "n_late": 0, "n_on_time": 0, "disclaimer": None}

    latest = prefix_df.sort_values("prefix_length").groupby("case_id").tail(1)
    feature_cols = FEATURE_COLS_NUM + FEATURE_COLS_CAT
    comparisons = outcome_comparison(latest, "outcome", feature_cols, top_n=top_n)

    return {
        "available": True,
        "comparisons": _records(comparisons),
        "n_late": int((latest["outcome"] == "LATE").sum()),
        "n_on_time": int((latest["outcome"] == "ON_TIME").sum()),
        "disclaimer": "Association statistique observée dans l'historique : ne démontre pas de lien de causalité.",
    }


@app.get("/api/monitoring/overview")
def monitoring_overview_route():
    snapshot = _monitoring_snapshot()
    try:
        late_threshold_hours = _classifier().get("late_threshold_hours") or 0.0
    except (FileNotFoundError, KeyError):
        late_threshold_hours = 0.0

    overview = monitoring_overview(snapshot, _cfg, late_threshold_hours)
    overview["thresholds"] = {"low_max": _cfg.risk_thresholds.low_max, "high_min": _cfg.risk_thresholds.high_min}
    return overview


@app.get("/api/monitoring/high-risk")
def monitoring_high_risk(limit: int = 50, offset: int = 0):
    snapshot = _monitoring_snapshot()
    if snapshot.empty:
        return {"cases": [], "total": 0, "limit": limit, "offset": offset}

    buckets = bucket_risk(snapshot["predicted_late_probability"], _cfg)
    high = snapshot[buckets == "HIGH"].sort_values("predicted_late_probability", ascending=False)
    total = len(high)
    page = high.iloc[max(offset, 0):max(offset, 0) + max(limit, 0)]
    return {"cases": _records(page), "total": int(total), "limit": limit, "offset": offset}


@app.get("/api/monitoring/case/{case_id}/history")
def monitoring_case_history(case_id: str):
    rows = _prefix_dataset()
    case_rows = rows[rows["case_id"] == case_id]
    if case_rows.empty:
        raise HTTPException(status_code=404, detail="Cas introuvable")

    note = (
        "Progression du risque à travers les étapes déjà connues de ce cas, pas un "
        "historique calendaire : ce dataset est un instantané figé, sans flux d'événements en direct."
    )
    try:
        bundle = _classifier()
        trajectory = case_risk_trajectory(bundle["pipeline"], bundle["classes"], case_rows, bundle["feature_cols"])
    except (FileNotFoundError, KeyError, ValueError) as exc:
        return {"case_id": case_id, "available": False, "reason": str(exc), "steps": [], "note": note}

    return {"case_id": case_id, "available": True, "reason": None, "steps": _records(trajectory), "note": note}


# --- Frontend statique (build Vite) : monte en dernier, sinon capte /api/* --
app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
