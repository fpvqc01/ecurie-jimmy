# -*- coding: utf-8 -*-
"""OPTIONS D'OPTIMISATION L4+ (20 aout, soir) — donnees propres, mode ON.
Chaque option testee seule contre la reference :
  B. un seul robot BTC en position a la fois (recommande par comite no 2)
  C. petrole : aucune NOUVELLE unite de pyramide le vendredi (garde OPEP+)
  D. petrole : pile reduite a 2 unites le vendredi apres 16 h
  E. plafond notionnel 1,0x equite par manche BTC (au lieu de 2,0x)
  F. EMA D1 : decision a 08:00 au lieu de minuit (rollover)
  G. risque BTC reduit 1,5 -> 1,25 % (les 2 robots BTC)
  H. risque BTC reduit 1,5 -> 1,0 %"""
import os, pandas as pd, numpy as np
D = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(D, "tests_comite_B.py"), encoding="utf-8").read().split("# ============ 5.")[0]
ns0 = {"__file__": os.path.join(D, "tests_comite_B.py")}
exec(src, ns0)
run, fab_l431, ns, f_or = ns0["run"], ns0["fab_l431"], ns0["ns"], ns0["f_or"]

def cap_btc(sl):
    btcs = [s for s in sl if s.nom.startswith("BTC")]
    for s in btcs:
        autres = [x for x in btcs if x is not s]
        sig0 = s.signal
        def sig(t, s=s, sig0=sig0, autres=autres):
            if any(x.pos is not None for x in autres): return None
            return sig0(t)
        s.signal = sig

def pas_ajout_vendredi(s):
    gerer0 = s.gerer
    def gerer(t, s=s, gerer0=gerer0):
        p = s.pos
        if p is not None and t.weekday() == 4 and "prochain" in p:
            sauv = p["prochain"]; p["prochain"] = float("inf")
            gerer0(t)
            if s.pos is p: p["prochain"] = sauv
        else:
            gerer0(t)
    s.gerer = gerer

def degonfle_vendredi(s, max_u=2):
    gerer0 = s.gerer
    def gerer(t, s=s, gerer0=gerer0):
        gerer0(t)
        p = s.pos
        if (p is not None and t.weekday() == 4 and t.hour >= 16
                and p.get("unites", 1) > max_u):
            cible = max_u * p["n0"]
            excedent = p["n"] - cible
            if excedent > 0:
                s.pnl[t] = s.pnl.get(t, 0) - s.frais * excedent
                p["n"] = cible; p["unites"] = max_u
    s.gerer = gerer

def plafond_notionnel(s, cap=1.0):
    gerer0 = s.gerer
    def gerer(t, s=s, gerer0=gerer0):
        gerer0(t)
        p = s.pos
        if p is not None and p["n"] > cap:
            excedent = p["n"] - cap
            s.pnl[t] = s.pnl.get(t, 0) - s.frais * excedent
            p["n"] = cap
    s.gerer = gerer

def ema_8h(s):
    sig_gated = s.signal
    sig0 = sig_gated.__defaults__[-1]   # signal d'origine sous porte_d1
    def sig(t, s=s, sig0=sig0):
        if t.hour != 8: return None
        return sig0(t)
    s.signal = sig

def fab_option(post):
    base = fab_l431()
    def f():
        sl = base()
        post(sl)
        return sl
    return f

def r_btc(sl, r):
    for s in sl:
        if s.nom.startswith("BTC"): s.risque = r

OPTIONS = [
    ("A. reference L4+", lambda sl: None),
    ("B. un seul BTC a la fois", cap_btc),
    ("C. petrole: pas d'ajout pyramide vendredi",
     lambda sl: [pas_ajout_vendredi(s) for s in sl if s.nom == "Petrole"]),
    ("D. petrole: pile reduite a 2 le vendredi 16h",
     lambda sl: [degonfle_vendredi(s) for s in sl if s.nom == "Petrole"]),
    ("E. plafond notionnel 1,0x sur manches BTC",
     lambda sl: [plafond_notionnel(s) for s in sl if s.nom.startswith("BTC")]),
    ("F. EMA D1 decision a 08:00",
     lambda sl: [ema_8h(s) for s in sl if s.nom == "BTC EMA"]),
    ("G. risque BTC 1,25 %", lambda sl: r_btc(sl, 0.0125)),
    ("H. risque BTC 1,0 %", lambda sl: r_btc(sl, 0.010)),
]

for etiquette, per in (("=== 10 ANS (2015-2026) ===", ("2015-08-21", "2026-12-31")),
                       ("=== 2021-2026 ===", ("2021-01-01", "2026-08-20"))):
    print(etiquette)
    for nom, post in OPTIONS:
        ns["DEBUT"], ns["FIN"] = per
        ns["sleeves_l4"] = fab_option(post)
        r = ns["sim_h4"](interdit=f_or)
        print("  %-46s : %+5.1f %% | reussite %3.0f %% | DD %+6.1f %% | Sharpe %.2f"
              % (nom, r[0], 100 - r[3], r[2], r[1]))
    print()
