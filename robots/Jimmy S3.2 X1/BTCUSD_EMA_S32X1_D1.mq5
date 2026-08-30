//+------------------------------------------------------------------+
//| GENERATION S3.2 (23 aout 2026) = S3 avec le CPPI a la place du    |
//| turbo-coussin, plafond porte a 1,60.                              |
//|  Banc avant/apres, objectif au SOLDE FERME (vraie regle FTMO) :   |
//|    S3 (turbo)  : 92,4 % / 256 j (10 ans) | 85,6 % / 384 j (21-26) |
//|    S3.1 (CPPI) :  100 % / 180 j          |  100 % / 290 j         |
//|  Le turbo ne payait pas la vitesse qu il pretendait acheter : ses  |
//|  echecs coutent du temps. Plateau du plafond CPPI 1,50-1,75.      |
//|  RESTENT A FAIRE (S3.2, aucun n accelere) : FermerPositions ne    |
//|  ferme qu un cinquieme du compte ; pas de plafond de notionnel sur |
//|  Nasdaq/Or/BTC EMA ; ChallengeInitialBalance a fixer ; saison      |
//|  petrole au signe inverse cote vente. Magics 20266041-45.         |
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| GENERATION S3 (remplacee par S3.1) = S2 + TURBO-COUSSIN x1.33 / +6 %    |
//|  CPPI eteint par defaut (CppiActif=false) ; R13 et mode challenge  |
//|  actifs. Combinaison la plus rapide du banc VAD v2 : esperance     |
//|  175 j (10 ans) / 205 j (2021-26), reussite 92,5 % / 90,8 %.       |
//|  Borne optimiste (turbo applique apres coup au banc). Compte        |
//|  FINANCE : remettre CppiActif=true. Magics 20266041-45.            |
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//|                                              BTCUSD_EMA_L43_D1.mq5 |
//|  Base I2 du bot EMA BTC, portee en L4.3 le 20 aout 2026 :        |
//|   - TP à +2R (~1000 $) au lieu de 1.5R                           |
//|   - RÉ-ENTRÉE sur repli de 0.25xATR après un TP, tant que les    |
//|     EMA restent haussières et la macro favorable                 |
//|   - risque 1.5 % (parite L4) ; decision et EMA/ATR JOURNALIERS   |
//|   - PLAFOND d'écurie : max 2 positions simultanées (tous robots) |
//|  Magic L4.3 (20261115) : ecurie independante des autres.         |
//+------------------------------------------------------------------+
#property copyright "Jimmy"
#property version   "2.00"
#property strict

#include <Trade\Trade.mqh>

input double RisqueParTradePct    = 1.13;  // L8 : allocation a x0,75 (etait 1,5)   // parite de risque validee 10 ans (etait 0.75)   // Risque par trade en % du solde (I2 : x1.5)
input double PlafondNotionnelEquite = 0.50;   // S3.2-F2 : notionnel max, en multiple de l equite (0 = aucun) - seule protection contre les gaps
input double FacteurRisqueGlobal     = 1.0;   // L8 : multiplicateur global (mettre 1.33 une fois finance, gardien fixe -2,5)
input bool   CppiActif       = false;  // S3.1 : RALLUME — le turbo etait plus lent une fois l objectif exige au solde ferme (256 j contre 198 j)   // X1 : meilleurs facteurs du laboratoire
input double CppiMax         = 1.60;   // S3.1 : 1,33 -> 1,60, plateau mesure 1,50-1,75 (falaise a 1,75+ sur 10 ans) ; predit par la theorie avant mesure
input double CppiPlancherPct = 10.0;   // S1 : plancher FTMO qui definit le coussin
input double CppiMin         = 0.30;   // S1 : facteur minimal pres du plancher
input bool   TurboCoussinActif   = true;   // S3.1 : ETEINT — il grossissait la mise DANS la zone de mort (banc du 22 aout : 74 challenges morts contre 0 pour le CPPI)   // X1 : meilleurs facteurs du laboratoire
input double TurboMultiplicateur = 1.15;   // S3 : banc VAD v2 du 23 aout 2026 — esperance 175 j / 205 j, reussite 92,5 % / 90,8 % (BORNE OPTIMISTE)   // X1 : meilleurs facteurs du laboratoire
input double TurboCoussinPct     = 6.0;    // S3 : coussin de phase, en %, qui coupe le turbo   // X1 : meilleurs facteurs du laboratoire
input double SpreadEntreeMaxPct      = 2.0;   // L8 : entree reportee si le spread depasse ce % de la distance de stop (0 = off)
input ENUM_TIMEFRAMES UT_Decision    = PERIOD_D1; // L4.3 : une decision par jour (valide walk-forward)
input ENUM_TIMEFRAMES UT_Indicateurs = PERIOD_D1; // L4.3 : EMA/ATR journaliers
input int             HeureDecision  = 8;         // L8F : heure serveur de la decision D1 (evite le spread du rollover de minuit)
input double LimitePerteJourPct   = 1.25;  // L11 : rendu a 2,50 % - la deconcentration du BTC a traite la cause (banc L11 : -41 a -75 jours, reussite inchangee)    // L3 : resserre (valide 19 aout ; FTMO = 5)   // D : reglage du laboratoire   // X1 : meilleurs facteurs du laboratoire
input double LimitePerteTotalePct = 9.5;    // Coupe-circuit perte totale en %
input double ChallengeInitialBalance = 0;   // L8-R10 : capital initial de la phase (0 = solde au chargement)
enum PhaseChallengeFTMO
  {
   PHASE_1        = 1,   // Phase 1 : objectif +10 %
   PHASE_2        = 2,   // Phase 2 : objectif +5 %
   COMPTE_FINANCE = 0    // Compte finance : aucune fermeture automatique
  };
input PhaseChallengeFTMO PhaseActuelle = PHASE_1;   // R13 : la phase en cours. Le robot en deduit son objectif.
input double ObjectifPhase1Pct  = 10.0;  // R13 : objectif de la phase 1, en % du capital de depart
input double ObjectifPhase2Pct  = 5.0;   // R13 : objectif de la phase 2, en % du capital de depart

