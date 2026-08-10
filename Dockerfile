# Image unique (Streamlit + PM4Py + XGBoost) - pas de backend separe, cf. decision
# d'architecture du plan de projet.
#
# NB licence : pm4py est sous AGPL v3 depuis 2024, usage commercial non open-source
# necessite une licence payante. Le dataset BPI Challenge 2012 est public (4TU).
#
# Les modeles (.pnml, .pkl) sont entraines HORS du conteneur (voir README) et
# montes en volume : ce conteneur ne fait que les charger pour servir le dashboard.
FROM python:3.13-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends graphviz ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Poste de dev local derriere un antivirus (Avast) qui intercepte le trafic HTTPS
# pour le scanner ; son certificat racine n'est pas connu du conteneur par defaut,
# ce qui fait echouer `pip install` (SSL: CERTIFICATE_VERIFY_FAILED). On l'ajoute
# au magasin de certificats du conteneur. Sans antivirus scannant le HTTPS
# (build en CI, autre machine), ce fichier est simplement ignore.
COPY avast-root.crt /usr/local/share/ca-certificates/avast-root.crt
RUN update-ca-certificates

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY app.py .

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]
