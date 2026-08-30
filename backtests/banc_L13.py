# -*- coding: utf-8 -*-
"""BANC L13 - 22 aout 2026. Mesure des correctifs de la generation L13.

POURQUOI CE BANC EXISTE
-----------------------
L13 corrige six defauts. Trois seulement changent le COMPORTEMENT de trading
et sont donc mesurables ici :

  C1  ANCRE ROULANTE. Le stop suiveur des deux robots a pyramide s'accrochait
      a `dernier`, le prix d'entree de la DERNIERE UNITE. Pile pleine a
      4 unites = plus aucune unite ajoutee = ancre gelee = stop qui cesse de
      monter. En L13 l'ancre suit l'extreme atteint.

  C2  PLAFOND D'ECURIE. `ComptePositionsEcurie()` ne comptait que trois
      magics (BTC EMA, BTC cassure, petrole). L'or et le Nasdaq etaient
      invisibles : le plafond de 2 piles en laissait passer jusqu'a 4, et ce
      meme plafond bloque aussi les AJOUTS de pyramide (ligne 875 du .mq5),
      donc la pyramide grossissait dans des situations ou elle n'aurait pas du.

  C3  GARDE-FOU DE CORRELATION. `FamilleCorreleeOccupee()` devait empecher
      "deux metaux/indices en meme temps". Sa liste de magics excluait l'or et
      le Nasdaq - exactement la paire a surveiller. Il n'a jamais pu se
      declencher.

Les trois autres correctifs (facteurVol conserve, refus ecrits au bloc-notes,
"news libre" vs "aveugle") ne se mesurent pas en backtest : ils touchent la
lecture de fichiers en direct et la tracabilite, pas la decision de trade.

CE QUE LE MOTEUR PYTHON FAISAIT, LUI
------------------------------------
Le moteur d'ecurie (`gerer_pyr_max`, `sim_h4`) n'est PAS un miroir de L12 :

  * il gele l'ancre exactement comme L12  -> meme defaut C1 ;
  * il compte les CINQ manches dans le plafond et applique le garde-fou de
    correlation -> il modelisait deja C2/C3 REPARES ;
  * il n'a JAMAIS applique le plafond aux ajouts de pyramide.

"L12 telle que publiee" n'est donc le portrait d'aucun robot ayant existe. Ce
banc mesure les trois etats separement et attribue chaque ecart.

METHODE
-------
Donnees figees et auditees (empreinte dans donnees/MANIFESTE.txt), chassis
L4.31 (gardien 2,50 %, breakeven 5 %, allocation deconcentree L11, repli
conditionnel 1,25 ATR / 5 barres / force 1,00), simulateur FTMO v2 : plancher
au SOLDE de minuit, aucun challenge jete, jours de trading comptes sur les
OUVERTURES, departs a plat, R13 actif.

    python banc_L13.py
"""
import io
import json
import os
import sys
import time
import types

import numpy as np

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
VUS_L12 = {"BTC EMA", "BTC Cassure", "Petrole"}     # les 3 magics codes en dur

# allocation deconcentree L11 : BTC cassure 1,15 %, le reste vers or/Nasdaq
ALLOC = {"Or": 0.0102, "Nasdaq": 0.0102, "Petrole": 0.0169,
         "BTC Cassure": 0.0115, "BTC EMA": 0.0113}
GARDE, BE = 0.025, 0.05
REPLI = dict(k_atr=1.25, fenetre=5, seuil_force=1.00)
CAP = 2


# -------------------------------------------------------- chassis (plafond)
A_OUVERTS = "        ouverts = sum(1 for s in sl if s.pos is not None)"
N_OUVERTS = "        ouverts = sum(1 for s in sl if s.pos is not None and s.nom in VUS)"
A_CORR = '            if MH.FAM[s.nom] == "mi" and "mi" in familles and cap_mi: continue'
N_CORR = "            if False: continue   # L12 reelle : garde-fou de correlation MORT"
A_INCR = "                ouverts += 1; familles.add(MH.FAM[s.nom])"
N_INCR = ("                ouverts += (1 if s.nom in VUS else 0)"
          "; familles.add(MH.FAM[s.nom])")
A_INJECT = "src = src.replace('if t >= pd.Timestamp(\"2015-08-21\")]',"


