"""Phase 3 - Couche Business Analysis : agrege les sorties de process mining,
de conformance et de performance en KPI et recommandations metier.

Lit :
- data/processed/event_log_clean.parquet (volume, variantes, durees)
- models/conformance_report.csv       (fitness / deviations)
- models/performance_transitions.csv  (goulots d'etranglement)
- models/performance_rework.csv       (taux de rework)
- models/performance_resources.csv    (charge par ressource)

Produit :
- models/kpi_summary.json      (consomme par le dashboard Streamlit)
- reports/process_analysis.md  (rapport metier lisible)

Usage :
    python -m src.business_analysis
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from src.config import DEFAULT_CONFIG, load_config
from src.preprocess import CLEAN_EVENT_LOG_PATH
from src.process_metrics import summarize
from src.performance_analysis import (
    TRANSITIONS_REPORT_PATH, REWORK_REPORT_PATH, RESOURCE_REPORT_PATH,
)

BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "models"
REPORTS_DIR = BASE_DIR / "reports"

CONFORMANCE_REPORT_PATH = MODELS_DIR / "conformance_report.csv"
KPI_SUMMARY_PATH = MODELS_DIR / "kpi_summary.json"
BUSINESS_REPORT_PATH = REPORTS_DIR / "process_analysis.md"

TOP_N = 5

# Seuils au-dela desquels un indicateur declenche une recommandation.
DEVIATION_ALERT = 0.20
REWORK_ALERT = 0.05
FRAGMENTATION_ALERT = 0.10


def compute_kpis(config_name: str = DEFAULT_CONFIG) -> dict:
    cfg = load_config(config_name)

    df = pd.read_parquet(CLEAN_EVENT_LOG_PATH)
    conformance = pd.read_csv(CONFORMANCE_REPORT_PATH)
    transitions = pd.read_csv(TRANSITIONS_REPORT_PATH)
    rework = pd.read_csv(REWORK_REPORT_PATH)
    resources = pd.read_csv(RESOURCE_REPORT_PATH)

    kpis = summarize(df, cfg)

    significant = transitions[transitions["count"] >= cfg.analysis.min_transition_count]

    kpis.update({
        "process": cfg.label,
        "deviation_rate": float((~conformance["is_fit"]).mean()),
        "avg_fitness": float(conformance["trace_fitness"].mean()),
        "overall_rework_rate": float(rework["rework_rate"].mean()) if len(rework) else 0.0,
        "top_bottlenecks": [
            {
                "from": row["from_activity"],
                "to": row["to_activity"],
                "avg_wait_hours": round(float(row["avg_wait_hours"]), 1),
                "count": int(row["count"]),
            }
            for _, row in significant.head(TOP_N).iterrows()
        ],
        "top_rework_activities": [
            {"activity": row["activity"], "rework_rate": round(float(row["rework_rate"]), 4)}
            for _, row in rework.head(TOP_N).iterrows()
        ],
        "top_resources": [
            {"resource": row["resource"], "n_events": int(row["n_events"])}
            for _, row in resources.head(TOP_N).iterrows()
        ],
    })
    return kpis


def build_recommendations(kpis: dict) -> list[str]:
    recos = []

    if kpis["deviation_rate"] > DEVIATION_ALERT:
        recos.append(
            f"{kpis['deviation_rate']:.1%} des cas devient du modele de processus decouvert : "
            "prioriser l'audit des variantes non conformes avant d'automatiser davantage le processus."
        )

    if kpis["top_bottlenecks"]:
        b = kpis["top_bottlenecks"][0]
        recos.append(
            f"Le passage '{b['from']}' -> '{b['to']}' est le principal goulot d'etranglement "
            f"(attente moyenne {b['avg_wait_hours']:.1f} h sur {b['count']} occurrences) : "
            "cibler cette transition en priorite pour reduire les delais globaux."
        )

    if kpis["overall_rework_rate"] > REWORK_ALERT:
        recos.append(
            f"Taux de rework moyen de {kpis['overall_rework_rate']:.1%} : "
            "des activites sont refaites plusieurs fois dans un meme cas, signe possible "
            "de retours qualite ou d'erreurs de saisie a investiguer."
        )

    if kpis["top_variant_share"] < FRAGMENTATION_ALERT:
        recos.append(
            f"La variante la plus frequente ne couvre que {kpis['top_variant_share']:.1%} des cas "
            f"sur {kpis['n_variants']} variantes au total : le processus reel est tres fragmente, "
            "un standard operatoire clair reduirait la variabilite."
        )

    if not recos:
        recos.append(
            "Aucune anomalie majeure detectee sur les seuils actuels ; processus globalement maitrise."
        )
    return recos


def format_report(kpis: dict, recommendations: list[str]) -> str:
    avg_h = kpis["avg_case_duration_hours"]
    med_h = kpis["median_case_duration_hours"]

    lines = [
        "# Analyse metier du processus (Business Analysis)",
        "",
        f"Processus analyse : **{kpis.get('process', 'non precise')}**",
        "",
        "## KPI",
        f"- Nombre de cas : {kpis['n_cases']:,}",
        f"- Nombre d'evenements : {kpis['n_events']:,}",
        f"- Duree moyenne d'un cas : {avg_h:.1f} h ({avg_h / 24:.1f} j)",
        f"- Duree mediane d'un cas : {med_h:.1f} h ({med_h / 24:.1f} j)",
        f"- Nombre de variantes : {kpis['n_variants']:,}",
        f"- Part de la variante la plus frequente : {kpis['top_variant_share']:.1%}",
        f"- Taux de deviation (non conformite) : {kpis['deviation_rate']:.1%}",
        f"- Fitness moyen : {kpis['avg_fitness']:.4f}",
        f"- Taux de rework moyen : {kpis['overall_rework_rate']:.1%}",
        "",
        f"## Goulots d'etranglement (top {TOP_N})",
    ]
    for b in kpis["top_bottlenecks"]:
        lines.append(
            f"- {b['from']} -> {b['to']} : {b['avg_wait_hours']:.1f} h d'attente moyenne ({b['count']} cas)"
        )

    lines += ["", f"## Activites avec le plus de rework (top {TOP_N})"]
    for r in kpis["top_rework_activities"]:
        lines.append(f"- {r['activity']} : {r['rework_rate']:.1%} des cas")

    lines += ["", f"## Ressources les plus sollicitees (top {TOP_N})"]
    for r in kpis["top_resources"]:
        lines.append(f"- {r['resource']} : {r['n_events']:,} evenements traites")

    lines += ["", "## Recommandations"]
    for reco in recommendations:
        lines.append(f"- {reco}")

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="KPI et recommandations metier")
    parser.add_argument("--config", default=DEFAULT_CONFIG, help="Nom du processus (voir config/)")
    args = parser.parse_args()

    kpis = compute_kpis(args.config)
    recommendations = build_recommendations(kpis)
    kpis["recommendations"] = recommendations

    MODELS_DIR.mkdir(exist_ok=True)
    KPI_SUMMARY_PATH.write_text(json.dumps(kpis, indent=2, ensure_ascii=False), encoding="utf-8")

    REPORTS_DIR.mkdir(exist_ok=True)
    report = format_report(kpis, recommendations)
    BUSINESS_REPORT_PATH.write_text(report, encoding="utf-8")

    print(report)
    print(f"KPI sauvegardes : {KPI_SUMMARY_PATH}")
    print(f"Rapport sauvegarde : {BUSINESS_REPORT_PATH}")


if __name__ == "__main__":
    main()
