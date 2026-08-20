# -*- coding: utf-8 -*-
"""Point B du comite : regle 'un seul robot BTC en position a la fois'.
Cout/benefice sur L4.31 (mode ON, 10 ans + 2021-2026)."""
import os, pandas as pd, numpy as np
D = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(D, "tests_comite_B.py"), encoding="utf-8").read().split("# ============ 5.")[0]
ns0 = {"__file__": os.path.join(D, "tests_comite_B.py")}
exec(src, ns0)
run, fab_l431 = ns0["run"], ns0["fab_l431"]
ns = ns0["ns"]

def fab_cap_btc(**kw):
    base = fab_l431(**kw)
    def f():
        sl = base()
        btcs = [s for s in sl if s.nom.startswith("BTC")]
        for s in btcs:
            autres = [x for x in btcs if x is not s]
            sig0 = s.signal
            def sig(t, s=s, sig0=sig0, autres=autres):
                if any(x.pos is not None for x in autres): return None   # un seul BTC
                return sig0(t)
            s.signal = sig
        return sl
    return f

for etiquette, per in (("10 ans", ("2015-08-21", "2026-12-31")),
                       ("21-26", ("2021-01-01", "2026-08-20"))):
    ns["DEBUT"], ns["FIN"] = per
    ns["sleeves_l4"] = fab_l431()
    a = ns["sim_h4"](interdit=ns0["f_or"] if "f_or" in ns0 else None)
    ns["DEBUT"], ns["FIN"] = per
    ns["sleeves_l4"] = fab_cap_btc()
    b = ns["sim_h4"](interdit=ns0["f_or"] if "f_or" in ns0 else None)
    print("%-7s SANS cap BTC : %+5.1f%% / reussite %3.0f%%  |  AVEC cap : %+5.1f%% / %3.0f%%  (delta %+.1f pt)"
          % (etiquette, a[0], 100-a[3], b[0], 100-b[3], b[0]-a[0]))
