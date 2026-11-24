# Nova FTMO — système neuf

Décision : **robots MQL5 natifs** (meilleur pour FTMO 24/7), projet **from scratch**.
Pas l’ancienne écurie. Pas d’agent LLM qui clique des trades.

## Stratégie verrouillée (`nova_v3_D`)

- Marchés : **XAUUSD H4** + **US100 H4**
- Long only : close croise au-dessus EMA20, avec EMA20 > EMA100 et prix > EMA100
- Stop = 1.8 / 1.7 ATR · Take-profit = 2.8R / 2.5R
- Risque 1.0 % or · 0.8 % Nasdaq · halt jour interne 2.4 %
- Flatten à l’objectif de phase challenge (10 % puis 5 %)

## Chiffres du banc (données H4 2015→2026)

| Fenêtre | Réussite challenge | Médiane si réussi | Morts | Timeouts |
|---|---|---|---|---|
| 2015–2026 | **68.4 %** | **354 j** | 9.5 % | 22 % |
| 2021–2026 | **67.6 %** | **362 j** | 3.2 % | 29 % |

Ce n’est **pas** encore >85 %. C’est la base Nova à améliorer. Aucune garantie de profit.

```bash
cd nova-ftmo
python3 banc.py
```

## Live (chez toi, Windows / VPS)

1. Compiler `robots/Nova_XAUUSD_H4.mq5` et `robots/Nova_US100_H4.mq5`
2. Compte FTMO **2-Step Swing** (démo → Free Trial → challenge)
3. Chart H4 XAUUSD + US100, Algo Trading ON
4. Phase 1 : `ObjectifPhasePct=10` · Phase 2 : `5` · Financé : `0`
5. Rewards dès J+14 une fois financé → viser scaling
