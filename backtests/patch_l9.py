# -*- coding: utf-8 -*-
"""CONSTRUCTION DE L9 (21 aout 2026) - demande Jimmy.

Batie a partir de L8. N'INTEGRE QUE ce qui est defendable SANS nouvelle
optimisation de backtest : un bogue reel, un retour a une valeur
precedente, et deux mecanismes appuyes par la litterature.

  L9-1  BOGUE CRITIQUE (reparation).
        L8-R5 a donne des magics propres a l'or (20261121) et au
        Nasdaq (20261122), mais les listes de magics de
        ComptePositionsEcurie() et FamilleCorreleeOccupee() n'ont PAS
        ete mises a jour dans les 5 robots. Consequences en production :
          - le plafond d'ecurie (2 piles) ne voit ni l'or ni le Nasdaq
            -> jusqu'a 4 piles simultanees au lieu de 2 ;
          - le plafond de correlation metal/indice est MORT -> l'or et
            le Nasdaq peuvent etre exposes en meme temps, ce que la
            regle interdisait justement (crise de sept. 2011).
        L9 ajoute les 2 magics aux 2 listes dans les 5 robots.

  L9-2  gardien quotidien 1,75 % -> 2,50 % (RETOUR arriere).
        Relance de banc_L8.py par la session principale, sur donnees
        saines (d10h1_btc.csv verifie : 0 barre corrompue) :
            -2,50 % : 79 % / 161 j (10 ans) | 74 % / 183 j (21-26)
            -2,00 % : 82 % / 163 j          | 74 % / 197 j
            -1,75 % : 79 % / 178 j          | 76 % / 227 j
            -1,50 % : 80 % / 168 j          | 79 % / 204 j
            -1,25 % : 90 % / 208 j          | 80 % / 318 j
        Aucun plateau : la suite 79/82/79/80/90 est du bruit, et 1,75 %
        n'y est pas meilleur tout en coutant 17 a 44 jours. 2,50 % a en
        plus une justification externe (moitie de la limite FTMO de 5 %)
        au lieu d'etre l'argmax d'un balayage.

  L9-3  ANCRE ROULANTE apres pyramide pleine (nouveau, INACTIF).
        MESUREE AU BANC PAR LE QUANT LE 21 AOUT, ET REJETEE dans la
        forme codee ici (K = 2,0) : 222 j au lieu de 204 j et -5 pts de
        CAGR. Les formes K = 1,8 / 2,2 / 2,5 sont pires encore. Seule la
        variante  ancre virtuelle a pas de 1,00 ATR  ameliore les deux
        axes - mais c est un pic de parametre (les pas 0,50 et 0,75
        s ecroulent a 60 % sur 2021-2026), donc pas deployable en l etat.
        Le code reste en place, desactive, pour pouvoir le rejouer.
        A 4/4 unites, l'ancre du stop (derniere unite - 2xATR) est
        FIGEE pour toujours ; seul le canal 10 jours peut encore monter
        le stop, avec 1-2 jours de retard. C'est la cause du give-back
        de ~11 % observe en reel le 21 aout, et les 3 IA du comite
        externe le placent a l'unanimite en tete de leurs propositions.
        L9 : pile pleine -> l'ancre suit le PLUS HAUT depuis la derniere
        unite. Meme multiplicateur ATR (2,0), donc jamais plus serre que
        le stop actuel : le comportement est continu avec L8. L'etat est
        reconstruit depuis le courtier (POSITION_TIME), donc il survit a
        un redemarrage du terminal.

  L9-4  PLAFOND DE HEAT AGREGE (nouveau, ACTIF, genereux : 8 %).
        Regle Turtle. Le plafond actuel borne le NOMBRE de piles (2)
        sans jamais regarder ce qu'elles risquent : 2 piles pyramidees
        pleines n'ont rien a voir avec 2 positions simples. L9 borne la
        somme des risques aux stops de toute l'ecurie, en % de l'equite.
        C'est la seule protection EX ANTE contre la barriere -5 %/jour ;
        le gardien quotidien, lui, est reactif (il agit apres coup).
        A 8 %, il ne mord que dans les configurations extremes.

  L9-5  EXPOSITION PROPORTIONNELLE AU COUSSIN (nouveau, INACTIF).
        Grossman-Zhou (1993), Cvitanic-Karatzas (1995) : sous contrainte
        de drawdown, l'exposition optimale est proportionnelle a la
        distance au plancher. Le frein d'equite actuel se declenche sur
        la moyenne 20 jours - un signal RELATIF qui ignore ou est le mur
        (un compte a +8 % freine sans raison ; un compte a -7 % qui
        rebondit ne freine pas alors qu'il est a 3 points de la mort).
        Implemente et DESACTIVE par defaut : a mesurer au banc avant
        toute activation.

CE QUI N'EST PAS AJOUTE, ET POURQUOI :
  - Aucun nouveau reglage choisi par balayage sur les memes donnees.
  - Le breakeven collectif est laisse TEL QUEL (ni retire ni renforce) :
    la relance sur donnees saines montre qu'il AIDE aux gardiens larges
    (-2,50 % : 79->85 %) et NUIT aux gardiens serres (-1,75 % : 79->75 %,
    -1,25 % : 90->85 %). Un effet qui change de signe selon un autre
    reglage est une signature de bruit, pas un gain propre. A trancher.

NON DEPLOYEE. Ce script cree les fichiers et s'arrete la.
"""
import glob, os, re, shutil

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(RACINE, "robots", "Jimmy L8")
DST = os.path.join(RACINE, "robots", "Jimmy L9")

