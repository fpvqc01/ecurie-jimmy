# -*- coding: utf-8 -*-
"""BANC GROKBOT1 -- les trois points du plan de banc du comite no 4 qui
n'avaient jamais ete executes, tous issus des propositions de Grok.

Contexte (RAPPORT_COMITE_L8_VITESSE.md, 21 aout 2026). Le comite externe
(ChatGPT / Grok / Gemini) avait laisse un plan de banc en 6 points. Un seul
a ete fait : l'ancre roulante (Grok no 1), REJETEE (voir Jimmy R2 :
"+18 j et -5 pts de CAGR a K=2,0"). Les points 4, 5 et 6 dorment depuis :

  4. REENGAGEMENT APRES UNE SORTIE GAGNANTE (Grok no 5)
     Apres une sortie en PROFIT, memoriser le sommet atteint pendant le
     trade, puis rentrer de nouveau des que le prix depasse ce sommet
     + K x ATR. Jamais de reentree immediate.

  5. CANAL DE SORTIE RAPIDE + REENGAGEMENT
     Le canal 7 jours seul avait ete rejete (le plus rapide du banc mais
     la reussite s'ecroulait). Gemini proposait de le REPARER en lui
     collant le reengagement comme filet. Point 5 du plan.

  6. COUPE-TEMPS CONDITIONNEL (les 3 IA)
     Jamais fermer par l'age. Fermer par ABSENCE DE PROGRES : si apres
     N barres le meilleur profit atteint n'a jamais depasse S x ATR,
     la position est fermee et le capital repart ailleurs.

Les trois ne touchent que les robots de CASSURE (BTC brk, Petrole) --
ceux qui ont un stop suiveur et aucun TP. Regle du labo : jamais de
mecanisme de tenue de position sur les robots fib/TP (or, Nasdaq).

Standards de validation appliques (les 4 du README) :
  1. principe economique externe -> continuation de tendance (Turtles) et
     cout d'opportunite du capital ; aucune idee nee de l'optimisation ;
  2. amelioration nette AVEC les frais reels -> portes par le moteur ;
  3. stabilite sur les DEUX fenetres ET sur les parametres voisins ;
  4. amelioration au niveau du PORTEFEUILLE sous le plafond de 2.

Critere fixe D'AVANCE par le comite : on ne retient une variante que si
la reussite du challenge ne baisse pas ET que la duree mediane baisse.
Le GIVE-BACK (meilleur profit atteint - profit realise) est mesure comme
statistique officielle, comme le demande le rapport.

Donnees : Yahoo Finance, 10 ans de barres journalieres, cache local dans
backtests/.cache_yahoo/. Deux fenetres, comme banc_L8 : 10 ans et 2021-2026.

Lancer :  python3 banc_comite_points456.py
"""
import os, json, numpy as np, pandas as pd

D = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(D, ".cache_yahoo")

# ------------------------------------------------------------------
# 1. Le moteur du labo, charge tel quel (convention maison : exec de la
#    source tronquee avant les prints). Seule la ligne de telechargement
#    est remplacee : 10 ans au lieu de 5, avec cache disque.
# ------------------------------------------------------------------
LIGNE_FETCH = 'btc, gc, nq, cl = fetch("BTC-USD"), fetch("GC=F"), fetch("NQ=F"), fetch("CL=F")'
REMPLACEMENT = '''
import os as _os, time as _time
_C = %r
_os.makedirs(_C, exist_ok=True)
def _fetch10(sym):
    """Meme appel que fetch(), mais sur 10 ans et avec cache disque."""
    f = _os.path.join(_C, sym.replace("=", "_").replace("-", "_") + "_10y.csv")
    if _os.path.exists(f):
        return pd.read_csv(f, index_col=0, parse_dates=True)
    derniere = None
    for hote in ("query1", "query2"):
        for essai in range(3):
            try:
                r = requests.get(
                    "https://%%s.finance.yahoo.com/v8/finance/chart/%%s" %% (hote, sym),
                    params={"range": "10y", "interval": "1d"},
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
                    timeout=60)
                r.raise_for_status()
                d = r.json()["chart"]["result"][0]
                q = d["indicators"]["quote"][0]
                df = pd.DataFrame({"t": pd.to_datetime(d["timestamp"], unit="s").normalize(),
                                   "o": q["open"], "h": q["high"],
                                   "l": q["low"], "c": q["close"]}
                                  ).dropna().drop_duplicates("t").set_index("t")
                df.to_csv(f)
                return df
            except Exception as e:
                derniere = e
                _time.sleep(3 * (essai + 1))
    raise RuntimeError("Yahoo injoignable pour %%s : %%r" %% (sym, derniere))
btc, gc, nq, cl = _fetch10("BTC-USD"), _fetch10("GC=F"), _fetch10("NQ=F"), _fetch10("CL=F")
''' % CACHE

