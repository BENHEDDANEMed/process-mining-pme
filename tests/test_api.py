"""Tests d'integration de l'API FastAPI (backend/api.py).

Premiere introduction de TestClient dans ce projet : les autres tests
exercent uniquement des fonctions pures de src/. Ici, chaque fonction de
chargement en cache (@lru_cache) est remplacee par une petite fixture
synthetique -- le vrai dataset (1.46M evenements, modeles entraines sur
disque) n'est jamais touche, donc ces tests restent rapides et
independants de ce qui est present sur la machine qui les execute.
"""

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

import backend.api as api_module

# Fonctions @lru_cache(maxsize=1) du module : nettoyees avant/apres chaque
# test pour qu'aucun cache popule par un test ne fuite vers le suivant.
_LRU_CACHED = [
    "_event_log", "_case_durations_days", "_petri_net", "_variants_df",
    "_conformance_df", "_transitions_df", "_rework_df", "_resources_df",
    "_case_sequences", "_case_variant_ids", "_variant_table_df",
    "_case_rework_counts", "_case_latest_predictions", "_variant_aggregates",
    "_case_table", "_mid_progress_dataset", "_monitoring_snapshot",
]


def _clear_caches():
    for name in _LRU_CACHED:
        getattr(api_module, name).cache_clear()


def _event(case, activity, day, resource="alice"):
    return {
        "case:concept:name": case,
        "concept:name": activity,
        "time:timestamp": pd.Timestamp(f"2024-01-{day:02d}", tz="UTC"),
        "org:resource": resource,
    }


def _synthetic_event_log() -> pd.DataFrame:
    return pd.DataFrame([
        _event("c1", "Ouverture", 1),
        _event("c1", "Traitement", 2),
        _event("c1", "Cloture", 3),
        _event("c2", "Ouverture", 1, resource="bob"),
        _event("c2", "Traitement", 2, resource="bob"),
        _event("c2", "Traitement", 3, resource="bob"),
        _event("c2", "Cloture", 5, resource="bob"),
    ])


def _synthetic_conformance() -> pd.DataFrame:
    return pd.DataFrame([
        {"case_id": "c1", "trace_fitness": 1.0, "is_fit": True, "missing_tokens": 0, "remaining_tokens": 0},
        {"case_id": "c2", "trace_fitness": 0.8, "is_fit": False, "missing_tokens": 1, "remaining_tokens": 1},
    ])


class _StubPipeline:
    """Pipeline factice : predict_proba/predict de forme correcte, sans modele reel."""

    def predict_proba(self, X):
        return np.tile([0.7, 0.3], (len(X), 1))

    def predict(self, X):
        return np.zeros(len(X))


@pytest.fixture
def client(monkeypatch):
    _clear_caches()
    monkeypatch.setattr(api_module, "_event_log", lambda: _synthetic_event_log())
    monkeypatch.setattr(api_module, "_conformance_df", lambda: _synthetic_conformance())
    # Echantillon ML vide par defaut : exerce le chemin "cas non echantillonne"
    # (predicted_label absent) pour tous les cas synthetiques.
    monkeypatch.setattr(api_module, "_prefix_dataset", lambda: pd.DataFrame(columns=["case_id", "prefix_length"]))
    monkeypatch.setattr(
        api_module, "_classifier",
        lambda: {"pipeline": _StubPipeline(), "classes": ["ON_TIME", "LATE"], "feature_cols": [], "decision_threshold": 0.5},
    )
    monkeypatch.setattr(api_module, "_regressor_model", lambda: _StubPipeline())

    yield TestClient(api_module.app)
    # Pas de nettoyage ici : monkeypatch restaure _event_log etc. a leurs
    # vraies fonctions @lru_cache a la fin du test, et le prochain appel a
    # `client` nettoie les caches derivees (_case_table, etc.) AVANT de les
    # re-remplir avec ses propres donnees synthetiques -- nettoyer ici
    # echouerait de toute facon puisque les fonctions remplacees par des
    # lambdas n'ont pas de .cache_clear().


