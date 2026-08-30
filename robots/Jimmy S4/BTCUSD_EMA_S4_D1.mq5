//+------------------------------------------------------------------+
//| GENERATION S4 (23 aout 2026) = S3 + les 10 correctifs du comite,   |
//| durcie S4.1 apres contre-verification par 5 agents.               |
//|  1. CPPI par defaut, turbo OFF (banc s4, BORNE OPTIMISTE : 100 %  |
//|     reussite, 0 mort, survie 100 % ; turbo = 17+10 morts).        |
//|  2. Coupe-circuit total = les 5 magics.  3. Plafond notionnel     |
//|     0,50 partout.  4. Gardien 1,25 % garde (banc de survie).       |
//|  5. Ancre 200 k + alarmes push.  6. Saison short = statu quo      |
//|     banche, doc honnete.  7. Purge heat perime + refus double     |
//|     generation.  8. Jamais long ET court sur un symbole.          |
//|  10. Fermetures espacees 30 s.  9 (git) : cote depot.             |
//|  S4.1 : gardien vivant dans OnTimer, refus traces au journal,     |
//|  pas de vente petrole fraiche le vendredi, CppiMin 0,30 garde     |
//|  (gains du balayage sous le bruit — banc_s4_suite).               |
//|  Magics 20263041-45. NON deployee - demo avant tout compte.       |
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
input double FacteurRisqueGlobal     = 1.0;   // L8 : multiplicateur global (mettre 1.33 une fois finance, gardien fixe -2,5)
input bool   CppiActif       = true;   // S4 (comite 23 aout, pt 1) : CPPI par defaut — banc s4 (BORNE OPTIMISTE, facteur applique apres coup) : 100 % reussite, 0 mort, survie 100 % ; turbo : 17+10 morts, survie 91-96 %
input double CppiMax         = 1.33;   // S4 : 1,33 CONFIRME sous LES DEUX regles de succes (R13 et solde ferme, banc_s4_suite 23 aout) : 1,50-1,75 plus lents ou non-termines, et la survie financee s'ecrase des 1,60 (borne optimiste, mais le classement tient aussi sous la regle FTMO exacte)
input double CppiPlancherPct = 10.0;   // S1 : plancher FTMO qui definit le coussin
input double CppiMin         = 0.30;   // S4 : 0,30 GARDE — le balayage versionne (banc_s4_suite) montre un plateau 0,4-0,8 a 0 mort mais des gains SOUS LE BRUIT (sigma 8 j) ; on garde l'exposition minimale au plancher de ruine (verdict du sceptique)
input bool   TurboCoussinActif   = false;  // S4 (pt 1) : ETEINT — 74 morts au banc du 22 aout ; s'allumait aussi a -6,5 % (zone de mort) et pendant TOUTE la phase 2. Ne s'applique que si CppiActif=false.
input double TurboMultiplicateur = 1.33;   // S3 : banc VAD v2 du 23 aout 2026 — esperance 175 j / 205 j, reussite 92,5 % / 90,8 % (BORNE OPTIMISTE)
input double TurboCoussinPct     = 6.0;    // S3 : coussin de phase, en %, qui coupe le turbo
input double SpreadEntreeMaxPct      = 2.0;   // L8 : entree reportee si le spread depasse ce % de la distance de stop (0 = off)
input double PlafondNotionnelEquite  = 0.50;   // S4 (comite 23 aout, pt 3) : porte depuis les cassures — banc des gaps : seul remede rentable, pire lundi -23 % -> -11 % ; sans lui, Nasdaq calme = 97 % de l'equite en notionnel
input ENUM_TIMEFRAMES UT_Decision    = PERIOD_D1; // L4.3 : une decision par jour (valide walk-forward)
input ENUM_TIMEFRAMES UT_Indicateurs = PERIOD_D1; // L4.3 : EMA/ATR journaliers
input int             HeureDecision  = 8;         // L8F : heure serveur de la decision D1 (evite le spread du rollover de minuit)
input double LimitePerteJourPct   = 1.25;  // S4 (pt 4) : 1,25 CONFIRME par le banc de survie du 23 aout (gardien > 2 % = survie financee 80-93 % ; le CPPI n'est sur qu'a 1,25). L'ancien commentaire « rendu a 2,50 » etait perime.
input double LimitePerteTotalePct = 8.0;    // Coupe-circuit perte totale en %
input double ChallengeInitialBalance = 200000; // S4 (pt 5) : ancre FIXE (FTMO 200 k). 0 = solde au chargement, dangereux : apres une reinstallation le coupe-circuit -8 % se re-ancrait plus bas (jusqu'a -13,5 % du vrai capital).
input double ObjectifPhasePct   = 10.0;  // L8-R13 : objectif de la phase en % (10 = phase 1 FTMO, 5 = phase 2, 0 = desactive)   // D : reglage du laboratoire
input double MargeObjectifPct   = 0.25;  // L8-R13 : coussin encaisse au-dessus de l'objectif (spread/commission)
input int    EMARapide            = 20;
input int    EMALente             = 50;
input int    PeriodeATR           = 14;
input double MultiplicateurSL     = 2.0;    // Stop = 2 x ATR (= 1R)
input double MultiplicateurTP     = 4.0;    // TP = 4 x ATR (= 2R, ~1000 $) (I2)
input double RetraceReentreeATR   = 0.25;   // Ré-entrée après repli de N x ATR sous le prix de sortie TP (I2)
input int    MaxPositionsEcurie   = 2;      // Plafond global de positions de l'écurie (I2)
input long   NumeroMagique        = 20263042;
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
      if(m != 20263041 && m != 20263042 && m != 20263043 && m != 20263044 && m != 20263045) continue;
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
      if(m != 20263041 && m != 20263042 && m != 20263043 && m != 20263044 && m != 20263045) continue;
      string cle = "|" + (string)m + ":" + PositionGetString(POSITION_SYMBOL) + "|";
      if(StringFind(vues, cle) >= 0) continue;
      vues += cle;
      n++;
     }
   return(n);
  }

