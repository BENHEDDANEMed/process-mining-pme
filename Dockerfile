# Build multi-etapes : le dashboard React puis l'API FastAPI qui le sert.
#
# NB licence : pm4py est sous AGPL v3 depuis 2024, usage commercial non open-source
# necessite une licence payante. Le dataset utilise est BPI Challenge 2019 (4TU, public).
#
# Les modeles (.pnml, .pkl) sont entraines HORS du conteneur (voir README) et
# montes en volume : ce conteneur ne fait que les charger pour servir l'API.
#
# Si le build echoue avec une erreur SSL (CERTIFICATE_VERIFY_FAILED), c'est
# generalement qu'un antivirus ou un proxy d'entreprise intercepte le trafic
# HTTPS de la machine qui construit l'image (ex. inspection SSL d'Avast).
# Dans ce cas, exporter le certificat racine de cet outil et le deposer dans
# docker/certs/ (n'importe quel nom en .crt) avant de relancer le build : les
# deux etapes ci-dessous l'installent automatiquement s'il est present. Ce
# fichier est propre a chaque machine, ne pas le committer (voir .gitignore).

FROM node:22-slim AS frontend
COPY docker/certs/*.crt /usr/local/share/ca-certificates/
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*
ENV NODE_EXTRA_CA_CERTS=/etc/ssl/certs/ca-certificates.crt

WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim

COPY docker/certs/*.crt /usr/local/share/ca-certificates/
RUN apt-get update \
    && apt-get install -y --no-install-recommends graphviz ca-certificates \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*
ENV PIP_CERT=/etc/ssl/certs/ca-certificates.crt
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY backend/ backend/
# Le dashboard charge la configuration du processus (via src/config.py) pour
# calculer le Process Health Score : config/ doit donc etre dans l'image.
COPY config/ config/
COPY --from=frontend /app/dist/ frontend/dist/

EXPOSE 8000

CMD ["uvicorn", "backend.api:app", "--host", "0.0.0.0", "--port", "8000"]
