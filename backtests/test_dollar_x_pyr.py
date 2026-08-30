# -*- coding: utf-8 -*-
"""H4 10 ans : filtre dollar x pyramide 3/4 (les 4 combinaisons)."""
import pandas as pd, numpy as np
src = open("test_l4_macro.py", encoding="utf-8").read().split("def int_or")[0]
src = src.replace("s.pyr_max = 3", "s.pyr_max = PYRMAX")
for nom, pyr, filtre in (("L4 pyr3 sans filtre", 3, False), ("L4 pyr3 + filtre dollar", 3, True),
                          ("L4 pyr4 sans filtre", 4, False), ("L4 pyr4 + filtre dollar", 4, True)):
    ns = {"__file__": "test_l4_macro.py", "PYRMAX": pyr}
    exec(src, ns)
    interdit = (lambda n, j, DF=ns["DOLLAR_FORT"]: n == "Or" and j in DF) if filtre else None
    c, s, d, m, a1, a2 = ns["sim_h4"](interdit=interdit)
    print("%-26s : CAGR %+6.1f%% | Sharpe %5.2f | MaxDD %+6.1f%% | morts %3.0f%% | moities %+5.1f/%+5.1f%%"
          % (nom, c, s, d, m, a1, a2), flush=True)
