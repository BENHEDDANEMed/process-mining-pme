"""Tests de la preparation des donnees d'entrainement.

Ces tests couvrent les deux pieges qui avaient fait chuter le modele sous le
niveau du hasard (accuracy 48.8%) :

1. la censure temporelle - des cas tronques par la fin du log etaient etiquetes
   "a l'heure" a tort, creant un ecart de distribution entre train et test ;
2. la fuite de donnees - une feature construite a partir d'informations
   posterieures a l'instant de prediction rendrait le modele inutilisable en
   production.
"""

import numpy as np
import pandas as pd
import pytest

from src.preprocess import CASE_ID_COL, ACTIVITY_COL, TIMESTAMP_COL
from src.train_model import (
    add_late_labels, build_prefix_dataset, case_total_hours,
    select_uncensored_cases, temporal_train_test_split,
)

AMOUNT_COL = "Cumulative net worth (EUR)"


def _log(cases: dict) -> pd.DataFrame:
    """Construit un log a partir de {case_id: [(activite, jour), ...]}."""
    rows = []
    for case_id, events in cases.items():
        for activity, day in events:
            rows.append({
                CASE_ID_COL: case_id,
                ACTIVITY_COL: activity,
                TIMESTAMP_COL: pd.Timestamp("2018-01-01", tz="UTC") + pd.Timedelta(days=day),
                AMOUNT_COL: 100.0,
            })
    return pd.DataFrame(rows)


# --- Censure temporelle -----------------------------------------------------

def test_select_uncensored_garde_un_cas_ancien_et_cloture():
    """Un cas cloture et demarre bien avant la fin du log doit etre conserve."""
    log = _log({
        "ancien": [("Create Purchase Order Item", 0), ("Clear Invoice", 10)],
        # Fixe la fin d'observation loin dans le temps, pour que 'ancien' se
        # situe au-dela de l'horizon de censure.
        "recent": [("Create Purchase Order Item", 300), ("Clear Invoice", 310)],
    })

    retenus = set(select_uncensored_cases(log)[CASE_ID_COL].unique())

    assert "ancien" in retenus


def test_select_uncensored_ecarte_un_cas_non_cloture():
    """Un dossier sans activite terminale est encore en cours : sa duree
    observee serait artificiellement courte."""
    log = _log({
        "cloture": [("Create Purchase Order Item", 0), ("Clear Invoice", 10)],
        "en_cours": [("Create Purchase Order Item", 0), ("Record Goods Receipt", 5)],
        "recent": [("Create Purchase Order Item", 300), ("Clear Invoice", 310)],
    })

    retenus = set(select_uncensored_cases(log)[CASE_ID_COL].unique())

    assert "cloture" in retenus
    assert "en_cours" not in retenus


def test_select_uncensored_ecarte_un_cas_demarre_trop_pres_de_la_fin_du_log():
    """Coeur de la correction : meme cloture, un cas demarre juste avant la fin
    du log n'a pas eu le temps de devenir lent, ce qui biaiserait l'etiquetage."""
    log = _log({
        "tot": [("Create Purchase Order Item", 0), ("Clear Invoice", 10)],
        "tard": [("Create Purchase Order Item", 299), ("Clear Invoice", 300)],
    })

    retenus = set(select_uncensored_cases(log)[CASE_ID_COL].unique())

    assert "tot" in retenus
    assert "tard" not in retenus


def test_select_uncensored_resiste_a_un_horodatage_aberrant_rare():
    """La fin d'observation est prise au quantile 99.9% et non au maximum, pour
    qu'une poignee de dates aberrantes ne repousse pas artificiellement la
    fenetre (BPI2019 contient 7 evenements dates jusqu'en 2020 alors que le log
    s'arrete en janvier 2019).

    Limite assumee : cette protection ne vaut que si les aberrations
    representent moins de 0.1% des evenements. Sur un log de quelques centaines
    de lignes, un seul horodatage farfelu deplacerait bien la fenetre.
    """
    normaux = _log({
        f"c{i:04d}": [("Create Purchase Order Item", i % 300), ("Clear Invoice", i % 300 + 5)]
        for i in range(2000)
    })
    aberrant = _log({"aberrant": [("Create Purchase Order Item", 20_000),
                                  ("Clear Invoice", 20_005)]})
    pollue = pd.concat([normaux, aberrant], ignore_index=True)

    retenus_propre = set(select_uncensored_cases(normaux)[CASE_ID_COL].unique())
    retenus_pollue = set(select_uncensored_cases(pollue)[CASE_ID_COL].unique())

    assert retenus_pollue - {"aberrant"} == retenus_propre


# --- Construction des prefixes ---------------------------------------------

@pytest.fixture
def prefixes():
    log = _log({
        "c1": [("Create Purchase Order Item", 0), ("Record Goods Receipt", 2), ("Clear Invoice", 5)],
        "c2": [("Create Purchase Order Item", 0), ("Clear Invoice", 20)],
    })
    return build_prefix_dataset(log)


