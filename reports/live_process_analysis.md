# Analyse du flux vivant - NYC 311 (API publique)

Ce rapport est genere a partir d'un appel API effectue au moment de l'execution.
Contrairement au dataset BPI Challenge 2019 (fige), **relancer le pipeline produit
des chiffres differents**, puisque de nouveaux tickets arrivent en continu.

Les indicateurs ci-dessous sont calcules par les memes fonctions que l'analyse
principale (`src/process_metrics.py`) : seule la configuration change.

## Instantane analyse
- Evenements : 45,799
- Cas (tickets) : 20,000
- Periode couverte : 2023-09-13 11:47 -> 2026-09-02 12:00
- Taux de cloture a l'instant T : 51.6% (10,311 tickets clotures)

## Delais de traitement
- Duree mediane : 1.9 h
- Duree moyenne : 12.9 h
- 90e percentile : 18.1 h

## Modele de processus decouvert
- Places : 8 | Transitions : 7 | Arcs : 18
- Nombre de variantes observees : 7

### Variantes les plus frequentes
- (8698 cas) Service Request Created -> Service Request Closed -> Resolution Action Updated
- (4512 cas) Service Request Created
- (4138 cas) Resolution Action Updated -> Service Request Created
- (1039 cas) Service Request Created -> Resolution Action Updated
- (936 cas) Service Request Created -> Resolution Action Updated -> Service Request Closed

## Goulots d'etranglement (attente moyenne entre etapes)
- Resolution Action Updated -> Service Request Created : 41.3 h (4805 occurrences)
- Service Request Created -> Resolution Action Updated : 10.6 h (1985 occurrences)
- Service Request Created -> Service Request Closed : 3.3 h (9365 occurrences)
- Resolution Action Updated -> Service Request Closed : 2.3 h (936 occurrences)
- Service Request Closed -> Resolution Action Updated : 0.7 h (8698 occurrences)

## Types de reclamation les plus lents (>= 20 cas)
- HEAT/HOT WATER : mediane 16.0 h (251 cas)
- Derelict Vehicles : mediane 15.9 h (115 cas)
- Building/Use : mediane 14.4 h (150 cas)
- Dead Animal : mediane 14.3 h (53 cas)
- WATER LEAK : mediane 14.3 h (383 cas)
- PLUMBING : mediane 13.9 h (513 cas)
- SAFETY : mediane 13.9 h (87 cas)
- UNSANITARY CONDITION : mediane 13.7 h (1134 cas)

## Interet pour une PME

Le processus modelise ici (ouverture -> traitement -> cloture d'une reclamation)
est structurellement identique a un service client ou un support technique de PME.
Les memes indicateurs - delai de traitement, taux de cloture, etapes ou le dossier
stagne - se transposent directement, la seule difference etant la source des
donnees : ici une API publique, en entreprise le systeme de ticketing interne.
