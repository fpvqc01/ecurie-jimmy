# -*- coding: utf-8 -*-
"""L6R13 = la variante VITESSE demandee par Jimmy le 21 aout.

Construite a partir de L8, PAS de L6 : elle garde donc les 12 bogues
corriges (frein d'equite persistant, magics distincts, risque sur l'equite,
plafond de positions, marge sur les unites de pyramide) et R13, la fermeture
automatique a +10 % de profit du compte.

On ne revient que sur les DEUX reglages qui font le troc vitesse/creux :
  gardien intrajournalier  1,75 %  ->  2,50 %   (celui de L6)
  breakeven collectif      actif   ->  inactif  (celui de L6)

Chiffres mesures (donnees reparees, simulateur FTMO exact, R13 modelise) :
  L6R13 : 86 %/175 j (10 ans) et 87 %/169 j (2021-26), creux -18,7 %
  L8    : 89 %/205 j (10 ans) et 84 %/228 j (2021-26), creux -13,9 %
= 30 a 60 jours plus vite, au prix de 4,8 points de creux en plus.

RESERVE : le banc ne modelise PAS le plafond de notionnel (L8-R3), qu'on
garde ici comme assurance contre les gaps. Compter environ 1 point de
rendement annuel de moins que le chiffre du banc."""
import glob, io, os, shutil, sys

SRC = r"C:\MT6\MQL5\Experts\Jimmy L8"
DST = r"C:\MT6\MQL5\Experts\Jimmy L6R13"
OK = True
def patch(nom, s, a, b, n=1):
    global OK
    c = s.count(a)
    if c != n:
        print("  !! ANCRE (%d/%d) : %r" % (c, n, a[:60])); OK = False; return s
    return s.replace(a, b)

if os.path.isdir(DST):
    print("!! %s existe deja - rien fait, verifie avant de relancer" % DST); sys.exit(1)
os.makedirs(DST)

for f in sorted(glob.glob(os.path.join(SRC, "*.mq5"))):
    nom = os.path.basename(f).replace("_L8_", "_L6R13_")
    d = os.path.join(DST, nom)
    shutil.copy(f, d)
    s = io.open(d, encoding="utf-8", errors="replace", newline="").read()
    print("--- " + nom)

    # 1. gardien : 1,75 -> 2,50
    avant = s
    for ancien in ("input double LimitePerteJourPct   = 1.75;",
                   "input double LimitePerteJourPct            = 1.75;"):
        if ancien in s:
            s = s.replace(ancien, ancien.replace("1.75", "2.50"))
            break
    if s == avant:
        print("  !! gardien introuvable"); OK = False
    s = s.replace("// L8-R1 : resserre (banc L8 : DD -18,7 -> -13,9)",
                  "// L6R13 : gardien de L6 (variante VITESSE : -60 j, creux -18,7 %)")
    s = s.replace("// L8-R1 : resserre (banc L8)",
                  "// L6R13 : gardien de L6 (variante VITESSE : -60 j, creux -18,7 %)")

    # 2. breakeven collectif : actif -> inactif (les 2 manches qui pyramident)
    if "BreakevenCollectifActif = true" in s:
        s = patch(nom, s,
            "input bool   BreakevenCollectifActif = true;   // L8-R2 : protege le point mort quand le trade est bien en profit",
            "input bool   BreakevenCollectifActif = false;  // L6R13 : DESACTIVE (il coute 30 jours ; c'est le prix de la vitesse)")

    # 3. empreintes : L8 -> L6R13, pour ne jamais confondre les deux dans le journal
    s = s.replace('Print("L8 charge | ', 'Print("L6R13 charge | ')
    s = s.replace('Print("L8 | ',        'Print("L6R13 | ')
    s = s.replace('Print("L8-R13 | ',    'Print("L6R13-R13 | ')
    s = s.replace('Print("L8 : ',        'Print("L6R13 : ')
    s = s.replace('Notifier("L8 : ',     'Notifier("L6R13 : ')
    s = s.replace('"MacroBot L8 demarre','"MacroBot L6R13 demarre')

    io.open(d, "w", encoding="utf-8", newline="").write(s)
    print("  ecrit.")

print()
print("TOUTES ANCRES OK" if OK else "!! DES ANCRES ONT MANQUE")
sys.exit(0 if OK else 1)