def charger_moteur():
    src = open(os.path.join(D, "optimisation_finale.py"), encoding="utf-8").read()
    src = src.split('print(f"{\'Config\'')[0]
    assert LIGNE_FETCH in src, "ANCRE FETCH INTROUVABLE dans optimisation_finale.py"
    src = src.replace(LIGNE_FETCH, REMPLACEMENT)
    ns = {"__file__": os.path.join(D, "optimisation_finale.py"), "__name__": "moteur_grok"}
    exec(compile(src, "optimisation_finale.py", "exec"), ns)
    return ns

M = charger_moteur()
Donch, Fib, EmaBTC = M["Donch"], M["Fib"], M["EmaBTC"]
BTC, GC, NQ, CL = M["btc"], M["gc"], M["nq"], M["cl"]

CASSURES = ("Petrole", "BTC brk")     # les seuls robots eligibles

# ------------------------------------------------------------------
# 2. Instrumentation : sommet, MFE et give-back de chaque trade.
#    Pure observation -- ne change AUCUNE decision.
# ------------------------------------------------------------------
def instrumenter(s):
    o0, g0, c0 = s.ouvrir, s.gerer, s._clore
    s.journal = []
    def ouvrir(date, entree, stop, **k):
        ok = o0(date, entree, stop, **k)
        if ok:
            i = s.jour(date)
            s.pos.update(t0=date, i0=i, sommet=entree, mfe=0.0,
                         atr0=float(s.a.iloc[i]) if i is not None else np.nan,
                         risque_pt=entree - stop)
            s.reeng_sommet = None          # une entree prise desarme le reengagement
        return ok
    def gerer(date):
        p, i = s.pos, s.jour(date)
        if p is not None and i is not None and "sommet" in p:
            h = float(s.df["h"].iloc[i])
            if h > p["sommet"]: p["sommet"] = h
            p["mfe"] = max(p["mfe"], h - p["e"])
        g0(date)
    def clore(date, prix):
        p = s.pos
        if p is not None and "risque_pt" in p:
            rp = p["risque_pt"] if p["risque_pt"] > 0 else np.nan
            j = s.jour(date)
            s.journal.append(dict(
                nom=s.nom, barres=(j - p["i0"]) if j is not None else np.nan,
                pnl_R=(prix - p["e"]) / rp, mfe_R=p["mfe"] / rp,
                mfe_atr=p["mfe"] / p["atr0"] if p["atr0"] > 0 else np.nan,
                gagnant=bool(prix > p["e"])))
        c0(date, prix)
    s.ouvrir, s.gerer, s._clore = ouvrir, gerer, clore
    s.reeng_sommet = None
    return s

