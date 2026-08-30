# -*- coding: utf-8 -*-
"""BANC GROKBOT -- la lignee NEUVE, batie a partir de rien.

Pourquoi une lignee de plus, alors que l'ecurie compte deja 30 generations ?
Parce qu'elles partagent toutes le meme angle mort, nomme dans le README :
l'ecurie est 100 % ACHETEUSE sur des actifs de risque (BTC, or, Nasdaq,
petrole). Elle n'a aucun robot capable de gagner quand le risque baisse.

GROKBOT EST CONSTRUIT POUR ETRE CE ROBOT-LA. Ce n'est pas une variante d'un
robot existant : c'est un chassis neuf, deux sens (achat ET vente), sur le
territoire FX -- la classe d'actifs menee par les cycles de politique
monetaire plutot que par l'appetit pour le risque.

PRINCIPE ECONOMIQUE EXTERNE (standard 1) : le momentum de serie temporelle
(Moskowitz-Ooi-Pedersen 2012 ; un siecle de donnees AQR) fonctionne DANS LES
DEUX SENS. Le README a rejete le TSMOM comme FILTRE de regime plaque sur des
robots deja suiveurs de tendance -- ce n'est pas le meme usage : ici c'est la
strategie elle-meme, sur un territoire ou l'ecurie n'a rien.

CE QUE LE BANC FAIT
  1. criblage : 3 familles de regles x leurs voisins x 6 paires, 10 ans,
     frais reels, sur les DEUX moities (standards 1-3) ;
  2. portefeuille : la meilleure regle ajoutee a l'ecurie sous le plafond
     de 2 positions, pour verifier qu'elle ne vole pas de sieges (standard 4).

LES FRAIS, DEFENDABLES ET PESSIMISTES
  Commission 2,5 $/lot/cote et spread ~0,3 pip, releves dans les specs MT5
  (README, section GBPUSD) -> 0,0036 % de notionnel par cote.
  Swap : -0,010 %/jour DES DEUX COTES. C'est l'hypothese PESSIMISTE que le
  README reclame lui-meme ("la majoration du courtier peut annuler le
  carry") : aucune paire ne recoit de credit de portage. Une sensibilite
  avec le portage documente de l'USDJPY est mesuree a part.

Donnees : Yahoo Finance, 10 ans de barres journalieres, cache local.
Lancer :  python3 banc_grokbot.py
"""
import os, json, time, math
import numpy as np, pandas as pd, requests

D = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(D, ".cache_yahoo")

# ------------------------------------------------------------------
# 1. Donnees
# ------------------------------------------------------------------
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})

def charger(sym, rng="10y"):
    os.makedirs(CACHE, exist_ok=True)
    f = os.path.join(CACHE, sym.replace("=", "_").replace("-", "_") + "_10y.csv")
    if os.path.exists(f):
        return pd.read_csv(f, index_col=0, parse_dates=True)
    derniere = None
    for hote in ("query1", "query2"):
        for essai in range(3):
            try:
                r = SESSION.get("https://%s.finance.yahoo.com/v8/finance/chart/%s" % (hote, sym),
                                params={"range": rng, "interval": "1d"}, timeout=60)
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
                time.sleep(3 * (essai + 1))
    raise RuntimeError("Yahoo injoignable pour %s : %r" % (sym, derniere))

PAIRES = {
    "USDJPY": "JPY=X",     "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X",
    "AUDJPY": "AUDJPY=X",  "AUDUSD": "AUDUSD=X", "USDCHF": "USDCHF=X",
}

FRAIS_COTE = 0.000036      # commission 2,5 $/lot/cote + demi-spread 0,3 pip
SWAP_JOUR  = -0.00010      # -0,010 %/jour DES DEUX COTES (hypothese pessimiste)
FS_WEEKEND = 1.4           # jour de swap triple, comme dans le moteur du labo

# ------------------------------------------------------------------
# 2. Indicateurs (memes formules que le moteur du labo)
# ------------------------------------------------------------------
def wilder(s, n): return s.ewm(alpha=1.0 / n, adjust=False).mean()

def atr_(df, n=14):
    tr = np.maximum(df["h"] - df["l"],
                    np.maximum((df["h"] - df["c"].shift()).abs(),
                               (df["l"] - df["c"].shift()).abs()))
    return wilder(tr, n)

