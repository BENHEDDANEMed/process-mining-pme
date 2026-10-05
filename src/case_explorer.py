"""Explorateur de cas : table de recherche et chronologie detaillee d'un cas.

Fonctions pures et generiques (pilotees par ProcessConfig), comme
process_metrics.py : aucune colonne codee en dur, aucun acces disque ici.
"""

from __future__ import annotations

import pandas as pd

from src.config import ProcessConfig
from src.process_metrics import case_durations_hours, completed_cases

TIMELINE_COLUMNS = ["seq", "activity", "timestamp", "resource", "wait_hours_since_prev", "is_repeat", "is_rare"]


def build_case_table(df: pd.DataFrame, cfg: ProcessConfig) -> pd.DataFrame:
    """Une ligne par cas : duree, volume d'evenements, cloture, attributs metier."""
    durations = case_durations_hours(df, cfg)
    grouped = df.groupby(cfg.case_id)
    closed_ids = set(completed_cases(df, cfg))

    table = pd.DataFrame({
        "duration_hours": durations,
        "n_events": grouped.size(),
        "start": grouped[cfg.timestamp].min(),
        "end": grouped[cfg.timestamp].max(),
    })
    table["closed"] = table.index.isin(closed_ids)

    if cfg.amount_column and cfg.amount_column in df.columns:
        amount = pd.to_numeric(df[cfg.amount_column], errors="coerce")
        table["amount"] = amount.groupby(df[cfg.case_id]).last()

    for col in cfg.categorical_attributes:
        if col in df.columns:
            table[col] = grouped[col].first()

    table.index.name = cfg.case_id
    return table.reset_index()


def search_cases(table: pd.DataFrame, columns: list[str], query: str = "") -> pd.DataFrame:
    """Filtre `table` par sous-chaine (insensible a la casse) sur `columns`.

    Ne derive pas les colonnes a chercher de `cfg` : `table` peut avoir ete
    renommee par l'appelant (ex. cles JSON nettoyees cote API) apres
    `build_case_table`, donc c'est a l'appelant de fournir les noms de
    colonnes tels qu'ils existent reellement dans `table`.
    """
    if not query:
        return table

    q = query.lower()
    mask = pd.Series(False, index=table.index)
    for col in columns:
        if col in table.columns:
            mask = mask | table[col].astype(str).str.lower().str.contains(q, na=False, regex=False)
    return table[mask]


def event_timeline(df: pd.DataFrame, cfg: ProcessConfig, case_id: str, rare_quantile: float = 0.10) -> pd.DataFrame:
    """Chronologie d'UN cas : attente depuis l'evenement precedent, ressource,
    activites deja vues dans ce cas (`is_repeat`) ou peu frequentes dans
    l'ensemble du log (`is_rare`, frequence relative globale <= rare_quantile).

    Limitation assumee : la deviation par rapport au modele decouvert n'est
    disponible qu'au niveau du cas entier (voir conformance_report.csv), pas
    evenement par evenement (demanderait de rejouer l'alignement de
    conformite a chaque etape) -- `is_rare`/`is_repeat` sont des indices
    d'anomalie de surface, pas un verdict de conformite.
    """
    case_df = df[df[cfg.case_id] == case_id].sort_values(cfg.timestamp, kind="stable").reset_index(drop=True)
    if case_df.empty:
        return pd.DataFrame(columns=TIMELINE_COLUMNS)

    activity_freq = df[cfg.activity].value_counts(normalize=True)
    rare_activities = set(activity_freq[activity_freq <= rare_quantile].index)

    seen: set = set()
    is_repeat = []
    for act in case_df[cfg.activity]:
        is_repeat.append(act in seen)
        seen.add(act)

    wait_hours = (case_df[cfg.timestamp] - case_df[cfg.timestamp].shift(1)).dt.total_seconds() / 3600
    has_resource = cfg.resource and cfg.resource in case_df.columns

    return pd.DataFrame({
        "seq": range(1, len(case_df) + 1),
        "activity": case_df[cfg.activity],
        "timestamp": case_df[cfg.timestamp],
        "resource": case_df[cfg.resource] if has_resource else None,
        "wait_hours_since_prev": wait_hours.fillna(0.0),
        "is_repeat": is_repeat,
        "is_rare": case_df[cfg.activity].isin(rare_activities).to_numpy(),
    })
