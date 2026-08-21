# -*- coding: utf-8 -*-
"""CONSTRUCTION DE L6+ (demande Jimmy : « construit la variante l6+ avec
turbo cousin » — construire seulement, NE PAS deployer).
L6+ = L6 + TURBO-COUSSIN (valide au banc verif_comite_vitesse.py :
reussite 78 %, duree mediane 109 j au lieu de 94 %/157 j) :
  - tant que l'equite < baseline x (1 + TurboCoussinPct %), le risque
    par trade est multiplie par TurboMultiplicateur (1,33) ;
  - des que le coussin est fait, retour au risque normal (x1,0) ;
  - gardien -2,5 %, arret -8 % et toutes les protections INCHANGES.
Baseline = MACROBOT_BASE_<login> (posee au premier lancement = debut de
la phase sur un compte FTMO neuf). Identites [L6+]/[L6+SC]. MEMES MAGICS
que L5/L6 : ne jamais attacher deux generations en meme temps."""
import glob, io, os, shutil, sys

SRC = [(r"C:\MT6\MQL5\Experts\Jimmy L6", r"C:\MT6\MQL5\Experts\Jimmy L6+"),
       (r"C:\MT6\MQL5\Experts\Jimmy L6 sans challenge", r"C:\MT6\MQL5\Experts\Jimmy L6+ sans challenge")]
for src, dst in SRC:
    if not os.path.isdir(dst):
        os.makedirs(dst)
    for f in glob.glob(os.path.join(src, "*.mq5")):
        shutil.copy2(f, dst)
print("dossiers L6+ crees")

OK = True
def patch(f, s, ancien, nouveau, n_attendu=1):
    global OK
    n = s.count(ancien)
    if n != n_attendu:
        print("  !! ANCRE (%d au lieu de %d) dans %s : %r..."
              % (n, n_attendu, f.split("\\")[-1], ancien[:60]))
        OK = False
        return s
    return s.replace(ancien, nouveau)

CRLF = lambda t: t.replace("\n", "\r\n")

INPUTS_TURBO = CRLF(
    "input bool   TurboCoussinActif     = true;   // L6+ : x TurboMultiplicateur tant que le coussin n'est pas fait, puis x1,0\n"
    "input double TurboMultiplicateur   = 1.33;   // L6+ : multiplicateur de risque avant le coussin (banc : 78 % / 109 j)\n"
    "input double TurboCoussinPct       = 4.0;    // L6+ : coussin (en % au-dessus de la baseline) qui coupe le turbo\n")

FONCTION_TURBO = CRLF(
    "\n//+------------------------------------------------------------------+\n"
    "//| L6+ : turbo-coussin — x1,33 tant que l'equite n'a pas +4 % au-   |\n"
    "//| dessus de la baseline de la phase, puis retour au risque normal. |\n"
    "//+------------------------------------------------------------------+\n"
    "double FacteurTurbo()\n"
    "  {\n"
    "   if(!TurboCoussinActif) return 1.0;\n"
    "   if(!GlobalVariableCheck(BaseGV())) return 1.0;\n"
    "   double basePhase = GlobalVariableGet(BaseGV());\n"
    "   if(basePhase <= 0) return 1.0;\n"
    "   if(AccountInfoDouble(ACCOUNT_EQUITY) >= basePhase * (1.0 + TurboCoussinPct / 100.0))\n"
    "      return 1.0;   // coussin fait : on finit au risque normal\n"
    "   return TurboMultiplicateur;\n"
    "  }\n")

for f in sorted(glob.glob(r"C:\MT6\MQL5\Experts\Jimmy L6+*\*.mq5")):
    s = io.open(f, encoding="utf-8", errors="replace", newline="").read()
    nom = f.split("\\")[-1]
    if "TurboCoussinActif" in s:
        print("deja fait :", nom); continue
    print("--- " + nom)

    # identite L6 -> L6+ (chaines et commentaires)
    s = s.replace("L6", "L6+")

    # inputs apres SpreadEntreeMaxPct
    idx = s.find("input double SpreadEntreeMaxPct")
    if idx < 0:
        print("  !! input SpreadEntreeMaxPct absent"); OK = False; continue
    fin = s.find("\n", idx) + 1
    s = s[:fin] + INPUTS_TURBO + s[fin:]

    # fonction apres la ligne BaseGV()
    idx = s.find("string BaseGV()")
    fin = s.find("\n", idx) + 1
    s = s[:fin] + FONCTION_TURBO + s[fin:]

    # multiplication dans le calcul du risque
    s = patch(f, s, "* facteurVol * FacteurRisqueGlobal * FacteurChallenge()",
              "* facteurVol * FacteurRisqueGlobal * FacteurTurbo() * FacteurChallenge()")

    # empreinte de demarrage
    if "XAUUSD_Or" in nom or "US100_Nasdaq" in nom:
        ancre = 'Print("MacroBot L6+ demarre'
    else:
        ancre = 'Print("L6+ charge | decision='
    idx = s.find(ancre)
    if idx < 0:
        print("  !! ancre empreinte absente"); OK = False
    else:
        debut_ligne = s.rfind("\n", 0, idx) + 1
        indent = s[debut_ligne:idx]
        s = s[:debut_ligne] + indent + 'Print("L6+ turbo-coussin | actif=", TurboCoussinActif, " mult=", TurboMultiplicateur, " coussin=+", TurboCoussinPct, "%");' + "\r\n" + s[debut_ligne:]

    io.open(f, "w", encoding="utf-8", newline="").write(s)
    print("  patche.")

print("TOUTES ANCRES OK" if OK else "!! DES ANCRES ONT MANQUE — NE PAS COMPILER SANS VERIFIER")
sys.exit(0 if OK else 1)