//+------------------------------------------------------------------+
//| R13 : l objectif depend de la phase. Avant, un seul pourcentage   |
//| qu il fallait changer a la main entre les deux phases - oublier   |
//| de le faire, c etait viser +10 % alors que +5 % suffisait.        |
//|                                                                   |
//| RESTAURE LE 24 AOUT 2026 : S3.2 avait perdu cette fonction au     |
//| profit d un input fige a 10 %, ecrit par remplacer_input() de     |
//| generer_D.py. Un objectif fige fait viser +10 % en phase 2 la ou  |
//| +5 % suffit, et ferme tout a +10 % sur un compte finance alors    |
//| qu il ne doit jamais fermer tout seul. C etait EXACTEMENT le      |
//| defaut que cette fonction avait ete ecrite pour empecher.         |
//+------------------------------------------------------------------+
double ObjectifPhasePctCourant()
  {
   if(PhaseActuelle == PHASE_1) return(ObjectifPhase1Pct);
   if(PhaseActuelle == PHASE_2) return(ObjectifPhase2Pct);
   return(0.0);   // compte finance : on ne ferme pas tout seul
  }
input double MargeObjectifPct   = 0.25;  // L8-R13 : coussin encaisse au-dessus de l'objectif (spread/commission)
input int    EMARapide            = 20;
input int    EMALente             = 50;
input int    PeriodeATR           = 14;
input double MultiplicateurSL     = 2.0;    // Stop = 2 x ATR (= 1R)
input double MultiplicateurTP     = 4.0;    // TP = 4 x ATR (= 2R, ~1000 $) (I2)
input double RetraceReentreeATR   = 0.25;   // Ré-entrée après repli de N x ATR sous le prix de sortie TP (I2)
input int    MaxPositionsEcurie   = 2;      // Plafond global de positions de l'écurie (I2)
input long   NumeroMagique        = 20266042;
input bool   ModeAchatSeulement   = true;
input bool   BiaisMacroDepuisFichier = true;
input bool   AchatPermisSansFichier  = true;
input bool   FiltreNouvellesActif    = true;
input int    MinutesBlocageAvantNews = 30;
input int    MinutesBlocageApresNews = 30;

enum ENUM_PROTECTION_NEWS
  {
   PROTECTION_AUCUNE = 0,
   PROTECTION_SERRER = 1,
   PROTECTION_FERMER = 2
  };
input ENUM_PROTECTION_NEWS ProtectionPositionsNews = PROTECTION_SERRER;
input bool   FacteurVolActif       = true; // moduler le risque selon la volatilite des marches (L3)
input bool   JournalActif          = true; // journal de reflexion (Files\Ecurie_Journal)
input bool   PlafondCorrelationActif = true;  // un seul metal/indice a la fois (crises)
input bool   ModeChallengeActif = true;  // L4 : ACTIF par defaut (valide scan 21 aout, 2 moteurs)
input double ThrottleChallenge  = 0.75;  // L3+ : facteur sous la moyenne 20 j
input bool   NotificationsPush       = true;

CTrade   trade;
int      hEmaRapide = INVALID_HANDLE;
int      hEmaLente  = INVALID_HANDLE;
int      hAtr       = INVALID_HANDLE;
datetime derniereBarre = 0;
datetime derniereLectureBiais = 0;
bool     biaisMacroOK = true;
datetime derniereLectureNews = 0;
long     newsEpochs[];
int      fngValeur = -1;
bool     newsBloquaitAvant = false;
datetime derniereLectureVol = 0;
double   facteurVol = 1.0;
bool     volLectureEchouee = false;   // L13

double   attenteReentree = 0;   // prix de sortie TP ; 0 = pas de ré-entrée en attente

string BaseGV() { return "MACROBOT_BASE_" + (string)AccountInfoInteger(ACCOUNT_LOGIN); }
string HaltGV() { return "MACROBOT_HALT_" + (string)AccountInfoInteger(ACCOUNT_LOGIN); }
string LastEqGV() { return "MACROBOT_LASTEQ_" + (string)AccountInfoInteger(ACCOUNT_LOGIN); }   // L4.32 : equite d'avant le gap

//+------------------------------------------------------------------+
//| L12 : turbo-coussin. Rejete dix fois quand il etait seul (il fait |
//| entrer plus gros au pire moment). Viable une fois combine au      |
//| repli conditionnel, qui corrige exactement ce defaut : 75 % de    |
//| reussite seul, 95 % avec le repli.                                |
//+------------------------------------------------------------------+
double FacteurTurbo()
  {
   // S1 : CPPI (Grossman & Zhou 1993). L'exposition est PROPORTIONNELLE au
   // coussin au-dessus du plancher FTMO, bornee [CppiMin, CppiMax].
   //
   // L'ancien turbo faisait l'INVERSE : risquer 1,33x tant que le coussin
   // n'etait pas fait — c'est-a-dire dans la zone de mort (-10 % a +6 %).
   // Banc du 22 aout 2026 (generation-S/banc_cppi.py, vrai moteur, donnees
   // figees) : turbo = 74 challenges morts sur 10 ans, CPPI = 0, et la
   // survie du compte finance a 2 ans passe de 95,8 % a 100 %.
   //
   // Limite assumee : le facteur ne s'applique qu'a l'OUVERTURE — les
   // positions deja ouvertes gardent leur taille. Le banc rescale chaque
   // jour, donc ses chiffres sont une borne optimiste de l'effet reel.
   if(!CppiActif)
     {
      // S3 : turbo-coussin classique (L6+/L12) quand le CPPI est eteint.
      // Mesure du 23 aout 2026 (banc VAD v2, S2 = achat + vente cond.) :
      // sans turbo 100 % / 237 j (10 ans) ; avec turbo 92,5 % / 156 j med,
      // 175 j esperes. On achete de la vitesse avec un peu de survie.
      // BORNE OPTIMISTE : le banc applique le facteur apres coup ; ici il ne
      // joue qu'a l'OUVERTURE. Si CppiActif=true, le CPPI ci-dessous gagne.
      if(!TurboCoussinActif) return(1.0);
      if(!GlobalVariableCheck(BaseGV())) return(1.0);
      double baseTurbo = GlobalVariableGet(BaseGV());
      if(baseTurbo <= 0) return(1.0);
      if(AccountInfoDouble(ACCOUNT_EQUITY) >= baseTurbo * (1.0 + TurboCoussinPct / 100.0))
         return(1.0);
      return(TurboMultiplicateur);
     }
   if(!GlobalVariableCheck(BaseGV())) return(1.0);
   double basePhase = GlobalVariableGet(BaseGV());
   if(basePhase <= 0) return(1.0);
   double plancher = 1.0 - CppiPlancherPct / 100.0;
   double m = (AccountInfoDouble(ACCOUNT_EQUITY) / basePhase - plancher)
              / (CppiPlancherPct / 100.0);
   if(m < CppiMin) m = CppiMin;
   if(m > CppiMax) m = CppiMax;
   return(m);
  }