# ------------------------------------------------------------------
# 3. MANCHE DEUX SENS -- le coeur neuf de GrokBot.
#    Convention de P/L identique au moteur du labo (fraction du capital
#    par jour, taille = risque / distance de stop, plafonnee a 2x le
#    notionnel), pour que les series soient additionnables a l'ecurie.
# ------------------------------------------------------------------
class MancheBi:
    def __init__(self, nom, df, risque=0.0075, frais=FRAIS_COTE,
                 swap=SWAP_JOUR, fs=FS_WEEKEND, swap_achat=None, swap_vente=None,
                 regle=None, breakeven_r=0.0, repli_atr=0.0, repli_fenetre=0,
                 retard=False):
        self.nom, self.df = nom, df
        self.regle = regle
        self.breakeven_r = breakeven_r      # GrokBot2 : stop au point mort a +N x R
        self.repli_atr = repli_atr          # GrokBot2 : reentree apres TP sur repli
        self.repli_fenetre = repli_fenetre
        self.attente = None                 # (sens, prix de sortie, barres restantes)
        self.retard = retard                # entree a l'ouverture SUIVANTE
        self._att = None                    # (barre du signal, signal)
        self.risque, self.frais, self.fs = risque, frais, fs
        self.swap_achat = swap if swap_achat is None else swap_achat
        self.swap_vente = swap if swap_vente is None else swap_vente
        self.idx = {d: i for i, d in enumerate(df.index)}
        self.O = df["o"].values; self.H = df["h"].values
        self.L = df["l"].values; self.C = df["c"].values
        self.A = atr_(df).values
        self.pos, self.pnl, self.trades = None, {}, 0
        self.journal = []

    # -- indicateurs a la demande, caches
    def canal(self, n, quoi):
        cle = ("canal", n, quoi)
        if cle not in self.__dict__.setdefault("_c", {}):
            s = self.df["h"] if quoi == "haut" else self.df["l"]
            v = (s.rolling(n).max() if quoi == "haut" else s.rolling(n).min()).shift(1)
            self._c[cle] = v.values
        return self._c[cle]

    def ema(self, n):
        cle = ("ema", n)
        if cle not in self.__dict__.setdefault("_c", {}):
            self._c[cle] = self.df["c"].ewm(span=n, adjust=False).mean().values
        return self._c[cle]

    def rendement(self, n):
        cle = ("ret", n)
        if cle not in self.__dict__.setdefault("_c", {}):
            self._c[cle] = (self.df["c"] / self.df["c"].shift(n) - 1.0).values
        return self._c[cle]

    # -- mecanique
    def _ajouter(self, date, v):
        self.pnl[date] = self.pnl.get(date, 0.0) + v

    def _clore(self, date, prix, motif):
        p = self.pos
        self._ajouter(date, p["sens"] * p["n"] * (prix - p["marque"]) / p["e"]
                            - self.frais * p["n"])
        rp = p["r0"]
        self.journal.append(dict(nom=self.nom, sens=p["sens"], motif=motif,
                                 pnl_R=p["sens"] * (prix - p["e"]) / rp if rp > 0 else np.nan,
                                 barres=self.idx.get(date, 0) - p["i0"]))
        self.pos = None

    def ouvrir(self, date, sens, entree, stop, tp=None, trail=None):
        r0 = abs(entree - stop)
        if r0 <= 0 or r0 > 0.5 * entree:
            return False
        n = min(self.risque / (r0 / entree), 2.0)
        self._ajouter(date, -self.frais * n)
        self.pos = dict(sens=sens, e=entree, s=stop, tp=tp, n=n, marque=entree,
                        trail=trail, i0=self.idx.get(date, 0), r0=r0, be_fait=False)
        self.trades += 1
        return True

    def signal(self, date):
        """Branchement sur le moteur du labo : meme signature que ses manches.

        Si retard=True, le signal calcule sur la bougie fermee n'est PAS
        joue a sa cloture (un robot ne peut pas) : il est rejoue a
        l'OUVERTURE de la bougie suivante, avec la meme distance de stop
        appliquee au prix reellement obtenu. Un signal plus vieux d'une
        barre est jete -- c'est ce qui evite de rentrer sur un signal
        perime apres une position."""
        i = self.idx.get(date)
        if i is None or self.regle is None:
            return None
        if self.retard:
            prec = self._att
            brut = self._brut(date)
            self._att = (i, brut) if brut is not None else None
            if prec is None or prec[0] != i - 1:
                return None
            sig, o = prec[1], self.O[i]
            R = abs(sig["entree"] - sig["stop"])
            if o <= 0 or R <= 0:
                return None
            sens = sig["sens"]
            tpr = (abs(sig["tp"] - sig["entree"]) / R) if sig.get("tp") else 0.0
            return dict(sens=sens, entree=o, stop=o - sens * R,
                        tp=(o + sens * tpr * R) if tpr else None, trail=sig.get("trail"))
        return self._brut(date)

    def _brut(self, date):
        i = self.idx.get(date)
        if i is None or self.regle is None:
            return None
        if self.pos is None and self.attente is not None:
            sens, sortie, reste = self.attente
            a = self.A[i]
            if reste <= 0 or math.isnan(a) or a <= 0:
                self.attente = None
            else:
                self.attente = (sens, sortie, reste - 1)
                vise = sortie - self.repli_atr * a if sens > 0 else sortie + self.repli_atr * a
                touche = (self.L[i] <= vise) if sens > 0 else (self.H[i] >= vise)
                if touche:
                    c, R = self.C[i], 2.0 * a
                    self.attente = None
                    return dict(sens=sens, entree=c,
                                stop=c - R if sens > 0 else c + R,
                                tp=(c + 1.5 * R) if sens > 0 else (c - 1.5 * R))
        return self.regle(self, i)

    def gerer(self, date):
        i = self.idx.get(date)
        if i is None or self.pos is None:
            return
        p = self.pos
        c, h, l = self.C[i], self.H[i], self.L[i]
        sens = p["sens"]

        # stop suiveur : canal oppose, jamais dans le mauvais sens
        if p["trail"]:
            n = p["trail"]
            niv = self.canal(n, "bas")[i] if sens > 0 else self.canal(n, "haut")[i]
            if not math.isnan(niv):
                p["s"] = max(p["s"], niv) if sens > 0 else min(p["s"], niv)

        # stop d'abord (hypothese prudente : le pire des deux le meme jour)
        if (sens > 0 and l <= p["s"]) or (sens < 0 and h >= p["s"]):
            self._clore(date, p["s"], "stop")
            return
        if p["tp"] is not None and ((sens > 0 and h >= p["tp"]) or (sens < 0 and l <= p["tp"])):
            tp = p["tp"]
            self._clore(date, tp, "tp")
            if self.repli_atr > 0:          # GrokBot2 : on garde le regime en memoire
                self.attente = (sens, tp, self.repli_fenetre)
            return

        # GrokBot2 : point mort verrouille des +N x R (ne coupe jamais la queue,
        # il ne fait que retirer le risque de la table)
        if self.breakeven_r > 0 and not p.get("be_fait"):
            seuil = p["e"] + sens * self.breakeven_r * p["r0"]
            if (sens > 0 and h >= seuil) or (sens < 0 and l <= seuil):
                p["s"] = max(p["s"], p["e"]) if sens > 0 else min(p["s"], p["e"])
                p["be_fait"] = True

        swap = self.swap_achat if sens > 0 else self.swap_vente
        self._ajouter(date, sens * p["n"] * (c - p["marque"]) / p["e"] + swap * self.fs * p["n"])
        p["marque"] = c

