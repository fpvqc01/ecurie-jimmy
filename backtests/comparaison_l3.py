# -*- coding: utf-8 -*-
"""COMPARAISON EXHAUSTIVE MQL5 L3 vs MQL4 L3 : chaque parametre de strategie
et chaque mecanisme, extrait des DEUX versions et mis cote a cote.
Objectif : prouver ou refuter que la transcription est fidele."""
import os, re, glob

MQ5 = r"C:\Users\jplou\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Experts\Jimmy L3"
MQ4 = r"C:\Users\jplou\AppData\Roaming\MetaQuotes\Terminal\2C68BEE3A904BDCEE3EEF5A5A77EC162\MQL4\Experts\Jimmy L3"

# cle semantique -> (regex MQL5, regex MQL4)
PARAMS = {
    "risque %/trade":      (r"(?:RiskPerTradePct|RisqueParTradePct)\s*=\s*([\d.]+)", None),
    "gardien jour %":      (r"(?:DailyStopPct|LimitePerteJourPct)\s*=\s*([\d.]+)", None),
    "gardien total %":     (r"(?:TotalStopPct|LimitePerteTotalePct)\s*=\s*([\d.]+)", None),
    "plafond ecurie":      (r"MaxPositionsEcurie\s*=\s*(\d+)", None),
    "magic":               (r"(?:MagicNumber|NumeroMagique)\s*=\s*(\d+)", None),
    "EMA rapide":          (r"(?:FastEMA|PeriodeRapide)\s*=\s*(\d+)", None),
    "EMA lente":           (r"(?:SlowEMA|PeriodeLente)\s*=\s*(\d+)", None),
    "SL xATR (ema)":       (r"MultiplicateurSL\s*=\s*([\d.]+)", None),
    "TP xATR (ema)":       (r"MultiplicateurTP\s*=\s*([\d.]+)", None),
    "swing lookback":      (r"SwingLookback\s*=\s*(\d+)", None),
    "fib bas":             (r"FibLo\s*=\s*([\d.]+)", None),
    "fib haut":            (r"FibHi\s*=\s*([\d.]+)", None),
    "seuil RSI":           (r"RsiPull\s*=\s*([\d.]+)", None),
    "SL xATR (fib)":       (r"StopAtrMult\s*=\s*([\d.]+)", None),
    "TP en R":             (r"TpR\s*=\s*([\d.]+)", None),
    "retrace re-entree":   (r"(?:RetraceReentree|RetraceReentreeATR)\s*=\s*([\d.]+)", None),
    "canal entree":        (r"PeriodeEntree\s*=\s*(\d+)", None),
    "canal sortie":        (r"PeriodeSortie\s*=\s*(\d+)", None),
    "max unites":          (r"MaxUnites\s*=\s*(\d+)", None),
    "pas unite xATR":      (r"PasUniteATR\s*=\s*([\d.]+)", None),
    "stop turtle xATR":    (r"StopSousDerniereUniteATR\s*=\s*([\d.]+)", None),
    "saison debut (mois)": (r"MoisDebutSaison\s*=\s*(\d+)", None),
    "saison fin (mois)":   (r"MoisFinSaison\s*=\s*(\d+)", None),
    "garde-fou SL max":    (r"distanceSL > ([\d.]+) \* ", None),
}

MECANISMES = {
    "desarmement re-entree apres usage": r"attenteReentree = 0",
    "invalidation plancher swing":       r"plancherSwing",
    "breakeven +1R":                     r"[Bb]reakeven",
    "stop commun pyramide":              r"AppliquerStopCommun|StopSousDerniere",
    "verif de marge":                    r"OrderCalcMargin|AccountFreeMarginCheck",
    "filtre macro (fichier)":            r"macrobot_bias",
    "filtre nouvelles":                  r"macrobot_news",
    "facteur volatilite":                r"macrobot_vol",
    "serrage stops pendant news":        r"ProtegerPositions",
    "journal de reflexion":              r"Ecurie_Journal",
    "notifications push":                r"SendNotification",
    "entree sur bougie FERMEE":          r"iClose\(.*1\)|rates\[1\]\.close|iTime|new.?bar|derniereBarre|lastBar",
}

paires = [
    ("BTCUSD_EMA_L3_H1", "EMA BTC"),
    ("BTCUSD_Cassure_L3_H4", "Cassure BTC"),
    ("XAUUSD_Or_L3_H4", "Or"),
    ("US100_Nasdaq_L3_H4", "Nasdaq"),
    ("USOIL_Petrole_L3_D1", "Petrole"),
]

total_ecarts = 0
for base, etiq in paires:
    p5 = os.path.join(MQ5, base + ".mq5")
    p4 = os.path.join(MQ4, base + ".mq4")
    t5 = open(p5, encoding="utf-8", errors="replace").read()
    t4 = open(p4, encoding="utf-8", errors="replace").read()
    print("=" * 78)
    print(" %s  (%s)" % (etiq, base))
    print("=" * 78)
    print("  %-28s | %-10s | %-10s | %s" % ("parametre", "MQL5", "MQL4", "verdict"))
    print("  " + "-" * 66)
    for nom, (rx, _) in PARAMS.items():
        m5 = re.search(rx, t5)
        m4 = re.search(rx, t4)
        v5 = m5.group(1) if m5 else "-"
        v4 = m4.group(1) if m4 else "-"
        if v5 == "-" and v4 == "-":
            continue
        try:
            egal = float(v5) == float(v4)
        except ValueError:
            egal = (v5 == v4)
        verdict = "IDENTIQUE" if egal else "!! ECART"
        if not egal:
            total_ecarts += 1
        print("  %-28s | %-10s | %-10s | %s" % (nom, v5, v4, verdict))
    print("  " + "-" * 66)
    for nom, rx in MECANISMES.items():
        a5 = bool(re.search(rx, t5))
        a4 = bool(re.search(rx, t4))
        if not a5 and not a4:
            continue
        if a5 == a4:
            verdict = "les deux"
        else:
            verdict = "!! MQL%s SEULEMENT" % ("5" if a5 else "4")
            total_ecarts += 1
        print("  %-28s | %-10s | %-10s | %s" % (nom, "oui" if a5 else "non", "oui" if a4 else "non", verdict))
    print()

print("=" * 78)
if total_ecarts == 0:
    print(" VERDICT GLOBAL : 0 ECART — la transcription MQL4 est fidele a la MQL5.")
else:
    print(" VERDICT GLOBAL : %d ecart(s) a corriger." % total_ecarts)
