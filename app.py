"""Dashboard Streamlit : Overview, Process, Conformance & Performance, Prediction, Recommendations.

Plateforme de Process Mining adaptee aux PME, validee experimentalement sur le
processus Purchase-to-Pay du dataset public BPI Challenge 2019.
"""

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import plotly.express as px
import pm4py
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data" / "processed"
MODELS_DIR = BASE_DIR / "models"

CASE_ID_COL = "case:concept:name"
ACTIVITY_COL = "concept:name"
TIMESTAMP_COL = "time:timestamp"
RESOURCE_COL = "org:resource"

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


@st.cache_data
def load_kpis() -> dict:
    return json.loads((MODELS_DIR / "kpi_summary.json").read_text(encoding="utf-8"))


@st.cache_data
def load_performance_reports() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    transitions = pd.read_csv(MODELS_DIR / "performance_transitions.csv")
    rework = pd.read_csv(MODELS_DIR / "performance_rework.csv")
    resources = pd.read_csv(MODELS_DIR / "performance_resources.csv")
    return transitions, rework, resources


@st.cache_data(ttl=300)
def load_live_kpis() -> dict | None:
    path = BASE_DIR / "data" / "live" / "live_kpi_summary.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


@st.cache_data(ttl=300)
def load_live_log() -> pd.DataFrame | None:
    path = BASE_DIR / "data" / "live" / "nyc311_events.parquet"
    if not path.exists():
        return None
    df = pd.read_parquet(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df


@st.cache_resource
def load_petri_net():
    return pm4py.read_pnml(str(MODELS_DIR / "process_model.pnml"))


@st.cache_resource
def load_classifier():
    return joblib.load(MODELS_DIR / "xgboost_classifier.pkl")


@st.cache_resource
def load_regressor():
    return joblib.load(MODELS_DIR / "xgboost_regressor.pkl")


def view_overview(df: pd.DataFrame, kpis: dict) -> None:
    st.header("Vue d'ensemble")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Nombre de cas", f"{kpis['n_cases']:,}")
    col2.metric("Duree moyenne", f"{kpis['avg_case_duration_hours'] / 24:.1f} j")
    col3.metric("Duree mediane", f"{kpis['median_case_duration_hours'] / 24:.1f} j")
    col4.metric("Taux de deviation", f"{kpis['deviation_rate']:.1%}")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Nombre d'evenements", f"{kpis['n_events']:,}")
    col6.metric("Nombre de variantes", f"{kpis['n_variants']:,}")
    col7.metric("Taux de rework moyen", f"{kpis['overall_rework_rate']:.1%}")
    col8.metric("Fitness moyen", f"{kpis['avg_fitness']:.3f}")

    per_case = df.groupby(CASE_ID_COL)[TIMESTAMP_COL].agg(["min", "max"])
    durations_h = (per_case["max"] - per_case["min"]).dt.total_seconds() / 3600

    st.subheader("Distribution de la duree des cas (jours, tronquee au 95e percentile)")
    p95 = durations_h.quantile(0.95)
    fig = px.histogram((durations_h[durations_h <= p95] / 24), nbins=50)
    fig.update_layout(xaxis_title="Duree (j)", yaxis_title="Nombre de cas", showlegend=False)
    st.plotly_chart(fig, width="stretch")

    st.subheader("Activites les plus frequentes")
    top_acts = df[ACTIVITY_COL].value_counts().head(15).reset_index()
    top_acts.columns = ["activite", "nombre"]
    fig2 = px.bar(top_acts, x="nombre", y="activite", orientation="h")
    fig2.update_layout(yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig2, width="stretch")


def view_process(df: pd.DataFrame) -> None:
    st.header("Modele de processus decouvert (Inductive Miner)")
    st.caption(
        "Modele decouvert sur les variantes couvrant 80% des cas "
        "(la version complete du log, avec 11 000+ variantes, produirait un modele illisible)."
    )
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
        df.sort_values([CASE_ID_COL, TIMESTAMP_COL], kind="stable")
        .groupby(CASE_ID_COL)[ACTIVITY_COL]
        .apply(lambda acts: " -> ".join(acts))
        .value_counts()
        .head(10)
        .reset_index()
    )
    variants.columns = ["variante", "nombre_de_cas"]
    st.dataframe(variants, width="stretch")