//+------------------------------------------------------------------+
void Notifier(string msg)
  {
   Print(msg);
   if(!NotificationsPush) return;
   static bool avertiEchec = false;
   if(!SendNotification("[L8] BTC bot : " + msg) && !avertiEchec)
     {
      Print("Push non envoyé. Configure ton MetaQuotes ID : Outils > Options > Notifications.");
      avertiEchec = true;
     }
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

   if(sens == DEAL_ENTRY_IN)
      Notifier(StringFormat("ENTRÉE achat %.2f lot @ %s", vol, DoubleToString(prix, _Digits)));
   else if(sens == DEAL_ENTRY_OUT)
     {
      Notifier(StringFormat("SORTIE %.2f lot @ %s | P/L: %.2f $", vol,
                            DoubleToString(prix, _Digits),
                            HistoryDealGetDouble(trans.deal, DEAL_PROFIT)));
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
   Print("L12-R13 | objectif de phase=", ObjectifPhasePct, "% (+", MargeObjectifPct, "% de coussin)");
   Print("S4 charge | decision=", EnumToString(UT_Decision), " indicateurs=", EnumToString(UT_Indicateurs), " heureDecision=", HeureDecision, "h");
   Print("S4 risque | CPPI=", CppiActif, " [", CppiMin, "-", CppiMax, "] plancher ", CppiPlancherPct,
         "% | turbo=", TurboCoussinActif, " (defaut OFF, comite 23 aout) | R13 objectif=", ObjectifPhasePct,
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
   // S4 (pt 5, durci S4.1) : alarmes d'ancre en PUSH (Notifier), pas en
   // simple Print. La bande de fonctionnement reelle est [-8 % ; +10,25 %]
   // autour de l'ancre : une alarme a 15 % laissait des comptes geles a
   // tort SANS alarme (red team). Seuils : 0,5 % ancre-vs-input (GV
   // heritee d'une autre generation), 5 % solde-vs-ancre.
   {
      double ancreS4 = GlobalVariableGet(BaseGV());
      double soldeS4 = AccountInfoDouble(ACCOUNT_BALANCE);
      if(ChallengeInitialBalance > 0 && ancreS4 > 0
         && MathAbs(ancreS4 / ChallengeInitialBalance - 1.0) > 0.005)
         Notifier(StringFormat("S4 ATTENTION : ancre heritee %.2f != ChallengeInitialBalance %.2f - purger MACROBOT_BASE_ si nouveau challenge.",
                               ancreS4, ChallengeInitialBalance));
      if(ancreS4 > 0 && soldeS4 > 0 && MathAbs(soldeS4 / ancreS4 - 1.0) > 0.05)
         Notifier(StringFormat("S4 ATTENTION : solde %.2f a plus de 5%% de l'ancre %.2f - verifier ChallengeInitialBalance.",
                               soldeS4, ancreS4));
   }

   Print("BTCUSD_EMA_L43_D1 démarré. Baseline = ", DoubleToString(GlobalVariableGet(BaseGV()), 2),
         " | TP 2R, ré-entrée ", DoubleToString(RetraceReentreeATR, 2),
         "xATR, plafond écurie ", MaxPositionsEcurie);
   EventSetTimer(60);
   // S4.1 (red team) : REFUS de demarrer si une position d'une AUTRE
   // generation (magic 2026xxxx hors 20263041-45) vit sur le compte.
   // Deux ecuries ensemble = plafonds, correlations et sens-oppose
   // aveugles entre elles, jusqu'a 1,0x l'equite de notionnel.
   for(int iP2 = PositionsTotal() - 1; iP2 >= 0; iP2--)
     {
      ulong tP2 = PositionGetTicket(iP2);
      if(tP2 == 0) continue;
      long mP2 = PositionGetInteger(POSITION_MAGIC);
      if(mP2 < 20260000 || mP2 > 20269999) continue;   // pas une ecurie Jimmy
      if(mP2 == 20263041 || mP2 == 20263042 || mP2 == 20263043
         || mP2 == 20263044 || mP2 == 20263045) continue;
      Print("S4 : position d'une AUTRE generation detectee (magic ", mP2,
            ") - REFUS de demarrer. Une seule generation par compte.");
      return(INIT_FAILED);
     }
   // S4 (comite 23 aout, pt 7) : purge des variables ECURIE_HEAT_ des
   // generations precedentes (S1/S2/S3). Elles survivent 4 semaines et
   // mangeaient le budget de 3 % en silence : toutes les entrees pouvaient
   // etre refusees sans aucun message.
   for(int iGV = GlobalVariablesTotal() - 1; iGV >= 0; iGV--)
     {
      string nomGV = GlobalVariableName(iGV);
      if(StringFind(nomGV, "ECURIE_HEAT_") == 0 && StringFind(nomGV, "_S4_") < 0)
        {
         Print("S4 : purge du heat perime ", nomGV);
         GlobalVariableDel(nomGV);
        }
     }
   HeatEcuriePublier();   // S4.1 : republication immediate (l'OnDeinit du rechargement a pu effacer notre part)
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnTimer()
  {
   HeatEcuriePublier();   // S1
   VerifierProtections();   // S4.1 (audit) : le gardien vit aussi SANS tick du symbole (week-end, seul graphique survivant)
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
   // S4 (pt 7, durci S4.1) : liberer sa part de heat SEULEMENT si aucune
   // position du robot n'existe. Sinon (rechargement, changement de
   // reglages, fermeture du terminal), la part publiee reste JUSTE et
   // les autres robots continuent de compter ce risque.
   bool resteS4 = false;
   for(int iP = PositionsTotal() - 1; iP >= 0; iP--)
     {
      ulong tP = PositionGetTicket(iP);
      if(tP == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != NumeroMagique) continue;
      resteS4 = true;
      break;
     }
   if(!resteS4) GlobalVariableDel(HeatGV());
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
      long mS4 = PositionGetInteger(POSITION_MAGIC);
      if(toutLeCompte)
        {
         // S4 (comite 23 aout, pt 2) : le drapeau se teste AVANT le magic.
         // Avant : chaque robot ne fermait que SES positions, et le message
         // « fermeture de tout » ne couvrait qu'un cinquieme du compte.
         if(mS4 != 20263041 && mS4 != 20263042 && mS4 != 20263043 && mS4 != 20263044 && mS4 != 20263045) continue;
        }
      else
        {
         if(mS4 != NumeroMagique) continue;
         if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
        }
      trade.PositionClose(ticket);
     }
  }

//+------------------------------------------------------------------+
//| S4 (comite 23 aout, pt 8) : jamais long ET court sur le MEME      |
//| symbole a l'echelle de l'ECURIE. BTC EMA long + BTC Cassure short |
//| = couverture involontaire : exposition nette nulle, double frais  |
//| et swap, deux sieges d'ecurie occupes pour rien.                  |
//+------------------------------------------------------------------+
bool SensOpposeEcurieOccupe(bool venteVoulue)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t == 0) continue;
      long mSens = PositionGetInteger(POSITION_MAGIC);
      if(mSens != 20263041 && mSens != 20263042 && mSens != 20263043 && mSens != 20263044 && mSens != 20263045) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      long typePos = PositionGetInteger(POSITION_TYPE);
      if(venteVoulue && typePos == POSITION_TYPE_BUY) return(true);
      if(!venteVoulue && typePos == POSITION_TYPE_SELL) return(true);
     }
   return(false);
  }

