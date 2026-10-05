"""Metriques de process mining, independantes de tout dataset.

Toutes les fonctions de ce module prennent une configuration (src/config.py)
plutot que des noms de colonnes codes en dur : elles s'appliquent donc au
Purchase-to-Pay de BPI2019 comme a tout processus qu'une PME viendrait
brancher via son propre fichier de configuration.

C'est ici que vit la logique d'analyse ; le module `performance_analysis`
ne fait que l'appliquer au journal nettoye et mettre en forme les resultats.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import ProcessConfig


def case_durations_hours(df: pd.DataFrame, cfg: ProcessConfig) -> pd.Series:
    """Duree totale de chaque cas, en heures, indexee par identifiant de cas."""
    per_case = df.groupby(cfg.case_id)[cfg.timestamp].agg(["min", "max"])
    return (per_case["max"] - per_case["min"]).dt.total_seconds() / 3600


def case_sequences(df: pd.DataFrame, cfg: ProcessConfig) -> pd.Series:
    """Sequence d'activites de chaque cas, indexee par identifiant de cas.

    Le tri est stable et porte sur (cas, horodatage) : deux evenements
    simultanes dans un meme cas gardent ainsi leur ordre d'origine, ce qui
    rend le comptage de variantes reproductible d'une execution a l'autre.

    Implementee en numpy plutot qu'en `groupby().apply()` : sur ~250k cas,
    l'appel Python par groupe de `apply()` coute ~55s (mesure), alors que
    trouver les frontieres de groupe sur le tableau trie puis `np.split`
    fait le meme travail en ~1s. Un appelant qui a besoin de plusieurs vues
    derivees (frequences, table de variantes, id par cas) doit calculer les
    sequences UNE fois et les passer aux `*_from_sequences` ci-dessous
    plutot que rappeler cette fonction plusieurs fois.
    """
    if len(df) == 0:
        return pd.Series(dtype=object)

    sorted_df = df.sort_values([cfg.case_id, cfg.timestamp], kind="stable")
    case_ids = sorted_df[cfg.case_id].to_numpy()
    activities = sorted_df[cfg.activity].to_numpy()

    boundaries = np.flatnonzero(case_ids[1:] != case_ids[:-1]) + 1
    chunks = np.split(activities, boundaries)
    chunk_case_ids = case_ids[np.concatenate(([0], boundaries))]
    return pd.Series([tuple(c) for c in chunks], index=chunk_case_ids)


def variant_counts_from_sequences(sequences: pd.Series) -> pd.Series:
    return sequences.value_counts()


def variant_table_from_sequences(sequences: pd.Series) -> pd.DataFrame:
    counts = variant_counts_from_sequences(sequences)
    return pd.DataFrame({
        "variant_id": range(1, len(counts) + 1),
        "sequence": counts.index.to_list(),
        "n_cases": counts.to_numpy(),
    })


def assign_variant_ids_from_sequences(sequences: pd.Series) -> pd.Series:
    """Identifiant de variante (1 = la plus frequente) pour chaque cas.

    Le classement reutilise `.value_counts()` sur les memes sequences que
    `variant_counts_from_sequences` : les identifiants restent coherents
    entre les deux par construction, jamais par coincidence.
    """
    rank = {seq: i + 1 for i, seq in enumerate(sequences.value_counts().index)}
    return sequences.map(rank).rename("variant_id")


def case_variants(df: pd.DataFrame, cfg: ProcessConfig) -> pd.Series:
    """Frequence de chaque sequence d'activites observee."""
    return variant_counts_from_sequences(case_sequences(df, cfg))


def variant_table(df: pd.DataFrame, cfg: ProcessConfig) -> pd.DataFrame:
    """Table des variantes : identifiant (1 = la plus frequente), sequence, effectif."""
    return variant_table_from_sequences(case_sequences(df, cfg))


def assign_variant_ids(df: pd.DataFrame, cfg: ProcessConfig) -> pd.Series:
    """Identifiant de variante (1 = la plus frequente) pour chaque cas."""
    return assign_variant_ids_from_sequences(case_sequences(df, cfg))


def case_rework_counts(df: pd.DataFrame, cfg: ProcessConfig) -> pd.Series:
    """Nombre d'evenements en surplus par cas (au-dela d'une occurrence par activite distincte)."""
    n_events = df.groupby(cfg.case_id).size()
    n_distinct = df.groupby(cfg.case_id)[cfg.activity].nunique()
    return (n_events - n_distinct).rename("rework_count")


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
    robuste aux horodatages desordonnes : sur certaines sources externes, un
    champ peut porter une date de derniere modification plutot qu'une etape
    du cycle de vie, faisant apparaitre l'evenement de cloture avant sa date
    reelle. Un cas clos y resterait donc a tort compte comme ouvert par
    `completed_cases`.
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
