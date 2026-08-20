# -*- coding: utf-8 -*-
"""L4+ options C et F (approuvees par Jimmy : « c+f go », 20 aout soir) :
C. Petrole : aucune NOUVELLE unite de pyramide le vendredi (gaps OPEP+).
   Cout backtest -0,2 pt, garde reelle sur les week-ends de reunion.
F. BTC EMA : decision quotidienne a 08:00 serveur au lieu du premier tick
   de minuit (rollover = spread 3-10x). Cout backtest -0,2 pt (21-26)."""
import glob, io, sys

OK = True
def patch(f, s, ancien, nouveau, n_attendu=1):
    global OK
    n = s.count(ancien)
    if n != n_attendu:
        print("  !! ANCRE (%d au lieu de %d) dans %s : %r..."
              % (n, n_attendu, f.split("\\")[-1], ancien[:70]))
        OK = False
        return s
    return s.replace(ancien, nouveau)

def inserer_apres_ligne(f, s, ancre, ligne):
    global OK
    idx = s.find(ancre)
    if idx < 0:
        print("  !! ANCRE ABSENTE dans %s : %r" % (f.split("\\")[-1], ancre[:70]))
        OK = False
        return s
    fin = s.find("\n", idx) + 1
    return s[:fin] + ligne.replace("\n", "\r\n") + s[fin:]

# ---------- C. Petrole ----------
for f in sorted(glob.glob(r"C:\MT6\MQL5\Experts\Jimmy L4+*\USOIL_Petrole*.mq5")):
    s = io.open(f, encoding="utf-8", errors="replace", newline="").read()
    if "GardeVendrediActif" in s:
        print("deja fait :", f.split("\\")[-1]); continue
    s = inserer_apres_ligne(f, s, "input int    MaxUnites",
        "input bool   GardeVendrediActif = true;  // L4+C : aucune nouvelle unite de pyramide le vendredi (gaps OPEP+ du week-end)\n")
    s = patch(f, s,
        "      if(PyramidageActif && unites > 0 && unites < MaxUnites && atrVal > 0 && dernier > 0)",
        "      MqlDateTime tvC;\r\n"
        "      TimeToStruct(TimeCurrent(), tvC);\r\n"
        "      bool ajoutBloqueVendredi = (GardeVendrediActif && tvC.day_of_week == 5);   // L4+C\r\n"
        "      if(PyramidageActif && !ajoutBloqueVendredi && unites > 0 && unites < MaxUnites && atrVal > 0 && dernier > 0)")
    s = patch(f, s,
        'Print("L4+ charge | PyramideMax=", MaxUnites, " ModeChallenge=", ModeChallengeActif);',
        'Print("L4+ charge | PyramideMax=", MaxUnites, " GardeVendredi=", GardeVendrediActif, " ModeChallenge=", ModeChallengeActif);')
    io.open(f, "w", encoding="utf-8", newline="").write(s)
    print("patche C :", f.split("\\")[-1])

# ---------- F. BTC EMA ----------
for f in sorted(glob.glob(r"C:\MT6\MQL5\Experts\Jimmy L4+*\BTCUSD_EMA*.mq5")):
    s = io.open(f, encoding="utf-8", errors="replace", newline="").read()
    if "HeureDecision" in s:
        print("deja fait :", f.split("\\")[-1]); continue
    s = inserer_apres_ligne(f, s, "input ENUM_TIMEFRAMES UT_Indicateurs",
        "input int             HeureDecision  = 8;         // L4+F : heure serveur de la decision D1 (evite le spread du rollover de minuit)\n")
    s = patch(f, s,
        "   datetime barreActuelle = iTime(_Symbol, UT_Decision, 0);   // L4.3\r\n"
        "   if(barreActuelle == derniereBarre) return;",
        "   datetime barreActuelle = iTime(_Symbol, UT_Decision, 0);   // L4.3\r\n"
        "   MqlDateTime tvF;\r\n"
        "   TimeToStruct(TimeCurrent(), tvF);\r\n"
        "   if(UT_Decision == PERIOD_D1 && tvF.hour < HeureDecision) return;   // L4+F : on decide a 08:00, pas au rollover\r\n"
        "   if(barreActuelle == derniereBarre) return;")
    s = patch(f, s,
        'Print("L4+ charge | decision=", EnumToString(UT_Decision), " indicateurs=", EnumToString(UT_Indicateurs));',
        'Print("L4+ charge | decision=", EnumToString(UT_Decision), " indicateurs=", EnumToString(UT_Indicateurs), " heureDecision=", HeureDecision, "h");')
    io.open(f, "w", encoding="utf-8", newline="").write(s)
    print("patche F :", f.split("\\")[-1])

print("TOUTES ANCRES OK" if OK else "!! DES ANCRES ONT MANQUE — NE PAS COMPILER SANS VERIFIER")
sys.exit(0 if OK else 1)
