"""Tests de l'explorateur de cas (table de recherche + chronologie)."""

import pandas as pd
import pytest

from src.case_explorer import build_case_table, event_timeline, search_cases


def test_build_case_table_agrege_une_ligne_par_cas(simple_log, cfg):
    table = build_case_table(simple_log, cfg).set_index("case_id")

    assert set(table.index) == {"c1", "c2", "c3"}
    assert table.loc["c1", "n_events"] == 3
    assert table.loc["c2", "n_events"] == 4
    assert bool(table.loc["c1", "closed"]) is True
    assert bool(table.loc["c3", "closed"]) is False
    assert table.loc["c1", "duration_hours"] == pytest.approx(48.0)
    assert table.loc["c2", "categorie"] == "A"  # premiere valeur du cas (avant le passage a "B")
    assert "amount" not in table.columns  # colonne absente du log de test : pas d'invention de champ


def test_search_cases_filtre_par_identifiant(simple_log, cfg):
    table = build_case_table(simple_log, cfg)
    columns = [cfg.case_id] + cfg.categorical_attributes

    assert set(search_cases(table, columns, "c1")["case_id"]) == {"c1"}
    assert set(search_cases(table, columns, "")["case_id"]) == {"c1", "c2", "c3"}
    assert search_cases(table, columns, "zzz").empty


def test_search_cases_filtre_aussi_sur_un_attribut_metier(simple_log, cfg):
    table = build_case_table(simple_log, cfg)
    columns = [cfg.case_id] + cfg.categorical_attributes

    # Les trois cas ont "A" comme premiere valeur de categorie.
    assert set(search_cases(table, columns, "a")["case_id"]) == {"c1", "c2", "c3"}


def test_search_cases_fonctionne_sur_une_table_dont_les_colonnes_ont_ete_renommees(simple_log, cfg):
    """Reproduit l'usage reel (backend/api.py) : la table est renommee apres
    build_case_table, search_cases doit chercher sur les noms EFFECTIFS."""
    table = build_case_table(simple_log, cfg).rename(columns={"categorie": "category"})

    assert set(search_cases(table, ["case_id", "category"], "a")["case_id"]) == {"c1", "c2", "c3"}


def test_event_timeline_calcule_les_attentes_et_le_rework(simple_log, cfg):
    timeline = event_timeline(simple_log, cfg, "c2")

    assert list(timeline["activity"]) == ["Ouverture", "Traitement", "Traitement", "Cloture"]
    assert timeline["wait_hours_since_prev"].iloc[0] == 0.0
    assert timeline["wait_hours_since_prev"].iloc[1] == pytest.approx(24.0)
    assert list(timeline["is_repeat"]) == [False, False, True, False]


def test_event_timeline_cas_inconnu_renvoie_un_tableau_vide(simple_log, cfg):
    assert event_timeline(simple_log, cfg, "inconnu").empty


def test_event_timeline_marque_les_activites_rares(cfg):
    ligne = lambda heure, activite: {
        "case_id": "x", "activity": activite,
        "timestamp": pd.Timestamp("2024-01-01", tz="UTC") + pd.Timedelta(hours=heure),
        "resource": "a", "categorie": "A",
    }
    log = pd.DataFrame([ligne(i, "Commun") for i in range(9)] + [ligne(9, "Exception")])
    timeline = event_timeline(log, cfg, "x").set_index("seq")

    assert timeline.loc[10, "activity"] == "Exception"
    assert bool(timeline.loc[10, "is_rare"]) is True
    assert bool(timeline.loc[1, "is_rare"]) is False
