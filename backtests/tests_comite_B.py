# -*- coding: utf-8 -*-
"""TESTS DU COMITE, partie B (L4.31, mode ON, H4 10 ans) :
5. WALK-FORWARD ROULANT : cadences re-choisies sur 3 ans, testees sur
   l'annee suivante, fenetre glissante 2019-2026 ; serie composite OOS.
6. VOISINS fib/RSI de l'or et du Nasdaq (un parametre a la fois).
7. CHANDELIER : plafonner le give-back des pyramides (stop >= plus-haut
   depuis l'entree - K x ATR journalier), K = 3/4/5.
8. ESPACEMENT de pyramide 0,5 -> 0,75 / 1,0 ATR (suggestion Grok)."""
import os, pandas as pd, numpy as np
D = os.path.dirname(os.path.abspath(__file__))
import moteur_h4 as MH
BTC_H1 = pd.read_csv(os.path.join(D, "d10h1_btc.csv"), index_col=0,
                     parse_dates=True)[["o","h","l","c"]].astype(float)

NS2 = {"__file__": os.path.join(D, "valide_candidats_h4.py")}
exec(open(os.path.join(D, "valide_candidats_h4.py"), encoding="utf-8").read()
     .split("RISQUES =")[0], NS2)

src = open(os.path.join(D, "test_l4_macro.py"), encoding="utf-8").read().split('print()')[0]
src = src.replace('if t >= pd.Timestamp("2015-08-21")]',
                  'if t >= pd.Timestamp(DEBUT) and t <= pd.Timestamp(FIN)]')
src = src.replace("    return cagr, sh, dd, (morts/n*100 if n else 0), c1, c2",
                  "    return cagr, sh, dd, (morts/n*100 if n else 0), c1, c2, tj")
ns = {"__file__": os.path.join(D, "test_l4_macro.py"), "DEBUT": "2015-08-21", "FIN": "2026-12-31"}
exec(src, ns)
ORIG = ns["sleeves_l4"]
dxy = ns["dxy"]
FORT = set(dxy.index[(dxy > dxy.ewm(span=200, adjust=False).mean())].date)
f_or = lambda n, j: n == "Or" and j in FORT

def porte_d1(x):
    sig0 = x.signal
    def sig(t, x=x, sig0=sig0):
        i = x.idx.get(t)
        if i is None or not x.NEWDAY[i]: return None
        return sig0(t)
    x.signal = sig
    return x

def btc_h1(nom, pyr_max=4):
    if nom == "BTC EMA":
        return MH.EmaBTCH4("BTC EMA", BTC_H1, 0.015, 0.0004, -0.000833/4, 1.0,
                           jimmy=True, retrace=0.25, tpj=2.0)
    s = MH.DonchH4("BTC Cassure", BTC_H1, 0.015, 0.0004, -0.000833/4, 1.0)
    s.pyr_max = pyr_max
    s.gerer = NS2["gerer_pyr_max"].__get__(s); s.ouvrir = MH.ouvrir_pyr.__get__(s)
    return s

def tampon(s, pct=0.0025):
    sig0 = s.signal
    def sig(t, s=s, sig0=sig0):
        r = sig0(t)
        if r is None: return None
        k = s.KPREV[s.idx.get(t)]
        if r["entree"] <= s.H20J[k] * (1 + pct): return None
        return r
    s.signal = sig
    return s

def chandelier(s, K):
    """stop plancher : plus-haut depuis l'entree - K x ATR journalier."""
    ouvrir0, gerer0 = s.ouvrir, s.gerer
    def ouvrir(t, **kw):
        ok = ouvrir0(t, **kw)
        if ok: s._hh = kw.get("entree", 0)
        return ok
    def gerer(t):
        i = s.idx.get(t)
        if i is not None and s.pos is not None:
            s._hh = max(getattr(s, "_hh", 0), s.H[i])
            v = s.prov(i)
            if v is not None:
                plancher = s._hh - K * v[0]
                if plancher > s.pos["s"]: s.pos["s"] = plancher
        gerer0(t)
    s.ouvrir, s.gerer = ouvrir, gerer
    return s

def espace(s, pas):
    """espacement de pyramide personnalise (defaut 0,5 ATR)."""
    ouvrir0 = s.ouvrir
    def ouvrir(t, **kw):
        ok = ouvrir0(t, **kw)
        if ok and s.pos is not None and "prochain" in s.pos:
            i = s.idx.get(t); v = s.prov(i)
            if v: s.pos["prochain"] = kw.get("entree", 0) + pas * v[0]
        return ok
    s.ouvrir = ouvrir
    # le pas des ajouts suivants reste 0,5 dans gerer_pyr_max : approximation
    # honnete (premier ecart seulement) -- suffisant pour juger la direction.
    return s

def fab_l431(cadences=None, mods=None, or_params=None, nq_params=None):
    cadences = cadences or {"BTC Cassure": "H1", "BTC EMA": "D1", "Petrole": "H4"}
    def f():
        sl = []
        for x in ORIG():
            if hasattr(x, "pyr_max"): x.pyr_max = 4
            cad = cadences.get(x.nom, "H4")
            if x.nom == "Or" and or_params:
                x = MH.FibH4("Or", MH.GC, 0.02, 0.0001, -0.000273, 1.4, jimmy=True,
                             retrace=0.25, **or_params)
            elif x.nom == "Nasdaq" and nq_params:
                x = MH.FibH4("Nasdaq", MH.NQ, 0.015, 0.00003, -0.000213, 1.4, jimmy=True,
                             retrace=0.5, **nq_params)
            if x.nom.startswith("BTC") and cad == "H1":
                x = btc_h1(x.nom)
            elif cad == "D1":
                x = porte_d1(x)
            if x.nom in ("BTC Cassure", "Petrole"):
                tampon(x)
                if mods: mods(x)
            sl.append(x)
        return sl
    return f