def charger(vus_3_magics=False):
    """Charge le chassis. `vus_3_magics` reproduit le plafond CASSE de L12."""
    src = io.open(os.path.join(D, "tests_comite_B.py"),
                  encoding="utf-8").read().split("# ============ 5.")[0]
    if vus_3_magics:
        bloc = ""
        for a, b in ((A_OUVERTS, N_OUVERTS), (A_CORR, N_CORR), (A_INCR, N_INCR)):
            bloc += ("src2 = src.replace(%r, %r)\n"
                     "assert src2 != src, 'ANCRE INTROUVABLE : %s'\nsrc = src2\n"
                     % (a, b, a.strip()[:34]))
        assert A_INJECT in src, "ANCRE D'INJECTION INTROUVABLE"
        src = src.replace(A_INJECT, bloc + A_INJECT)
    ns0 = {"__file__": os.path.join(D, "tests_comite_B.py")}
    s = sys.stdout
    sys.stdout = io.StringIO()
    exec(src, ns0)
    sys.stdout = s
    if vus_3_magics:
        ns0["ns"]["VUS"] = set(VUS_L12)
    return ns0


# -------------------------------------------------------------- correctifs
def ancre_roulante(s):
    """C1 : le stop suit l'EXTREME atteint, pile pleine ou non.

    On ne reecrit pas `gerer_pyr_max` : on le laisse faire sa gestion L12
    complete (ancre gelee incluse), puis on remonte le stop avec la bonne
    ancre, EN FIN DE BARRE. C'est exactement l'ordre du robot : le stop pose a
    la barre i n'est teste qu'a la barre i+1, donc aucun regard vers l'avenir.
    Traduction fidele de :
        if(hautDecision > ancreExtreme) ancreExtreme = hautDecision;
        double ancre = MathMax(ancreExtreme, dernier);
        stopTurtle = ancre - StopSousDerniereUniteATR * atrVal;
    """
    g0 = s.gerer

    def gerer(t):
        g0(t)
        p = s.pos
        if p is None:
            return
        i = s.idx.get(t)
        if i is None:
            return
        v = s.prov(i)
        if v is None:
            return
        atr = v[0]
        p["ancre"] = max(p.get("ancre", p["e"]), s.H[i])
        if p["unites"] > 1 and atr > 0:
            niveau = max(p["ancre"], p["dernier"]) - 2.0 * atr
            if niveau > p["s"]:
                p["s"] = niveau

    s.gerer = gerer
    return s


def ancre_pile_pleine(s, K):
    """VARIANTE CIBLEE : l'ancre ne roule QUE lorsque la pile est pleine.

    C'est le correctif que le comite du 21 aout avait retenu et que L13 n'a
    pas implemente. Le defaut observe en direct etait precis : a 4/4 unites,
    plus aucune unite n'est ajoutee, donc `dernier` gele DEFINITIVEMENT. Tant
    que la pile grossit encore, `dernier` avance a chaque ajout et le stop
    suit deja. Cette variante ne touche donc que l'etat gele, avec l'ancre
    prise sur le plus-haut depuis la 4e unite (Grok K=1,8-2,2 ; Gemini 2,5).

    A comparer a C1 de L13, qui ancre sur le plus-haut depuis l'ENTREE des
    l'unite 2 : c'est le "chandelier large" que le comite avait deja rejete
    a K=3/4/5, applique ici encore plus serre (K=2).
    """
    plein = s.pyr_max                  # 4, lu avant toute alteration passagere
    g0 = s.gerer

    def gerer(t):
        g0(t)
        p = s.pos
        if p is None:
            return
        i = s.idx.get(t)
        if i is None:
            return
        v = s.prov(i)
        if v is None or v[0] <= 0 or p["unites"] < plein:
            return
        p["ancre4"] = max(p.get("ancre4", p["dernier"]), s.H[i])
        niveau = p["ancre4"] - K * v[0]
        if niveau > p["s"]:
            p["s"] = niveau

    s.gerer = gerer
    return s


