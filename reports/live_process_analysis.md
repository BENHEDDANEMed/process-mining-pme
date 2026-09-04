# Analyse du flux vivant - NYC 311 (API publique)

Ce rapport est genere a partir d'un appel API effectue au moment de l'execution.
Contrairement au dataset BPI Challenge 2019 (fige), **relancer le pipeline produit
des chiffres differents**, puisque de nouveaux tickets arrivent en continu.

Les indicateurs ci-dessous sont calcules par les memes fonctions que l'analyse
principale (`src/process_metrics.py`) : seule la configuration change.

## Instantane analyse
- Evenements : 40,761
- Cas (tickets) : 20,000
- Periode couverte : 2026-08-31 07:06 -> 2026-09-02 12:00
- Taux de cloture a l'instant T : 51.6% (10,311 tickets clotures)

## Delais de traitement
- Duree mediane : 0.1 h
- Duree moyenne : 3.0 h
- 90e percentile : 10.1 h

## Modele de processus decouvert
- Places : 7 | Transitions : 7 | Arcs : 16
- Nombre de variantes observees : 6

### Variantes les plus frequentes
- (8826 cas) Service Request Created
- (8698 cas) Service Request Created -> Service Request Closed -> Resolution Action Updated
- (879 cas) Service Request Created -> Resolution Action Updated -> Service Request Closed
- (863 cas) Service Request Created -> Resolution Action Updated
- (724 cas) Service Request Created -> Service Request Closed

## Goulots d'etranglement (attente moyenne entre etapes)
- Service Request Created -> Resolution Action Updated : 12.1 h (1752 occurrences)
- Service Request Created -> Service Request Closed : 3.2 h (9422 occurrences)
- Resolution Action Updated -> Service Request Closed : 2.5 h (879 occurrences)
- Service Request Closed -> Resolution Action Updated : 0.7 h (8698 occurrences)

## Types de reclamation les plus lents (>= 20 cas)
- Derelict Vehicles : mediane 15.9 h (115 cas)
- Dead Animal : mediane 14.3 h (53 cas)
- Water Maintenance : mediane 7.2 h (400 cas)
- Litter Basket Complaint : mediane 7.2 h (20 cas)
- Homeless Person Assistance : mediane 3.9 h (283 cas)
- Dumpster Complaint : mediane 3.8 h (25 cas)
- Abandoned Vehicle : mediane 1.8 h (550 cas)
- Street Sign - Dangling : mediane 1.8 h (23 cas)

## Interet pour une PME

Le processus modelise ici (ouverture -> traitement -> cloture d'une reclamation)
est structurellement identique a un service client ou un support technique de PME.
Les memes indicateurs - delai de traitement, taux de cloture, etapes ou le dossier
stagne - se transposent directement, la seule difference etant la source des
donnees : ici une API publique, en entreprise le systeme de ticketing interne.
