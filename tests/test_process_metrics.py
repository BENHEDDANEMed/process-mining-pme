"""Tests des metriques de process mining generiques."""

import pandas as pd
import pytest

from src.process_metrics import (
    bottlenecks, case_durations_hours, case_variants, closed_cases,
    completed_cases, resource_load, rework_rates, summarize, transition_waits,
)


def test_case_durations_mesure_du_premier_au_dernier_evenement(simple_log, cfg):
    durations = case_durations_hours(simple_log, cfg)

    assert durations["c1"] == pytest.approx(48.0)   # 1 -> 3 janvier
    assert durations["c2"] == pytest.approx(96.0)   # 1 -> 5 janvier
    assert durations["c3"] == pytest.approx(24.0)   # 1 -> 2 janvier


def test_case_variants_compte_les_sequences_distinctes(simple_log, cfg):
    variants = case_variants(simple_log, cfg)

    assert variants[("Ouverture", "Traitement", "Cloture")] == 1
    assert variants[("Ouverture", "Traitement", "Traitement", "Cloture")] == 1
    assert len(variants) == 3


def test_case_variants_ignore_l_ordre_des_lignes_en_entree(simple_log, cfg):
    """Le resultat doit dependre des horodatages, pas de l'ordre du DataFrame."""
    shuffled = simple_log.sample(frac=1, random_state=0).reset_index(drop=True)

    assert case_variants(shuffled, cfg).equals(case_variants(simple_log, cfg))


def test_transition_waits_calcule_l_attente_entre_activites(simple_log, cfg):
    transitions = transition_waits(simple_log, cfg).set_index(["from_activity", "to_activity"])

    # c1 : Traitement (2 jan) -> Cloture (3 jan) = 24 h
    # c2 : Traitement (3 jan) -> Cloture (5 jan) = 48 h  => moyenne 36 h
    assert transitions.loc[("Traitement", "Cloture"), "avg_wait_hours"] == pytest.approx(36.0)
    assert transitions.loc[("Traitement", "Cloture"), "count"] == 2


def test_transition_waits_ne_franchit_pas_la_frontiere_entre_cas(simple_log, cfg):
    """La derniere activite d'un cas ne doit pas etre reliee au cas suivant."""
    transitions = transition_waits(simple_log, cfg)
    paires = set(zip(transitions["from_activity"], transitions["to_activity"]))

    assert ("Cloture", "Ouverture") not in paires


def test_bottlenecks_filtre_les_transitions_trop_rares(simple_log, cfg):
    """Une transition sous le seuil d'occurrences ne doit pas remonter."""
    from dataclasses import replace
    from src.config import AnalysisParams

    exigeant = replace(cfg, analysis=AnalysisParams(min_transition_count=2))
    retenues = bottlenecks(simple_log, exigeant)

    assert (retenues["count"] >= 2).all()
    assert len(retenues) < len(transition_waits(simple_log, cfg))


def test_rework_rates_detecte_les_activites_repetees(simple_log, cfg):
    rework = rework_rates(simple_log, cfg).set_index("activity")

    # Seul c2 repete 'Traitement', sur 3 cas au total.
    assert rework.loc["Traitement", "cases_with_rework"] == 1
    assert rework.loc["Traitement", "rework_rate"] == pytest.approx(1 / 3)
    assert rework.loc["Ouverture", "rework_rate"] == 0.0


def test_closed_cases_reconnait_un_cas_dont_la_cloture_n_est_pas_le_dernier_evenement(cfg):
    """Robustesse aux horodatages desordonnes (cas reel de l'API NYC 311)."""
    log = pd.DataFrame([
        {"case_id": "x", "activity": "Ouverture",
         "timestamp": pd.Timestamp("2024-01-01", tz="UTC"), "resource": "a", "categorie": "A"},
        {"case_id": "x", "activity": "Cloture",
         "timestamp": pd.Timestamp("2024-01-02", tz="UTC"), "resource": "a", "categorie": "A"},
        # Mise a jour horodatee APRES la cloture : frequent quand la source
        # expose une date de derniere modification plutot qu'une etape.
        {"case_id": "x", "activity": "Traitement",
         "timestamp": pd.Timestamp("2024-01-03", tz="UTC"), "resource": "a", "categorie": "A"},
    ])

    assert "x" in closed_cases(log, cfg)       # a atteint un etat terminal
    assert "x" not in completed_cases(log, cfg)  # mais ne finit pas dessus


def test_completed_cases_exclut_les_cas_encore_ouverts(simple_log, cfg):
    completes = completed_cases(simple_log, cfg)

    assert set(completes) == {"c1", "c2"}
    assert "c3" not in completes


def test_resource_load_agrege_par_ressource(simple_log, cfg):
    charge = resource_load(simple_log, cfg).set_index("resource")

    assert charge.loc["bob", "n_events"] == 2
    assert charge.loc["bob", "n_cases"] == 1
    assert charge.loc["alice", "n_cases"] == 3


def test_resource_load_renvoie_un_tableau_vide_sans_colonne_ressource(simple_log, cfg):
    from dataclasses import replace

    sans_ressource = replace(cfg, resource=None)
    assert resource_load(simple_log, sans_ressource).empty


def test_summarize_produit_des_indicateurs_coherents(simple_log, cfg):
    kpis = summarize(simple_log, cfg)

    assert kpis["n_events"] == 9
    assert kpis["n_cases"] == 3
    assert kpis["n_activities"] == 3
    assert kpis["n_closed_cases"] == 2
    assert kpis["closure_rate"] == pytest.approx(2 / 3)
    assert kpis["median_case_duration_hours"] == pytest.approx(48.0)
    assert kpis["n_variants"] == 3


def test_summarize_sur_un_seul_cas_ne_divise_pas_par_zero(cfg):
    log = pd.DataFrame([
        {"case_id": "solo", "activity": "Ouverture",
         "timestamp": pd.Timestamp("2024-01-01", tz="UTC"), "resource": "a", "categorie": "A"},
        {"case_id": "solo", "activity": "Cloture",
         "timestamp": pd.Timestamp("2024-01-02", tz="UTC"), "resource": "a", "categorie": "A"},
    ])

    kpis = summarize(log, cfg)

    assert kpis["n_cases"] == 1
    assert kpis["closure_rate"] == 1.0
    assert kpis["top_variant_share"] == 1.0
