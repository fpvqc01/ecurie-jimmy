# Guide pour le développeur — Écurie de robots FTMO de Jimmy

Bienvenue. Ce dépôt contient tout le projet : ~40 générations de robots de
trading MQL5, le moteur de backtest Python, les données figées et les
rapports d'audit. Voici la carte pour t'y retrouver.

## Le projet en trois phrases

Une « écurie » = 5 robots MQL5 qui tournent ensemble sur un compte MetaTrader 5
(Or H4, Nasdaq H4, Pétrole H4, BTC cassure H1, BTC croisement d'EMA D1), tous
en suivi de tendance, achat seulement, avec des coupe-circuits FTMO partagés
via les variables globales du terminal. L'objectif : passer les challenges
FTMO (+10 % puis +5 %, jamais −5 %/jour ni −10 % au total). Chaque
« génération » (L6, L8, L11, L12, S3...) est une itération complète de ces
5 robots, testée au banc avant d'exister.

## Où est quoi

- `robots/Jimmy <GEN>/` — les 5 sources .mq5 de chaque génération.
  Les .ex5 ne sont pas versionnés : compiler avec `metaeditor64 /portable`.
- `backtests/` — le moteur Python (`moteur_h4.py` + chaîne de scripts qui se
  chargent par `exec`), le simulateur FTMO exact, les données figées (CSV) et
  ~80 scripts de banc d'essai. Python 3.12, pandas/numpy seulement.
- `pipeline_python/` — les exports quotidiens (volatilité, biais macro,
  nouvelles) que les robots lisent dans `MQL5\Files`.
- `RAPPORT_*.md` — les audits (comités d'experts, bancs, crises).

## Les générations qui comptent (le reste est historique)

| Génération | Rôle | Réussite challenge (10 ans / 2021-26) |
|---|---|---|
| **L12** | la plus rapide fiable (repli conditionnel + turbo 1,15) | 95 % / 99 %, ~184 j espérés |
| **L11** | la plus sûre (déconcentration BTC, gardien 2,5 %) | 99 % / 97 % |
| **L8** | la base des 12 correctifs de bogues | 89 % / 84 % |
| S3.x | branche vente à découvert (autre conversation) | en essai sur démo |

Chiffres mesurés sur données réparées, simulateur corrigé (objectif jugé sur
solde FERMÉ, règle FTMO), départs glissants ~1 200.

## Les trois leçons chèrement payées (à lire avant de toucher)

1. **Données** : un bogue de colonnes a corrompu 81 % des barres H1 du BTC
   pendant des jours (`list("tochlv")` au lieu de `list("tohlcv")`). Tout est
   réparé et `backtests/AUDIT_donnees.py` doit tourner avant toute campagne.
2. **Simulateur** : FTMO valide l'objectif sur le solde positions FERMÉES,
   pas l'équité flottante (`backtests/sim_ferme.py`). D'où « R13 » : les
   robots ferment tout à +10 % (phase 1) / +5 % (phase 2), réglé par l'enum
   `PhaseActuelle`.
3. **Méthode** : toute idée passe au banc AVANT d'entrer dans un robot, sur
   DEUX fenêtres (10 ans et 2021-2026), et on exige un plateau (les réglages
   voisins gagnent aussi), jamais un pic isolé.

## Pièges concrets MQL5

- MetaEditor en ligne de commande exige `/portable` sur les installations
  portables, sinon il supprime les .ex5.
- Le terminal ne recharge PAS un .ex5 recompilé : redémarrer le terminal.
- Les modèles de graphique (.tpl) et les .chr stockent des inputs qui
  ÉCRASENT les valeurs par défaut du source.
- Plusieurs générations partagent les mêmes numéros magiques : JAMAIS deux
  générations sur le même compte.
- Les journaux du terminal sont en UTF-16.

## Ce qui tourne en ce moment (30 août 2026, tout en démo FTMO)

MT6 (C:\MT6) → L6 · MT5 original → L6+ · « MT7 » (C:\NouveauMT5) → S3.2 X1.
Les décisions barre par barre s'écrivent dans `MQL5\Files\Ecurie_Journal\`.
