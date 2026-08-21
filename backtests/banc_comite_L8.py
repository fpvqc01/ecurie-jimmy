# -*- coding: utf-8 -*-
"""BANC DES IDEES DU COMITE EXTERNE (21 aout 2026), sur L8 + donnees reparees.

Reference = L8 : gardien -1,75 %, breakeven collectif 5 %, allocation a x0,75,
mode challenge, ET fermeture automatique a l'objectif (R13, deja pose dans le
robot). Le simulateur reflete R13 : la phase est validee quand l'equite de
cloture passe la cible, puisque le robot ferme tout a ce moment-la.

Mecanismes testes :
  M1  ancre roulante apres pyramide pleine (le no 1 unanime des 3 IA)
      stop = max(canal 10 j, plus-haut depuis la pile pleine - K x ATR)
  M2  coupe-temps CONDITIONNEL (absence de progres, pas l'age)
  M3  serrage a l'approche de la ligne d'arrivee (borne OPTIMISTE, voir plus bas)
"""
import os, sys, numpy as np
D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, D)
import banc_L8 as B

ALLOC, PYR = B.ALLOC, B.PYR

# ---------------- M1 : ancre roulante apres pyramide pleine ----------------
def ancre_roulante(s, K):
    """Une fois la pile pleine, l'ancre du stop cesse d'etre figee sur la
    derniere unite : elle suit le plus-haut atteint depuis ce moment."""
    g0 = s.gerer
    maxu = getattr(s, "pyr_max", 3)
    def g(t):
        g0(t)
        p = s.pos
        if p is None: return
        i = s.idx.get(t)
        if i is None: return
        if p.get("unites", 1) < maxu:
            p.pop("ph", None); return
        v = s.prov(i)
        if v is None: return
        a = v[0]
        if not (a > 0): return
        h = s.H[i]
        p["ph"] = max(p.get("ph", p.get("dernier", h)), h)
        niv = p["ph"] - K * a
        if niv > p["s"]: p["s"] = niv
    s.gerer = g
    return s

# ---------------- M2 : coupe-temps conditionnel ----------------
def coupe_temps(s, barres, seuil_atr):
    """Ferme la position si, apres `barres` barres, le meilleur profit atteint
    n'a jamais depasse `seuil_atr` x ATR. Ce n'est pas l'age qui coupe, c'est
    l'absence de progres."""
    g0, o0 = s.gerer, s.ouvrir
    def o(t, *a, **k):
        r = o0(t, *a, **k)
        if s.pos is not None:
            s.pos["nb"] = 0; s.pos["mfe"] = 0.0
        return r
    def g(t):
        p0 = s.pos
        g0(t)
        p = s.pos
        if p is None: return
        i = s.idx.get(t)
        if i is None: return
        v = s.prov(i)
        if v is None: return
        a = v[0]
        p["nb"] = p.get("nb", 0) + 1
        p["mfe"] = max(p.get("mfe", 0.0), s.H[i] - p["e"])
        if p["nb"] >= barres and a > 0 and p["mfe"] < seuil_atr * a:
            s._clore(t, s.C[i]); s.attente = None
    s.ouvrir, s.gerer = o, g
    return s

def mesure(ns0, meca, debut, fin):
    ns, f_or, fab = ns0["ns"], ns0["f_or"], ns0["fab_l431"]
    def f():
        sl = fab()()
        for s in sl:
            if s.nom in ALLOC: s.risque = ALLOC[s.nom]
        for s in sl:
            if s.nom in PYR: B.breakeven(s, 0.05)      # L8 de base
        if meca: meca(sl)
        return sl
    ns["DEBUT"], ns["FIN"] = debut, fin
    ns["sleeves_l4"] = f
    r = ns["sim_h4"](interdit=f_or)
    tj = r[6].sort_index()
    o, m = B.ftmo(tj)
    return r[0], o, m, r[2], tj

