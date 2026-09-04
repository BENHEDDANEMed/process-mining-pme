"""Tests du Process Health Score.

Le score etant une couche de synthese, ces tests ne verifient aucun calcul de
process mining : ils portent sur la normalisation, la robustesse aux donnees
manquantes ou aberrantes, et la renormalisation des poids lorsqu'une dimension
n'est pas disponible - le cas reel du flux NYC 311, qui n'a ni conformance
checking ni modele de prediction.
"""

import math
from dataclasses import replace

import pytest

from src.config import AnalysisParams, HealthWeights, ProcessConfig
from src.process_health import (
    DIMENSIONS, calculate_process_health, get_health_status, interpret,
    normalize_metric, score_conformance, score_delay_risk, score_performance,
    score_resource_load, score_rework,
)


@pytest.fixture
def cfg() -> ProcessConfig:
    return ProcessConfig(
        name="test",
        label="Processus de test",
        description="",
        case_id="case_id",
        activity="activity",
        timestamp="timestamp",
        resource="resource",
        terminal_activities=["Cloture"],
        amount_column=None,
        analysis=AnalysisParams(late_quantile=0.75),
        health_weights=HealthWeights(),
    )


@pytest.fixture
def kpis_complets() -> dict:
    """KPI d'un processus fournissant les cinq dimensions."""
    return {
        "n_events": 1000,
        "median_case_duration_hours": 100.0,
        "p90_case_duration_hours": 200.0,      # ratio 2.0 -> performance parfaite
        "deviation_rate": 0.10,                 # -> 90
        "high_delay_risk_rate": 0.25,           # = reference attendue -> 50
        "overall_rework_rate": 0.05,            # -> 75
        "top_rework_activities": [{"activity": "Controle", "rework_rate": 0.30}],
        "top_resources": [{"resource": "alice", "n_events": 300}],  # part 0.30 -> 50
    }


# --- normalize_metric : robustesse ------------------------------------------

def test_normalize_situe_la_valeur_entre_les_bornes():
    assert normalize_metric(0.0, best=0.0, worst=100.0) == 100.0
    assert normalize_metric(100.0, best=0.0, worst=100.0) == 0.0
    assert normalize_metric(25.0, best=0.0, worst=100.0) == 75.0


def test_normalize_borne_les_valeurs_hors_intervalle():
    """Un KPI meilleur que 'best' ou pire que 'worst' reste dans 0-100."""
    assert normalize_metric(-50.0, best=0.0, worst=100.0) == 100.0
    assert normalize_metric(500.0, best=0.0, worst=100.0) == 0.0


def test_normalize_gere_le_sens_inverse():
    """best > worst encode une metrique ou 'plus haut vaut mieux'."""
    assert normalize_metric(1.0, best=1.0, worst=0.0) == 100.0
    assert normalize_metric(0.0, best=1.0, worst=0.0) == 0.0


@pytest.mark.parametrize("valeur", [None, float("nan"), float("inf"), "texte", [1, 2]])
def test_normalize_rejette_les_valeurs_inexploitables(valeur):
    assert normalize_metric(valeur, best=0.0, worst=100.0) is None


def test_normalize_ne_divise_pas_par_zero():
    """Des bornes identiques rendraient la pente infinie."""
    assert normalize_metric(5.0, best=10.0, worst=10.0) is None


def test_normalize_log_refuse_les_valeurs_non_positives():
    """Le logarithme n'est pas defini sur zero ou les negatifs."""
    assert normalize_metric(0.0, best=2.0, worst=25.0, log_scale=True) is None
    assert normalize_metric(5.0, best=0.0, worst=25.0, log_scale=True) is None


def test_normalize_log_est_bien_logarithmique():
    """Sur une echelle log, la valeur mediane geometrique donne 50."""
    milieu = math.sqrt(2.0 * 32.0)  # = 8
    assert normalize_metric(milieu, best=2.0, worst=32.0, log_scale=True) == 50.0


# --- Dimensions prises une a une --------------------------------------------

def test_performance_note_la_regularite_des_durees(kpis_complets):
    score, detail = score_performance(kpis_complets)
    assert score == 100.0
    assert detail["tail_ratio"] == 2.0


def test_performance_absente_si_la_mediane_est_nulle():
    """Un log ou la moitie des cas sont instantanes rend le rapport indefini."""
    score, _ = score_performance({"p90_case_duration_hours": 10, "median_case_duration_hours": 0})
    assert score is None


def test_conformance_est_le_complement_du_taux_de_deviation(kpis_complets):
    score, detail = score_conformance(kpis_complets)
    assert score == 90.0
    assert detail["deviation_rate"] == 0.10


def test_delay_risk_est_ancre_sur_le_quantile_de_retard(cfg, kpis_complets):
    """A late_quantile=0.75, 25% de cas a risque est le taux attendu -> 50."""
    score, detail = score_delay_risk(kpis_complets, cfg)
    assert score == 50.0
    assert detail["expected_rate"] == 0.25


def test_delay_risk_suit_le_quantile_configure(cfg, kpis_complets):
    """Changer late_quantile deplace la reference, donc le score."""
    exigeant = replace(cfg, analysis=AnalysisParams(late_quantile=0.90))
    score, detail = score_delay_risk(kpis_complets, exigeant)

    assert detail["expected_rate"] == pytest.approx(0.10)
    assert score == 0.0  # 25% de risque pour 10% attendu : le double est depasse


def test_rework_remonte_l_activite_la_plus_reprise(kpis_complets):
    score, detail = score_rework(kpis_complets)
    assert score == 75.0
    assert detail["worst_activity"] == "Controle"


