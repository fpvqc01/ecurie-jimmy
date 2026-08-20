# -*- coding: utf-8 -*-
"""L4 + LECTURES MACRO ET CORRELATION INTERMARCHE (21 aout).
Trois overlays a principe economique, testes sur 10 ANS H4 (Dukascopy) :
  A. L4 reference
  B. MACRO DOLLAR : pas d'entree OR quand le DXY > sa moyenne 200 j
  C. INTERMARCHE : pas d'entree BTC quand le Nasdaq < sa moyenne 200 j
  D. CORRELATION DYNAMIQUE : le plafond or/Nasdaq ne s'applique que si la
     correlation 60 j mesuree entre les deux depasse 0,3
  E. combinaison des gagnants (decidee apres B-D)
Chaque overlay est aussi teste sur le moteur D1 10 ans (contre-verification).
"""
import os, time, requests, pandas as pd, numpy as np

D = os.path.dirname(os.path.abspath(__file__))

# ---------- DXY 10 ans (Yahoo daily) ----------
chemin = os.path.join(D, "d10_dxy.csv")
if not os.path.exists(chemin):
    fin = int(time.time()); debut = fin - int(11*365.25*86400)
    r = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/DX-Y.NYB",
                     params={"period1": debut, "period2": fin, "interval": "1d"},
                     headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
    r.raise_for_status()
    d_ = r.json()["chart"]["result"][0]; q = d_["indicators"]["quote"][0]
    pd.DataFrame({"t": pd.to_datetime(d_["timestamp"], unit="s").normalize(),
                  "c": q["close"]}).dropna().drop_duplicates("t").set_index("t").to_csv(chemin)
dxy = pd.read_csv(chemin, index_col=0, parse_dates=True)["c"]
dxy_e200 = dxy.ewm(span=200, adjust=False).mean()
DOLLAR_FORT = set(dxy.index[(dxy > dxy_e200)].date)   # jours ou le dollar est fort
print("DXY : %d jours, dollar fort %d%% du temps" % (len(dxy), 100*len(DOLLAR_FORT)/len(dxy)))

# ---------- donnees 10 ans ----------
def charge(nom):
    return pd.read_csv(os.path.join(D, "d10h4_%s.csv" % nom), index_col=0,
                       parse_dates=True)[["o", "h", "l", "c"]].astype(float)
GC10, CL10, NQ10, BTC10 = charge("gc"), charge("cl"), charge("nq"), charge("btc")

nq_j = NQ10["c"].resample("1D").last().dropna()
nq_e200 = nq_j.ewm(span=200, adjust=False).mean()
RISK_OFF = set(nq_j.index[(nq_j < nq_e200)].date)     # Nasdaq sous sa moyenne 200

gc_j = GC10["c"].resample("1D").last().dropna()
r_gc = gc_j.pct_change(); r_nq = nq_j.pct_change()
corr60 = r_gc.rolling(60).corr(r_nq).shift(1)          # correlation mesuree (veille)
CORR_HAUTE = set(corr60.index[corr60 > 0.3].date)
print("Correlation or/Nasdaq 60 j > 0,3 : %d%% du temps" % (100*len(CORR_HAUTE)/max(len(corr60.dropna()),1)))

# ---------- moteur H4 (reprend test_l4_h4_10ans) ----------
import moteur_h4 as MH
src = open(os.path.join(D, "valide_candidats_h4.py"), encoding="utf-8").read()
ns = {"__file__": os.path.join(D, "valide_candidats_h4.py")}
exec(src.split("RISQUES =")[0], ns)
gerer_pyr_max = ns["gerer_pyr_max"]

def sleeves_l4():
    sl = [
        MH.FibH4("Or", GC10, 0.02, 0.0001, -0.000273, 1.4, jimmy=True, retrace=0.25, tpj=1.5,
                 lookback=10, fib=(0.2, 0.8), pull=55, mult=3.0, tpr=2.0),
        MH.DonchH4("Petrole", CL10, 0.015, 0.00045, +0.000051, 1.4, saison=(1201, 531)),
        MH.DonchH4("BTC Cassure", BTC10, 0.015, 0.0004, -0.000833, 1.0),
        MH.FibH4("Nasdaq", NQ10, 0.015, 0.00003, -0.000213, 1.4, jimmy=True, retrace=0.5,
                 tpj=1.0, lookback=7, fib=(0.1, 0.9), pull=60, mult=2.0, tpr=2.0),
        MH.EmaBTCH4("BTC EMA", BTC10, 0.015, 0.0004, -0.000833, 1.0, jimmy=True,
                    retrace=0.25, tpj=2.0),
    ]
    for s in sl:
        if s.nom in ("BTC Cassure", "Petrole"):
            s.pyr_max = 3
            s.gerer = gerer_pyr_max.__get__(s); s.ouvrir = MH.ouvrir_pyr.__get__(s)
    return sl

def sim_h4(interdit=None, corr_dyn=False):
    """interdit(nom, date)->True = pas d'entree pour cette manche ce jour-la."""
    sl = sleeves_l4(); garde = -0.025
    ts = [t for t in sorted(set().union(*[set(s.index) for s in sl]))
          if t >= pd.Timestamp("2015-08-21")]
    jour_pnl, jour_cour, jour_stop = 0.0, None, False
    eq, eq_jours = 1.0, []
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
            jour_stop = True; continue
        fc = 0.75 if (len(eq_jours) > 20 and eq*(1+jour_pnl) < np.mean(eq_jours[-20:])) else 1.0
        ouverts = sum(1 for s in sl if s.pos is not None)
        familles = {MH.FAM[s.nom] for s in sl if s.pos is not None}
        cap_mi = (not corr_dyn) or (j in CORR_HAUTE)
        for s in sl:
            if s.pos is not None or ouverts >= 2: continue
            if MH.FAM[s.nom] == "mi" and "mi" in familles and cap_mi: continue
            if interdit and interdit(s.nom, j): continue
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
    tj = pd.Series([tot.get(x, 0.0) for x in tous], index=pd.DatetimeIndex(tous))
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
    return cagr, sh, dd, (morts/n*100 if n else 0), c1, c2

def int_or(nom, j):  return nom == "Or" and j in DOLLAR_FORT
def int_btc(nom, j): return nom in ("BTC Cassure", "BTC EMA") and j in RISK_OFF

print()
print("=== L4 + MACRO / INTERMARCHE (H4, 10 ans) ===")
print("  %-44s | %-7s | %-6s | %-7s | %-5s | %s"
      % ("Variante", "CAGR", "Sharpe", "MaxDD", "Morts", "Moities"))
print("  " + "-" * 92)
for nom, kw in (
    ("A. L4 reference", dict()),
    ("B. macro dollar (or bloque si DXY>e200)", dict(interdit=int_or)),
    ("C. intermarche (BTC bloque si NQ<e200)", dict(interdit=int_btc)),
    ("D. plafond de correlation DYNAMIQUE", dict(corr_dyn=True)),
    ("E. B + C", dict(interdit=lambda n, j: int_or(n, j) or int_btc(n, j))),
    ("F. B + C + D", dict(interdit=lambda n, j: int_or(n, j) or int_btc(n, j), corr_dyn=True)),
):
    c, s, d, m, a1, a2 = sim_h4(**kw)
    print("  %-44s | %+6.1f%% | %6.2f | %+6.1f%% | %4.0f%% | %+5.1f/%+5.1f%%"
          % (nom, c, s, d, m, a1, a2))
