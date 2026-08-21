# -*- coding: utf-8 -*-
"""L8-R13 : FERMETURE AUTOMATIQUE A L'OBJECTIF DE PHASE.

Pourquoi c'est necessaire : FTMO valide l'objectif (+10 % puis +5 %) sur le
solde POSITIONS FERMEES, pas sur l'equite flottante. Les robots ne fermaient
jamais a l'objectif : ils attendaient leurs stops, et le profit flottant
pouvait repartir avant d'etre encaisse.

Mesure au simulateur corrige (sim_ferme.py, 21 aout) :
  sans fermeture a l'objectif : 80 % de reussite, 274 jours (10 ans)
  avec fermeture a l'objectif : 89 % de reussite, 205 jours
= +9 points de reussite et -69 jours."""
import glob, io, os, sys
DST = r"C:\MT6\MQL5\Experts\Jimmy L8"
OK = True
def patch(f, s, a, b, n=1):
    global OK
    c = s.count(a)
    if c != n:
        print("  !! ANCRE (%d/%d) : %r" % (c, n, a[:60])); OK = False; return s
    return s.replace(a, b)
CRLF = lambda t: t.replace("\n", "\r\n")

INPUTS = CRLF("""input double ObjectifPhasePct   = 10.0;  // L8-R13 : objectif de la phase en % (10 = phase 1 FTMO, 5 = phase 2, 0 = desactive)
input double MargeObjectifPct   = 0.25;  // L8-R13 : coussin encaisse au-dessus de l'objectif (spread/commission)
""")

ANCRE_HALT = CRLF("""   if(GlobalVariableCheck(HaltGV()) && GlobalVariableGet(HaltGV()) > 0.5)
     {
      FermerPositions(true);   // L4.32 : on retente la fermeture a chaque tick
      return(false);
     }
""")

BLOC = ANCRE_HALT + CRLF("""
   // ---- L8-R13 : OBJECTIF DE PHASE ATTEINT -> on encaisse ----
   // FTMO valide sur le solde POSITIONS FERMEES. Tant que le profit reste
   // flottant il ne compte pas, et il peut repartir. Des que l'equite passe
   // l'objectif (plus un coussin pour le spread), on ferme tout et on
   // arrete : la phase est gagnee, c'est a Jimmy de passer a la suivante.
   if(ObjectifPhasePct > 0
      && equite >= base * (1.0 + (ObjectifPhasePct + MargeObjectifPct) / 100.0))
     {
      Notifier(StringFormat("🎯 OBJECTIF DE PHASE ATTEINT (+%.2f %%). Fermeture de tout, arret. Solde a encaisser : %.2f",
                            100.0 * (equite / base - 1.0), equite));
      FermerPositions(true);
      GlobalVariableSet(HaltGV(), 1.0);
      GlobalVariableSet("MACROBOT_CIBLE_" + (string)AccountInfoInteger(ACCOUNT_LOGIN), equite);
      return(false);
     }
""")

for f in sorted(glob.glob(os.path.join(DST, "*.mq5"))):
    nom = os.path.basename(f)
    s = io.open(f, encoding="utf-8", errors="replace", newline="").read()
    if "ObjectifPhasePct" in s:
        print("deja fait :", nom); continue
    print("--- " + nom)

    i = s.find("input double ChallengeInitialBalance = 0;")
    fin = s.find("\n", i) + 1
    s = s[:fin] + INPUTS + s[fin:]

    s = patch(f, s, ANCRE_HALT, BLOC)

    # empreinte : une seule ligne ajoutee, sur la 1re occurrence
    anc = 'Print("L8 charge | '
    i = s.find(anc)
    if i < 0:
        print("  !! empreinte absente"); OK = False
    else:
        deb = s.rfind("\n", 0, i) + 1
        ind = s[deb:i]
        s = (s[:deb] + ind + 'Print("L8-R13 | objectif de phase=", ObjectifPhasePct,'
             ' "% (+", MargeObjectifPct, "% de coussin)");' + "\r\n" + s[deb:])

    io.open(f, "w", encoding="utf-8", newline="").write(s)
    print("  patche.")

print("TOUTES ANCRES OK" if OK else "!! DES ANCRES ONT MANQUE")
sys.exit(0 if OK else 1)