# ------------------------------------------------------------------
# 4. Les trois familles de regles. Chacune rend un signal ou None.
#    Aucune n'est nee de l'optimisation : chacune a une source.
# ------------------------------------------------------------------
def regle_donchian(entree_n, sortie_n):
    """Turtle deux sens (Dennis/Eckhardt). Cassure de canal, stop suiveur
    sur le canal oppose, jamais de TP -- la queue paie."""
    def f(m, i):
        if i < entree_n + 2: return None
        hh, bb = m.canal(entree_n, "haut")[i], m.canal(entree_n, "bas")[i]
        c = m.C[i]
        if math.isnan(hh) or math.isnan(bb): return None
        if c > hh:
            s = m.canal(sortie_n, "bas")[i]
            if not math.isnan(s) and s < c: return dict(sens=+1, entree=c, stop=s, trail=sortie_n)
        if c < bb:
            s = m.canal(sortie_n, "haut")[i]
            if not math.isnan(s) and s > c: return dict(sens=-1, entree=c, stop=s, trail=sortie_n)
        return None
    return f

def regle_ema(rapide, lente, atr_mult, tp_r):
    """Croisement d'EMA dans les DEUX sens, stop a N x ATR, TP a M x R.
    C'est la forme que le labo avait deja validee sur USDJPY (README,
    section territoire forex) sans jamais l'implementer."""
    def f(m, i):
        if i < lente + 2: return None
        er, el = m.ema(rapide), m.ema(lente)
        a, c = m.A[i], m.C[i]
        if math.isnan(a) or a <= 0: return None
        R = atr_mult * a
        if er[i] > el[i] and er[i-1] <= el[i-1]:
            return dict(sens=+1, entree=c, stop=c - R, tp=(c + tp_r * R) if tp_r else None)
        if er[i] < el[i] and er[i-1] >= el[i-1]:
            return dict(sens=-1, entree=c, stop=c + R, tp=(c - tp_r * R) if tp_r else None)
        return None
    return f

