# -*- coding: utf-8 -*-
"""BANC GAPS DE RESULTATS - 25 aout 2026. Volet "serrage de stops" du
filtre resultats US100.

LA QUESTION
-----------
Le volet "blocage des nouvelles entrees" a ete tranche le meme jour par
banc_resultats_us100.py : REGRESSION NETTE, on ne bloque pas les entrees.
Reste le second volet du vrai robot (ProtegerPositionsNews(), lignes
~694-733 de US100_Nasdaq_S32_H4.mq5) : pendant la fenetre autour d'une
publication de resultats d'un geant du US100, le robot releve chaque
minute le stop des positions DEJA OUVERTES a `bid - 0,5 x ATR(14, H4)`,
jamais abaisse, et jamais sous le prix d'entree quand la position est
gagnante (`if(bid > entree && entree > nouveau) nouveau = entree;`).

EXECUTION DES STOPS DANS LE MOTEUR (constat, 25 aout 2026)
----------------------------------------------------------
moteur_h4.py, SleeveH4.gerer, lignes 130-131 :

    if l <= p["s"]:
        self._clore(t, p["s"]); ...

Le moteur remplit AU PRIX DU STOP meme quand la barre OUVRE dessous
(gerer_pyr_max de valide_candidats_h4.py, lignes 21-22, fait pareil).
Aucun glissement de gap n'est modelise. Ce banc ajoute donc une
surcouche "gaps pessimistes" sur la manche Nasdaq : si une barre H4
ouvre SOUS le stop d'une position acheteuse, la sortie se fait a l'OPEN
de la barre. La surcouche est appliquee a la REFERENCE comme aux
configs serrees, sinon la comparaison serait biaisee en faveur du
serrage (qui place des stops hauts, exactement la ou les gaps mordent).

TRADUCTION DU SERRAGE EN H4
---------------------------
A chaque barre H4 dont l'horodatage tombe dans [publication - 4 h ;
publication + 18 h], la manche Nasdaq fait, AVANT la gestion normale de
la barre :

    niveau = close_precedente - K x ATR          (K = 0,5 ou 1,0)
    si close_precedente > entree et entree > niveau : niveau = entree
    stop = max(stop, niveau)                     (jamais abaisse)

L'ATR est celui que la manche connait deja : v[0] de s.prov(i), l'ATR
JOURNALIER hybride (jour en cours inclus). ATTENTION : le vrai robot
serre a 0,5 x ATR(14, H4), nettement PLUS pres du prix (l'ATR H4 vaut
grosso modo 40 % de l'ATR journalier). Le serrage teste ici est donc
MOINS agressif que celui du robot : si ce serrage-ci coute deja, le
vrai coute plus.

INSTRUMENT PRINCIPAL : LE BILAN PAR EVENEMENT
---------------------------------------------
Chaque sortie causee par un stop serre (stop touche alors que le stop
d'origine ne l'aurait pas ete, ou gap d'ouverture entre les deux) est
rejouee en ombre : la position est suivie barre par barre avec son stop
D'ORIGINE (la manche Nasdaq n'a ni breakeven ni trailing : son stop ne
bouge JAMAIS dans le moteur de base, le contrefactuel est propre)
jusqu'a sa sortie naturelle (stop, TP, ou fin des donnees), gaps
pessimistes inclus. Le delta = ce que le serrage a sauve (>0) ou coute
(<0), en % du compte. Cet instrument n'est PAS soumis au plancher de
bruit de sigma = 7,9 jours du simulateur de challenges.

Limites du contrefactuel : il ignore le gardien quotidien (qui aurait pu
couper la position en chemin) et le fait que la manche, restee en
position, n'aurait pas pris ses entrees suivantes au meme moment.

    python banc_gaps_resultats.py
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
    """Importe un module SANS executer le banc qu'il contient a la fin."""
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
import CLASSEMENT_DEFINITIF as CD          # noqa: E402
from serie_flottant import instrumenter2   # noqa: E402
sys.stdout = _o
import SIM_FTMO_V2 as V2                   # noqa: E402

PYR = B.PYR                       # ("BTC Cassure", "Petrole")
CIBLES = RC.CIBLES

# allocation deconcentree L11 : BTC cassure 1,15 %, le reste vers or/Nasdaq
ALLOC = {"Or": 0.0102, "Nasdaq": 0.0102, "Petrole": 0.0169,
         "BTC Cassure": 0.0115, "BTC EMA": 0.0113}
