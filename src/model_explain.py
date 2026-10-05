"""Explicabilite des modeles ML (root-cause analysis) : contributions SHAP
d'une prediction, et comparaison agregee entre deux groupes de cas (ex.
en retard vs a l'heure) sur les attributs metier.

Les deux modeles sont des Pipeline sklearn a deux etapes ("preprocess": un
ColumnTransformer OneHotEncoder+passthrough, "model": XGBClassifier ou
XGBRegressor -- voir src/train_model.py:build_pipeline). SHAP doit expliquer
le modele et les features REELLEMENT utilisees en production, jamais une
approximation : on extrait donc les deux etapes du pipeline deja entraine
plutot que de reconstruire quoi que ce soit.

Les contributions SHAP d'un XGBoost sont additives dans l'espace BRUT du
modele (log-odds pour le classifieur, log1p(heures) pour le regresseur), pas
directement en points de pourcentage ou en heures. Fabriquer une conversion
vers ces unites romprait l'additivite (la somme ne correspondrait plus a la
prediction) et donnerait une fausse impression de precision : cet espace
brut est donc expose tel quel (colonne `impact`), le signe et l'ordre de
grandeur relatif restant corrects et suffisants pour identifier les facteurs
qui poussent le plus la prediction dans un sens ou l'autre.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline

try:
    import shap
    SHAP_AVAILABLE = True
except ImportError:  # pragma: no cover - exerce uniquement si shap n'est pas installe
    SHAP_AVAILABLE = False


class ExplainUnavailable(RuntimeError):
    """SHAP n'est pas installe, ou le pipeline n'a pas la structure attendue."""


def source_column_of(encoded_name: str, categorical_cols: list[str]) -> str:
    """'cat__vendor_OTHER' -> 'vendor' ; 'num__elapsed_hours' -> 'elapsed_hours'.

    Le prefixe de ColumnTransformer ("cat__"/"num__") est retire, puis pour
    une colonne categorielle (one-hot-encodee en "col_valeur"), le nom de la
    colonne source est retrouve par correspondance de prefixe EXACTE contre
    `categorical_cols` -- jamais par un simple split sur "_", qui casserait
    si une valeur de categorie contient elle-meme un underscore.

    Teste les colonnes candidates de la plus longue a la plus courte : si
    une colonne ("vendor") est elle-meme le prefixe d'une autre
    ("vendor_type"), la plus specifique doit gagner quel que soit l'ordre
    de `categorical_cols`.
    """
    name = encoded_name.split("__", 1)[-1]
    for col in sorted(categorical_cols, key=len, reverse=True):
        if name == col or name.startswith(col + "_"):
            return col
    return name


def _to_native(value):
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    return value


def explain_prediction(pipeline: Pipeline, row: pd.DataFrame, categorical_cols: list[str], top_n: int = 8) -> dict:
    """Contributions SHAP d'une seule ligne, agregees par colonne source.

    `row` : DataFrame a exactement une ligne, avec les memes colonnes/ordre
    que celles utilisees a l'entrainement (bundle["feature_cols"]).
    """
    if not SHAP_AVAILABLE:
        raise ExplainUnavailable("Le module shap n'est pas installe.")
    if len(row) != 1:
        raise ValueError(f"explain_prediction attend exactement 1 ligne, recu {len(row)}")

    preprocess, model = pipeline.named_steps["preprocess"], pipeline.named_steps["model"]
    transformed = preprocess.transform(row)
    feature_names = preprocess.get_feature_names_out()

    explainer = shap.TreeExplainer(model, feature_perturbation="tree_path_dependent")
    raw_values = np.asarray(explainer.shap_values(transformed))[0]
    base_value = float(np.asarray(explainer.expected_value).reshape(-1)[0])
    prediction = float(base_value + raw_values.sum())

    contributions = (
        pd.Series(raw_values, index=feature_names)
        .groupby(lambda n: source_column_of(n, categorical_cols))
        .sum()
    )
    contributions = contributions.reindex(contributions.abs().sort_values(ascending=False).index)

    top = contributions.head(top_n)
    other_impact = float(contributions.iloc[top_n:].sum()) if len(contributions) > top_n else 0.0
    feature_values = row.iloc[0]

    return {
        "base_value": base_value,
        "prediction": prediction,
        "contributions": [
            {"feature": name, "value": _to_native(feature_values.get(name)), "impact": float(impact)}
            for name, impact in top.items()
        ],
        "other_impact": other_impact,
    }


def outcome_comparison(df: pd.DataFrame, group_col: str, feature_cols: list[str], top_n: int = 8) -> pd.DataFrame:
    """Compare deux groupes de `group_col` (typiquement LATE vs ON_TIME) sur
    chaque colonne de `feature_cols` : ecart de moyenne pour une colonne
    numerique, categorie la plus discriminante (et son ecart de proportion)
    pour une colonne categorielle.

    Ne calcule qu'une ASSOCIATION statistique observee dans l'historique,
    jamais une causalite -- le tri ne porte que sur l'ampleur de l'ecart.
    """
    groups = sorted(df[group_col].dropna().unique().tolist())
    if len(groups) != 2:
        raise ValueError(f"outcome_comparison attend exactement 2 groupes, recu {groups!r}")
    g1, g2 = groups

    rows = []
    for col in feature_cols:
        if col not in df.columns:
            continue
        series = df[col]
        if pd.api.types.is_numeric_dtype(series):
            mean1 = float(series[df[group_col] == g1].mean())
            mean2 = float(series[df[group_col] == g2].mean())
            rows.append({
                "feature": col, "type": "numerique",
                "group_1": g1, "group_2": g2,
                "value_1": mean1, "value_2": mean2,
                "ecart": mean2 - mean1,
            })
        else:
            prop1 = df.loc[df[group_col] == g1, col].value_counts(normalize=True)
            prop2 = df.loc[df[group_col] == g2, col].value_counts(normalize=True)
            categories = set(prop1.index) | set(prop2.index)
            if not categories:
                continue
            diffs = {c: float(prop2.get(c, 0.0) - prop1.get(c, 0.0)) for c in categories}
            top_cat = max(diffs, key=lambda c: abs(diffs[c]))
            rows.append({
                "feature": col, "type": "categoriel", "categorie": top_cat,
                "group_1": g1, "group_2": g2,
                "value_1": float(prop1.get(top_cat, 0.0)), "value_2": float(prop2.get(top_cat, 0.0)),
                "ecart": diffs[top_cat],
            })

    result = pd.DataFrame(rows)
    if result.empty:
        return result
    order = result["ecart"].abs().sort_values(ascending=False).index
    return result.reindex(order).head(top_n).reset_index(drop=True)
