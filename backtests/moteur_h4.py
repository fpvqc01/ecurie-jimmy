# -*- coding: utf-8 -*-
"""MOTEUR DE BACKTEST H4 (21 aout 2026) -- version numpy (rapide).
Memes strategies que le moteur journalier (optimisation_finale.py) --
indicateurs JOURNALIERS -- mais execution en barres de 4 heures :
  - valeurs provisoires intrajournalieres ATR/RSI/EMA (recurrence de Wilder
    avec le haut/bas/cloture du jour en cours), ce qu'un robot voit vraiment
    sur un graphique daily en cours de journee ;
  - canaux Donchian / fenetres fib sur les jours COMPLETS precedents ;
  - stops/TP testes barre par barre (6 barres/jour) ;
  - GARDIEN QUOTIDIEN INTRAJOURNALIER : des que le PnL du jour touche le
    seuil, tout est ferme a la barre meme et plus rien jusqu'au lendemain ;
  - filtres d'entree par horodatage (ex. vendredi apres 12h Montreal).
Donnees : BTC Binance 4h 2017-2026 ; or/petrole/Nasdaq Yahoo 1h->4h (730 j).
Horodatages UTC. Generations : I2+ / L3 / I2++ / L3+."""
import os, pandas as pd, numpy as np
from datetime import date, timedelta

D = os.path.dirname(os.path.abspath(__file__))

def charger(nom):
    df = pd.read_csv(os.path.join(D, nom + ".csv"), index_col=0, parse_dates=True)
    return df[["o", "h", "l", "c"]].astype(float)

BTC, GC, NQ, CL = charger("btc_4h"), charger("gc_4h"), charger("nq_4h"), charger("cl_4h")
BPJ = 6.0

# ---------------- calendrier des feries US ----------------
def _nieme(an, mois, js, n):
    d = date(an, mois, 1); d += timedelta(days=(js - d.weekday()) % 7)
    return d + timedelta(weeks=n-1)
def _dernier(an, mois, js):
    d = date(an, mois+1, 1) - timedelta(days=1) if mois < 12 else date(an, 12, 31)
    while d.weekday() != js: d -= timedelta(days=1)
    return d
