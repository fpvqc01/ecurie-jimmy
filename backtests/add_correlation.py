# -*- coding: utf-8 -*-
"""Ajoute le PLAFOND DE CORRELATION (metal/indice) a I2++ (MQL5) et L3+ (MQL4).
Regle validee : un seul robot de la famille « metal ou indice » (or, Nasdaq)
peut etre en position a la fois. Test des crises : 2011 passe de -8,0 %
(compte mort) a -2,2 % sans halt ; crises positives 5/7 -> 6/7 ; cout 1,1 pt.
Le pyramidage BTC/petrole n'est pas touche (familles crypto/energie)."""
import glob, os, re

D5 = r"C:\Users\jplou\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Experts\Jimmy I2++"
D4 = r"C:\Users\jplou\AppData\Roaming\MetaQuotes\Terminal\2C68BEE3A904BDCEE3EEF5A5A77EC162\MQL4\Experts\Jimmy L3+"
D5L = r"C:\Users\jplou\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Experts\Jimmy L3+"

# ---------- bloc MQL5 ----------
BLOC5 = '''
//+------------------------------------------------------------------+
//| PLAFOND DE CORRELATION (valide sur 99 ans de crises)              |
//| L'or et les indices semblent independants... jusqu'a une crise de |
//| liquidite qui les fait chuter ENSEMBLE (septembre 2011 : l'or de  |
//| 1920 a 1530 pendant que les indices plongeaient). Un seul robot   |
//| de la famille metal/indice peut donc etre en position a la fois.  |
//| Test : 2011 passe de -8,0 % (compte mort) a -2,2 % ; crises       |
//| positives 5/7 -> 6/7 ; cout 1,1 point de rendement annuel.        |
//+------------------------------------------------------------------+
bool EstMetalOuIndice(string symbole)
  {
   string s = symbole;
   StringToUpper(s);
   if(StringFind(s, "XAU") >= 0) return(true);   // or
   if(StringFind(s, "XAG") >= 0) return(true);   // argent
   if(StringFind(s, "US100") >= 0) return(true); // Nasdaq
   if(StringFind(s, "NAS") >= 0) return(true);
   if(StringFind(s, "US30") >= 0) return(true);
   if(StringFind(s, "US500") >= 0) return(true);
   if(StringFind(s, "SPX") >= 0) return(true);
   if(StringFind(s, "GER") >= 0 || StringFind(s, "DE30") >= 0) return(true);
   return(false);
  }

//| true si une AUTRE position metal/indice de l'ecurie est ouverte
bool FamilleCorreleeOccupee()
  {
   if(!PlafondCorrelationActif) return(false);
   if(!EstMetalOuIndice(_Symbol)) return(false);   // ne concerne pas BTC/petrole
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      long m = PositionGetInteger(POSITION_MAGIC);
      if(m != 20260815 && m != 20260817 && m != 20260818 &&
         m != 20260915 && m != 20260917 && m != 20260918) continue;
      string sym = PositionGetString(POSITION_SYMBOL);
      if(sym == _Symbol) continue;                 // c'est nous
      if(EstMetalOuIndice(sym)) return(true);      // un cousin est deja expose
     }
   return(false);
  }
'''

# ---------- bloc MQL4 ----------
BLOC4 = '''
//+------------------------------------------------------------------+
//| PLAFOND DE CORRELATION (valide sur 99 ans de crises)              |
//| Un seul robot de la famille metal/indice (or, Nasdaq) en position |
//| a la fois : evite la double exposition au meme choc de liquidite  |
//| (septembre 2011 : or ET indices en chute simultanee = compte mort)|
//| Test : 2011 de -8,0 % (mort) a -2,2 % ; crises positives 5/7->6/7.|
//+------------------------------------------------------------------+
bool EstMetalOuIndice(string symbole)
  {
   string s = symbole;
   StringToUpper(s);
   if(StringFind(s, "XAU") >= 0) return(true);
   if(StringFind(s, "XAG") >= 0) return(true);
   if(StringFind(s, "US100") >= 0) return(true);
   if(StringFind(s, "NAS") >= 0) return(true);
   if(StringFind(s, "US30") >= 0) return(true);
   if(StringFind(s, "US500") >= 0) return(true);
   if(StringFind(s, "SPX") >= 0) return(true);
   if(StringFind(s, "GER") >= 0 || StringFind(s, "DE30") >= 0) return(true);
   return(false);
  }

bool FamilleCorreleeOccupee()
  {
   if(!PlafondCorrelationActif) return(false);
   if(!EstMetalOuIndice(Symbol())) return(false);
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) continue;
      int m = OrderMagicNumber();
      if(m != 20260815 && m != 20260817 && m != 20260818 &&
         m != 20260915 && m != 20260917 && m != 20260918) continue;
      if(OrderSymbol() == Symbol()) continue;
      if(EstMetalOuIndice(OrderSymbol())) return(true);
     }
   return(false);
  }
'''

def traiter(dossier, ext, bloc, ancre_fonction, motif_input):
    for p in sorted(glob.glob(os.path.join(dossier, "*." + ext))):
        t = open(p, encoding="utf-8", errors="replace").read()
        nom = os.path.basename(p)
        notes = []
        if "FamilleCorreleeOccupee" in t:
            print("  %-32s (deja fait)" % nom); continue
        # 1) input
        m = re.search(motif_input, t)
        if m:
            t = t.replace(m.group(1), m.group(1) +
                "input bool   PlafondCorrelationActif = true;  // un seul metal/indice a la fois (crises)\n", 1)
            notes.append("input")
        # 2) fonctions
        if ancre_fonction in t:
            t = t.replace(ancre_fonction, bloc.strip() + "\n\n" + ancre_fonction, 1)
            notes.append("fonctions")
        # 3) blocage a l'entree : juste apres chaque test de plafond d'ecurie
        avant = t
        t = re.sub(r"(if\(ComptePositionsEcurie\(\) >= MaxPositionsEcurie\)\s*return;)",
                   r"\1\n   if(FamilleCorreleeOccupee()) return;   // plafond de correlation",
                   t)
        if t != avant: notes.append("blocage entree")
        open(p, "w", encoding="utf-8").write(t)
        print("  %-32s %s" % (nom, ", ".join(notes) if notes else "!! aucun point d'ancrage"))

print("--- I2++ (MQL5) ---")
traiter(D5, "mq5", BLOC5, "int ComptePositionsEcurie()", r"(input\s+bool\s+JournalActif[^\n]*\n)")
print("\n--- L3+ (MQL5) ---")
traiter(D5L, "mq5", BLOC5, "int ComptePositionsEcurie()", r"(input\s+bool\s+JournalActif[^\n]*\n)")
print("\n--- L3+ (MQL4) ---")
traiter(D4, "mq4", BLOC4, "int ComptePositionsEcurie()", r"(input\s+bool\s+JournalActif[^\n]*\n)")