def regle_tsmom(fenetre, atr_mult, sortie_n):
    """Momentum de serie temporelle : le SIGNE du rendement sur `fenetre`
    jours decide du sens. Entree au changement de signe seulement.
    Moskowitz-Ooi-Pedersen 2012."""
    def f(m, i):
        if i < fenetre + 2: return None
        r = m.rendement(fenetre)
        if math.isnan(r[i]) or math.isnan(r[i-1]): return None
        a, c = m.A[i], m.C[i]
        if math.isnan(a) or a <= 0: return None
        R = atr_mult * a
        if r[i] > 0 and r[i-1] <= 0: return dict(sens=+1, entree=c, stop=c - R, trail=sortie_n)
        if r[i] < 0 and r[i-1] >= 0: return dict(sens=-1, entree=c, stop=c + R, trail=sortie_n)
        return None
    return f

# ------------------------------------------------------------------
# 5. Simulation d'une manche seule
# ------------------------------------------------------------------
def simuler_manche(paire, regle, depuis=None, jusqua=None, retard=False, **kw):
    """retard=True : CONTROLE D'EXECUTION. Le banc entre normalement a la
    cloture de la bougie de signal -- un robot reel ne peut pas : il voit la
    bougie fermee puis entre a l'OUVERTURE suivante. Avec retard=True on
    mesure la strategie telle que le robot la vivra vraiment. La distance de
    stop (1 R) est conservee, appliquee au prix reellement obtenu."""
    df = charger(PAIRES[paire])
    if depuis is not None: df = df[df.index >= pd.Timestamp(depuis)]
    if jusqua is not None: df = df[df.index <  pd.Timestamp(jusqua)]
    m = MancheBi(paire, df, regle=regle, retard=retard, **kw)
    for date in df.index:
        m.gerer(date)
        sig = m.signal(date)          # toujours appele : le tampon du retard avance
        if m.pos is not None or sig is None: continue
        m.ouvrir(date, **sig)
    return m

def mesurer_manche(m):
    j = [t for t in m.journal if not math.isnan(t["pnl_R"])]
    if not j:
        return dict(R=0.0, pf=0.0, trades=0, gagnants=0.0, parAn=0.0)
    R = np.array([t["pnl_R"] for t in j])
    gains, pertes = R[R > 0].sum(), -R[R < 0].sum()
    annees = max(len(m.df) / 252.0, 0.1)
    return dict(R=float(R.sum()), pf=float(gains / pertes) if pertes > 0 else float("inf"),
                trades=len(j), gagnants=float(100.0 * (R > 0).mean()),
                parAn=float(len(j) / annees))

# ------------------------------------------------------------------
# 6. Le criblage (standards 1 a 3)
# ------------------------------------------------------------------
FAMILLES = [
    ("Donchian 20/10", regle_donchian(20, 10)),
    ("Donchian 55/20", regle_donchian(55, 20)),
    ("Donchian 40/20", regle_donchian(40, 20)),
    ("EMA 20/50 TP1,5R", regle_ema(20, 50, 2.0, 1.5)),
    ("EMA 20/50 suiveur", regle_ema(20, 50, 2.0, 0.0)),
    ("EMA 10/40 TP1,5R", regle_ema(10, 40, 2.0, 1.5)),
    ("EMA 30/60 TP1,5R", regle_ema(30, 60, 2.0, 1.5)),
    ("TSMOM 252 j", regle_tsmom(252, 3.0, 20)),
    ("TSMOM 126 j", regle_tsmom(126, 3.0, 20)),
]
COUPURE = "2021-08-25"       # milieu des 10 ans

