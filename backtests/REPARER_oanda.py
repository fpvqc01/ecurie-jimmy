# -*- coding: utf-8 -*-
"""REPARATION DES FICHIERS oanda_*.csv (21 aout 2026, demande de Jimmy).

Ce n'est PAS le bogue de colonnes du matin : test_oanda_univers.py mappe
correctement ("o": q["open"], "h": q["high"], ...). C'est la source (Yahoo,
tickers forex "=X") qui livre des barres incoherentes : l'ouverture et la
fermeture viennent d'un instantane different du haut et du bas, donc parfois
o ou c tombe hors de [bas, haut].

Reparation conservatrice : haut = max(o,h,l,c) et bas = min(o,h,l,c).
On n'invente aucun prix : on ne fait qu'elargir la meche jusqu'aux valeurs
que la source a elle-meme rapportees. Sauvegarde avant ecriture."""
import glob, os, shutil
import pandas as pd

D = r"C:\Users\jplou\Downloads\Ecurie_Jimmy_I2plus_partage\backtests"
SAUV = os.path.join(D, "sauvegarde_avant_reparation_oanda")
os.makedirs(SAUV, exist_ok=True)

total_f = total_b = 0
for f in sorted(glob.glob(os.path.join(D, "oanda*.csv"))):
    nom = os.path.basename(f)
    df = pd.read_csv(f)
    if not all(c in df.columns for c in "ohlc"): 
        print("%-24s ignore (pas o/h/l/c)" % nom); continue
    O, H, L, C = (df[c].values.copy() for c in "ohlc")
    mauvais = ((H < L) | (H < O) | (H < C) | (L > O) | (L > C)).sum()
    if mauvais == 0:
        print("%-24s OK, rien a faire" % nom); continue
    shutil.copy(f, os.path.join(SAUV, nom))
    df["h"] = df[list("ohlc")].max(axis=1)
    df["l"] = df[list("ohlc")].min(axis=1)
    df.to_csv(f, index=False)
    reste = ((df["h"] < df["l"]) | (df["h"] < df["o"]) | (df["h"] < df["c"])
             | (df["l"] > df["o"]) | (df["l"] > df["c"])).sum()
    print("%-24s %5d barres reparees, %d incoherence(s) restante(s)" % (nom, mauvais, reste))
    total_f += 1; total_b += int(mauvais)

print()
print("%d fichier(s), %d barre(s) reparee(s). Sauvegardes dans %s" % (total_f, total_b, SAUV))
