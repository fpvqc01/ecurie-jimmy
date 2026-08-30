# -*- coding: utf-8 -*-
"""BANC RESULTATS US100 - 25 aout 2026. Filtre "resultats d'entreprises"
sur la manche Nasdaq.

L'IDEE TESTEE
-------------
Les 8 geants du Nasdaq 100 (NVDA MSFT AAPL GOOGL AMZN META TSLA AVGO,
~la moitie du poids de l'indice) publient leurs resultats trimestriels,
presque toujours APRES la cloture de New York (16 h ET). Le lendemain,
l'indice gappe souvent de 1-2 %. Le filtre propose : BLOQUER toute NOUVELLE
entree de la manche Nasdaq dans une fenetre autour de chaque publication.
Les positions deja ouvertes ne sont pas touchees (dans le vrai robot elles
auront un serrage de stop, non mesurable ici).

CALENDRIER
----------
resultats_us100.csv (414 publications 2014-2026, via yfinance, heures
America/New_York converties en UTC). Verification faite : 98 % des
horodatages tombent a 20 h ou 21 h UTC = 16 h a New York selon l'heure
d'ete/hiver, exactement l'heure attendue.

FUSEAU DES DONNEES NASDAQ (verifie le 25 aout 2026)
---------------------------------------------------
d10h4_nq.csv porte des horodatages NAIFS. Preuve qu'ils sont en UTC :
l'amplitude moyenne (haut-bas) par barre H4 culmine sur la barre 12h-16h
(1,12 %) qui contient l'ouverture du comptant americain (13 h 30 UTC l'ete,
14 h 30 UTC l'hiver) dans LES DEUX saisons ; et la volatilite de la barre
20h-24h passe de 0,29 % l'ete a 0,59 % l'hiver, pile le deplacement de la
cloture (20 h UTC l'ete -> 21 h UTC l'hiver). Un fuseau courtier GMT+2/+3
mettrait l'ouverture dans la barre 16h-20h : ce n'est pas le cas. Les
fenetres de blocage sont donc comparees en UTC naif, sans conversion.

CONFIGURATIONS
--------------
  1. REFERENCE     : aucun filtre (doit reproduire la ligne de base du
                     chassis, = "L12 telle que PUBLIEE" de banc_L13).
  2. FILTRE COURT  : entrees Nasdaq bloquees de 4 h avant chaque
                     publication a 18 h apres (soir de l'annonce + matinee
                     du lendemain).
  3. FILTRE LARGE  : de 4 h avant a 30 h apres (tout le lendemain).

METHODE (calquee sur banc_L13)
------------------------------
Donnees figees et auditees (empreinte dans donnees/MANIFESTE.txt), chassis
L4.31, allocation deconcentree L11, gardien 2,50 %, breakeven 5 %, repli
conditionnel 1,25 ATR / 5 barres / force 1,00, simulateur FTMO v2, R13
actif, sans turbo ni CPPI (comparaison structurelle). Le filtre enveloppe
UNIQUEMENT s.ouvrir de la manche Nasdaq : si l'horodatage de la barre tombe
dans une fenetre de blocage, on retourne False (la valeur "rien fait" de
SleeveH4.ouvrir - sim_h4 teste `if ok:` et passe son chemin). Chaque
tentative bloquee est comptee : c'est la preuve que le filtre a mordu.

    python banc_resultats_us100.py
"""
import io
import json
import os
import sys
import time
import types

import numpy as np
import pandas as pd

D = os.path.dirname(os.path.abspath(__file__))
if D not in sys.path:
    sys.path.insert(0, D)


# --------------------------------------------------------------- chargement
def module_coupe(nom, coupe):
    """Importe un module SANS executer le banc qu'il contient a la fin.

    banc_L8.py et banc_repli*.py lancent leur propre banc au chargement (des
    dizaines de passes moteur). On coupe la source avant, et on enregistre le
    module dans sys.modules pour que les imports suivants reutilisent celui-ci.
    """
    src = io.open(os.path.join(D, nom), encoding="utf-8").read()
    assert coupe in src, "COUPE INTROUVABLE dans %s : %r" % (nom, coupe)
    m = types.ModuleType(nom[:-3])
    m.__file__ = os.path.join(D, nom)
    exec(compile(src.split(coupe)[0], m.__file__, "exec"), m.__dict__)
    sys.modules[nom[:-3]] = m
    return m


