"""Tests de l'explicabilite des modeles (SHAP + comparaison de groupes)."""

import numpy as np
import pandas as pd
import pytest
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBClassifier

from src.model_explain import ExplainUnavailable, explain_prediction, outcome_comparison, source_column_of


def test_source_column_of_colonnes_numeriques():
    assert source_column_of("num__elapsed_hours", ["vendor"]) == "elapsed_hours"


def test_source_column_of_colonnes_categorielles():
    assert source_column_of("cat__vendor_OTHER", ["vendor", "item_category"]) == "vendor"


def test_source_column_of_ne_confond_pas_une_colonne_prefixe_d_une_autre():
    """'vendor' est un prefixe litteral de 'vendor_type' : la correspondance
    la plus specifique doit gagner, quel que soit l'ordre de la liste."""
    cols = ["vendor", "vendor_type"]
    assert source_column_of("cat__vendor_type_A", cols) == "vendor_type"
    assert source_column_of("cat__vendor_type_A", list(reversed(cols))) == "vendor_type"
    assert source_column_of("cat__vendor_XYZ", cols) == "vendor"


def _tiny_pipeline_and_row():
    """Petit pipeline XGBoost reel (meme structure que train_model.build_pipeline),
    entraine sur des donnees synthetiques ou une categorie domine clairement."""
    rng = np.random.default_rng(0)
    n = 40
    df = pd.DataFrame({
        "amount": rng.normal(100, 10, n),
        "vendor": rng.choice(["A", "B"], n),
    })
    # Cible fortement liee a "amount" et au vendor "B" : le pipeline doit
    # pouvoir apprendre quelque chose de non trivial a expliquer.
    y = ((df["amount"] > 100) | (df["vendor"] == "B")).astype(int)

    pipeline = Pipeline([
        ("preprocess", ColumnTransformer([
            ("cat", OneHotEncoder(handle_unknown="ignore"), ["vendor"]),
            ("num", "passthrough", ["amount"]),
        ])),
        ("model", XGBClassifier(n_estimators=20, max_depth=2, random_state=0)),
    ])
    pipeline.fit(df[["amount", "vendor"]], y)
    row = df.iloc[[0]][["amount", "vendor"]]
    return pipeline, row


def test_explain_prediction_est_additif_et_coherent_avec_predict_proba():
    pipeline, row = _tiny_pipeline_and_row()
    result = explain_prediction(pipeline, row, categorical_cols=["vendor"], top_n=5)

    assert set(result.keys()) == {"base_value", "prediction", "contributions", "other_impact"}
    total = result["base_value"] + sum(c["impact"] for c in result["contributions"]) + result["other_impact"]
    assert total == pytest.approx(result["prediction"], abs=1e-4)

    # une seule colonne source "vendor" doit apparaitre (jamais "vendor_A"/"vendor_B" separement)
    names = [c["feature"] for c in result["contributions"]]
    assert "vendor" in names
    assert not any(n.startswith("vendor_") for n in names)


def test_explain_prediction_rejette_plusieurs_lignes():
    pipeline, row = _tiny_pipeline_and_row()
    with pytest.raises(ValueError):
        explain_prediction(pipeline, pd.concat([row, row]), categorical_cols=["vendor"])


def test_explain_prediction_signale_shap_indisponible(monkeypatch):
    import src.model_explain as model_explain

    monkeypatch.setattr(model_explain, "SHAP_AVAILABLE", False)
    pipeline, row = _tiny_pipeline_and_row()

    with pytest.raises(ExplainUnavailable):
        explain_prediction(pipeline, row, categorical_cols=["vendor"])


def test_outcome_comparison_detecte_l_ecart_numerique_et_categoriel():
    # Avec seulement 2 categories, tout ecart de proportion est necessairement
    # symetrique (|diff_A| == |diff_B|) : la categorie "la plus discriminante"
    # serait ambigue. Une 3e categorie (C) evite l'egalite et rend "B" gagnant
    # sans ambiguite (|diff|=0.4 pour B, contre 0.3 pour A et 0.1 pour C).
    df = pd.DataFrame({
        "outcome": ["LATE"] * 10 + ["ON_TIME"] * 10,
        "elapsed_hours": [100] * 10 + [10] * 10,
        "vendor": ["B"] * 7 + ["A"] * 2 + ["C"] * 1 + ["A"] * 5 + ["B"] * 3 + ["C"] * 2,
    })
    result = outcome_comparison(df, "outcome", ["elapsed_hours", "vendor"], top_n=5)

    assert set(result["feature"]) == {"elapsed_hours", "vendor"}
    # groupes tries alphabetiquement : group_1="LATE" (moyenne 100), group_2="ON_TIME" (moyenne 10)
    elapsed_row = result[result["feature"] == "elapsed_hours"].iloc[0]
    assert elapsed_row["ecart"] == pytest.approx(10 - 100)
    vendor_row = result[result["feature"] == "vendor"].iloc[0]
    assert vendor_row["categorie"] == "B"


def test_outcome_comparison_exige_exactement_deux_groupes():
    df = pd.DataFrame({"outcome": ["LATE", "ON_TIME", "UNKNOWN"], "amount": [1, 2, 3]})
    with pytest.raises(ValueError):
        outcome_comparison(df, "outcome", ["amount"])


def test_outcome_comparison_ignore_les_colonnes_absentes():
    df = pd.DataFrame({"outcome": ["LATE", "ON_TIME"], "amount": [1, 2]})
    result = outcome_comparison(df, "outcome", ["amount", "colonne_absente"])
    assert list(result["feature"]) == ["amount"]
