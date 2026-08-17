# Écurie Jimmy I2+ — Système de trading algorithmique pour challenges FTMO

Paquet de partage pour revue de code / optimisation. Généré le 17 août 2026.
Environnement : MetaTrader 5 (MQL5) sur compte FTMO-Demo 100k, hedging.

## Vue d'ensemble

5 robots (Expert Advisors) sur 4 marchés, coordonnés par des protections partagées.
Performance simulée (5 ans, frais réels du compte relevés dans MT5) :
**~+21 %/an, Sharpe 1,39, pire journée -4,0 %, pire creux vs départ -6,1 %**
— toujours à l'intérieur des règles FTMO (perte journalière max 5 %, totale max 10 %).

| Robot | Marché/TF | Stratégie | Risque/trade |
|---|---|---|---|
| BTCUSD_EMA_I2+_H1 | BTCUSD H1 | Croisement EMA 20/50, achat seul, TP 2R + ré-entrée sur repli 0,25×ATR | 0,75 % |
| BTCUSD_Cassure_I2+_H4 | BTCUSD H4 | Cassure Donchian 55/20, achat seul, stop suiveur (jamais de TP) | 0,75 % |
| XAUUSD_Or_I2+_H4 | XAUUSD H4 | Repli fibonacci (20-80 % du swing 60 barres) + RSI<55 qui remonte, TP 1,5R + ré-entrée 0,25×ATR, breakeven à +1R | 3,0 % |
| US100_Nasdaq_I2+_H4 | US100 H4 | Même famille, fib 10-90 % du swing 40 barres, RSI<60, TP 1R + ré-entrée 0,5×ATR | 1,5 % |
| USOIL_Petrole_I2+_D1 | USOIL (données D1, TF du graphique indifférent) | Cassure Donchian 20/10 journalière, ACTIVE SEULEMENT déc→mai (saisonnalité raffineries pré-driving-season) | 0,75 % |

## Mécanismes transversaux (dans chaque EA)

1. **Coupe-circuits partagés** via GlobalVariables MT5 (`MACROBOT_BASE/HALT/DAY_<login>`) :
   -3,5 % de perte journalière (équité du compte) → chaque robot ferme ses positions, pause
   jusqu'au lendemain ; -8 % vs solde initial → fermeture générale + arrêt définitif (drapeau partagé).
2. **Plafond d'écurie** : max 2 positions simultanées tous robots confondus
   (`ComptePositionsEcurie()` compte les magics 20260815/17/18). Validé en backtest :
   améliore le Sharpe de 0,73→1,39 en filtrant les signaux excédentaires.
3. **Ré-entrée après take-profit** (robots EMA/or/Nasdaq) : détection `DEAL_REASON_TP` dans
   OnTradeTransaction → arme une ré-entrée si le prix retrace de N×ATR sous le prix de sortie,
   tant que le régime tient (EMA haussières / plancher du swing intact). Un stop touché annule.
4. **Filtre macro** (BTC seulement) : lit `MQL5\Files\macrobot_bias.txt` (écrit par le pipeline
   Python depuis les données BIS — posture Fed). Or/Nasdaq : même mécanisme via l'input BiasFromFile.
5. **Filtre d'annonces** : `macrobot_news.txt` (calendrier ForexFactory, annonces USD à fort
   impact, epochs UTC) → aucune nouvelle entrée ±30 min, et serrage des stops des positions
   ouvertes (breakeven si profit, sinon 0,5×ATR) pendant la fenêtre.
6. **Volatility targeting** (Moreira & Muir 2017) : `macrobot_vol.txt` (facteur 0,5-1,5 calculé
   chaque matin = 1 / vol relative moyenne des 4 marchés) multiplie le risque par trade.
7. **Notifications push** (SendNotification) sur chaque entrée/sortie/coupe-circuit.

## Pipeline Python (dossier pipeline_python/)

- `export_bias.py` : biais macro BIS (taux directeurs + CPI US) → GOLD/NAS/BTC=0|1.
  Règles dans `assets.py` (or: taux réels US qui ne montent pas ; nasdaq/btc: Fed pas en serrage).
- `export_news.py` : calendrier ForexFactory (XML, heures GMT!) + Fear&Greed crypto.
- `export_vol.py` : facteur de volatilité quotidien.
- Orchestré par `bot.cmd ftmo-bias`, tâches planifiées Windows (7h30 quotidien + horaire).

## Frais réels du compte (relevés dans les spécifications MT5, essentiels aux backtests)

| Marché | Swap long | Commission | Spread approx. |
|---|---|---|---|
| BTCUSD | **-30 %/an** (7j/7) | 0,0325 %/côté | ~0,015 % |
| XAUUSD | ~-7,8 %/an (triple mercredi) | ~0 | ~0,01 % |
| US100 | ~-7,8 %/an (triple vendredi) | 0 | ~0,006 % |
| USOIL | **+1,8 %/an (crédit!)** | 0 | ~0,09 % |

Le swap BTC est le frais dominant — toute stratégie qui tient longtemps ses positions BTC le paie cher.

## ⚠️ IMPORTANT pour l'optimisation : le cimetière des idées déjà testées

~60 backtests réalisés (Python, données Yahoo 5-10 ans, frais réels, validation par moitiés
de période et paramètres voisins). **Idées testées et REJETÉES — ne pas refaire :**

- Scalping M1/M5 (toutes variantes) : frais 12× l'avantage brut
- Support/résistance H4 avec entrée M5 : stops serrés = frais énormes en R
- Trading des nouvelles EIA pétrole (momentum et fade) : surprise absorbée avant réaction
- Inflation comme signal pétrole : le pétrole cause le CPI, pas l'inverse
- Saisonnalité pétrole SEULE (sans cassure) : krach 2020 en pleine "saison favorable"
- Argent/XAG (9 stratégies) : rien de robuste ; corrélé or avec 2× les frais
- US30 et US500 (7 stratégies chacun) : toujours inférieurs au Nasdaq
- IBS+RSI21 mean-reversion Nasdaq : PF 3,40→1,22 entre les moitiés de décennie (avantage mourant)
- Fib profond 0,618/0,886 : meilleurs trades mais 2× moins de gains (1 trade/an)
- EMA200 comme filtre global : ampute les totaux partout
- fib+RSI sur les cassures : zéro trade (conditions incompatibles)
- TP fixe + ré-entrée SUR LES CASSURES (testé 1R→6R) : ampute la queue grasse, le stop
  suiveur domine mathématiquement
- Runners 75/25 : redondants avec la ré-entrée (même métier, moins bien payé)
- 8 stratégies cumulées : corrélation intra-marché, vole les sièges du plafond
- Risque global ×2+ : brise les limites FTMO (validé par simulation)
- Plafond de 1 position : trop restrictif ; sans plafond : Sharpe s'effondre

**Standards de validation utilisés** (à conserver pour toute proposition) :
1. principe économique externe (pas d'idée née de l'optimisation elle-même),
2. amélioration nette avec les frais réels,
3. stabilité sur les DEUX moitiés de période ET sur les paramètres voisins,
4. amélioration au niveau du PORTEFEUILLE sous le plafond de 2 (pas juste en solo).

## Territoire encore inexploré

Paires forex majeures (EUR/USD etc.) avec le pipeline macro par devise (scores carry/momentum
des taux/inflation déjà codés dans macro.py) — jamais backtesté dans cet environnement.

Bonne revue! — Jimmy (et Claude, son partenaire de laboratoire)