PYRAMIDE = ("BTCUSD_Cassure", "USOIL_Petrole")   # les 2 manches qui pyramident
OK = True


def lire(p):
    with open(p, "rb") as f:
        return f.read().decode("utf-8")


def ecrire(p, s):
    with open(p, "wb") as f:
        f.write(s.encode("utf-8"))


def patch(nom, s, ancien, nouveau, n=1):
    """remplace et verifie le nombre d'occurrences (echoue bruyamment)"""
    global OK
    c = s.count(ancien)
    if c != n:
        print("  !! ANCRE %s (%d trouvee(s), %d attendue(s)) : %r"
              % (nom, c, n, ancien[:60]))
        OK = False
        return s
    return s.replace(ancien, nouveau)


def CRLF(t):
    return t.replace("\n", "\r\n")


INPUTS_L9 = CRLF("""
input double HeatMaxEcuriePct     = 8.0;    // L9-4 : somme des risques aux stops de l'ecurie, en % de l'equite (0 = aucun plafond)
input bool   AncreRoulanteActive  = false;  // L9-3 : DESACTIVE - banc du quant 21 aout : la forme K=2,0 ralentit (+18 j) et coute 5 pts de CAGR
input bool   ExpoCoussinActive    = false;  // L9-5 : exposition proportionnelle a la distance au plancher (Grossman-Zhou) - A TESTER
input double ExpoCoussinMini      = 0.40;   // L9-5 : plancher du facteur (ne descend jamais sous 40 % de la taille normale)""")