def criblage():
    print("=" * 108)
    print("CRIBLAGE -- 6 paires x 9 regles, deux sens, 10 ans, frais reels pessimistes")
    print("  standard 3 : on ne garde que ce qui est POSITIF sur les DEUX moities")
    print("=" * 108)
    print("%-18s %-9s | %8s %6s %6s %7s | %8s %8s | %s"
          % ("regle", "paire", "R 10ans", "PF", "gagn.", "trades/an",
             "R 1re m.", "R 2e m.", "verdict"))
    print("-" * 108)
    survivants, tout = [], {}
    for nom, regle in FAMILLES:
        for paire in PAIRES:
            m = simuler_manche(paire, regle)
            r = mesurer_manche(m)
            m1 = mesurer_manche(simuler_manche(paire, regle, jusqua=COUPURE))
            m2 = mesurer_manche(simuler_manche(paire, regle, depuis=COUPURE))
            ok = (r["R"] > 0 and m1["R"] > 0 and m2["R"] > 0 and r["pf"] >= 1.3
                  and r["parAn"] >= 2.0)
            tout["%s | %s" % (nom, paire)] = dict(total=r, m1=m1, m2=m2, retenu=bool(ok))
            if ok: survivants.append((nom, paire, regle, r, m1, m2))
            if r["R"] > 0 or ok:
                print("%-18s %-9s | %+8.1f %6.2f %5.0f %% %7.1f | %+8.1f %+8.1f | %s"
                      % (nom, paire, r["R"], r["pf"], r["gagnants"], r["parAn"],
                         m1["R"], m2["R"], "RETENU" if ok else ""))
    print("-" * 108)
    print("survivants du criblage : %d" % len(survivants))
    return survivants, tout

# ------------------------------------------------------------------
# 7. PLATEAU (standard 3, 2e volet) : un pic de parametre ne vaut rien.
#    On balaie EMA rapide/lente, le TP et le multiple d'ATR, un axe a la
#    fois, et on exige que TOUT le voisinage reste positif sur les DEUX
#    moities. C'est ce test qui separe USDJPY des autres paires.
# ------------------------------------------------------------------
def plateau(paire, base=(20, 50, 2.0, 1.5)):
    r0, l0, a0, t0 = base
    axes = [("EMA rapide/lente", [(r, l, a0, t0) for r, l in
                                  ((10, 40), (15, 45), (20, 50), (25, 55), (30, 60))]),
            ("TP en R",          [(r0, l0, a0, t) for t in (1.0, 1.5, 2.0, 3.0)]),
            ("stop en ATR",      [(r0, l0, a, t0) for a in (1.5, 2.0, 2.5, 3.0)])]
    print()
    print("=" * 108)
    print("PLATEAU -- %s, un axe a la fois. Positif partout ET sur les deux moities ?" % paire)
    print("=" * 108)
    tout, solide = {}, True
    for titre, points in axes:
        print("%-18s |" % titre, end="")
        detail = []
        for (r, l, a, t) in points:
            reg = regle_ema(r, l, a, t)
            g  = mesurer_manche(simuler_manche(paire, reg))
            g1 = mesurer_manche(simuler_manche(paire, reg, jusqua=COUPURE))
            g2 = mesurer_manche(simuler_manche(paire, reg, depuis=COUPURE))
            ok = g["R"] > 0 and g1["R"] > 0 and g2["R"] > 0
            solide = solide and ok
            cle = "EMA%d/%d ATR%.1f TP%.1f" % (r, l, a, t)
            tout[cle] = dict(total=g, m1=g1, m2=g2, ok=bool(ok))
            detail.append("%s%+5.1f" % ("*" if ok else " ", g["R"]))
        print(" ".join(detail), "   (* = positif sur 10 ans ET sur les 2 moities)")
    print("-" * 108)
    print("PLATEAU %s : %s" % (paire, "SOLIDE -- tout le voisinage tient" if solide
                               else "PERCE -- au moins un voisin echoue"))
    return solide, tout

# ------------------------------------------------------------------
# 8. GROKBOT2 : les ajouts candidats, mesures sur la base GrokBot1.
#    Aucun n'est invente ici : le point mort et la reentree sur repli
#    sont deux mecanismes que le labo a deja valides ailleurs ; la
#    question est de savoir s'ils tiennent sur un chassis DEUX SENS.
# ------------------------------------------------------------------
CANDIDATS_V2 = [
    ("GrokBot1 (base)",                     dict()),
    ("TP 2,0 R au lieu de 1,5",             dict(_tp=2.0)),
    ("TP 1,0 R au lieu de 1,5",             dict(_tp=1.0)),
    ("stop 3,0 ATR au lieu de 2,0",         dict(_atr=3.0)),
    ("stop 1,5 ATR au lieu de 2,0",         dict(_atr=1.5)),
    ("+ point mort a +1,0 R",               dict(breakeven_r=1.0)),
    ("+ point mort a +0,75 R",              dict(breakeven_r=0.75)),
    ("+ point mort a +1,25 R",              dict(breakeven_r=1.25)),
    ("+ reentree sur repli 0,25 ATR",       dict(repli_atr=0.25, repli_fenetre=5)),
    ("+ reentree sur repli 0,50 ATR",       dict(repli_atr=0.50, repli_fenetre=5)),
    ("+ reentree sur repli 1,00 ATR",       dict(repli_atr=1.00, repli_fenetre=5)),
    ("+ point mort 1,0 R + repli 0,50 ATR", dict(breakeven_r=1.0, repli_atr=0.50, repli_fenetre=5)),
]