def test_variants_renvoie_les_deux_variantes_synthetiques(client):
    r = client.get("/api/variants?top_n=20")
    assert r.status_code == 200
    body = r.json()

    assert body["total_cases"] == 2
    assert body["total_variants"] == 2
    ids = {v["variant_id"] for v in body["variants"]}
    assert ids == {1, 2}
    assert all(v["n_cases"] == 1 for v in body["variants"])


def test_variants_regroupe_le_reste_sous_other_quand_top_n_est_petit(client):
    r = client.get("/api/variants?top_n=1")
    body = r.json()

    assert len(body["variants"]) == 2  # 1 variante + le bucket "Other"
    other = [v for v in body["variants"] if v["variant_id"] == -1][0]
    assert other["n_cases"] == 1
    assert other["sequence"] is None


def test_cases_list_pagination_de_base(client):
    r = client.get("/api/cases?limit=1&offset=0")
    body = r.json()

    assert body["total"] == 2
    assert len(body["cases"]) == 1
    assert body["limit"] == 1
    assert body["offset"] == 0


def test_cases_list_pagination_au_dela_de_la_fin_ne_plante_pas(client):
    r = client.get("/api/cases?limit=5&offset=999")
    assert r.status_code == 200
    assert r.json()["cases"] == []
    assert r.json()["total"] == 2


def test_cases_list_recherche_par_identifiant(client):
    r = client.get("/api/cases?q=c1")
    body = r.json()

    assert body["total"] == 1
    assert body["cases"][0]["case_id"] == "c1"


def test_cases_list_filtre_par_variant_id(client):
    variants = client.get("/api/variants").json()["variants"]
    target = variants[0]["variant_id"]

    r = client.get(f"/api/cases?variant_id={target}")
    assert all(c["variant_id"] == target for c in r.json()["cases"])


def test_case_detail_cas_connu(client):
    r = client.get("/api/cases/c2")
    assert r.status_code == 200
    body = r.json()

    assert body["case"]["case_id"] == "c2"
    assert len(body["timeline"]) == 4  # Ouverture, Traitement x2, Cloture
    assert body["prediction"] is None  # hors echantillon ML (prefix_dataset vide)
    assert "deviation_note" in body


def test_case_detail_cas_inconnu_renvoie_404(client):
    r = client.get("/api/cases/inconnu")
    assert r.status_code == 404


def _real_tiny_classifier_bundle():
    """Vrai Pipeline XGBoost (meme structure que train_model.build_pipeline),
    entraine sur des donnees synthetiques -- pour tester le vrai chemin SHAP,
    pas seulement le repli "modele indisponible" du _StubPipeline par defaut."""
    from sklearn.compose import ColumnTransformer
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder
    from xgboost import XGBClassifier

    rng = np.random.default_rng(0)
    n = 30
    train_df = pd.DataFrame({"amount": rng.normal(100, 10, n), "vendor": rng.choice(["A", "B"], n)})
    y = (train_df["amount"] > 100).astype(int)
    pipeline = Pipeline([
        ("preprocess", ColumnTransformer([
            ("cat", OneHotEncoder(handle_unknown="ignore"), ["vendor"]),
            ("num", "passthrough", ["amount"]),
        ])),
        ("model", XGBClassifier(n_estimators=10, max_depth=2, random_state=0)),
    ])
    pipeline.fit(train_df[["amount", "vendor"]], y)
    return {"pipeline": pipeline, "classes": ["ON_TIME", "LATE"], "feature_cols": ["amount", "vendor"], "decision_threshold": 0.5}


def test_explain_cas_inconnu_renvoie_404(client):
    r = client.get("/api/prediction/inconnu/1/explain")
    assert r.status_code == 404


def test_explain_degrade_proprement_avec_le_pipeline_stub_par_defaut(client, monkeypatch):
    # Le _StubPipeline par defaut n'a pas de .named_steps : explain_prediction
    # doit echouer proprement (available=False), jamais lever un 500.
    monkeypatch.setattr(api_module, "_prefix_dataset", lambda: pd.DataFrame({"case_id": ["c1"], "prefix_length": [1]}))
    api_module._case_table.cache_clear()

    r = client.get("/api/prediction/c1/1/explain")
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is False
    assert body["reason"] is not None
    assert body["classifier"] is None


