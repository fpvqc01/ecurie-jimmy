# -*- coding: utf-8 -*-
"""L4.32 -- correctifs du comite de verification (20 aout, approuves) :
1. HALT : la fermeture est retentee A CHAQUE TICK dans les 5 robots.
2. Anti-gap : la reference du gardien-jour = equite d'AVANT le gap
   (variable partagee MACROBOT_LASTEQ mise a jour a chaque tick).
3. Facteur de volatilite : appel ajoute dans BTC EMA (bogue), peremption
   7 jours du fichier (neutre si perime), plafond 1,0 en mode challenge.
4. Or/Nasdaq : ATR/RSI/fenetres de swing passes en JOURNALIER (fideles au
   moteur valide walk-forward), decision H4 conservee, lookback 60/40
   barres H4 -> 10/7 JOURS."""
import glob, io, sys

OK = True
def patch(f, s, ancien, nouveau, obligatoire=True, n_attendu=1):
    global OK
    n = s.count(ancien)
    if n == 0 and obligatoire:
        print("  !! ANCRE ABSENTE dans %s : %r..." % (f.split("\\")[-1], ancien[:60]))
        OK = False
        return s
    return s.replace(ancien, nouveau)

LASTEQ_DEF = 'string LastEqGV() { return "MACROBOT_LASTEQ_" + (string)AccountInfoInteger(ACCOUNT_LOGIN); }   // L4.32 : equite d\'avant le gap\n'
STALE_VOL = ('   derniereLectureVol = TimeCurrent();\n'
             '   long modifVol = (long)FileGetInteger("macrobot_vol.txt", FILE_MODIFY_DATE);   // L4.32\n'
             '   if(modifVol > 0 && TimeCurrent() - (datetime)modifVol > 7 * 86400)\n'
             '     { facteurVol = 1.0; return; }   // L4.32 : fichier perime -> facteur neutre\n')
CAP_VOL = '   if(ModeChallengeActif && facteurVol > 1.0) facteurVol = 1.0;   // L4.32 : jamais amplifier en challenge\n'

