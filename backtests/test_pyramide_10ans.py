# -*- coding: utf-8 -*-
"""Pyramide 3/4/5 sur 10 ANS (1d) config L4 ON."""
import pandas as pd, numpy as np
src = open("test_l4_10ans.py", encoding="utf-8").read().split("CONFIGS = [")[0]
src = src.replace("s.pyr_max = 3", "s.pyr_max = PYRMAX")
ns = {"__file__": "test_l4_10ans.py"}
for pyr in (3, 4, 5):
    ns["PYRMAX"] = pyr
    exec(src, ns)
    r = ns["sim10"]("L4", "auto")
    pire = min(r["par_an"].values())
    print("pyramide %d : CAGR %+6.1f%% | morts %3.0f%% | maxDD %+6.1f%% | moities %+5.1f/%+5.1f%% | pire annee %+5.1f%%"
          % (pyr, r["cagr"], r["morts"], r["dd"], r["m1"], r["m2"], pire))
