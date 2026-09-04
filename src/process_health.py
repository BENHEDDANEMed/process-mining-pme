"""Process Health Score - synthese decisionnelle des analyses existantes.

Ce module ne calcule aucune metrique de process mining : il **resume** en un
score unique (0-100) les KPI deja produits par `business_analysis.py`,
`performance_analysis.py`, `process_metrics.py` et les modeles de
`train_model.py`. C'est une couche de lecture, pas une couche de calcul.

Objectif metier : permettre a un responsable de PME qui ne connait pas le
process mining de savoir en un coup d'oeil si son processus va bien, et par
ou commencer si ce n'est pas le cas.

--------------------------------------------------------------------------
Principe de conception : des metriques SANS ECHELLE
--------------------------------------------------------------------------
Un dossier d'achat BPI2019 dure 64 jours en mediane, un ticket NYC 311 dure
9 minutes. Aucun seuil exprime en heures ne peut donc servir les deux. Chaque
dimension est par consequent reduite a un **ratio** interpretable
independamment du processus (p90/mediane, part des cas deviants, part des
evenements traites par la ressource la plus chargee...), ce qui rend le score
comparable d'un processus a l'autre et conforme a l'architecture generique du
projet.

--------------------------------------------------------------------------
Les cinq dimensions
--------------------------------------------------------------------------
| Dimension      | Mesure                              | Sens          |
|----------------|-------------------------------------|---------------|
| Performance    | p90 / mediane des durees de cas     | bas = mieux   |
| Conformance    | taux de deviation au modele decouvert| bas = mieux   |
| Delay risk     | part des cas signales a risque      | bas = mieux   |
| Rework         | taux de rework moyen                | bas = mieux   |
| Resource load  | part des evenements de la ressource |               |
|                | la plus chargee                     | bas = mieux   |

Une dimension dont le KPI source est absent est **ecartee** (jamais remplacee
par une valeur inventee) et les poids des dimensions restantes sont
renormalises pour que le score final reste sur 100.

--------------------------------------------------------------------------
Limite assumee de la dimension Performance
--------------------------------------------------------------------------
Le rapport p90/mediane mesure la **regularite** des durees, pas la vitesse
absolue. Un processus uniformement lent mais previsible obtient un bon score
sur cette dimension. C'est volontaire : juger la vitesse absolue exigerait un
objectif de delai (SLA) que la plateforme ne connait pas, et l'inventer
reviendrait a fabriquer une valeur. La lenteur absolue reste visible dans les
KPI de la vue d'ensemble ; le score, lui, signale l'irregularite.
"""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

from src.config import DEFAULT_CONFIG, ProcessConfig, load_config

BASE_DIR = Path(__file__).resolve().parent.parent
DIMENSIONS = ("performance", "conformance", "delay_risk", "rework", "resource_load")

DIMENSION_LABELS = {
    "performance": "Performance",
    "conformance": "Conformite",
    "delay_risk": "Risque de retard",
    "rework": "Rework",
    "resource_load": "Charge ressources",
}

# Seuils de classification du score global.
STATUS_THRESHOLDS = (
    (90, "EXCELLENT"),
    (75, "GOOD"),
    (60, "WARNING"),
    (0, "CRITICAL"),
)