def banc_v2(paire, base=(20, 50, 2.0, 1.5)):
    print()
    print("=" * 108)
    print("GROKBOT2 -- les ajouts candidats sur la base GrokBot1 (%s)" % paire)
    print("  MESURE EN EXECUTION REELLE : entree a l'ouverture de la bougie")
    print("  SUIVANTE, jamais a la cloture du signal. La premiere version de")
    print("  ce banc mesurait a la cloture et donnait la reentree sur repli")
    print("  gagnante (+21,5 R) ; en execution reelle elle tombe a +7,0 R,")
    print("  soit MOINS que la base. C'etait un artefact de moteur -- le")
    print("  meme piege que le ' +64,6 %% apparent ' du README. Le controle")
    print("  d'execution est donc devenu le critere, pas une verification.")
    print("  Retenu si : R total EN HAUSSE et les DEUX moities EN HAUSSE.")
    print("  NOTE DE METHODE, a lire : une premiere version de ce banc exigeait")
    print("  AUSSI un PF en hausse. Ce veto a ete RETIRE, et il faut le dire :")
    print("  le PF ne fait pas partie des 4 standards du README, et le labo a")
    print("  deja tranche dans l'autre sens (' fib profond : meilleurs trades")
    print("  mais 2x moins de gains ' -> REJETE). Un mecanisme qui multiplie les")
    print("  occasions baisse mecaniquement le PF ; ce qui compte est le total,")
    print("  la stabilite des moities, le plateau des voisins, et le portefeuille.")
    print("  Le PF reste AFFICHE : s'il passait sous 1,5 il redeviendrait un veto.")
    print("=" * 108)
    print("%-38s | %8s %6s %6s %8s | %8s %8s" %
          ("variante", "R 10ans", "PF", "trades", "gagn.", "R 1re m.", "R 2e m."))
    print("-" * 108)
    res = {}
    for nom, kw in CANDIDATS_V2:
        kw = dict(kw)
        r0, l0, a0, t0 = base
        a0 = kw.pop("_atr", a0); t0 = kw.pop("_tp", t0)
        reg = regle_ema(r0, l0, a0, t0)
        # TOUT est mesure en EXECUTION REELLE (entree a l'ouverture suivante) :
        # c'est le controle qui a tue la premiere v2, il devient le critere.
        g  = mesurer_manche(simuler_manche(paire, reg, retard=True, **kw))
        g1 = mesurer_manche(simuler_manche(paire, reg, retard=True, jusqua=COUPURE, **kw))
        g2 = mesurer_manche(simuler_manche(paire, reg, retard=True, depuis=COUPURE, **kw))
        res[nom] = dict(total=g, m1=g1, m2=g2, kw=kw, reglage=(r0, l0, a0, t0))
        print("%-38s | %+8.1f %6.2f %6d %7.0f %% | %+8.1f %+8.1f"
              % (nom, g["R"], g["pf"], g["trades"], g["gagnants"], g1["R"], g2["R"]))
    ref = res["GrokBot1 (base)"]
    print("-" * 108)
    gagnants = []
    for nom, r in res.items():
        if nom.startswith("GrokBot1"): continue
        motifs = []
        if r["total"]["R"] <= ref["total"]["R"]: motifs.append("R total")
        if r["m1"]["R"] < ref["m1"]["R"] - 1e-9: motifs.append("1re moitie")
        if r["m2"]["R"] < ref["m2"]["R"] - 1e-9: motifs.append("2e moitie")
        if r["total"]["pf"] < 1.5: motifs.append("PF sous 1,5")
        if motifs: print("  REJETE  %-36s : %s en baisse" % (nom, ", ".join(motifs)))
        else:      print("  RETENU  %-36s" % nom); gagnants.append(nom)
    if not gagnants:
        print("  Aucun ajout ne passe : GrokBot2 = GrokBot1. Resultat negatif = resultat.")
    return res, gagnants

