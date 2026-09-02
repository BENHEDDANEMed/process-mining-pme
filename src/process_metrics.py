"""Metriques de process mining, independantes de tout dataset.

Toutes les fonctions de ce module prennent une configuration (src/config.py)
plutot que des noms de colonnes codes en dur : elles s'appliquent donc
indifferemment au Purchase-to-Pay de BPI2019 ou au flux de reclamations
NYC 311, et a tout processus qu'une PME viendrait brancher.

C'est ici que vit la logique d'analyse ; les modules `performance_analysis`
et `live_analysis` ne font que l'appliquer a leur source respective et mettre
en forme les resultats.
"""

from __future__ import annotations

import pandas as pd

from src.config import ProcessConfig


def case_durations_hours(df: pd.DataFrame, cfg: ProcessConfig) -> pd.Series:
    """Duree totale de chaque cas, en heures, indexee par identifiant de cas."""
    per_case = df.groupby(cfg.case_id)[cfg.timestamp].agg(["min", "max"])
    return (per_case["max"] - per_case["min"]).dt.total_seconds() / 3600


def case_variants(df: pd.DataFrame, cfg: ProcessConfig) -> pd.Series:
    """Frequence de chaque sequence d'activites observee.

    Le tri est stable et porte sur (cas, horodatage) : deux evenements
    simultanes dans un meme cas gardent ainsi leur ordre d'origine, ce qui
    rend le comptage de variantes reproductible d'une execution a l'autre.
    """
    return (
        df.sort_values([cfg.case_id, cfg.timestamp], kind="stable")
        .groupby(cfg.case_id)[cfg.activity]
        .apply(tuple)
        .value_counts()
    )


def transition_waits(df: pd.DataFrame, cfg: ProcessConfig) -> pd.DataFrame:
    """Temps d'attente entre chaque paire d'activites consecutives.

    Revele les goulots d'etranglement : les transitions ou un dossier stagne
    le plus longtemps avant de passer a l'etape suivante.
    """
    work = df.sort_values([cfg.case_id, cfg.timestamp], kind="stable").copy()
    work["next_activity"] = work.groupby(cfg.case_id)[cfg.activity].shift(-1)
    work["next_timestamp"] = work.groupby(cfg.case_id)[cfg.timestamp].shift(-1)
    work = work.dropna(subset=["next_activity"])

    wait_hours = (work["next_timestamp"] - work[cfg.timestamp]).dt.total_seconds() / 3600

    transitions = pd.DataFrame({
        "from_activity": work[cfg.activity].to_numpy(),
        "to_activity": work["next_activity"].to_numpy(),
        "wait_hours": wait_hours.to_numpy(),
    })

    return (
        transitions.groupby(["from_activity", "to_activity"])["wait_hours"]
        .agg(count="count", avg_wait_hours="mean", median_wait_hours="median")
        .reset_index()
        .sort_values("avg_wait_hours", ascending=False)
    )


def bottlenecks(df: pd.DataFrame, cfg: ProcessConfig, top_n: int = 5) -> pd.DataFrame:
    """Principaux goulots, filtres sur un nombre minimal d'occurrences.

    Sans ce filtre, une transition vue deux fois avec une attente aberrante
    passerait devant un goulot recurrent et reellement couteux.
    """
    transitions = transition_waits(df, cfg)
    significant = transitions[transitions["count"] >= cfg.analysis.min_transition_count]
    return significant.head(top_n)


def rework_rates(df: pd.DataFrame, cfg: ProcessConfig) -> pd.DataFrame:
    """Part des cas ou chaque activite est realisee plus d'une fois."""
    counts = df.groupby([cfg.case_id, cfg.activity]).size().rename("n").reset_index()
    n_cases = df[cfg.case_id].nunique()

    rework = (
        counts.assign(is_rework=counts["n"] > 1)
        .groupby(cfg.activity)["is_rework"]
        .sum()
        .rename("cases_with_rework")
        .reset_index()
        .rename(columns={cfg.activity: "activity"})
    )
    rework["rework_rate"] = rework["cases_with_rework"] / n_cases if n_cases else 0.0
    return rework.sort_values("rework_rate", ascending=False)


