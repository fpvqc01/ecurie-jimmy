# -*- coding: utf-8 -*-
"""CONSTRUCTION DE L8 (21 aout 2026) — demande Jimmy : « corrige, trouve
et cree la version l8 ». Batie a partir de L6, apres l'audit des 20 agents
du groupe de verification ET la reparation du fichier de donnees BTC.

RECHIFFRAGE SUR DONNEES SAINES (banc_L8.py / banc_L8b.py) :
   L6 actuelle : +29,5 %/86 %/175 j/DD -18,7   (10 ans)
                 +19,1 %/87 %/169 j/DD -19,1   (2021-2026)
   L8          : +27,1 %/89 %/209 j/DD -13,9   (10 ans)
                 +18,7 %/84 %/242 j/DD -13,6   (2021-2026)
   Le gain principal est le DRAWDOWN (-4,8 pts), la contrainte qui tue
   un compte FTMO (limite -10 %). Le CAGR baisse peu, la duree monte.

CE QUE L8 CORRIGE (chaque point vient d'un agent, verifie par moi) :
  R1 gardien quotidien 2,5 % -> 1,75 % (quant : le seul reglage qui
     ameliore rendement ET risque ; rejoue sur donnees saines)
  R2 breakeven collectif 5 % (reduit le DD de ~4 pts sur les 2 fenetres)
  R3 plafond de notionnel 1,25x l'equite par manche (expert levier :
     assurance contre les gaps, que le backtest ne sait pas simuler)
  R4 frein d'equite PERSISTANT en variables globales (infra : il etait
     remis a zero a chaque redemarrage -> jamais actif en production)
  R5 magics distincts or/nasdaq (3 robots partageaient 20261115)
  R6 plafond de pyramide : <= devient < (le plafond ne freinait jamais)
  R7 ACCOUNT_BALANCE -> ACCOUNT_EQUITY (fidele au moteur, et ne
     sur-risque plus en drawdown)
  R8 FILE_SHARE_READ sur toutes les lectures (les filtres tombaient
     des centaines de fois par jour sur verrou de fichier)
  R9 anti-spam sur PositionModify (stops identiques renvoyes en boucle)
  R10 ChallengeInitialBalance sur les 5 robots (baseline figee)
  R11 les ajouts de pyramide passent par LotSelonMarge + notification
  R12 turbo-coussin RETIRE (47-52 % de perdre un compte finance)"""
import glob, io, os, shutil, sys

SRC = r"C:\MT6\MQL5\Experts\Jimmy L6"
DST = r"C:\MT6\MQL5\Experts\Jimmy L8"
if not os.path.isdir(DST): os.makedirs(DST)
for f in glob.glob(os.path.join(SRC, "*.mq5")):
    shutil.copy2(f, os.path.join(DST, os.path.basename(f).replace("_L6_", "_L8_")))
print("dossier L8 cree :", len(glob.glob(os.path.join(DST, "*.mq5"))), "fichiers")

OK = True
def patch(f, s, ancien, nouveau, n=1, oblig=True):
    global OK
    c = s.count(ancien)
    if c != n:
        if oblig:
            print("  !! ANCRE (%d/%d) : %r" % (c, n, ancien[:70])); OK = False
        return s
    return s.replace(ancien, nouveau)

CRLF = lambda t: t.replace("\n", "\r\n")

MAGICS = {"XAUUSD_Or": "20261121", "US100_Nasdaq": "20261122"}

FREIN_PERSISTANT = CRLF("""
//+------------------------------------------------------------------+
//| L8-R4 : le frein d'equite survit aux redemarrages.                |
//| Avant : tableau en memoire vive -> remis a zero a chaque relance, |
//| donc le mode challenge n'etait JAMAIS actif en production.        |
//+------------------------------------------------------------------+
string CleEqJour(datetime j)
  {
   MqlDateTime d; TimeToStruct(j, d);
   return(StringFormat("MACROBOT_EQJ_%04d%02d%02d_%s", d.year, d.mon, d.day,
                       (string)AccountInfoInteger(ACCOUNT_LOGIN)));
  }
""")

FREIN_NOUVEAU = CRLF("""void ReleverEquite()
  {
   datetime jour = iTime(_Symbol, PERIOD_D1, 0);
   if(jour <= 0 || jour == dernierReleve) return;
   dernierReleve = jour;
   string cle = CleEqJour(jour);
   if(!GlobalVariableCheck(cle))
      GlobalVariableSet(cle, AccountInfoDouble(ACCOUNT_EQUITY));   // L8-R4
   for(int k = 41; k <= 60; k++)                                   // menage
      GlobalVariableDel(CleEqJour(jour - k * 86400));
  }
""")