string DayGV()
  {
   MqlDateTime now;
   TimeToStruct(TimeCurrent(), now);
   return StringFormat("MACROBOT_DAY_%04d%02d%02d_%s",
                       now.year, now.mon, now.day,
                       (string)AccountInfoInteger(ACCOUNT_LOGIN));
  }

//+------------------------------------------------------------------+
//| Plafond d'écurie : compte les positions de TOUS nos robots       |
//| (magics 20261115 EMA+MacroBots, 20261117 BTC brk, 20261118 oil)  |
//+------------------------------------------------------------------+

//+------------------------------------------------------------------+
//| L3 : test de position robuste (PositionSelect n'est pas fiable    |
//| sur un compte hedging) -> boucle explicite symbole + magic.       |
//+------------------------------------------------------------------+
bool PositionOuverte()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != NumeroMagique) continue;
      return(true);
     }
   return(false);
  }

//+------------------------------------------------------------------+
//| PLAFOND DE CORRELATION (valide sur 99 ans de crises)              |
//| L'or et les indices semblent independants... jusqu'a une crise de |
//| liquidite qui les fait chuter ENSEMBLE (septembre 2011 : l'or de  |
//| 1920 a 1530 pendant que les indices plongeaient). Un seul robot   |
//| de la famille metal/indice peut donc etre en position a la fois.  |
//| Test : 2011 passe de -8,0 % (compte mort) a -2,2 % ; crises       |
//| positives 5/7 -> 6/7 ; cout 1,1 point de rendement annuel.        |
//+------------------------------------------------------------------+
bool EstMetalOuIndice(string symbole)
  {
   string s = symbole;
   StringToUpper(s);
   if(StringFind(s, "XAU") >= 0) return(true);   // or
   if(StringFind(s, "XAG") >= 0) return(true);   // argent
   if(StringFind(s, "US100") >= 0) return(true); // Nasdaq
   if(StringFind(s, "NAS") >= 0) return(true);
   if(StringFind(s, "US30") >= 0) return(true);
   if(StringFind(s, "US500") >= 0) return(true);
   if(StringFind(s, "SPX") >= 0) return(true);
   if(StringFind(s, "GER") >= 0 || StringFind(s, "DE30") >= 0) return(true);
   return(false);
  }

//| true si une AUTRE position metal/indice de l'ecurie est ouverte
bool FamilleCorreleeOccupee()
  {
   if(!PlafondCorrelationActif) return(false);
   if(!EstMetalOuIndice(_Symbol)) return(false);   // ne concerne pas BTC/petrole
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      long m = PositionGetInteger(POSITION_MAGIC);
      if(m != 20266041 && m != 20266042 && m != 20266043 && m != 20266044 && m != 20266045) continue;
      string sym = PositionGetString(POSITION_SYMBOL);
      if(sym == _Symbol) continue;                 // c'est nous
      if(EstMetalOuIndice(sym)) return(true);      // un cousin est deja expose
     }
   return(false);
  }

int ComptePositionsEcurie()
  {
   // L3 : on compte les PILES, pas les positions. Un robot qui pyramide
   // (3 unites sur le meme marche) occupe UN seul siege de l'ecurie.
   string vues = "";
   int n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      long m = PositionGetInteger(POSITION_MAGIC);
      if(m != 20266041 && m != 20266042 && m != 20266043 && m != 20266044 && m != 20266045) continue;
      string cle = "|" + (string)m + ":" + PositionGetString(POSITION_SYMBOL) + "|";
      if(StringFind(vues, cle) >= 0) continue;
      vues += cle;
      n++;
     }
   return(n);
  }

//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| IDENTITE DU ROBOT DANS LES NOTIFICATIONS  (23 aout 2026)         |
//|                                                                  |
//| Avant : [L8] XAUUSD : ENTREE achat 0.15 lot @ 3421.50            |
//|   -> etiquette de generation perimee, aucun nom de robot,        |
//|      aucun terminal. Avec quatre terminaux ouverts en meme       |
//|      temps et une vingtaine de robots qui ecrivent sur le        |
//|      meme telephone, un message pareil ne veut rien dire.        |
//|                                                                  |
//| Apres : XAUUSD_Or_S32_H4 sur MT7 a ACHETE 0.15 lot a 3421.50     |
//|                                                                  |
//| Le nom vient de MQLInfoString(MQL_PROGRAM_NAME) : c'est le nom   |
//| reel du robot, il ne peut pas se perimer. Le poste est deduit    |
//| du chemin du terminal, donc rien a regler nulle part.            |
//+------------------------------------------------------------------+
string NomDuPoste()
  {
   static string cache = "";
   if(cache != "") return(cache);
   string chemin = TerminalInfoString(TERMINAL_PATH);
   if(StringFind(chemin, "NouveauMT5") >= 0)  cache = "MT7";
   else if(StringFind(chemin, "MT8") >= 0)    cache = "MT8";
   else if(StringFind(chemin, "MT6") >= 0)    cache = "MT6";
   else if(StringFind(chemin, "(x86)") >= 0)  cache = "MT4";
   else                                       cache = "MT5";
   return(cache);
  }

string SignatureRobot()
  {
   return(MQLInfoString(MQL_PROGRAM_NAME) + " sur " + NomDuPoste());
  }

void EnvoyerNotification(string ligne)
  {
   if(StringLen(ligne) > 250) ligne = StringSubstr(ligne, 0, 247) + "...";   // plafond push MetaQuotes
   Print(ligne);
   if(!NotificationsPush) return;
   static bool avertiEchec = false;
   if(!SendNotification(ligne) && !avertiEchec)
     {
      Print("Push non envoye. Configure ton MetaQuotes ID : Outils > Options > Notifications.");
      avertiEchec = true;
     }
  }

//| Etat ou alerte : « <robot> sur MT7 : stop du jour touche »
void Notifier(string msg)
  {
   EnvoyerNotification(SignatureRobot() + " : " + msg);
  }

//| Action : « <robot> sur MT7 a ACHETE 0.15 lot a 3421.50 »
void NotifierAction(string phrase)
  {
   EnvoyerNotification(SignatureRobot() + " " + phrase);
  }