GARDE, BE = 0.025, 0.05
REPLI = dict(k_atr=1.25, fenetre=5, seuil_force=1.00)
AVANT_H, APRES_H = 4.0, 18.0      # fenetre de serrage, comme le filtre court


def charger():
    """Chassis canonique (tests_comite_B.py coupe avant la partie 5)."""
    src = io.open(os.path.join(D, "tests_comite_B.py"),
                  encoding="utf-8").read().split("# ============ 5.")[0]
    ns0 = {"__file__": os.path.join(D, "tests_comite_B.py")}
    s = sys.stdout
    sys.stdout = io.StringIO()
    exec(src, ns0)
    sys.stdout = s
    return ns0


def charger_calendrier():
    cal = pd.read_csv(os.path.join(D, "resultats_us100.csv"))
    ts = pd.to_datetime(cal["datetime_utc"]).dropna()
    return np.sort(ts.values.astype("datetime64[ns]"))


# ==================================================================== #
# ETAPE 1 - RADIOGRAPHIE DES EVENEMENTS (donnees H4, aucune simulation) #
# ==================================================================== #
def stats_dist(x):
    x = np.asarray(x, dtype=float)
    return dict(n=int(len(x)), mediane=float(np.median(x)),
                p10=float(np.percentile(x, 10)),
                p90=float(np.percentile(x, 90)),
                pire=float(np.min(x)),
                pct_adverse=float(100.0 * np.mean(x < 0)),
                mediane_abs=float(np.median(np.abs(x))))


def radiographie(ev):
    nq = pd.read_csv(os.path.join(D, "d10h4_nq.csv"), index_col=0,
                     parse_dates=True)[["o", "h", "l", "c"]].astype(float)
    idx = nq.index
    O, C = nq["o"].values, nq["c"].values
    pos_de_t = {t: i for i, t in enumerate(idx)}
    # barre 12h du jour dd : premiere barre a 12:00 datee dd..dd+4j
    douze = {}                      # date -> indice de la barre 12h
    for i, t in enumerate(idx):
        if t.hour == 12 and t.date() not in douze:
            douze[t.date()] = i

    def mesures(i_pub):
        """(ret barre, gap du soir, seance du lendemain) pour la barre i_pub."""
        r_barre = C[i_pub] / O[i_pub] - 1.0
        gap = None
        if i_pub + 1 < len(idx):
            gap = O[i_pub + 1] / C[i_pub] - 1.0
        lend = None
        d = idx[i_pub].date()
        for dj in range(1, 5):
            j = douze.get(d + pd.Timedelta(days=dj).to_pytimedelta())
            if j is not None and j > i_pub:
                lend = C[j] / C[i_pub] - 1.0
                break
        return r_barre, gap, lend

    # --- evenements couverts par les donnees
    ev_ts = pd.DatetimeIndex(ev)
    e_barre, e_gap, e_lend, dates_ev = [], [], [], set()
    couverts = 0
    for t_ev in ev_ts:
        if t_ev < idx[0] or t_ev > idx[-1]:
            continue
        # barre contenant la publication : derniere barre ouverte <= t_ev
        i = int(np.searchsorted(idx.values, np.datetime64(t_ev), "right")) - 1
        if i < 0 or not (idx[i] <= t_ev < idx[i] + pd.Timedelta(hours=4)):
            continue
        couverts += 1
        dates_ev.add(idx[i].date())
        rb, g, ld = mesures(i)
        e_barre.append(rb)
        if g is not None:
            e_gap.append(g)
        if ld is not None:
            e_lend.append(ld)

    # --- controle : meme barre (20h), memes jours de semaine, sans
    #     publication a moins de 48 h
    jours_ev = {t.weekday() for t in ev_ts}
    marge = pd.Timedelta(hours=48)
    c_barre, c_gap, c_lend = [], [], []
    for i, t in enumerate(idx):
        if t.hour != 20 or t.weekday() not in jours_ev:
            continue
        k = int(np.searchsorted(ev, np.datetime64(t)))
        proche = ((k < len(ev) and pd.Timestamp(ev[k]) - t <= marge) or
                  (k > 0 and t - pd.Timestamp(ev[k - 1]) <= marge))
        if proche:
            continue
        rb, g, ld = mesures(i)
        c_barre.append(rb)
        if g is not None:
            c_gap.append(g)
        if ld is not None:
            c_lend.append(ld)

    out = dict(
        evenements_total=int(len(ev)), evenements_couverts=int(couverts),
        evenement=dict(barre=stats_dist(e_barre), gap_soir=stats_dist(e_gap),
                       lendemain=stats_dist(e_lend)),
        controle=dict(barre=stats_dist(c_barre), gap_soir=stats_dist(c_gap),
                      lendemain=stats_dist(c_lend)))

    print()
    print("-" * 122)
    print("ETAPE 1 - RADIOGRAPHIE : %d publications, %d couvertes par les "
          "donnees H4 (2015-2026)" % (len(ev), couverts))
    print("le controle = barres 20h-24h des memes jours de semaine, sans "
          "publication a moins de 48 h")
    print("-" * 122)
    print("%-26s %6s %8s %8s %8s %9s %9s %9s"
          % ("mesure (position ACHETEUSE)", "n", "mediane", "p10", "p90",
             "pire", "% <0", "med |x|"))
    for cle, etq in (("barre", "barre de publication 20h-24h"),
                     ("gap_soir", "gap du soir (open suivant)"),
                     ("lendemain", "seance du lendemain (16h)")):
        for grp, tag in (("evenement", "PUBLICATION"), ("controle", "controle")):
            st = out[grp][cle]
            print("%-26s %6d %+7.2f%% %+7.2f%% %+7.2f%% %+8.2f%% %8.1f%% %8.2f%%"
                  % ("%s %s" % (etq if grp == "evenement" else " ", tag),
                     st["n"], 100 * st["mediane"], 100 * st["p10"],
                     100 * st["p90"], 100 * st["pire"], st["pct_adverse"],
                     100 * st["mediane_abs"]))
    return out


