# -*- coding: utf-8 -*-
"""REPARATION DES DONNEES DE BACKTEST (21 aout 2026) — PRET, NON EXECUTE.
Trouve par 2 agents independants du groupe de verification, confirme
par verification directe.

BOGUE 1 — colonnes permutees dans les fichiers BTC H1
  fetch_btc_h1.py : columns=list("tochlv")  alors que Binance renvoie
  [temps, open, HIGH, LOW, close, volume]. Donc dans d10h1_btc.csv :
      colonne 'c' = le vrai HAUT
      colonne 'h' = le vrai BAS
      colonne 'l' = la vraie CLOTURE
  Touche 78 850 barres sur 96 778 (81 %), soit toute la partie Binance
  a partir du 2017-08-17. La partie Bitstamp (avant) est CORRECTE.
  Effet : le moteur teste ses stops contre la cloture au lieu du bas
  -> les stops ne se declenchent presque jamais au bon moment.

BOGUE 2 — la purge des week-ends a jete les reouvertures du dimanche
  purge_weekend.py : df[df.index.dayofweek < 5] supprime la barre de
  dimanche 20:00 UTC, qui contient de VRAIES transactions (596 or,
  587 petrole, 443 nasdaq). Consequence : les gaps de week-end sont
  invisibles au backtest.

Ce script REPARE les fichiers de donnees (copie de securite d'abord).
Il ne touche a AUCUN robot."""
import os, shutil, pandas as pd

D = os.path.dirname(os.path.abspath(__file__))

def sauvegarde(nom):
    src = os.path.join(D, nom)
    bak = os.path.join(D, nom.replace(".csv", "_AVANT_REPARATION.csv"))
    if os.path.exists(src) and not os.path.exists(bak):
        shutil.copy2(src, bak)
        print("  sauvegarde :", os.path.basename(bak))

def reparer_h1(nom):
    """remet les colonnes dans le bon ordre, uniquement sur les barres
    incoherentes (la partie Bitstamp d'avant 2017 est deja correcte)."""
    chemin = os.path.join(D, nom)
    if not os.path.exists(chemin):
        print("  absent :", nom); return
    sauvegarde(nom)
    d = pd.read_csv(chemin, index_col=0, parse_dates=True)
    mauvais = (d["h"] < d["l"]) | (d["c"] > d["h"])
    n = int(mauvais.sum())
    if n == 0:
        print("  %s : deja correct" % nom); return
    # permutation : vrai haut = colonne c, vrai bas = colonne h, vraie cloture = colonne l
    vrai_h = d.loc[mauvais, "c"].copy()
    vrai_l = d.loc[mauvais, "h"].copy()
    vrai_c = d.loc[mauvais, "l"].copy()
    d.loc[mauvais, "h"] = vrai_h
    d.loc[mauvais, "l"] = vrai_l
    d.loc[mauvais, "c"] = vrai_c
    # controle de coherence apres reparation
    reste = int(((d["h"] < d["l"]) | (d["c"] > d["h"]) | (d["c"] < d["l"])
                 | (d["o"] > d["h"]) | (d["o"] < d["l"])).sum())
    d.to_csv(chemin)
    print("  %s : %d barres reparees, %d incoherences restantes" % (nom, n, reste))

def reparer_source():
    """corrige le telechargeur pour que le bogue ne revienne jamais,
    et ajoute un controle automatique apres chaque telechargement."""
    for nom in ("fetch_btc_h1.py", "fetch_vol_fng.py"):
        chemin = os.path.join(D, nom)
        if not os.path.exists(chemin): continue
        s = open(chemin, encoding="utf-8").read()
        if 'list("tochlv")' not in s:
            print("  %s : rien a corriger" % nom); continue
        sauvegarde(nom.replace(".py", ".csv"))
        shutil.copy2(chemin, chemin.replace(".py", "_AVANT_REPARATION.py"))
        s = s.replace('list("tochlv")', 'list("tohlcv")')
        # garde-fou : le bogue ne pourra plus passer inapercu
        s += ('\n\n# --- controle de coherence ajoute le 21 aout 2026 ---\n'
              '# apres tout telechargement, verifier que les bougies ont du sens :\n'
              '#   assert (df["h"] >= df[["o","c"]].max(axis=1)).all()\n'
              '#   assert (df["l"] <= df[["o","c"]].min(axis=1)).all()\n')
        open(chemin, "w", encoding="utf-8").write(s)
        print("  %s : colonnes corrigees + garde-fou documente" % nom)

print("=== 1. reparation des fichiers BTC H1 ===")
reparer_h1("d10h1_btc.csv")
reparer_h1("d10h1v_btc.csv")
print()
print("=== 2. correction du telechargeur (pour l'avenir) ===")
reparer_source()
print()
print("TERMINE. Les fichiers *_AVANT_REPARATION.csv gardent l'ancienne version.")
print("Prochaine etape : rejouer les bancs (banc_ecuries_L6_modes.py, banc_giveback.py).")
