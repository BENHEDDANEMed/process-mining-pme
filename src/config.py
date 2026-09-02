"""Chargement de la configuration d'un processus a analyser.

Le coeur de la plateforme est generique : il raisonne en termes de "cas",
"activite" et "horodatage", jamais en termes de colonnes d'un dataset
particulier. Un fichier YAML dans config/ fait le lien entre ces concepts et
les colonnes reelles d'un log donne.

Consequence pratique pour une PME : brancher un nouveau processus (tickets
support, commandes, dossiers RH...) revient a ecrire une dizaine de lignes de
YAML, sans toucher au code d'analyse.

Usage :
    from src.config import load_config
    cfg = load_config("bpi2019")
    df.groupby(cfg.case_id)...
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"

DEFAULT_CONFIG = "bpi2019"


@dataclass(frozen=True)
class AnalysisParams:
    """Parametres numeriques de l'analyse (seuils, tailles d'echantillon)."""

    discovery_top_k_variants: int = 20
    min_transition_count: int = 20
    late_quantile: float = 0.75


@dataclass(frozen=True)
class ProcessConfig:
    """Description complete d'un processus analysable."""

    name: str
    label: str
    description: str

    case_id: str
    activity: str
    timestamp: str
    resource: str | None

    terminal_activities: list[str]
    amount_column: str | None
    categorical_attributes: list[str] = field(default_factory=list)
    analysis: AnalysisParams = field(default_factory=AnalysisParams)

    @property
    def core_columns(self) -> list[str]:
        """Les trois colonnes indispensables a tout traitement process mining."""
        return [self.case_id, self.activity, self.timestamp]


def available_configs() -> list[str]:
    """Noms des processus configures (un fichier .yaml = un processus)."""
    if not CONFIG_DIR.exists():
        return []
    return sorted(p.stem for p in CONFIG_DIR.glob("*.yaml"))


def load_config(name: str = DEFAULT_CONFIG) -> ProcessConfig:
    """Charge la configuration d'un processus depuis config/<name>.yaml."""
    path = CONFIG_DIR / f"{name}.yaml"
    if not path.exists():
        disponibles = ", ".join(available_configs()) or "aucune"
        raise FileNotFoundError(
            f"Configuration '{name}' introuvable ({path}). Configurations disponibles : {disponibles}"
        )

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return _from_dict(raw, source=path)


def _from_dict(raw: dict, source: Path | None = None) -> ProcessConfig:
    origin = f" ({source})" if source else ""

    try:
        columns = raw["columns"]
        case_id = columns["case_id"]
        activity = columns["activity"]
        timestamp = columns["timestamp"]
    except KeyError as exc:
        raise ValueError(
            f"Configuration invalide{origin} : la cle {exc} est obligatoire "
            "(columns.case_id, columns.activity et columns.timestamp)."
        ) from exc

    attributes = raw.get("attributes") or {}
    analysis_raw = raw.get("analysis") or {}

    known = {f for f in AnalysisParams.__dataclass_fields__}
    unknown = set(analysis_raw) - known
    if unknown:
        raise ValueError(
            f"Configuration invalide{origin} : parametre(s) d'analyse inconnu(s) "
            f"{sorted(unknown)}. Attendus : {sorted(known)}."
        )

    return ProcessConfig(
        name=raw.get("name", source.stem if source else "sans-nom"),
        label=raw.get("label", raw.get("name", "")),
        description=(raw.get("description") or "").strip(),
        case_id=case_id,
        activity=activity,
        timestamp=timestamp,
        resource=columns.get("resource"),
        terminal_activities=list(raw.get("terminal_activities") or []),
        amount_column=attributes.get("amount"),
        categorical_attributes=list(attributes.get("categorical") or []),
        analysis=AnalysisParams(**analysis_raw),
    )