for f in sorted(glob.glob(r"C:\MT6\MQL5\Experts\Jimmy L4.3*\*.mq5")):
    s = io.open(f, encoding="utf-8", errors="replace", newline="").read()
    if "L4.32" in s:
        print("deja fait :", f.split("\\")[-1]); continue
    nom = f.split("\\")[-1]

    # --- LastEqGV : definition apres HaltGV (une ligne dans les 5) ---
    if "string HaltGV()" in s:
        idx = s.find("string HaltGV()")
        fin_ligne = s.find("\n", idx) + 1
        s = s[:fin_ligne] + LASTEQ_DEF.replace("\n", "\r\n") + s[fin_ligne:]

    if "XAUUSD_Or" in nom or "US100_Nasdaq" in nom:
        # 1. HALT : fermer a chaque tick
        s = patch(f, s,
            "if(GlobalVariableCheck(HaltGV()) && GlobalVariableGet(HaltGV()) > 0.5)\r\n      return true;",
            "if(GlobalVariableCheck(HaltGV()) && GlobalVariableGet(HaltGV()) > 0.5)\r\n"
            "     {\r\n      CloseAllOurs(\"\");   // L4.32 : on retente la fermeture a chaque tick\r\n"
            "      return true;\r\n     }")
        # 2. anti-gap
        s = patch(f, s,
            "   if(!GlobalVariableCheck(dayKey))\r\n      GlobalVariableSet(dayKey, equity);",
            "   if(!GlobalVariableCheck(dayKey))\r\n"
            "      GlobalVariableSet(dayKey, GlobalVariableCheck(LastEqGV()) ? GlobalVariableGet(LastEqGV()) : equity);   // L4.32 : reference d'AVANT le gap")
        s = patch(f, s,
            "   double dayStart = GlobalVariableGet(dayKey);",
            "   double dayStart = GlobalVariableGet(dayKey);\r\n"
            "   GlobalVariableSet(LastEqGV(), equity);   // L4.32")
        # 3. vol : peremption + plafond (appel deja present dans OnTimer)
        s = patch(f, s, "   derniereLectureVol = TimeCurrent();\r\n", STALE_VOL.replace("\n", "\r\n"))
        s = patch(f, s, "   LireFacteurVol();\r\n", "   LireFacteurVol();\r\n" + CAP_VOL.replace("\n", "\r\n"))
        # 4. indicateurs journaliers (fideles au moteur valide)
        s = patch(f, s, "hATR = iATR(_Symbol, PERIOD_H4, AtrPeriod);", "hATR = iATR(_Symbol, PERIOD_D1, AtrPeriod);   // L4.32 : journalier (= moteur valide)")
        s = patch(f, s, "hRSI = iRSI(_Symbol, PERIOD_H4, RsiPeriod, PRICE_CLOSE);", "hRSI = iRSI(_Symbol, PERIOD_D1, RsiPeriod, PRICE_CLOSE);   // L4.32 : journalier")
        s = patch(f, s, "if(CopyRates(_Symbol, PERIOD_H4, 0, need, rates) < need)", "if(CopyRates(_Symbol, PERIOD_D1, 0, need, rates) < need)   // L4.32 : swing sur jours")
        s = patch(f, s, "iClose(_Symbol, PERIOD_H4, 1),", "iClose(_Symbol, PERIOD_D1, 1),")
        s = patch(f, s, "SwingLookback = 60;", "SwingLookback = 10;   // L4.32 : 10 JOURS (= moteur)")
        s = patch(f, s, "SwingLookback = 40;", "SwingLookback = 7;    // L4.32 : 7 JOURS (= moteur)")
        s = patch(f, s, "MacroBot L4.3 demarre", "MacroBot L4.32 demarre (indicateurs journaliers)")

    elif "BTCUSD_EMA" in nom:
        s = patch(f, s,
            "if(GlobalVariableCheck(HaltGV()) && GlobalVariableGet(HaltGV()) > 0.5)\r\n      return(false);",
            "if(GlobalVariableCheck(HaltGV()) && GlobalVariableGet(HaltGV()) > 0.5)\r\n"
            "     {\r\n      FermerPositions(true);   // L4.32 : on retente la fermeture a chaque tick\r\n"
            "      return(false);\r\n     }")
        s = patch(f, s,
            "   if(!GlobalVariableCheck(cle))\r\n      GlobalVariableSet(cle, equite);",
            "   if(!GlobalVariableCheck(cle))\r\n"
            "      GlobalVariableSet(cle, GlobalVariableCheck(LastEqGV()) ? GlobalVariableGet(LastEqGV()) : equite);   // L4.32 : reference d'AVANT le gap")
        s = patch(f, s,
            "   double debutJour = GlobalVariableGet(cle);",
            "   double debutJour = GlobalVariableGet(cle);\r\n"
            "   GlobalVariableSet(LastEqGV(), equite);   // L4.32")
        # BOGUE C : appel manquant
        s = patch(f, s,
            "void OnTimer()\r\n  {\r\n   ReleverEquite();",
            "void OnTimer()\r\n  {\r\n   ReleverEquite();\r\n   LireFacteurVol();\r\n" + CAP_VOL.replace("\n", "\r\n"))
        s = patch(f, s, "   derniereLectureVol = TimeCurrent();\r\n", STALE_VOL.replace("\n", "\r\n"))
        s = patch(f, s, "L4.3 charge | decision=", "L4.32 charge | decision=")

    else:  # Cassure + Petrole
        s = patch(f, s,
            "      static bool dejaFerme = false;\r\n      if(!dejaFerme) { FermerPositions(true); dejaFerme = true; }\r\n      return(false);",
            "      FermerPositions(true);   // L4.32 : on retente la fermeture a chaque tick\r\n      return(false);")
        s = patch(f, s,
            "   if(!GlobalVariableCheck(cle))\r\n      GlobalVariableSet(cle, equite);",
            "   if(!GlobalVariableCheck(cle))\r\n"
            "      GlobalVariableSet(cle, GlobalVariableCheck(LastEqGV()) ? GlobalVariableGet(LastEqGV()) : equite);   // L4.32 : reference d'AVANT le gap")
        s = patch(f, s,
            "   double debutJour = GlobalVariableGet(cle);",
            "   double debutJour = GlobalVariableGet(cle);\r\n"
            "   GlobalVariableSet(LastEqGV(), equite);   // L4.32")
        s = patch(f, s, "   derniereLectureVol = TimeCurrent();\r\n", STALE_VOL.replace("\n", "\r\n"))
        s = s.replace("   LireFacteurVol();\r\n", "   LireFacteurVol();\r\n" + CAP_VOL.replace("\n", "\r\n"))
        s = patch(f, s, "L4.31 charge | decision=", "L4.32 charge | decision=")

    io.open(f, "w", encoding="utf-8", newline="").write(s)
    print("patche :", nom)

print("TOUTES ANCRES OK" if OK else "!! DES ANCRES ONT MANQUE — NE PAS COMPILER SANS VERIFIER")
sys.exit(0 if OK else 1)
