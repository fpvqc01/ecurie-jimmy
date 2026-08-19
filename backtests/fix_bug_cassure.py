# -*- coding: utf-8 -*-
"""CORRECTION du bug qui a empeche le robot cassure MT4 de trader la cassure
du BTC (achat pris par I2+ mais pas par L3) :
  BUG 1 : garde-fou de distance SL trop serre (10 % / 15 %) alors que la
          strategie VALIDEE autorise jusqu'a 50 % (r0p > 0.5 dans le moteur
          Python). Une cassure explosive avec un canal bas eloigne depasse
          10 % -> le robot rejette le trade EN SILENCE.
  BUG 2 : OrderSend n'a aucune journalisation d'echec -> une entree ratee
          (rejet, requote, marge) passe totalement inapercue.
Applique aux robots MQL4 ET MQL5 de l'ecurie L3."""
import glob, os, re

DIRS = [
    r"C:\Users\jplou\AppData\Roaming\MetaQuotes\Terminal\2C68BEE3A904BDCEE3EEF5A5A77EC162\MQL4\Experts\Jimmy L3",
    r"C:\Users\jplou\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Experts\Jimmy L3",
]

for d in DIRS:
    lang = "MQL4" if "MQL4" in d else "MQL5"
    print("--- %s ---" % lang)
    for p in sorted(glob.glob(os.path.join(d, "*.mq4" if lang == "MQL4" else "*.mq5"))):
        t = open(p, encoding="utf-8", errors="replace").read()
        nom = os.path.basename(p)
        avant = t
        notes = []

        # ---- BUG 1 : elargir le garde-fou a 50 % (comme le backtest) ----
        n1 = 0
        t, k = re.subn(r"distanceSL > 0\.10 \* Ask", "distanceSL > 0.50 * Ask", t); n1 += k
        t, k = re.subn(r"distanceSL > 0\.15 \* Ask", "distanceSL > 0.50 * Ask", t); n1 += k
        # MQL5 : meme motif possible avec prix courant
        t, k = re.subn(r"distanceSL > 0\.10 \* (prix|ask|Ask|entree)", r"distanceSL > 0.50 * \1", t); n1 += k
        t, k = re.subn(r"distanceSL > 0\.15 \* (prix|ask|Ask|entree)", r"distanceSL > 0.50 * \1", t); n1 += k
        if n1: notes.append("garde-fou SL 10/15%%->50%% (x%d)" % n1)

        # ---- BUG 2 : journaliser les echecs d'OrderSend (MQL4) ----
        if lang == "MQL4":
            # bloc entree principal : if(ticket > 0) { ... }  -> ajouter else
            if "if(ticket > 0)" in t and "OrderSend echoue" not in t:
                # trouver la fin du bloc if(ticket>0){...} et inserer un else
                idx = t.find("if(ticket > 0)")
                # localiser l'accolade fermante correspondante
                j = t.find("{", idx)
                prof = 0
                for k in range(j, len(t)):
                    if t[k] == "{": prof += 1
                    elif t[k] == "}":
                        prof -= 1
                        if prof == 0:
                            fin = k + 1
                            break
                t = t[:fin] + '\n   else\n      Print("OrderSend (entree) echoue, erreur ", GetLastError(), " lot=", DoubleToString(lot, 2));' + t[fin:]
                notes.append("log echec entree")
            # bloc pyramide : if(t > 0) { ... }
            if "if(t > 0)" in t and "OrderSend (pyramide)" not in t:
                idx = t.find("if(t > 0)")
                j = t.find("{", idx)
                prof = 0
                for k in range(j, len(t)):
                    if t[k] == "{": prof += 1
                    elif t[k] == "}":
                        prof -= 1
                        if prof == 0:
                            fin = k + 1
                            break
                t = t[:fin] + '\n         else\n            Print("OrderSend (pyramide) echoue, erreur ", GetLastError());' + t[fin:]
                notes.append("log echec pyramide")

        if t != avant:
            open(p, "w", encoding="utf-8").write(t)
            print("  %-28s %s" % (nom, ", ".join(notes) if notes else "modifie"))
        else:
            print("  %-28s (rien a changer)" % nom)