//+------------------------------------------------------------------+
bool VerifierProtections()
  {
   double equite = AccountInfoDouble(ACCOUNT_EQUITY);
   double base   = GlobalVariableGet(BaseGV());
   if(base <= 0) return(false);

   if(GlobalVariableCheck(HaltGV()) && GlobalVariableGet(HaltGV()) > 0.5)
     {
      // S4 (comite 23 aout, pt 10) : en HALT, une position non fermable
      // declenchait une rafale de requetes a chaque tick (BTC 24/7 ->
      // risque de blocage du compte cote serveur). Reessai toutes les 30 s.
      static datetime dernierEssaiHalt = 0;
      if(TimeCurrent() - dernierEssaiHalt >= 30)
        {
         dernierEssaiHalt = TimeCurrent();
         FermerPositions(true);
        }
      return(false);
     }

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
      // S4 (pt 10) : meme espacement de 30 s pour le gardien du jour.
      static datetime dernierEssaiJour = 0;
      if(TimeCurrent() - dernierEssaiJour >= 30)
        {
         dernierEssaiJour = TimeCurrent();
         FermerPositions(true);
        }
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
//| S4 (comite 23 aout, pt 3) : plafond de notionnel, porte depuis    |
//| les cassures. Seule protection contre les gaps (que le backtest   |
//| ne simule pas). Banc des gaps du 23 aout : zero point de          |
//| rendement perdu en echantillon, pire lundi -23 % -> -11 %.        |
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
      Print("S4 : plafond de notionnel atteint, entree refusee");
      return(0.0);
     }
   double lotMaxN = reste / (prix * contrat);
   if(lot > lotMaxN)
     {
      Print(StringFormat("S4 : lot plafonne par le notionnel %.2f -> %.2f", lot, lotMaxN));
      lot = lotMaxN;
     }
   double pasN = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(pasN > 0) lot = MathFloor(lot / pasN + 1e-8) * pasN;
   if(lot < SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN)) return(0.0);
   return(lot);
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
   return(LotSelonMarge(lot));
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
   double lot = LotSelonPlafondNotionnel(CalculerLot(distanceSL));   // S4 (pt 3) : plafond de notionnel
   if(lot <= 0) { EcrireJournal("refus=lot_zero"); return; }   // S4.1 : refus trace pour la revue matinale
   double spreadCourant = SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID);   // L8
   if(SpreadEntreeMaxPct > 0 && spreadCourant > SpreadEntreeMaxPct / 100.0 * distanceSL)
     {
      Print("L12 : entree reportee, spread ", DoubleToString(spreadCourant, _Digits), " > ", DoubleToString(SpreadEntreeMaxPct, 1), " % de la distance de stop");
      EcrireJournal("refus=spread");   // S4.1 : refus trace pour la revue matinale
      return;
     }

   double prix = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double sl   = NormalizeDouble(prix - distanceSL, _Digits);
   double tp   = NormalizeDouble(prix + distanceTP, _Digits);
   trade.Buy(lot, _Symbol, 0.0, sl, tp, commentaire);
  }

//+------------------------------------------------------------------+
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
   if(!macroPermis) { EcrireJournal("refus=biais_macro"); return; }
   if(ComptePositionsEcurie() >= MaxPositionsEcurie) { EcrireJournal("refus=plafond_ecurie"); return; }
   if(FamilleCorreleeOccupee()) { EcrireJournal("refus=famille_correlee"); return; }   // plafond de correlation   // plafond d'écurie (I2)
   if(SensOpposeEcurieOccupe(false)) { EcrireJournal("refus=sens_oppose"); return; }   // S4 (pt 8)

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
