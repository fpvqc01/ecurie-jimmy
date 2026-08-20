# -*- coding: utf-8 -*-
"""Applique la PARITE DE RISQUE validee (or 3->1,5 %, BTC/petrole 0,75->1,5 %,
Nasdaq 1,5 % inchange) aux generations I2++ et L3+ (MQL5 et MQL4).
Validation : CAGR 11,2 -> 13,8 %, Sharpe 1,08 -> 1,21, MaxDD -12,2 -> -9,7 %,
moities les plus equilibrees de toutes les configurations testees (10 ans)."""
import glob, os, re

DOSSIERS = [
    (r"C:\Users\jplou\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Experts\Jimmy I2++", "mq5"),
    (r"C:\Users\jplou\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Experts\Jimmy L3+", "mq5"),
    (r"C:\Users\jplou\AppData\Roaming\MetaQuotes\Terminal\2C68BEE3A904BDCEE3EEF5A5A77EC162\MQL4\Experts\Jimmy L3+", "mq4"),
]

for dossier, ext in DOSSIERS:
    print("--- %s (%s) ---" % (os.path.basename(dossier), ext))
    for p in sorted(glob.glob(os.path.join(dossier, "*." + ext))):
        t = open(p, encoding="utf-8", errors="replace").read()
        nom = os.path.basename(p)
        m = re.search(r"((?:input\s+double\s+)?(?:RiskPerTradePct|RisqueParTradePct)\s*=\s*)([\d.]+)", t)
        if not m:
            print("  %-34s !! aucun input de risque trouve" % nom)
            continue
        avant = m.group(2)
        if avant == "1.5":
            print("  %-34s deja a 1,5 %%" % nom)
            continue
        t = t[:m.start(2)] + "1.5" + t[m.end(2):]
        # note explicative
        t = t.replace("1.5;", "1.5;   // parite de risque validee 10 ans (etait %s)" % avant, 1) \
             if ("1.5;" in t and "parite de risque" not in t) else t
        open(p, "w", encoding="utf-8").write(t)
        print("  %-34s risque %s %% -> 1,5 %%" % (nom, avant))
