"""Volet complementaire - process mining applique au flux vivant NYC 311.

Ce module est la demonstration concrete que la chaine d'analyse n'est pas liee
au dataset BPI2019 : il appelle exactement les memes fonctions de
`src/process_metrics.py` que l'analyse principale, en changeant simplement de
configuration (config/nyc311.yaml au lieu de config/bpi2019.yaml).

Aucune metrique n'est reimplementee ici : brancher un nouveau processus se
resume a ecrire un fichier YAML.

Prerequis : avoir execute `python -m src.live_source` au moins une fois.

Usage :
    python -m src.live_analysis
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pm4py

from src.config import load_config
from src.live_source import EVENT_LOG_PATH
from src.process_metrics import (
    bottlenecks, case_durations_hours, case_variants, resource_load,
    rework_rates, summarize,
)

BASE_DIR = Path(__file__).resolve().parent.parent
LIVE_DATA_DIR = BASE_DIR / "data" / "live"
REPORTS_DIR = BASE_DIR / "reports"

LIVE_PNML_PATH = LIVE_DATA_DIR / "live_process_model.pnml"
LIVE_KPI_PATH = LIVE_DATA_DIR / "live_kpi_summary.json"
LIVE_REPORT_PATH = REPORTS_DIR / "live_process_analysis.md"

CONFIG_NAME = "nyc311"
MIN_CASES_PER_TYPE = 20
TOP_N = 5


def load_live_log() -> pd.DataFrame:
    if not EVENT_LOG_PATH.exists():
        raise FileNotFoundError(
            f"{EVENT_LOG_PATH} introuvable. Executer d'abord : python -m src.live_source"
        )
    df = pd.read_parquet(EVENT_LOG_PATH)
    cfg = load_config(CONFIG_NAME)
    df[cfg.timestamp] = pd.to_datetime(df[cfg.timestamp], utc=True)
    return df


def discover(df: pd.DataFrame, cfg):
    formatted = pm4py.format_dataframe(
        df, case_id=cfg.case_id, activity_key=cfg.activity, timestamp_key=cfg.timestamp
    )
    return pm4py.discover_petri_net_inductive(
        formatted, case_id_key=cfg.case_id, activity_key=cfg.activity, timestamp_key=cfg.timestamp
    )


def slowest_categories(df: pd.DataFrame, cfg) -> dict:
    """Types de reclamation dont le traitement est le plus lent.

    Filtre sur un nombre minimal de cas : sans cela, un type vu trois fois
    dominerait le classement sur un simple alea.
    """
    category_col = cfg.categorical_attributes[0] if cfg.categorical_attributes else None
    if not category_col or category_col not in df.columns:
        return {}

    durations = case_durations_hours(df, cfg)
    case_category = df.drop_duplicates(cfg.case_id).set_index(cfg.case_id)[category_col]
    stats = durations.groupby(case_category).agg(["count", "median"])
    stats = stats[stats["count"] >= MIN_CASES_PER_TYPE]

    return {
        str(name): {"n_cases": int(row["count"]), "median_hours": round(float(row["median"]), 2)}
        for name, row in stats.sort_values("median", ascending=False).head(8).iterrows()
    }


def compute_kpis(df: pd.DataFrame, cfg) -> dict:
    kpis = summarize(df, cfg)
    variants = case_variants(df, cfg)

    kpis.update({
        "process": cfg.label,
        "top_variants": [
            {"variant": " -> ".join(v), "n_cases": int(c)} for v, c in variants.head(TOP_N).items()
        ],
        "top_bottlenecks": [
            {
                "from": row["from_activity"],
                "to": row["to_activity"],
                "avg_wait_hours": round(float(row["avg_wait_hours"]), 2),
                "count": int(row["count"]),
            }
            for _, row in bottlenecks(df, cfg, top_n=TOP_N).iterrows()
        ],
        "slowest_complaint_types": slowest_categories(df, cfg),
    })
    kpis.update(_rework_and_resource_kpis(df, cfg))
    return kpis


def _rework_and_resource_kpis(df: pd.DataFrame, cfg) -> dict:
    """Rework et charge des ressources, au meme format que business_analysis.

    Ces deux KPI viennent des memes fonctions generiques que l'analyse
    principale ; les exposer ici permet au Process Health Score de noter le
    flux vivant sur trois dimensions au lieu d'une seule.
    """
    rework = rework_rates(df, cfg)
    resources = resource_load(df, cfg)

    return {
        "overall_rework_rate": float(rework["rework_rate"].mean()) if len(rework) else 0.0,
        "top_rework_activities": [
            {"activity": row["activity"], "rework_rate": round(float(row["rework_rate"]), 4)}
            for _, row in rework.head(TOP_N).iterrows()
        ],
        "top_resources": [
            {"resource": row["resource"], "n_events": int(row["n_events"])}
            for _, row in resources.head(TOP_N).iterrows()
        ],
    }


def format_report(kpis: dict, net_stats: dict) -> str:
    lines = [
        "# Analyse du flux vivant - NYC 311 (API publique)",
        "",
        "Ce rapport est genere a partir d'un appel API effectue au moment de l'execution.",
        "Contrairement au dataset BPI Challenge 2019 (fige), **relancer le pipeline produit",
        "des chiffres differents**, puisque de nouveaux tickets arrivent en continu.",
        "",
        "Les indicateurs ci-dessous sont calcules par les memes fonctions que l'analyse",
        "principale (`src/process_metrics.py`) : seule la configuration change.",
        "",
        "## Instantane analyse",
        f"- Evenements : {kpis['n_events']:,}",
        f"- Cas (tickets) : {kpis['n_cases']:,}",
        f"- Periode couverte : {kpis['period_start'][:16]} -> {kpis['period_end'][:16]}",
        f"- Taux de cloture a l'instant T : {kpis['closure_rate']:.1%} "
        f"({kpis['n_closed_cases']:,} tickets clotures)",
        "",
        "## Delais de traitement",
        f"- Duree mediane : {kpis['median_case_duration_hours']:.1f} h",
        f"- Duree moyenne : {kpis['avg_case_duration_hours']:.1f} h",
        f"- 90e percentile : {kpis['p90_case_duration_hours']:.1f} h",
        "",
        "## Modele de processus decouvert",
        f"- Places : {net_stats['places']} | Transitions : {net_stats['transitions']} "
        f"| Arcs : {net_stats['arcs']}",
        f"- Nombre de variantes observees : {kpis['n_variants']}",
        "",
        "### Variantes les plus frequentes",
    ]
    for v in kpis["top_variants"]:
        lines.append(f"- ({v['n_cases']} cas) {v['variant']}")

    lines += ["", "## Goulots d'etranglement (attente moyenne entre etapes)"]
    for b in kpis["top_bottlenecks"]:
        lines.append(
            f"- {b['from']} -> {b['to']} : {b['avg_wait_hours']:.1f} h ({b['count']} occurrences)"
        )

    if kpis["slowest_complaint_types"]:
        lines += ["", f"## Types de reclamation les plus lents (>= {MIN_CASES_PER_TYPE} cas)"]
        for name, stats in kpis["slowest_complaint_types"].items():
            lines.append(f"- {name} : mediane {stats['median_hours']:.1f} h ({stats['n_cases']} cas)")

    lines += [
        "",
        "## Interet pour une PME",
        "",
        "Le processus modelise ici (ouverture -> traitement -> cloture d'une reclamation)",
        "est structurellement identique a un service client ou un support technique de PME.",
        "Les memes indicateurs - delai de traitement, taux de cloture, etapes ou le dossier",
        "stagne - se transposent directement, la seule difference etant la source des",
        "donnees : ici une API publique, en entreprise le systeme de ticketing interne.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    cfg = load_config(CONFIG_NAME)
    df = load_live_log()
    print(f"Processus analyse : {cfg.label}")
    print(f"Log vivant charge : {len(df)} evenements, {df[cfg.case_id].nunique()} cas")

    net, im, fm = discover(df, cfg)
    LIVE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    pm4py.write_pnml(net, im, fm, str(LIVE_PNML_PATH))
    net_stats = {
        "places": len(net.places),
        "transitions": len(net.transitions),
        "arcs": len(net.arcs),
    }
    print(f"Modele decouvert : {net_stats}")

    kpis = compute_kpis(df, cfg)
    LIVE_KPI_PATH.write_text(json.dumps(kpis, indent=2, ensure_ascii=False), encoding="utf-8")

    REPORTS_DIR.mkdir(exist_ok=True)
    report = format_report(kpis, net_stats)
    LIVE_REPORT_PATH.write_text(report, encoding="utf-8")

    print()
    print(report)
    print(f"Rapport sauvegarde : {LIVE_REPORT_PATH}")


if __name__ == "__main__":
    main()
