# -*- coding: utf-8 -*-
"""LE BACKTEST H4 COMPLET SUR 10 ANS (21 aout) -- donnees Dukascopy
(or/petrole/Nasdaq H1->H4, 2015-2026) + Bitstamp/Binance (BTC 4h).
Memes generations que le test D1 10 ans : I2+, L3, L3+, L4 ON, L4 OFF.
Moteur H4 : gardien intrajournalier, stops barre par barre."""
import os, pandas as pd, numpy as np

D = os.path.dirname(os.path.abspath(__file__))
import moteur_h4 as MH

def charge(nom):
    df = pd.read_csv(os.path.join(D, "d10h4_%s.csv" % nom), index_col=0, parse_dates=True)
    return df[["o", "h", "l", "c"]].astype(float)

GC10, CL10, NQ10, BTC10 = charge("gc"), charge("cl"), charge("nq"), charge("btc")

def sleeves(gen):
    par = gen in ("L3+", "L4", "L4off")
    r_or = {"I2+": 0.03, "L3": 0.03, "L3+": 0.015, "L4": 0.02, "L4off": 0.02}[gen]
    r_pb = 0.015 if par else 0.0075
    sl = [
        MH.FibH4("Or", GC10, r_or, 0.0001, -0.000273, 1.4, jimmy=True, retrace=0.25, tpj=1.5,
                 lookback=10, fib=(0.2, 0.8), pull=55, mult=3.0, tpr=2.0),
        MH.DonchH4("Petrole", CL10, r_pb, 0.00045, +0.000051, 1.4, saison=(1201, 531)),
        MH.DonchH4("BTC Cassure", BTC10, r_pb, 0.0004, -0.000833, 1.0),
        MH.FibH4("Nasdaq", NQ10, 0.015, 0.00003, -0.000213, 1.4, jimmy=True, retrace=0.5,
                 tpj=1.0, lookback=7, fib=(0.1, 0.9), pull=60, mult=2.0, tpr=2.0),
        MH.EmaBTCH4("BTC EMA", BTC10, r_pb, 0.0004, -0.000833, 1.0, jimmy=True,
                    retrace=0.25, tpj=2.0),
    ]
    pyr = gen != "I2+"
    src = open(os.path.join(D, "valide_candidats_h4.py"), encoding="utf-8").read()
    ns = {"__file__": os.path.join(D, "valide_candidats_h4.py")}
    exec(src.split("RISQUES =")[0], ns)
    for s in sl:
        if pyr and s.nom in ("BTC Cassure", "Petrole"):
            s.pyr_max = 3
            s.gerer = ns["gerer_pyr_max"].__get__(s); s.ouvrir = MH.ouvrir_pyr.__get__(s)
    return sl

