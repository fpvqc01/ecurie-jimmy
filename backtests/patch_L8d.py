# -*- coding: utf-8 -*-
"""L8-R13, deuxieme forme : Or et Nasdaq utilisent GuardianBlocks() qui
retourne TRUE quand ca bloque (semantique inversee) et CloseAllOurs("").
Ces deux-la n'ont PAS de garde 'base <= 0' : on la met dans la condition,
sinon une baseline a zero fermerait tout des le premier tick."""
import io, os, sys
DST = r"C:\MT6\MQL5\Experts\Jimmy L8"
OK = True
CRLF = lambda t: t.replace("\n", "\r\n")

ANCRE = CRLF("""   if(GlobalVariableCheck(HaltGV()) && GlobalVariableGet(HaltGV()) > 0.5)
     {
      CloseAllOurs("");   // L4.32 : on retente la fermeture a chaque tick
      return true;
     }
""")

BLOC = ANCRE + CRLF("""
   // ---- L8-R13 : OBJECTIF DE PHASE ATTEINT -> on encaisse ----
   // FTMO valide sur le solde POSITIONS FERMEES. Tant que le profit reste
   // flottant il ne compte pas, et il peut repartir. Des que l'equite passe
   // l'objectif (plus un coussin pour le spread), on ferme tout et on arrete.
   if(base > 0 && ObjectifPhasePct > 0
      && equity >= base * (1.0 + (ObjectifPhasePct + MargeObjectifPct) / 100.0))
     {
      Notifier(StringFormat("OBJECTIF DE PHASE ATTEINT (+%.2f %%) - fermeture de tout, arret. Solde a encaisser : %.2f",
                            100.0 * (equity / base - 1.0), equity));
      CloseAllOurs("");
      GlobalVariableSet(HaltGV(), 1.0);
      GlobalVariableSet("MACROBOT_CIBLE_" + (string)AccountInfoInteger(ACCOUNT_LOGIN), equity);
      return true;
     }
""")

for nom in ("US100_Nasdaq_L8_H4.mq5", "XAUUSD_Or_L8_H4.mq5"):
    f = os.path.join(DST, nom)
    s = io.open(f, encoding="utf-8", errors="replace", newline="").read()
    print("--- " + nom)
    if "L8-R13 : OBJECTIF DE PHASE" in s:
        print("  deja fait"); continue
    if s.count(ANCRE) != 1:
        print("  !! ANCRE introuvable"); OK = False; continue
    s = s.replace(ANCRE, BLOC)

    # Or a recu 2 fois l'input (1re passe partielle) : on nettoie
    dbl = CRLF("input double ObjectifPhasePct   = 10.0;  // L8-R13 : objectif de la phase en % (10 = phase 1 FTMO, 5 = phase 2, 0 = desactive)\n"
               "input double MargeObjectifPct   = 0.25;  // L8-R13 : coussin encaisse au-dessus de l'objectif (spread/commission)\n")
    while s.count(dbl) > 1:
        i = s.find(dbl); s = s[:i] + s[i + len(dbl):]
        print("  input R13 en double : retire")

    io.open(f, "w", encoding="utf-8", newline="").write(s)
    print("  patche.")

# empreinte manquante pour le Nasdaq seulement
f = os.path.join(DST, "US100_Nasdaq_L8_H4.mq5")
s = io.open(f, encoding="utf-8", errors="replace", newline="").read()
if "L8-R13 | objectif" not in s:
    anc = '   Print("MacroBot L8 demarre (indicateurs journaliers). Baseline: "'
    if s.count(anc) != 1:
        print("!! empreinte Nasdaq : ancre introuvable"); OK = False
    else:
        s = s.replace(anc, CRLF('   Print("L8-R13 | objectif de phase=", ObjectifPhasePct, "% (+", MargeObjectifPct, "% de coussin) gardien=", LimitePerteJourPct, "%");\n') + anc)
        io.open(f, "w", encoding="utf-8", newline="").write(s)
        print("empreinte Nasdaq ajoutee.")

print("TOUTES ANCRES OK" if OK else "!! DES ANCRES ONT MANQUE")
sys.exit(0 if OK else 1)