def test_explain_avec_un_vrai_pipeline_renvoie_des_contributions_coherentes(client, monkeypatch):
    prefix_df = pd.DataFrame({"case_id": ["c1"], "prefix_length": [1], "amount": [120.0], "vendor": ["A"]})
    monkeypatch.setattr(api_module, "_prefix_dataset", lambda: prefix_df)
    monkeypatch.setattr(api_module, "_classifier", _real_tiny_classifier_bundle)
    monkeypatch.setattr(api_module, "_regressor_model", lambda: _real_tiny_classifier_bundle()["pipeline"])

    r = client.get("/api/prediction/c1/1/explain")
    assert r.status_code == 200
    body = r.json()

    assert body["available"] is True
    assert body["reason"] is None
    for explanation in (body["classifier"], body["regressor"]):
        assert "base_value" in explanation
        assert any(c["feature"] == "amount" for c in explanation["contributions"])


def test_root_cause_sans_echantillon_ml_renvoie_available_false(client):
    r = client.get("/api/root-cause")
    assert r.status_code == 200
    assert r.json()["available"] is False


def test_root_cause_avec_echantillon_renvoie_les_comparaisons(client, monkeypatch):
    prefix_df = pd.DataFrame({
        "case_id": [f"c{i}" for i in range(10)],
        "prefix_length": [1] * 10,
        "elapsed_hours": [100] * 5 + [10] * 5,
        "amount_log": [1.0] * 10,
        "n_distinct_activities": [1] * 10,
        "n_rework": [0] * 10,
        "hours_since_last_event": [0.0] * 10,
        "mean_hours_between_events": [0.0] * 10,
        "max_gap_hours": [0.0] * 10,
        "start_dayofweek": [0] * 10,
        "start_month": [1] * 10,
        "current_dayofweek": [0] * 10,
        "current_activity": ["A"] * 10,
        "vendor": ["V1"] * 10,
        "item_category": ["I1"] * 10,
        "document_type": ["D1"] * 10,
        "spend_area": ["S1"] * 10,
        "company": ["C1"] * 10,
        "item_type": ["T1"] * 10,
        "source": ["SRC1"] * 10,
        "gr_based_inv_verif": ["True"] * 10,
        "goods_receipt": ["True"] * 10,
        "outcome": ["LATE"] * 5 + ["ON_TIME"] * 5,
    })
    monkeypatch.setattr(api_module, "_prefix_dataset", lambda: prefix_df)

    r = client.get("/api/root-cause?top_n=5")
    assert r.status_code == 200
    body = r.json()

    assert body["available"] is True
    assert body["n_late"] == 5
    assert body["n_on_time"] == 5
    assert any(c["feature"] == "elapsed_hours" for c in body["comparisons"])
    assert body["disclaimer"]


def _monitoring_prefix_dataset() -> pd.DataFrame:
    """3 etapes pour 'c1' (pour tester mid_progress_rows + la trajectoire),
    1 seule pour 'c2' -- assez pour exercer le monitoring de bout en bout."""
    return pd.DataFrame({
        "case_id": ["c1", "c1", "c1", "c2"],
        "prefix_length": [1, 2, 3, 1],
        "elapsed_hours": [0.0, 10.0, 20.0, 5.0],
        "amount": [100.0, 100.0, 100.0, 500.0],
        "vendor": ["A", "A", "A", "B"],
    })


class _MonitoringStubPipeline:
    """Probabilite fixe (0.8, > high_min) pour que chaque cas tombe
    deterministiquement dans le bucket HIGH, quel que soit l'ordre issu
    de mid_progress_rows/groupby -- rend les assertions non vacueusement vraies."""

    def predict_proba(self, X):
        return np.tile([0.2, 0.8], (len(X), 1))

    def predict(self, X):
        return np.zeros(len(X))


