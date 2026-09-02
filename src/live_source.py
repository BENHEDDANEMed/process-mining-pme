"""Volet complementaire - ingestion d'un flux de donnees VIVANT via une API publique.

Le dataset BPI Challenge 2019 (utilise pour l'analyse principale du projet) est un
jeu de recherche fige, publie une fois pour toutes. Pour demontrer que la
plateforme sait aussi ingerer des donnees qui se renouvellent reellement dans le
temps (ce qu'attendrait une PME branchant son propre systeme), ce module
interroge l'API publique NYC 311 (Socrata) : des dizaines de nouvelles
reclamations/tickets de service y sont enregistrees chaque heure.

Le processus modelise est un cycle de vie de ticket de support/reclamation
(ouverture -> mise a jour -> cloture), directement transposable a un service
client de PME - le meme type de raisonnement (delai, SLA, goulots) que pour le
Purchase-to-Pay de BPI2019, mais sur une source qui bouge reellement a chaque
appel.

Cle d'API : un app_token Socrata gratuit augmente fortement les quotas (voir
https://data.cityofnewyork.us/profile/edit/developer_settings). Sans token,
l'API repond quand meme mais avec un throttling plus agressif. Placer le token
dans un fichier .env a la racine du projet :
    SOCRATA_APP_TOKEN=xxxxxxxx

Usage :
    python -m src.live_source
"""

from __future__ import annotations

import os
import ssl
from pathlib import Path

import certifi
import pandas as pd
import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
LIVE_DATA_DIR = BASE_DIR / "data" / "live"
CERTS_DIR = BASE_DIR / "certs"
LOCAL_ROOT_CERT = BASE_DIR / "avast-root.crt"
COMBINED_BUNDLE = CERTS_DIR / "ca_bundle.pem"

NYC311_ENDPOINT = "https://data.cityofnewyork.us/resource/erm2-nwe9.json"
APP_TOKEN = os.getenv("SOCRATA_APP_TOKEN")

CASE_ID_COL = "case_id"
ACTIVITY_COL = "activity"
TIMESTAMP_COL = "timestamp"

RAW_SNAPSHOT_PATH = LIVE_DATA_DIR / "nyc311_raw_snapshot.parquet"
EVENT_LOG_PATH = LIVE_DATA_DIR / "nyc311_events.parquet"


class _LocalTrustAdapter(HTTPAdapter):
    """Adaptateur HTTPS acceptant une autorite racine locale d'interception SSL.

    Sur un poste equipe d'un antivirus qui inspecte le trafic HTTPS (ici Avast),
    toutes les connexions sont re-signees par une autorite racine generee
    localement. Deux ajustements sont necessaires :

    - ajouter cette racine au magasin de confiance (bundle certifi + racine locale) ;
    - desactiver VERIFY_X509_STRICT, active par defaut depuis Python 3.13 : le
      certificat genere par Avast n'est pas conforme au RFC 5280 (extension
      Basic Constraints non marquee critique) et serait rejete malgre sa presence
      dans le magasin.

    La verification du certificat serveur reste active : seul le controle de
    conformite formelle est relache, on ne bascule jamais sur verify=False.
    """

    def __init__(self, ca_bundle: str, *args, **kwargs):
        self._ca_bundle = ca_bundle
        super().__init__(*args, **kwargs)

    def init_poolmanager(self, connections, maxsize, block=False, **kwargs):
        context = ssl.create_default_context(cafile=self._ca_bundle)
        context.verify_flags &= ~ssl.VERIFY_X509_STRICT
        kwargs["ssl_context"] = context
        self.poolmanager = PoolManager(
            num_pools=connections, maxsize=maxsize, block=block, **kwargs
        )


def _build_combined_bundle() -> Path | None:
    """Fusionne le bundle certifi et la racine d'interception locale, si presente."""
    if not LOCAL_ROOT_CERT.exists():
        return None

    CERTS_DIR.mkdir(exist_ok=True)
    base = Path(certifi.where()).read_text(encoding="utf-8").rstrip()
    local = LOCAL_ROOT_CERT.read_text(encoding="utf-8").strip()
    COMBINED_BUNDLE.write_text(f"{base}\n{local}\n", encoding="utf-8")
    return COMBINED_BUNDLE


def build_session() -> requests.Session:
    """Session HTTPS fonctionnant avec ou sans interception SSL locale.

    Tente d'abord la verification standard ; ne bascule sur le magasin etendu
    que si le poste intercepte reellement le trafic HTTPS.
    """
    session = requests.Session()
    try:
        session.get(NYC311_ENDPOINT, params={"$limit": 1}, timeout=20).raise_for_status()
        return session
    except requests.exceptions.SSLError:
        pass

    bundle = _build_combined_bundle()
    if bundle is None:
        raise RuntimeError(
            "Verification SSL impossible et aucune autorite racine locale trouvee "
            f"({LOCAL_ROOT_CERT.name} absent a la racine du projet)."
        )

    print(f"Interception SSL locale detectee : utilisation du magasin etendu ({bundle.name}).")
    session.mount("https://", _LocalTrustAdapter(str(bundle)))
    return session


