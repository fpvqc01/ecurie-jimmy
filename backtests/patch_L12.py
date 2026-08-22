# -*- coding: utf-8 -*-
"""L12 = L11 + le repli conditionnel de Jimmy + turbo x1,15.

1) REPLI CONDITIONNEL, sur les 2 manches qui achetent la cassure (BTC Cassure
   et Petrole). Constat de Jimmy, verifie dans le code : la manche achetait a
   la cloture des que le prix depassait le plus-haut 20 jours, donc le sommet
   de la cassure. Mais attendre un repli SYSTEMATIQUEMENT ecroule le rendement
   (+29,5 % -> +12,5 % au banc) : dans une vraie tendance le repli ne vient
   jamais. D'ou la condition :
       force = (prix de decision - EMA 50 journaliere) / ATR journalier
       force >= 1,00 -> tendance forte : on prend la cassure tout de suite
       force <  1,00 -> tendance molle : on arme une attente a
                        (prix - 1,25 x ATR), valable 5 barres de decision.
   Le stop utilise est celui memorise a l'armement, comme au banc.

2) TURBO x1,15 tant que l'equite de la phase n'a pas +4 % au-dessus de la
   baseline, puis risque normal. Porte depuis L6+, applique aux 5 robots.

MESURE (donnees reparees, simulateur FTMO exact, fermeture a +10 %)
                reussite / duree mediane / JOURS ESPERES / frais esperes
  L11   10 ans   99 % / 197 j / 199 j / 444 EUR      2021-26  97 % / 223 j / 231 j
  L12   10 ans   95 % / 180 j / 184 j / 464 EUR      2021-26  99 % / 182 j / 183 j

Le turbo SEUL sur L11 donnait 75 % et 221 jours esperes : c'est le repli qui
le rend viable. Plateau verifie de x1,15 a x1,33, falaise nette a x1,50 ;
x1,15 est le meilleur point du plateau."""
import glob, io, os, shutil, sys

SRC = r"C:\MT6\MQL5\Experts\Jimmy L11"
DST = r"C:\MT6\MQL5\Experts\Jimmy L12"
DONCH = ("BTCUSD_Cassure", "USOIL_Petrole")
OK = True


def att(cond, msg):
    global OK
    if not cond:
        print("  !! " + msg)
        OK = False
    return cond


def crlf(t):
    return t.replace("\n", "\r\n")


TURBO_IN = crlf(
    'input bool   TurboCoussinActif   = true;   // L12 : risque x TurboMultiplicateur tant que le coussin de phase n\'est pas fait\n'
    'input double TurboMultiplicateur = 1.15;   // L12 : plateau verifie 1,15-1,33 ; 1,15 est le meilleur point (falaise a 1,50)\n'
    'input double TurboCoussinPct     = 4.0;    // L12 : coussin, en % au-dessus de la baseline, qui coupe le turbo\n')

TURBO_FN = crlf("""
//+------------------------------------------------------------------+
//| L12 : turbo-coussin. Rejete dix fois quand il etait seul (il fait |
//| entrer plus gros au pire moment). Viable une fois combine au      |
//| repli conditionnel, qui corrige exactement ce defaut : 75 % de    |
//| reussite seul, 95 % avec le repli.                                |
//+------------------------------------------------------------------+
double FacteurTurbo()
  {
   if(!TurboCoussinActif) return(1.0);
   if(!GlobalVariableCheck(BaseGV())) return(1.0);
   double basePhase = GlobalVariableGet(BaseGV());
   if(basePhase <= 0) return(1.0);
   if(AccountInfoDouble(ACCOUNT_EQUITY) >= basePhase * (1.0 + TurboCoussinPct / 100.0))
      return(1.0);
   return(TurboMultiplicateur);
  }
""")

REPLI_IN = crlf(
    'input bool   ReplyActif          = true;   // L12 : ne pas acheter le sommet de la cassure quand la tendance est molle\n'
    'input double ReplyATR            = 1.25;   // L12 : profondeur du repli attendu, en ATR journalier (plateau 0,75-1,25)\n'
    'input int    ReplyFenetre        = 5;      // L12 : validite de l\'attente, en barres de decision\n'
    'input double ReplySeuilForce     = 1.00;   // L12 : (prix - EMA50) / ATR au-dela duquel on prend la cassure tout de suite\n')

REPLI_GLOB = crlf(
    'int      hEma50 = INVALID_HANDLE;   // L12 : EMA 50 journaliere, pour mesurer la force de la tendance\n'
    'bool     replArme = false;          // L12 : une attente de repli est-elle armee ?\n'
    'double   replNiveau = 0.0;          // L12 : prix vise pour l\'entree\n'
    'double   replStop = 0.0;            // L12 : stop memorise au moment de l\'armement\n'
    'int      replReste = 0;             // L12 : barres restantes avant expiration de l\'attente\n')

REPLI_FN = crlf("""
//+------------------------------------------------------------------+
//| L12 : REPLI CONDITIONNEL (idee de Jimmy, 21 aout 2026).           |
//| La manche achetait a la cloture des que le prix passait le        |
//| plus-haut 20 jours : le sommet de la cassure. Attendre un repli   |
//| a chaque fois ecroule le rendement, parce que dans une vraie      |
//| tendance le repli ne vient jamais. On n'attend donc le repli que  |
//| si la tendance est molle.                                         |
//+------------------------------------------------------------------+
double ValeurAtrJour()
  {
   if(hAtr == INVALID_HANDLE) return(0.0);
   double b[];
   if(CopyBuffer(hAtr, 0, 1, 1, b) < 1) return(0.0);
   return(b[0]);
  }

double ValeurEma50()
  {
   if(hEma50 == INVALID_HANDLE) return(0.0);
   double b[];
   if(CopyBuffer(hEma50, 0, 1, 1, b) < 1) return(0.0);
   return(b[0]);
  }

double ForceTendance(double prix, double atr)
  {
   double e = ValeurEma50();
   if(e <= 0 || atr <= 0) return(999.0);   // mesure indisponible : on ne bloque rien
   return((prix - e) / atr);
  }

void DesarmerRepli(string raison)
  {
   replArme = false; replNiveau = 0.0; replStop = 0.0; replReste = 0;
   if(raison != "") Print("L12 repli : attente annulee (", raison, ")");
  }
""")