def test_monitoring_overview_sans_echantillon(client):
    r = client.get("/api/monitoring/overview")
    assert r.status_code == 200
    body = r.json()
    assert body["total_cases"] == 0
    assert body["counts"] == {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
    assert body["thresholds"] == {"low_max": 0.40, "high_min": 0.70}


def test_monitoring_high_risk_sans_echantillon(client):
    r = client.get("/api/monitoring/high-risk")
    assert r.status_code == 200
    assert r.json() == {"cases": [], "total": 0, "limit": 50, "offset": 0}


def test_monitoring_case_history_cas_inconnu_404(client):
    r = client.get("/api/monitoring/case/inconnu/history")
    assert r.status_code == 404


def test_monitoring_overview_avec_echantillon(client, monkeypatch):
    monkeypatch.setattr(api_module, "_prefix_dataset", lambda: _monitoring_prefix_dataset())
    monkeypatch.setattr(
        api_module, "_classifier",
        lambda: {"pipeline": _MonitoringStubPipeline(), "classes": ["ON_TIME", "LATE"], "feature_cols": ["amount", "vendor"], "decision_threshold": 0.5, "late_threshold_hours": 100.0},
    )
    monkeypatch.setattr(api_module, "_regressor_model", lambda: _MonitoringStubPipeline())
    api_module._mid_progress_dataset.cache_clear()
    api_module._monitoring_snapshot.cache_clear()

    r = client.get("/api/monitoring/overview")
    assert r.status_code == 200
    body = r.json()
    assert body["total_cases"] == 2  # 1 ligne mi-parcours par cas (c1, c2)
    assert body["counts"] == {"LOW": 0, "MEDIUM": 0, "HIGH": 2}  # proba fixee a 0.8 par le stub


def test_monitoring_high_risk_filtre_et_trie(client, monkeypatch):
    monkeypatch.setattr(api_module, "_prefix_dataset", lambda: _monitoring_prefix_dataset())
    monkeypatch.setattr(
        api_module, "_classifier",
        lambda: {"pipeline": _MonitoringStubPipeline(), "classes": ["ON_TIME", "LATE"], "feature_cols": ["amount", "vendor"], "decision_threshold": 0.5, "late_threshold_hours": 100.0},
    )
    monkeypatch.setattr(api_module, "_regressor_model", lambda: _MonitoringStubPipeline())
    api_module._mid_progress_dataset.cache_clear()
    api_module._monitoring_snapshot.cache_clear()

    r = client.get("/api/monitoring/high-risk")
    body = r.json()
    assert body["total"] == 2
    assert all(c["predicted_late_probability"] > 0.70 for c in body["cases"])


def test_monitoring_case_history_renvoie_la_trajectoire_triee(client, monkeypatch):
    monkeypatch.setattr(api_module, "_prefix_dataset", lambda: _monitoring_prefix_dataset())
    monkeypatch.setattr(
        api_module, "_classifier",
        lambda: {"pipeline": _MonitoringStubPipeline(), "classes": ["ON_TIME", "LATE"], "feature_cols": ["amount", "vendor"], "decision_threshold": 0.5},
    )

    r = client.get("/api/monitoring/case/c1/history")
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is True
    assert [s["prefix_length"] for s in body["steps"]] == [1, 2, 3]
    assert "instantané figé" in body["note"]


def test_case_table_degrade_proprement_si_le_modele_est_indisponible(client, monkeypatch):
    # Echantillon non vide (sinon le code court-circuite avant meme d'appeler
    # le modele) pour reellement exercer le chemin "modele casse".
    monkeypatch.setattr(
        api_module, "_prefix_dataset",
        lambda: pd.DataFrame({"case_id": ["c1"], "prefix_length": [1]}),
    )

    def _raise():
        raise FileNotFoundError("modele absent")

    monkeypatch.setattr(api_module, "_classifier", _raise)
    api_module._case_latest_predictions.cache_clear()
    api_module._case_table.cache_clear()

    r = client.get("/api/cases")
    assert r.status_code == 200
    assert all(c["predicted_label"] is None for c in r.json()["cases"])