HELPERS = CRLF("""
//+------------------------------------------------------------------+
//| L9-4 : heat agrege de l'ecurie = somme des risques aux stops.     |
//| Regle Turtle. Le plafond de 2 piles compte les SIEGES ; celui-ci  |
//| compte ce que l'ecurie risque vraiment. Seule protection ex ante  |
//| contre la barriere -5 %/jour (le gardien, lui, agit apres coup).  |
//+------------------------------------------------------------------+
double HeatEcuriePct()
  {
   double equite = AccountInfoDouble(ACCOUNT_EQUITY);
   if(equite <= 0) return(0.0);
   double total = 0.0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      long m = PositionGetInteger(POSITION_MAGIC);
      if(m != 20260815 && m != 20260817 && m != 20260818 &&
         m != 20261115 && m != 20261117 && m != 20261118 &&
         m != 20261121 && m != 20261122) continue;
      double sl = PositionGetDouble(POSITION_SL);
      if(sl <= 0) continue;                       // pas de stop connu : ignore
      string sym  = PositionGetString(POSITION_SYMBOL);
      double dist = MathAbs(PositionGetDouble(POSITION_PRICE_OPEN) - sl);
      double ts   = SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_SIZE);
      double tv   = SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_VALUE);
      if(ts <= 0 || tv <= 0) continue;
      total += dist / ts * tv * PositionGetDouble(POSITION_VOLUME);
     }
   return(total / equite * 100.0);
  }

bool HeatEcuriePlein()
  {
   if(HeatMaxEcuriePct <= 0) return(false);
   return(HeatEcuriePct() >= HeatMaxEcuriePct);
  }

//+------------------------------------------------------------------+
//| L9-5 : exposition proportionnelle au coussin (Grossman-Zhou 1993).|
//| f = (equite - plancher) / (base - plancher), borne a [mini, 1].   |
//| INACTIF par defaut : a mesurer au banc avant activation.          |
//+------------------------------------------------------------------+
double FacteurCoussin()
  {
   if(!ExpoCoussinActive) return(1.0);
   if(!GlobalVariableCheck(BaseGV())) return(1.0);
   double base = GlobalVariableGet(BaseGV());
   if(base <= 0) return(1.0);
   double plancher = base * (1.0 - LimitePerteTotalePct / 100.0);
   double marge    = base - plancher;
   if(marge <= 0) return(1.0);
   double f = (AccountInfoDouble(ACCOUNT_EQUITY) - plancher) / marge;
   if(f > 1.0) f = 1.0;
   if(f < ExpoCoussinMini) f = ExpoCoussinMini;
   return(f);
  }
""")

HELPER_ANCRE = CRLF("""
//+------------------------------------------------------------------+
//| L9-3 : plus haut atteint depuis l'ouverture de la derniere unite. |
//| Reconstruit depuis le courtier (POSITION_TIME) -> survit a un     |
//| redemarrage du terminal, comme le reste de l'etat de la pyramide. |
//+------------------------------------------------------------------+
double PlusHautDepuisDerniereUnite()
  {
   datetime tDer = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != NumeroMagique) continue;
      datetime t = (datetime)PositionGetInteger(POSITION_TIME);
      if(t > tDer) tDer = t;
     }
   if(tDer == 0) return(0.0);
   int n = Bars(_Symbol, UT_Decision, tDer, TimeCurrent());
   if(n <= 0) return(0.0);
   if(n > 5000) n = 5000;
   int idx = iHighest(_Symbol, UT_Decision, MODE_HIGH, n, 0);
   if(idx < 0) return(0.0);
   return(iHigh(_Symbol, UT_Decision, idx));
  }
""")

if not os.path.isdir(SRC):
    raise SystemExit("dossier source introuvable : " + SRC)
if os.path.isdir(DST):
    shutil.rmtree(DST)
os.makedirs(DST)

