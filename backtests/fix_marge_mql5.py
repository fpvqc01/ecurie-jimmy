# -*- coding: utf-8 -*-
"""Verification de marge pour les 5 robots MQL5 L3 (2 variantes de fonction)."""
import glob, os, re

MQ5 = r"C:\Users\jplou\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Experts\Jimmy L3"

BLOC = """
//+------------------------------------------------------------------+
//| L3 : verifie que la MARGE suffit, sinon reduit le lot ou annule   |
//| (sans ca l'ordre est rejete et le signal est perdu en silence)    |
//+------------------------------------------------------------------+
double LotSelonMarge(double lot)
  {
   double lotMin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double pas    = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double prix   = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double marge  = 0.0;
   int essais = 0;
   while(lot >= lotMin && essais < 12)
     {
      if(OrderCalcMargin(ORDER_TYPE_BUY, _Symbol, lot, prix, marge))
         if(marge < AccountInfoDouble(ACCOUNT_MARGIN_FREE) * 0.95)
            return(lot);
      lot -= MathMax(pas, lot * 0.2);
      if(pas > 0) lot = MathFloor(lot / pas) * pas;
      essais++;
     }
   Print("Marge insuffisante pour ouvrir : ordre annule.");
   return(0.0);
  }
"""

# variante A (robots fib/EMA) : return MathMin(lots, maxLot);
A_ANCIEN = """   if(lots < minLot)
      return 0;
   return MathMin(lots, maxLot);"""
A_NOUVEAU = """   if(lots < minLot)
      return 0;
   return LotSelonMarge(MathMin(lots, maxLot));"""

for p in sorted(glob.glob(os.path.join(MQ5, "*.mq5"))):
    t = open(p, encoding="utf-8", errors="replace").read()
    nom = os.path.basename(p)
    if "LotSelonMarge" in t:
        print("  %-28s deja fait" % nom); continue
    modifie = False
    if A_ANCIEN in t:
        t = t.replace(A_ANCIEN, A_NOUVEAU, 1); modifie = True
    else:
        # variante B (cassures) : chercher le return final de CalculerLot
        m = re.search(r"(double CalculerLot\(double distanceSL\).*?)(   return\(NormalizeDouble\(lot, 2\)\);)",
                      t, re.S)
        if m:
            t = t.replace(m.group(2), "   return(LotSelonMarge(NormalizeDouble(lot, 2)));", 1)
            modifie = True
    if not modifie:
        print("  %-28s !! aucun motif de retour trouve" % nom); continue
    # inserer la fonction juste avant la fonction de lot
    for ancre in ("double LotsForRisk(double stopDist)", "double CalculerLot(double distanceSL)"):
        if ancre in t:
            t = t.replace(ancre, BLOC.strip() + "\n\n" + ancre, 1)
            break
    open(p, "w", encoding="utf-8").write(t)
    print("  %-28s verification de marge ajoutee" % nom)