def gate_pyramide(s, sleeves, vus):
    """C2, second effet : le plafond d'ecurie bloque aussi les AJOUTS.

    Ligne 875 du .mq5 : `ComptePositionsEcurie() < MaxPositionsEcurie`. Comme
    le compte inclut la pile courante, une unite ne s'ajoute que si ce robot
    est le SEUL de l'ecurie a etre en position. Le moteur Python n'a jamais eu
    ce test. On l'obtient sans reecrire la boucle d'ajout, en abaissant
    `pyr_max` au nombre d'unites deja detenues, le temps de la barre.
    """
    g0 = s.gerer

    def gerer(t):
        vrai = s.pyr_max
        if s.pos is not None:
            n = sum(1 for o in sleeves if o.pos is not None and o.nom in vus)
            if n >= CAP:
                s.pyr_max = s.pos["unites"]
        try:
            g0(t)
        finally:
            s.pyr_max = vrai

    s.gerer = gerer
    return s


def mesurer_giveback(s):
    """Enregistre, pour chaque trade, (profit flottant MAXIMAL, profit final).

    S'applique APRES instrumenter2, qui tient `_run` (cumul du P&L de la
    manche) et `_cum0` (sa valeur a l'ouverture). Le flottant courant vaut donc
    `_run - _cum0`, en fraction du compte.
    """
    s.gb = []
    s._pic = 0.0
    g0, o0, c0 = s.gerer, s.ouvrir, s._clore

    def pic():
        s._pic = max(s._pic, s._run - s._cum0)

    def gerer(t):
        g0(t)
        if s.pos is not None:
            pic()

    def ouvrir(t, *a, **k):
        r = o0(t, *a, **k)
        if r and s.pos is not None:
            s._pic = 0.0
            pic()
        return r

    def _clore(t, prix):
        c0(t, prix)
        s.gb.append((s._pic, s._run - s._cum0))
        s._pic = 0.0

    s.gerer, s.ouvrir, s._clore = gerer, ouvrir, _clore
    return s


# ------------------------------------------------------------------ series
def serie(ns0, debut, fin, ancre, vus):
    """Retourne (cagr, dd, vm, vo, vf, trades, giveback).

    `ancre` : None (gelee, comme L12), "entree" (C1 de L13), ou un nombre K
    (variante ciblee : ancre roulante seulement une fois la pile pleine).
    """
    ns, f_or, fab = ns0["ns"], ns0["f_or"], ns0["fab_l431"]
    boite = []

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
                if vus is not None:
                    gate_pyramide(s, sl, vus)
                if ancre == "entree":
                    ancre_roulante(s)
                elif ancre is not None:
                    ancre_pile_pleine(s, ancre)
        for s in sl:
            mesurer_giveback(instrumenter2(s))
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

    gb = [x for s in boite if s.nom in PYR for x in s.gb]
    pics = sum(p for p, _ in gb if p > 0)
    rendu = sum(p - q for p, q in gb if p > 0)
    giveback = dict(trades_pyr=len(gb), pic_total=100 * pics,
                    rendu_total=100 * rendu,
                    part=(100 * rendu / pics if pics > 0 else 0.0))
    return (r[0], r[2], tj.values.astype(float), vo, vf,
            sum(s.trades for s in boite), giveback)


# ----------------------------------------------------------------- configs
# (etiquette, ancre, magics vus par le plafond, plafond sur les ajouts de
#  pyramide ; None = aucun, comme le moteur Python d'origine)
#   ancre : None = gelee (L12) | "entree" = C1 de L13 | K = ancre roulante
#           seulement une fois la pile pleine, a K x ATR sous le plus-haut
CONFIGS = [
    ("L12 telle que PUBLIEE (moteur tel quel)",   None, "5", None),
    ("L12 telle que DEPLOYEE (3 magics)",         None, "3", VUS_L12),
    ("  + ancre roulante seule (C1)",         "entree", "3", VUS_L12),
    ("  + plafonds repares seuls (C2/C3)",        None, "5", "TOUS"),
    ("L13 (C1 + C2 + C3)",                   "entree", "5", "TOUS"),
    ("VARIANTE pile pleine K=1,8 + C2/C3",         1.8, "5", "TOUS"),
    ("VARIANTE pile pleine K=2,0 + C2/C3",         2.0, "5", "TOUS"),
    ("VARIANTE pile pleine K=2,5 + C2/C3",         2.5, "5", "TOUS"),
]
FENETRES = (("10 ans ", "2015-08-21", "2026-12-31", 730),
            ("2021-26", "2021-01-01", "2026-08-20", 730))
FTMO = dict(cibles=(0.10, 0.05), perte_jour=0.05, perte_totale=0.10,
            jours_min=4)
TURBO = (1.15, 0.04)

