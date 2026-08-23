# -*- coding: utf-8 -*-
"""R13 PAR PHASE : +10 % en phase 1, +5 % en phase 2 (demande de Jimmy).

AVANT : un seul reglage `ObjectifPhasePct = 10.0`, que Jimmy devait penser a
changer a la main en passant en phase 2. S'il oubliait, le robot visait +10 %
alors que la phase 2 se valide a +5 % : il laissait courir 5 points de profit
pour rien, avec tout le risque que ca comporte.

APRES : on declare la PHASE, pas le pourcentage.
    PHASE_1        -> objectif +10 %
    PHASE_2        -> objectif  +5 %
    COMPTE_FINANCE -> aucune fermeture automatique (les retraits se font a la
                      main ; le robot ne doit pas s'arreter tout seul)

Les deux pourcentages restent modifiables, mais le robot choisit le bon tout
seul selon la phase declaree.

Report des valeurs existantes : 10.0 -> PHASE_1, 5.0 -> PHASE_2,
0.0 -> COMPTE_FINANCE (D7 avait R13 desactive, on preserve son comportement).
"""
import glob, io, os, re, sys

RACINES = [r"C:\MT6\MQL5\Experts", r"C:\NouveauMT5\MQL5\Experts"]
SAUV = r"C:\Users\jplou\Downloads\sauvegarde_avant_R13_phases"

BLOC = (
 'enum PhaseChallengeFTMO\r\n'
 '  {\r\n'
 '   PHASE_1        = 1,   // Phase 1 : objectif +10 %\r\n'
 '   PHASE_2        = 2,   // Phase 2 : objectif +5 %\r\n'
 '   COMPTE_FINANCE = 0    // Compte finance : aucune fermeture automatique\r\n'
 '  };\r\n'
 'input PhaseChallengeFTMO PhaseActuelle = {PHASE};   // R13 : la phase en cours. Le robot en deduit son objectif.\r\n'
 'input double ObjectifPhase1Pct  = 10.0;  // R13 : objectif de la phase 1, en % du capital de depart\r\n'
 'input double ObjectifPhase2Pct  = 5.0;   // R13 : objectif de la phase 2, en % du capital de depart\r\n'
 '\r\n'
 '//+------------------------------------------------------------------+\r\n'
 '//| R13 : l objectif depend de la phase. Avant, un seul pourcentage   |\r\n'
 '//| qu il fallait changer a la main entre les deux phases - oublier   |\r\n'
 '//| de le faire, c etait viser +10 % alors que +5 % suffisait.        |\r\n'
 '//+------------------------------------------------------------------+\r\n'
 'double ObjectifPhasePctCourant()\r\n'
 '  {\r\n'
 '   if(PhaseActuelle == PHASE_1) return(ObjectifPhase1Pct);\r\n'
 '   if(PhaseActuelle == PHASE_2) return(ObjectifPhase2Pct);\r\n'
 '   return(0.0);   // compte finance : on ne ferme pas tout seul\r\n'
 '  }\r\n')

MAP = {"10.0": "PHASE_1", "10": "PHASE_1", "5.0": "PHASE_2", "5": "PHASE_2",
       "0.0": "COMPTE_FINANCE", "0": "COMPTE_FINANCE"}

RE_INPUT = re.compile(r"^input\s+double\s+ObjectifPhasePct\s*=\s*([0-9.]+)\s*;.*?$", re.M)

os.makedirs(SAUV, exist_ok=True)
total_f = total_e = 0
soucis = []

for r in RACINES:
    term = "MT6" if r.startswith(r"C:\MT6") else "MT7"
    for d in sorted(glob.glob(os.path.join(r, "Jimmy *"))):
        ecurie = os.path.basename(d)
        touches = 0
        for f in sorted(glob.glob(os.path.join(d, "*.mq5"))):
            s = io.open(f, encoding="utf-8", errors="replace", newline="").read()
            if "ObjectifPhasePctCourant" in s:
                continue                      # deja fait
            m = RE_INPUT.search(s)
            if not m:
                continue                      # pas de R13 dans ce fichier
            valeur = m.group(1)
            phase = MAP.get(valeur)
            if phase is None:
                soucis.append("%s/%s : valeur inattendue %s" % (ecurie, os.path.basename(f), valeur))
                continue

            # sauvegarde avant ecriture
            cible = os.path.join(SAUV, term, ecurie)
            os.makedirs(cible, exist_ok=True)
            io.open(os.path.join(cible, os.path.basename(f)), "w",
                    encoding="utf-8", newline="").write(s)

            # 1) la ligne d input devient le bloc enum + inputs + fonction
            s = s[:m.start()] + BLOC.replace("{PHASE}", phase).rstrip("\r\n") + s[m.end():]
            # 2) tous les autres usages passent par la fonction
            s2 = re.sub(r"\bObjectifPhasePct\b(?!Courant)", "ObjectifPhasePctCourant()", s)
            # on ne doit pas avoir casse les nouveaux noms
            s2 = s2.replace("ObjectifPhase1Pct", "ObjectifPhase1Pct").replace(
                            "ObjectifPhase2Pct", "ObjectifPhase2Pct")
            if "ObjectifPhasePctCourant()" not in s2:
                soucis.append("%s/%s : aucun usage remplace" % (ecurie, os.path.basename(f)))
                continue
            io.open(f, "w", encoding="utf-8", newline="").write(s2)
            touches += 1
            total_f += 1
        if touches:
            total_e += 1
            print("  %-4s %-16s %d fichier(s)  -> %s" % (term, ecurie, touches, phase))

print()
print("%d fichier(s) corriges dans %d ecurie(s)." % (total_f, total_e))
print("Sauvegardes : %s" % SAUV)
if soucis:
    print("\n!! A REGARDER :")
    for x in soucis:
        print("   " + x)
sys.exit(1 if soucis else 0)