# ---------------- M3 : serrage ligne d'arrivee (BORNE OPTIMISTE) ----------
# On ne peut PAS simuler fidelement ce mecanisme avec une serie de rendements
# calculee une seule fois : serrer les stops change les trades qui existent.
# On calcule donc une BORNE SUPERIEURE : des que la phase depasse `seuil`, on
# suppose que l'equite ne peut plus retomber de plus de `marge` sous son
# sommet. Si meme cette borne genereuse n'apporte rien, le mecanisme est mort.
def phase_serrage(v, i0, cible, seuil, marge):
    eq = 1.0; jt = 0; pic = 1.0; arme = False
    for j in range(i0, len(v)):
        r = v[j]
        if r != 0.0: jt += 1
        if r <= -0.05: return 0, j - i0 + 1
        eq *= (1 + r)
        if arme: eq = max(eq, pic - marge)
        pic = max(pic, eq)
        if eq >= 1 + seuil: arme = True
        if eq <= 0.90: return 0, j - i0 + 1
        if eq >= 1 + cible and jt >= 4: return 1, j - i0 + 1
    return -1, len(v) - i0

def ftmo_serrage(tj, seuil, marge):
    v = tj.values; ok = mort = 0; d = []
    for i0 in range(0, len(v) - 60, 3):
        v1, d1 = phase_serrage(v, i0, 0.10, seuil, marge)
        if v1 == -1: continue
        if v1 == 0: mort += 1; continue
        v2, d2 = phase_serrage(v, i0 + d1, 0.05, seuil * 0.5, marge)
        if v2 == -1: continue
        if v2 == 0: mort += 1; continue
        ok += 1; d.append(d1 + d2)
    n = ok + mort
    return 100.0 * ok / max(n, 1), (np.median(d) if d else 0)

if __name__ == "__main__":
    FEN = (("10 ANS ", "2015-08-21", "2026-12-31"),
           ("2021-26", "2021-01-01", "2026-08-20"))
    ns0 = B.charger(0.0175)

    VAR = [("REFERENCE L8", None)]
    for K in (1.8, 2.0, 2.2, 2.5):
        VAR.append(("M1 ancre roulante K=%.1f" % K,
                    (lambda K: (lambda sl: [ancre_roulante(s, K) for s in sl if s.nom in PYR]))(K)))
    for nb, sa in ((8, 0.75), (12, 1.0), (16, 1.0)):
        VAR.append(("M2 coupe-temps %d barres <%.2f ATR" % (nb, sa),
                    (lambda nb, sa: (lambda sl: [coupe_temps(s, nb, sa) for s in sl]))(nb, sa)))

    print("=== BANC DES IDEES DU COMITE (L8, donnees reparees, R13 actif) ===")
    print("%-34s | %-30s | %s" % ("", "10 ANS", "2021-2026"))
    print("%-34s | %8s %8s %6s %7s | %8s %8s %6s %7s"
          % ("mecanisme", "CAGR", "reussite", "duree", "DD", "CAGR", "reussite", "duree", "DD"))
    print("-" * 118)
    series = {}
    for nom, meca in VAR:
        ligne = "%-34s |" % nom
        for etq, deb, f in FEN:
            c, o, m, dd, tj = mesure(ns0, meca, deb, f)
            if meca is None: series[etq] = tj
            ligne += " %+7.1f %% %6.0f %% %4.0f j %+6.1f %% |" % (c, o, m, dd)
        print(ligne)

    print()
    print("=== M3 SERRAGE LIGNE D'ARRIVEE (BORNE OPTIMISTE, pas une mesure) ===")
    print("%-34s | %-19s | %s" % ("", "10 ANS", "2021-2026"))
    print("%-34s | %9s %8s | %9s %8s" % ("variante", "reussite", "duree", "reussite", "duree"))
    print("-" * 82)
    for seuil, marge in ((0.08, 0.015), (0.08, 0.010), (0.07, 0.015), (0.06, 0.015)):
        ligne = "%-34s |" % ("serre des +%.0f %%, plancher %.1f %%" % (seuil*100, marge*100))
        for etq, deb, f in FEN:
            o, m = ftmo_serrage(series[etq], seuil, marge)
            ligne += " %8.0f %% %6.0f j |" % (o, m)
        print(ligne)
