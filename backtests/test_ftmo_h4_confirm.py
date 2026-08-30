# -*- coding: utf-8 -*-
"""CONFIRMATION H4 de l'optimisation challenge FTMO : le gagnant du moteur
1d (L4 complet + USD_JPY/AUD_JPY/Brent/JP225 a 1,5 %, cap 2) refait en
execution 4 heures (2 ans, fenetre commune), avec les variantes defensives
(frein DD, risque x0,75). Donnees candidates : Yahoo 60m -> 4h (730 j),
cache oanda4h_*.csv."""
import os, time, pandas as pd, numpy as np
import moteur_h4 as MH
import fetch_h4

D = os.path.dirname(os.path.abspath(__file__))
def charger_4h(sym):
    fn = os.path.join(D, "oanda4h_" + sym.replace("=", "").replace("^", "") + ".csv")
    if os.path.exists(fn):
        return pd.read_csv(fn, index_col=0, parse_dates=True)
    df = fetch_h4.yahoo_h4(sym)
    df.to_csv(fn); time.sleep(0.3)
    return df

src = open("combo_l4.py", encoding="utf-8").read().split("MARCHES = (")[0]
ns = {"__file__": "combo_l4.py"}; exec(src, ns)
sleeves_h4_base, gerer_pyr_max_h4 = ns["sleeves_h4"], ns["gerer_pyr_max_h4"]

CAND = {"USD_JPY": ("USDJPY=X", "fx", 0.00010, -0.00005),
        "AUD_JPY": ("AUDJPY=X", "fx", 0.00020, -0.00005),
        "BCO_USD": ("BZ=F",     "en", 0.00045, +0.00005),
        "JP225":   ("NKD=F",    "mi", 0.00010, -0.00015)}
FAMX = dict(MH.FAM)
DATA4H = {}
print("Telechargement H4 des candidats...")
for nom, (sym, fam, frais, swap) in CAND.items():
    FAMX[nom] = fam
    try:
        df = charger_4h(sym)
        DATA4H[nom] = df
        print("  %-8s %d barres (%s -> %s)" % (nom, len(df), df.index[0], df.index[-1]))
    except Exception as e:
        print("  %-8s ECHEC (%s)" % (nom, type(e).__name__))

BASE5 = ("Or", "Petrole", "Nasdaq", "BTC Cassure", "BTC EMA")

def construire(ajouts=(), risque_ajout=0.015, mult_risque=1.0):
    sl = sleeves_h4_base(BASE5)
    for s in sl: s.risque *= mult_risque
    for nom in ajouts:
        if nom not in DATA4H: continue
        sym, fam, frais, swap = CAND[nom]
        x = MH.DonchH4(nom, DATA4H[nom], risque_ajout*mult_risque, frais, swap, 1.4)
        x.pyr_max = 3
        x.gerer = gerer_pyr_max_h4.__get__(x); x.ouvrir = MH.ouvrir_pyr.__get__(x)
        sl.append(x)
    return sl

def sim(ajouts=(), cap=2, risque_ajout=0.015, mult_risque=1.0, throttle=0.75, frein=False):
    sl = construire(ajouts, risque_ajout, mult_risque)
    garde = -0.025
    ts = [t for t in sorted(set().union(*[set(s.index) for s in sl]))
          if t >= pd.Timestamp("2024-08-21")]
    jour_pnl, jour_cour, jour_stop = 0.0, None, False
    eq, eq_jours, sommet = 1.0, [], 1.0
    for t in ts:
        j = t.date()
        if j != jour_cour:
            if jour_cour is not None:
                eq *= (1 + jour_pnl); eq_jours.append(eq); sommet = max(sommet, eq)
            jour_cour, jour_pnl, jour_stop = j, 0.0, False
        avant = [s.pnl.get(t, 0) for s in sl]
        for s in sl: s.gerer(t)
        jour_pnl += sum(s.pnl.get(t, 0) - avant[q] for q, s in enumerate(sl))
        if jour_stop: continue
        if jour_pnl <= garde:
            av3 = [s.pnl.get(t, 0) for s in sl]
            for s in sl:
                if s.pos is not None:
                    i = s.idx.get(t)
                    if i is not None: s._clore(t, s.C[i])
                s.attente = None
            jour_pnl += sum(s.pnl.get(t, 0) - av3[q] for q, s in enumerate(sl))
            jour_stop = True; continue
        fc = 1.0
        if throttle and len(eq_jours) > 20 and eq*(1+jour_pnl) < np.mean(eq_jours[-20:]): fc = throttle
        if frein and eq*(1+jour_pnl) < sommet * 0.96: fc = min(fc, 0.5)
        ouverts = sum(1 for s in sl if s.pos is not None)
        familles = {FAMX[s.nom] for s in sl if s.pos is not None}
        for s in sl:
            if s.pos is not None or ouverts >= cap: continue
            if FAMX[s.nom] == "mi" and "mi" in familles: continue
            sig = s.signal(t)
            if sig is None: continue
            r0 = s.risque; s.risque = r0 * fc
            av2 = s.pnl.get(t, 0)
            ok = s.ouvrir(t, **sig); s.risque = r0
            if ok:
                jour_pnl += s.pnl.get(t, 0) - av2
                ouverts += 1; familles.add(FAMX[s.nom])
    tot = {}
    for s in sl:
        for tt, vv in s.pnl.items():
            jj = tt.date(); tot[jj] = tot.get(jj, 0) + vv
    tous = sorted({t.date() for t in ts})
    return pd.Series([tot.get(j, 0.0) for j in tous], index=pd.DatetimeIndex(tous))

def stats_challenge(tj):
    vals = tj.values; morts = 0; durees = []
    for i0 in range(0, len(vals) - 40, 21):
        e2 = 1.0
        for jx in range(i0, len(vals)):
            e2 *= (1 + vals[jx])
            if e2 <= 0.92: morts += 1; break
            if e2 >= 1.10: durees.append(jx - i0); break
    n = morts + len(durees)
    eq = (1 + tj).cumprod()
    ans = (tj.index[-1] - tj.index[0]).days / 365.25
    cagr = (eq.iloc[-1] ** (1/ans) - 1) * 100
    dd = ((eq / eq.cummax()) - 1).min() * 100
    return (morts/n*100 if n else 0), (np.median(durees) if durees else float("nan")), cagr, dd

C4 = ("USD_JPY", "AUD_JPY", "BCO_USD", "JP225")
print()
print("=== CONFIRMATION H4 (2 ans, fenetre commune) ===")
print("%-36s | %-6s %-9s %-8s %-7s" % ("Config", "Echecs", "MedJours", "CAGR", "MaxDD"))
print("-" * 75)
for nom, kw in (("L4 complet (reference)", dict()),
                ("L4 + 4 cand. 1,5% cap 2", dict(ajouts=C4)),
                ("L4 + 4 cand. 0,75% cap 3", dict(ajouts=C4, risque_ajout=0.0075, cap=3)),
                ("L4 + frein DD 4%", dict(frein=True)),
                ("L4 risque x0,75", dict(mult_risque=0.75))):
    m, dj, c, dd = stats_challenge(sim(**kw))
    print("%-36s | %5.0f%% %6.0f j  %+6.1f%%  %+6.1f%%" % (nom, m, dj, c, dd))