def sim10(gen):
    sl = sleeves(gen)
    garde = -0.035 if gen == "I2+" else -0.025
    corr = gen in ("L3+", "L4", "L4off")
    thr = 0.75 if gen in ("L3+", "L4") else None
    ts = [t for t in sorted(set().union(*[set(s.index) for s in sl]))
          if t >= pd.Timestamp("2015-08-21")]
    jour_pnl, jour_cour, jour_stop = 0.0, None, False
    eq, eq_jours, coupes = 1.0, [], 0
    for t in ts:
        j = t.date()
        if j != jour_cour:
            if jour_cour is not None: eq *= (1+jour_pnl); eq_jours.append(eq)
            jour_cour, jour_pnl, jour_stop = j, 0.0, False
        avant = [s.pnl.get(t, 0) for s in sl]
        for s in sl: s.gerer(t)
        jour_pnl += sum(s.pnl.get(t, 0)-avant[q] for q, s in enumerate(sl))
        if jour_stop: continue
        if jour_pnl <= garde:
            av3 = [s.pnl.get(t, 0) for s in sl]
            for s in sl:
                if s.pos is not None:
                    i = s.idx.get(t)
                    if i is not None: s._clore(t, s.C[i])
                s.attente = None
            jour_pnl += sum(s.pnl.get(t, 0)-av3[q] for q, s in enumerate(sl))
            jour_stop = True; coupes += 1; continue
        fc = 0.75 if (thr and len(eq_jours) > 20 and eq*(1+jour_pnl) < np.mean(eq_jours[-20:])) else 1.0
        ouverts = sum(1 for s in sl if s.pos is not None)
        familles = {MH.FAM[s.nom] for s in sl if s.pos is not None}
        for s in sl:
            if s.pos is not None or ouverts >= 2: continue
            if corr and MH.FAM[s.nom] == "mi" and "mi" in familles: continue
            sig = s.signal(t)
            if sig is None: continue
            r0 = s.risque; s.risque = r0*fc
            av2 = s.pnl.get(t, 0)
            ok = s.ouvrir(t, **sig); s.risque = r0
            if ok:
                jour_pnl += s.pnl.get(t, 0)-av2
                ouverts += 1; familles.add(MH.FAM[s.nom])
    tot = {}
    for s in sl:
        for tt, vv in s.pnl.items():
            jj = tt.date(); tot[jj] = tot.get(jj, 0)+vv
    tous = sorted({t.date() for t in ts})
    tj = pd.Series([tot.get(j, 0.0) for j in tous], index=pd.DatetimeIndex(tous))
    eqs = (1+tj).cumprod(); ans = (tj.index[-1]-tj.index[0]).days/365.25
    cagr = (eqs.iloc[-1]**(1/ans)-1)*100
    sh = tj.mean()/tj.std()*np.sqrt(365) if tj.std() > 0 else 0
    dd = ((eqs/eqs.cummax())-1).min()*100
    vals = tj.values; morts = reussis = 0
    for i0 in range(0, len(vals)-40, 21):
        e2 = 1.0
        for jx in range(i0, len(vals)):
            e2 *= (1+vals[jx])
            if e2 <= 0.92: morts += 1; break
            if e2 >= 1.10: reussis += 1; break
    n = morts+reussis
    m = len(tj)//2
    c1 = ((1+tj[:m]).prod()**(1/(m/365.25))-1)*100
    c2 = ((1+tj[m:]).prod()**(1/((len(tj)-m)/365.25))-1)*100
    par_an = {an: ((1+tj[tj.index.year == an]).prod()-1)*100
              for an in sorted({d.year for d in tj.index})}
    return dict(cagr=cagr, sh=sh, dd=dd, coupes=coupes, morts=(morts/n*100 if n else 0),
                m1=c1, m2=c2, par_an=par_an)

NOMS = [("I2+", "I2+"), ("L3", "L3"), ("L3+", "L3+"),
        ("L4 (mode challenge ON)", "L4"), ("L4 (mode OFF)", "L4off")]
res = {}
print("=== BACKTEST H4 COMPLET, 10 ANS (2015-2026, Dukascopy + Bitstamp/Binance) ===")
print("  %-26s | %-7s | %-6s | %-7s | %-6s | %-5s | %s"
      % ("Config", "CAGR", "Sharpe", "MaxDD", "Coupes", "Morts", "Moities"))
print("  " + "-" * 84)
for nom, gen in NOMS:
    r = sim10(gen); res[nom] = r
    print("  %-26s | %+6.1f%% | %6.2f | %+6.1f%% | %6d | %4.0f%% | %+5.1f/%+5.1f%%"
          % (nom, r["cagr"], r["sh"], r["dd"], r["coupes"], r["morts"], r["m1"], r["m2"]))
print()
print("=== RENDEMENT PAR ANNEE (H4, 10 ans) ===")
noms = [n for n, _ in NOMS]
annees = sorted(res[noms[0]]["par_an"].keys())
print("  %-6s | %s" % ("Annee", " | ".join("%-9s" % ("L4 ON" if "ON" in n else ("L4 OFF" if "OFF" in n else n)) for n in noms)))
print("  " + "-" * 70)
for an in annees:
    print("  %-6d | %s" % (an, " | ".join("%+8.1f%%" % res[n]["par_an"].get(an, 0) for n in noms)))
print("  (2015 = 4 mois, 2026 = 8 mois)")