//+------------------------------------------------------------------+
//| Notifications + détection des sorties TP (déclenche la ré-entrée)|
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result)
  {
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD) return;
   if(!HistoryDealSelect(trans.deal)) return;
   if(HistoryDealGetInteger(trans.deal, DEAL_MAGIC) != NumeroMagique) return;
   if(HistoryDealGetString(trans.deal, DEAL_SYMBOL) != _Symbol) return;

   double vol  = HistoryDealGetDouble(trans.deal, DEAL_VOLUME);
   double prix = HistoryDealGetDouble(trans.deal, DEAL_PRICE);
   long   sens = HistoryDealGetInteger(trans.deal, DEAL_ENTRY);
   long   typ  = HistoryDealGetInteger(trans.deal, DEAL_TYPE);

   if(sens == DEAL_ENTRY_IN)
      NotifierAction(StringFormat("a %s %.2f lot a %s",
                                  (typ == DEAL_TYPE_BUY ? "ACHETE" : "VENDU"),
                                  vol, DoubleToString(prix, _Digits)));
   else if(sens == DEAL_ENTRY_OUT)
     {
      NotifierAction(StringFormat("a ferme sa position %s de %.2f lot a %s : %s de %.2f $",
                                  (typ == DEAL_TYPE_BUY ? "VENTE" : "ACHAT"),   // le deal de sortie
                                  vol, DoubleToString(prix, _Digits),           // est de sens inverse
                                  (HistoryDealGetDouble(trans.deal, DEAL_PROFIT) >= 0
                                   ? "gain" : "perte"),
                                  MathAbs(HistoryDealGetDouble(trans.deal, DEAL_PROFIT))));
      long raison = HistoryDealGetInteger(trans.deal, DEAL_REASON);
      if(raison == DEAL_REASON_TP)
        {
         attenteReentree = prix;   // profit encaissé -> on guette le repli
         Print("TP encaissé : ré-entrée armée sous ", DoubleToString(prix, _Digits));
        }
      else
         attenteReentree = 0;      // stop ou fermeture stratégique : pas de ré-entrée
     }
  }


//+------------------------------------------------------------------+
//| Journal de reflexion : une ligne par bougie dans                 |
//| MQL8\Files\Ecurie_Journal\<robot>.txt (lisible au Bloc-notes)    |
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| L13 : combien d'annonces le flux contient-il ENCORE A VENIR ?     |
//|                                                                   |
//| Le 22 aout 2026, macrobot_news.txt ne contenait qu'un evenement,  |
//| vieux de trois jours. La fenetre de blocage etant de +/- 30 min,  |
//| le filtre ne pouvait mathematiquement plus rien bloquer — et il   |
//| ecrivait quand meme « libre » dans le bloc-notes. « Libre » et    |
//| « aveugle » devenaient indiscernables. Ils ne le sont plus.       |
//+------------------------------------------------------------------+
int NewsEvenementsAVenir()
  {
   int fh = FileOpen("macrobot_news.txt",
                     FILE_READ | FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_TXT | FILE_ANSI);
   if(fh == INVALID_HANDLE) return(-1);            // -1 = flux illisible
   long maintenant = (long)TimeGMT();
   int n = 0;
   while(!FileIsEnding(fh))
     {
      string ligne = FileReadString(fh);
      if(StringFind(ligne, "EVENT=") != 0) continue;
      string reste = StringSubstr(ligne, 6);
      int sep = StringFind(reste, ";");
      long epoch = StringToInteger(sep > 0 ? StringSubstr(reste, 0, sep) : reste);
      if(epoch > maintenant) n++;
     }
   FileClose(fh);
   return(n);
  }

string EtatFluxNouvelles()
  {
   int n = NewsEvenementsAVenir();
   if(n < 0)  return("AVEUGLE (flux illisible)");
   if(n == 0) return("AVEUGLE (flux sans evenement futur)");
   return(StringFormat("libre (%d a venir)", n));
  }

//+------------------------------------------------------------------+
//| S1 : BUDGET DE RISQUE OUVERT DE TOUTE L'ECURIE                    |
//|                                                                   |
//| La regle des 12 unites des Turtles, generalisee : la somme du     |
//| risque ouvert de TOUS les robots ne depasse jamais HeatEcurieMax. |
//| Sans elle, le pire cas mesure etait 9,2 %% de risque ouvert       |
//| contre un plancher de mort FTMO a 10 %%.                          |
//|                                                                   |
//| Mecanique : chaque robot publie sa part dans une variable globale |
//| du terminal (ECURIE_HEAT_<nom du programme>), recalculee depuis   |
//| les positions REELLES — donc auto-reparante apres un redemarrage, |
//| et sans dependance aux magics des autres generations.             |
//+------------------------------------------------------------------+
input double HeatEcurieMaxPct = 3.0;   // S1 : risque ouvert max de l'ecurie, en %% (0 = off)

string HeatGV() { return "ECURIE_HEAT_" + MQLInfoString(MQL_PROGRAM_NAME); }

void HeatEcuriePublier()
  {
   int unites = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != NumeroMagique) continue;
      unites++;
     }
   GlobalVariableSet(HeatGV(), unites * RisqueParTradePct);
  }

double HeatEcurieTotal()
  {
   double total = 0.0;
   for(int i = GlobalVariablesTotal() - 1; i >= 0; i--)
     {
      string nom = GlobalVariableName(i);
      if(StringFind(nom, "ECURIE_HEAT_") == 0)
         total += GlobalVariableGet(nom);
     }
   return(total);
  }

bool HeatEcurieBloque(double risqueNouvelleUnite)
  {
   if(HeatEcurieMaxPct <= 0) return(false);
   HeatEcuriePublier();
   double total = HeatEcurieTotal();
   if(total + risqueNouvelleUnite <= HeatEcurieMaxPct) return(false);
   EcrireJournal(StringFormat("refus=heat_ecurie (%.2f%% ouvert + %.2f%% > %.2f%%)",
                              total, risqueNouvelleUnite, HeatEcurieMaxPct));
   return(true);
  }

void EcrireJournal(string texte)
  {
   if(!JournalActif) return;
   string fichier = "Ecurie_Journal\\" + MQLInfoString(MQL_PROGRAM_NAME) + ".txt";
   int fh = FileOpen(fichier, FILE_READ | FILE_WRITE | FILE_TXT | FILE_ANSI);
   if(fh == INVALID_HANDLE) return;
   FileSeek(fh, 0, SEEK_END);
   FileWriteString(fh, TimeToString(TimeCurrent(), TIME_DATE | TIME_MINUTES) + " | " + texte + "\r\n");
   FileClose(fh);
  }
