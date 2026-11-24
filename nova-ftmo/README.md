# Nova FTMO — système neuf

Robots **MQL5** from scratch (pas l’ancienne écurie). Pas d’agent LLM qui trade.

## Deux modes

| Mode | EA | Pass labo | Médiane | Rôle |
|---|---|---|---|---|
| Survie H4 `nova_v3_D` | `Nova_XAUUSD_H4` + `Nova_US100_H4` | ~68 % | ~350 j | Base |
| **Sprint ORB M5** `orb_fast` | `Nova_ORB_XAUUSD_M5` | **~12 %** | **~15 j** | Tentative ≤30 j |

Sprint = plus rapide, **beaucoup plus de fails**. Détails : `RESULTATS_30J.md`.

## Bancs

```bash
cd nova-ftmo
python3 -m pip install pandas numpy yfinance
python3 fetch_data.py
python3 banc.py        # H4
python3 banc_orb.py    # ORB sprint
python3 banc_scalp.py  # EMA scalp (échec après frais)
```

## Live

1. Compiler les `.mq5` dans MetaEditor  
2. FTMO **2-Step Swing** — **Free Trial d’abord**  
3. Sprint : chart **XAUUSD M5** + `Nova_ORB_XAUUSD_M5` (heures Londres/NY)  
4. Algo Trading ON  

Aucune garantie de profit.
