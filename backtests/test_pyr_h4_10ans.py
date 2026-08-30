# -*- coding: utf-8 -*-
"""Pyramide 3/4/5 sur le moteur H4 10 ANS (config L4 ON) - juge de paix."""
import pandas as pd, numpy as np
src = open("test_l4_macro.py", encoding="utf-8").read().split("def int_or")[0]
src = src.replace("s.pyr_max = 3", "s.pyr_max = PYRMAX")
for pyr in (3, 4, 5):
    ns = {"__file__": "test_l4_macro.py", "PYRMAX": pyr}
    exec(src, ns)
    c, s, d, m, a1, a2 = ns["sim_h4"]()
    print("pyramide %d : CAGR %+6.1f%% | Sharpe %5.2f | MaxDD %+6.1f%% | morts %3.0f%% | moities %+5.1f/%+5.1f%%"
          % (pyr, c, s, d, m, a1, a2), flush=True)
