# -*- coding: utf-8 -*-
"""MOTEUR 1D UNIFIE (21 aout 2026) : la meme interface que moteur_h4.sim
(gen, avec_btc, btc_seul, bloque, aplatit, debut, trace) mais en bougies
JOURNALIERES -- strategies et gardien identiques aux tests de la semaine
(gardien fin de journee : PnL du jour plafonne au seuil, positions fermees).
Donnees : Yahoo 5 ans (moteur d'origine) + BTC Binance resample 1d (8 ans)
pour la section BTC seul."""
import os, pandas as pd, numpy as np
from datetime import date, timedelta

d0 = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(d0, "test_marche_us_ferme.py"), encoding="utf-8").read()
_ns = {"__file__": os.path.join(d0, "test_marche_us_ferme.py")}
exec(src.split("def sim(")[0], _ns)         # Fib/Donch/EmaBTC + pyramidage + feries + donnees
Fib, Donch, EmaBTC = _ns["Fib"], _ns["Donch"], _ns["EmaBTC"]
gerer_pyr, ouvrir_pyr = _ns["gerer_pyr"], _ns["ouvrir_pyr"]
TOUS, JOURS_US = _ns["TOUS"], _ns["JOURS_US"]
gc, cl, nq, btc = _ns["gc"], _ns["cl"], _ns["nq"], _ns["btc"]

# BTC 8 ans : Binance 4h resample en 1d
_b4 = pd.read_csv(os.path.join(d0, "btc_4h.csv"), index_col=0, parse_dates=True)
BTC8 = pd.DataFrame({"o": _b4["o"].resample("1D").first(), "h": _b4["h"].resample("1D").max(),
                     "l": _b4["l"].resample("1D").min(),  "c": _b4["c"].resample("1D").last()}).dropna()

FAM = {"Or": "mi", "Nasdaq": "mi", "Petrole": "en", "BTC Cassure": "cr", "BTC EMA": "cr"}

def construire(gen, avec_btc=True, btc_seul=False):
    pyr = gen in ("L3", "I2++", "L3+")
    par = gen in ("I2++", "L3+")
    r_or  = 0.015 if par else 0.03
    r_pet = 0.015 if par else 0.0075
    r_btc = 0.015 if par else 0.0075
    b = BTC8 if btc_seul else btc
    sl = []
    if not btc_seul:
        sl += [Fib("Or", gc, r_or, 0.0001, -0.000273, 1.4, jimmy=True, retrace=0.25, tpj=1.5,
                   lookback=10, fib=(0.2, 0.8), pull=55, mult=3.0, tpr=2.0),
               Donch("Petrole", cl, r_pet, 0.00045, +0.000051, 1.4, saison=(1201, 531)),
               Fib("Nasdaq", nq, 0.015, 0.00003, -0.000213, 1.4, jimmy=True, retrace=0.5,
                   tpj=1.0, lookback=7, fib=(0.1, 0.9), pull=60, mult=2.0, tpr=2.0)]
    if avec_btc or btc_seul:
        sl += [Donch("BTC Cassure", b, r_btc, 0.0004, -0.000833, 1.0),
               EmaBTC("BTC EMA", b, r_btc, 0.0004, -0.000833, 1.0, jimmy=True,
                      retrace=0.25, tpj=2.0)]
    for s in sl:
        if pyr and s.nom in ("BTC Cassure", "Petrole"):
            s.gerer = gerer_pyr.__get__(s); s.ouvrir = ouvrir_pyr.__get__(s)
    return sl

def sim(gen, avec_btc=True, btc_seul=False, bloque=None, aplatit=None,
        debut=None, fin=None, trace=False):
    sleeves = construire(gen, avec_btc, btc_seul)
    garde = -0.035 if gen == "I2+" else -0.025
    chal = (gen == "L3+")
    corr = gen in ("I2++", "L3+")
    dates = sorted(set().union(*[set(s.df.index) for s in sleeves]))
    if debut: dates = [d for d in dates if d >= pd.Timestamp(debut)]
    if fin:   dates = [d for d in dates if d <= pd.Timestamp(fin)]
    equite, histo = 1.0, []
    coupes, entrees = 0, []
    for d in dates:
        for s in sleeves: s.gerer(d)
        if aplatit and aplatit(d):
            for s in sleeves:
                if s.pos is not None:
                    i = s.jour(d)
                    if i is not None: s._clore(d, s.df["c"].iloc[i])
                    s.attente = None
        jt = sum(s.pnl.get(d, 0) for s in sleeves)
        if jt <= garde:                     # gardien fin de journee (comme la semaine)
            f = garde/jt
            for s in sleeves:
                if d in s.pnl: s.pnl[d] *= f
                s.pos = None; s.attente = None; s.runners = []
            coupes += 1; jt = garde
        equite *= (1+jt); histo.append(equite)
        if jt <= garde: continue
        if bloque and bloque(d): continue
        fc = 1.0
        if chal and len(histo) > 20 and equite < np.mean(histo[-20:]): fc = 0.75
        ouverts = sum(1 for s in sleeves if s.pos is not None)
        familles = {FAM[s.nom] for s in sleeves if s.pos is not None}
        for s in sleeves:
            if s.pos is not None or ouverts >= 2: continue
            if corr and FAM[s.nom] == "mi" and "mi" in familles: continue
            sig = s.signal(d)
            if sig is None: continue
            r0 = s.risque; s.risque = r0 * fc
            ok = s.ouvrir(d, **sig)
            s.risque = r0
            if ok:
                ouverts += 1; familles.add(FAM[s.nom]); entrees.append((d, s.nom))
    if trace: return entrees
    total = pd.Series(0.0, index=pd.DatetimeIndex(dates))
    for s in sleeves:
        for dt, v in s.pnl.items():
            if dt in total.index: total[dt] += v
    total = total.clip(lower=garde)
    eq = (1+total).cumprod()
    ans = (total.index[-1] - total.index[0]).days / 365.25
    cagr = (eq.iloc[-1]**(1/ans)-1)*100 if ans > 0 else 0
    sh = total.mean()/total.std()*np.sqrt(365) if total.std() > 0 else 0
    dd = ((eq/eq.cummax())-1).min()*100
    trades = sum(s.trades for s in sleeves)
    m = len(total)//2
    c1 = ((1+total[:m]).prod()**(1/max(m/365.25, 1e-9))-1)*100
    c2 = ((1+total[m:]).prod()**(1/max((len(total)-m)/365.25, 1e-9))-1)*100
    vals = total.values; morts = reussis = 0
    for i0 in range(0, len(vals)-40, 21):
        e2 = 1.0
        for jx in range(i0, len(vals)):
            e2 *= (1+vals[jx])
            if e2 <= 0.92: morts += 1; break
            if e2 >= 1.10: reussis += 1; break
    n = morts + reussis
    return dict(cagr=cagr, sharpe=sh, dd=dd, trades=trades, coupes=coupes,
                morts=(morts/n*100 if n else 0), m1=c1, m2=c2)