ANCRE_CASSURE = "   if(declencheur <= hautCanal * (1.0 + TamponCassurePct / 100.0)) return;   // L4.31 tampon anti-faux-signal"

PORTE = crlf("""   // ---------- L12 : repli conditionnel ----------
   double atrJour  = ValeurAtrJour();
   double basBarre = iLow(_Symbol, UT_Decision, 1);
   bool   entreeParRepli = false;
   if(ReplyActif && replArme)
     {
      if(basBarre > 0 && basBarre <= replNiveau)
        {
         Print("L12 repli : touche a ", DoubleToString(replNiveau, _Digits), ", on entre");
         basCanal = replStop;              // stop memorise a l'armement, comme au banc
         entreeParRepli = true;
         DesarmerRepli("");
        }
      else
        {
         replReste--;
         if(replReste <= 0) DesarmerRepli("fenetre expiree, cassure laissee passer");
         return;                            // on attend encore
        }
     }
   if(!entreeParRepli)
     {
""") + ANCRE_CASSURE + crlf("""
      double force = ForceTendance(declencheur, atrJour);
      if(ReplyActif && atrJour > 0 && force < ReplySeuilForce)
        {
         replArme   = true;
         replNiveau = declencheur - ReplyATR * atrJour;
         replStop   = basCanal;
         replReste  = ReplyFenetre;
         Print("L12 repli : tendance molle (force ", DoubleToString(force, 2), " < ",
               DoubleToString(ReplySeuilForce, 2), "), on attend ",
               DoubleToString(replNiveau, _Digits), " pendant ", ReplyFenetre, " barres");
         return;                            // on n'achete PAS le sommet
        }
     }
""")

if os.path.isdir(DST):
    print("!! %s existe deja - rien fait" % DST)
    sys.exit(1)
os.makedirs(DST)

for f in sorted(glob.glob(os.path.join(SRC, "*.mq5"))):
    base = os.path.basename(f)
    nom = base.replace("_L11_", "_L12_")
    d = os.path.join(DST, nom)
    shutil.copy(f, d)
    s = io.open(d, encoding="utf-8", errors="replace", newline="").read()
    donch = base.startswith(DONCH)
    print("--- " + nom)

    # 1. inputs
    a = "input double FacteurRisqueGlobal     = 1.0;"
    if att(s.count(a) == 1, "ancre inputs"):
        fin = s.find("\n", s.find(a)) + 1
        s = s[:fin] + TURBO_IN + (REPLI_IN if donch else "") + s[fin:]

    # 2. globals + fonctions
    # on insere APRES LastEqGV : BaseGV et HaltGV sont alors deja definis,
    # ce dont FacteurTurbo() a besoin. Cette ligne est identique dans les 5
    # robots, contrairement a HaltGV dont l'espacement varie.
    a = "string LastEqGV()"
    if att(s.count(a) == 1, "ancre fonctions"):
        fin = s.find("\n", s.find(a)) + 1
        s = s[:fin] + (REPLI_GLOB if donch else "") + TURBO_FN + (REPLI_FN if donch else "") + s[fin:]

    # 3. le turbo entre dans le calcul du risque
    a = "* facteurVol * FacteurRisqueGlobal * FacteurChallenge();"
    if att(s.count(a) == 1, "ancre risque"):
        s = s.replace(a, "* facteurVol * FacteurRisqueGlobal * FacteurTurbo() * FacteurChallenge();   // L12")

    if donch:
        # 4. handle EMA50 : creation et liberation
        a = "   hAtr = iATR(_Symbol, PERIOD_D1, PeriodeATR);"
        if att(s.count(a) == 1, "ancre creation hAtr"):
            s = s.replace(a, a + crlf("\n   hEma50 = iMA(_Symbol, PERIOD_D1, 50, 0, MODE_EMA, PRICE_CLOSE);   // L12"))
        a = "   if(hAtr != INVALID_HANDLE) IndicatorRelease(hAtr);"
        if att(s.count(a) == 1, "ancre liberation hAtr"):
            s = s.replace(a, a + crlf("\n   if(hEma50 != INVALID_HANDLE) IndicatorRelease(hEma50);   // L12"))

        # 5. la porte du repli
        if att(s.count(ANCRE_CASSURE) == 1, "ancre cassure"):
            s = s.replace(ANCRE_CASSURE, PORTE)

    # 6. empreintes de journal
    for x, y in (('Print("L11 charge | ', 'Print("L12 charge | '),
                 ('Print("L11 | ', 'Print("L12 | '),
                 ('Print("L11-R13 | ', 'Print("L12-R13 | '),
                 ('Print("L11 : ', 'Print("L12 : '),
                 ('Notifier("L11 : ', 'Notifier("L12 : '),
                 ('"MacroBot L11 demarre', '"MacroBot L12 demarre')):
        s = s.replace(x, y)

    io.open(d, "w", encoding="utf-8", newline="").write(s)
    print("    ecrit  (%s)" % ("repli + turbo" if donch else "turbo seul"))

print()
print("TOUTES ANCRES OK" if OK else "!! DES ANCRES ONT MANQUE")
sys.exit(0 if OK else 1)