# ------------------------------------------------------------------
# 3. POINT 4 -- reengagement apres une sortie gagnante (Grok no 5)
# ------------------------------------------------------------------
def reengagement(s, k_atr, fenetre=None):
    """Arme une reentree apres CHAQUE sortie en profit ; elle part quand le
    prix depasse le sommet du trade precedent + k_atr x ATR. La cassure
    reste prioritaire. `fenetre` (barres) borne la validite, None = illimite.
    Compteurs : reeng_arme (occasions), reeng_pris (entrees reellement dues
    au mecanisme), reeng_double (fois ou la cassure tirait le meme jour)."""
    c0, sig0 = s._clore, s.signal
    s.reeng_i = None
    s.reeng_arme = s.reeng_pris = s.reeng_double = 0
    def clore(date, prix):
        p = s.pos
        if p is not None and prix > p["e"]:            # sortie GAGNANTE seulement
            s.reeng_sommet = p.get("sommet", prix)
            s.reeng_i = s.jour(date)
            s.reeng_arme += 1
        c0(date, prix)
    def signal(date):
        r = sig0(date)
        if s.reeng_sommet is None:
            return r
        i = s.jour(date)
        if i is None or i < 25:
            return r
        if fenetre is not None and s.reeng_i is not None and (i - s.reeng_i) > fenetre:
            s.reeng_sommet = None
            return r
        c, a = float(s.df["c"].iloc[i]), float(s.a.iloc[i])
        if not (a > 0) or c <= s.reeng_sommet + k_atr * a:
            return r                                    # seuil pas atteint
        if r is not None:
            s.reeng_double += 1                         # la cassure tire aussi
            return r                                    # ... et elle prime
        stop = float(s.b10.iloc[i])
        if stop >= c:
            return None
        s.reeng_pris += 1
        return dict(entree=c, stop=stop, trail=True, sortie_cloture=True)
    s._clore, s.signal = clore, signal
    return s

# ------------------------------------------------------------------
# 4. POINT 5 -- canal de sortie rapide (7 ou 5 jours au lieu de 10)
# ------------------------------------------------------------------
def canal_sortie(s, jours):
    """Remplace le canal de sortie 10 jours. b10 sert a la fois de stop
    initial, de stop suiveur et de sortie en cloture : le changer ici
    change les trois d'un coup, comme dans le robot."""
    s.b10 = s.df["l"].rolling(jours).min().shift(1)
    return s

# ------------------------------------------------------------------
# 5. POINT 6 -- coupe-temps conditionnel (absence de progres)
# ------------------------------------------------------------------
def coupe_temps(s, barres, seuil_atr):
    g0 = s.gerer
    s.coupes = 0
    def gerer(date):
        g0(date)                                        # stop / trail d'abord
        p, i = s.pos, s.jour(date)
        if p is None or i is None or "i0" not in p:
            return
        if (i - p["i0"]) < barres:
            return
        a0 = p.get("atr0", np.nan)
        if not (a0 > 0) or p["mfe"] >= seuil_atr * a0:
            return
        s.coupes += 1
        s._clore(date, float(s.df["c"].iloc[i]))
        s.attente = None
    s.gerer = gerer
    return s

# ------------------------------------------------------------------
# 6. Le portefeuille du labo (config H : jimmy=True, cap 2, reglages KW2)
# ------------------------------------------------------------------
KW2 = dict(tpj_or=2.0, tpj_nq=1.0, tpj_ema=2.0)

def fabriquer(reeng=None, coupe=None, canal=None, m=1.0):
    sleeves = [
        Fib("Or", GC, 0.01*m, 0.0001, -0.000273, 1.4, jimmy=True, retrace=0.25,
            tpj=KW2["tpj_or"], lookback=10, fib=(0.2, 0.8), pull=55, mult=3.0, tpr=2.0),
        Donch("Petrole", CL, 0.005*m, 0.00045, +0.000051, 1.4, saison=(1201, 531)),
        Donch("BTC brk", BTC, 0.005*m, 0.0004, -0.000833, 1.0),
        Fib("Nasdaq", NQ, 0.01*m, 0.00003, -0.000213, 1.4, jimmy=True, retrace=0.5,
            tpj=KW2["tpj_nq"], lookback=7, fib=(0.1, 0.9), pull=60, mult=2.0, tpr=2.0),
        EmaBTC("BTC ema", BTC, 0.005*m, 0.0004, -0.000833, 1.0, jimmy=True,
               retrace=0.25, tpj=KW2["tpj_ema"]),
    ]
    for s in sleeves:
        if s.nom in CASSURES and canal:
            canal_sortie(s, canal)          # avant tout : change les series
        instrumenter(s)                     # puis l'observation...
        if s.nom in CASSURES:               # ...puis les mecanismes
            if coupe: coupe_temps(s, *coupe)
            if reeng: reengagement(s, *reeng)
    return sleeves

