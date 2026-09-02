# Analyse du flux vivant - NYC 311 (API publique)

Ce rapport est genere a partir d'un appel API effectue au moment de l'execution.
Contrairement au dataset BPI Challenge 2019 (fige), **relancer le pipeline produit
des chiffres differents**, puisque de nouveaux tickets arrivent en continu.

Les indicateurs ci-dessous sont calcules par les memes fonctions que l'analyse
principale (`src/process_metrics.py`) : seule la configuration change.

## Instantane analyse
- Evenements : 11,001
- Cas (tickets) : 5,000
- Periode couverte : 2026-05-22 13:59 -> 2026-08-31 12:00
- Taux de cloture a l'instant T : 54.5% (2,723 tickets clotures)

## Delais de traitement
- Duree mediane : 0.4 h
- Duree moyenne : 3.3 h
- 90e percentile : 15.1 h

## Modele de processus decouvert
- Places : 8 | Transitions : 7 | Arcs : 18
- Nombre de variantes observees : 7

### Variantes les plus frequentes
- (2614 cas) Service Request Created -> Service Request Closed -> Resolution Action Updated
- (1722 cas) Service Request Created
- (475 cas) Resolution Action Updated -> Service Request Created
- (80 cas) Service Request Created -> Resolution Action Updated
- (72 cas) Resolution Action Updated -> Service Request Created -> Service Request Closed

## Goulots d'etranglement (attente moyenne entre etapes)
- Resolution Action Updated -> Service Request Created : 22.6 h (547 occurrences)
- Service Request Created -> Service Request Closed : 1.4 h (2686 occurrences)
- Service Request Created -> Resolution Action Updated : 1.1 h (117 occurrences)
- Service Request Closed -> Resolution Action Updated : 0.1 h (2614 occurrences)
- Resolution Action Updated -> Service Request Closed : 0.0 h (36 occurrences)

## Types de reclamation les plus lents (>= 20 cas)
- HEAT/HOT WATER : mediane 19.4 h (25 cas)
- ELECTRIC : mediane 19.1 h (34 cas)
- GENERAL : mediane 19.0 h (28 cas)
- PLUMBING : mediane 18.8 h (58 cas)
- UNSANITARY CONDITION : mediane 18.1 h (141 cas)
- DOOR/WINDOW : mediane 17.4 h (47 cas)
- WATER LEAK : mediane 17.2 h (45 cas)
- FLOORING/STAIRS : mediane 17.2 h (21 cas)

## Interet pour une PME

Le processus modelise ici (ouverture -> traitement -> cloture d'une reclamation)
est structurellement identique a un service client ou un support technique de PME.
Les memes indicateurs - delai de traitement, taux de cloture, etapes ou le dossier
stagne - se transposent directement, la seule difference etant la source des
donnees : ici une API publique, en entreprise le systeme de ticketing interne.