def _paques(an):
    a=an%19; b=an//100; c=an%100; d=b//4; e=b%4; f=(b+8)//25; g=(b-f+1)//3
    h=(19*a+b-d-g+15)%30; i=c//4; k=c%4; l=(32+2*e+2*i-h-k)%7; m=(a+11*h+22*l)//451
    return date(an, (h+l-7*m+114)//31, ((h+l-7*m+114)%31)+1)
def _feries(an):
    return {date(an,1,1), _nieme(an,1,0,3), _nieme(an,2,0,3), _paques(an)-timedelta(days=2),
            _dernier(an,5,0), date(an,6,19), date(an,7,4), _nieme(an,9,0,1),
            _nieme(an,11,3,4), date(an,12,25)}
FERIES = set()
for _an in range(2016, 2028): FERIES |= _feries(_an)

# ---------------- manche H4 (numpy) ----------------
class SleeveH4:
    def __init__(self, nom, df, risque, frais, swap, fs, jimmy=False, retrace=0.25, tpj=1.0):
        self.nom = nom
        self.risque, self.frais, self.swap, self.fs = risque, frais, swap, fs
        self.jimmy, self.retrace, self.tpj = jimmy, retrace, tpj
        self.index = df.index
        self.O = df["o"].values; self.H = df["h"].values
        self.L = df["l"].values; self.C = df["c"].values
        self.idx = {t: i for i, t in enumerate(df.index)}
        # journalier (jours complets)
        dj = pd.DataFrame({"o": df["o"].resample("1D").first(), "h": df["h"].resample("1D").max(),
                           "l": df["l"].resample("1D").min(),  "c": df["c"].resample("1D").last()}).dropna()
        self.DJH = dj["h"].values; self.DJL = dj["l"].values; self.DJC = dj["c"].values
        tr = np.maximum(dj["h"]-dj["l"], np.maximum((dj["h"]-dj["c"].shift()).abs(),
                                                    (dj["l"]-dj["c"].shift()).abs()))
        self.ATRJ = tr.ewm(alpha=1/14, adjust=False).mean().values
        dd = dj["c"].diff()
        self.AG = dd.clip(lower=0).ewm(alpha=1/14, adjust=False).mean().values
        self.AP = (-dd.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean().values
        self.E20J = dj["c"].ewm(span=20, adjust=False).mean().values
        self.E50J = dj["c"].ewm(span=50, adjust=False).mean().values
        self.H20J = dj["h"].rolling(20).max().values
        self.B10J = dj["l"].rolling(10).min().values
        # k_prev : indice du dernier jour COMPLET avant la barre i
        djpos = {d.date(): k for k, d in enumerate(dj.index)}
        dates_b = df.index.date
        self.KPREV = np.full(len(df), -1, dtype=np.int64)
        self.NEWDAY = np.zeros(len(df), dtype=bool)
        prev_d = None
        for i, jd in enumerate(dates_b):
            if jd != prev_d:
                self.NEWDAY[i] = True; prev_d = jd
            k = djpos.get(jd)
            if k is not None and k > 0:
                self.KPREV[i] = k - 1
            else:
                jj, ess = jd - timedelta(days=1), 0
                while jj not in djpos and ess < 7:
                    jj -= timedelta(days=1); ess += 1
                self.KPREV[i] = djpos.get(jj, -1)
        self.pos, self.pnl, self.trades = None, {}, 0
        self.attente, self.plancher = None, None
        self.dh = self.dl = 0.0

    def _maj_jour(self, i):
        if self.NEWDAY[i]:
            self.dh, self.dl = self.H[i], self.L[i]
        else:
            if self.H[i] > self.dh: self.dh = self.H[i]
            if self.L[i] < self.dl: self.dl = self.L[i]

    def prov(self, i):
        k = self.KPREV[i]
        if k < 55: return None
        c = self.C[i]; cp = self.DJC[k]
        tr = max(self.dh - self.dl, abs(self.dh - cp), abs(self.dl - cp))
        a = (self.ATRJ[k]*13 + tr) / 14
        d = c - cp
        ag = (self.AG[k]*13 + max(d, 0.0)) / 14
        ap = (self.AP[k]*13 + max(-d, 0.0)) / 14
        rsi = 100 - 100/(1 + ag/ap) if ap > 0 else 100.0
        rsip = 100 - 100/(1 + self.AG[k]/self.AP[k]) if self.AP[k] > 0 else 100.0
        e20 = (2/21)*c + (1 - 2/21)*self.E20J[k]
        e50 = (2/51)*c + (1 - 2/51)*self.E50J[k]
        return (a, rsi, rsip, e20, e50, self.E20J[k], self.E50J[k],
                self.H20J[k], self.B10J[k], c, k)

    def _clore(self, t, prix):
        p = self.pos
        self.pnl[t] = self.pnl.get(t, 0) + p["n"]*(prix-p["prix"])/p["e"] - self.frais*p["n"]
        self.pos = None

    def gerer(self, t):
        i = self.idx.get(t)
        if i is None: return
        self._maj_jour(i)
        if self.pos is None: return
        v = self.prov(i)
        if v is None: return
        a, rsi, rsip, e20, e50, e20p, e50p, h20, b10, c, k = v
        p = self.pos
        l, h = self.L[i], self.H[i]
        if p.get("trail") and not np.isnan(b10) and b10 > p["s"]: p["s"] = b10
        if l <= p["s"]:
            self._clore(t, p["s"]); self.attente = None; return
        if p.get("tp") and h >= p["tp"]:
            tp = p["tp"]; self._clore(t, tp)
            if self.jimmy: self.attente = tp
            return
        if p.get("be") and not p["be_fait"] and h >= p["be"]:
            if p["e"] > p["s"]: p["s"] = p["e"]
            p["be_fait"] = True
        if p.get("sortie_cloture") and self.sortie_cloture(v):
            self._clore(t, c); self.attente = None; return
        self.pnl[t] = self.pnl.get(t, 0) + p["n"]*((c-p["prix"])/p["e"] + self.swap*self.fs/BPJ)
        p["prix"] = c

    def ouvrir(self, t, entree, stop, tp=None, be=None, trail=False, sortie_cloture=False):
        r0p = (entree - stop) / entree
        if r0p <= 0 or r0p > 0.5: return False
        n = min(self.risque / r0p, 2.0)
        self.pnl[t] = self.pnl.get(t, 0) - self.frais * n
        self.pos = dict(e=entree, s=stop, tp=tp, n=n, be=be, be_fait=False,
                        prix=entree, trail=trail, sortie_cloture=sortie_cloture)
        self.trades += 1; self.attente = None
        return True

class EmaBTCH4(SleeveH4):
    def sortie_cloture(self, v): return v[3] <= v[4]
    def signal(self, t):
        i = self.idx.get(t)
        if i is None: return None
        v = self.prov(i)
        if v is None: return None
        a, rsi, rsip, e20, e50, e20p, e50p, h20, b10, c, k = v
        if e20 <= e50: self.attente = None; return None
        R = 2*a
        tp = c + self.tpj*R
        be = c + R if self.tpj >= 2.0 else None
        if e20p <= e50p:
            return dict(entree=c, stop=c-R, tp=tp, be=be, sortie_cloture=True)
        if self.attente is not None and self.L[i] <= self.attente - self.retrace*a:
            return dict(entree=c, stop=c-R, tp=tp, be=be, sortie_cloture=True)
        return None

class DonchH4(SleeveH4):
    def __init__(self, *a, saison=None, **k):
        super().__init__(*a, **k); self.saison = saison
    def sortie_cloture(self, v): return v[9] < v[8]
    def signal(self, t):
        i = self.idx.get(t)
        if i is None: return None
        v = self.prov(i)
        if v is None: return None
        a, rsi, rsip, e20, e50, e20p, e50p, h20, b10, c, k = v
        if np.isnan(h20): return None
        if self.saison:
            md = t.month*100 + t.day
            if not (md >= self.saison[0] or md <= self.saison[1]): return None
        if c > h20:
            return dict(entree=c, stop=b10, trail=True, sortie_cloture=True)
        return None

class FibH4(SleeveH4):
    def __init__(self, *a, lookback=10, fib=(0.2, 0.8), pull=55, mult=3.0, tpr=2.0, **k):
        super().__init__(*a, **k)
        self.lb, self.fz, self.pull, self.mult, self.tpr = lookback, fib, pull, mult, tpr
    def sortie_cloture(self, v): return False
    def signal(self, t):
        i = self.idx.get(t)
        if i is None: return None
        v = self.prov(i)
        if v is None: return None
        a, rsi, rsip, e20, e50, e20p, e50p, h20, b10, c, k = v
        if k < self.lb + 16: return None
        if self.attente is not None and self.plancher is not None and c < self.plancher:
            self.attente = None
        wh = self.DJH[k+1-self.lb:k+1]; wl = self.DJL[k+1-self.lb:k+1]
        hi_i = int(wh.argmax()); lo_i = int(wl.argmin())
        setup = False
        if lo_i < hi_i:
            span = wh[hi_i] - wl[lo_i]
            if span > 0:
                retr = (wh[hi_i] - c) / span
                setup = (self.fz[0] <= retr <= self.fz[1] and rsip < self.pull and rsi > rsip)
        R = self.mult * a
        if setup:
            self.plancher = wl[lo_i]
            if self.jimmy:
                be = c + R if self.tpj >= 2.0 else None
                return dict(entree=c, stop=c-R, tp=c+self.tpj*R, be=be)
            return dict(entree=c, stop=c-R, tp=c+self.tpr*R, be=c+R)
        if (self.jimmy and self.attente is not None and self.plancher is not None
                and self.L[i] <= self.attente - self.retrace*a
                and c > self.plancher):
            be = c + R if self.tpj >= 2.0 else None
            return dict(entree=c, stop=c-R, tp=c+self.tpj*R, be=be)
        return None

# ---------------- pyramidage ----------------
def gerer_pyr(self, t):
    i = self.idx.get(t)
    if i is None: return
    self._maj_jour(i)
    if self.pos is None: return
    v = self.prov(i)
    if v is None: return
    a, rsi, rsip, e20, e50, e20p, e50p, h20, b10, c, k = v
    p = self.pos
    l, h = self.L[i], self.H[i]
    if p.get("trail") and not np.isnan(b10) and b10 > p["s"]: p["s"] = b10
    if l <= p["s"]:
        self._clore(t, p["s"]); self.attente = None; return
    while p["unites"] < 3 and h >= p["prochain"]:
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
    self.pnl[t] = self.pnl.get(t, 0) + p["n"]*((c-p["prix"])/p["e"] + self.swap*self.fs/BPJ)
    p["prix"] = c

def ouvrir_pyr(self, t, entree, stop, tp=None, be=None, trail=False, sortie_cloture=False):
    r0p = (entree - stop) / entree
    if r0p <= 0 or r0p > 0.5: return False
    n = min(self.risque / r0p, 2.0)
    self.pnl[t] = self.pnl.get(t, 0) - self.frais * n
    i = self.idx.get(t); v = self.prov(i)
    self.pos = dict(e=entree, s=stop, tp=tp, n=n, n0=n, be=be, be_fait=False,
                    prix=entree, trail=trail, sortie_cloture=sortie_cloture,
                    unites=1, prochain=entree + 0.5*v[0], dernier=entree)
    self.trades += 1; self.attente = None
    return True

FAM = {"Or": "mi", "Nasdaq": "mi", "Petrole": "en", "BTC Cassure": "cr", "BTC EMA": "cr"}

def construire(gen, avec_btc=True, btc_seul=False):
    pyr = gen in ("L3", "I2++", "L3+")
    par = gen in ("I2++", "L3+")
    r_or  = 0.015 if par else 0.03
    r_pet = 0.015 if par else 0.0075
    r_btc = 0.015 if par else 0.0075
    sl = []
    if not btc_seul:
        sl += [FibH4("Or", GC, r_or, 0.0001, -0.000273, 1.4, jimmy=True, retrace=0.25, tpj=1.5,
                     lookback=10, fib=(0.2, 0.8), pull=55, mult=3.0, tpr=2.0),
               DonchH4("Petrole", CL, r_pet, 0.00045, +0.000051, 1.4, saison=(1201, 531)),
               FibH4("Nasdaq", NQ, 0.015, 0.00003, -0.000213, 1.4, jimmy=True, retrace=0.5,
                     tpj=1.0, lookback=7, fib=(0.1, 0.9), pull=60, mult=2.0, tpr=2.0)]
    if avec_btc or btc_seul:
        sl += [DonchH4("BTC Cassure", BTC, r_btc, 0.0004, -0.000833, 1.0),
               EmaBTCH4("BTC EMA", BTC, r_btc, 0.0004, -0.000833, 1.0, jimmy=True,
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
    ts = sorted(set().union(*[set(s.index) for s in sleeves]))
    if debut: ts = [t for t in ts if t >= pd.Timestamp(debut)]
    if fin:   ts = [t for t in ts if t <= pd.Timestamp(fin)]
    jour_pnl, jour_cour, jour_stop = 0.0, None, False
    eq, eq_jours = 1.0, []
    coupes, entrees = 0, []
    for t in ts:
        j = t.date()
        if j != jour_cour:
            if jour_cour is not None:
                eq *= (1 + jour_pnl); eq_jours.append(eq)
            jour_cour, jour_pnl, jour_stop = j, 0.0, False
        avant = [s.pnl.get(t, 0) for s in sleeves]
        for s in sleeves: s.gerer(t)
        if aplatit and aplatit(t):
            for s in sleeves:
                if s.pos is not None:
                    i = s.idx.get(t)
                    if i is not None: s._clore(t, s.C[i])
                    s.attente = None
        jour_pnl += sum(s.pnl.get(t, 0) - avant[q] for q, s in enumerate(sleeves))
        if jour_stop: continue
        if jour_pnl <= garde:                       # GARDIEN INTRAJOURNALIER
            av3 = [s.pnl.get(t, 0) for s in sleeves]
            for s in sleeves:
                if s.pos is not None:
                    i = s.idx.get(t)
                    if i is not None: s._clore(t, s.C[i])
                s.attente = None
            jour_pnl += sum(s.pnl.get(t, 0) - av3[q] for q, s in enumerate(sleeves))
            jour_stop = True; coupes += 1; continue
        if bloque and bloque(t): continue
        fc = 1.0
        if chal and len(eq_jours) > 20 and eq*(1+jour_pnl) < np.mean(eq_jours[-20:]): fc = 0.75
        ouverts = sum(1 for s in sleeves if s.pos is not None)
        if ouverts >= 2: continue
        familles = {FAM[s.nom] for s in sleeves if s.pos is not None}
        for s in sleeves:
            if s.pos is not None or ouverts >= 2: continue
            if corr and FAM[s.nom] == "mi" and "mi" in familles: continue
            sig = s.signal(t)
            if sig is None: continue
            r0 = s.risque; s.risque = r0 * fc
            av2 = s.pnl.get(t, 0)
            ok = s.ouvrir(t, **sig)
            s.risque = r0
            if ok:
                jour_pnl += s.pnl.get(t, 0) - av2
                ouverts += 1; familles.add(FAM[s.nom]); entrees.append((t, s.nom))
    if trace: return entrees
    tot = {}
    for s in sleeves:
        for tt, vv in s.pnl.items():
            jj = tt.date(); tot[jj] = tot.get(jj, 0) + vv
    tous_jours = sorted({t.date() for t in ts})       # TOUS les jours de la fenetre
    tj = pd.Series([tot.get(j, 0.0) for j in tous_jours],
                   index=pd.DatetimeIndex(tous_jours))
    eqs = (1 + tj).cumprod(); ans = (tj.index[-1] - tj.index[0]).days / 365.25
    cagr = (eqs.iloc[-1] ** (1/ans) - 1) * 100 if ans > 0 else 0
    sh = tj.mean()/tj.std()*np.sqrt(365) if tj.std() > 0 else 0
    dd = ((eqs/eqs.cummax()) - 1).min() * 100
    trades = sum(s.trades for s in sleeves)
    m = len(tj)//2
    c1 = ((1+tj[:m]).prod()**(1/max(m/365.25, 1e-9))-1)*100
    c2 = ((1+tj[m:]).prod()**(1/max((len(tj)-m)/365.25, 1e-9))-1)*100
    vals = tj.values; morts = reussis = 0
    for i0 in range(0, len(vals)-40, 21):
        e2 = 1.0
        for jx in range(i0, len(vals)):
            e2 *= (1+vals[jx])
            if e2 <= 0.92: morts += 1; break
            if e2 >= 1.10: reussis += 1; break
    n = morts + reussis
    return dict(cagr=cagr, sharpe=sh, dd=dd, trades=trades, coupes=coupes,
                morts=(morts/n*100 if n else 0), m1=c1, m2=c2)

def ligne(nom, r):
    return ("  %-42s | %+6.1f%% | %6.2f | %+6.1f%% | %6d | %5d | %4.0f%% | %+5.1f/%+5.1f%%"
            % (nom, r["cagr"], r["sharpe"], r["dd"], r["trades"], r["coupes"],
               r["morts"], r["m1"], r["m2"]))
ENTETE = ("  %-42s | %-7s | %-6s | %-7s | %-6s | %-5s | %-5s | %s"
          % ("Variante", "CAGR", "Sharpe", "MaxDD", "Trades", "Coupes", "Morts", "Moities"))
