# -*- coding: utf-8 -*-
"""FIGE ET AUDITE LE JEU DE DONNEES DE REFERENCE (21 aout 2026).

Pourquoi ce script existe
-------------------------
Le comite du 21 aout a etabli que le choix de preparation des donnees
deplace le taux de reussite de L8 de 89 % a 75 % - plus que tout ecart
entre generations. Et jusqu'a aujourd'hui, les donnees qui faisaient foi
vivaient dans un dossier temporaire Windows, effacable sans preavis,
pendant que le depot contenait des versions brutes differentes.

Ce script ecrit `donnees/MANIFESTE.txt` : pour chaque fichier du jeu de
reference, son empreinte SHA256, sa periode, son nombre de barres, et le
resultat de 8 controles d'integrite. Toute publication de chiffres doit
citer l'empreinte du manifeste. Si une empreinte change, les chiffres
changent : c'est le contrat.

Les 8 controles
---------------
  1. haut < bas                  (le bogue Binance des colonnes)
  2. ouverture ou cloture hors [bas, haut]
  3. prix nul ou negatif
  4. horodatages en double
  5. horodatages non tries
  6. barres plates (o == h == l == c)   <- controle AJOUTE le 21 aout
  7. barres de week-end sur un marche qui ferme  <- AJOUTE le 21 aout
  8. trous anormaux dans la serie

Les controles 6 et 7 sont ceux qui manquaient : ils laissaient passer
27 a 31 % de fausses bougies sans rien dire.
"""
import hashlib
import io
import os
import sys

import pandas as pd

D = os.path.dirname(os.path.abspath(__file__))
DONNEES = os.path.join(os.path.dirname(D), "donnees")

# marches qui FERMENT la fin de semaine (le BTC, lui, cote 7 j/7)
FERME_WEEKEND = ("gc", "nq", "cl", "dxy")


def sha256(chemin):
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def controles(df, nom):
    """retourne (liste de constats, nombre d'anomalies bloquantes)"""
    out, dur = [], 0
    cols = set(df.columns)

    if {"o", "h", "l", "c"} <= cols:
        n = int((df["h"] < df["l"]).sum())
        out.append(("1. haut < bas", n))
        dur += n

        hors = int(((df["o"] > df["h"]) | (df["o"] < df["l"]) |
                    (df["c"] > df["h"]) | (df["c"] < df["l"])).sum())
        out.append(("2. o/c hors [bas, haut]", hors))
        dur += hors

        nuls = int((df[["o", "h", "l", "c"]] <= 0).any(axis=1).sum())
        # EXCEPTION DOCUMENTEE : le WTI a reellement cote en NEGATIF les
        # 20 et 21 avril 2020 (reglement a -37,63 $). Ce n est pas une
        # corruption. A savoir : le CFD USOIL de FTMO, lui, n est jamais
        # descendu sous +10 $ -> le journalier (contrats a terme) et le
        # H4 (CFD comptant) ne racontent PAS la meme crise 2020.
        if "cl" in nom and nuls <= 2:
            out.append(("3. prix nul ou negatif", str(nuls) + " (WTI avril 2020, reel)"))
        else:
            out.append(("3. prix nul ou negatif", nuls))
            dur += nuls

        plates = int((df["o"].eq(df["h"]) & df["h"].eq(df["l"]) &
                      df["l"].eq(df["c"])).sum())
        out.append(("6. barres plates", plates))          # informatif
    else:
        out.append(("1-3, 6. controles OHLC", "n/a (pas de colonnes OHLC)"))

    if "t" in cols:
        t = pd.to_datetime(df["t"])
        dbl = int(t.duplicated().sum())
        out.append(("4. horodatages en double", dbl))
        dur += dbl

        tri = 0 if t.is_monotonic_increasing else 1
        out.append(("5. horodatages non tries", tri))
        dur += tri

        base = nom.split("_")[-1].replace(".csv", "")
        if any(m in nom for m in FERME_WEEKEND):
            we = int(t.dt.dayofweek.isin([5, 6]).sum())
            out.append(("7. barres de week-end", we))     # informatif
        else:
            out.append(("7. barres de week-end", "n/a (cote 7 j/7)"))

        if len(t) > 2:
            ecarts = t.diff().dropna()
            median = ecarts.median()
            trous = int((ecarts > median * 20).sum())
            out.append(("8. trous > 20x l'ecart median", trous))
        else:
            out.append(("8. trous", 0))
    else:
        out.append(("4-5, 7-8. controles temporels", "n/a (pas de colonne t)"))

    return out, dur


def main():
    if not os.path.isdir(DONNEES):
        sys.exit("dossier introuvable : " + DONNEES)

    fichiers = sorted(f for f in os.listdir(DONNEES) if f.endswith(".csv"))
    if not fichiers:
        sys.exit("aucun CSV dans " + DONNEES)

    lignes = []
    lignes.append("MANIFESTE DU JEU DE DONNEES DE REFERENCE")
    lignes.append("=" * 78)
    lignes.append("")
    lignes.append("Genere par backtests/FIGER_donnees.py")
    lignes.append("Toute publication de chiffres doit citer l'empreinte globale ci-dessous.")
    lignes.append("")

    total_dur = 0
    empreintes = []

    for nom in fichiers:
        chemin = os.path.join(DONNEES, nom)
        emp = sha256(chemin)
        empreintes.append(emp)
        try:
            df = pd.read_csv(chemin)
        except Exception as e:
            lignes.append("%-34s LECTURE IMPOSSIBLE : %s" % (nom, e))
            lignes.append("")
            continue

        res, dur = controles(df, nom)
        total_dur += dur

        periode = ""
        if "t" in df.columns and len(df):
            t = pd.to_datetime(df["t"])
            periode = "%s -> %s" % (t.iloc[0].date(), t.iloc[-1].date())

        lignes.append(nom)
        lignes.append("  sha256   : " + emp)
        lignes.append("  lignes   : %d" % len(df))
        if periode:
            lignes.append("  periode  : " + periode)
        for libelle, valeur in res:
            marque = ""
            if isinstance(valeur, int) and valeur > 0:
                bloquant = libelle[0] in "12345"
                marque = "  <== ANOMALIE" if bloquant else "  (informatif)"
            lignes.append("  %-32s %s%s" % (libelle, valeur, marque))
        lignes.append("")

    globale = hashlib.sha256("".join(sorted(empreintes)).encode()).hexdigest()

    lignes.append("=" * 78)
    lignes.append("FICHIERS            : %d" % len(fichiers))
    lignes.append("ANOMALIES BLOQUANTES: %d" % total_dur)
    lignes.append("EMPREINTE GLOBALE   : " + globale)
    lignes.append("=" * 78)
    if total_dur == 0:
        lignes.append("")
        lignes.append("JEU DE DONNEES SAIN - utilisable comme reference.")
    else:
        lignes.append("")
        lignes.append("!! NE PAS UTILISER CE JEU TANT QUE LES ANOMALIES NE SONT PAS REGLEES.")

    texte = "\n".join(lignes) + "\n"
    with io.open(os.path.join(DONNEES, "MANIFESTE.txt"), "w",
                 encoding="utf-8", newline="\n") as f:
        f.write(texte)
    print(texte)


if __name__ == "__main__":
    main()