# ==================================================================== #
# ETAPE 2 - SURCOUCHE NASDAQ : serrage + gaps pessimistes               #
# ==================================================================== #
def dans_fenetre(ev, t64, avant, apres):
    i = np.searchsorted(ev, t64 - apres, side="left")
    return i < len(ev) and ev[i] <= t64 + avant


def contrefactuel(s, i, s0, tp):
    """Sortie naturelle de la position avec son stop d'origine s0, gaps
    pessimistes inclus, a partir de la barre i. -> (prix, barres)."""
    n = len(s.C)
    for j in range(i, n):
        if s.O[j] < s0:
            return s.O[j], j - i
        if s.L[j] <= s0:
            return s0, j - i
        if tp is not None and s.H[j] >= tp:
            return tp, j - i
    return s.C[n - 1], n - 1 - i


def surcouche_nasdaq(s, ev, k_serrage, stats):
    """Serrage de stop en fenetre d'annonce (si k_serrage) + execution
    pessimiste dans les gaps (toujours). Manche Nasdaq uniquement.

    La manche Nasdaq (FibH4, tpj=1,0) n'a NI breakeven (be=None des que
    tpj < 2,0) NI trailing : son stop d'origine ne bouge jamais dans le
    moteur de base. Toute difference entre p["s"] et p["s0"] vient donc
    du serrage - le contrefactuel par evenement est exact.
    """
    avant = np.timedelta64(int(AVANT_H * 3600), "s")
    apres = np.timedelta64(int(APRES_H * 3600), "s")
    g0, o0 = s.gerer, s.ouvrir

    def ouvrir(t, *a, **kw):
        r = o0(t, *a, **kw)
        if r and s.pos is not None:
            s.pos["s0"] = s.pos["s"]
        return r

    def clore_trace(t, prix):
        s._trace_clore = prix
        c0(t, prix)

    c0 = s._clore
    s._clore = clore_trace

    def gerer(t):
        i = s.idx.get(t)
        p = s.pos
        if i is None or p is None or "s0" not in p:
            return g0(t)
        # 1) serrage si la barre tombe dans une fenetre d'annonce
        if k_serrage is not None and dans_fenetre(
                ev, np.datetime64(t.to_datetime64()), avant, apres):
            s._maj_jour(i)                      # idempotent
            v = s.prov(i)
            if v is not None and v[0] > 0 and i > 0:
                cp = s.C[i - 1]
                niveau = cp - k_serrage * v[0]
                if cp > p["e"] and p["e"] > niveau:
                    niveau = p["e"]             # jamais sous l'entree gagnante
                if niveau > p["s"]:
                    p["s"] = niveau
                    stats["serrages"] += 1
        # 2) gap pessimiste : la barre ouvre sous le stop -> sortie a l'OPEN
        if s.O[i] < p["s"]:
            prix, s0, tp = s.O[i], p["s0"], p.get("tp")
            nn, e = p["n"], p["e"]
            s._clore(t, prix)
            s.attente = None
            if prix <= s0:                      # serait sorti de toute facon
                stats["gaps_anyway"] += 1
                stats["cout_gaps_anyway"] += 100 * nn * (prix - s0) / e
            else:                               # sortie CAUSEE par le serrage
                pcf, nb = contrefactuel(s, i, s0, tp)
                stats["journal"].append(dict(
                    t=str(t), cause="gap_serre", prix=float(prix),
                    stop_origine=float(s0), prix_contrefactuel=float(pcf),
                    barres_avant_sortie_naturelle=int(nb),
                    delta_pct=float(100 * nn * (prix - pcf) / e)))
            return g0(t)                        # pos=None : ne fait plus rien
        # 3) gestion normale, puis attribution d'une sortie stop serre
        stop_barre, s0, tp = p["s"], p["s0"], p.get("tp")
        nn, e = p["n"], p["e"]
        s._trace_clore = None
        g0(t)
        if (s.pos is None and s._trace_clore is not None
                and abs(s._trace_clore - stop_barre) < 1e-9 * max(stop_barre, 1)
                and stop_barre > s0 * (1 + 1e-12) and stop_barre > s0):
            pcf, nb = contrefactuel(s, i, s0, tp)
            stats["journal"].append(dict(
                t=str(t), cause="stop_serre", prix=float(stop_barre),
                stop_origine=float(s0), prix_contrefactuel=float(pcf),
                barres_avant_sortie_naturelle=int(nb),
                delta_pct=float(100 * nn * (stop_barre - pcf) / e)))

    s.ouvrir, s.gerer = ouvrir, gerer
    return s