def simuler(reeng=None, coupe=None, canal=None, m=1.0, cap=2, depuis=None, jusqua=None):
    sleeves = fabriquer(reeng, coupe, canal, m)
    dates = sorted(set().union(*[s.df.index for s in sleeves]))
    if depuis is not None:
        dates = [d for d in dates if d >= pd.Timestamp(depuis)]
    if jusqua is not None:
        dates = [d for d in dates if d < pd.Timestamp(jusqua)]
    for date in dates:
        for s in sleeves: s.gerer(date)
        ouverts = sum(1 for s in sleeves if s.pos is not None)
        for s in sleeves:
            if s.pos is not None: continue
            sig = s.signal(date)
            if sig is None: continue
            if cap is not None and ouverts >= cap: continue
            if s.ouvrir(date, **sig): ouverts += 1
    total = pd.Series(0.0, index=pd.DatetimeIndex(dates))
    for s in sleeves:
        for dt, v in s.pnl.items():
            if dt in total.index: total[dt] += v
    return total, sleeves

# ------------------------------------------------------------------
# 7. Mesures : metriques du labo + challenge FTMO 2 phases
#    (phase() / ftmo() repris tels quels de banc_L8, la reference maison)
# ------------------------------------------------------------------
def phase(v, i0, cible):
    eq, jt = 1.0, 0
    for j in range(i0, len(v)):
        r = v[j]
        if r != 0.0: jt += 1
        if r <= -0.05: return 0, j - i0 + 1        # limite journaliere FTMO
        eq *= (1 + r)
        if eq <= 0.90: return 0, j - i0 + 1        # limite totale FTMO
        if eq >= 1 + cible and jt >= 4: return 1, j - i0 + 1
    return -1, len(v) - i0

def ftmo(total):
    v = total.values
    ok = mort = 0
    d = []
    for i0 in range(0, max(len(v) - 60, 1), 3):
        v1, d1 = phase(v, i0, 0.10)
        if v1 == -1: continue
        if v1 == 0: mort += 1; continue
        v2, d2 = phase(v, i0 + d1, 0.05)
        if v2 == -1: continue
        if v2 == 0: mort += 1; continue
        ok += 1; d.append(d1 + d2)
    n = ok + mort
    return (100.0 * ok / max(n, 1)), (float(np.median(d)) if d else float("nan")), n

def mesurer(total, sleeves):
    eq = (1 + total).cumprod()
    annees = len(total) / 365.25
    cagr = (eq.iloc[-1] ** (1 / annees) - 1) * 100
    dd = (eq / eq.cummax() - 1).min() * 100
    pire = total.min() * 100
    sh = total.mean() / total.std() * np.sqrt(365) if total.std() > 0 else 0.0
    reussite, duree, n = ftmo(total)
    j = [t for s in sleeves if s.nom in CASSURES for t in s.journal]
    gb = float("nan")
    if j:
        mfe = float(np.nansum([t["mfe_R"] for t in j]))
        rea = float(np.nansum([max(t["pnl_R"], 0.0) for t in j]))
        gb = 100.0 * (mfe - rea) / mfe if mfe > 0 else float("nan")
    return dict(cagr=cagr, dd=dd, pire=pire, sharpe=sh, reussite=reussite,
                duree=duree, nchal=n, giveback=gb,
                trades=sum(s.trades for s in sleeves),
                trades_cassure=sum(s.trades for s in sleeves if s.nom in CASSURES),
                reeng_arme=sum(getattr(s, "reeng_arme", 0) for s in sleeves),
                reeng_pris=sum(getattr(s, "reeng_pris", 0) for s in sleeves),
                reeng_double=sum(getattr(s, "reeng_double", 0) for s in sleeves),
                coupes=sum(getattr(s, "coupes", 0) for s in sleeves))