//+------------------------------------------------------------------+
int OnInit()
  {
   if(MQLInfoInteger(MQL_TESTER))
      GlobalVariablesDeleteAll("MACROBOT_");   // testeur : purge des gardiens entre les passes (correctif L3 MT4 porte en L4.3)
   Print("L12-R13 | objectif de phase=", ObjectifPhasePctCourant(), "% (+", MargeObjectifPct, "% de coussin)");
   Print("S3.2 charge | decision=", EnumToString(UT_Decision), " indicateurs=", EnumToString(UT_Indicateurs), " heureDecision=", HeureDecision, "h");
   AvertirBaseline();   // S3.2-F3
   Print("S3.2 risque | CppiActif=", CppiActif, " CppiMax=", CppiMax, " TurboCoussinActif=", TurboCoussinActif,
         " x", TurboMultiplicateur, " jusqu'a +", TurboCoussinPct, "% | R13 objectif=", ObjectifPhasePctCourant(),
         "% | ModeChallenge=", ModeChallengeActif);
   trade.SetExpertMagicNumber(NumeroMagique);
   trade.SetDeviationInPoints(50);

   hEmaRapide = iMA(_Symbol, UT_Indicateurs, EMARapide, 0, MODE_EMA, PRICE_CLOSE);
   hEmaLente  = iMA(_Symbol, UT_Indicateurs, EMALente,  0, MODE_EMA, PRICE_CLOSE);
   hAtr       = iATR(_Symbol, UT_Indicateurs, PeriodeATR);
   if(hEmaRapide == INVALID_HANDLE || hEmaLente == INVALID_HANDLE || hAtr == INVALID_HANDLE)
     {
      Print("Erreur : impossible de créer les indicateurs.");
      return(INIT_FAILED);
     }

   if(!GlobalVariableCheck(BaseGV()))
      GlobalVariableSet(BaseGV(), (ChallengeInitialBalance > 0)
                                  ? ChallengeInitialBalance
                                  : AccountInfoDouble(ACCOUNT_BALANCE));   // L8-R10

   Print("BTCUSD_EMA_L43_D1 démarré. Baseline = ", DoubleToString(GlobalVariableGet(BaseGV()), 2),
         " | TP 2R, ré-entrée ", DoubleToString(RetraceReentreeATR, 2),
         "xATR, plafond écurie ", MaxPositionsEcurie);
   EventSetTimer(60);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnTimer()
  {
   HeatEcuriePublier();   // S1
   ReleverEquite();
   LireFacteurVol();
   if(facteurVol > 1.0) facteurVol = 1.0;   // L8 : jamais amplifier, challenge ou pas

   LireNouvelles();
   BiaisMacroPermis();
   BloqueParNouvelles();
   ProtegerPositionsNews();
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   if(hEmaRapide != INVALID_HANDLE) IndicatorRelease(hEmaRapide);
   if(hEmaLente  != INVALID_HANDLE) IndicatorRelease(hEmaLente);
   if(hAtr       != INVALID_HANDLE) IndicatorRelease(hAtr);
  }

//+------------------------------------------------------------------+
void FermerPositions(bool toutLeCompte)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      long m = PositionGetInteger(POSITION_MAGIC);
      if(toutLeCompte)
        {
         // S3.2-F1 : « tout le compte » veut ENFIN dire toute l ecurie.
         // Avant, le filtre magic passait AVANT ce test : le coupe-circuit
         // total ne fermait qu un cinquieme du compte, et le message
         // « arret definitif » etait donc trompeur.
         if(m != 20266041 &&
         m != 20266042 &&
         m != 20266043 &&
         m != 20266044 &&
         m != 20266045) continue;
        }
      else
        {
         if(m != NumeroMagique) continue;
         if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
        }
      trade.PositionClose(ticket);
     }
  }

//+------------------------------------------------------------------+
bool VerifierProtections()
  {
   double equite = AccountInfoDouble(ACCOUNT_EQUITY);
   double base   = GlobalVariableGet(BaseGV());
   if(base <= 0) return(false);

   if(GlobalVariableCheck(HaltGV()) && GlobalVariableGet(HaltGV()) > 0.5)
     {
      // S3.2-F5 : on retente (correctif L4.32) mais toutes les 10 s.
      // A chaque tick, sur le BTC 24/7, une position que le courtier
      // refuse de fermer noyait le serveur (TOO_MANY_REQUESTS).
      static datetime derniereFermeture = 0;
      if(TimeCurrent() - derniereFermeture >= 10)
        {
         derniereFermeture = TimeCurrent();
         FermerPositions(true);
        }
      return(false);
     }

   // ---- L8-R13 : OBJECTIF DE PHASE ATTEINT -> on encaisse ----
   // FTMO valide sur le solde POSITIONS FERMEES. Tant que le profit reste
   // flottant il ne compte pas, et il peut repartir. Des que l'equite passe
   // l'objectif (plus un coussin pour le spread), on ferme tout et on
   // arrete : la phase est gagnee, c'est a Jimmy de passer a la suivante.
   if(ObjectifPhasePctCourant() > 0
      && equite >= base * (1.0 + (ObjectifPhasePctCourant() + MargeObjectifPct) / 100.0))
     {
      Notifier(StringFormat("🎯 OBJECTIF DE PHASE ATTEINT (+%.2f %%). Fermeture de tout, arret. Solde a encaisser : %.2f",
                            100.0 * (equite / base - 1.0), equite));
      FermerPositions(true);
      GlobalVariableSet(HaltGV(), 1.0);
      GlobalVariableSet("MACROBOT_CIBLE_" + (string)AccountInfoInteger(ACCOUNT_LOGIN), equite);
      return(false);
     }

   if(equite <= base * (1.0 - LimitePerteTotalePct / 100.0))
     {
      Notifier("🚨 LIMITE DE PERTE TOTALE ATTEINTE. Fermeture de tout le compte, arrêt définitif.");
      FermerPositions(true);
      GlobalVariableSet(HaltGV(), 1.0);
      return(false);
     }

   string cle = DayGV();
   if(!GlobalVariableCheck(cle))
      GlobalVariableSet(cle, GlobalVariableCheck(LastEqGV()) ? GlobalVariableGet(LastEqGV()) : equite);   // L4.32 : reference d'AVANT le gap
   double debutJour = GlobalVariableGet(cle);
   GlobalVariableSet(LastEqGV(), equite);   // L4.32
   static bool avisJourFait = false;
   if(equite <= debutJour * (1.0 - LimitePerteJourPct / 100.0))
     {
      if(!avisJourFait)
        {
         Notifier("⚠️ Limite de perte journalière atteinte. Fermeture, pause jusqu'à demain.");
         avisJourFait = true;
        }
      FermerPositions(true);
      return(false);
     }
   avisJourFait = false;
   return(true);
  }