def run(debut, fin, **kw):
    ns["DEBUT"], ns["FIN"] = debut, fin
    ns["sleeves_l4"] = fab_l431(**kw)
    return ns["sim_h4"](interdit=f_or)

OR0 = dict(tpj=1.5, lookback=10, fib=(0.2, 0.8), pull=55, mult=3.0, tpr=2.0)
NQ0 = dict(tpj=1.0, lookback=7, fib=(0.1, 0.9), pull=60, mult=2.0, tpr=2.0)

# ============ 5. WALK-FORWARD ROULANT ============
print("### 5. WALK-FORWARD ROULANT (opt 3 ans -> test 1 an) ###")
BASE_C = {"BTC Cassure": "H4", "BTC EMA": "H1", "Petrole": "D1"}   # robots d'origine
CANDS = [("BTC Cassure", "H1"), ("BTC Cassure", "D1"), ("BTC EMA", "H4"),
         ("BTC EMA", "D1"), ("Petrole", "H4")]
oos = []
for an_test in range(2019, 2027):
    d_opt, f_opt = "%d-01-01" % (an_test-3), "%d-12-31" % (an_test-1)
    d_tst, f_tst = "%d-01-01" % an_test, "%d-12-31" % an_test
    base = run(d_opt, f_opt, cadences=dict(BASE_C))[0]
    choix = dict(BASE_C)
    for nom, cad in CANDS:
        c2 = dict(BASE_C); c2[nom] = cad
        if run(d_opt, f_opt, cadences=c2)[0] > base + 0.5:
            if choix.get(nom) == BASE_C[nom]: choix[nom] = cad
            else:
                c3 = dict(choix); c3[nom] = cad
                if run(d_opt, f_opt, cadences=c3)[0] > run(d_opt, f_opt, cadences=choix)[0]:
                    choix[nom] = cad
    r = run(d_tst, f_tst, cadences=choix)
    oos.append(r[6])
    diffs = {k: v for k, v in choix.items() if v != BASE_C[k]}
    print("  %d : choix %s -> OOS %+.1f %%" % (an_test, diffs, r[0]))
serie = pd.concat(oos).sort_index()
ans = (serie.index[-1]-serie.index[0]).days/365.25
cagr = ((1+serie).prod()**(1/ans)-1)*100
vals = serie.values; morts = reussis = 0
for i0 in range(0, len(vals)-40, 21):
    e2 = 1.0
    for jx in range(i0, len(vals)):
        e2 *= (1+vals[jx])
        if e2 <= 0.92: morts += 1; break
        if e2 >= 1.10: reussis += 1; break
nn = morts + reussis
print("  COMPOSITE hors echantillon 2019-2026 : CAGR %+.1f %% | reussite %.0f %%"
      % (cagr, 100 - (morts/nn*100 if nn else 0)))

# ============ 6. VOISINS FIB/RSI ============
print()
print("### 6. VOISINS DES PARAMETRES OR ET NASDAQ (un a la fois) ###")
ref = run("2015-08-21", "2026-12-31")[0]
print("  reference L4.31 : %+.1f %%" % ref)
for etiquette, cible, base_p, cle, valeurs in (
        ("Or RSI seuil", "or", OR0, "pull", [50, 60]),
        ("Or zone fib", "or", OR0, "fib", [(0.15, 0.85), (0.25, 0.75)]),
        ("Or stop xATR", "or", OR0, "mult", [2.5, 3.5]),
        ("Or TP xR", "or", OR0, "tpj", [1.25, 1.75]),
        ("Nasdaq RSI seuil", "nq", NQ0, "pull", [55, 65]),
        ("Nasdaq TP xR", "nq", NQ0, "tpj", [0.75, 1.25]),
        ("Nasdaq stop xATR", "nq", NQ0, "mult", [1.5, 2.5])):
    sortie = "  %-18s :" % etiquette
    for v in valeurs:
        p = dict(base_p); p[cle] = v
        kw = {"or_params": p} if cible == "or" else {"nq_params": p}
        c = run("2015-08-21", "2026-12-31", **kw)[0]
        sortie += "  %s -> %+.1f %%" % (str(v), c)
    print(sortie)

# ============ 7. CHANDELIER (plafond de give-back) ============
print()
print("### 7. CHANDELIER sur les pyramides (stop >= plus-haut - K x ATR) ###")
for K in (3, 4, 5):
    r = run("2015-08-21", "2026-12-31", mods=lambda s, K=K: chandelier(s, K))
    print("  K=%d : CAGR %+.1f %% | reussite %.0f %% | DD %+.1f %%" % (K, r[0], 100-r[3], r[2]))

# ============ 8. ESPACEMENT PYRAMIDE ============
print()
print("### 8. ESPACEMENT premiere unite 0,5 -> 0,75 / 1,0 ATR (Grok) ###")
for pas in (0.75, 1.0):
    r = run("2015-08-21", "2026-12-31", mods=lambda s, p=pas: espace(s, p))
    print("  pas=%.2f ATR : CAGR %+.1f %% | reussite %.0f %%" % (pas, r[0], 100-r[3]))

print()
print("### CONTROLE : reconstruction avec parametres IDENTIQUES ###")
print("  or  identique  : %+.1f %% (ref 47.0)" % run("2015-08-21", "2026-12-31", or_params=dict(OR0))[0])
print("  nas identique  : %+.1f %% (ref 47.0)" % run("2015-08-21", "2026-12-31", nq_params=dict(NQ0))[0])
