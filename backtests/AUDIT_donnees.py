# -*- coding: utf-8 -*-
"""AUDIT DE TOUS LES FICHIERS DE DONNEES.
Cherche tout ce qui pourrait etre un 2e bogue du meme genre.
7 controles par fichier :
  1. haut >= bas                     (le bogue de colonnes du 21 aout)
  2. haut >= ouverture et fermeture  (colonnes melangees plus subtilement)
  3. bas  <= ouverture et fermeture
  4. aucun prix <= 0
  5. horodatage strictement croissant, aucun doublon
  6. aucun saut de prix > 40 % d'une barre a l'autre (donnee aberrante)
  7. volume >= 0 s'il existe
"""
import glob, os, sys
import pandas as pd, numpy as np

RACINES = [r"C:\Users\jplou\AppData\Local\Temp\claude\C--Users-jplou-Downloads\402ab065-414d-49fe-b7c5-31e3426fcd6c\scratchpad",
           r"C:\Users\jplou\Downloads\Ecurie_Jimmy_I2plus_partage\backtests",
           r"C:\Users\jplou\Downloads\Ecurie_Jimmy_I2plus_partage\donnees"]

fichiers = []
for r in RACINES:
    fichiers += glob.glob(os.path.join(r, "**", "*.csv"), recursive=True)
EXCLUS = ("AVANT_REPARATION", "sauvegarde_avant", "sauv_test", ".sauv")
fichiers = sorted(set(f for f in fichiers if not any(x in f for x in EXCLUS)))

# Anomalies REELLES et documentees : c'est de l'histoire, pas un bogue.
# Verifiees une par une le 21 aout 2026, impact mesure a zero.
CONNUES = {
    "d10_cl.csv":   ("prix<=0", "saut >40 %"),   # WTI a -37,63 $ les 20-21 avril 2020
    "oanda_NGF.csv": ("saut >40 %",),            # gaz naturel, roulement de contrat
}

def col(df, *noms):
    for n in noms:
        for c in df.columns:
            if c.strip().lower() == n: return c
    return None

print("%-42s %8s | %s" % ("fichier", "barres", "verdict"))
print("-" * 100)
total_pb = 0
for f in fichiers:
    nom = os.path.basename(f)
    try:
        df = pd.read_csv(f)
    except Exception as e:
        print("%-42s %8s | LECTURE IMPOSSIBLE : %s" % (nom[:42], "-", e)); continue
    o, h, l, c = (col(df, "o", "open"), col(df, "h", "high"),
                  col(df, "l", "low"), col(df, "c", "close"))
    if not all((h, l, c)):
        print("%-42s %8d | pas un fichier de chandelles (ignore)" % (nom[:42], len(df))); continue
    pb = []
    H, L, C = df[h].values, df[l].values, df[c].values
    O = df[o].values if o else C
    n = len(df)
    x = int((H < L).sum());                        pb.append(("haut<bas", x))
    x = int(((H < O) | (H < C)).sum());            pb.append(("haut<ouv/ferm", x))
    x = int(((L > O) | (L > C)).sum());            pb.append(("bas>ouv/ferm", x))
    x = int(((H <= 0) | (L <= 0) | (C <= 0)).sum()); pb.append(("prix<=0", x))
    t = col(df, "t", "time", "date", "datetime", "timestamp")
    if t:
        ts = pd.to_datetime(df[t], errors="coerce", utc=True)
        pb.append(("horodatage illisible", int(ts.isna().sum())))
        pb.append(("doublons", int(ts.duplicated().sum())))
        pb.append(("hors ordre", int((ts.diff().dt.total_seconds() < 0).sum())))
    with np.errstate(divide="ignore", invalid="ignore"):
        var = np.abs(np.diff(C) / C[:-1])
    pb.append(("saut >40 %", int((var > 0.40).sum())))
    v = col(df, "v", "volume")
    if v: pb.append(("volume<0", int((df[v].values < 0).sum())))

    mauvais = [(k, x) for k, x in pb if x > 0]
    connues = CONNUES.get(nom, ())
    reelles = [(k, x) for k, x in mauvais if k not in connues]
    if mauvais and not reelles:
        print("%-42s %8d | OK (anomalie connue et documentee : %s)"
              % (nom[:42], n, ", ".join(k for k, _ in mauvais)))
    elif reelles:
        mauvais = reelles
        total_pb += 1
        print("%-42s %8d | *** %s" % (nom[:42], n,
              ", ".join("%s : %d" % (k, x) for k, x in mauvais)))
    else:
        print("%-42s %8d | OK" % (nom[:42], n))

print("-" * 100)
print("%d fichier(s) avec au moins une anomalie sur %d examines." % (total_pb, len(fichiers)))