def test_resource_load_mesure_la_concentration(kpis_complets):
    score, detail = score_resource_load(kpis_complets)
    assert score == 50.0
    assert detail["busiest_share"] == pytest.approx(0.30)


def test_resource_load_absent_sans_evenements():
    """Division par zero : un log vide n'a pas de part a calculer."""
    score, _ = score_resource_load({"n_events": 0, "top_resources": [{"resource": "a", "n_events": 5}]})
    assert score is None


# --- Score global -----------------------------------------------------------

def test_score_global_reste_dans_0_100(cfg, kpis_complets):
    health = calculate_process_health(kpis_complets, cfg)
    assert 0 <= health["overall_score"] <= 100


def test_toutes_les_dimensions_disponibles(cfg, kpis_complets):
    health = calculate_process_health(kpis_complets, cfg)

    assert set(health["available_dimensions"]) == set(DIMENSIONS)
    assert health["missing_dimensions"] == []
    assert all(health["scores"][d] is not None for d in DIMENSIONS)


def test_score_global_est_la_moyenne_ponderee_attendue(cfg, kpis_complets):
    health = calculate_process_health(kpis_complets, cfg)

    attendu = 0.25 * 100 + 0.25 * 90 + 0.20 * 50 + 0.15 * 75 + 0.15 * 50
    assert health["overall_score"] == pytest.approx(attendu, abs=0.1)


def test_dimensions_absentes_exclues_et_poids_renormalises(cfg, kpis_complets):
    """Cas reel du flux NYC 311 : ni conformance, ni modele de prediction."""
    partiels = {k: v for k, v in kpis_complets.items()
                if k not in {"deviation_rate", "high_delay_risk_rate"}}

    health = calculate_process_health(partiels, cfg)

    assert set(health["missing_dimensions"]) == {"conformance", "delay_risk"}
    # Les poids restants (0.25 + 0.15 + 0.15 = 0.55) sont ramenes a 1.
    assert sum(health["weights_used"].values()) == pytest.approx(1.0)
    assert 0 <= health["overall_score"] <= 100


def test_une_dimension_absente_ne_penalise_pas_le_score(cfg, kpis_complets):
    """Une dimension manquante doit etre ecartee, jamais comptee comme zero."""
    sans_conformance = {k: v for k, v in kpis_complets.items() if k != "deviation_rate"}

    avec_zero = calculate_process_health({**kpis_complets, "deviation_rate": 1.0}, cfg)
    sans = calculate_process_health(sans_conformance, cfg)

    assert sans["overall_score"] > avec_zero["overall_score"]


def test_valeurs_nan_traitees_comme_absentes(cfg, kpis_complets):
    pollues = {**kpis_complets, "deviation_rate": float("nan"),
               "overall_rework_rate": float("nan")}

    health = calculate_process_health(pollues, cfg)

    assert "conformance" in health["missing_dimensions"]
    assert "rework" in health["missing_dimensions"]
    assert 0 <= health["overall_score"] <= 100


def test_dataset_vide_ne_produit_aucun_score(cfg):
    health = calculate_process_health({}, cfg)

    assert health["overall_score"] is None
    assert health["status"] == "UNKNOWN"
    assert health["available_dimensions"] == []
    assert health["main_strength"] is None and health["main_weakness"] is None


def test_kpis_none_ne_leve_pas(cfg):
    health = calculate_process_health(None, cfg)
    assert health["overall_score"] is None


def test_delay_risk_fourni_en_argument_alimente_la_dimension(cfg, kpis_complets):
    """Le taux vient de l'export des predictions, pas du fichier de KPI."""
    sans_risque = {k: v for k, v in kpis_complets.items() if k != "high_delay_risk_rate"}

    health = calculate_process_health(sans_risque, cfg, delay_risk_rate=0.25)

    assert health["scores"]["delay_risk"] == 50.0


# --- Classification et lecture ----------------------------------------------

@pytest.mark.parametrize("score,attendu", [
    (95, "EXCELLENT"), (90, "EXCELLENT"),
    (80, "GOOD"), (75, "GOOD"),
    (65, "WARNING"), (60, "WARNING"),
    (40, "CRITICAL"), (0, "CRITICAL"),
])
def test_classification_du_score(score, attendu):
    assert get_health_status(score) == attendu


def test_classification_d_un_score_indisponible():
    assert get_health_status(None) == "UNKNOWN"
    assert get_health_status(float("nan")) == "UNKNOWN"


def test_identification_du_point_fort_et_du_point_faible(cfg, kpis_complets):
    health = calculate_process_health(kpis_complets, cfg)

    # performance 100 (max) ; delay_risk et resource_load a 50 (min ex aequo).
    assert health["main_strength"] == "Performance"
    assert health["scores"]["performance"] == 100.0
    faible = min(health["available_dimensions"], key=lambda d: health["scores"][d])
    assert health["scores"][faible] == 50.0


def test_interpretation_cite_le_statut_et_le_point_faible(cfg, kpis_complets):
    health = calculate_process_health(kpis_complets, cfg)
    texte = health["interpretation"]

    assert health["status"] in texte
    assert str(int(health["overall_score"])) in texte
    assert health["main_weakness"].lower() in texte.lower()


def test_interpretation_signale_les_dimensions_absentes(cfg, kpis_complets):
    partiels = {k: v for k, v in kpis_complets.items() if k != "deviation_rate"}
    texte = calculate_process_health(partiels, cfg)["interpretation"]

    assert "non disponibles" in texte.lower()
    assert "conformite" in texte.lower()


def test_interpretation_d_un_score_indisponible(cfg):
    texte = interpret(calculate_process_health({}, cfg))
    assert "indisponible" in texte.lower()
