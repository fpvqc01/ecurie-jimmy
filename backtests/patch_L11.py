# -*- coding: utf-8 -*-
"""L11 = L8+ avec le gardien intrajournalier ramene a 2,50 %.

POURQUOI. Le gardien avait ete resserre a 1,75 % dans L8 pour contenir les
journees noires du BTC. Depuis L8+, BTC Cassure est passe de 1,69 a 1,15 % de
risque : la cause est traitee a la source, et le gardien serre ne fait plus
que ralentir le robot.

BANC (backtests/banc_L11.py, chassis L8+, donnees reparees, R13) :
                            10 ans                    | 2021-2026
  gardien 1,75 % (L8+)   +23,1 %  99 %/238 j  DD -12,9 | +16,2 %  97 %/298 j
  gardien 2,50 % (L11)   +24,5 %  99 %/197 j  DD -13,1 | +20,2 %  97 %/223 j

Meme reussite exactement (99 % et 97 %), mais +1,4 et +4,0 points de
rendement annuel, et 41 a 75 JOURS DE MOINS. Le drawdown ne bouge pas
(-12,9 -> -13,1). C'est le premier gain sans contrepartie de la journee.

HYPOTHESE REJETEE AU PASSAGE : « le breakeven collectif peut remplacer le
frein d'equite ». Sur le chassis deconcentre, couper le frein fait tomber la
reussite de 99 a 83-88 % (10 ans) et de 97 a 74-76 % (recent). Le resultat
observe sur « L6++ sans challenge » ne survit pas a la deconcentration.

Le frein d'equite reste donc ON, comme dans toutes les generations depuis L3+."""
import glob, io, os, shutil, sys

SRC = r"C:\MT6\MQL5\Experts\Jimmy L8+"
DST = r"C:\MT6\MQL5\Experts\Jimmy L11"
OK = True

if os.path.isdir(DST):
    print("!! %s existe deja - rien fait" % DST); sys.exit(1)
if not os.path.isdir(SRC):
    print("!! source %s introuvable" % SRC); sys.exit(1)
os.makedirs(DST)

for f in sorted(glob.glob(os.path.join(SRC, "*.mq5"))):
    nom = os.path.basename(f).replace("_L8+_", "_L11_")
    d = os.path.join(DST, nom)
    shutil.copy(f, d)
    s = io.open(d, encoding="utf-8", errors="replace", newline="").read()
    print("--- " + nom)

    fait = False
    for anc in ("input double LimitePerteJourPct   = 1.75;",
                "input double LimitePerteJourPct            = 1.75;"):
        if anc in s:
            if s.count(anc) != 1:
                print("  !! gardien en double"); OK = False
            s = s.replace(anc, anc.replace("1.75", "2.50"))
            fait = True; break
    if not fait:
        print("  !! gardien introuvable"); OK = False
    s = s.replace("// L8-R1 : resserre (banc L8 : DD -18,7 -> -13,9)",
                  "// L11 : rendu a 2,50 % - la deconcentration du BTC a traite la cause (banc L11 : -41 a -75 jours, reussite inchangee)")
    s = s.replace("// L8-R1 : resserre (banc L8)",
                  "// L11 : rendu a 2,50 % - la deconcentration du BTC a traite la cause (banc L11 : -41 a -75 jours, reussite inchangee)")

    for a, b in (('Print("L8+ charge | ', 'Print("L11 charge | '),
                 ('Print("L8+ | ', 'Print("L11 | '),
                 ('Print("L8+-R13 | ', 'Print("L11-R13 | '),
                 ('Print("L8+ : ', 'Print("L11 : '),
                 ('Notifier("L8+ : ', 'Notifier("L11 : '),
                 ('"MacroBot L8+ demarre', '"MacroBot L11 demarre')):
        s = s.replace(a, b)

    io.open(d, "w", encoding="utf-8", newline="").write(s)
    print("    ecrit.")

print()
print("TOUTES ANCRES OK" if OK else "!! DES ANCRES ONT MANQUE")
sys.exit(0 if OK else 1)
