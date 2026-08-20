# -*- coding: utf-8 -*-
"""Validation H4 (2 ans, fenetre commune) des 3 candidats du scan 1d :
  C1 = R1 sans corr (parite 1,5 plate, pyr 3)          [1d : +27,6 %, 8 %]
  C2 = R2 (or 1,5/nas 1,5/pet 1,0/btc 1,0, pyr 3)      [1d : +22,9 %, 0 %]
  C3 = R3 (or 2,0/nas 1,5/pet 1,0/btc 1,0, pyr 3)      [1d : +25,4 %, 5 %]
References : L3 et L3+."""
import pandas as pd, numpy as np
import moteur_h4 as M

def gerer_pyr_max(self, t):
    i = self.idx.get(t)
    if i is None: return
    self._maj_jour(i)
    if self.pos is None: return
    v = self.prov(i)
    if v is None: return
    a = v[0]; b10 = v[8]; c = v[9]
    p = self.pos
    l, h = self.L[i], self.H[i]
    if p.get("trail") and not np.isnan(b10) and b10 > p["s"]: p["s"] = b10
    if l <= p["s"]:
        self._clore(t, p["s"]); self.attente = None; return
    while p["unites"] < self.pyr_max and h >= p["prochain"]:
        prix = p["prochain"]
        n_add = min(p["n0"], 2.0 - p["n"])
        if n_add <= 0: break
        self.pnl[t] = self.pnl.get(t, 0) + n_add*(c-prix)/p["e"] - self.frais*n_add
        p["n"] += n_add; p["unites"] += 1; p["prochain"] += 0.5*a; p["dernier"] = prix
    if p.get("tp") and h >= p["tp"]:
        tp = p["tp"]; self._clore(t, tp)
        if self.jimmy: self.attente = tp
        return
    if p.get("be") and not p["be_fait"] and h >= p["be"]:
        if p["e"] > p["s"]: p["s"] = p["e"]
        p["be_fait"] = True
    if p.get("sortie_cloture") and self.sortie_cloture(v):
        self._clore(t, c); self.attente = None; return
    if p["unites"] > 1 and a > 0:
        tr2 = p["dernier"] - 2.0*a
        if tr2 > p["s"]: p["s"] = tr2
    self.pnl[t] = self.pnl.get(t, 0) + p["n"]*((c-p["prix"])/p["e"] + self.swap*self.fs/M.BPJ)
    p["prix"] = c

RISQUES = {
    "L3":  dict(Or=0.03,  Nasdaq=0.015, Petrole=0.0075, BTC=0.0075),
    "C1":  dict(Or=0.015, Nasdaq=0.015, Petrole=0.015,  BTC=0.015),
    "C2":  dict(Or=0.015, Nasdaq=0.015, Petrole=0.01,   BTC=0.01),
    "C3":  dict(Or=0.02,  Nasdaq=0.015, Petrole=0.01,   BTC=0.01),
}

