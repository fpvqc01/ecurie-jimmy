# -*- coding: utf-8 -*-
"""L8+ = L8 + DECONCENTRATION DU BTC + garde anti-spam sur le stop.

LE PROBLEME (rapport crises, confirme sur donnees reparees) : BTC Cassure
faisait 74,9 % du rendement ET 9 des 10 pires journees de l'ecurie, souvent
100 % de la perte du jour. L'ecurie n'etait pas diversifiee : c'etait un
robot avec quatre passagers.

LA CORRECTION : on baisse le risque de BTC Cassure de 1,69 % a 1,15 % et on
redistribue a l'or et au Nasdaq, a BUDGET DE RISQUE TOTAL CONSTANT (6,01 %) :
    Or           0,75 -> 1,02 %
    Nasdaq       0,75 -> 1,02 %
    BTC Cassure  1,69 -> 1,15 %
    Petrole      1,69 %  (inchange)
    BTC EMA      1,13 %  (inchange)

POURQUOI 1,15 ET PAS AUTRE CHOSE : balayage fin de 1,69 a 0,75 %. Entre 1,69
et 1,25 la reussite est erratique (89, 92, 91, 98, 82 % = du bruit). A partir
de 1,15 et en dessous, PLATEAU NET sur cinq valeurs consecutives et sur les
DEUX fenetres : 99 % sur 10 ans, 97-98 % sur 2021-2026. 1,15 est le point du
plateau qui garde le plus de rendement.

MESURE (donnees reparees, simulateur corrige, R13) :
    L8   +28,4 %  89 %/205 j  DD -13,9 %  |  +19,1 %  84 %/228 j
    L8+  +23,1 %  99 %/238 j  DD -12,7 %  |  +16,2 %  97 %/298 j
= +10 points de reussite sur 10 ans, +13 sur le recent, journees sous -3 %
qui passent de 7 a 1. Prix : -5,3 points de rendement annuel et +33/+70 jours.

CE N'EST PAS DE LA MAGIE : c'est un desengagement du BTC. Le gain vient de ce
que BTC Cassure etait surdimensionne et que ses journees noires etaient
exactement ce qui faisait echouer les challenges.

R9 : le garde anti-spam du stop existait mais se declenchait des +1 point,
soit 1 cent sur le BTC. Remplace par un pas minimum en % du prix."""
import glob, io, os, shutil, sys

SRC = r"C:\MT6\MQL5\Experts\Jimmy L8"
DST = r"C:\MT6\MQL5\Experts\Jimmy L8+"
OK = True
def att(cond, msg):
    global OK
    if not cond: print("  !! " + msg); OK = False
    return cond

RISQUES = {"BTCUSD_Cassure": ("1.69", "1.15"), "XAUUSD_Or": ("0.75", "1.02"),
           "US100_Nasdaq":   ("0.75", "1.02")}

if os.path.isdir(DST):
    print("!! %s existe deja - rien fait" % DST); sys.exit(1)
os.makedirs(DST)

for f in sorted(glob.glob(os.path.join(SRC, "*.mq5"))):
    base = os.path.basename(f)
    nom = base.replace("_L8_", "_L8+_")
    d = os.path.join(DST, nom)
    shutil.copy(f, d)
    s = io.open(d, encoding="utf-8", errors="replace", newline="").read()
    print("--- " + nom)

    # 1. allocation
    cle = next((k for k in RISQUES if base.startswith(k)), None)
    if cle:
        vieux, neuf = RISQUES[cle]
        fait = False
        for champ in ("RisqueParTradePct    = ", "RiskPerTradePct         = "):
            anc = "input double " + champ + vieux + ";"
            if anc in s:
                att(s.count(anc) == 1, "risque en double dans " + nom)
                s = s.replace(anc, "input double " + champ + neuf + ";")
                s = s.replace("// L8 : allocation a x0,75",
                              "// L8+ : deconcentration BTC (banc : plateau sous 1,15 %)   // L8 : allocation a x0,75", 1)
                fait = True; break
        att(fait, "risque introuvable dans " + nom)

    # 2. R9 : pas minimum sur la remontee du stop
    anc = "      if(niveau > slActuel + _Point)      // le stop ne fait que monter"
    if anc in s:
        s = s.replace(anc,
            "      // L8+-R9 : le stop ne fait que monter, et seulement par pas utiles.\r\n"
            "      // L'ancienne garde etait +1 point, soit 1 cent sur le BTC : le robot\r\n"
            "      // inondait le courtier de demandes de modification pendant les rushes.\r\n"
            "      double pasMin = bid * PasMinStopPct / 100.0;\r\n"
            "      if(niveau > slActuel + pasMin)")
        i = s.find("input double RisqueParTradePct")
        if i < 0: i = s.find("input double RiskPerTradePct")
        fin = s.find("\n", i) + 1
        s = (s[:fin] + "input double PasMinStopPct        = 0.02;  "
             "// L8+-R9 : remontee minimale du stop, en % du prix (anti-spam courtier)\r\n" + s[fin:])
        print("    R9 pose.")

    # 3. empreintes
    for a, b in (('Print("L8 charge | ', 'Print("L8+ charge | '),
                 ('Print("L8 | ', 'Print("L8+ | '),
                 ('Print("L8-R13 | ', 'Print("L8+-R13 | '),
                 ('Print("L8 : ', 'Print("L8+ : '),
                 ('Notifier("L8 : ', 'Notifier("L8+ : '),
                 ('"MacroBot L8 demarre', '"MacroBot L8+ demarre')):
        s = s.replace(a, b)

    io.open(d, "w", encoding="utf-8", newline="").write(s)
    print("    ecrit.")

print()
print("TOUTES ANCRES OK" if OK else "!! DES ANCRES ONT MANQUE")
sys.exit(0 if OK else 1)
