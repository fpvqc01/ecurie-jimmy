# -*- coding: utf-8 -*-
"""CONSTRUCTION DE L6++ (demande Jimmy 21 aout : « construit la variante
l6++ »). L6++ = L6+ + BREAKEVEN COLLECTIF, le seul mecanisme survivant
du banc give-back (banc_giveback.py + robustesse) :

  des que le profit du trade depasse BreakevenCollectifPct, le stop
  commun ne peut plus descendre sous le prix d'entree MOYEN des unites
  ((premiere + derniere)/2, exactement la formule backtestee).

Chiffres du banc (config L6, donnees propres, simulateur FTMO exact) :
  reference L6      : +38,1 % | 94 % | 157 j | DD -16,7
  breakeven a +5 %  : +38,2 % | 97 % | 156 j   <-- DEFAUT (le plus sur)
  breakeven a +6 %  : +38,6 % | 92 % | 144 j   (13 jours de moins)
  plateau verifie 5-9 %, gagne sur les DEUX fenetres ; sur 2021-2026
  il ajoute meme +5 pts de reussite (88 -> 93 %).

IMPORTANT : le TURBO-COUSSIN herite de L6+ est mis a FALSE par defaut,
pour que L6++ corresponde exactement a la config testee (L6 + breakeven).
Le mettre a true cumule les deux mecanismes -- combinaison NON backtestee.
Applique aux 2 manches qui pyramident : Cassure BTC et Petrole."""
import glob, io, os, shutil, sys

SRC = [(r"C:\MT6\MQL5\Experts\Jimmy L6+", r"C:\MT6\MQL5\Experts\Jimmy L6++"),
       (r"C:\MT6\MQL5\Experts\Jimmy L6+ sans challenge", r"C:\MT6\MQL5\Experts\Jimmy L6++ sans challenge")]
for src, dst in SRC:
    if not os.path.isdir(dst):
        os.makedirs(dst)
    for f in glob.glob(os.path.join(src, "*.mq5")):
        base = os.path.basename(f).replace("_L6+_", "_L6++_")
        shutil.copy2(f, os.path.join(dst, base))
print("dossiers L6++ crees")

OK = True
def patch(f, s, ancien, nouveau, n=1):
    global OK
    c = s.count(ancien)
    if c != n:
        print("  !! ANCRE (%d au lieu de %d) : %r..." % (c, n, ancien[:60])); OK = False
        return s
    return s.replace(ancien, nouveau)

CRLF = lambda t: t.replace("\n", "\r\n")

INPUTS = CRLF(
    "input bool   BreakevenCollectifActif = true;  // L6++ : proteger le point mort quand la pyramide est pleine\n"
    "input double BreakevenCollectifPct   = 5.0;   // L6++ : seuil de profit du trade qui arme la protection (plateau 5-9 ; 6.0 = 13 jours de moins)\n")

FONCTION = CRLF(
    "\n//+------------------------------------------------------------------+\n"
    "//| L6++ : prix d'entree MOYEN des unites = (premiere + derniere)/2, |\n"
    "//| exactement la formule validee au banc give-back du 21 aout.      |\n"
    "//+------------------------------------------------------------------+\n"
    "double PrixPremiereUnite()   // prix d'ouverture le plus BAS = 1re unite\n"
    "  {\n"
    "   double p = 0.0;\n"
    "   for(int i = PositionsTotal() - 1; i >= 0; i--)\n"
    "     {\n"
    "      ulong ticket = PositionGetTicket(i);\n"
    "      if(ticket == 0) continue;\n"
    "      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;\n"
    "      if(PositionGetInteger(POSITION_MAGIC) != NumeroMagique) continue;\n"
    "      double po = PositionGetDouble(POSITION_PRICE_OPEN);\n"
    "      if(p == 0.0 || po < p) p = po;\n"
    "     }\n"
    "   return(p);\n"
    "  }\n"
    "\n"
    "//| Remonte le niveau de stop au point mort collectif si le trade a  |\n"
    "//| depasse le seuil de profit. Ne fait JAMAIS descendre le stop.    |\n"
    "double AppliquerBreakevenCollectif(double niveau, double dernier)\n"
    "  {\n"
    "   if(!BreakevenCollectifActif || BreakevenCollectifPct <= 0) return(niveau);\n"
    "   double premiere = PrixPremiereUnite();\n"
    "   if(premiere <= 0 || dernier <= 0) return(niveau);\n"
    "   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);\n"
    "   if(bid <= 0) return(niveau);\n"
    "   double gain = (bid - premiere) / premiere;\n"
    "   if(gain < BreakevenCollectifPct / 100.0) return(niveau);\n"
    "   double moyen = (premiere + dernier) / 2.0;\n"
    "   if(moyen > niveau)\n"
    "     {\n"
    "      static datetime dernierAvis = 0;\n"
    "      if(TimeCurrent() - dernierAvis > 3600)\n"
    "        {\n"
    "         dernierAvis = TimeCurrent();\n"
    "         Print(\"L6++ breakeven collectif arme : gain \", DoubleToString(gain * 100, 2),\n"
    "               \" % -> stop remonte au point mort \", DoubleToString(moyen, _Digits));\n"
    "        }\n"
    "      return(moyen);\n"
    "     }\n"
    "   return(niveau);\n"
    "  }\n")

for f in sorted(glob.glob(r"C:\MT6\MQL5\Experts\Jimmy L6++*\*.mq5")):
    s = io.open(f, encoding="utf-8", errors="replace", newline="").read()
    nom = os.path.basename(f)
    if "BreakevenCollectifActif" in s:
        print("deja fait :", nom); continue
    print("--- " + nom)

    s = s.replace("L6+", "L6++")

    # turbo desactive par defaut : L6++ = la config exactement testee
    s = patch(f, s, "input bool   TurboCoussinActif     = true;",
              "input bool   TurboCoussinActif     = false;  // L6++ : turbo OFF par defaut (la combinaison turbo + breakeven n'est PAS backtestee)")

    est_pyramide = ("BTCUSD_Cassure" in nom) or ("USOIL_Petrole" in nom)
    if est_pyramide:
        idx = s.find("input double StopSousDerniereUniteATR")
        fin = s.find("\n", idx) + 1
        s = s[:fin] + INPUTS + s[fin:]

        idx = s.find("double PrixDerniereUnite()")
        deb = s.rfind("\n", 0, idx) + 1
        s = s[:deb] + FONCTION + s[deb:]

        s = patch(f, s,
            "      AppliquerStopCommun(niveauStop);",
            "      niveauStop = AppliquerBreakevenCollectif(niveauStop, dernier);   // L6++\r\n"
            "      AppliquerStopCommun(niveauStop);")

        anc = 'Print("L6++ charge | PyramideMax='
        idx = s.find(anc)
        if idx < 0:
            print("  !! empreinte absente"); OK = False
        else:
            deb = s.rfind("\n", 0, idx) + 1
            ind = s[deb:idx]
            s = (s[:deb] + ind +
                 'Print("L6++ breakeven collectif | actif=", BreakevenCollectifActif, " seuil=+", BreakevenCollectifPct, "%");'
                 + "\r\n" + s[deb:])

    io.open(f, "w", encoding="utf-8", newline="").write(s)
    print("  patche%s." % ("" if est_pyramide else " (identite seulement : pas de pyramide)"))

print("TOUTES ANCRES OK" if OK else "!! DES ANCRES ONT MANQUE")
sys.exit(0 if OK else 1)