# ------------------------------------------------------------------
# 8. Le banc
# ------------------------------------------------------------------
VARIANTES = [
    ("REFERENCE (config H du labo)",             None,     None,        None),
    # -- point 4 : le reengagement, plateau de K (standard 3)
    ("P4 reengagement +0,25 ATR",                (0.25,),  None,        None),
    ("P4 reengagement +0,50 ATR   (Grok)",       (0.50,),  None,        None),
    ("P4 reengagement +1,00 ATR   (Grok)",       (1.00,),  None,        None),
    ("P4 reengagement +1,50 ATR",                (1.50,),  None,        None),
    # -- point 5 : canal rapide seul, puis repare par le reengagement
    ("P5 canal sortie 7 j seul",                 None,     None,        7),
    ("P5 canal sortie 5 j seul",                 None,     None,        5),
    ("P5 canal 7 j + reeng +0,50 ATR",           (0.50,),  None,        7),
    ("P5 canal 7 j + reeng +1,00 ATR",           (1.00,),  None,        7),
    ("P5 canal 5 j + reeng +0,50 ATR",           (0.50,),  None,        5),
    # -- point 6 : coupe-temps conditionnel, plateau (standard 3)
    ("P6 coupe-temps  8 b / 0,75 ATR (comite)",  None,     (8, 0.75),   None),
    ("P6 coupe-temps 12 b / 1,00 ATR (comite)",  None,     (12, 1.00),  None),
    ("P6 coupe-temps  8 b / 1,50 ATR",           None,     (8, 1.50),   None),
    ("P6 coupe-temps 12 b / 2,00 ATR",           None,     (12, 2.00),  None),
    ("P6 coupe-temps 20 b / 3,00 ATR",           None,     (20, 3.00),  None),
    # -- les trois idees ensemble
    ("P4+5+6 canal 7 j + 0,50 ATR + 12 b/2 ATR", (0.50,),  (12, 2.00),  7),
]

FENETRES = (("10 ANS", None, None),
            ("moitie 1 (2016-2021)", None, "2021-01-01"),
            ("moitie 2 (2021-2026)", "2021-01-01", None))

EN_TETE = ("%-43s | %7s %7s %7s %6s | %6s %6s %4s | %6s %6s"
           % ("variante", "CAGR", "DD", "pireJ", "Sharpe",
              "reussi", "duree", "n", "giveb.", "trades"))

def ligne(nom, r):
    return ("%-43s | %+6.1f %% %6.1f %% %6.2f %% %6.2f | %5.0f %% %4.0f j %4d | %5.1f %% %6d"
            % (nom, r["cagr"], r["dd"], r["pire"], r["sharpe"],
               r["reussite"], r["duree"], r["nchal"], r["giveback"], r["trades"]))

