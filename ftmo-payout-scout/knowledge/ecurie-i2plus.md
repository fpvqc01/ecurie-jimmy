# Écurie Jimmy I2+ / L5 — base utile pour l’agent

Objectif : passer des challenges FTMO, obtenir des comptes financés Swing, maximiser le cash
légitime (Rewards + scaling), sans casser les règles (perte jour / totale).

## Système en service

5 robots, compte FTMO-Demo style 100k hedging, MT5 :

| Robot | Marché | Idée | Risque/trade (réf.) |
| --- | --- | --- | --- |
| BTCUSD EMA H1 | BTC | EMA 20/50 long, TP 2R + ré-entrée | 0,75 % |
| BTCUSD Cassure H4 | BTC | Donchian 55/20, stop suiveur, pas de TP | 0,75 % |
| XAUUSD Or H4 | Or | Fib swing + RSI, TP 1,5R + ré-entrée | 3,0 % |
| US100 Nasdaq H4 | Nasdaq | Fib + RSI, TP 1R + ré-entrée | 1,5 % |
| USOIL Pétrole D1 | Pétrole | Donchian 20/10, actif déc→mai | 0,75 % |

Couches transversales : plafond écurie max 2 positions ; coupe-circuits partagés
(jour ~−3,5 %, total ~−8 %) sous les limites FTMO 5 % / 10 % ; vol targeting ;
filtres news / biais macro.

Perf simulée historique (ordre de grandeur) : ~+21 %/an, Sharpe ~1,4, pire jour ~−4 %,
pire creux ~−6 %. Challenge +10 % : médiane ~3–5 mois selon config.

## Plan cash (comité L5 — chiffres backtest, pas une garantie)

1. Challenge : risque ×1,0 (réf. ~90 % réussite) — accélérer avec ×1,33 seulement si
   gardien jour fixe ~−2,5 %. Monter le risque + élargir le gardien tue le compte.
2. Financé : ×1,33 gardien fixe — meilleur revenu net espéré vs durée de vie.
3. Produit : **FTMO 2-Step Swing** (nuit/week-end/news OK une fois financé). Éviter 1-Step
   pour cette écurie (pas de Swing financé).
4. Taille : préférer 200k (frais remboursés au 1er payout) ; 2×200k en parallèle permis
   sous plafond ~400k — double le capital, pas une assurance (mêmes trades).
5. Scaling : +10 % net / 4 mois + **2 Rewards traités** → +25 % capital et split 90 %
   (2-Step). Demander les payouts dès J+14, ne pas laisser dormir le profit.
6. Allocation optionnelle « a×0,75 » : Or/Nas 0,75 %, pétrole/BTC cassure 1,69 %,
   BTC EMA 1,13 % — léger gain CAGR / réussite, risque total plus bas.

## Candidat validé non encore forcément déployé

Pyramidage Turtle (2–3 unités, +0,5 ATR) sur robots de **cassure seulement**
(BTC Cassure, Pétrole) : CAGR / Sharpe up, morts challenge stables ~15 %.
Pas sur les robots à TP.

## Méthode (ne pas violer)

1. Frais d’abord (swap BTC −30 %/an, pétrole swap +).
2. Tempérament marché = stratégie (repli vs cassure).
3. Plateau de voisins + 2 moitiés de période, pas un pic d’opti.
4. Nouvelle idée = métier absent, pas un doublon.
5. Diversification > champion unique.
6. Frontière risque = mur FTMO.
7. Après beaucoup de backtests : walk-forward vivant (démo → Free Trial → challenge).