def view_conformance_performance(
    conformance: pd.DataFrame,
    transitions: pd.DataFrame,
    rework: pd.DataFrame,
    resources: pd.DataFrame,
) -> None:
    st.header("Conformite et performance")

    col1, col2 = st.columns(2)
    col1.metric("Fitness moyen", f"{conformance['trace_fitness'].mean():.4f}")
    col2.metric("Cas non conformes", f"{(~conformance['is_fit']).sum():,} / {len(conformance):,}")

    st.subheader("Distribution du fitness par cas")
    fig = px.histogram(conformance, x="trace_fitness", nbins=50)
    st.plotly_chart(fig, width="stretch")

    st.subheader("Cas les plus deviants")
    st.dataframe(conformance.sort_values("trace_fitness").head(50), width="stretch")

    st.subheader("Goulots d'etranglement (temps d'attente moyen entre activites)")
    top_transitions = transitions[transitions["count"] >= 20].head(15)
    fig_t = px.bar(
        top_transitions,
        x="avg_wait_hours",
        y=top_transitions["from_activity"] + " -> " + top_transitions["to_activity"],
        orientation="h",
    )
    fig_t.update_layout(
        xaxis_title="Temps d'attente moyen (h)", yaxis_title="",
        yaxis={"categoryorder": "total ascending"},
    )
    st.plotly_chart(fig_t, width="stretch")

    col3, col4 = st.columns(2)
    with col3:
        st.subheader("Top rework par activite")
        st.dataframe(rework.head(10), width="stretch", hide_index=True)
    with col4:
        st.subheader("Charge par ressource")
        st.dataframe(resources.head(10), width="stretch", hide_index=True)


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
        "vendor": row["vendor"],
        "item_category": row["item_category"],
        "document_type": row["document_type"],
        "prefix_length": int(row["prefix_length"]),
        "elapsed_hours": round(float(row["elapsed_hours"]), 1),
        "activites_distinctes": int(row["n_distinct_activities"]),
        "rework": int(row["n_rework"]),
        "plus_longue_pause_h": round(float(row["max_gap_hours"]), 1),
        "amount": float(row["amount"]),
    })

    bundle = load_classifier()
    pipeline, classes = bundle["pipeline"], bundle["classes"]
    # Le jeu de features est enregistre avec le modele : on rejoue exactement
    # les memes colonnes que celles vues a l'entrainement.
    features = row[bundle["feature_cols"]].to_frame().T

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Risque de retard")
        threshold_h = bundle.get("late_threshold_hours")
        if threshold_h:
            st.caption(f"Un cas est dit en retard au-dela de {threshold_h / 24:.0f} jours de duree totale.")
        proba = pipeline.predict_proba(features)[0]
        late_idx = classes.index("LATE") if "LATE" in classes else 0
        st.metric("Probabilite de retard", f"{proba[late_idx]:.1%}")
        proba_df = pd.DataFrame({"classe": classes, "probabilite": proba}).sort_values(
            "probabilite", ascending=False
        )
        st.dataframe(proba_df, width="stretch", hide_index=True)
        st.metric("Issue reelle du cas (classement a posteriori)", row.get("outcome", "N/A"))

    with col2:
        st.subheader("Temps restant estime")
        regressor = load_regressor()
        pred_log = regressor.predict(features)[0]
        pred_hours = float(np.expm1(pred_log))
        st.metric("Temps restant predit", f"{pred_hours:.1f} h ({pred_hours / 24:.1f} j)")
        st.metric("Temps restant reel", f"{row['remaining_hours']:.1f} h ({row['remaining_hours'] / 24:.1f} j)")


def view_recommendations(kpis: dict) -> None:
    st.header("Recommandations")
    st.caption("Regles generees automatiquement a partir des KPI de process mining et de performance.")

    for reco in kpis.get("recommendations", []):
        st.warning(reco)

    st.subheader("Problemes detectes et impact")
    rows = []
    for b in kpis["top_bottlenecks"]:
        rows.append({
            "probleme": f"Goulot d'etranglement : {b['from']} -> {b['to']}",
            "impact": f"{b['avg_wait_hours']:.1f} h d'attente moyenne sur {b['count']} occurrences",
        })
    for r in kpis["top_rework_activities"]:
        rows.append({
            "probleme": f"Rework sur '{r['activity']}'",
            "impact": f"{r['rework_rate']:.1%} des cas repassent par cette activite",
        })
    if rows:
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    else:
        st.info("Aucun probleme majeur detecte sur les seuils actuels.")