def sim_p(nom_r, corr=False, throttle=None, pyr_max=3):
    R = RISQUES[nom_r]
    sleeves = [
        M.FibH4("Or", M.GC, R["Or"], 0.0001, -0.000273, 1.4, jimmy=True, retrace=0.25, tpj=1.5,
                lookback=10, fib=(0.2, 0.8), pull=55, mult=3.0, tpr=2.0),
        M.DonchH4("Petrole", M.CL, R["Petrole"], 0.00045, +0.000051, 1.4, saison=(1201, 531)),
        M.DonchH4("BTC Cassure", M.BTC, R["BTC"], 0.0004, -0.000833, 1.0),
        M.FibH4("Nasdaq", M.NQ, R["Nasdaq"], 0.00003, -0.000213, 1.4, jimmy=True, retrace=0.5,
                tpj=1.0, lookback=7, fib=(0.1, 0.9), pull=60, mult=2.0, tpr=2.0),
        M.EmaBTCH4("BTC EMA", M.BTC, R["BTC"], 0.0004, -0.000833, 1.0, jimmy=True,
                   retrace=0.25, tpj=2.0),
    ]
    for s in sleeves:
        if s.nom in ("BTC Cassure", "Petrole"):
            s.pyr_max = pyr_max
            s.gerer = gerer_pyr_max.__get__(s); s.ouvrir = M.ouvrir_pyr.__get__(s)
    garde = -0.025
    ts = [t for t in sorted(set().union(*[set(s.index) for s in sleeves]))
          if t >= pd.Timestamp("2024-08-21")]
    jour_pnl, jour_cour, jour_stop = 0.0, None, False
    eq, eq_jours, coupes = 1.0, [], 0
    for t in ts:
        j = t.date()
        if j != jour_cour:
            if jour_cour is not None:
                eq *= (1 + jour_pnl); eq_jours.append(eq)
            jour_cour, jour_pnl, jour_stop = j, 0.0, False
        avant = [s.pnl.get(t, 0) for s in sleeves]
        for s in sleeves: s.gerer(t)
        jour_pnl += sum(s.pnl.get(t, 0) - avant[q] for q, s in enumerate(sleeves))
        if jour_stop: continue
        if jour_pnl <= garde:
            av3 = [s.pnl.get(t, 0) for s in sleeves]
            for s in sleeves:
                if s.pos is not None:
                    i = s.idx.get(t)
                    if i is not None: s._clore(t, s.C[i])
                s.attente = None
            jour_pnl += sum(s.pnl.get(t, 0) - av3[q] for q, s in enumerate(sleeves))
            jour_stop = True; coupes += 1; continue
        fc = 1.0
        if throttle and len(eq_jours) > 20 and eq*(1+jour_pnl) < np.mean(eq_jours[-20:]): fc = throttle
        ouverts = sum(1 for s in sleeves if s.pos is not None)
        familles = {M.FAM[s.nom] for s in sleeves if s.pos is not None}
        for s in sleeves:
            if s.pos is not None or ouverts >= 2: continue
            if corr and M.FAM[s.nom] == "mi" and "mi" in familles: continue
            sig = s.signal(t)
            if sig is None: continue
            r0 = s.risque; s.risque = r0 * fc
            av2 = s.pnl.get(t, 0)
            ok = s.ouvrir(t, **sig)
            s.risque = r0
            if ok:
                jour_pnl += s.pnl.get(t, 0) - av2
                ouverts += 1; familles.add(M.FAM[s.nom])
    tot = {}
    for s in sleeves:
        for tt, vv in s.pnl.items():
            jj = tt.date(); tot[jj] = tot.get(jj, 0) + vv
    tous_jours = sorted({t.date() for t in ts})
    tj = pd.Series([tot.get(j, 0.0) for j in tous_jours], index=pd.DatetimeIndex(tous_jours))
    eqs = (1 + tj).cumprod(); ans = (tj.index[-1] - tj.index[0]).days / 365.25
    cagr = (eqs.iloc[-1] ** (1/ans) - 1) * 100
    sh = tj.mean()/tj.std()*np.sqrt(365) if tj.std() > 0 else 0
    dd = ((eqs/eqs.cummax()) - 1).min() * 100
    vals = tj.values; morts = reussis = 0
    for i0 in range(0, len(vals)-40, 21):
        e2 = 1.0
        for jx in range(i0, len(vals)):
            e2 *= (1+vals[jx])
            if e2 <= 0.92: morts += 1; break
            if e2 >= 1.10: reussis += 1; break
    n = morts + reussis
    return cagr, sh, dd, (morts/n*100 if n else 0)

print("=== VALIDATION H4, 2 ans (fenetre commune) ===")
print("  %-34s | %-7s | %-6s | %-7s | %s" % ("Config", "CAGR", "Sharpe", "MaxDD", "Morts"))
print("  " + "-" * 70)
for nom, args in (("L3 (reference)", dict(nom_r="L3")),
                  ("L3+ (reference)", dict(nom_r="C1", corr=True, throttle=0.75)),
                  ("C1 parite 1,5 plate", dict(nom_r="C1")),
                  ("C2 or1,5/pet-btc1,0", dict(nom_r="C2")),
                  ("C3 or2,0/pet-btc1,0", dict(nom_r="C3")),
                  ("C3 + throttle 0,75", dict(nom_r="C3", throttle=0.75)),
                  ("C2 pyramide 2 unites", dict(nom_r="C2", pyr_max=2))):
    c, s, d, m = sim_p(**args)
    print("  %-34s | %+6.1f%% | %6.2f | %+6.1f%% | %4.0f%%" % (nom, c, s, d, m))
