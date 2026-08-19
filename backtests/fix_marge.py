# -*- coding: utf-8 -*-
"""Ajoute la verification de MARGE DISPONIBLE avant tout ordre, dans les
5 robots MQL4 et les 5 robots MQL5 de l'ecurie L3.
Sans ca : erreur 134 (marge insuffisante), l'ordre echoue en silence et
le signal est perdu. Avec : on reduit le lot jusqu'a ce qu'il passe, ou
on annule proprement avec un message."""
import glob, os, re

MQ4 = r"C:\Users\jplou\AppData\Roaming\MetaQuotes\Terminal\2C68BEE3A904BDCEE3EEF5A5A77EC162\MQL4\Experts\Jimmy L3"
MQ5 = r"C:\Users\jplou\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Experts\Jimmy L3"

# ---------- MQL4 ----------
ANCIEN4 = """   if(lot < mini) return(0.0);
   if(lot > maxi) lot = maxi;
   return(NormalizeDouble(lot, 2));"""

NOUVEAU4 = """   if(lot < mini) return(0.0);
   if(lot > maxi) lot = maxi;
   lot = NormalizeDouble(lot, 2);

   // L3 : verification de la MARGE (sinon erreur 134, ordre perdu en silence)
   int essais = 0;
   while(lot >= mini && essais < 12)
     {
      ResetLastError();
      double libre = AccountFreeMarginCheck(Symbol(), OP_BUY, lot);
      if(libre > 0 && GetLastError() != 134) return(lot);
      lot = NormalizeDouble(lot - MathMax(pas, lot * 0.2), 2);   // on reduit
      essais++;
     }
   Print("Marge insuffisante pour ouvrir : ordre annule (lot demande trop gros).");
   return(0.0);"""

# ---------- MQL5 ----------
ANCIEN5_RX = re.compile(
    r"(   if\(lot < mini\) lot = mini;\n   if\(lot > maxi\) lot = maxi;\n"
    r"   return\(NormalizeDouble\(lot, 2\)\);)")

NOUVEAU5 = """   if(lot < mini) return(0.0);
   if(lot > maxi) lot = maxi;
   lot = NormalizeDouble(lot, 2);

   // L3 : verification de la MARGE avant d'envoyer l'ordre
   double marge = 0.0, prixAsk = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   int essais = 0;
   while(lot >= mini && essais < 12)
     {
      if(OrderCalcMargin(ORDER_TYPE_BUY, _Symbol, lot, prixAsk, marge))
         if(marge < AccountInfoDouble(ACCOUNT_MARGIN_FREE) * 0.95)
            return(NormalizeDouble(lot, 2));
      lot = NormalizeDouble(lot - MathMax(pas, lot * 0.2), 2);
      essais++;
     }
   Print("Marge insuffisante pour ouvrir : ordre annule.");
   return(0.0);"""

print("--- MQL4 ---")
for p in sorted(glob.glob(os.path.join(MQ4, "*.mq4"))):
    t = open(p, encoding="utf-8").read()
    nom = os.path.basename(p)
    if "AccountFreeMarginCheck" in t:
        print("  %-28s deja fait" % nom)
        continue
    if ANCIEN4 in t:
        open(p, "w", encoding="utf-8").write(t.replace(ANCIEN4, NOUVEAU4))
        print("  %-28s verification de marge ajoutee" % nom)
    else:
        print("  %-28s !! motif introuvable" % nom)

print("\n--- MQL5 ---")
for p in sorted(glob.glob(os.path.join(MQ5, "*.mq5"))):
    t = open(p, encoding="utf-8", errors="replace").read()
    nom = os.path.basename(p)
    if "OrderCalcMargin" in t:
        print("  %-28s deja fait" % nom)
        continue
    t2, n = ANCIEN5_RX.subn(NOUVEAU5, t, count=1)
    if n:
        open(p, "w", encoding="utf-8").write(t2)
        print("  %-28s verification de marge ajoutee" % nom)
    else:
        # variante : pas de clamp mini
        m = re.search(r"   if\(lot > maxi\) lot = maxi;\n   return\(NormalizeDouble\(lot, 2\)\);", t)
        if m:
            t2 = t.replace(m.group(0), NOUVEAU5.split("\n", 1)[1])
            open(p, "w", encoding="utf-8").write(t2)
            print("  %-28s verification de marge ajoutee (variante)" % nom)
        else:
            print("  %-28s !! motif introuvable" % nom)
