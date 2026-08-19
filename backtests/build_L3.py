# -*- coding: utf-8 -*-
"""Construction de l'ECURIE L3 a partir des sources I2+.
Changements valides le 19 aout 2026 :
  1. Gardien quotidien -3,5 % -> -2,5 % (les 5 robots)
  2. PYRAMIDAGE Turtle sur les 2 robots de cassure : +1 unite chaque +0,5 ATR,
     max 3 unites, stop commun a 2,0 ATR sous la derniere unite
  3. Plafond d'ecurie : compte les PILES (un robot pyramide = 1 siege)
  4. Test de position robuste dans les robots fib (hedging)
  5. Nouveaux magics 202609xx
  6. Commentaires d'ordre corriges
"""
import os, re, shutil

SRC = r"C:\Users\jplou\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Experts\Jimmy I2+"
DST = r"C:\Users\jplou\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Experts\Jimmy L3"
DL = r"C:\Users\jplou\Downloads\Ecurie_L3_sources"
os.makedirs(DST, exist_ok=True)
os.makedirs(DL, exist_ok=True)

FICHIERS = {
    "BTCUSD_EMA_I2+_H1.mq5": ("BTCUSD_EMA_L3_H1.mq5", False),
    "XAUUSD_Or_I2+_H4.mq5": ("XAUUSD_Or_L3_H4.mq5", False),
    "US100_Nasdaq_I2+_H4.mq5": ("US100_Nasdaq_L3_H4.mq5", False),
    "BTCUSD_Cassure_I2+_H4.mq5": ("BTCUSD_Cassure_L3_H4.mq5", True),
    "USOIL_Petrole_I2+_D1.mq5": ("USOIL_Petrole_L3_D1.mq5", True),
}

CAP_ECURIE = """int ComptePositionsEcurie()
  {
   // L3 : on compte les PILES, pas les positions. Un robot qui pyramide
   // (3 unites sur le meme marche) occupe UN seul siege de l'ecurie.
   string vues = "";
   int n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      long m = PositionGetInteger(POSITION_MAGIC);
      if(m != 20260915 && m != 20260917 && m != 20260918) continue;
      string cle = "|" + (string)m + ":" + PositionGetString(POSITION_SYMBOL) + "|";
      if(StringFind(vues, cle) >= 0) continue;
      vues += cle;
      n++;
     }
   return(n);
  }"""

INPUTS_PYR = """input bool   PyramidageActif    = true;  // L3 : ajouter des unites sur un trade gagnant (Turtles)
input int    MaxUnites          = 3;     // L3 : nombre maximum d'unites empilees
input double PasUniteATR        = 0.5;   // L3 : ajouter une unite chaque +N x ATR
input double StopSousDerniereUniteATR = 2.0; // L3 : stop commun a N x ATR sous la derniere unite
"""

FONCTIONS_PYR = """
//+------------------------------------------------------------------+
//| PYRAMIDAGE (L3, regle des Turtles) : l'etat est lu directement    |
//| dans les positions ouvertes -> survit a un redemarrage de MT5.    |
//+------------------------------------------------------------------+
int NombreUnites()
  {
   int n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != NumeroMagique) continue;
      n++;
     }
   return(n);
  }

double PrixDerniereUnite()   // prix d'ouverture le plus HAUT = derniere unite ajoutee
  {
   double p = 0.0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != NumeroMagique) continue;
      double po = PositionGetDouble(POSITION_PRICE_OPEN);
      if(po > p) p = po;
     }
   return(p);
  }

double LotUnite()            // taille de la 1re unite (prix d'ouverture le plus BAS)
  {
   double p = 0.0, lot = 0.0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != NumeroMagique) continue;
      double po = PositionGetDouble(POSITION_PRICE_OPEN);
      if(p == 0.0 || po < p) { p = po; lot = PositionGetDouble(POSITION_VOLUME); }
     }
   return(lot);
  }

void AppliquerStopCommun(double niveau)
  {
   double distMin = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
   double bid     = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(niveau > bid - distMin) niveau = bid - distMin;
   niveau = NormalizeDouble(niveau, _Digits);
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != NumeroMagique) continue;
      double slActuel = PositionGetDouble(POSITION_SL);
      if(niveau > slActuel + _Point)      // le stop ne fait que monter
         trade.PositionModify(ticket, niveau, PositionGetDouble(POSITION_TP));
     }
  }

"""

HELPER_FIB = """
//+------------------------------------------------------------------+
//| L3 : test de position robuste (PositionSelect n'est pas fiable    |
//| sur un compte hedging) -> boucle explicite symbole + magic.       |
//+------------------------------------------------------------------+
bool PositionOuverte()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != NumeroMagique) continue;
      return(true);
     }
   return(false);
  }

"""


def patch_commun(t):
    t = re.sub(r"input double LimitePerteJourPct\s*=\s*3\.5;[^\r\n]*",
               "input double LimitePerteJourPct   = 2.5;    // L3 : resserre (valide 19 aout ; FTMO = 5)", t)
    t = t.replace("20260815", "20260915").replace("20260817", "20260917").replace("20260818", "20260918")
    t = re.sub(r"int ComptePositionsEcurie\(\)\s*\{.*?\n  \}", CAP_ECURIE, t, count=1, flags=re.S)
    t = t.replace("MacroBot_I2", "Ecurie_L3")
    t = t.replace("I2+", "L3").replace("MacroBot I2", "MacroBot L3")
    return t


def patch_fib(t):
    t = t.replace("int ComptePositionsEcurie()", HELPER_FIB + "int ComptePositionsEcurie()", 1)
    t = t.replace("PositionSelect(_Symbol)", "PositionOuverte()")
    return t


def patch_cassure(t):
    t = re.sub(r"(input bool   JournalActif)", INPUTS_PYR + r"\1", t, count=1)
    marqueur = "//+------------------------------------------------------------------+\nvoid OnTick()"
    t = t.replace(marqueur, FONCTIONS_PYR + marqueur, 1)
    return t


for src_nom, (dst_nom, est_cassure) in FICHIERS.items():
    with open(os.path.join(SRC, src_nom), "r", encoding="utf-8", errors="replace") as f:
        t = f.read()
    t = patch_commun(t)
    t = patch_cassure(t) if est_cassure else patch_fib(t)
    with open(os.path.join(DST, dst_nom), "w", encoding="utf-8") as f:
        f.write(t)
    shutil.copy(os.path.join(DST, dst_nom), os.path.join(DL, dst_nom))
    marque = "PYRAMIDAGE" if est_cassure else "fib"
    print("  %-28s ecrit (%d car., %s)" % (dst_nom, len(t), marque))

print("\nEtape 1 terminee. Reste : inserer la logique de pyramidage dans OnTick.")