ENTETE = ("%-42s %6s %-13s %5s %6s %6s | %6s %7s %6s %4s"
          % ("configuration", "reuss", "  [IC95]", "med", "esp", "<=60j",
             "CAGR", "creux", "trades", "ind"))


def main():
    emp = CD.rediriger_vers_donnees()
    print("=" * 122)
    print("BANC L13 - que valent vraiment les correctifs du 22 aout 2026 ?")
    print(emp)
    print("chassis L4.31 | gardien 2,50 % | breakeven 5 % | alloc deconcentree "
          "L11 | repli conditionnel 1,25/5/1,00")
    print("simulateur FTMO v2 (plancher au solde de minuit) | departs a plat | "
          "R13 actif | 2-Step 10 % + 5 %")
    print("=" * 122)

    chassis = {}
    S, sortie = {}, {}
    for etq, ancre, vus_cle, vus in CONFIGS:
        if vus_cle not in chassis:
            chassis[vus_cle] = charger(vus_3_magics=(vus_cle == "3"))
        v = None if vus is None else (set(ALLOC) if vus == "TOUS" else vus)
        for lib, deb, fin, _ in FENETRES:
            t0 = time.time()
            S[(etq, lib)] = serie(chassis[vus_cle], deb, fin, ancre, v)
            print("   . %-42s %s en %4.1f s" % (etq, lib, time.time() - t0),
                  file=sys.stderr)

    for turbo in (None, TURBO):
        for lib, deb, fin, piste in FENETRES:
            print()
            print("-" * 122)
            print("FENETRE %s (%s -> %s)%s" % (
                lib, deb, fin,
                "" if turbo is None else
                "   [+ turbo x%.2f sous coussin %.0f %% - BORNE, pas mesure]"
                % (turbo[0], 100 * turbo[1])))
            print("-" * 122)
            print(ENTETE)
            for etq, _, _, _ in CONFIGS:
                cagr, dd, vm, vo, vf, tr, gb = S[(etq, lib)]
                r = V2.simuler(vm, vf, vo, piste_min=piste, r13=True,
                               regle="ftmo", gardien=0.010, turbo=turbo, **FTMO)
                print("%-42s %5.1f%% [%4.1f-%5.1f] %4.0fj %5.0fj %5.1f%% |"
                      " %+5.1f%% %6.1f%% %6d %4d"
                      % (etq, r["reussite"], r["ic95"][0], r["ic95"][1],
                         r["duree_med"], r["esperance"], r["p60"],
                         cagr, dd, tr, r["n_independants"]))
                cle = "%s%s" % (lib, "" if turbo is None else " +turbo")
                sortie.setdefault(cle, []).append(
                    dict(config=etq, reussite=r["reussite"], ic95=r["ic95"],
                         med=r["duree_med"], p10=r["duree_p10"], p45=r["p45"],
                         p60=r["p60"], esp=r["esperance"], cagr=cagr, dd=dd,
                         trades=tr, morts_jour=r["morts_jour"],
                         morts_totale=r["morts_totale"],
                         non_resolus=r["non_resolus"],
                         n_departs=r["n_departs"],
                         n_independants=r["n_independants"], giveback=gb))

    print()
    print("RAPPEL : 'ind' = nombre de challenges REELLEMENT independants. Un")
    print("ecart de reussite dont les IC95 se recouvrent ne veut RIEN dire.")
    print("Comparer d'abord la DUREE et le CAGR, mesures sur toute la serie.")

    print()
    print("-" * 122)
    print("GIVE-BACK DES PYRAMIDES - profit flottant maximal atteint, puis rendu")
    print("-" * 122)
    print("%-42s %8s %11s %11s %8s"
          % ("configuration", "trades", "pic cumule", "rendu", "part"))
    for lib, _, _, _ in FENETRES:
        print("  fenetre %s" % lib)
        for etq, _, _, _ in CONFIGS:
            gb = S[(etq, lib)][6]
            print("%-42s %8d %9.1f %% %9.1f %% %6.1f %%"
                  % ("    " + etq.strip(), gb["trades_pyr"], gb["pic_total"],
                     gb["rendu_total"], gb["part"]))

    with io.open(os.path.join(D, "resultats_banc_L13.json"), "w",
                 encoding="utf-8") as fh:
        fh.write(json.dumps(sortie, indent=1, ensure_ascii=False))
    print()
    print("-> resultats_banc_L13.json")


if __name__ == "__main__":
    main()
