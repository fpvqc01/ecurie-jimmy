# -*- coding: utf-8 -*-
"""Les 2 barres a prix negatif du petrole (20-21 avril 2020) sont de la VRAIE
histoire, pas un bogue : le WTI a cote -37,63 $. Mais un prix negatif dans le
canal 10 jours et dans l'ATR peut deregler la manche pendant des semaines.
On mesure : L8 tel quel vs L8 avec ces 2 barres bornees a un plancher positif."""
import os, sys, shutil, io
D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, D)
import pandas as pd

F = os.path.join(D, "d10_cl.csv")
SAUV = F + ".sauv_test"

def mesurer(etiquette):
    for m in list(sys.modules):
        if m in ("banc_L8", "sim_ferme", "duel_L6_L8"): del sys.modules[m]
    import banc_L8 as B
    ns0 = B.charger(0.0175)
    ns, f_or, fab = ns0["ns"], ns0["f_or"], ns0["fab_l431"]
    def f():
        sl = fab()()
        for s in sl:
            if s.nom in B.ALLOC: s.risque = B.ALLOC[s.nom]
        for s in sl:
            if s.nom in B.PYR: B.breakeven(s, 0.05)
        return sl
    ns["DEBUT"], ns["FIN"] = "2015-08-21", "2026-12-31"
    ns["sleeves_l4"] = f
    r = ns["sim_h4"](interdit=f_or)
    o, m = B.ftmo(r[6].sort_index())
    print(">>> %-28s CAGR %+6.1f %%   reussite %3.0f %%   duree %3.0f j   DD %+5.1f %%"
          % (etiquette, r[0], o, m, r[2]))
    return r[0], o, m, r[2]

a = mesurer("L8 tel quel (prix negatifs)")

shutil.copy(F, SAUV)
try:
    df = pd.read_csv(F)
    n = 0
    for col in ("o", "h", "l", "c"):
        mask = df[col] <= 0
        n += int(mask.sum())
        df.loc[mask, col] = 0.01           # plancher positif
    # coherence : haut = max, bas = min
    df["h"] = df[["o", "h", "l", "c"]].max(axis=1)
    df["l"] = df[["o", "h", "l", "c"]].min(axis=1)
    df.to_csv(F, index=False)
    print("(%d valeurs negatives bornees a 0,01)" % n)
    b = mesurer("L8 avec plancher a 0,01")
finally:
    shutil.move(SAUV, F)
    print("(fichier d origine restaure)")

print()
print("ECART : CAGR %+.2f pt | reussite %+.0f pt | duree %+.0f j | DD %+.2f pt"
      % (b[0]-a[0], b[1]-a[1], b[2]-a[2], b[3]-a[3]))
