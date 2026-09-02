# Audit dataset : bpi2012

Fichier source : `data\bpi_challenge_2012.xes`

## Volume
- Nombre d'evenements : 262200
- Nombre de cas : 13087
- Nombre d'activites distinctes : 24
- Nombre de ressources/utilisateurs : 68

## Attributs disponibles
- org:resource, lifecycle:transition, concept:name, time:timestamp, case:REG_DATE, case:concept:name, case:AMOUNT_REQ

## Qualite des donnees
- Valeurs manquantes par colonne : {'org:resource': 18010}
- Doublons (lignes identiques) : 0
- Timestamps valides : 262200
- Periode couverte : 2011-10-01 00:38:44.546000+00:00 -> 2012-03-14 16:04:54.681000+00:00

## Duree des cas
- Duree moyenne (h) : 206.9
- Duree mediane (h) : 19.4

## Variantes
- Nombre de variantes uniques : 4379
- Top 5 variantes les plus frequentes :
  - (3429 cas) A_SUBMITTED -> A_PARTLYSUBMITTED -> A_DECLINED
  - (1872 cas) A_SUBMITTED -> A_PARTLYSUBMITTED -> W_Afhandelen leads -> W_Afhandelen leads -> A_DECLINED -> W_Afhandelen leads
  - (271 cas) A_SUBMITTED -> A_PARTLYSUBMITTED -> W_Afhandelen leads -> W_Afhandelen leads -> W_Afhandelen leads -> W_Afhandelen leads -> A_DECLINED -> W_Afhandelen leads
  - (209 cas) A_SUBMITTED -> A_PARTLYSUBMITTED -> W_Afhandelen leads -> W_Afhandelen leads -> A_PREACCEPTED -> W_Completeren aanvraag -> W_Afhandelen leads -> W_Completeren aanvraag -> A_DECLINED -> W_Completeren aanvraag
  - (160 cas) A_SUBMITTED -> A_PARTLYSUBMITTED -> A_PREACCEPTED -> W_Completeren aanvraag -> W_Completeren aanvraag -> A_DECLINED -> W_Completeren aanvraag

## Aptitude Process Mining (a completer manuellement apres lecture)
- Process Discovery : possible si activites + case id + timestamp presents (voir ci-dessus).
- Conformance Checking : necessite un modele decouvrable (variantes non triviales).
- Analyse de performance : necessite des timestamps fiables (voir periode couverte).
- Cibles Machine Learning envisageables : a definir a partir des attributs listes ci-dessus.
