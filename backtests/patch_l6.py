# -*- coding: utf-8 -*-
"""CONSTRUCTION DE L6 (demande Jimmy, 20 aout soir) — dossiers NEUFS,
compilee mais PAS deployee. L6 = L5 +
1. Allocation a x0,75 : Or 0,75 / Nasdaq 0,75 / Petrole 1,69 /
   Cassure 1,69 / EMA 1,13 (validee sur 2 moteurs independants).
2. FacteurRisqueGlobal (defaut 1,0) — pret pour x1,33 une fois finance.
3. Plafond facteurVol INCONDITIONNEL (plus reserve au mode challenge).
4. Peremption 7 jours des fichiers macrobot_news.txt et macrobot_bias.txt
   (comme macrobot_vol.txt) -> neutre si perime.
5. Garde de spread a l'entree : refuse (reporte) l'entree si le spread
   depasse SpreadEntreeMaxPct (2 %) de la distance de stop.
6. Petrole : alerte quotidienne si le swap long USOIL devient negatif.
7. Commentaire du garde-fou d'aberration corrige (10 % -> 50 %).
Identites [L6]/[L6SC], empreintes « L6 charge ». MEMES MAGICS que L5
(20261115/17/18) : NE JAMAIS attacher L5 et L6 en meme temps."""
import glob, io, os, shutil, sys

SRC = [(r"C:\MT6\MQL5\Experts\Jimmy L5", r"C:\MT6\MQL5\Experts\Jimmy L6"),
       (r"C:\MT6\MQL5\Experts\Jimmy L5 sans challenge", r"C:\MT6\MQL5\Experts\Jimmy L6 sans challenge")]

for src, dst in SRC:
    if not os.path.isdir(dst):
        os.makedirs(dst)
    for f in glob.glob(os.path.join(src, "*.mq5")):
        shutil.copy2(f, dst)
print("dossiers L6 crees (sources copiees, .ex5 non copies)")

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

def patch_tous(f, s, ancien, nouveau):
    global OK
    n = s.count(ancien)
    if n == 0:
        print("  !! ANCRE ABSENTE dans %s : %r..." % (f.split("\\")[-1], ancien[:60]))
        OK = False
        return s
    print("    (%dx) %s" % (n, ancien.strip()[:50]))
    return s.replace(ancien, nouveau)

CRLF = lambda t: t.replace("\n", "\r\n")

GARDE_SPREAD_STOPDIST = CRLF(
    "   double spreadCourant = SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID);   // L6\n"
    "   if(SpreadEntreeMaxPct > 0 && spreadCourant > SpreadEntreeMaxPct / 100.0 * stopDist)\n"
    "     {\n"
    "      Print(\"L6 : entree reportee, spread \", DoubleToString(spreadCourant, _Digits), \" > \", DoubleToString(SpreadEntreeMaxPct, 1), \" % de la distance de stop\");\n"
    "      return;\n"
    "     }\n")
GARDE_SPREAD_DISTSL = GARDE_SPREAD_STOPDIST.replace("stopDist", "distanceSL")

STALE_NEWS_VIDE = CRLF(
    "   long modifNews = (long)FileGetInteger(\"macrobot_news.txt\", FILE_MODIFY_DATE);   // L6\n"
    "   if(modifNews > 0 && TimeCurrent() - (datetime)modifNews > 7 * 86400)\n"
    "     { ArrayResize(newsEpochs, 0); return; }   // L6 : fichier perime -> neutre\n")
STALE_BIAS_BTC = CRLF(
    "   long modifBias = (long)FileGetInteger(\"macrobot_bias.txt\", FILE_MODIFY_DATE);   // L6\n"
    "   if(modifBias > 0 && TimeCurrent() - (datetime)modifBias > 7 * 86400)\n"
    "     { biaisMacroOK = AchatPermisSansFichier; return(biaisMacroOK); }   // L6 : perime -> neutre\n")