_o = sys.stdout
sys.stdout = io.StringIO()
B = module_coupe("banc_L8.py", '\nprint("=== BANC L8')
module_coupe("banc_repli.py", "\nFEN = (")
RC = module_coupe("banc_repli_conditionnel.py", "\nFEN = R.FEN")
import CLASSEMENT_DEFINITIF as CD          # noqa: E402  (banc_L8 deja en cache)
from serie_flottant import instrumenter2   # noqa: E402
sys.stdout = _o
import SIM_FTMO_V2 as V2                   # noqa: E402

PYR = B.PYR                       # ("BTC Cassure", "Petrole")
CIBLES = RC.CIBLES                # memes deux manches, pour le repli

# allocation deconcentree L11 : BTC cassure 1,15 %, le reste vers or/Nasdaq
ALLOC = {"Or": 0.0102, "Nasdaq": 0.0102, "Petrole": 0.0169,
         "BTC Cassure": 0.0115, "BTC EMA": 0.0113}
GARDE, BE = 0.025, 0.05
REPLI = dict(k_atr=1.25, fenetre=5, seuil_force=1.00)


def charger():
    """Charge le chassis canonique (tests_comite_B.py coupe avant la partie 5)."""
    src = io.open(os.path.join(D, "tests_comite_B.py"),
                  encoding="utf-8").read().split("# ============ 5.")[0]
    ns0 = {"__file__": os.path.join(D, "tests_comite_B.py")}
    s = sys.stdout
    sys.stdout = io.StringIO()
    exec(src, ns0)
    sys.stdout = s
    return ns0


# ------------------------------------------------- calendrier des resultats
def charger_calendrier():
    """Horodatages UTC naifs des 414 publications, tries, en datetime64[ns]."""
    cal = pd.read_csv(os.path.join(D, "resultats_us100.csv"))
    ts = pd.to_datetime(cal["datetime_utc"]).dropna()
    ev = np.sort(ts.values.astype("datetime64[ns]"))
    return ev


def filtre_resultats(s, ev, avant_h, apres_h, compteur):
    """Enveloppe s.ouvrir : bloque toute NOUVELLE entree si l'horodatage de
    la barre tombe dans [publication - avant_h ; publication + apres_h].

    sim_h4 n'appelle ouvrir que sur un signal reel : chaque appel bloque est
    une vraie tentative d'entree refusee. On retourne False, la valeur
    "rien fait" de SleeveH4.ouvrir (sim_h4 : `ok = s.ouvrir(...); if ok:`).
    Les positions deja ouvertes ne sont pas touchees : gerer() reste intact.
    """
    o0 = s.ouvrir
    avant = np.timedelta64(int(avant_h * 3600), "s")
    apres = np.timedelta64(int(apres_h * 3600), "s")

    def ouvrir(t, *a, **k):
        t64 = np.datetime64(t.to_datetime64())
        # bloque s'il existe une publication e avec e-avant <= t <= e+apres,
        # c.-a-d. e dans [t-apres ; t+avant]
        i = np.searchsorted(ev, t64 - apres, side="left")
        if i < len(ev) and ev[i] <= t64 + avant:
            compteur[0] += 1
            return False
        return o0(t, *a, **k)

    s.ouvrir = ouvrir
    return s


# ------------------------------------------------------------------ series
def serie(ns0, debut, fin, ev, fenetre_bloc):
    """Retourne (cagr, dd, vm, vo, vf, trades, entrees_bloquees).

    `fenetre_bloc` : None (reference) ou (avant_h, apres_h) en heures.
    """
    ns, f_or, fab = ns0["ns"], ns0["f_or"], ns0["fab_l431"]
    boite, compteur = [], [0]

    def f():
        sl = fab()()
        for s in sl:
            if s.nom in ALLOC:
                s.risque = ALLOC[s.nom]
        for s in sl:
            if s.nom in CIBLES:
                RC.repli_conditionnel(s, REPLI["k_atr"], REPLI["fenetre"],
                                      REPLI["seuil_force"])
            if s.nom in PYR:
                B.breakeven(s, BE)
            if s.nom == "Nasdaq" and fenetre_bloc is not None:
                filtre_resultats(s, ev, fenetre_bloc[0], fenetre_bloc[1],
                                 compteur)
        for s in sl:
            instrumenter2(s)
        boite[:] = sl
        return sl

    ns["DEBUT"], ns["FIN"] = debut, fin
    ns["sleeves_l4"] = f
    r = ns["sim_h4"](interdit=f_or)

    tj = r[6].sort_index()
    ouverts, flot = {}, {}
    for s in boite:
        for j in s.ouvertures:
            ouverts[j] = 1
        for j, vv in s.flot.items():
            flot[j] = flot.get(j, 0.0) + vv
    idx = tj.index
    vo = np.array([ouverts.get(j.date(), 0) for j in idx], dtype=float)
    vf = np.array([flot.get(j.date(), 0.0) for j in idx], dtype=float)
    return (r[0], r[2], tj.values.astype(float), vo, vf,
            sum(s.trades for s in boite), compteur[0])


