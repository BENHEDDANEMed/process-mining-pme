# Interface web — Process Mining PME

Application React (build Vite) qui restitue les analyses de la plateforme. Elle
consomme exclusivement les routes JSON de l'API FastAPI (`backend/api.py`) et ne
recalcule aucune metrique cote client.

## Structure

```
src/
├── App.jsx           # navigation (6 onglets, dont 2 avec sous-onglets)
├── views/            # les 7 vues : Overview, Process, Variants, Conformance,
│                     #   CaseExplorer, Prediction, Monitoring, Recommendations
├── components/       # composants partages (Gauge, StatCard, Table, HBarChart...)
└── lib/              # client API, formatage, couleurs de statut
```

## Developpement

```bash
npm install
npm run dev      # serveur de dev Vite (l'API doit tourner sur le port 8000)
npm run build    # bundle statique dans dist/
```

En production, le bundle `dist/` est servi directement par FastAPI depuis le
meme processus (voir `Dockerfile`) : pas de serveur front separe, donc pas de
configuration CORS.

Le systeme de conception (palette, typographie, regles d'usage des composants)
est documente dans `DESIGN.md` a la racine du depot.