for f in sorted(glob.glob(r"C:\MT6\MQL5\Experts\Jimmy L6*\*.mq5")):
    s = io.open(f, encoding="utf-8", errors="replace", newline="").read()
    nom = f.split("\\")[-1]
    if "// L6 " in s or "FacteurRisqueGlobal" in s:
        print("deja fait :", nom); continue
    print("--- " + nom)

    # 0. identite L5 -> L6 (partout : [L5], L5 charge, Ecurie_L5, L5 unite...)
    s = s.replace("L5", "L6")

    # 1-2. allocation + nouveaux inputs
    if "XAUUSD_Or" in nom:
        s = patch(f, s, "input double RiskPerTradePct         = 2.0;",
                  "input double RiskPerTradePct         = 0.75;  // L6 : allocation a x0,75 (etait 2,0)")
    elif "US100_Nasdaq" in nom:
        s = patch(f, s, "input double RiskPerTradePct         = 1.5;",
                  "input double RiskPerTradePct         = 0.75;  // L6 : allocation a x0,75 (etait 1,5)")
    elif "BTCUSD_EMA" in nom:
        s = patch(f, s, "input double RisqueParTradePct    = 1.5;",
                  "input double RisqueParTradePct    = 1.13;  // L6 : allocation a x0,75 (etait 1,5)")
    else:  # Cassure + Petrole
        s = patch(f, s, "input double RisqueParTradePct    = 1.5;",
                  "input double RisqueParTradePct    = 1.69;  // L6 : allocation a x0,75 (etait 1,5)")
    nom_input = "RiskPerTradePct" if ("XAUUSD" in nom or "US100" in nom) else "RisqueParTradePct"
    idx = s.find("input double " + nom_input)
    fin = s.find("\n", idx) + 1
    s = s[:fin] + CRLF(
        "input double FacteurRisqueGlobal     = 1.0;   // L6 : multiplicateur global (mettre 1.33 une fois finance, gardien fixe -2,5)\n"
        "input double SpreadEntreeMaxPct      = 2.0;   // L6 : entree reportee si le spread depasse ce % de la distance de stop (0 = off)\n") + s[fin:]

    # 2b. multiplicateur dans le calcul du risque
    s = patch(f, s, "* facteurVol * FacteurChallenge()",
              "* facteurVol * FacteurRisqueGlobal * FacteurChallenge()")

    # 3. plafond vol inconditionnel
    s = patch_tous(f, s,
        "if(ModeChallengeActif && facteurVol > 1.0) facteurVol = 1.0;   // L4.32 : jamais amplifier en challenge",
        "if(facteurVol > 1.0) facteurVol = 1.0;   // L6 : jamais amplifier, challenge ou pas")

    # 4. peremption news/bias
    if "XAUUSD_Or" in nom or "US100_Nasdaq" in nom:
        s = patch(f, s, '   int fh = FileOpen("macrobot_bias.txt", FILE_READ | FILE_TXT | FILE_ANSI);',
            CRLF('   long modifBias = (long)FileGetInteger("macrobot_bias.txt", FILE_MODIFY_DATE);   // L6\n'
                 '   if(modifBias > 0 && TimeCurrent() - (datetime)modifBias > 7 * 86400)\n'
                 '      return MacroLongAllowed;   // L6 : fichier perime -> neutre\n')
            + '   int fh = FileOpen("macrobot_bias.txt", FILE_READ | FILE_TXT | FILE_ANSI);')
        s = patch(f, s, '   int fh = FileOpen("macrobot_news.txt", FILE_READ | FILE_TXT | FILE_ANSI);',
            CRLF('   long modifNews = (long)FileGetInteger("macrobot_news.txt", FILE_MODIFY_DATE);   // L6\n'
                 '   if(modifNews > 0 && TimeCurrent() - (datetime)modifNews > 7 * 86400)\n'
                 '      return false;   // L6 : fichier perime -> neutre (pas de blocage fantome)\n')
            + '   int fh = FileOpen("macrobot_news.txt", FILE_READ | FILE_TXT | FILE_ANSI);')
    else:
        s = patch(f, s, '   int fh = FileOpen("macrobot_news.txt", FILE_READ | FILE_TXT | FILE_ANSI);',
            STALE_NEWS_VIDE + '   int fh = FileOpen("macrobot_news.txt", FILE_READ | FILE_TXT | FILE_ANSI);')
        if "USOIL" not in nom:  # cassure + EMA ont un biais BTC; le petrole n'en a pas
            s = patch(f, s, '   int fh = FileOpen("macrobot_bias.txt", FILE_READ | FILE_TXT | FILE_ANSI);',
                STALE_BIAS_BTC + '   int fh = FileOpen("macrobot_bias.txt", FILE_READ | FILE_TXT | FILE_ANSI);')

    # 5. garde de spread a l'entree
    if "XAUUSD_Or" in nom or "US100_Nasdaq" in nom:
        s = patch(f, s,
            "void OuvrirAchat(double stopDist, string commentaire)\r\n  {\r\n   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);",
            "void OuvrirAchat(double stopDist, string commentaire)\r\n  {\r\n"
            + GARDE_SPREAD_STOPDIST
            + "   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);")
    else:
        s = patch(f, s,
            "   double lot = CalculerLot(distanceSL);\r\n   if(lot <= 0) return;",
            "   double lot = CalculerLot(distanceSL);\r\n   if(lot <= 0) return;\r\n" + GARDE_SPREAD_DISTSL)

    # 6. petrole : alerte swap negatif (1x/jour via OnTimer)
    if "USOIL" in nom:
        s = patch(f, s, "void OnTimer()\r\n  {",
            "void OnTimer()\r\n  {\r\n" + CRLF(
            "   static datetime dernierAvisSwap = 0;   // L6\n"
            "   if(TimeCurrent() - dernierAvisSwap > 86400)\n"
            "     {\n"
            "      dernierAvisSwap = TimeCurrent();\n"
            "      double swapLong = SymbolInfoDouble(_Symbol, SYMBOL_SWAP_LONG);\n"
            "      if(swapLong < 0)\n"
            "         Notifier(StringFormat(\"swap long USOIL NEGATIF (%.2f/nuit) : contango — surveiller la manche petrole\", swapLong));\n"
            "     }\n"))

    # 7. commentaire du garde-fou d'aberration (cassure + petrole)
    if "risque > 10% du prix = aberrant" in s:
        s = s.replace("risque > 10% du prix = aberrant", "risque > 50 % du prix = aberrant   // L6 : commentaire aligne sur le code")

    io.open(f, "w", encoding="utf-8", newline="").write(s)
    print("  patche.")

print("TOUTES ANCRES OK" if OK else "!! DES ANCRES ONT MANQUE — NE PAS COMPILER SANS VERIFIER")
sys.exit(0 if OK else 1)