# Bornes de normalisation, choisies pour etre lisibles et defendables :
# - PERF : un processus maitrise a un p90 ~2x sa mediane ; au-dela de 25x, la
#   duree d'un dossier est imprevisible. Echelle logarithmique car il s'agit
#   d'un rapport (passer de 2 a 4 est aussi significatif que de 10 a 20).
PERF_RATIO_BEST, PERF_RATIO_WORST = 2.0, 25.0
# - REWORK : au-dela d'un cas sur cinq refait, le processus se reprend en
#   permanence.
REWORK_BEST, REWORK_WORST = 0.0, 0.20
# - RESOURCE : une ressource concentrant plus de la moitie des evenements est
#   un point de fragilite (surcharge, dependance a une personne).
RESOURCE_SHARE_BEST, RESOURCE_SHARE_WORST = 0.10, 0.50


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _as_finite_float(value) -> float | None:
    """Convertit en float exploitable, ou None (None, NaN, inf, texte, ...)."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def normalize_metric(value, best: float, worst: float, log_scale: bool = False) -> float | None:
    """Ramene un KPI brut sur une echelle 0-100, ou None s'il est inexploitable.

    `best` est la valeur qui vaut 100, `worst` celle qui vaut 0 ; l'ordre des
    deux encode donc le sens de la metrique, sans avoir a preciser ailleurs si
    "plus haut" ou "plus bas" est meilleur. Toute valeur au-dela des bornes est
    ramenee dans l'intervalle plutot que de produire un score hors 0-100.

    `log_scale` sert aux rapports (p90/mediane) : un facteur 2 y compte autant
    entre 2 et 4 qu'entre 10 et 20.
    """
    number = _as_finite_float(value)
    if number is None:
        return None

    if log_scale:
        # Le logarithme n'est defini que sur des valeurs strictement positives.
        if min(number, best, worst) <= 0:
            return None
        number, best, worst = math.log(number), math.log(best), math.log(worst)

    span = worst - best
    if span == 0:
        return None

    return round(100.0 * (1.0 - _clamp((number - best) / span)), 1)


# --- Une fonction par dimension --------------------------------------------
# Chacune renvoie (score, detail) ou (None, detail) si le KPI source manque.
# `detail` porte la valeur brute, utilisee pour l'interpretation en clair.


def score_performance(kpis: dict) -> tuple[float | None, dict]:
    """Regularite des durees : rapport entre le 90e percentile et la mediane."""
    p90 = _as_finite_float(kpis.get("p90_case_duration_hours"))
    median = _as_finite_float(kpis.get("median_case_duration_hours"))

    if p90 is None or median is None or median <= 0:
        return None, {}

    ratio = p90 / median
    score = normalize_metric(ratio, PERF_RATIO_BEST, PERF_RATIO_WORST, log_scale=True)
    return score, {"tail_ratio": round(ratio, 2)}


def score_conformance(kpis: dict) -> tuple[float | None, dict]:
    """Part des cas conformes au modele de processus decouvert."""
    deviation = _as_finite_float(kpis.get("deviation_rate"))
    if deviation is None:
        return None, {}

    deviation = _clamp(deviation)
    return round(100.0 * (1.0 - deviation), 1), {"deviation_rate": deviation}


def score_delay_risk(kpis: dict, cfg: ProcessConfig) -> tuple[float | None, dict]:
    """Part des cas que le classifieur existant signale comme a risque.

    Le seuil de retard etant defini au quantile `late_quantile` (0.75 par
    defaut), une part de (1 - late_quantile) = 25% de cas a risque correspond
    a la situation de reference : c'est le taux attendu par construction. On
    note donc l'ecart a cette reference, et le score tombe a 0 quand le double
    est atteint.
    """
    rate = _as_finite_float(kpis.get("high_delay_risk_rate"))
    if rate is None:
        return None, {}

    expected = 1.0 - _clamp(cfg.analysis.late_quantile)
    if expected <= 0:
        return None, {}

    score = normalize_metric(_clamp(rate), best=0.0, worst=2.0 * expected)
    return score, {"high_delay_risk_rate": _clamp(rate), "expected_rate": expected}


def score_rework(kpis: dict) -> tuple[float | None, dict]:
    """Taux de rework moyen tel que calcule par `business_analysis`.

    Il s'agit d'une moyenne sur les activites : une activite refaite dans 50%
    des cas est diluee par les dizaines d'activites jamais repetees. La mesure
    est donc conservatrice, et l'activite la plus touchee est rappelee dans
    l'interpretation pour compenser.
    """
    rate = _as_finite_float(kpis.get("overall_rework_rate"))
    if rate is None:
        return None, {}

    rate = _clamp(rate)
    score = normalize_metric(rate, REWORK_BEST, REWORK_WORST)
    detail = {"overall_rework_rate": rate}

    top = kpis.get("top_rework_activities") or []
    if isinstance(top, list) and top and isinstance(top[0], dict):
        detail["worst_activity"] = top[0].get("activity")
        detail["worst_activity_rate"] = _as_finite_float(top[0].get("rework_rate"))

    return score, detail


def score_resource_load(kpis: dict) -> tuple[float | None, dict]:
    """Concentration de la charge sur la ressource la plus sollicitee.

    Attention : une source qui code l'absence de ressource par un identifiant
    factice (BPI2019 utilise `NONE`) le voit compte comme une ressource a part
    entiere, ce qui gonfle la concentration apparente. Le module n'a aucun
    moyen generique de distinguer un tel marqueur d'un vrai acteur.
    """
    resources = kpis.get("top_resources")
    n_events = _as_finite_float(kpis.get("n_events"))

    if not isinstance(resources, list) or not resources or n_events is None or n_events <= 0:
        return None, {}

    busiest = resources[0]
    if not isinstance(busiest, dict):
        return None, {}

    events = _as_finite_float(busiest.get("n_events"))
    if events is None or events < 0:
        return None, {}

    share = _clamp(events / n_events)
    score = normalize_metric(share, RESOURCE_SHARE_BEST, RESOURCE_SHARE_WORST)
    return score, {"busiest_resource": busiest.get("resource"), "busiest_share": share}


def get_health_status(score: float | None) -> str:
    """Classe un score global : EXCELLENT / GOOD / WARNING / CRITICAL."""
    number = _as_finite_float(score)
    if number is None:
        return "UNKNOWN"

    for threshold, status in STATUS_THRESHOLDS:
        if number >= threshold:
            return status
    return "CRITICAL"


def load_delay_risk_rate(cfg: ProcessConfig) -> float | None:
    """Part des cas que le classifieur signale a risque, si ce processus en a un.

    Lit la sortie deja produite par `src/export_powerbi.py` plutot que de
    rejouer le modele : le Health Score reste une couche de synthese.

    Le chemin vient de `artifacts.predictions` dans le YAML du processus, et
    non d'une constante : un processus sans modele entraine (le flux NYC 311,
    par exemple) n'a pas cette cle et renvoie donc None, ce qui ecarte la
    dimension au lieu de lui appliquer les predictions d'un autre dataset.
    """
    if not cfg.predictions_path:
        return None

    path = BASE_DIR / cfg.predictions_path
    if not path.exists():
        return None
    try:
        predictions = pd.read_csv(path, usecols=["predicted_label"])
    except (ValueError, OSError, pd.errors.ParserError):
        return None
    if predictions.empty:
        return None
    return float((predictions["predicted_label"] == "LATE").mean())


def calculate_process_health(
    kpis: dict,
    cfg: ProcessConfig | None = None,
    delay_risk_rate: float | None = None,
) -> dict:
    """Calcule le Process Health Score a partir de KPI deja produits.

    `kpis` est le dictionnaire de `models/kpi_summary.json` (ou son equivalent
    pour un autre processus). `delay_risk_rate` vient de `load_delay_risk_rate`
    et reste optionnel : sans lui, la dimension est simplement ecartee.
    """
    cfg = cfg or load_config(DEFAULT_CONFIG)
    kpis = dict(kpis or {})

    if delay_risk_rate is not None:
        kpis.setdefault("high_delay_risk_rate", delay_risk_rate)

    computed = {
        "performance": score_performance(kpis),
        "conformance": score_conformance(kpis),
        "delay_risk": score_delay_risk(kpis, cfg),
        "rework": score_rework(kpis),
        "resource_load": score_resource_load(kpis),
    }

    scores = {name: value for name, (value, _) in computed.items()}
    details = {name: detail for name, (_, detail) in computed.items()}

    available = [name for name in DIMENSIONS if scores[name] is not None]
    missing = [name for name in DIMENSIONS if scores[name] is None]

    # Renormalisation : les poids des seules dimensions disponibles sont
    # ramenes a une somme de 1, pour que le score reste sur 100 meme lorsque
    # le processus ne fournit qu'une partie des KPI.
    configured = cfg.health_weights.as_dict()
    total_weight = sum(configured[name] for name in available)

    if not available or total_weight <= 0:
        weights_used: dict[str, float] = {}
        overall = None
    else:
        weights_used = {name: configured[name] / total_weight for name in available}
        overall = round(sum(scores[name] * weights_used[name] for name in available), 1)

    ranked = sorted(available, key=lambda name: scores[name])
    main_weakness = DIMENSION_LABELS[ranked[0]] if ranked else None
    main_strength = DIMENSION_LABELS[ranked[-1]] if ranked else None

    health = {
        "overall_score": overall,
        "status": get_health_status(overall),
        "scores": scores,
        "labels": DIMENSION_LABELS,
        "details": details,
        "available_dimensions": available,
        "missing_dimensions": missing,
        "weights_used": weights_used,
        "main_strength": main_strength,
        "main_weakness": main_weakness,
    }
    health["interpretation"] = interpret(health, kpis)
    return health


def interpret(health: dict, kpis: dict | None = None) -> str:
    """Redige une lecture en clair du score, sans jargon de process mining.

    Interpretation strictement deterministe : chaque phrase decoule d'un seuil
    ou d'une valeur mesuree, aucun modele de langage n'intervient.
    """
    kpis = kpis or {}
    overall = health.get("overall_score")

    if overall is None:
        return (
            "Score indisponible : aucune des dimensions du Process Health Score n'a pu "
            "etre calculee a partir des KPI fournis."
        )

    phrases = [f"Le processus est dans un etat {health['status']} ({overall:.0f}/100)."]

    weakness_key = health["available_dimensions"] and min(
        health["available_dimensions"], key=lambda name: health["scores"][name]
    )
    if weakness_key:
        phrases.append(
            f"Le point faible est {DIMENSION_LABELS[weakness_key].lower()} "
            f"({health['scores'][weakness_key]:.0f}/100){_explain(weakness_key, health, kpis)}"
        )

    strength_key = max(health["available_dimensions"], key=lambda name: health["scores"][name])
    if strength_key != weakness_key:
        phrases.append(
            f"A l'inverse, {DIMENSION_LABELS[strength_key].lower()} reste solide "
            f"({health['scores'][strength_key]:.0f}/100)."
        )

    if health["missing_dimensions"]:
        absentes = ", ".join(DIMENSION_LABELS[name].lower() for name in health["missing_dimensions"])
        phrases.append(
            f"Dimensions non disponibles pour ce processus et donc exclues du calcul : {absentes}."
        )

    return " ".join(phrases)


def _explain(dimension: str, health: dict, kpis: dict) -> str:
    """Complement factuel derriere le score le plus faible."""
    detail = health["details"].get(dimension) or {}

    if dimension == "performance":
        ratio = detail.get("tail_ratio")
        base = (
            f", les 10% de cas les plus lents durant {ratio:.0f} fois plus longtemps "
            "qu'un cas typique" if ratio else ""
        )
        bottlenecks = kpis.get("top_bottlenecks") or []
        if bottlenecks and isinstance(bottlenecks[0], dict):
            worst = bottlenecks[0]
            base += (
                f". L'attente la plus longue se situe entre '{worst.get('from')}' et "
                f"'{worst.get('to')}' ({worst.get('avg_wait_hours')} h en moyenne)"
            )
        return base + "."

    if dimension == "conformance":
        rate = detail.get("deviation_rate")
        return f", avec {rate:.1%} des cas qui s'ecartent du deroulement attendu." if rate is not None else "."

    if dimension == "delay_risk":
        rate, expected = detail.get("high_delay_risk_rate"), detail.get("expected_rate")
        if rate is None:
            return "."
        return (
            f", le modele signalant {rate:.1%} de dossiers a risque "
            f"pour une reference attendue de {expected:.0%}."
        )

    if dimension == "rework":
        activity = detail.get("worst_activity")
        rate = detail.get("worst_activity_rate")
        if activity and rate is not None:
            return f", l'activite la plus reprise etant '{activity}' ({rate:.1%} des cas)."
        return "."

    if dimension == "resource_load":
        resource, share = detail.get("busiest_resource"), detail.get("busiest_share")
        if resource is not None and share is not None:
            return f", '{resource}' traitant a elle seule {share:.1%} des evenements."
        return "."

    return "."


def main() -> None:
    """Affiche le Process Health Score en console (diagnostic rapide)."""
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Process Health Score")
    parser.add_argument("--config", default=DEFAULT_CONFIG, help="Nom du processus (voir config/)")
    parser.add_argument(
        "--kpis", type=Path, default=BASE_DIR / "models" / "kpi_summary.json",
        help="Fichier de KPI a resumer",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    kpis = json.loads(args.kpis.read_text(encoding="utf-8"))
    health = calculate_process_health(kpis, cfg, load_delay_risk_rate(cfg))

    print(f"=== PROCESS HEALTH - {cfg.label} ===\n")
    print(f"  {health['overall_score']} / 100   {health['status']}\n")
    for name in DIMENSIONS:
        score = health["scores"][name]
        rendu = f"{score:>5.1f} / 100" if score is not None else "non disponible"
        print(f"  {DIMENSION_LABELS[name]:<20} {rendu}")
    print(f"\n  Point fort   : {health['main_strength']}")
    print(f"  Point faible : {health['main_weakness']}")
    print(f"\n{health['interpretation']}")


if __name__ == "__main__":
    main()
