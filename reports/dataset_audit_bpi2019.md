# Audit dataset : bpi2019

Fichier source : `data\raw\bpi_challenge_2019.xes`

## Volume
- Nombre d'evenements : 1595923
- Nombre de cas : 251734
- Nombre d'activites distinctes : 42
- Nombre de ressources/utilisateurs : 628

## Attributs disponibles
- User, org:resource, concept:name, Cumulative net worth (EUR), time:timestamp, case:Spend area text, case:Company, case:Document Type, case:Sub spend area text, case:Purchasing Document, case:Purch. Doc. Category name, case:Vendor, case:Item Type, case:Item Category, case:Spend classification text, case:Source, case:Name, case:GR-Based Inv. Verif., case:Item, case:concept:name, case:Goods Receipt

## Qualite des donnees
- Valeurs manquantes par colonne : aucune
- Doublons (lignes identiques) : 132748
- Timestamps valides : 1595923
- Periode couverte : 1948-01-26 22:59:00+00:00 -> 2020-04-09 21:59:00+00:00

## Duree des cas
- Duree moyenne (h) : 1716.6
- Duree mediane (h) : 1537.1

## Variantes
- Nombre de variantes uniques : 14099
- Top 5 variantes les plus frequentes :
  - (50283 cas) Create Purchase Order Item -> Vendor creates invoice -> Record Goods Receipt -> Record Invoice Receipt -> Clear Invoice
  - (30793 cas) Create Purchase Order Item -> Record Goods Receipt -> Vendor creates invoice -> Record Invoice Receipt -> Clear Invoice
  - (12160 cas) Create Purchase Order Item -> Record Goods Receipt
  - (11381 cas) Create Purchase Order Item -> Vendor creates invoice -> Record Goods Receipt -> Record Invoice Receipt -> Remove Payment Block -> Clear Invoice
  - (8921 cas) Create Purchase Requisition Item -> Create Purchase Order Item -> Vendor creates invoice -> Record Goods Receipt -> Record Invoice Receipt -> Clear Invoice

## Aptitude Process Mining (a completer manuellement apres lecture)
- Process Discovery : possible si activites + case id + timestamp presents (voir ci-dessus).
- Conformance Checking : necessite un modele decouvrable (variantes non triviales).
- Analyse de performance : necessite des timestamps fiables (voir periode couverte).
- Cibles Machine Learning envisageables : a definir a partir des attributs listes ci-dessus.
