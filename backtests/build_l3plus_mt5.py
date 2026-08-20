# -*- coding: utf-8 -*-
"""Cree la version MQL5 de L3+ : L3 (pyramidage Turtle + gardien 2,5 %)
+ MODE CHALLENGE (throttle d'equite de Seykota, desactive par defaut).
Objectif : pouvoir comparer I2++ et L3+ dans le MEME environnement MT5."""
import glob, os, re

D = r"C:\Users\jplou\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Experts\Jimmy L3+"

THROTTLE = """
//+------------------------------------------------------------------+
//| L3+ MODE CHALLENGE (throttle d'equite, Seykota) : sous la moyenne |
//| 20 jours de l'equite, les nouvelles entrees prennent un risque    |
//| reduit. Backtest : challenges morts 13 % -> 6 % pour -1,9 pt/an.  |
//+------------------------------------------------------------------+
double   HistoEquite[20];
int      HistoIndex = 0;
bool     HistoPlein = false;
datetime dernierReleve = 0;

void ReleverEquite()
  {
   datetime jour = iTime(_Symbol, PERIOD_D1, 0);
   if(jour == dernierReleve) return;
   dernierReleve = jour;
   HistoEquite[HistoIndex] = AccountInfoDouble(ACCOUNT_EQUITY);
   HistoIndex = HistoIndex + 1;
   if(HistoIndex >= 20) { HistoIndex = 0; HistoPlein = true; }
  }

double FacteurChallenge()
  {
   if(!ModeChallengeActif || !HistoPlein) return(1.0);
   double somme = 0;
   for(int i = 0; i < 20; i++) somme += HistoEquite[i];
   double moyenne = somme / 20.0;
   if(moyenne > 0 && AccountInfoDouble(ACCOUNT_EQUITY) < moyenne) return(ThrottleChallenge);
   return(1.0);
  }
"""

for p in sorted(glob.glob(os.path.join(D, "*.mq5"))):
    t = open(p, encoding="utf-8", errors="replace").read()
    nom = os.path.basename(p)
    notes = []
    # identite L3+
    t = (t.replace("_L3_", "_L3plus_").replace("L3 H4", "L3+ H4")
          .replace("L3 H1", "L3+ H1").replace("L3 D1", "L3+ D1")
          .replace("Ecurie_L3", "Ecurie_L3plus").replace("Ecurie L3", "Ecurie L3+"))
    if "ModeChallengeActif" not in t:
        m = re.search(r"(input\s+bool\s+JournalActif[^\n]*\n)", t)
        if m:
            t = t.replace(m.group(1), m.group(1) +
                "input bool   ModeChallengeActif = false; // L3+ : risque reduit en drawdown\n"
                "input double ThrottleChallenge  = 0.75;  // L3+ : facteur sous la moyenne 20 j\n", 1)
            notes.append("inputs")
        for ancre in ("double LotsForRisk(double stopDist)", "double CalculerLot(double distanceSL)"):
            if ancre in t:
                t = t.replace(ancre, THROTTLE.strip() + "\n\n" + ancre, 1)
                notes.append("throttle")
                break
        applique = False
        for motif in (r"(double riskMoney = AccountInfoDouble\(ACCOUNT_EQUITY\) \* RiskPerTradePct / 100\.0 \* facteurVol)",
                      r"(double risqueArgent = AccountInfoDouble\(ACCOUNT_BALANCE\) \* RisqueParTradePct / 100\.0 \* facteurVol)"):
            t2, n = re.subn(motif, r"\1 * FacteurChallenge()", t)
            if n:
                t = t2; applique = True; break
        if applique: notes.append("applique")
        t2, n = re.subn(r"(void OnTimer\(\)\s*\n\s*\{\s*\n)", r"\1   ReleverEquite();\n", t)
        if n: t = t2; notes.append("releve")
    open(p, "w", encoding="utf-8").write(t)
    print("  %-34s %s" % (nom, ", ".join(notes) if notes else "(aucun changement)"))