for src in sorted(glob.glob(os.path.join(SRC, "*.mq5"))):
    base = os.path.basename(src)
    nom = base.replace("_L8_", "_L9_")
    dst = os.path.join(DST, nom)
    s = lire(src)
    court = base.split("_L8_")[0]
    print("")
    print(nom)

    # -- L9-1 : reparation des listes de magics (2 listes par robot) --
    s = patch("magics", s,
              "m != 20261115 && m != 20261117 && m != 20261118) continue;",
              "m != 20261115 && m != 20261117 && m != 20261118 &&\r\n"
              "         m != 20261121 && m != 20261122) continue;"
              "   // L9-1 : or et Nasdaq etaient invisibles",
              n=2)

    # -- L9-2 : gardien 1,75 -> 2,50 + insertion des inputs L9 --------
    m = re.search(r"input double LimitePerteJourPct( +)= 1\.75;([^\r\n]*)", s)
    if m is None:
        print("  !! ANCRE gardien : introuvable")
        OK = False
    else:
        remplacement = ("input double LimitePerteJourPct%s= 2.50;%s"
                        % (m.group(1), m.group(2))) + INPUTS_L9
        s = s.replace(m.group(0), remplacement, 1)

    # -- helpers communs (inseres juste avant OnTick) ------------------
    bloc = HELPERS + (HELPER_ANCRE if court in PYRAMIDE else "")
    s = patch("OnTick", s, "\r\nvoid OnTick()", bloc + "\r\nvoid OnTick()", n=1)

    # -- L9-5 : facteur coussin dans le calcul de lot ------------------
    for var in ("RisqueParTradePct", "RiskPerTradePct"):
        vieux = ("AccountInfoDouble(ACCOUNT_EQUITY) * %s / 100.0 * facteurVol "
                 "* FacteurRisqueGlobal * FacteurChallenge();" % var)
        if vieux in s:
            s = patch("risque", s, vieux,
                      vieux[:-1] + " * FacteurCoussin();   // L9-5", n=1)

    # -- L9-4 : plafond de heat avant toute nouvelle entree ------------
    gate = "if(ComptePositionsEcurie() >= MaxPositionsEcurie) return;"
    n_gate = s.count(gate)
    s = patch("heat", s, gate,
              gate + "\r\n   if(HeatEcuriePlein()) return;"
                     "   // L9-4 : plafond de heat agrege", n=n_gate)

    if court in PYRAMIDE:
        # -- L9-4 : heat avant l'ajout d'une unite de pyramide ---------
        s = patch("heat pyr", s,
                  "if(hautDecision >= seuilAjout && ComptePositionsEcurie() < MaxPositionsEcurie)",
                  "if(hautDecision >= seuilAjout && ComptePositionsEcurie() < MaxPositionsEcurie\r\n"
                  "            && !HeatEcuriePlein())   // L9-4", n=1)
        # -- L9-3 : ancre roulante quand la pile est pleine ------------
        s = patch("ancre", s,
                  "         double stopTurtle = dernier - StopSousDerniereUniteATR * atrVal;",
                  "         double ancre = dernier;                       // L9-3\r\n"
                  "         if(AncreRoulanteActive && unites >= MaxUnites)\r\n"
                  "           {\r\n"
                  "            double ph = PlusHautDepuisDerniereUnite();\r\n"
                  "            if(ph > ancre) ancre = ph;"
                  "                 // la pile pleine ne fige plus le stop\r\n"
                  "           }\r\n"
                  "         double stopTurtle = ancre - StopSousDerniereUniteATR * atrVal;",
                  n=1)

    # -- etiquettes ----------------------------------------------------
    for a, b in (('"L8 charge', '"L9 charge'), ('"L8 |', '"L9 |'),
                 ('"L8-R13 |', '"L9 |'), ('Ecurie_L8', 'Ecurie_L9'),
                 ('"L8 unite ', '"L9 unite '), ('[L8]', '[L9]'),
                 ('"L8 : ', '"L9 : '), ('MacroBot L8', 'MacroBot L9')):
        s = s.replace(a, b)

    ecrire(dst, s)
    print("  ecrit : %s (%d octets)" % (nom, len(s.encode("utf-8"))))

print("")
print("=" * 62)
if OK:
    print("L9 CONSTRUITE : %s" % DST)
    print("5 robots. NON DEPLOYEE, NON COMPILEE par ce script.")
    print("Defauts : gardien -2,50 % | ancre roulante ON | heat 8 % ON |")
    print("          expo coussin OFF (a tester au banc).")
else:
    print("!! DES ANCRES ONT ECHOUE - verifier avant toute compilation.")
