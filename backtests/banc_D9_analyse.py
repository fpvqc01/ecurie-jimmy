# -*- coding: utf-8 -*-
"""Chassis du banc D9 (24 nov 2026), reutilise par banc_D10.py.

Reprend banc_L13.py (coupe de banc_L8.py ajustee : le banc ne tourne plus
au chargement depuis le 30 aout) et SIM_FTMO_V2 sur les donnees figees.

`charger(garde, caps_morts)` :
  caps_morts=False -> plafond d'ecurie, correlation et gate pyramide actifs
  caps_morts=True  -> aucun magic de l'ecurie n'est vu (le defaut D9 :
                      les listes en dur sont encore celles de L13)

Lancer ce fichier seul refait la matrice L13 / D8 / D9. La comparaison
D9 tel que code vs D10 est dans banc_D10.py."""
import io, os, sys, time, json
D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, D)
import types
_src = io.open(os.path.join(D, "banc_L13.py"), encoding="utf-8").read()
# banc_L8.py a ete protege par if __name__ le 30 aout : l'ancienne coupe n'existe plus
_src = _src.replace('\'\\nprint("=== BANC L8\'', '\'\\nif __name__ == "__main__":\'')
L = types.ModuleType("banc_L13_d9"); L.__file__ = os.path.join(D, "banc_L13.py")
exec(compile(_src, L.__file__, "exec"), L.__dict__)

LIGNE_GARDE = "sl = sleeves_l4(); garde = -0.025"

def charger(garde, caps_morts):
    src = io.open(os.path.join(D, "tests_comite_B.py"), encoding="utf-8").read().split("# ============ 5.")[0]
    bloc = ""
    paires = []
    if abs(garde - 0.025) > 1e-9:
        paires.append((LIGNE_GARDE, "sl = sleeves_l4(); garde = -%.5f" % garde))
    if caps_morts:
        paires += [(L.A_OUVERTS, L.N_OUVERTS), (L.A_CORR, L.N_CORR), (L.A_INCR, L.N_INCR)]
    for a, b in paires:
        bloc += ("src2 = src.replace(%r, %r)\nassert src2 != src, 'ANCRE INTROUVABLE'\nsrc = src2\n" % (a, b))
    if bloc:
        src = src.replace(L.A_INJECT, bloc + L.A_INJECT)
    ns0 = {"__file__": os.path.join(D, "tests_comite_B.py")}
    s = sys.stdout; sys.stdout = io.StringIO()
    exec(src, ns0)
    sys.stdout = s
    if caps_morts:
        ns0["ns"]["VUS"] = set()      # D9 : aucune de ses propres magics n'est vue
    return ns0

# (etiquette, gardien robot, breakeven, caps_morts, turbo)
CONFIGS = [
    ("L13 ref (g2,50 BE5 turbo1,15/4%)", 0.025, 0.05, False, (1.15, 0.04)),
    ("D8 voulu (g1,25 sansBE, sans turbo)", 0.0125, None, False, None),
    ("D9 voulu (g1,25 sansBE turbo1,15/6%)", 0.0125, None, False, (1.15, 0.06)),
    ("D9 tel que code (plafonds morts)", 0.0125, None, True, (1.15, 0.06)),
    ("D8 tel que code (plafonds morts)", 0.0125, None, True, None),
]

def main():
    print(L.CD.rediriger_vers_donnees())
    out = {}
    for etq, garde, be, morts, turbo in CONFIGS:
        ns0 = charger(garde, morts)
        L.BE = be if be else 0.0
        vus = set() if morts else set(L.ALLOC)
        for lib, deb, fin, piste in L.FENETRES:
            t0 = time.time()
            # breakeven : banc_L13.serie applique toujours B.breakeven(s, BE) ; BE=0 -> on le neutralise
            if be is None:
                orig = L.B.breakeven; L.B.breakeven = lambda s, seuil: s
            try:
                cagr, dd, vm, vo, vf, tr, gb = L.serie(ns0, deb, fin, "entree", vus)
            finally:
                if be is None: L.B.breakeven = orig
            r = L.V2.simuler(vm, vf, vo, piste_min=piste, r13=True, regle="ftmo",
                             gardien=0.010, turbo=turbo, **L.FTMO)
            ligne = dict(cagr=cagr, dd=dd, trades=tr, reussite=r["reussite"], ic95=r["ic95"],
                         duree_med=r["duree_med"], p60=r["p60"], esperance=r["esperance"],
                         morts_jour=r["morts_jour"], morts_totale=r["morts_totale"],
                         non_resolus=r["non_resolus"], ind=r["n_independants"], giveback_part=gb["part"])
            out["%s | %s" % (etq, lib)] = ligne
            print("%-40s %s CAGR %+6.1f%% creux %6.1f%% trades %4d | reussite %5.1f%% IC[%4.1f-%5.1f] med %4.0fj <=60j %5.1f%% mortsJ %s mortsT %s ind %d (%.0fs)"
                  % (etq, lib, cagr, dd, tr, r["reussite"], r["ic95"][0], r["ic95"][1], r["duree_med"],
                     r["p60"], r["morts_jour"], r["morts_totale"], r["n_independants"], time.time()-t0), flush=True)
    json.dump(out, open(os.path.join(D, "resultats_banc_D9.json"), "w"), indent=1, default=float)

if __name__ == "__main__":
    main()
