# -*- coding: utf-8 -*-
"""CONSTRUCTION DE L4.3 dans de nouveaux dossiers MT6 (+ maitres).
Changements vs L4.2 :
  - Cassure BTC : decision H1, canaux/ATR JOURNALIERS (input UT_*)
  - Petrole     : decision H4, canaux journaliers (deja D1)
  - BTC EMA     : decision D1, EMA/ATR journaliers
  - Or, Nasdaq  : inchanges (cadence H4)
  - magics 20261115/17/18, notifications [L4.3]/[L4.3-SC], empreintes."""
import io, os, re, shutil

SRC_ON = r"C:\MT6\MQL5\Experts\Jimmy L4"
SRC_SC = r"C:\MT6\MQL5\Experts\Jimmy L4 sans challenge"
DST_ON = r"C:\MT6\MQL5\Experts\Jimmy L4.3"
DST_SC = r"C:\MT6\MQL5\Experts\Jimmy L4.3 sans challenge"

RENOMME = {  # nouveau nom refletant la CADENCE de decision
    "XAUUSD_Or_L4_H4": "XAUUSD_Or_L43_H4",
    "US100_Nasdaq_L4_H4": "US100_Nasdaq_L43_H4",
    "BTCUSD_Cassure_L4_H4": "BTCUSD_Cassure_L43_H1",
    "BTCUSD_EMA_L4_H1": "BTCUSD_EMA_L43_D1",
    "USOIL_Petrole_L4_D1": "USOIL_Petrole_L43_H4",
}

def commun(s):
    s = s.replace("20261015", "20261115").replace("20261017", "20261117").replace("20261018", "20261118")
    s = s.replace('"[L4] "', '"[L4.3] "').replace('"[L4] ', '"[L4.3] ').replace('"[L4-SC] ', '"[L4.3-SC] ')
    s = s.replace("L4.1 charge", "L4.3 charge").replace("L4.2 charge", "L4.3 charge")
    return s

def patch_donchian(s, ut_decision, apres_input):
    # inputs UT
    s = s.replace(apres_input, apres_input +
        "input ENUM_TIMEFRAMES UT_Decision    = %s; // L4.3 : cadence de decision (valide walk-forward)\n" % ut_decision, 1)
    # gate sur UT_Decision
    s = s.replace("datetime barreActuelle = iTime(_Symbol, _Period, 0);",
                  "datetime barreActuelle = iTime(_Symbol, UT_Decision, 0);   // L4.3")
    s = s.replace("datetime jourActuel = iTime(_Symbol, PERIOD_D1, 0);\n   if(jourActuel == dernierJour) return;",
                  "datetime jourActuel = iTime(_Symbol, UT_Decision, 0);   // L4.3 : decision par barre UT\n   if(jourActuel == dernierJour) return;")
    # indicateurs journaliers (cassure : _Period -> D1 ; petrole deja D1)
    s = s.replace("hAtr = iATR(_Symbol, _Period, PeriodeATR);",
                  "hAtr = iATR(_Symbol, PERIOD_D1, PeriodeATR);   // L4.3 : ATR journalier")
    s = s.replace("if(CopyRates(_Symbol, _Period, 0, besoin, rates) < besoin) return;",
                  "if(CopyRates(_Symbol, PERIOD_D1, 0, besoin, rates) < besoin) return;   // L4.3 : canaux journaliers")
    # declencheur intrabarre apres le CopyRates (D1)
    ancre = "if(CopyRates(_Symbol, PERIOD_D1, 0, besoin, rates) < besoin) return;"
    idx = s.find(ancre)
    for a in (ancre + "   // L4.3 : canaux journaliers", ancre):
        if a in s:
            s = s.replace(a, a +
                "\n   double declencheur  = iClose(_Symbol, UT_Decision, 1);   // L4.3 : barre de decision fermee"
                "\n   double hautDecision = iHigh(_Symbol, UT_Decision, 1);"
                "\n   if(declencheur <= 0 || hautDecision <= 0) return;", 1)
            break
    # canaux sur les jours COMPLETS [1..N] (avant : [2..N+1], la veille servait de declencheur)
    s = s.replace("double hautCanal = rates[2].high;", "double hautCanal = rates[1].high;   // L4.3")
    s = s.replace("for(int i = 3; i <= PeriodeEntree + 1; i++)", "for(int i = 2; i <= PeriodeEntree; i++)")
    s = s.replace("double basCanal = rates[2].low;", "double basCanal = rates[1].low;   // L4.3")
    s = s.replace("for(int i = 3; i <= PeriodeSortie + 1; i++)", "for(int i = 2; i <= PeriodeSortie; i++)")
    # les references a la veille deviennent la barre de decision
    s = s.replace("rates[1].close", "declencheur").replace("rates[1].high", "hautDecision")
    # garde : plus de dependance au graphique
    s = s.replace("if(_Period != PERIOD_H4)", "if(false)   // L4.3 : le graphique n'a plus d'importance")
    return s