# ------------------------------------------------------------------
# 8bis. CONTROLE D'EXECUTION : la meme strategie, mais entree a
#       l'ouverture suivante -- ce que le robot fera vraiment.
# ------------------------------------------------------------------
def controle_execution(paire="USDJPY", base=(20, 50, 2.0, 1.5)):
    reg = regle_ema(*base)
    print()
    print("=" * 108)
    print("CONTROLE D'EXECUTION -- le banc entre a la cloture du signal ;")
    print("  un robot reel entre a l'OUVERTURE SUIVANTE. Voici les deux.")
    print("=" * 108)
    print("%-38s | %9s %9s %9s | %8s %8s" %
          ("", "R cloture", "R ouv.+1", "ecart", "R 1re m.", "R 2e m."))
    print("-" * 108)
    res = {}
    for nom, kw in (("GrokBot1", dict()),
                    ("GrokBot2 (repli 0,50 ATR)", dict(repli_atr=0.50, repli_fenetre=5))):
        a = mesurer_manche(simuler_manche(paire, reg, **kw))
        b = mesurer_manche(simuler_manche(paire, reg, retard=True, **kw))
        b1 = mesurer_manche(simuler_manche(paire, reg, retard=True, jusqua=COUPURE, **kw))
        b2 = mesurer_manche(simuler_manche(paire, reg, retard=True, depuis=COUPURE, **kw))
        res[nom] = dict(cloture=a, ouverture=b, m1=b1, m2=b2)
        print("%-38s | %+9.1f %+9.1f %+9.1f | %+8.1f %+8.1f"
              % (nom, a["R"], b["R"], b["R"] - a["R"], b1["R"], b2["R"]))
    print("-" * 108)
    print("  L'avantage doit survivre a l'execution reelle ET rester positif")
    print("  sur les deux moities. Sinon c'est un artefact de moteur.")
    return res

# ------------------------------------------------------------------
# 9. STANDARD 4 -- le portefeuille. GrokBot vole-t-il des sieges sous
#    le plafond de 2 positions, ou apporte-t-il vraiment ?
#    On charge le moteur du labo tel quel et on lui ajoute une manche.
# ------------------------------------------------------------------
LIGNE_FETCH = 'btc, gc, nq, cl = fetch("BTC-USD"), fetch("GC=F"), fetch("NQ=F"), fetch("CL=F")'

def charger_ecurie():
    src = open(os.path.join(D, "optimisation_finale.py"), encoding="utf-8").read()
    src = src.split('print(f"{\'Config\'')[0]
    assert LIGNE_FETCH in src, "ANCRE FETCH INTROUVABLE"
    src = src.replace(LIGNE_FETCH,
        'btc, gc, nq, cl = (_ext("BTC-USD"), _ext("GC=F"), _ext("NQ=F"), _ext("CL=F"))')
    ns = {"__file__": os.path.join(D, "optimisation_finale.py"),
          "__name__": "moteur_ecurie", "_ext": charger}
    exec(compile(src, "optimisation_finale.py", "exec"), ns)
    return ns

def portefeuille(paires=(), base=(20, 50, 2.0, 1.5),
                 risque=0.0075, depuis=None, jusqua=None, kw_v2=None, cap=2):
    E = charger_ecurie()
    KW2 = dict(tpj_or=2.0, tpj_nq=1.0, tpj_ema=2.0)
    m = 1.0
    manches = [
        E["Fib"]("Or", E["gc"], 0.01*m, 0.0001, -0.000273, 1.4, jimmy=True, retrace=0.25,
                 tpj=KW2["tpj_or"], lookback=10, fib=(0.2, 0.8), pull=55, mult=3.0, tpr=2.0),
        E["Donch"]("Petrole", E["cl"], 0.005*m, 0.00045, +0.000051, 1.4, saison=(1201, 531)),
        E["Donch"]("BTC brk", E["btc"], 0.005*m, 0.0004, -0.000833, 1.0),
        E["Fib"]("Nasdaq", E["nq"], 0.01*m, 0.00003, -0.000213, 1.4, jimmy=True, retrace=0.5,
                 tpj=KW2["tpj_nq"], lookback=7, fib=(0.1, 0.9), pull=60, mult=2.0, tpr=2.0),
        E["EmaBTC"]("BTC ema", E["btc"], 0.005*m, 0.0004, -0.000833, 1.0, jimmy=True,
                    retrace=0.25, tpj=KW2["tpj_ema"]),
    ]
    for paire in paires:
        manches.append(MancheBi("GrokBot " + paire, charger(PAIRES[paire]), risque=risque,
                                regle=regle_ema(*base), retard=True, **(kw_v2 or {})))
    dates = sorted(set().union(*[x.df.index for x in manches]))
    if depuis is not None: dates = [d for d in dates if d >= pd.Timestamp(depuis)]
    if jusqua is not None: dates = [d for d in dates if d <  pd.Timestamp(jusqua)]
    for date in dates:
        for x in manches: x.gerer(date)
        ouverts = sum(1 for x in manches if x.pos is not None)
        for x in manches:
            sig = x.signal(date)          # appele meme si occupe : tampon du retard
            if x.pos is not None or sig is None: continue
            if cap is not None and ouverts >= cap: continue
            if x.ouvrir(date, **sig): ouverts += 1
    total = pd.Series(0.0, index=pd.DatetimeIndex(dates))
    for x in manches:
        for dt, v in x.pnl.items():
            if dt in total.index: total[dt] += v
    return total, manches