def main():
    print(__doc__.split("Lancer")[0].strip())
    resultats = {}
    for titre, depuis, jusqua in FENETRES:
        print()
        print("=" * len(EN_TETE))
        print("BANC GROKBOT1 -- %s -- portefeuille complet, plafond de 2, frais reels"
              % titre)
        print("=" * len(EN_TETE))
        print(EN_TETE)
        print("-" * len(EN_TETE))
        for nom, reeng, coupe, canal in VARIANTES:
            total, sleeves = simuler(reeng=reeng, coupe=coupe, canal=canal,
                                     depuis=depuis, jusqua=jusqua)
            r = mesurer(total, sleeves)
            resultats.setdefault(nom, {})[titre] = r
            print(ligne(nom, r))

    # ---- ce que les compteurs disent des mecanismes eux-memes
    print()
    print("=" * len(EN_TETE))
    print("COMPTEURS -- combien de fois chaque mecanisme a REELLEMENT agi (10 ans)")
    print("=" * len(EN_TETE))
    print("%-43s | %9s %9s %9s %9s" % ("variante", "arme", "pris", "double", "coupes"))
    print("-" * len(EN_TETE))
    for nom, _, _, _ in VARIANTES:
        r = resultats[nom]["10 ANS"]
        if r["reeng_arme"] or r["coupes"]:
            print("%-43s | %9d %9d %9d %9d"
                  % (nom, r["reeng_arme"], r["reeng_pris"], r["reeng_double"], r["coupes"]))

    # ---- verdict contre les criteres fixes d'avance
    ref = resultats["REFERENCE (config H du labo)"]
    print()
    print("=" * len(EN_TETE))
    print("VERDICT -- criteres fixes D'AVANCE par le comite (RAPPORT_COMITE_L8_VITESSE)")
    print("  Le comite exigeait : reussite qui ne baisse pas ET duree mediane en baisse.")
    print("  Operationnalise ici, sur les TROIS fenetres (standard 3 du README) :")
    print("    a. CAGR      : ne baisse sur AUCUNE fenetre (tolerance 0,1 pt)")
    print("    b. reussite  : ne baisse sur AUCUNE fenetre (tolerance 0,5 pt)")
    print("    c. duree     : ne monte sur AUCUNE fenetre, et baisse sur au moins une")
    print("=" * len(EN_TETE))
    TOL_C, TOL_R, TOL_D = 0.1, 0.5, 1.0
    retenus = []
    for nom, _, _, _ in VARIANTES:
        if nom.startswith("REFERENCE"):
            continue
        motifs, baisse_duree = [], False
        for titre, _, _ in FENETRES:
            r, r0 = resultats[nom][titre], ref[titre]
            if r["cagr"] < r0["cagr"] - TOL_C:
                motifs.append("%-20s CAGR %+.2f vs %+.2f" % (titre, r["cagr"], r0["cagr"]))
            if r["reussite"] < r0["reussite"] - TOL_R:
                motifs.append("%-20s reussite %.1f vs %.1f" % (titre, r["reussite"], r0["reussite"]))
            if r["duree"] > r0["duree"] + TOL_D:
                motifs.append("%-20s duree %.0f j vs %.0f j" % (titre, r["duree"], r0["duree"]))
            if r["duree"] < r0["duree"] - TOL_D:
                baisse_duree = True
        if not baisse_duree:
            motifs.append("duree jamais en baisse (le mecanisme ne sert pas la vitesse)")
        if motifs:
            print("  REJETE  %s" % nom)
            for mo in motifs:
                print("            %s" % mo)
        else:
            print("  RETENU  %s" % nom)
            for titre, _, _ in FENETRES:
                r, r0 = resultats[nom][titre], ref[titre]
                print("            %-20s CAGR %+.2f (ref %+.2f) | duree %.0f j (ref %.0f j)"
                      " | reussite %.1f (ref %.1f)"
                      % (titre, r["cagr"], r0["cagr"], r["duree"], r0["duree"],
                         r["reussite"], r0["reussite"]))
            retenus.append(nom)
    if not retenus:
        print()
        print("  Aucune variante ne passe. Les points 4, 5 et 6 du plan de banc")
        print("  du comite rejoignent le cimetiere. Un resultat negatif est un")
        print("  resultat : c'est exactement ce que le banc doit produire.")

    with open(os.path.join(D, "resultats_comite_points456.json"), "w", encoding="utf-8") as f:
        json.dump({"variantes": resultats, "retenus": retenus}, f, indent=2, default=float)
    print()
    print("Resultats bruts : backtests/resultats_comite_points456.json")

if __name__ == "__main__":
    main()