def patch_ema(s, apres_input):
    s = s.replace(apres_input, apres_input +
        "input ENUM_TIMEFRAMES UT_Decision    = PERIOD_D1; // L4.3 : une decision par jour (valide walk-forward)\n"
        "input ENUM_TIMEFRAMES UT_Indicateurs = PERIOD_D1; // L4.3 : EMA/ATR journaliers\n", 1)
    s = s.replace("datetime barreActuelle = iTime(_Symbol, _Period, 0);",
                  "datetime barreActuelle = iTime(_Symbol, UT_Decision, 0);   // L4.3")
    s = s.replace("(_Symbol, _Period", "(_Symbol, UT_Indicateurs")
    return s

def empreinte(s, texte):
    return s.replace("int OnInit()\n  {\n", "int OnInit()\n  {\n   %s\n" % texte, 1)

for src_dir, dst_dir, suffixe in ((SRC_ON, DST_ON, ""), (SRC_SC, DST_SC, "_SansChallenge")):
    os.makedirs(dst_dir, exist_ok=True)
    for base, neuf in RENOMME.items():
        anc = os.path.join(src_dir, base + suffixe + ".mq5")
        dst = os.path.join(dst_dir, neuf + suffixe + ".mq5")
        s = io.open(anc, encoding="utf-8", errors="replace").read()
        s = commun(s)
        s = s.replace(base, neuf)          # references internes au nom
        if "Cassure" in base:
            s = patch_donchian(s, "PERIOD_H1", "input int    MaxUnites          = 4;     // L4.2 : pyramide 4 (valide scan 21 aout, +2 pts H4 10 ans)\n")
            s = empreinte(s, 'Print("L4.3 charge | decision=", EnumToString(UT_Decision), " canaux=D1");')
        elif "Petrole" in base:
            s = patch_donchian(s, "PERIOD_H4", "input int    PeriodeSortie        = 10;     // Stop suiveur sous le plus bas des M jours\n")
            s = empreinte(s, 'Print("L4.3 charge | decision=", EnumToString(UT_Decision), " canaux=D1");')
        elif "EMA" in base:
            s = patch_ema(s, "input double RisqueParTradePct    = 1.5;   // parite de risque validee 10 ans (etait 0.75)   // Risque par trade en % du solde (I2 : x1.5)\n")
            s = empreinte(s, 'Print("L4.3 charge | decision=", EnumToString(UT_Decision), " indicateurs=", EnumToString(UT_Indicateurs));')
        io.open(dst, "w", encoding="utf-8").write(s)
        # verifications
        pb = []
        if "Cassure" in base or "EMA" in base:
            if ", _Period" in s: pb.append("_Period restant")
        if "20261015" in s or "20261017" in s or "20261018" in s: pb.append("ancien magic")
        print("%-45s -> %-45s %s" % (base + suffixe, neuf + suffixe, ("!! " + ",".join(pb)) if pb else "OK"))