def test_le_dernier_prefixe_d_un_cas_est_exclu(prefixes):
    """Predire alors que le cas est deja fini n'aurait aucun sens."""
    assert (prefixes[prefixes["case_id"] == "c1"]["prefix_length"] < 3).all()
    assert len(prefixes[prefixes["case_id"] == "c1"]) == 2


def test_elapsed_et_remaining_se_completent(prefixes):
    """A tout instant : temps ecoule + temps restant = duree totale du cas."""
    totaux = case_total_hours(prefixes)

    for case_id, duree_attendue in [("c1", 5 * 24.0), ("c2", 20 * 24.0)]:
        valeurs = totaux[prefixes["case_id"] == case_id]
        assert np.allclose(valeurs, duree_attendue)


def test_les_features_d_historique_n_utilisent_pas_le_futur(prefixes):
    """Verifie l'absence de fuite : au 1er evenement, aucune activite ulterieure
    ne doit etre marquee comme deja realisee."""
    premier = prefixes[(prefixes["case_id"] == "c1") & (prefixes["prefix_length"] == 1)].iloc[0]

    assert premier["done_create_purchase_order_item"] == 1
    assert premier["done_record_goods_receipt"] == 0
    assert premier["done_clear_invoice"] == 0
    assert premier["n_distinct_activities"] == 1
    assert premier["n_rework"] == 0


def test_les_indicateurs_d_activite_sont_cumulatifs(prefixes):
    second = prefixes[(prefixes["case_id"] == "c1") & (prefixes["prefix_length"] == 2)].iloc[0]

    assert second["done_create_purchase_order_item"] == 1  # reste vrai
    assert second["done_record_goods_receipt"] == 1        # vient de se produire
    assert second["n_distinct_activities"] == 2


def test_le_rework_compte_les_activites_repetees():
    log = _log({"c": [("Create Purchase Order Item", 0), ("Create Purchase Order Item", 1),
                      ("Clear Invoice", 3)]})

    prefixes = build_prefix_dataset(log)
    second = prefixes[prefixes["prefix_length"] == 2].iloc[0]

    assert second["n_distinct_activities"] == 1
    assert second["n_rework"] == 1


# --- Separation train/test et etiquetage ------------------------------------

def test_le_split_temporel_ne_partage_aucun_cas():
    log = _log({f"c{i:03d}": [("Create Purchase Order Item", i), ("Clear Invoice", i + 3)]
                for i in range(100)})
    prefixes = build_prefix_dataset(log)

    train, test = temporal_train_test_split(prefixes)

    assert set(train["case_id"]).isdisjoint(set(test["case_id"]))
    assert len(train) > 0 and len(test) > 0


def test_le_split_temporel_met_les_cas_recents_en_test():
    log = _log({f"c{i:03d}": [("Create Purchase Order Item", i), ("Clear Invoice", i + 3)]
                for i in range(100)})
    prefixes = build_prefix_dataset(log)

    train, test = temporal_train_test_split(prefixes)

    assert train["case_start"].max() <= test["case_start"].min()


def test_le_seuil_de_retard_est_appris_sur_le_seul_train():
    """Calculer le seuil sur l'ensemble des donnees serait une fuite du test
    vers l'entrainement."""
    log = _log({f"c{i:03d}": [("Create Purchase Order Item", i),
                              ("Clear Invoice", i + 1 + (i % 10))]
                for i in range(100)})
    prefixes = build_prefix_dataset(log)
    train, test = temporal_train_test_split(prefixes)

    _, _, seuil = add_late_labels(train, test)

    durees_train = case_total_hours(train).groupby(train["case_id"]).first()
    assert seuil == pytest.approx(durees_train.quantile(0.75))


def test_les_deux_classes_sont_presentes_apres_etiquetage():
    log = _log({f"c{i:03d}": [("Create Purchase Order Item", i),
                              ("Clear Invoice", i + 1 + (i % 12))]
                for i in range(120)})
    prefixes = build_prefix_dataset(log)
    train, test = temporal_train_test_split(prefixes)

    train, test, _ = add_late_labels(train, test)

    assert set(train["outcome"]) == {"LATE", "ON_TIME"}
    assert "outcome" in test.columns


def test_toutes_les_lignes_d_un_meme_cas_ont_la_meme_etiquette():
    """L'etiquette porte sur le cas entier, pas sur l'instant de prediction."""
    log = _log({
        "lent": [("Create Purchase Order Item", 0), ("Record Goods Receipt", 10),
                 ("Clear Invoice", 60)],
        "rapide": [("Create Purchase Order Item", 0), ("Record Goods Receipt", 1),
                   ("Clear Invoice", 2)],
    })
    prefixes = build_prefix_dataset(log)
    train, test = temporal_train_test_split(prefixes)
    train, test, _ = add_late_labels(train, test)

    for part in (train, test):
        if not part.empty:
            assert (part.groupby("case_id")["outcome"].nunique() == 1).all()
