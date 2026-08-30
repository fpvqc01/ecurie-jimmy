# -*- coding: utf-8 -*-
"""BTC seul H4 8 ans (Binance 2018-2026) : pyramide 3 vs 4 vs 5.
Patch du moteur_h4 : la limite "unites < 3" devient parametrique."""
import pandas as pd, numpy as np, os
for pyr in (3, 4, 5):
    src = open("moteur_h4.py", encoding="utf-8").read()
    src = src.replace('while p["unites"] < 3 and', 'while p["unites"] < %d and' % pyr)
    ns = {"__file__": os.path.abspath("moteur_h4.py")}
    exec(src, ns)
    r = ns["sim"]("L3+", btc_seul=True, debut="2018-01-01")
    print("pyramide %d : CAGR %+6.1f%% | Sharpe %5.2f | MaxDD %+6.1f%% | morts %3.0f%%"
          % (pyr, r["cagr"], r["sharpe"], r["dd"], r["morts"]))
