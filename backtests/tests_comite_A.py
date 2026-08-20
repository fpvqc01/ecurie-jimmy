# -*- coding: utf-8 -*-
"""TESTS DU COMITE EXTERNE (ChatGPT/Gemini), partie A -- sur L4.31 exact
(cadences C2 + tampon 0,25 + pyr4 + filtre dollar), mode challenge ON.
1. SIMULATEUR FTMO EXACT : phase 1 (+10 %) puis phase 2 (+5 %), perte
   jour 5 % (equite vs debut de jour), perte totale 10 % du solde INITIAL
   de chaque phase, minimum 4 jours de trading par phase, sans limite de
   temps (regles FTMO actuelles). Un challenge demarre chaque semaine.
2. CONCENTRATION : retirer les 5/10 meilleurs JOURS (approx. des trades).
3. RISQUE AGREGE AU STOP : pire exposition simultanee si tous les stops
   sont touches d'un coup (pyramides comprises).
4. CORRELATION DE STRESS : correlations des manches sur les 5 % pires jours."""
import os, pandas as pd, numpy as np
D = os.path.dirname(os.path.abspath(__file__))
import moteur_h4 as MH
BTC_H1 = pd.read_csv(os.path.join(D, "d10h1_btc.csv"), index_col=0,
                     parse_dates=True)[["o","h","l","c"]].astype(float)

# ---- moteur L4.31 (C2 + tampon) avec capture des manches et du risque ----
src = open(os.path.join(D, "test_l43_realiste.py"), encoding="utf-8").read().split("BASE =")[0]
ns0 = {"__file__": os.path.join(D, "test_l43_realiste.py")}
exec(src, ns0)
ns, fabrique = ns0["ns"], ns0["fabrique"]
dxy = ns["dxy"]
FORT = set(dxy.index[(dxy > dxy.ewm(span=200, adjust=False).mean())].date)
f_or = lambda n, j: n == "Or" and j in FORT
C2 = {"Or": "H4", "Nasdaq": "H4", "BTC Cassure": "H1", "BTC EMA": "D1", "Petrole": "H4"}

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

capture = {}
RISQUE_STOP = []          # (t, risque agrege au stop en % equite)
def fab():
    base = fabrique(C2)
    sl = base()
    for s in sl:
        if s.nom in ("BTC Cassure", "Petrole"): tampon(s)
    capture["sl"] = sl
    return sl
ns["sleeves_l4"] = fab

# instrumentation du risque au stop : on echantillonne apres chaque gerer
src_sim = open(os.path.join(D, "test_l4_macro.py"), encoding="utf-8").read().split('print()')[0]
src_sim = src_sim.replace('if t >= pd.Timestamp("2015-08-21")]',
                          'if t >= pd.Timestamp(DEBUT) and t <= pd.Timestamp(FIN)]')
src_sim = src_sim.replace(
    "        jour_pnl += sum(s.pnl.get(t, 0)-avant[q] for q, s in enumerate(sl))",
    "        jour_pnl += sum(s.pnl.get(t, 0)-avant[q] for q, s in enumerate(sl))\n"
    "        if ECHANT and t.hour == 0:\n"
    "            rt = 0.0\n"
    "            for s in sl:\n"
    "                p = s.pos\n"
    "                if p is None: continue\n"
    "                rt += p['n'] * max(p.get('prix', p['e']) - p['s'], 0) / p['e']\n"
    "            RISQUE_STOP.append((t, rt))")
assert "ECHANT and t.hour" in src_sim, "instrumentation non inseree !"
ns2 = {"__file__": os.path.join(D, "test_l4_macro.py"), "DEBUT": "2015-08-21",
       "FIN": "2026-12-31", "ECHANT": True, "RISQUE_STOP": RISQUE_STOP}
exec(src_sim, ns2)
ns2["sleeves_l4"] = fab
c, s_, d_, m_, a1, a2 = ns2["sim_h4"](interdit=f_or)
sl = capture["sl"]
print("run L4.31 : CAGR %+.1f%% (controle, attendu ~+47)" % c)

# series journalieres par manche + portefeuille
dates_tot = {}
par_manche = {}
for s in sl:
    dm = {}
    for tt, vv in s.pnl.items():
        j = tt.date(); dm[j] = dm.get(j, 0) + vv; dates_tot[j] = dates_tot.get(j, 0) + vv
    par_manche[s.nom] = dm