def view_live_source() -> None:
    st.header("Flux vivant - API publique NYC 311")
    st.caption(
        "Volet complementaire : l'analyse principale porte sur BPI Challenge 2019, un jeu "
        "de recherche fige. Cette vue montre la meme chaine d'analyse appliquee a une source "
        "qui se renouvelle reellement - un flux de tickets de reclamation interroge en direct."
    )

    live_kpis = load_live_kpis()
    live_log = load_live_log()

    if live_kpis is None or live_log is None:
        st.warning(
            "Aucun instantane du flux vivant n'a encore ete recupere. "
            "Executer, depuis la racine du projet : "
            "`python -m src.live_source` puis `python -m src.live_analysis`."
        )
        return

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Tickets (cas)", f"{live_kpis['n_cases']:,}")
    col2.metric("Taux de cloture", f"{live_kpis['closure_rate']:.1%}")
    col3.metric("Duree mediane", f"{live_kpis['median_duration_hours']:.1f} h")
    col4.metric("Variantes", f"{live_kpis['n_variants']}")

    st.info(
        f"Instantane couvrant {live_kpis['period_start'][:10]} -> {live_kpis['period_end'][:10]}. "
        "Relancer `python -m src.live_source` recupere de nouveaux tickets : "
        "les chiffres de cette vue evoluent a chaque appel, contrairement aux autres onglets."
    )

    st.subheader("Types de reclamation les plus lents")
    slowest = live_kpis.get("slowest_complaint_types", {})
    if slowest:
        slow_df = pd.DataFrame([
            {"type": k, "duree_mediane_h": v["median_hours"], "nombre_de_cas": v["n_cases"]}
            for k, v in slowest.items()
        ])
        fig = px.bar(slow_df, x="duree_mediane_h", y="type", orientation="h",
                     hover_data=["nombre_de_cas"])
        fig.update_layout(xaxis_title="Duree mediane (h)", yaxis_title="",
                          yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, width="stretch")

    col5, col6 = st.columns(2)
    with col5:
        st.subheader("Variantes observees")
        st.dataframe(
            pd.DataFrame(live_kpis["top_variants"]).rename(
                columns={"variant": "variante", "n_cases": "nombre_de_cas"}
            ),
            width="stretch", hide_index=True,
        )
    with col6:
        st.subheader("Goulots d'etranglement")
        st.dataframe(
            pd.DataFrame(live_kpis["top_bottlenecks"]).rename(
                columns={"from": "de", "to": "vers", "avg_wait_hours": "attente_moy_h",
                         "count": "occurrences"}
            ),
            width="stretch", hide_index=True,
        )

    st.subheader("Volume de tickets crees par jour")
    created = live_log[live_log["activity"] == "Service Request Created"]
    per_day = created.set_index("timestamp").resample("D").size().reset_index()
    per_day.columns = ["jour", "tickets_crees"]
    fig2 = px.line(per_day, x="jour", y="tickets_crees", markers=True)
    st.plotly_chart(fig2, width="stretch")

    with st.expander("Limite de qualite de donnees identifiee"):
        st.markdown(
            "Certaines variantes sont chronologiquement incoherentes (par exemple "
            "`Resolution Action Updated -> Service Request Created`). Le champ "
            "`resolution_action_updated_date` de l'API 311 est un horodatage de derniere "
            "modification, qui ne suit donc pas toujours l'ordre logique du cycle de vie."
            "\n\n"
            "C'est un resultat en soi : le process mining rend visible un defaut de qualite "
            "de donnees qui resterait invisible dans un simple tableau de bord agrege."
        )


def main() -> None:
    st.title("Process Mining PME - Purchase-to-Pay (BPI Challenge 2019)")
    st.caption(
        "Plateforme de Process Mining adaptee aux besoins des PME, "
        "validee experimentalement sur un dataset public."
    )

    df = load_event_log()
    conformance = load_conformance_report()
    prefix_df = load_prefix_dataset()
    kpis = load_kpis()
    transitions, rework, resources = load_performance_reports()

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
        ["Vue d'ensemble", "Processus", "Conformite & Performance", "Prediction",
         "Recommandations", "Flux vivant (API)"]
    )
    with tab1:
        view_overview(df, kpis)
    with tab2:
        view_process(df)
    with tab3:
        view_conformance_performance(conformance, transitions, rework, resources)
    with tab4:
        view_prediction(prefix_df)
    with tab5:
        view_recommendations(kpis)
    with tab6:
        view_live_source()


if __name__ == "__main__":
    main()