//+------------------------------------------------------------------+
bool BiaisMacroPermis()
  {
   if(!BiaisMacroDepuisFichier) return(true);
   if(TimeCurrent() - derniereLectureBiais < 60) return(biaisMacroOK);
   derniereLectureBiais = TimeCurrent();

   long modifBias = (long)FileGetInteger("macrobot_bias.txt", FILE_MODIFY_DATE);   // L8
   if(modifBias > 0 && TimeCurrent() - (datetime)modifBias > 7 * 86400)
     { biaisMacroOK = AchatPermisSansFichier; return(biaisMacroOK); }   // L8 : perime -> neutre
   int fh = FileOpen("macrobot_bias.txt", FILE_READ | FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_TXT | FILE_ANSI);
   if(fh == INVALID_HANDLE)
     {
      biaisMacroOK = AchatPermisSansFichier;
      return(biaisMacroOK);
     }
   string ligne = FileReadString(fh);
   FileClose(fh);

   bool nouveau = (StringFind(ligne, "BTC=1") >= 0);
   if(nouveau != biaisMacroOK)
      Print("Biais macro BTC : ", nouveau ? "ACHATS PERMIS" : "ACHATS BLOQUÉS", " (", ligne, ")");
   biaisMacroOK = nouveau;
   return(biaisMacroOK);
  }

//+------------------------------------------------------------------+
void LireNouvelles()
  {
   if(TimeCurrent() - derniereLectureNews < 60) return;
   derniereLectureNews = TimeCurrent();

   long modifNews = (long)FileGetInteger("macrobot_news.txt", FILE_MODIFY_DATE);   // L8
   if(modifNews > 0 && TimeCurrent() - (datetime)modifNews > 7 * 86400)
     { ArrayResize(newsEpochs, 0); return; }   // L8 : fichier perime -> neutre
   int fh = FileOpen("macrobot_news.txt", FILE_READ | FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_TXT | FILE_ANSI);
   if(fh == INVALID_HANDLE) return;

   ArrayResize(newsEpochs, 0);
   while(!FileIsEnding(fh))
     {
      string ligne = FileReadString(fh);
      if(StringFind(ligne, "FNG=") == 0)
        {
         int v = (int)StringToInteger(StringSubstr(ligne, 4));
         if(v != fngValeur && v >= 0)
            Print("Fear & Greed crypto : ", v, "/100");
         fngValeur = v;
        }
      else if(StringFind(ligne, "EVENT=") == 0)
        {
         string reste = StringSubstr(ligne, 6);
         int sep = StringFind(reste, ";");
         long epoch = StringToInteger(sep > 0 ? StringSubstr(reste, 0, sep) : reste);
         if(epoch > 0)
           {
            int n = ArraySize(newsEpochs);
            ArrayResize(newsEpochs, n + 1);
            newsEpochs[n] = epoch;
           }
        }
     }
   FileClose(fh);
  }

//+------------------------------------------------------------------+
bool BloqueParNouvelles()
  {
   if(!FiltreNouvellesActif) return(false);
   long maintenant = (long)TimeGMT();
   bool bloque = false;
   for(int i = 0; i < ArraySize(newsEpochs); i++)
     {
      if(maintenant >= newsEpochs[i] - (long)MinutesBlocageAvantNews * 60 &&
         maintenant <= newsEpochs[i] + (long)MinutesBlocageApresNews * 60)
        {
         bloque = true;
         break;
        }
     }
   if(bloque != newsBloquaitAvant)
      Notifier(bloque ? "Annonce USD imminente : entrées bloquées, stops en protection."
                      : "Fenêtre d'annonce terminée : retour à la normale.");
   newsBloquaitAvant = bloque;
   return(bloque);
  }

//+------------------------------------------------------------------+
void ProtegerPositionsNews()
  {
   if(ProtectionPositionsNews == PROTECTION_AUCUNE || !newsBloquaitAvant) return;

   double atrBuf[];
   ArraySetAsSeries(atrBuf, true);
   if(CopyBuffer(hAtr, 0, 1, 1, atrBuf) < 1) return;
   double serre = atrBuf[0] * 0.5;
   if(serre <= 0) return;
   double distMin = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != NumeroMagique) continue;

      if(ProtectionPositionsNews == PROTECTION_FERMER)
        {
         Print("Annonce imminente : fermeture préventive de ", ticket);
         trade.PositionClose(ticket);
         continue;
        }
      double slActuel = PositionGetDouble(POSITION_SL);
      double tp       = PositionGetDouble(POSITION_TP);
      double entree   = PositionGetDouble(POSITION_PRICE_OPEN);
      double bid      = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double nouveau  = bid - serre;
      if(bid > entree && entree > nouveau) nouveau = entree;
      if(nouveau > bid - distMin) nouveau = bid - distMin;
      nouveau = NormalizeDouble(nouveau, _Digits);
      if(nouveau > slActuel + serre * 0.1)
         if(trade.PositionModify(ticket, nouveau, tp))
            Print("Fenêtre d'annonce : stop serré à ", DoubleToString(nouveau, _Digits));
     }
  }