# ------------------------------------------------------------------ series
def serie(ns0, debut, fin, ev, k_serrage, gaps):
    """-> (cagr, dd, vm, vo, vf, trades, stats)."""
    ns, f_or, fab = ns0["ns"], ns0["f_or"], ns0["fab_l431"]
    boite = []
    stats = dict(serrages=0, gaps_anyway=0, cout_gaps_anyway=0.0, journal=[])

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
            if s.nom == "Nasdaq" and gaps:
                surcouche_nasdaq(s, ev, k_serrage, stats)
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
            sum(s.trades for s in boite), stats)


# ----------------------------------------------------------------- configs
CONFIGS = [
    ("REFERENCE (moteur tel quel)",          None, False),
    ("REFERENCE + gaps pessimistes",         None, True),
    ("SERRAGE 0,5 ATR (+ gaps)",              0.5, True),
    ("SERRAGE PRUDENT 1,0 ATR (+ gaps)",      1.0, True),
]
FENETRES = (("10 ans ", "2015-08-21", "2026-12-31", 730),
            ("2021-26", "2021-01-01", "2026-08-20", 730))
FTMO = dict(cibles=(0.10, 0.05), perte_jour=0.05, perte_totale=0.10,
            jours_min=4)

ENTETE = ("%-34s %6s %-13s %5s %6s %6s | %6s %7s %6s %8s %8s %4s"
          % ("configuration", "reuss", "  [IC95]", "med", "esp", "<=60j",
             "CAGR", "creux", "trades", "serrages", "sorties", "ind"))


