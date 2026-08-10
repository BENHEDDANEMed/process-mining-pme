"""Phase 5 - Dashboard Streamlit : vue d'ensemble, processus, conformite, prediction."""

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import plotly.express as px
import pm4py
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"

CASE_ID_COL = "case:concept:name"
ACTIVITY_COL = "concept:name"
TIMESTAMP_COL = "time:timestamp"

st.set_page_config(page_title="Process Mining PME", layout="wide")


@st.cache_data
def load_event_log() -> pd.DataFrame:
    df = pd.read_parquet(DATA_DIR / "event_log_clean.parquet")
    df[TIMESTAMP_COL] = pd.to_datetime(df[TIMESTAMP_COL], utc=True)
    return df


@st.cache_data
def load_conformance_report() -> pd.DataFrame:
    return pd.read_csv(MODELS_DIR / "conformance_report.csv")


@st.cache_data
def load_prefix_dataset() -> pd.DataFrame:
    return pd.read_parquet(MODELS_DIR / "prefix_dataset.parquet")


@st.cache_resource
def load_petri_net():
    return pm4py.read_pnml(str(MODELS_DIR / "process_model.pnml"))


@st.cache_resource
def load_classifier():
    return joblib.load(MODELS_DIR / "xgboost_classifier.pkl")


@st.cache_resource
def load_regressor():
    return joblib.load(MODELS_DIR / "xgboost_regressor.pkl")


def view_overview(df: pd.DataFrame, conformance: pd.DataFrame) -> None:
    st.header("Vue d'ensemble")

    per_case = df.groupby(CASE_ID_COL)[TIMESTAMP_COL].agg(["min", "max"])
    durations_h = (per_case["max"] - per_case["min"]).dt.total_seconds() / 3600
    conformance_rate = conformance["is_fit"].mean()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Nombre de cas", f"{df[CASE_ID_COL].nunique():,}")
    col2.metric("Duree moyenne", f"{durations_h.mean():.1f} h")
    col3.metric("Duree mediane", f"{durations_h.median():.1f} h")
    col4.metric("Taux de conformite", f"{conformance_rate:.1%}")

    st.subheader("Distribution de la duree des cas (heures, tronquee au 95e percentile)")
    p95 = durations_h.quantile(0.95)
    fig = px.histogram(durations_h[durations_h <= p95], nbins=50)
    fig.update_layout(xaxis_title="Duree (h)", yaxis_title="Nombre de cas", showlegend=False)
    st.plotly_chart(fig, width='stretch')

    st.subheader("Activites les plus frequentes")
    top_acts = df[ACTIVITY_COL].value_counts().head(15).reset_index()
    top_acts.columns = ["activite", "nombre"]
    fig2 = px.bar(top_acts, x="nombre", y="activite", orientation="h")
    fig2.update_layout(yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig2, width='stretch')


def view_process(df: pd.DataFrame) -> None:
    st.header("Modele de processus decouvert (Inductive Miner)")
    net, im, fm = load_petri_net()
    st.write(f"Places : {len(net.places)} | Transitions : {len(net.transitions)} | Arcs : {len(net.arcs)}")

    try:
        from pm4py.visualization.petri_net import visualizer as pn_visualizer
        gviz = pn_visualizer.apply(net, im, fm)
        st.graphviz_chart(gviz)
    except Exception as exc:
        st.warning(
            "Visualisation graphique indisponible (Graphviz non trouve dans le PATH). "
            f"Le modele reste consultable via le fichier .pnml. Detail : {exc}"
        )

    st.subheader("Top 10 des variantes de processus")
    variants = (
        df.sort_values(TIMESTAMP_COL)
        .groupby(CASE_ID_COL)[ACTIVITY_COL]
        .apply(lambda acts: " -> ".join(acts))
        .value_counts()
        .head(10)
        .reset_index()
    )
    variants.columns = ["variante", "nombre_de_cas"]
    st.dataframe(variants, width='stretch')


def view_conformance(conformance: pd.DataFrame) -> None:
    st.header("Verification de conformite")

    col1, col2 = st.columns(2)
    col1.metric("Fitness moyen", f"{conformance['trace_fitness'].mean():.4f}")
    col2.metric("Cas non conformes", f"{(~conformance['is_fit']).sum():,} / {len(conformance):,}")

    st.subheader("Distribution du fitness par cas")
    fig = px.histogram(conformance, x="trace_fitness", nbins=50)
    st.plotly_chart(fig, width='stretch')

    st.subheader("Cas les plus deviants")
    st.dataframe(
        conformance.sort_values("trace_fitness").head(50),
        width='stretch',
    )


def view_prediction(prefix_df: pd.DataFrame) -> None:
    st.header("Prediction sur un cas")

    case_ids = sorted(prefix_df["case_id"].unique().tolist())
    selected_case = st.selectbox("Choisir un cas existant", case_ids)

    case_rows = prefix_df[prefix_df["case_id"] == selected_case].sort_values("prefix_length")
    step = st.slider("Etape du cas (longueur de prefixe)", 1, len(case_rows), len(case_rows))
    row = case_rows.iloc[step - 1]

    st.write("**Etat du cas a cette etape :**")
    st.json({
        "activite_courante": row["current_activity"],
        "prefix_length": int(row["prefix_length"]),
        "elapsed_hours": round(float(row["elapsed_hours"]), 1),
        "amount": float(row["amount"]),
    })

    features = pd.DataFrame([{
        "current_activity": row["current_activity"],
        "prefix_length": row["prefix_length"],
        "elapsed_hours": row["elapsed_hours"],
        "amount": row["amount"],
    }])

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Issue probable du dossier")
        bundle = load_classifier()
        pipeline, classes = bundle["pipeline"], bundle["classes"]
        proba = pipeline.predict_proba(features)[0]
        proba_df = pd.DataFrame({"classe": classes, "probabilite": proba}).sort_values(
            "probabilite", ascending=False
        )
        st.dataframe(proba_df, width='stretch', hide_index=True)
        st.metric("Issue reelle du cas", row.get("outcome", "N/A"))

    with col2:
        st.subheader("Temps restant estime")
        regressor = load_regressor()
        pred_log = regressor.predict(features)[0]
        pred_hours = float(np.expm1(pred_log))
        st.metric("Temps restant predit", f"{pred_hours:.1f} h ({pred_hours / 24:.1f} j)")
        st.metric("Temps restant reel", f"{row['remaining_hours']:.1f} h ({row['remaining_hours'] / 24:.1f} j)")


def main() -> None:
    st.title("Process Mining PME - Demandes de pret (BPI Challenge 2012)")

    df = load_event_log()
    conformance = load_conformance_report()
    prefix_df = load_prefix_dataset()

    tab1, tab2, tab3, tab4 = st.tabs(
        ["Vue d'ensemble", "Processus", "Conformite", "Prediction"]
    )
    with tab1:
        view_overview(df, conformance)
    with tab2:
        view_process(df)
    with tab3:
        view_conformance(conformance)
    with tab4:
        view_prediction(prefix_df)


if __name__ == "__main__":
    main()
