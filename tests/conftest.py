"""Fixtures partagees : petits logs d'evenements construits a la main.

Les tests n'utilisent jamais le dataset BPI2019 complet : ils travaillent sur
des logs miniatures dont on connait la reponse attendue a l'avance. C'est ce
qui permet de verifier la logique - et non de simplement constater qu'elle
tourne.
"""

import pandas as pd
import pytest

from src.config import AnalysisParams, ProcessConfig


@pytest.fixture
def cfg() -> ProcessConfig:
    """Configuration minimale d'un processus de test."""
    return ProcessConfig(
        name="test",
        label="Processus de test",
        description="",
        case_id="case_id",
        activity="activity",
        timestamp="timestamp",
        resource="resource",
        terminal_activities=["Cloture"],
        amount_column="amount",
        categorical_attributes=["categorie"],
        analysis=AnalysisParams(min_transition_count=1, late_quantile=0.75),
    )


def _event(case, activity, day, hour=0, resource="alice", categorie="A"):
    return {
        "case_id": case,
        "activity": activity,
        "timestamp": pd.Timestamp(f"2024-01-{day:02d} {hour:02d}:00", tz="UTC"),
        "resource": resource,
        "categorie": categorie,
    }


@pytest.fixture
def simple_log() -> pd.DataFrame:
    """Trois cas aux profils volontairement differents.

    - c1 : parcours nominal, cloture, 2 jours
    - c2 : rework sur 'Traitement', cloture, 4 jours
    - c3 : encore ouvert (pas de cloture), 1 jour observe
    """
    rows = [
        _event("c1", "Ouverture", 1),
        _event("c1", "Traitement", 2),
        _event("c1", "Cloture", 3),

        _event("c2", "Ouverture", 1),
        _event("c2", "Traitement", 2, resource="bob"),
        _event("c2", "Traitement", 3, resource="bob", categorie="B"),
        _event("c2", "Cloture", 5, categorie="B"),

        _event("c3", "Ouverture", 1),
        _event("c3", "Traitement", 2),
    ]
    return pd.DataFrame(rows)
