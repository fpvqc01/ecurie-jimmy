# -*- coding: utf-8 -*-
"""L8 partie B : breakeven collectif (R2) + plafond de notionnel (R3)
+ ajouts de pyramide qui verifient la marge (R11)."""
import glob, io, os, sys
DST = r"C:\MT6\MQL5\Experts\Jimmy L8"
OK = True
def patch(f, s, a, b, n=1):
    global OK
    c = s.count(a)
    if c != n:
        print("  !! ANCRE (%d/%d) : %r" % (c, n, a[:70])); OK = False; return s
    return s.replace(a, b)
CRLF = lambda t: t.replace("\n", "\r\n")

INPUTS = CRLF("""input bool   BreakevenCollectifActif = true;   // L8-R2 : protege le point mort quand le trade est bien en profit
input double BreakevenCollectifPct   = 5.0;    // L8-R2 : seuil de profit qui arme la protection
input double PlafondNotionnelEquite  = 1.25;   // L8-R3 : notionnel max de cette manche, en multiple de l'equite (0 = aucun)
""")

FONCTIONS = CRLF("""
//+------------------------------------------------------------------+
//| L8-R2 : point mort collectif des unites = (premiere+derniere)/2   |
//+------------------------------------------------------------------+
double PrixPremiereUnite()
  {
   double p = 0.0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != NumeroMagique) continue;
      double po = PositionGetDouble(POSITION_PRICE_OPEN);
      if(p == 0.0 || po < p) p = po;
     }
   return(p);
  }

double AppliquerBreakevenCollectif(double niveau, double dernier)
  {
   if(!BreakevenCollectifActif || BreakevenCollectifPct <= 0) return(niveau);
   double premiere = PrixPremiereUnite();
   if(premiere <= 0 || dernier <= 0) return(niveau);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(bid <= 0) return(niveau);
   if((bid - premiere) / premiere < BreakevenCollectifPct / 100.0) return(niveau);
   double moyen = (premiere + dernier) / 2.0;
   return(moyen > niveau ? moyen : niveau);
  }

//+------------------------------------------------------------------+
//| L8-R3 : plafond de notionnel. Le moteur de backtest bride a 2,0x  |
//| l'equite ; les robots n'avaient AUCUN plafond (jusqu'a 3,2x       |
//| observe). Assurance contre les gaps, que le backtest ne simule pas|
//+------------------------------------------------------------------+
double NotionnelManche()
  {
   double n = 0.0;
   double contrat = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   double prix    = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != NumeroMagique) continue;
      n += PositionGetDouble(POSITION_VOLUME) * contrat * prix;
     }
   return(n);
  }

double LotSelonPlafondNotionnel(double lot)
  {
   if(PlafondNotionnelEquite <= 0) return(lot);
   double contrat = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   double prix    = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double equite  = AccountInfoDouble(ACCOUNT_EQUITY);
   if(contrat <= 0 || prix <= 0 || equite <= 0) return(lot);
   double reste = PlafondNotionnelEquite * equite - NotionnelManche();
   if(reste <= 0)
     {
      Notifier("L8 : plafond de notionnel atteint, unite refusee");
      return(0.0);
     }
   double lotMax = reste / (prix * contrat);
   if(lot > lotMax)
     {
      Notifier(StringFormat("L8 : lot plafonne par le notionnel %.2f -> %.2f", lot, lotMax));
      lot = lotMax;
     }
   double pas = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(pas > 0) lot = MathFloor(lot / pas + 1e-8) * pas;
   if(lot < SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN)) return(0.0);
   return(lot);
  }
""")

for f in sorted(glob.glob(os.path.join(DST, "*.mq5"))):
    nom = os.path.basename(f)
    if not ("BTCUSD_Cassure" in nom or "USOIL_Petrole" in nom):
        continue
    s = io.open(f, encoding="utf-8", errors="replace", newline="").read()
    if "BreakevenCollectifActif" in s:
        print("deja fait :", nom); continue
    print("--- " + nom)

    i = s.find("input double StopSousDerniereUniteATR")
    fin = s.find("\n", i) + 1
    s = s[:fin] + INPUTS + s[fin:]

    i = s.find("double PrixDerniereUnite()")
    deb = s.rfind("\n", 0, i) + 1
    s = s[:deb] + FONCTIONS + s[deb:]

    # R2 : brancher le breakeven juste avant l'application du stop commun
    s = patch(f, s, "      AppliquerStopCommun(niveauStop);",
              "      niveauStop = AppliquerBreakevenCollectif(niveauStop, dernier);   // L8-R2\r\n"
              "      AppliquerStopCommun(niveauStop);")

    # R11 + R3 : les ajouts de pyramide verifient marge ET notionnel
    s = patch(f, s, "            double lotAjout = LotUnite();",
              "            double lotAjout = LotSelonPlafondNotionnel(LotSelonMarge(LotUnite()));   // L8-R3/R11")
    s = patch(f, s, "            if(lotAjout > 0)",
              "            if(lotAjout <= 0)\r\n"
              "               Notifier(\"L8 : unite de pyramide REFUSEE (marge ou notionnel)\");\r\n"
              "            else")

    # R3 : l'entree initiale aussi
    s = patch(f, s, "   double lot = CalculerLot(distanceSL);",
              "   double lot = LotSelonPlafondNotionnel(CalculerLot(distanceSL));   // L8-R3")

    # empreinte
    anc = 'Print("L8 charge | PyramideMax='
    i = s.find(anc)
    if i < 0:
        print("  !! empreinte absente"); OK = False
    else:
        deb = s.rfind("\n", 0, i) + 1
        ind = s[deb:i]
        s = (s[:deb] + ind + 'Print("L8 | gardien=", LimitePerteJourPct, "% breakeven=+",'
             ' BreakevenCollectifPct, "% notionnelMax=", PlafondNotionnelEquite, "x equite");'
             + "\r\n" + s[deb:])

    io.open(f, "w", encoding="utf-8", newline="").write(s)
    print("  patche.")

print("TOUTES ANCRES OK" if OK else "!! DES ANCRES ONT MANQUE")
sys.exit(0 if OK else 1)