def fetch_recent_tickets(limit: int = 5000, session: requests.Session | None = None) -> pd.DataFrame:
    """Recupere un instantane des tickets 311 les plus recents.

    Chaque appel renvoie l'etat courant des tickets recents : relancer ce script
    a des heures differentes retourne des tickets differents, ce qui est la
    demonstration recherchee (donnee "renouvelable" vs dataset fige).
    """
    session = session or build_session()
    params = {"$limit": limit, "$order": "created_date DESC"}
    headers = {"X-App-Token": APP_TOKEN} if APP_TOKEN else {}

    resp = session.get(NYC311_ENDPOINT, params=params, headers=headers, timeout=60)
    resp.raise_for_status()
    return pd.DataFrame(resp.json())


def to_event_log(raw: pd.DataFrame) -> pd.DataFrame:
    """Transforme les tickets 311 (1 ligne = 1 etat courant) en log d'evenements
    (1 ligne = 1 etape du cycle de vie), au format generique attendu par le
    process mining (case_id, activity, timestamp).

    Le dataset 311 n'expose pas l'historique complet des changements de statut,
    mais trois jalons fiables et horodates suffisent a un process mining
    minimal : creation, mise a jour de l'action de resolution, cloture.
    """
    date_cols = ["created_date", "resolution_action_updated_date", "closed_date", "due_date"]
    for col in date_cols:
        if col in raw.columns:
            raw[col] = pd.to_datetime(raw[col], errors="coerce", utc=True)

    keep_attrs = [c for c in [
        "complaint_type", "descriptor", "agency", "agency_name",
        "borough", "incident_zip", "status", "due_date",
    ] if c in raw.columns]

    milestones = [
        ("created_date", "Service Request Created"),
        ("resolution_action_updated_date", "Resolution Action Updated"),
        ("closed_date", "Service Request Closed"),
    ]

    events = []
    for date_col, activity in milestones:
        if date_col not in raw.columns:
            continue
        part = raw[raw[date_col].notna()][["unique_key", date_col] + keep_attrs].copy()
        part[ACTIVITY_COL] = activity
        part = part.rename(columns={"unique_key": CASE_ID_COL, date_col: TIMESTAMP_COL})
        events.append(part)

    log = pd.concat(events, ignore_index=True)
    log = log.dropna(subset=[CASE_ID_COL, ACTIVITY_COL, TIMESTAMP_COL])
    log = log.sort_values([CASE_ID_COL, TIMESTAMP_COL]).reset_index(drop=True)
    return log


def summarize(log: pd.DataFrame) -> None:
    per_case = log.groupby(CASE_ID_COL)[TIMESTAMP_COL].agg(["min", "max"])
    durations_h = (per_case["max"] - per_case["min"]).dt.total_seconds() / 3600
    closed = log[log[ACTIVITY_COL] == "Service Request Closed"][CASE_ID_COL].nunique()

    print(f"Log d'evenements : {len(log)} evenements, {log[CASE_ID_COL].nunique()} cas")
    print(f"Periode couverte : {log[TIMESTAMP_COL].min():%Y-%m-%d %H:%M} -> {log[TIMESTAMP_COL].max():%Y-%m-%d %H:%M}")
    print(f"Cas deja clotures : {closed} ({closed / log[CASE_ID_COL].nunique():.1%})")
    print(f"Duree de traitement : mediane {durations_h.median():.1f} h, moyenne {durations_h.mean():.1f} h")
    print("\nTypes de reclamation les plus frequents :")
    if "complaint_type" in log.columns:
        top = log.drop_duplicates(CASE_ID_COL)["complaint_type"].value_counts().head(5)
        for name, count in top.items():
            print(f"  {count:>5}  {name}")


def main() -> None:
    LIVE_DATA_DIR.mkdir(parents=True, exist_ok=True)

    print("Appel de l'API NYC 311 (data.cityofnewyork.us)...")
    session = build_session()
    raw = fetch_recent_tickets(session=session)
    fetched_at = pd.Timestamp.now(tz="UTC")
    print(f"{len(raw)} tickets recuperes a {fetched_at:%Y-%m-%d %H:%M:%S} UTC")
    if not APP_TOKEN:
        print("Astuce : aucun SOCRATA_APP_TOKEN dans .env - l'API repond, mais avec un quota reduit.")
    print()

    raw.to_parquet(RAW_SNAPSHOT_PATH, index=False)
    log = to_event_log(raw)
    log.to_parquet(EVENT_LOG_PATH, index=False)

    summarize(log)
    print(f"\nSauvegarde : {EVENT_LOG_PATH}")


if __name__ == "__main__":
    main()