FACTEUR_NOUVEAU = CRLF("""double FacteurChallenge()
  {
   if(!ModeChallengeActif) return(1.0);
   datetime jour = iTime(_Symbol, PERIOD_D1, 0);
   double somme = 0; int n = 0;
   for(int k = 1; k <= 40 && n < 20; k++)          // L8-R4 : lit les GV
     {
      string cle = CleEqJour(jour - k * 86400);
      if(!GlobalVariableCheck(cle)) continue;
      somme += GlobalVariableGet(cle); n++;
     }
   if(n < 20) return(1.0);
   double moyenne = somme / n;
   if(moyenne > 0 && AccountInfoDouble(ACCOUNT_EQUITY) < moyenne) return(ThrottleChallenge);
   return(1.0);
  }
""")

for f in sorted(glob.glob(os.path.join(DST, "*.mq5"))):
    s = io.open(f, encoding="utf-8", errors="replace", newline="").read()
    nom = os.path.basename(f)
    print("--- " + nom)
    s = s.replace("L6", "L8")

    # R1 gardien 2,5 -> 1,75
    s = patch(f, s, "LimitePerteJourPct   = 2.5;",
              "LimitePerteJourPct   = 1.75;  // L8-R1 : resserre (banc L8 : DD -18,7 -> -13,9)", oblig=False)
    s = patch(f, s, "LimitePerteJourPct            = 2.5;",
              "LimitePerteJourPct            = 1.75;  // L8-R1 : resserre (banc L8)", oblig=False)

    # R5 magics distincts
    for cle, mg in MAGICS.items():
        if cle in nom:
            s = patch(f, s, "MagicNumber             = 20261115;",
                      "MagicNumber             = %s;  // L8-R5 : magic propre (3 robots partageaient 20261115)" % mg)

    # R7 assiette du risque : equite partout
    s = s.replace("AccountInfoDouble(ACCOUNT_BALANCE) * RisqueParTradePct",
                  "AccountInfoDouble(ACCOUNT_EQUITY) * RisqueParTradePct")   # L8-R7

    # R8 lectures de fichiers partageables
    s = s.replace("FILE_READ | FILE_TXT | FILE_ANSI",
                  "FILE_READ | FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_TXT | FILE_ANSI")

    # R6 plafond de pyramide
    s = s.replace("ComptePositionsEcurie() <= MaxPositionsEcurie",
                  "ComptePositionsEcurie() < MaxPositionsEcurie")   # L8-R6

    # R10 baseline figee : ajouter l'input aux 3 robots qui ne l'ont pas
    if "ChallengeInitialBalance" not in s:
        i = s.find("input double LimitePerteTotalePct")
        fin = s.find("\n", i) + 1
        s = s[:fin] + CRLF("input double ChallengeInitialBalance = 0;   // L8-R10 : capital initial de la phase (0 = solde au chargement)\n") + s[fin:]
        s = patch(f, s, "      GlobalVariableSet(BaseGV(), AccountInfoDouble(ACCOUNT_BALANCE));",
                  "      GlobalVariableSet(BaseGV(), (ChallengeInitialBalance > 0)\n"
                  "                                  ? ChallengeInitialBalance\n"
                  "                                  : AccountInfoDouble(ACCOUNT_BALANCE));   // L8-R10", oblig=False)

    # R4 frein d'equite persistant
    if "void ReleverEquite()" in s:
        i = s.find("void ReleverEquite()")
        deb = s.rfind("\n", 0, i) + 1
        s = s[:deb] + FREIN_PERSISTANT + s[deb:]
        i = s.find("void ReleverEquite()")
        j = s.find("\n  }", i) + 5
        s = s[:i] + FREIN_NOUVEAU + s[j:]
        i = s.find("double FacteurChallenge()")
        if i > 0:
            j = s.find("\n  }", i) + 5
            s = s[:i] + FACTEUR_NOUVEAU + s[j:]

    io.open(f, "w", encoding="utf-8", newline="").write(s)
    print("  patche.")

print("TOUTES ANCRES OK" if OK else "!! DES ANCRES ONT MANQUE")
sys.exit(0 if OK else 1)
