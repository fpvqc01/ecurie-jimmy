# -*- coding: utf-8 -*-
"""LES MEMES TESTS QUE LE 10 ANS D1, MAIS EN H4 (21 aout).
Limite ferme : or/petrole/Nasdaq n'ont que 730 jours d'intraday (Yahoo).
Donc : (1) ecurie complete H4 = 2 ans, avec rendement par annee ;
       (2) BTC seul H4 = 8 ans (Binance 2018-2026), par generation."""
import pandas as pd, numpy as np
import moteur_h4 as MH

# sim H4 parametrique qui retourne aussi la serie journaliere
src = open("valide_candidats_h4.py", encoding="utf-8").read()
src = src.split('print("=== VALIDATION')[0].replace(
    "return cagr, sh, dd, (morts/n*100 if n else 0)",
    "return cagr, sh, dd, (morts/n*100 if n else 0), tj")
ns = {"__file__": "valide_candidats_h4.py"}; exec(src, ns)
sim_p = ns["sim_p"]
ns["RISQUES"]["L4"] = dict(Or=0.02, Nasdaq=0.015, Petrole=0.015, BTC=0.015)
ns["RISQUES"]["L3P"] = dict(Or=0.015, Nasdaq=0.015, Petrole=0.015, BTC=0.015)

CONFIGS = [
    ("I2+",                    dict(nom_r="L3")),                              # risques originaux, pas de corr/thr
    ("L3",                     dict(nom_r="L3")),
    ("L3+",                    dict(nom_r="L3P", corr=True, throttle=0.75)),
    ("L4 (mode challenge ON)", dict(nom_r="L4", corr=True, throttle=0.75)),
    ("L4 (mode OFF)",          dict(nom_r="L4", corr=True, throttle=None)),
]
# note : I2+ et L3 partagent les memes risques ; la difference I2+/L3 en H4
# passe par le moteur gen (gardien 3,5 vs 2,5, pyramide) -> on utilise
# moteur_h4.sim pour eux, et sim_p pour les configs a risques custom.

print("=== 1. ECURIE COMPLETE EN H4 -- 2 ans (fenetre max des donnees) ===")
print("  %-26s | %-7s | %-6s | %-7s | %s" % ("Config", "CAGR", "Sharpe", "MaxDD", "Morts"))
print("  " + "-" * 64)
series = {}
r = MH.sim("I2+", debut="2024-08-21")
print("  %-26s | %+6.1f%% | %6.2f | %+6.1f%% | %4.0f%%" % ("I2+", r["cagr"], r["sharpe"], r["dd"], r["morts"]))
r = MH.sim("L3", debut="2024-08-21")
print("  %-26s | %+6.1f%% | %6.2f | %+6.1f%% | %4.0f%%" % ("L3", r["cagr"], r["sharpe"], r["dd"], r["morts"]))
for nom, kw in CONFIGS[2:]:
    c, s, d, m, tj = sim_p(**kw)
    series[nom] = tj
    print("  %-26s | %+6.1f%% | %6.2f | %+6.1f%% | %4.0f%%" % (nom, c, s, d, m))
print()
print("=== RENDEMENT PAR ANNEE (H4, ecurie complete, 2 ans) ===")
noms = [n for n, _ in CONFIGS[2:]]
annees = sorted({d.year for d in series[noms[0]].index})
print("  %-6s | %s" % ("Annee", " | ".join("%-9s" % ("L4 ON" if "ON" in n else ("L4 OFF" if "OFF" in n else n)) for n in noms)))
for an in annees:
    vals = [((1+series[n][series[n].index.year == an]).prod()-1)*100 for n in noms]
    print("  %-6d | %s" % (an, " | ".join("%+8.1f%%" % v for v in vals)))
print("  (2024 = 4 mois, 2026 = 8 mois)")
print()

print("=== 2. BTC SEUL EN H4 -- 8 ANS (Binance 2018-2026), par generation ===")
print("  %-34s | %-7s | %-6s | %-7s | %s" % ("Config BTC (cassure + EMA)", "CAGR", "Sharpe", "MaxDD", "Morts"))
print("  " + "-" * 72)
for nom, gen in (("I2+ (0,75 %, sans pyramide)", "I2+"),
                 ("L3 (0,75 %, pyramide)", "L3"),
                 ("L4 OFF (1,5 %, pyramide)", "I2++"),
                 ("L4 ON (1,5 %, pyr + throttle)", "L3+")):
    r = MH.sim(gen, btc_seul=True, debut="2018-01-01")
    print("  %-34s | %+6.1f%% | %6.2f | %+6.1f%% | %4.0f%%"
          % (nom, r["cagr"], r["sharpe"], r["dd"], r["morts"]))