def phase_ftmo(v, i0, cible):
    eq, jt = 1.0, 0
    for j in range(i0, len(v)):
        r = v[j]
        if r != 0.0: jt += 1
        if r <= -0.05: return 0, j - i0 + 1
        eq *= (1 + r)
        if eq <= 0.90: return 0, j - i0 + 1
        if eq >= 1 + cible and jt >= 4: return 1, j - i0 + 1
    return -1, len(v) - i0

def ftmo(total):
    v = total.values; ok = mort = 0; d = []
    for i0 in range(0, max(len(v) - 60, 1), 3):
        v1, d1 = phase_ftmo(v, i0, 0.10)
        if v1 == -1: continue
        if v1 == 0: mort += 1; continue
        v2, d2 = phase_ftmo(v, i0 + d1, 0.05)
        if v2 == -1: continue
        if v2 == 0: mort += 1; continue
        ok += 1; d.append(d1 + d2)
    n = ok + mort
    return 100.0 * ok / max(n, 1), (float(np.median(d)) if d else float("nan")), n

def mesurer_portefeuille(total):
    eq = (1 + total).cumprod()
    annees = len(total) / 365.25
    cagr = (eq.iloc[-1] ** (1 / annees) - 1) * 100
    dd = (eq / eq.cummax() - 1).min() * 100
    sh = total.mean() / total.std() * np.sqrt(365) if total.std() > 0 else 0.0
    reussite, duree, n = ftmo(total)
    return dict(cagr=cagr, dd=dd, pire=total.min() * 100, sharpe=sh,
                reussite=reussite, duree=duree, nchal=n)

FENETRES = (("10 ANS", None, None),
            ("moitie 1", None, COUPURE),
            ("moitie 2", COUPURE, None))

def banc_portefeuille(kw_v2=None, paire="USDJPY"):
    """3 colonnes : ecurie seule, ecurie + GrokBot1, ecurie + GrokBot2."""
    print()
    print("=" * 108)
    print("STANDARD 4 -- l'ecurie SANS et AVEC GrokBot, sous le plafond de 2 positions")
    print("  la question n'est pas 'ca gagne-t-il seul' mais 'vole-t-il des sieges'")
    print("=" * 108)
    print("%-38s | %8s %7s %6s | %7s %7s %6s" %
          ("configuration", "CAGR", "creux", "Sharpe", "reussi", "duree", "n"))
    print("-" * 108)
    configs = [("ecurie seule", (), None),
               ("+ GrokBot1 USDJPY", ("USDJPY",), None),
               ("+ GrokBot1 x2 (USDJPY+USDCHF)", ("USDJPY", "USDCHF"), None)]
    if kw_v2: configs.append(("+ mecanisme v2", ("USDJPY",), kw_v2))
    res = {}
    for titre, dep, jus in FENETRES:
        for etiq, pr, kw in configs:
            t, _ = portefeuille(paires=pr, depuis=dep, jusqua=jus, kw_v2=kw)
            r = mesurer_portefeuille(t)
            nom = "%-9s %s" % (titre, etiq)
            res[nom] = r
            print("%-38s | %+7.2f %% %6.1f %% %6.2f | %6.1f %% %5.0f j %6d"
                  % (nom, r["cagr"], r["dd"], r["sharpe"], r["reussite"], r["duree"], r["nchal"]))
        print("-" * 118)
    return res

if __name__ == "__main__":
    print(__doc__.split("Lancer")[0].strip())
    print()
    survivants, crible = criblage()
    solide, plat = plateau("USDJPY")
    solide_audusd, plat_audusd = plateau("AUDUSD")
    v2, gagnants_v2 = banc_v2("USDJPY")
    exec_reel = controle_execution()
    kw = v2[gagnants_v2[0]]["kw"] if gagnants_v2 else None
    porte = banc_portefeuille(kw_v2=kw)
    with open(os.path.join(D, "resultats_grokbot.json"), "w", encoding="utf-8") as f:
        json.dump(dict(criblage=crible, plateau_usdjpy=plat, plateau_audusd=plat_audusd,
                       v2=v2, gagnants_v2=gagnants_v2, execution=exec_reel,
                       portefeuille=porte),
                  f, indent=2, default=float)
    print("\nResultats bruts : backtests/resultats_grokbot.json")
