# -*- coding: utf-8 -*-
"""Genere les 5 templates L3 a partir des templates I2+ :
   - chemin de l'expert repointe vers Jimmy L3\\<nom L3>
   - nom de l'expert mis a jour
   - inputs L3 ajoutes (pyramidage) et gardien resserre
ATTENTION .tpl : UTF-16LE, CRLF, chaque balise sur SA ligne."""
import os, re

TPL_SRC = r"C:\Users\jplou\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Profiles\Templates\Jimmy I2+"
TPL_DST = r"C:\Users\jplou\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Profiles\Templates\Jimmy L3"
os.makedirs(TPL_DST, exist_ok=True)

PAIRES = {
    "jimmy btc ema I2+ H1.tpl":     ("jimmy btc ema L3 H1.tpl",     "BTCUSD_EMA_I2+_H1",     "BTCUSD_EMA_L3_H1",     False),
    "jimmy or I2+ H4.tpl":          ("jimmy or L3 H4.tpl",          "XAUUSD_Or_I2+_H4",      "XAUUSD_Or_L3_H4",      False),
    "jimmy nasdaq I2+ H4.tpl":      ("jimmy nasdaq L3 H4.tpl",      "US100_Nasdaq_I2+_H4",   "US100_Nasdaq_L3_H4",   False),
    "jimmy btc cassure I2+ H4.tpl": ("jimmy btc cassure L3 H4.tpl", "BTCUSD_Cassure_I2+_H4", "BTCUSD_Cassure_L3_H4", True),
    "jimmy petrole I2+ D1.tpl":     ("jimmy petrole L3 D1.tpl",     "USOIL_Petrole_I2+_D1",  "USOIL_Petrole_L3_D1",  True),
}

INPUTS_PYR = ("PyramidageActif=true\r\n"
              "MaxUnites=3\r\n"
              "PasUniteATR=0.5\r\n"
              "StopSousDerniereUniteATR=2.0\r\n")

for src, (dst, ancien, nouveau, cassure) in PAIRES.items():
    p = os.path.join(TPL_SRC, src)
    with open(p, "r", encoding="utf-16-le", newline="") as f:
        t = f.read()
    if t.startswith("\ufeff"):
        t = t[1:]
    # 1. repointer l'expert
    t = t.replace("Jimmy I2+\\\\" + ancien, "Jimmy L3\\\\" + nouveau)
    t = t.replace("Jimmy I2+\\" + ancien, "Jimmy L3\\" + nouveau)
    t = t.replace(ancien, nouveau)
    t = t.replace("Jimmy I2+", "Jimmy L3")
    # 2. gardien resserre dans les inputs du template
    t = re.sub(r"LimitePerteJourPct=3\.5", "LimitePerteJourPct=2.5", t)
    t = re.sub(r"DailyStopPct=3\.5", "DailyStopPct=2.5", t)
    # 3. inputs de pyramidage pour les cassures
    if cassure and "PyramidageActif" not in t:
        t = re.sub(r"(JournalActif=\w+\r\n)", INPUTS_PYR + r"\1", t, count=1)
        if "PyramidageActif" not in t:   # filet : sinon avant </inputs>
            t = t.replace("</inputs>", INPUTS_PYR + "</inputs>", 1)
    # 4. verification : aucune balise collee
    colles = re.findall(r"></?\w+>", t)
    with open(os.path.join(TPL_DST, dst), "w", encoding="utf-16-le", newline="") as f:
        f.write("\ufeff" + t)
    etat = "ATTENTION balises collees" if colles else "ok"
    print("  %-30s <- %-30s [%s]" % (dst, src, etat))

print("\nVerification du contenu genere :")
for _, (dst, _, nouveau, cassure) in PAIRES.items():
    with open(os.path.join(TPL_DST, dst), "r", encoding="utf-16-le") as f:
        t = f.read()
    a = "L3" if nouveau in t else "MANQUE"
    b = "2.5" if ("LimitePerteJourPct=2.5" in t or "DailyStopPct=2.5" in t) else "gardien?"
    c = "pyr" if "PyramidageActif" in t else ("-" if not cassure else "PYR MANQUANT")
    crlf = "CRLF" if t.count("\r\n") > 10 else "LF!"
    print("  %-30s expert:%s | gardien:%s | %s | %s" % (dst, a, b, c, crlf))