tous = sorted(dates_tot)
tj = pd.Series([dates_tot[j] for j in tous], index=pd.DatetimeIndex(tous))

# ============ 1. SIMULATEUR FTMO EXACT ============
print()
print("### 1. SIMULATEUR FTMO EXACT (phase 1 +10 % -> phase 2 +5 %) ###")
vals = tj.values
def phase(i0, cible):
    """retourne (reussi, i_fin, jours_trades) ; regles : jour -5 % (sur equite
    de debut de jour), total -10 % du solde initial de la phase, cible atteinte."""
    eq = 1.0; jours = 0
    for i in range(i0, len(vals)):
        r = vals[i]
        if abs(r) > 1e-9: jours += 1
        if r <= -0.05: return (False, i, jours)          # perte jour (equite debut jour)
        eq *= (1 + r)
        if eq <= 0.90: return (False, i, jours)          # perte totale 10 %
        if eq >= 1.0 + cible and jours >= 4: return (True, i, jours)
    return (None, len(vals)-1, jours)                    # donnees epuisees
p1 = p2 = tout = 0; n = 0; durees = []
for i0 in range(0, len(vals) - 90, 5):                   # un depart par semaine
    ok1, i1, j1 = phase(i0, 0.10)
    if ok1 is None: break
    n += 1
    if not ok1: continue
    p1 += 1
    ok2, i2, j2 = phase(i1 + 1, 0.05)
    if ok2: p2 += 1; tout += 1; durees.append((i2 - i0))
    elif ok2 is None: p2 += 1; tout += 1                 # phase 2 en cours, non morte
print("  departs testes            : %d" % n)
print("  phase 1 reussie (+10 %%)   : %.0f %%" % (100*p1/n))
print("  phase 1+2 reussies        : %.0f %%  <- LE chiffre FTMO complet" % (100*tout/n))
print("  duree mediane (les 2)     : %s jours de calendrier boursier" %
      (int(np.median(durees)) if durees else "n/a"))
print("  (rappel : ancien proxy 'fenetres +10/-8' donnait ~85 %)")

# ============ 2. CONCENTRATION DES GAINS ============
print()
print("### 2. RETRAIT DES MEILLEURS JOURS (concentration) ###")
lr = np.log1p(tj)
part5 = lr.nlargest(5).sum() / lr.sum() * 100
part10 = lr.nlargest(10).sum() / lr.sum() * 100
print("  part des 5 meilleurs jours dans le log-rendement total : %.0f %%" % part5)
print("  part des 10 meilleurs : %.0f %%" % part10)
for k in (5, 10, 20):
    t2 = tj.drop(tj.nlargest(k).index)
    ans = (t2.index[-1]-t2.index[0]).days/365.25
    cagr2 = ((1+t2).prod()**(1/ans)-1)*100
    print("  CAGR sans les %2d meilleurs jours : %+5.1f %% (ref %+5.1f %%)" % (k, cagr2, c))

# ============ 3. RISQUE AGREGE AU STOP ============
print()
print("### 3. RISQUE AGREGE SI TOUS LES STOPS SAUTENT D'UN COUP ###")
rs = pd.Series([r for _, r in RISQUE_STOP])
print("  echantillons (1/jour)      : %d" % len(rs))
print("  risque agrege moyen        : %.2f %% de l'equite" % (rs.mean()*100))
print("  95e percentile             : %.2f %%" % (rs.quantile(0.95)*100))
print("  MAXIMUM historique         : %.2f %%   (perte jour FTMO = 5 %%)" % (rs.max()*100))

# ============ 4. CORRELATION DE STRESS ============
print()
print("### 4. CORRELATIONS SUR LES 5 %% PIRES JOURS ###")
df = pd.DataFrame({nom: pd.Series({pd.Timestamp(k): v for k, v in dm.items()})
                   for nom, dm in par_manche.items()}).reindex(tj.index).fillna(0.0)
seuil = tj.quantile(0.05)
stress = df[tj <= seuil]
paires = [("BTC Cassure", "BTC EMA"), ("Or", "Nasdaq"), ("BTC Cassure", "Nasdaq"),
          ("Or", "BTC Cassure"), ("Petrole", "BTC Cassure")]
print("  %-28s | %-10s | %s" % ("Paire", "10 ans", "pires 5 % des jours"))
for a, b in paires:
    c_tot = df[a].corr(df[b])
    c_str = stress[a].corr(stress[b])
    print("  %-28s | %+9.2f | %+9.2f" % (a + " / " + b, c_tot, c_str))
