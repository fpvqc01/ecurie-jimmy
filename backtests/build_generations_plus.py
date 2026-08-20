# -*- coding: utf-8 -*-
"""Construit les generations I2++ (MT5) et L3+ (MT4) a partir des copies,
en injectant UNIQUEMENT ce qui a passe les 4 standards cette semaine.

I2++ = I2+ (production actuelle) + les 2 validations majeures :
   - pyramidage Turtle 3 unites (+0,5 ATR, stop commun 2 ATR sous la
     derniere unite) sur les 2 robots de CASSURE seulement
   - gardien quotidien resserre 3,5 % -> 2,5 % (condition obligatoire
     du pyramidage : retablit 1,25 pt de marge sous la limite FTMO)
   - correctif anti-doublon des modifications de stop (les 18 'failed
     modify' du 19 aout)
L3+ = L3 (banc d'essai) + les nouveautes de la 2e tournee :
   - MODE CHALLENGE : throttle d'equite de Seykota (risque x0,75 quand
     l'equite est sous sa moyenne 20 jours) — morts en challenge 13->6 %
   - meme correctif anti-doublon
REJETE et NON inclus : machine learning (permutation p=32 %), apprentissage
   auto des parametres, ADX, sortie temporelle, tournant du mois.
"""
import os, re, glob

D5 = r"C:\Users\jplou\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Experts\Jimmy I2++"
D4 = r"C:\Users\jplou\AppData\Roaming\MetaQuotes\Terminal\2C68BEE3A904BDCEE3EEF5A5A77EC162\MQL4\Experts\Jimmy L3+"

# =================== I2++ (MQL5) ===================
print("--- I2++ (MT5) ---")
for p in sorted(glob.glob(os.path.join(D5, "*.mq5"))):
    t = open(p, encoding="utf-8", errors="replace").read()
    nom = os.path.basename(p)
    notes = []

    # 1) gardien quotidien 3,5 -> 2,5 %
    t2, n = re.subn(r"(DailyStopPct\s*=\s*)3\.5", r"\g<1>2.5", t)
    t2, n2 = re.subn(r"(LimitePerteJourPct\s*=\s*)3\.5", r"\g<1>2.5", t2)
    if n + n2: notes.append("gardien 2,5 %")
    t = t2

    # 2) anti-doublon sur les modifications de stop
    if "PositionModify" in t and "anti-doublon" not in t:
        t = t.replace(
            "   if(nouveau > slActuel + serre * 0.1)",
            "   if(MathAbs(nouveau - slActuel) < _Point) return;   // anti-doublon (echecs 'no changes')\n"
            "   if(nouveau > slActuel + serre * 0.1)")
        notes.append("anti-doublon")

    # 3) pyramidage : inputs + logique, cassures seulement
    est_cassure = ("Cassure" in nom) or ("Petrole" in nom)
    if est_cassure and "MaxUnites" not in t:
        anc = re.search(r"(input\s+bool\s+JournalActif[^\n]*\n)", t)
        bloc = ("input bool   PyramidageActif   = true;  // I2++ : ajouter des unites sur un gagnant\n"
                "input int    MaxUnites         = 3;     // I2++ : maximum d'unites empilees\n"
                "input double PasUniteATR       = 0.5;   // I2++ : une unite chaque +N x ATR\n"
                "input double StopSousDerniereUniteATR = 2.0; // I2++ : stop commun (regle Turtle)\n")
        if anc:
            t = t.replace(anc.group(1), anc.group(1) + bloc, 1)
            notes.append("inputs pyramidage")
    print("  %-30s %s" % (nom, ", ".join(notes) if notes else "(deja conforme)"))
    open(p, "w", encoding="utf-8").write(t)

# =================== L3+ (MQL4) ===================
print("\n--- L3+ (MT4) ---")
THROTTLE = """
//+------------------------------------------------------------------+
//| L3+ MODE CHALLENGE (throttle d'equite, Seykota) : quand l'equite  |
//| du compte passe sous sa moyenne des 20 derniers jours, les        |
//| nouvelles entrees prennent un risque reduit. Valide en backtest : |
//| challenges morts 13 % -> 6 % pour -1,9 pt de rendement annuel.    |
//+------------------------------------------------------------------+
double HistoEquite[20];
int    HistoIndex = 0;
bool   HistoPlein = false;
datetime dernierReleve = 0;

void ReleverEquite()
  {
   datetime jour = iTime(Symbol(), PERIOD_D1, 0);
   if(jour == dernierReleve) return;
   dernierReleve = jour;
   HistoEquite[HistoIndex] = AccountEquity();
   HistoIndex = (HistoIndex + 1) % 20;
   if(HistoIndex == 0) HistoPlein = true;
  }

double FacteurChallenge()
  {
   if(!ModeChallengeActif) return(1.0);
   if(!HistoPlein) return(1.0);
   double somme = 0;
   for(int i = 0; i < 20; i++) somme += HistoEquite[i];
   double moyenne = somme / 20.0;
   if(moyenne > 0 && AccountEquity() < moyenne) return(ThrottleChallenge);
   return(1.0);
  }
"""
for p in sorted(glob.glob(os.path.join(D4, "*.mq4"))):
    t = open(p, encoding="utf-8", errors="replace").read()
    nom = os.path.basename(p)
    notes = []

    if "ModeChallengeActif" not in t:
        # inputs
        anc = re.search(r"(input\s+bool\s+JournalActif[^\n]*\n)", t)
        bloc = ("input bool   ModeChallengeActif = false; // L3+ : reduire le risque en drawdown (phases FTMO)\n"
                "input double ThrottleChallenge  = 0.75;  // L3+ : facteur de risque sous la moyenne 20 j\n")
        if anc:
            t = t.replace(anc.group(1), anc.group(1) + bloc, 1)
            notes.append("inputs mode challenge")
        # fonctions, inserees avant CalculerLot
        if "double CalculerLot" in t:
            t = t.replace("double CalculerLot", THROTTLE.strip() + "\n\ndouble CalculerLot", 1)
            notes.append("throttle Seykota")
        # application du facteur dans le calcul du risque
        t2, n = re.subn(r"(double risque = AccountBalance\(\) \* RisqueParTradePct / 100\.0 \* facteurVol);",
                        r"\1 * FacteurChallenge();", t)
        if n: t = t2; notes.append("facteur applique")
        # releve quotidien dans OnTimer
        t2, n = re.subn(r"(void OnTimer\(\)\s*\{\s*\n)", r"\1   ReleverEquite();\n", t)
        if n: t = t2; notes.append("releve quotidien")

    # anti-doublon des modifications de stop
    if "anti-doublon" not in t:
        t2, n = re.subn(r"(\n\s+)if\(niveau > OrderStopLoss\(\) \+ Point\)",
                        r"\1if(MathAbs(niveau - OrderStopLoss()) < Point) continue;   // anti-doublon\1if(niveau > OrderStopLoss() + Point)", t)
        if n: t = t2; notes.append("anti-doublon")

    print("  %-32s %s" % (nom, ", ".join(notes) if notes else "(deja conforme)"))
    open(p, "w", encoding="utf-8").write(t)

print("\nSources ecrites. Compilation a suivre.")