def main():
    emp = CD.rediriger_vers_donnees()
    print("=" * 122)
    print("BANC GAPS DE RESULTATS - serrer le stop du Nasdaq pendant les "
          "fenetres de publication, ca sauve ou ca coute ?")
    print(emp)
    print("chassis L4.31 | gardien 2,50 % | breakeven 5 % | alloc deconcentree "
          "L11 | repli conditionnel 1,25/5/1,00")
    print("simulateur FTMO v2 (plancher au solde de minuit) | departs a plat | "
          "R13 actif | 2-Step 10 % + 5 % | sans turbo ni CPPI")
    print("fenetre de serrage : -%.0f h -> +%.0f h autour de chaque "
          "publication | gaps pessimistes : sortie a l'OPEN si la barre"
          % (AVANT_H, APRES_H))
    print("ouvre sous le stop (le moteur, lui, remplit AU PRIX DU STOP : "
          "moteur_h4.py lignes 130-131)")
    print("=" * 122)

    ev = charger_calendrier()
    radio = radiographie(ev)

    ns0 = charger()
    S, sortie = {}, {"radiographie": radio}
    for etq, k, gaps in CONFIGS:
        for lib, deb, fin, _ in FENETRES:
            t0 = time.time()
            S[(etq, lib)] = serie(ns0, deb, fin, ev, k, gaps)
            print("   . %-34s %s en %4.1f s" % (etq, lib, time.time() - t0),
                  file=sys.stderr)

    for lib, deb, fin, piste in FENETRES:
        print()
        print("-" * 122)
        print("FENETRE %s (%s -> %s)" % (lib, deb, fin))
        print("-" * 122)
        print(ENTETE)
        for etq, _, _ in CONFIGS:
            cagr, dd, vm, vo, vf, tr, st = S[(etq, lib)]
            r = V2.simuler(vm, vf, vo, piste_min=piste, r13=True,
                           regle="ftmo", gardien=0.010, **FTMO)
            print("%-34s %5.1f%% [%4.1f-%5.1f] %4.0fj %5.0fj %5.1f%% |"
                  " %+5.1f%% %6.1f%% %6d %8d %8d %4d"
                  % (etq, r["reussite"], r["ic95"][0], r["ic95"][1],
                     r["duree_med"], r["esperance"], r["p60"],
                     cagr, dd, tr, st["serrages"], len(st["journal"]),
                     r["n_independants"]))
            sortie.setdefault(lib, []).append(
                dict(config=etq, reussite=r["reussite"], ic95=r["ic95"],
                     med=r["duree_med"], p10=r["duree_p10"], p45=r["p45"],
                     p60=r["p60"], esp=r["esperance"], cagr=cagr, dd=dd,
                     trades=tr, serrages=st["serrages"],
                     gaps_anyway=st["gaps_anyway"],
                     cout_gaps_anyway_pct=st["cout_gaps_anyway"],
                     sorties_serrage=st["journal"],
                     morts_jour=r["morts_jour"],
                     morts_totale=r["morts_totale"],
                     non_resolus=r["non_resolus"],
                     n_departs=r["n_departs"],
                     n_independants=r["n_independants"]))

    # ------------------------------------------------ bilan par evenement
    print()
    print("-" * 122)
    print("BILAN PAR EVENEMENT (l'instrument le plus sensible - pas soumis "
          "au plancher de bruit de 7,9 j)")
    print("delta > 0 = le serrage a SAUVE de l'argent (sortie meilleure que "
          "la sortie naturelle), delta < 0 = il en a COUTE")
    print("-" * 122)
    for lib, _, _, _ in FENETRES:
        print("  fenetre %s" % lib)
        for etq, k, gaps in CONFIGS:
            st = S[(etq, lib)][6]
            j = st["journal"]
            if not gaps:
                print("    %-34s (moteur tel quel : aucun gap, aucun serrage)"
                      % etq)
                continue
            sauv = [x["delta_pct"] for x in j if x["delta_pct"] > 0]
            cout = [x["delta_pct"] for x in j if x["delta_pct"] <= 0]
            print("    %-34s serrages %5d | sorties serrees %3d "
                  "(sauvetages %2d : %+6.3f %% ; prematurees %2d : %+6.3f %%)"
                  " | net %+6.3f %% | gaps de toute facon %2d (%+6.3f %%)"
                  % (etq, st["serrages"], len(j), len(sauv), sum(sauv),
                     len(cout), sum(cout), sum(sauv) + sum(cout),
                     st["gaps_anyway"], st["cout_gaps_anyway"]))
        print()

    print("RAPPEL : plancher de bruit du labo sigma = 7,9 jours sur")
    print("l'esperance ; les metriques de challenge ne tranchent qu'au-dela.")
    print("Le bilan par evenement, lui, est exact a ses limites pres")
    print("(gardien et re-entrees ignores dans le contrefactuel).")

    with io.open(os.path.join(D, "resultats_banc_gaps_resultats.json"), "w",
                 encoding="utf-8") as fh:
        fh.write(json.dumps(sortie, indent=1, ensure_ascii=False))
    print()
    print("-> resultats_banc_gaps_resultats.json")


if __name__ == "__main__":
    main()
