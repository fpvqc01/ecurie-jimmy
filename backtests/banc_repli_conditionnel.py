# -*- coding: utf-8 -*-
"""REPLI CONDITIONNEL : « comprendre que le repli est incoherent avec la
macro actuelle » (question de Jimmy, 21 aout).

CE QUE LE PREMIER BANC A MONTRE. Attendre un repli de 0,50 ou 1,00 ATR fait
s'effondrer le rendement (+29,5 % -> +16,0 % puis +12,5 %) et fait perdre des
trades (272 -> 257 -> 225). Raison : dans une vraie tendance, le repli NE
VIENT JAMAIS. On reste sur le quai pendant les plus gros mouvements, ceux qui
font tout le rendement du suivi de tendance.

L'IDEE DE JIMMY. Ne pas attendre le repli quand le regime ne s'y prete pas.
On mesure la FORCE de la tendance au moment du signal :
      force = (prix - EMA 50) / ATR
c'est-a-dire de combien d'ATR le prix est au-dessus de sa moyenne moyenne.

  force >= seuil  -> tendance forte : on achete la cassure TOUT DE SUITE,
                     parce qu'attendre un repli n'a pas de sens.
  force <  seuil  -> tendance molle : on attend le repli, parce que la
                     cassure a de bonnes chances d'etre un faux depart.

C'est exactement « le repli est incoherent avec la macro actuelle », traduit
en regle testable et decidee sur la barre en cours, sans regarder l'avenir."""
import os, sys
import numpy as np, pandas as pd
D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, D)
import banc_L8 as B
import banc_repli as R

CIBLES = R.CIBLES

def repli_conditionnel(s, k_atr, fenetre, seuil_force):
    sig0 = s.signal
    s._arme = None
    def sig(t):
        i = s.idx.get(t)
        if i is None: return None
        v = s.prov(i)
        if v is None: return None
        a, rsi, rsip, e20, e50, e20p, e50p, h20, b10, c, k = v
        if s._arme is not None:
            niveau, reste, base = s._arme
            if s.L[i] <= niveau:
                s._arme = None
                d = dict(base); d["entree"] = niveau
                if d["entree"] <= d["stop"]: return None
                return d
            if reste <= 0: s._arme = None
            else:
                s._arme = (niveau, reste - 1, base); return None
        r = sig0(t)
        if r is None or not (a > 0): return None
        force = (c - e50) / a if (e50 == e50 and a > 0) else 0.0
        if force >= seuil_force:
            return r                               # tendance forte : on prend la cassure
        s._arme = (r["entree"] - k_atr * a, fenetre, r)
        return None                                # tendance molle : on attend le repli
    s.signal = sig
    return s

FEN = R.FEN
VAR = [("reference (achat de la cassure)", None),
       ("repli 0,50 ATR TOUJOURS",
        lambda sl: [R.repli(s,0.50,5) for s in sl if s.nom in CIBLES])]
for seuil in (1.0, 2.0, 3.0):
    VAR.append(("repli 0,50 sauf si force >= %.0f ATR" % seuil,
                (lambda z: (lambda sl: [repli_conditionnel(s,0.50,5,z) for s in sl if s.nom in CIBLES]))(seuil)))
for seuil in (1.0, 2.0):
    VAR.append(("repli 1,00 sauf si force >= %.0f ATR" % seuil,
                (lambda z: (lambda sl: [repli_conditionnel(s,1.00,5,z) for s in sl if s.nom in CIBLES]))(seuil)))
VAR.append(("repli 0,25 + max 2 pyr/jour",
            lambda sl: [R.max_pyr_jour(R.repli(s,0.25,5),2) for s in sl if s.nom in CIBLES]))
VAR.append(("repli 0,50 si force<2 + max 2 pyr/j",
            lambda sl: [R.max_pyr_jour(repli_conditionnel(s,0.50,5,2.0),2) for s in sl if s.nom in CIBLES]))

print("=== REPLI CONDITIONNEL A LA FORCE DE LA TENDANCE (chassis L6 + R13) ===")
print("%-38s | %-32s | %s" % ("", "10 ANS", "2021-2026"))
print("%-38s | %6s %7s %8s %6s %7s | %8s %6s"
      % ("mecanisme", "trades", "CAGR", "reussite", "duree", "DD", "reussite", "duree"))
print("-" * 112)
for etq, meca in VAR:
    l = "%-38s |" % etq
    for k, (e, d0, f0) in enumerate(FEN):
        tr, cagr, o, m, dd = R.mesure(0.025, meca, 1.00, None, d0, f0)
        if k == 0: l += " %6d %+6.1f %% %6.0f %% %4.0f j %+6.1f %% |" % (tr, cagr, o, m, dd)
        else:      l += " %6.0f %% %4.0f j" % (o, m)
    print(l)
