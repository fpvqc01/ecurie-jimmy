# -*- coding: utf-8 -*-
"""Decode et resume le journal du Strategy Tester MT4."""
import glob, os, sys

BASE = r"C:\Users\jplou\AppData\Local\Temp\claude\C--Users-jplou-Downloads\402ab065-414d-49fe-b7c5-31e3426fcd6c\scratchpad\MT4-Test"
motifs = ("ENTREE", "TP encaisse", "take profit", "stop loss", "re-entree", "Plancher",
          "PAUSE", "ARRET", "processed", "PYRAMIDE", "Fermeture", "demarre", "Echec")

logs = sorted(glob.glob(os.path.join(BASE, "tester", "logs", "*.log")))
if not logs:
    print("Aucun log de testeur trouve.")
    sys.exit()

for p in logs:
    raw = open(p, "rb").read()
    texte = None
    for enc in ("utf-16-le", "utf-16-be", "cp1252", "utf-8"):
        try:
            t = raw.decode(enc, errors="strict")
            if "XAUUSD" in t or "Tester" in t or "BTCUSD" in t:
                texte, encodage = t, enc
                break
        except Exception:
            continue
    if texte is None:
        texte, encodage = raw.decode("cp1252", errors="replace"), "cp1252(force)"
    lignes = [l for l in texte.splitlines() if l.strip()]
    print("=" * 70)
    print("%s  (%s, %d lignes)" % (os.path.basename(p), encodage, len(lignes)))
    print("=" * 70)
    interessantes = [l for l in lignes if any(m in l for m in motifs)]
    for l in interessantes:
        bout = l.split("\t")[-1].strip()
        print("  " + bout[:160])
    if not interessantes:
        for l in lignes[-25:]:
            print("  " + l.split("\t")[-1].strip()[:160])
