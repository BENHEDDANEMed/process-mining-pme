# Analyse metier du processus (Business Analysis)

Processus analyse : **Purchase-to-Pay (BPI Challenge 2019)**

## KPI
- Nombre de cas : 248,899
- Nombre d'evenements : 1,460,254
- Duree moyenne d'un cas : 1690.0 h (70.4 j)
- Duree mediane d'un cas : 1543.2 h (64.3 j)
- Nombre de variantes : 11,316
- Part de la variante la plus frequente : 20.2%
- Taux de deviation (non conformite) : 13.8%
- Fitness moyen : 0.9810
- Taux de rework moyen : 0.4%

## Goulots d'etranglement (top 5)
- Change Approval for Purchase Order -> Block Purchase Order Item : 3920.9 h d'attente moyenne (107 cas)
- Clear Invoice -> SRM: In Transfer to Execution Syst. : 3815.6 h d'attente moyenne (79 cas)
- Cancel Goods Receipt -> Cancel Invoice Receipt : 3109.1 h d'attente moyenne (300 cas)
- Clear Invoice -> Cancel Invoice Receipt : 2026.8 h d'attente moyenne (2111 cas)
- Vendor creates invoice -> Create Purchase Requisition Item : 1586.1 h d'attente moyenne (61 cas)

## Activites avec le plus de rework (top 5)
- Record Goods Receipt : 4.8% des cas
- Record Invoice Receipt : 3.9% des cas
- Clear Invoice : 2.6% des cas
- Vendor creates invoice : 2.1% des cas
- Record Service Entry Sheet : 1.4% des cas

## Ressources les plus sollicitees (top 5)
- NONE : 278,158 evenements traites
- user_002 : 165,817 evenements traites
- user_029 : 71,125 evenements traites
- user_020 : 39,770 evenements traites
- user_013 : 35,068 evenements traites

## Recommandations
- Le passage 'Change Approval for Purchase Order' -> 'Block Purchase Order Item' est le principal goulot d'etranglement (attente moyenne 3920.9 h sur 107 occurrences) : cibler cette transition en priorite pour reduire les delais globaux.
