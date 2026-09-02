"""Phase 1 (modifications.md) - Audit generique d'un event log XES.

Calcule les criteres de la section 1 de modifications.md (nombre de cas,
d'evenements, d'activites, ressources, attributs, qualite des timestamps,
valeurs manquantes, doublons, duree des cas, variantes) pour un fichier XES
donne, sans dependre du dataset (BPI2012 ou BPI2019).

Usage:
    python -m src.audit_dataset --xes data/bpi_challenge_2012.xes --name bpi2012
    python -m src.audit_dataset --xes data/raw/bpi_challenge_2019.xes --name bpi2019
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import pm4py

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"

CASE_ID_COL = "case:concept:name"
ACTIVITY_COL = "concept:name"
TIMESTAMP_COL = "time:timestamp"
RESOURCE_COL = "org:resource"


def audit(df: pd.DataFrame) -> dict:
    n_events = len(df)
    n_cases = df[CASE_ID_COL].nunique() if CASE_ID_COL in df.columns else None
    n_activities = df[ACTIVITY_COL].nunique() if ACTIVITY_COL in df.columns else None
    n_resources = df[RESOURCE_COL].nunique() if RESOURCE_COL in df.columns else 0

    missing = df.isna().sum()
    missing = missing[missing > 0].to_dict()
    n_duplicates = int(df.duplicated().sum())

    timestamp_ok = None
    period_start = period_end = None
    avg_duration_h = median_duration_h = None
    n_variants = None
    top_variants = []

    if TIMESTAMP_COL in df.columns:
        ts = pd.to_datetime(df[TIMESTAMP_COL], utc=True, errors="coerce")
        timestamp_ok = int(ts.notna().sum())
        period_start, period_end = ts.min(), ts.max()

        if CASE_ID_COL in df.columns:
            work = df.copy()
            work[TIMESTAMP_COL] = ts
            work = work.dropna(subset=[TIMESTAMP_COL])
            per_case = work.groupby(CASE_ID_COL)[TIMESTAMP_COL].agg(["min", "max"])
            durations = (per_case["max"] - per_case["min"]).dt.total_seconds() / 3600
            avg_duration_h = durations.mean()
            median_duration_h = durations.median()

            if ACTIVITY_COL in df.columns:
                variants = (
                    work.sort_values(TIMESTAMP_COL)
                    .groupby(CASE_ID_COL)[ACTIVITY_COL]
                    .apply(tuple)
                    .value_counts()
                )
                n_variants = len(variants)
                top_variants = variants.head(5).items()

    attributes = list(df.columns)

    return {
        "n_events": n_events,
        "n_cases": n_cases,
        "n_activities": n_activities,
        "n_resources": n_resources,
        "attributes": attributes,
        "missing_values": missing,
        "n_duplicates": n_duplicates,
        "timestamps_valid": timestamp_ok,
        "period_start": period_start,
        "period_end": period_end,
        "avg_case_duration_hours": avg_duration_h,
        "median_case_duration_hours": median_duration_h,
        "n_variants": n_variants,
        "top_variants": top_variants,
    }


def format_report(name: str, xes_path: Path, stats: dict) -> str:
    lines = [
        f"# Audit dataset : {name}",
        "",
        f"Fichier source : `{xes_path}`",
        "",
        "## Volume",
        f"- Nombre d'evenements : {stats['n_events']}",
        f"- Nombre de cas : {stats['n_cases']}",
        f"- Nombre d'activites distinctes : {stats['n_activities']}",
        f"- Nombre de ressources/utilisateurs : {stats['n_resources']}",
        "",
        "## Attributs disponibles",
        f"- {', '.join(stats['attributes'])}",
        "",
        "## Qualite des donnees",
        f"- Valeurs manquantes par colonne : {stats['missing_values'] or 'aucune'}",
        f"- Doublons (lignes identiques) : {stats['n_duplicates']}",
        f"- Timestamps valides : {stats['timestamps_valid']}",
        f"- Periode couverte : {stats['period_start']} -> {stats['period_end']}",
        "",
        "## Duree des cas",
        f"- Duree moyenne (h) : {stats['avg_case_duration_hours']:.1f}"
        if stats["avg_case_duration_hours"] is not None
        else "- Duree moyenne (h) : n/a",
        f"- Duree mediane (h) : {stats['median_case_duration_hours']:.1f}"
        if stats["median_case_duration_hours"] is not None
        else "- Duree mediane (h) : n/a",
        "",
        "## Variantes",
        f"- Nombre de variantes uniques : {stats['n_variants']}",
        "- Top 5 variantes les plus frequentes :",
    ]
    for variant, count in stats["top_variants"]:
        lines.append(f"  - ({count} cas) {' -> '.join(variant)}")

    lines += [
        "",
        "## Aptitude Process Mining (a completer manuellement apres lecture)",
        "- Process Discovery : possible si activites + case id + timestamp presents (voir ci-dessus).",
        "- Conformance Checking : necessite un modele decouvrable (variantes non triviales).",
        "- Analyse de performance : necessite des timestamps fiables (voir periode couverte).",
        "- Cibles Machine Learning envisageables : a definir a partir des attributs listes ci-dessus.",
        "",
    ]
    return "\n".join(lines)


def run_audit(xes_path: Path, name: str) -> Path:
    log = pm4py.read_xes(str(xes_path))
    df = pm4py.convert_to_dataframe(log)
    stats = audit(df)
    report = format_report(name, xes_path, stats)

    REPORTS_DIR.mkdir(exist_ok=True)
    out_path = REPORTS_DIR / f"dataset_audit_{name}.md"
    out_path.write_text(report, encoding="utf-8")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit d'un event log XES")
    parser.add_argument("--xes", type=Path, required=True, help="Chemin du fichier .xes")
    parser.add_argument("--name", type=str, required=True, help="Nom court du dataset (ex: bpi2012, bpi2019)")
    args = parser.parse_args()

    out_path = run_audit(args.xes, args.name)
    print(f"Audit termine : {out_path}")


if __name__ == "__main__":
    main()
