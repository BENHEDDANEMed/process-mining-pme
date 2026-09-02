"""Tests du chargement de configuration.

L'interet de ces tests depasse la validation technique : ils garantissent que
brancher un nouveau processus se fait bien par configuration, et qu'une erreur
de saisie dans le YAML produit un message exploitable plutot qu'un plantage
obscur au milieu du pipeline.
"""

import pytest
import yaml

from src.config import _from_dict, available_configs, load_config

CONFIG_MINIMALE = {
    "name": "demo",
    "columns": {"case_id": "cid", "activity": "act", "timestamp": "ts"},
}


def test_les_configurations_du_projet_sont_chargeables():
    """Chaque fichier de config/ doit etre valide."""
    noms = available_configs()

    assert "bpi2019" in noms
    assert "nyc311" in noms
    for nom in noms:
        assert load_config(nom).case_id


def test_bpi2019_expose_les_colonnes_xes():
    cfg = load_config("bpi2019")

    assert cfg.case_id == "case:concept:name"
    assert cfg.activity == "concept:name"
    assert "Clear Invoice" in cfg.terminal_activities
    assert cfg.core_columns == ["case:concept:name", "concept:name", "time:timestamp"]


def test_nyc311_et_bpi2019_decrivent_des_colonnes_differentes():
    """C'est tout l'objet de la generalisation : deux processus, un seul code."""
    bpi = load_config("bpi2019")
    nyc = load_config("nyc311")

    assert bpi.case_id != nyc.case_id
    assert bpi.terminal_activities != nyc.terminal_activities


def test_configuration_inconnue_leve_une_erreur_explicite():
    with pytest.raises(FileNotFoundError, match="Configurations disponibles"):
        load_config("processus-inexistant")


def test_colonne_obligatoire_manquante_est_signalee():
    incomplete = {"name": "demo", "columns": {"case_id": "cid"}}

    with pytest.raises(ValueError, match="obligatoire"):
        _from_dict(incomplete)


def test_parametre_d_analyse_inconnu_est_rejete():
    """Une faute de frappe dans le YAML ne doit pas passer silencieusement."""
    faute = dict(CONFIG_MINIMALE, analysis={"late_quantil": 0.9})

    with pytest.raises(ValueError, match="inconnu"):
        _from_dict(faute)


def test_valeurs_par_defaut_appliquees_si_section_analysis_absente():
    cfg = _from_dict(CONFIG_MINIMALE)

    assert cfg.analysis.late_quantile == 0.75
    assert cfg.analysis.min_transition_count == 20
    assert cfg.terminal_activities == []


def test_config_est_immuable():
    """Evite qu'un module modifie par inadvertance la config partagee."""
    cfg = load_config("bpi2019")

    with pytest.raises(Exception):
        cfg.case_id = "autre"


def test_un_yaml_ecrit_a_la_main_est_utilisable(tmp_path):
    """Simule une PME qui ajoute son propre processus."""
    contenu = yaml.safe_dump({
        "name": "tickets_pme",
        "label": "Support client",
        "columns": {"case_id": "ticket", "activity": "etape", "timestamp": "date"},
        "terminal_activities": ["Resolu"],
    })
    fichier = tmp_path / "tickets_pme.yaml"
    fichier.write_text(contenu, encoding="utf-8")

    cfg = _from_dict(yaml.safe_load(fichier.read_text(encoding="utf-8")), source=fichier)

    assert cfg.label == "Support client"
    assert cfg.case_id == "ticket"
    assert cfg.terminal_activities == ["Resolu"]
