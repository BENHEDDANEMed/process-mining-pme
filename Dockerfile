# Image unique (Streamlit + PM4Py + XGBoost) - pas de backend separe, cf. decision
# d'architecture du plan de projet.
#
# NB licence : pm4py est sous AGPL v3 depuis 2024, usage commercial non open-source
# necessite une licence payante. Le dataset utilise est BPI Challenge 2019 (4TU, public).
#
# Les modeles (.pnml, .pkl) sont entraines HORS du conteneur (voir README) et
# montes en volume : ce conteneur ne fait que les charger pour servir le dashboard.
FROM python:3.13-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends graphviz ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Si `pip install` echoue plus bas avec une erreur SSL (CERTIFICATE_VERIFY_FAILED),
# c'est generalement qu'un antivirus ou un proxy d'entreprise intercepte le trafic
# HTTPS sur la machine qui construit l'image. Dans ce cas, ajouter ici :
#   COPY votre-certificat-racine.crt /usr/local/share/ca-certificates/
#   RUN update-ca-certificates
# Ce fichier est propre a chaque machine : ne pas le committer dans le depot.

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
# Le dashboard charge la configuration du processus (via src/config.py) pour
# calculer le Process Health Score : config/ doit donc etre dans l'image.
COPY config/ config/
COPY app.py .

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]