# ----------------------------------------------------------------- configs
CONFIGS = [
    ("REFERENCE (aucun filtre)",            None),
    ("FILTRE COURT (-4 h -> +18 h)",        (4.0, 18.0)),
    ("FILTRE LARGE (-4 h -> +30 h)",        (4.0, 30.0)),
]
FENETRES = (("10 ans ", "2015-08-21", "2026-12-31", 730),
            ("2021-26", "2021-01-01", "2026-08-20", 730))
FTMO = dict(cibles=(0.10, 0.05), perte_jour=0.05, perte_totale=0.10,
            jours_min=4)

ENTETE = ("%-34s %6s %-13s %5s %6s %6s | %6s %7s %6s %8s %4s"
          % ("configuration", "reuss", "  [IC95]", "med", "esp", "<=60j",
             "CAGR", "creux", "trades", "bloquees", "ind"))


def main():
    emp = CD.rediriger_vers_donnees()
    print("=" * 122)
    print("BANC RESULTATS US100 - le filtre 'resultats d'entreprises' sur le "
          "Nasdaq coute-t-il quelque chose ?")
    print(emp)
    print("chassis L4.31 | gardien 2,50 % | breakeven 5 % | alloc deconcentree "
          "L11 | repli conditionnel 1,25/5/1,00")
    print("simulateur FTMO v2 (plancher au solde de minuit) | departs a plat | "
          "R13 actif | 2-Step 10 % + 5 % | sans turbo ni CPPI")
    print("calendrier : resultats_us100.csv (414 publications 2014-2026, "
          "8 tickers, UTC) | donnees Nasdaq verifiees UTC naif")
    print("=" * 122)

    ev = charger_calendrier()
    ns0 = charger()
    S, sortie = {}, {}
    for etq, fen in CONFIGS:
        for lib, deb, fin, _ in FENETRES:
            t0 = time.time()
            S[(etq, lib)] = serie(ns0, deb, fin, ev, fen)
            print("   . %-34s %s en %4.1f s" % (etq, lib, time.time() - t0),
                  file=sys.stderr)

    for lib, deb, fin, piste in FENETRES:
        print()
        print("-" * 122)
        print("FENETRE %s (%s -> %s)" % (lib, deb, fin))
        print("-" * 122)
        print(ENTETE)
        for etq, _ in CONFIGS:
            cagr, dd, vm, vo, vf, tr, bloq = S[(etq, lib)]
            r = V2.simuler(vm, vf, vo, piste_min=piste, r13=True,
                           regle="ftmo", gardien=0.010, **FTMO)
            print("%-34s %5.1f%% [%4.1f-%5.1f] %4.0fj %5.0fj %5.1f%% |"
                  " %+5.1f%% %6.1f%% %6d %8d %4d"
                  % (etq, r["reussite"], r["ic95"][0], r["ic95"][1],
                     r["duree_med"], r["esperance"], r["p60"],
                     cagr, dd, tr, bloq, r["n_independants"]))
            sortie.setdefault(lib, []).append(
                dict(config=etq, reussite=r["reussite"], ic95=r["ic95"],
                     med=r["duree_med"], p10=r["duree_p10"], p45=r["p45"],
                     p60=r["p60"], esp=r["esperance"], cagr=cagr, dd=dd,
                     trades=tr, entrees_bloquees=bloq,
                     morts_jour=r["morts_jour"],
                     morts_totale=r["morts_totale"],
                     non_resolus=r["non_resolus"],
                     n_departs=r["n_departs"],
                     n_independants=r["n_independants"]))

    print()
    print("RAPPEL : plancher de bruit du labo sigma = 7,9 jours sur")
    print("l'esperance. Tout ecart d'esperance < ~8 jours et tout ecart de")
    print("reussite dont les IC95 se recouvrent est du BRUIT. La question")
    print("n'est pas 'le filtre rapporte-t-il ?' mais 'coute-t-il ?'.")

    with io.open(os.path.join(D, "resultats_banc_resultats_us100.json"), "w",
                 encoding="utf-8") as fh:
        fh.write(json.dumps(sortie, indent=1, ensure_ascii=False))
    print()
    print("-> resultats_banc_resultats_us100.json")


if __name__ == "__main__":
    main()
