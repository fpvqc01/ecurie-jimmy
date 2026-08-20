# -*- coding: utf-8 -*-
"""L4 SUR 10 ANS (2015-2026, 1d) -- la question de Jimmy du 21 aout.
Donnees Yahoo par period1/period2 (le piege range=max donne du mensuel).
BTC-USD demarre en sept. 2014 chez Yahoo -> fenetre commune ~10 ans.
Configs : I2+, L3, L3+, L4 (mode challenge ON et OFF).
Metriques : CAGR, morts en challenge, moities, pire annee, annee par annee."""
import os, time, requests, pandas as pd, numpy as np

D = os.path.dirname(os.path.abspath(__file__))

def fetch_10y(sym, nom):
    chemin = os.path.join(D, "d10_%s.csv" % nom)
    if os.path.exists(chemin):
        df = pd.read_csv(chemin, index_col=0, parse_dates=True)
        return df
    fin = int(time.time())
    debut = fin - int(11 * 365.25 * 86400)
    r = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/%s" % sym,
                     params={"period1": debut, "period2": fin, "interval": "1d"},
                     headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
    r.raise_for_status()
    d = r.json()["chart"]["result"][0]
    q = d["indicators"]["quote"][0]
    df = pd.DataFrame({"t": pd.to_datetime(d["timestamp"], unit="s").normalize(),
                       "o": q["open"], "h": q["high"], "l": q["low"], "c": q["close"]}
                      ).dropna().drop_duplicates("t").set_index("t")
    df.to_csv(chemin)
    return df

btc10 = fetch_10y("BTC-USD", "btc")
gc10  = fetch_10y("GC=F", "gc")
nq10  = fetch_10y("NQ=F", "nq")
cl10  = fetch_10y("CL=F", "cl")
print("Donnees 10 ans : BTC %d j (%s->), OR %d j, NQ %d j, CL %d j" %
      (len(btc10), btc10.index[0].date(), len(gc10), len(nq10), len(cl10)))
print()

from moteur_1d import Fib, Donch, EmaBTC, ouvrir_pyr, FAM
src = open(os.path.join(D, "scan_strategies.py"), encoding="utf-8").read().split("RISQUES =")[0]
ns = {"__file__": os.path.join(D, "scan_strategies.py")}; exec(src, ns)
gerer_pyr_max = ns["gerer_pyr_max"]

def sim10(gen, thr_force="auto"):
    pyr  = gen in ("L3", "L3+", "L4")
    corr = gen in ("L3+", "L4")
    thr  = 0.75 if gen in ("L3+", "L4") else None
    if thr_force != "auto": thr = thr_force
    garde = -0.035 if gen == "I2+" else -0.025
    r_or = {"I2+": 0.03, "L3": 0.03, "L3+": 0.015, "L4": 0.02}[gen]
    r_pb = 0.015 if gen in ("L3+", "L4") else 0.0075
    sl = [
        Fib("Or", gc10, r_or, 0.0001, -0.000273, 1.4, jimmy=True, retrace=0.25, tpj=1.5,
            lookback=10, fib=(0.2, 0.8), pull=55, mult=3.0, tpr=2.0),
        Donch("Petrole", cl10, r_pb, 0.00045, +0.000051, 1.4, saison=(1201, 531)),
        Donch("BTC Cassure", btc10, r_pb, 0.0004, -0.000833, 1.0),
        Fib("Nasdaq", nq10, 0.015, 0.00003, -0.000213, 1.4, jimmy=True, retrace=0.5,
            tpj=1.0, lookback=7, fib=(0.1, 0.9), pull=60, mult=2.0, tpr=2.0),
        EmaBTC("BTC EMA", btc10, r_pb, 0.0004, -0.000833, 1.0, jimmy=True, retrace=0.25, tpj=2.0),
    ]
    for s in sl:
        if pyr and s.nom in ("BTC Cassure", "Petrole"):
            s.pyr_max = 3
            s.gerer = gerer_pyr_max.__get__(s); s.ouvrir = ouvrir_pyr.__get__(s)
    dates = sorted(set().union(*[set(s.df.index) for s in sl]))
    equite, histo = 1.0, []
    for d in dates:
        for s in sl: s.gerer(d)
        jt = sum(s.pnl.get(d, 0) for s in sl)
        if jt <= garde:
            f = garde/jt
            for s in sl:
                if d in s.pnl: s.pnl[d] *= f
                s.pos = None; s.attente = None; s.runners = []
            jt = garde
        equite *= (1+jt); histo.append(equite)
        if jt <= garde: continue
        fc = 0.75 if (thr and len(histo) > 20 and equite < np.mean(histo[-20:])) else 1.0
        ouverts = sum(1 for s in sl if s.pos is not None)
        familles = {FAM[s.nom] for s in sl if s.pos is not None}
        for s in sl:
            if s.pos is not None or ouverts >= 2: continue
            if corr and FAM[s.nom] == "mi" and "mi" in familles: continue
            sig = s.signal(d)
            if sig is None: continue
            r0 = s.risque; s.risque = r0*fc
            ok = s.ouvrir(d, **sig); s.risque = r0
            if ok: ouverts += 1; familles.add(FAM[s.nom])
    tj = pd.Series(0.0, index=pd.DatetimeIndex(dates))
    for s in sl:
        for dt, v in s.pnl.items():
            if dt in tj.index: tj[dt] += v
    tj = tj.clip(lower=garde)
    eq = (1+tj).cumprod()
    ans = (tj.index[-1]-tj.index[0]).days/365.25
    cagr = (eq.iloc[-1]**(1/ans)-1)*100
    sh = tj.mean()/tj.std()*np.sqrt(365) if tj.std() > 0 else 0
    dd = ((eq/eq.cummax())-1).min()*100
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
    return dict(cagr=cagr, sh=sh, dd=dd, morts=(morts/n*100 if n else 0),
                m1=c1, m2=c2, par_an=par_an)

CONFIGS = [("I2+", "auto"), ("L3", "auto"), ("L3+", "auto"),
           ("L4 (mode challenge ON)", "auto"), ("L4 (mode OFF)", None)]
res = {}
print("=== 10 ANS (1d, 2015-2026) ===")
print("  %-26s | %-7s | %-6s | %-7s | %-5s | %s"
      % ("Config", "CAGR", "Sharpe", "MaxDD", "Morts", "Moities"))
print("  " + "-" * 78)
for nom, thr in CONFIGS:
    gen = "L4" if nom.startswith("L4") else nom
    r = sim10(gen, thr)
    res[nom] = r
    print("  %-26s | %+6.1f%% | %6.2f | %+6.1f%% | %4.0f%% | %+5.1f/%+5.1f%%"
          % (nom, r["cagr"], r["sh"], r["dd"], r["morts"], r["m1"], r["m2"]))
print()
print("=== RENDEMENT PAR ANNEE ===")
noms = [c[0] for c in CONFIGS]
annees = sorted(res[noms[0]]["par_an"].keys())
print("  %-6s | %s" % ("Annee", " | ".join("%-9s" % ("L4 ON" if n == "L4 (mode challenge ON)"
      else ("L4 OFF" if n == "L4 (mode OFF)" else n)) for n in noms)))
print("  " + "-" * 70)
for an in annees:
    print("  %-6d | %s" % (an, " | ".join("%+8.1f%%" % res[n]["par_an"].get(an, 0) for n in noms)))
