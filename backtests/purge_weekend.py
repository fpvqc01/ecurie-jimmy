# -*- coding: utf-8 -*-
"""Point E du comite : purger les barres de week-end / plates des CSV
Dukascopy (or, petrole, Nasdaq). Le BTC garde ses week-ends (il trade 7/7).
Originaux sauvegardes en *_brut.csv."""
import os, shutil, pandas as pd
D = os.path.dirname(os.path.abspath(__file__))
for nom in ("gc", "cl", "nq"):
    p = os.path.join(D, "d10h4_%s.csv" % nom)
    brut = os.path.join(D, "d10h4_%s_brut.csv" % nom)
    if not os.path.exists(brut):
        shutil.copy2(p, brut)
    df = pd.read_csv(brut, index_col=0, parse_dates=True)
    avant = len(df)
    df = df[df.index.dayofweek < 5]                      # samedi/dimanche dehors
    df = df[~((df["h"] == df["l"]) & (df["o"] == df["c"]))]   # barres plates dehors
    df.to_csv(p)
    print("%s : %d -> %d barres (%.0f %% purgees)" % (nom, avant, len(df), 100*(avant-len(df))/avant))