//+------------------------------------------------------------------+
//| Facteur de volatilite (macrobot_vol.txt, ecrit chaque matin) :   |
//| >1 marches calmes = mises grossies, <1 agites = mises reduites.  |
//+------------------------------------------------------------------+
void LireFacteurVol()
  {
   if(!FacteurVolActif) { facteurVol = 1.0; return; }
   if(TimeCurrent() - derniereLectureVol < 60) return;
   derniereLectureVol = TimeCurrent();
   long modifVol = (long)FileGetInteger("macrobot_vol.txt", FILE_MODIFY_DATE);   // L4.32
   if(modifVol > 0 && TimeCurrent() - (datetime)modifVol > 7 * 86400)
     { facteurVol = 1.0; return; }   // L4.32 : fichier perime -> facteur neutre
   int fh = FileOpen("macrobot_vol.txt", FILE_READ | FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_TXT | FILE_ANSI);
   if(fh == INVALID_HANDLE)
     {
      // L13 : NE PAS remettre le facteur a 1.0 ici. Un echec de lecture est
      // presque toujours transitoire — le fichier est reecrit chaque heure
      // par la tache Windows, et l'EA tombe parfois pendant l'ecriture.
      // Remettre 1.0 faisait remonter le risque de 0,92 a 1,00 en silence,
      // soit 9 % de taille en plus, jusqu'a la lecture suivante. Constate
      // dans le journal du 22 aout 2026 : 13 impressions de la meme valeur
      // pour le seul robot petrole.
      if(!volLectureEchouee)
        {
         volLectureEchouee = true;
         Print("Facteur de volatilite : lecture impossible, on GARDE ",
               DoubleToString(facteurVol, 2));
        }
      return;
     }
   volLectureEchouee = false;
   string ligne = FileReadString(fh);
   FileClose(fh);
   if(StringFind(ligne, "FACTEUR=") == 0)
     {
      double f = StringToDouble(StringSubstr(ligne, 8));
      if(f >= 0.5 && f <= 1.5)
        {
         if(MathAbs(f - facteurVol) > 0.01)
            Print("Facteur de volatilite mis a jour : ", DoubleToString(f, 2));
         facteurVol = f;
        }
     }
  }
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| L3 : verifie que la MARGE suffit, sinon reduit le lot ou annule   |
//| (sans ca l'ordre est rejete et le signal est perdu en silence)    |
//+------------------------------------------------------------------+
double LotSelonMarge(double lot)
  {
   double lotMin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double pas    = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double prix   = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double marge  = 0.0;
   int essais = 0;
   while(lot >= lotMin && essais < 12)
     {
      if(OrderCalcMargin(ORDER_TYPE_BUY, _Symbol, lot, prix, marge))
         if(marge < AccountInfoDouble(ACCOUNT_MARGIN_FREE) * 0.95)
            return(lot);
      lot -= MathMax(pas, lot * 0.2);
      if(pas > 0) lot = MathFloor(lot / pas) * pas;
      essais++;
     }
   Print("Marge insuffisante pour ouvrir : ordre annule.");
   return(0.0);
  }

//+------------------------------------------------------------------+
//| L3+ MODE CHALLENGE (throttle d'equite, Seykota) : sous la moyenne |
//| 20 jours de l'equite, les nouvelles entrees prennent un risque    |
//| reduit. Backtest : challenges morts 13 % -> 6 % pour -1,9 pt/an.  |
//+------------------------------------------------------------------+
double   HistoEquite[20];
int      HistoIndex = 0;
bool     HistoPlein = false;
datetime dernierReleve = 0;


//+------------------------------------------------------------------+
//| L8-R4 : le frein d'equite survit aux redemarrages.                |
//| Avant : tableau en memoire vive -> remis a zero a chaque relance, |
//| donc le mode challenge n'etait JAMAIS actif en production.        |
//+------------------------------------------------------------------+
string CleEqJour(datetime j)
  {
   MqlDateTime d; TimeToStruct(j, d);
   return(StringFormat("MACROBOT_EQJ_%04d%02d%02d_%s", d.year, d.mon, d.day,
                       (string)AccountInfoInteger(ACCOUNT_LOGIN)));
  }
void ReleverEquite()
  {
   datetime jour = iTime(_Symbol, PERIOD_D1, 0);
   if(jour <= 0 || jour == dernierReleve) return;
   dernierReleve = jour;
   string cle = CleEqJour(jour);
   if(!GlobalVariableCheck(cle))
      GlobalVariableSet(cle, AccountInfoDouble(ACCOUNT_EQUITY));   // L8-R4
   for(int k = 41; k <= 60; k++)                                   // menage
      GlobalVariableDel(CleEqJour(jour - k * 86400));
  }


double FacteurChallenge()
  {
   if(!ModeChallengeActif) return(1.0);
   datetime jour = iTime(_Symbol, PERIOD_D1, 0);
   double somme = 0; int n = 0;
   for(int k = 1; k <= 40 && n < 20; k++)          // L8-R4 : lit les GV
     {
      string cle = CleEqJour(jour - k * 86400);
      if(!GlobalVariableCheck(cle)) continue;
      somme += GlobalVariableGet(cle); n++;
     }
   if(n < 20) return(1.0);
   double moyenne = somme / n;
   if(moyenne > 0 && AccountInfoDouble(ACCOUNT_EQUITY) < moyenne) return(ThrottleChallenge);
   return(1.0);
  }


double CalculerLot(double distanceSL)
  {
   double valeurTick = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tailleTick = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(valeurTick <= 0 || tailleTick <= 0 || distanceSL <= 0) return(0);

   double risqueArgent = AccountInfoDouble(ACCOUNT_EQUITY) * RisqueParTradePct / 100.0 * facteurVol * FacteurRisqueGlobal * FacteurTurbo() * FacteurChallenge();   // L12
   double perteParLot  = distanceSL / tailleTick * valeurTick;
   if(perteParLot <= 0) return(0);

   double lot = risqueArgent / perteParLot;
   double pas    = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double lotMin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double lotMax = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   if(pas > 0) lot = MathFloor(lot / pas) * pas;
   if(lot > lotMax) lot = lotMax;
   if(lot < lotMin)
     {
      Print("Lot calculé trop petit (", DoubleToString(lot, 4), "). Trade annulé.");
      return(0);
     }
   return(LotSelonPlafondNotionnel(LotSelonMarge(lot)));   // S3.2-F2
  }

//+------------------------------------------------------------------+
int PositionActuelle()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != NumeroMagique) continue;
      if(PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) return(1);
      return(-1);
     }
   return(0);
  }

//+------------------------------------------------------------------+
//| Ouvre un achat avec SL/TP standard (utilisé par les 2 entrées)   |
//+------------------------------------------------------------------+
void OuvrirAchat(double atrVal, string commentaire)
  {
   if(HeatEcurieBloque(RisqueParTradePct * FacteurTurbo())) return;   // S1 : budget d'ecurie
   double distanceSL = atrVal * MultiplicateurSL;
   double distanceTP = atrVal * MultiplicateurTP;
   if(distanceSL <= 0) return;
   double lot = CalculerLot(distanceSL);
   if(lot <= 0) return;
   double spreadCourant = SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID);   // L8
   if(SpreadEntreeMaxPct > 0 && spreadCourant > SpreadEntreeMaxPct / 100.0 * distanceSL)
     {
      Print("L12 : entree reportee, spread ", DoubleToString(spreadCourant, _Digits), " > ", DoubleToString(SpreadEntreeMaxPct, 1), " % de la distance de stop");
      return;
     }

   double prix = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double sl   = NormalizeDouble(prix - distanceSL, _Digits);
   double tp   = NormalizeDouble(prix + distanceTP, _Digits);
   trade.Buy(lot, _Symbol, 0.0, sl, tp, commentaire);
  }

