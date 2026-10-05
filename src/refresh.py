"""Regenere en une commande les analyses derivees du journal d'evenements.

Enchaine conformite, performance et KPI metier, puis reexporte les tables
Power BI. Pratique apres une modification du journal nettoye ou du fichier de
configuration du processus (config/bpi2019.yaml), sans avoir a relancer
chaque script a la main.

L'entrainement des modeles ML n'est volontairement pas inclus : il est couteux
et n'a pas a etre refait a chaque regeneration. Le relancer manuellement
(`python -m src.train_model`) lors d'une reevaluation periodique.

Usage :
    python -m src.refresh
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / "logs"
LOG_PATH = LOG_DIR / "refresh.log"

# Etapes enchainees, dans l'ordre. Chaque entree : (module, libelle).
STEPS = [
    ("src.conformance_check", "Verification de conformite"),
    ("src.performance_analysis", "Analyse de performance"),
    ("src.business_analysis", "KPI et recommandations metier"),
    ("src.export_powerbi", "Export des tables Power BI"),
]


def log(message: str) -> None:
    """Ecrit sur la sortie standard et dans logs/refresh.log."""
    horodatage = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    ligne = f"[{horodatage}] {message}"
    print(ligne, flush=True)

    LOG_DIR.mkdir(exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(ligne + "\n")


def run_step(module: str, libelle: str) -> bool:
    """Execute une etape. Renvoie True si elle a reussi."""
    log(f"-> {libelle} ({module})")
    debut = datetime.now(timezone.utc)

    resultat = subprocess.run(
        [sys.executable, "-m", module],
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    duree = (datetime.now(timezone.utc) - debut).total_seconds()

    if resultat.returncode == 0:
        log(f"   OK en {duree:.1f}s")
        return True

    log(f"   ECHEC (code {resultat.returncode}) apres {duree:.1f}s")
    # Les dernieres lignes d'erreur suffisent a diagnostiquer sans noyer le journal.
    for ligne in (resultat.stderr or "").strip().splitlines()[-8:]:
        log(f"   | {ligne}")
    return False


def check_interpreter() -> bool:
    """Verifie que l'interpreteur qui lance ce script a bien les dependances
    du projet installees, avant de les propager (via sys.executable) a chaque
    sous-processus.

    Sans ce garde-fou, lancer `refresh.py` avec un autre Python que celui du
    projet (ex. l'interpreteur global choisi par defaut dans un IDE) produit
    un ModuleNotFoundError incomprehensible au milieu d'une etape, plutot
    qu'un message clair au demarrage.
    """
    try:
        import pandas, pm4py  # noqa: F401
        return True
    except ImportError as exc:
        log(f"ERREUR : interpreteur incorrect ({sys.executable})")
        log(f"         module manquant : {exc.name}")
        log("         Lancer ce script avec l'interpreteur du projet, par exemple :")
        log(r"           .venv\Scripts\python -m src.refresh")
        return False


def main() -> int:
    if not check_interpreter():
        return 1

    log(f"=== Regeneration : {len(STEPS)} etape(s) ===")

    echecs = [libelle for module, libelle in STEPS if not run_step(module, libelle)]

    if echecs:
        log(f"=== Termine avec {len(echecs)} echec(s) : {', '.join(echecs)} ===")
        return 1

    log("=== Termine avec succes ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