def resource_load(df: pd.DataFrame, cfg: ProcessConfig) -> pd.DataFrame:
    """Charge de travail par ressource et duree moyenne des cas traites."""
    empty = pd.DataFrame(columns=["resource", "n_events", "n_cases", "avg_case_duration_hours"])
    if not cfg.resource or cfg.resource not in df.columns:
        return empty

    durations = case_durations_hours(df, cfg)
    work = df.dropna(subset=[cfg.resource]).copy()
    work["case_duration_hours"] = work[cfg.case_id].map(durations)

    return (
        work.groupby(cfg.resource)
        .agg(
            n_events=(cfg.activity, "count"),
            n_cases=(cfg.case_id, "nunique"),
            avg_case_duration_hours=("case_duration_hours", "mean"),
        )
        .reset_index()
        .rename(columns={cfg.resource: "resource"})
        .sort_values("n_events", ascending=False)
    )


def closed_cases(df: pd.DataFrame, cfg: ProcessConfig) -> pd.Index:
    """Cas ayant ATTEINT un etat terminal (l'activite de cloture y figure).

    Repond a la question metier "ce dossier a-t-il ete traite ?". Volontairement
    robuste aux horodatages desordonnes : sur certaines sources, l'evenement de
    cloture n'est pas le dernier chronologiquement (cf. le champ
    `resolution_action_updated_date` de l'API NYC 311, qui porte une date de
    derniere modification et non une etape du cycle de vie). Un ticket clos y
    resterait donc a tort compte comme ouvert par `completed_cases`.
    """
    if not cfg.terminal_activities:
        return pd.Index(df[cfg.case_id].unique())

    reached = df[df[cfg.activity].isin(cfg.terminal_activities)][cfg.case_id].unique()
    return pd.Index(reached)


def completed_cases(df: pd.DataFrame, cfg: ProcessConfig) -> pd.Index:
    """Cas dont la DERNIERE activite est terminale (definition stricte).

    Repond a la question analytique "ce cas s'est-il termine dans la fenetre
    d'observation ?". C'est le critere a utiliser avant tout calcul de duree ou
    tout entrainement de modele : un cas encore en cours a une duree observee
    artificiellement courte, qui biaiserait moyennes et predictions (voir la
    correction de censure temporelle dans le README).
    """
    if not cfg.terminal_activities:
        return pd.Index(df[cfg.case_id].unique())

    last_activity = (
        df.sort_values([cfg.case_id, cfg.timestamp], kind="stable")
        .groupby(cfg.case_id)[cfg.activity]
        .last()
    )
    return last_activity.index[last_activity.isin(cfg.terminal_activities)]


def summarize(df: pd.DataFrame, cfg: ProcessConfig) -> dict:
    """Indicateurs de synthese d'un log, quel que soit le processus."""
    durations = case_durations_hours(df, cfg)
    variants = case_variants(df, cfg)
    n_cases = int(df[cfg.case_id].nunique())
    n_closed = len(closed_cases(df, cfg))

    return {
        "n_events": int(len(df)),
        "n_cases": n_cases,
        "n_activities": int(df[cfg.activity].nunique()),
        "n_closed_cases": n_closed,
        "closure_rate": float(n_closed / n_cases) if n_cases else 0.0,
        "period_start": str(df[cfg.timestamp].min()),
        "period_end": str(df[cfg.timestamp].max()),
        "avg_case_duration_hours": float(durations.mean()),
        "median_case_duration_hours": float(durations.median()),
        "min_case_duration_hours": float(durations.min()),
        "max_case_duration_hours": float(durations.max()),
        "p90_case_duration_hours": float(durations.quantile(0.90)),
        "n_variants": int(len(variants)),
        "top_variant_share": float(variants.iloc[0] / n_cases) if n_cases and len(variants) else 0.0,
    }