//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| S3.2-F2 : plafond de notionnel.                                   |
//| Le calcul de lot borne la perte AU STOP. Il ne borne pas ce que   |
//| l on perd si le prix SAUTE par-dessus le stop. Quand l ATR est    |
//| faible, le stop est serre et le lot devient enorme : le Nasdaq    |
//| pouvait atteindre 97 % de l equite en notionnel, et un gap de     |
//| -10 % (16 mars 2020) aurait tue le compte. Ce plafond est la      |
//| seule protection contre ce cas.                                   |
//+------------------------------------------------------------------+
double NotionnelManche()
  {
   double n = 0.0;
   double contrat = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   double prix    = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != NumeroMagique) continue;
      n += PositionGetDouble(POSITION_VOLUME) * contrat * prix;
     }
   return(n);
  }

double LotSelonPlafondNotionnel(double lot)
  {
   if(PlafondNotionnelEquite <= 0) return(lot);
   double contrat = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   double prix    = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double equite  = AccountInfoDouble(ACCOUNT_EQUITY);
   if(contrat <= 0 || prix <= 0 || equite <= 0) return(lot);
   double reste = PlafondNotionnelEquite * equite - NotionnelManche();
   if(reste <= 0)
     {
      Print("S3.2 : plafond de notionnel atteint, entree refusee");
      return(0.0);
     }
   double lotMax = reste / (prix * contrat);
   if(lot > lotMax)
     {
      Print(StringFormat("S3.2 : lot plafonne par le notionnel %.2f -> %.2f", lot, lotMax));
      lot = lotMax;
     }
   double pas = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(pas > 0) lot = MathFloor(lot / pas + 1e-8) * pas;
   if(lot < SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN)) return(0.0);
   return(lot);
  }

//+------------------------------------------------------------------+
//| S3.2-F3 : la base du coupe-circuit doit etre le capital INITIAL   |
//| du challenge, pas le solde du jour ou le robot a ete attache.     |
//| Si ChallengeInitialBalance vaut 0 et que les variables globales   |
//| ont ete perdues (reinstallation, profil neuf, 4 semaines sans     |
//| lecture), la base se re-ancre sur le solde du moment : partant    |
//| d un creux de -6 %%, le garde-fou -8 %% viserait -13,5 %% du capital  |
//| initial, alors que FTMO ferme le compte a -10 %%.                  |
//| Le robot ne peut pas deviner le bon chiffre. Il peut au moins     |
//| cesser de se taire.                                               |
//+------------------------------------------------------------------+
void AvertirBaseline()
  {
   if(ChallengeInitialBalance > 0) return;
   string msg = "S3.2 ATTENTION : ChallengeInitialBalance = 0. La base du "
                "coupe-circuit est le SOLDE ACTUEL ("
                + DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2)
                + "). Si ce n est pas le capital initial du challenge, le "
                  "garde-fou de perte totale est mal ancre. A renseigner "
                  "dans les parametres du robot.";
   Print(msg);
   Alert(msg);
  }

void OnTick()
  {
   if(!VerifierProtections()) return;

   LireNouvelles();
   bool macroPermis = BiaisMacroPermis() && !BloqueParNouvelles();
   ProtegerPositionsNews();

   datetime barreActuelle = iTime(_Symbol, UT_Decision, 0);   // L4.3
   MqlDateTime tvF;
   TimeToStruct(TimeCurrent(), tvF);
   if(UT_Decision == PERIOD_D1 && tvF.hour < HeureDecision) return;   // L8F : on decide a 08:00, pas au rollover
   if(barreActuelle == derniereBarre) return;
   derniereBarre = barreActuelle;

   double emaRapide[], emaLente[], atr[];
   ArraySetAsSeries(emaRapide, true);
   ArraySetAsSeries(emaLente,  true);
   ArraySetAsSeries(atr,       true);
   if(CopyBuffer(hEmaRapide, 0, 0, 3, emaRapide) < 3) return;
   if(CopyBuffer(hEmaLente,  0, 0, 3, emaLente)  < 3) return;
   if(CopyBuffer(hAtr,       0, 0, 2, atr)       < 2) return;

   bool haussier           = (emaRapide[1] > emaLente[1]);
   bool croisementHaussier = (haussier && emaRapide[2] <= emaLente[2]);
   bool croisementBaissier = (!haussier && emaRapide[2] >= emaLente[2]);

   EcrireJournal(StringFormat("prix=%.2f | EMA20=%.2f %s EMA50=%.2f | position=%s | macro=%s | news=%s | facteurVol=%.2f | reentree_armee=%s",
      iClose(_Symbol, UT_Indicateurs, 1), emaRapide[1], (haussier ? ">" : "<"), emaLente[1],
      (PositionActuelle() != 0 ? "OUVERTE" : "aucune"), (biaisMacroOK ? "OK" : "BLOQUE"),
      (newsBloquaitAvant ? "FENETRE ANNONCE" : EtatFluxNouvelles()), facteurVol, (attenteReentree > 0 ? "OUI" : "non")));

   // régime baissier : fermeture éventuelle + annulation de la ré-entrée
   if(!haussier)
     {
      attenteReentree = 0;
      if(croisementBaissier && PositionActuelle() == 1)
         FermerPositions(false);
      return;
     }

   if(PositionActuelle() != 0) return;
   if(!macroPermis) { EcrireJournal(BiaisMacroPermis() ? "refus=fenetre_annonce" : "refus=biais_macro"); return; }
   if(ComptePositionsEcurie() >= MaxPositionsEcurie) { EcrireJournal("refus=plafond_ecurie"); return; }
   if(FamilleCorreleeOccupee()) { EcrireJournal("refus=famille_correlee"); return; }   // plafond de correlation   // plafond d'écurie (I2)

   // Entrée 1 : croisement haussier frais
   if(croisementHaussier)
     {
      OuvrirAchat(atr[1], "BTC_I2 croisement");
      return;
     }
   // Entrée 2 (I2) : ré-entrée sur repli après un TP encaissé
   if(attenteReentree > 0 &&
      iLow(_Symbol, UT_Indicateurs, 1) <= attenteReentree - RetraceReentreeATR * atr[1])
     {
      Print("Repli de ", DoubleToString(RetraceReentreeATR, 2), "xATR atteint : ré-entrée.");
      OuvrirAchat(atr[1], "BTC_I2 re-entree");
      attenteReentree = 0;
     }
  }
//+------------------------------------------------------------------+
