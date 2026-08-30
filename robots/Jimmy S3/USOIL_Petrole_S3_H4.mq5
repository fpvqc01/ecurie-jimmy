//+------------------------------------------------------------------+
//| GENERATION S3 (23 aout 2026) = S2 + TURBO-COUSSIN x1.33 / +6 %    |
//|  CPPI eteint par defaut (CppiActif=false) ; R13 et mode challenge  |
//|  actifs. Combinaison la plus rapide du banc VAD v2 : esperance     |
//|  175 j (10 ans) / 205 j (2021-26), reussite 92,5 % / 90,8 %.       |
//|  Borne optimiste (turbo applique apres coup au banc). Compte        |
//|  FINANCE : remettre CppiActif=true. Magics 20263031-35.            |
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//|                                           USOIL_Petrole_L43_H4.mq5 |
//|  Cassure Donchian 20/10 JOURNALIER sur le pétrole WTI,           |
//|  ACHAT + VENTE S2, ACTIVE SEULEMENT EN SAISON (déc -> mai :       |
//|  accumulation des raffineries avant la "driving season" US).     |
//|                                                                  |
//|  Backtest 10 ans frais FTMO réels : +11.9%/an, Sharpe 0.65,      |
//|  robuste sur 5 fenêtres saisonnières et les 2 moitiés.           |
//|  Le swap long du pétrole est POSITIF sur ce compte (bonus).      |
//|                                                                  |
//|  Utilise les données JOURNALIÈRES peu importe le graphique       |
//|  (impossible de se tromper de cadre de temps en l'attachant).    |
//|  Protections FTMO partagées avec les autres robots (MACROBOT_*). |
//+------------------------------------------------------------------+
#property copyright "Jimmy"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

input double RisqueParTradePct    = 1.69;  // L8 : allocation a x0,75 (etait 1,5)   // parite de risque validee 10 ans (etait 0.75)   // Risque par trade en % du solde (I2 : x1.5)
input double PasMinStopPct        = 0.02;  // L8+-R9 : remontee minimale du stop, en % du prix (anti-spam courtier)
input double FacteurRisqueGlobal     = 1.0;   // L8 : multiplicateur global (mettre 1.33 une fois finance, gardien fixe -2,5)
input bool   CppiActif       = false;  // S3 : ETEINT — remplace par le turbo-coussin (remettre true pour le compte FINANCE : le CPPI reprend la main)
input double CppiMax         = 1.33;   // S1 : facteur a coussin plein (banc 22 aout : 100 % reussite, 0 mort)
input double CppiPlancherPct = 10.0;   // S1 : plancher FTMO qui definit le coussin
input double CppiMin         = 0.30;   // S1 : facteur minimal pres du plancher
input bool   TurboCoussinActif   = true;   // S3 : risque x TurboMultiplicateur tant que l'equite de la phase n'a pas fait +TurboCoussinPct (actif seulement si CppiActif=false)
input double TurboMultiplicateur = 1.33;   // S3 : banc VAD v2 du 23 aout 2026 — esperance 175 j / 205 j, reussite 92,5 % / 90,8 % (BORNE OPTIMISTE)
input double TurboCoussinPct     = 6.0;    // S3 : coussin de phase, en %, qui coupe le turbo
input bool   ReplyActif          = true;   // L12 : ne pas acheter le sommet de la cassure quand la tendance est molle
input double ReplyATR            = 1.25;   // L12 : profondeur du repli attendu, en ATR journalier (plateau 0,75-1,25)
input int    ReplyFenetre        = 5;      // L12 : validite de l'attente, en barres de decision
input double ReplySeuilForce     = 1.00;   // L12 : (prix - EMA50) / ATR au-dela duquel on prend la cassure tout de suite
input double SpreadEntreeMaxPct      = 2.0;   // L8 : entree reportee si le spread depasse ce % de la distance de stop (0 = off)
input double LimitePerteJourPct   = 1.25;  // L11 : rendu a 2,50 % - la deconcentration du BTC a traite la cause (banc L11 : -41 a -75 jours, reussite inchangee)    // L3 : resserre (valide 19 aout ; FTMO = 5)   // D : reglage du laboratoire
input double LimitePerteTotalePct = 8.0;    // Coupe-circuit perte totale (FTMO = 10)
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
//+------------------------------------------------------------------+
double ObjectifPhasePctCourant()
  {
   if(PhaseActuelle == PHASE_1) return(ObjectifPhase1Pct);
   if(PhaseActuelle == PHASE_2) return(ObjectifPhase2Pct);
   return(0.0);   // compte finance : on ne ferme pas tout seul
  }
input double MargeObjectifPct   = 0.25;  // L8-R13 : coussin encaisse au-dessus de l'objectif (spread/commission)
input int    PeriodeEntree        = 20;     // Cassure du plus haut des N jours
input int    PeriodeSortie        = 10;     // Stop suiveur sous le plus bas des M jours
input ENUM_TIMEFRAMES UT_Decision    = PERIOD_H4; // L4.3 : cadence de decision (valide walk-forward)
input double TamponCassurePct = 0.25; // L4.31 : entree seulement si cassure > canal + X % (plateau 0,15-0,30 valide)
input bool   VenteActive      = true;   // S2 : cote vendeur (cassure du canal bas 20 j, miroir strict — banc 22 aout)
input int    VenteFiltreEMA   = 200;    // S2 : vente armee seulement sous l'EMA N jours du symbole (0 = toujours armee)
input int    MoisDebutSaison      = 12;     // Saison favorable : début (mois)
input int    JourDebutSaison      = 1;      //   ... jour
input int    MoisFinSaison        = 5;      // Saison favorable : fin (mois)
input int    JourFinSaison        = 31;     //   ... jour
input int    PeriodeATR           = 14;     // ATR journalier (protection annonces)
input long   NumeroMagique        = 20263034; // Identifiant distinct
input int    MaxPositionsEcurie   = 2;      // Plafond global de positions de l'ecurie (I2)
input bool   FiltreNouvellesActif    = true; // bloquer les entrées autour des annonces USD fort impact
input int    MinutesBlocageAvantNews = 30;
input int    MinutesBlocageApresNews = 30;

enum ENUM_PROTECTION_NEWS
  {
   PROTECTION_AUCUNE = 0,   // ne rien faire sur les positions ouvertes
   PROTECTION_SERRER = 1,   // serrer les stops pendant la fenêtre d'annonce (recommandé)
   PROTECTION_FERMER = 2    // fermer les positions avant l'annonce
  };
input ENUM_PROTECTION_NEWS ProtectionPositionsNews = PROTECTION_SERRER;
input bool   FacteurVolActif       = true; // moduler le risque selon la volatilite des marches (L3)
input bool   PyramidageActif    = true;  // L3 : ajouter des unites sur un trade gagnant (Turtles)
input int    MaxUnites          = 4;     // L4.2 : pyramide 4 (valide 21 aout, +2 pts H4 10 ans)
input bool   GardeVendrediActif = true;  // L8C : aucune nouvelle unite de pyramide le vendredi (gaps OPEP+ du week-end)
input double PasUniteATR        = 0.5;   // L3 : ajouter une unite chaque +N x ATR
input double StopSousDerniereUniteATR = 2.0; // L3 : stop commun a N x ATR sous la derniere unite
input bool   BreakevenCollectifActif = false;   // L8-R2 : protege le point mort quand le trade est bien en profit   // D : reglage du laboratoire
input double BreakevenCollectifPct   = 5.0;    // L8-R2 : seuil de profit qui arme la protection
input double PlafondNotionnelEquite  = 0.50;   // S1 : mesure 22 aout — CAGR inchange, pire choc historique -40 %% -> -25 %%
input bool   JournalActif          = true; // journal de reflexion (Files\Ecurie_Journal)
input bool   PlafondCorrelationActif = true;  // un seul metal/indice a la fois (crises)
input bool   ModeChallengeActif = true;  // L4 : ACTIF par defaut (valide scan 21 aout, 2 moteurs)
input double ThrottleChallenge  = 0.75;  // L3+ : facteur sous la moyenne 20 j
input bool   NotificationsPush       = true; // push cellulaire (MetaQuotes ID)

CTrade   trade;
int      hAtr = INVALID_HANDLE;
datetime dernierJour = 0;
datetime derniereLectureNews = 0;
long     newsEpochs[];
bool     newsBloquaitAvant = false;
datetime derniereLectureVol = 0;
double   facteurVol = 1.0;
bool     volLectureEchouee = false;   // L13
int      hEmaVente = INVALID_HANDLE;   // S2 : EMA du filtre de regime vendeur (D1)


string BaseGV() { return "MACROBOT_BASE_" + (string)AccountInfoInteger(ACCOUNT_LOGIN); }
string HaltGV() { return "MACROBOT_HALT_" + (string)AccountInfoInteger(ACCOUNT_LOGIN); }
string LastEqGV() { return "MACROBOT_LASTEQ_" + (string)AccountInfoInteger(ACCOUNT_LOGIN); }   // L4.32 : equite d'avant le gap
int      hEma50 = INVALID_HANDLE;   // L12 : EMA 50 journaliere, pour mesurer la force de la tendance
bool     replArme = false;          // L12 : une attente de repli est-elle armee ?
double   replNiveau = 0.0;          // L12 : prix vise pour l'entree
double   replStop = 0.0;            // L12 : stop memorise au moment de l'armement
int      replReste = 0;             // L12 : barres restantes avant expiration de l'attente

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
string DayGV()
  {
   MqlDateTime now;
   TimeToStruct(TimeCurrent(), now);
   return StringFormat("MACROBOT_DAY_%04d%02d%02d_%s",
                       now.year, now.mon, now.day,
                       (string)AccountInfoInteger(ACCOUNT_LOGIN));
  }

//+------------------------------------------------------------------+
//| Plafond d'ecurie : positions de tous nos robots (I2)             |
//+------------------------------------------------------------------+
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
      if(m != 20263031 && m != 20263032 && m != 20263033 && m != 20263034 && m != 20263035) continue;
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
      if(m != 20263031 && m != 20263032 && m != 20263033 && m != 20263034 && m != 20263035) continue;
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
   if(!SendNotification("[L8] Pétrole : " + msg) && !avertiEchec)
     {
      Print("Push non envoyé. Configure ton MetaQuotes ID : Outils > Options > Notifications.");
      avertiEchec = true;
     }
  }

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
      Notifier(StringFormat("ENTRÉE cassure saisonnière %.2f lot @ %s", vol, DoubleToString(prix, _Digits)));
   else if(sens == DEAL_ENTRY_OUT)
      Notifier(StringFormat("SORTIE %.2f lot @ %s | P/L: %.2f $", vol,
                            DoubleToString(prix, _Digits),
                            HistoryDealGetDouble(trans.deal, DEAL_PROFIT)));
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
   // S2.1 : sur un compte NETTING (une position nette par symbole), un
   // ordre de vente de ce robot REDUIRAIT ou FERMERAIT la position
   // d'achat d'un autre robot sur le meme symbole. Toute la logique de
   // piles suppose un compte HEDGING — FTMO en fournit, mais on ne le
   // suppose plus : on le verifie.
   if(VenteActive && AccountInfoInteger(ACCOUNT_MARGIN_MODE)
      != ACCOUNT_MARGIN_MODE_RETAIL_HEDGING)
     {
      Print("S2 : compte NETTING detecte — le cote vendeur casserait les"
            " positions des autres robots. Refus de demarrer.");
      return(INIT_FAILED);
     }
   if(MQLInfoInteger(MQL_TESTER))
      GlobalVariablesDeleteAll("MACROBOT_");   // testeur : purge des gardiens entre les passes (correctif L3 MT4 porte en L4.3)
   Print("L12-R13 | objectif de phase=", ObjectifPhasePctCourant(), "% (+", MargeObjectifPct, "% de coussin)");
   Print("S3 charge | decision=", EnumToString(UT_Decision), " canaux=D1 tampon=", TamponCassurePct, "%");
   Print("L12 | gardien=", LimitePerteJourPct, "% breakeven=+", BreakevenCollectifPct, "% notionnelMax=", PlafondNotionnelEquite, "x equite");
   Print("S3 charge | PyramideMax=", MaxUnites, " GardeVendredi=", GardeVendrediActif, " ModeChallenge=", ModeChallengeActif);
   Print("S3 turbo | CppiActif=", CppiActif, " TurboCoussinActif=", TurboCoussinActif,
         " x", TurboMultiplicateur, " jusqu'a +", TurboCoussinPct, "% | R13 objectif=", ObjectifPhasePctCourant(),
         "% | ModeChallenge=", ModeChallengeActif);
   Print("S2 vendeur | VenteActive=", VenteActive, " FiltreEMA=", VenteFiltreEMA,
         " (arme seulement si cloture D1 complete < EMA)");
   trade.SetExpertMagicNumber(NumeroMagique);
   trade.SetDeviationInPoints(50);

   hAtr = iATR(_Symbol, PERIOD_D1, PeriodeATR);
   hEma50 = iMA(_Symbol, PERIOD_D1, 50, 0, MODE_EMA, PRICE_CLOSE);   // L12
   if(VenteActive && VenteFiltreEMA > 0)   // S2 : filtre de regime du cote vendeur
     {
      hEmaVente = iMA(_Symbol, PERIOD_D1, VenteFiltreEMA, 0, MODE_EMA, PRICE_CLOSE);
      if(hEmaVente == INVALID_HANDLE)
         Print("S2 : EMA du filtre vendeur introuvable -> cote vendeur DESARME (les achats continuent).");
     }
   if(hAtr == INVALID_HANDLE)
     {
      Print("Erreur : impossible de créer l'ATR.");
      return(INIT_FAILED);
     }

   if(!GlobalVariableCheck(BaseGV()))
      GlobalVariableSet(BaseGV(), (ChallengeInitialBalance > 0)
                                  ? ChallengeInitialBalance
                                  : AccountInfoDouble(ACCOUNT_BALANCE));   // L8-R10

   Print("USOIL_Petrole_L43_H4 démarré. Baseline challenge = ",
         DoubleToString(GlobalVariableGet(BaseGV()), 2),
         " | Saison favorable : ", MoisDebutSaison, "/", JourDebutSaison,
         " au ", MoisFinSaison, "/", JourFinSaison);

   EventSetTimer(60);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnTimer()
  {
   HeatEcuriePublier();   // S1
   static datetime dernierAvisSwap = 0;   // L8
   if(TimeCurrent() - dernierAvisSwap > 86400)
     {
      dernierAvisSwap = TimeCurrent();
      double swapLong = SymbolInfoDouble(_Symbol, SYMBOL_SWAP_LONG);
      if(swapLong < 0)
         Notifier(StringFormat("swap long USOIL NEGATIF (%.2f/nuit) : contango — surveiller la manche petrole", swapLong));
     }

   ReleverEquite();
   LireNouvelles();
   LireFacteurVol();
   if(facteurVol > 1.0) facteurVol = 1.0;   // L8 : jamais amplifier, challenge ou pas
   BloqueParNouvelles();
   ProtegerPositionsNews();
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   if(hAtr != INVALID_HANDLE) IndicatorRelease(hAtr);
   if(hEma50 != INVALID_HANDLE) IndicatorRelease(hEma50);   // L12
   if(hEmaVente != INVALID_HANDLE) IndicatorRelease(hEmaVente);   // S2
  }

//+------------------------------------------------------------------+
//| Sommes-nous dans la fenêtre saisonnière favorable ?              |
//| Gère les fenêtres qui chevauchent le Nouvel An (déc -> mai).     |
//+------------------------------------------------------------------+
bool EnSaison()
  {
   MqlDateTime now;
   TimeToStruct(TimeCurrent(), now);
   int md  = now.mon * 100 + now.day;
   int deb = MoisDebutSaison * 100 + JourDebutSaison;
   int fin = MoisFinSaison * 100 + JourFinSaison;
   if(deb <= fin) return(md >= deb && md <= fin);
   return(md >= deb || md <= fin);   // fenêtre à cheval sur l'année
  }

//+------------------------------------------------------------------+
void FermerPositions(bool toutLeCompte)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) != NumeroMagique) continue;
      if(!toutLeCompte && PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
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
      FermerPositions(true);   // L4.32 : on retente la fermeture a chaque tick
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
      Notifier("🚨 LIMITE DE PERTE TOTALE ATTEINTE. Fermeture, arrêt définitif.");
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
      if(StringFind(ligne, "EVENT=") == 0)
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
   double serre = atrBuf[0] * 0.25;   // ATR journalier : serrage au quart
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
         Print("Annonce imminente : fermeture préventive de la position ", ticket);
         trade.PositionClose(ticket);
         continue;
        }

      double slActuel = PositionGetDouble(POSITION_SL);
      double tp       = PositionGetDouble(POSITION_TP);
      double entree   = PositionGetDouble(POSITION_PRICE_OPEN);
      if(PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_SELL)   // S2 : serrage miroir du cote vendeur
        {
         double askV     = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double nouveauV = askV + serre;
         if(askV < entree && entree < nouveauV) nouveauV = entree;
         if(nouveauV < askV + distMin) nouveauV = askV + distMin;
         nouveauV = NormalizeDouble(nouveauV, _Digits);
         if(slActuel <= 0 || nouveauV < slActuel - serre * 0.1)
            if(trade.PositionModify(ticket, nouveauV, tp))
               Print("Fenetre d'annonce : stop VENTE serre a ", DoubleToString(nouveauV, _Digits));
         continue;
        }
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
double LotSelonMarge(double lot, bool vente=false)   // S2 : vente=true -> marge cote SELL
  {
   double lotMin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double pas    = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double prix   = SymbolInfoDouble(_Symbol, vente ? SYMBOL_BID : SYMBOL_ASK);   // S2
   double marge  = 0.0;
   int essais = 0;
   while(lot >= lotMin && essais < 12)
     {
      if(OrderCalcMargin(vente ? ORDER_TYPE_SELL : ORDER_TYPE_BUY, _Symbol, lot, prix, marge))   // S2
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


double CalculerLot(double distanceSL, bool vente=false)   // S2
  {
   double valeurTick = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tailleTick = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(valeurTick <= 0 || tailleTick <= 0 || distanceSL <= 0)
     {
      Print("Impossible de calculer le lot (tick=", tailleTick, ", valeur=", valeurTick, ").");
      return(0);
     }

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
   return(LotSelonMarge(lot, vente));   // S2
  }

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
//| PYRAMIDAGE (L3, regle des Turtles) : l'etat est lu directement    |
//| dans les positions ouvertes -> survit a un redemarrage de MT5.    |
//+------------------------------------------------------------------+
int NombreUnites()
  {
   int n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != NumeroMagique) continue;
      n++;
     }
   return(n);
  }


//+------------------------------------------------------------------+
//| L8-R2 : point mort collectif des unites = (premiere+derniere)/2   |
//+------------------------------------------------------------------+
double PrixPremiereUnite()
  {
   double p = 0.0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != NumeroMagique) continue;
      if(PositionGetInteger(POSITION_TYPE) != POSITION_TYPE_BUY) continue;   // S2 : ne compte que les achats
      double po = PositionGetDouble(POSITION_PRICE_OPEN);
      if(p == 0.0 || po < p) p = po;
     }
   return(p);
  }

double AppliquerBreakevenCollectif(double niveau, double dernier)
  {
   if(!BreakevenCollectifActif || BreakevenCollectifPct <= 0) return(niveau);
   double premiere = PrixPremiereUnite();
   if(premiere <= 0 || dernier <= 0) return(niveau);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(bid <= 0) return(niveau);
   if((bid - premiere) / premiere < BreakevenCollectifPct / 100.0) return(niveau);
   double moyen = (premiere + dernier) / 2.0;
   return(moyen > niveau ? moyen : niveau);
  }

//+------------------------------------------------------------------+
//| L8-R3 : plafond de notionnel. Le moteur de backtest bride a 2,0x  |
//| l'equite ; les robots n'avaient AUCUN plafond (jusqu'a 3,2x       |
//| observe). Assurance contre les gaps, que le backtest ne simule pas|
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
      Notifier("L12 : plafond de notionnel atteint, unite refusee");
      return(0.0);
     }
   double lotMax = reste / (prix * contrat);
   if(lot > lotMax)
     {
      Notifier(StringFormat("L8 : lot plafonne par le notionnel %.2f -> %.2f", lot, lotMax));
      lot = lotMax;
     }
   double pas = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(pas > 0) lot = MathFloor(lot / pas + 1e-8) * pas;
   if(lot < SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN)) return(0.0);
   return(lot);
  }
double PrixDerniereUnite()   // prix d'ouverture le plus HAUT = derniere unite ajoutee
  {
   double p = 0.0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != NumeroMagique) continue;
      if(PositionGetInteger(POSITION_TYPE) != POSITION_TYPE_BUY) continue;   // S2 : ne compte que les achats
      double po = PositionGetDouble(POSITION_PRICE_OPEN);
      if(po > p) p = po;
     }
   return(p);
  }

double LotUnite()            // taille de la 1re unite (prix d'ouverture le plus BAS)
  {
   double p = 0.0, lot = 0.0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != NumeroMagique) continue;
      if(PositionGetInteger(POSITION_TYPE) != POSITION_TYPE_BUY) continue;   // S2 : ne compte que les achats
      double po = PositionGetDouble(POSITION_PRICE_OPEN);
      if(p == 0.0 || po < p) { p = po; lot = PositionGetDouble(POSITION_VOLUME); }
     }
   return(lot);
  }

void AppliquerStopCommun(double niveau)
  {
   double distMin = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
   double bid     = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(niveau > bid - distMin) niveau = bid - distMin;
   niveau = NormalizeDouble(niveau, _Digits);
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != NumeroMagique) continue;
      if(PositionGetInteger(POSITION_TYPE) != POSITION_TYPE_BUY) continue;   // S2 : ne compte que les achats
      double slActuel = PositionGetDouble(POSITION_SL);
      // L8+-R9 : le stop ne fait que monter, et seulement par pas utiles.
      // L'ancienne garde etait +1 point, soit 1 cent sur le BTC : le robot
      // inondait le courtier de demandes de modification pendant les rushes.
      double pasMin = bid * PasMinStopPct / 100.0;
      if(niveau > slActuel + pasMin)
         trade.PositionModify(ticket, niveau, PositionGetDouble(POSITION_TP));
     }
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   if(!VerifierProtections()) return;

   LireNouvelles();
   LireFacteurVol();
   if(facteurVol > 1.0) facteurVol = 1.0;   // L8 : jamais amplifier, challenge ou pas
   bool newsOK = !BloqueParNouvelles();
   ProtegerPositionsNews();

   // une décision par JOUR (données journalières, peu importe le graphique)
   datetime jourActuel = iTime(_Symbol, UT_Decision, 0);   // L4.3 : decision par barre UT
   if(jourActuel == dernierJour) return;
   dernierJour = jourActuel;

   int besoin = MathMax(PeriodeEntree, PeriodeSortie) + 2;
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, PERIOD_D1, 0, besoin, rates) < besoin) return;
   double declencheur  = iClose(_Symbol, UT_Decision, 1);   // L4.3 : barre de decision fermee
   double hautDecision = iHigh(_Symbol, UT_Decision, 1);
   if(declencheur <= 0 || hautDecision <= 0) return;

   double hautCanal = rates[1].high;   // L4.3 (corrige 20 aout : la veille fait partie du canal)
   for(int i = 2; i <= PeriodeEntree; i++)
      if(rates[i].high > hautCanal) hautCanal = rates[i].high;
   double basCanal = rates[1].low;   // L4.3
   for(int i = 2; i <= PeriodeSortie; i++)
      if(rates[i].low < basCanal) basCanal = rates[i].low;

   // S2 : canaux miroirs du cote vendeur (entree = bas PeriodeEntree j,
   // rachat/stop suiveur = haut PeriodeSortie j)
   double basCanalVente = rates[1].low;
   for(int i = 2; i <= PeriodeEntree; i++)
      if(rates[i].low < basCanalVente) basCanalVente = rates[i].low;
   double hautCanalVente = rates[1].high;
   for(int i = 2; i <= PeriodeSortie; i++)
      if(rates[i].high > hautCanalVente) hautCanalVente = rates[i].high;

   EcrireJournal(StringFormat("cloture=%.2f | canal_haut=%.2f (dist %.2f%%) | canal_bas=%.2f | saison=%s | position=%s | news=%s | facteurVol=%.2f",
      declencheur, hautCanal, (hautCanal - declencheur) / declencheur * 100.0, basCanal,
      (EnSaison() ? "FAVORABLE" : "hors saison"), (PositionOuverte() ? (StringFormat("OUVERTE %d unite(s)", NombreUnites())) : "aucune"),
      (newsBloquaitAvant ? "FENETRE ANNONCE" : EtatFluxNouvelles()), facteurVol));
   if(VenteActive)   // S2 : trace du cote vendeur
      EcrireJournal(StringFormat("S2 vente : canal_bas%d=%.2f | canal_haut%d=%.2f | regime=%s",
         PeriodeEntree, basCanalVente, PeriodeSortie, hautCanalVente,
         (VenteArmee() ? "ARME (cloture D1 sous EMA)" : "desarme")));
   if(PositionOuverte())
     {
      if(PositionPileVendeuse())   // S2 : la pile est vendeuse -> gestion miroir
        {
         GererPositionVente(declencheur, hautCanalVente);
         return;
        }
      // sortie : clôture journalière sous le canal bas (toujours active,
      // même hors saison — on ne garde jamais une position sans gestion)
      if(declencheur < basCanal)
        {
         FermerPositions(false);
         return;
        }
      // --- L3 : PYRAMIDAGE (Turtles) + stop commun -------------------
      double atrPyr[];
      ArraySetAsSeries(atrPyr, true);
      double atrVal = 0.0;
      if(CopyBuffer(hAtr, 0, 1, 1, atrPyr) >= 1) atrVal = atrPyr[0];

      int    unites  = NombreUnites();
      double dernier = PrixDerniereUnite();

      // 1) ajout d'une unite quand le prix a avance de PasUniteATR
      //    depuis la derniere unite (une seule unite par bougie : prudent)
      MqlDateTime tvC;
      TimeToStruct(TimeCurrent(), tvC);
      bool ajoutBloqueVendredi = (GardeVendrediActif && tvC.day_of_week == 5);   // L8C
      if(PyramidageActif && !ajoutBloqueVendredi && unites > 0 && unites < MaxUnites && atrVal > 0 && dernier > 0)
        {
         double seuilAjout = dernier + PasUniteATR * atrVal;
         if(hautDecision >= seuilAjout && ComptePositionsEcurie() < MaxPositionsEcurie)
           {
            double lotAjout = LotSelonPlafondNotionnel(LotSelonMarge(LotUnite()));
               if(HeatEcurieBloque(RisqueParTradePct * FacteurTurbo())) lotAjout = 0.0;   // S1   // L8-R3/R11
            if(lotAjout <= 0)
               Notifier("L12 : unite de pyramide REFUSEE (marge ou notionnel)");
            else
              {
               double slProvisoire = NormalizeDouble(basCanal, _Digits);
               if(trade.Buy(lotAjout, _Symbol, 0.0, slProvisoire, 0.0,
                            "L8 unite " + (string)(unites + 1) + "/" + (string)MaxUnites))
                 {
                  Notifier(StringFormat("PYRAMIDE unite %d/%d : +%.2f lot @ %.2f",
                           unites + 1, MaxUnites, lotAjout,
                           SymbolInfoDouble(_Symbol, SYMBOL_ASK)));
                  unites  = NombreUnites();
                  dernier = PrixDerniereUnite();
                 }
              }
           }
        }

      // 2) stop commun : le plus HAUT entre le canal bas et
      //    (derniere unite - StopSousDerniereUniteATR x ATR)
      double niveauStop = basCanal;
      if(PyramidageActif && unites > 1 && atrVal > 0 && dernier > 0)
        {
         double stopTurtle = dernier - StopSousDerniereUniteATR * atrVal;
         if(stopTurtle > niveauStop) niveauStop = stopTurtle;
        }
      niveauStop = AppliquerBreakevenCollectif(niveauStop, dernier);   // L8-R2
      AppliquerStopCommun(niveauStop);
      return;
     }

   // S2 : logique ACHAT d'origine (deplacee VERBATIM dans TenterEntreeAchat),
   // puis cote vendeur seulement si aucune position n'existe.
   TenterEntreeAchat(declencheur, hautCanal, basCanal, newsOK);
   if(PositionOuverte()) return;   // S2 : jamais long ET court sur le meme robot
   TenterEntreeVente(declencheur, basCanalVente, hautCanalVente);
  }
//+------------------------------------------------------------------+

//+------------------------------------------------------------------+
//| S2 : COTE VENDEUR — miroir strict de la cassure achat, valide au  |
//| banc le 22 aout 2026 (generation-S/banc_vad_cond.py, RAPPORT_VAD  |
//| sections 7-8, revalide au simulateur v2 : feu vert de banc).      |
//|   - vente a la cassure du canal BAS 20 j (tampon miroir -0,25 %)  |
//|   - rachat a la cloture au-dessus du canal HAUT 10 j              |
//|   - pyramide symetrique : +1 unite chaque 0,5 ATR VERS LE BAS     |
//|   - stop commun 2 ATR AU-DESSUS de la derniere unite : il ne fait |
//|     que DESCENDRE (miroir du stop achat qui ne fait que monter)   |
//|   - ARME seulement si la cloture D1 de la derniere barre COMPLETE |
//|     est sous l'EMA VenteFiltreEMA jours (decalage 1 — jamais la   |
//|     barre en cours : aucun regard vers l'avenir)                  |
//|   - une vente ouverte N'EST PAS fermee si le filtre se desarme :  |
//|     elle vit sa vie (stop suiveur + rachat canal haut)            |
//+------------------------------------------------------------------+
void TenterEntreeAchat(double declencheur, double hautCanal, double basCanal, bool newsOK)
  {
   // Extraction VERBATIM de l'ancienne fin d'OnTick (S1) : aucune ligne
   // modifiee. Un return quitte la fonction et OnTick tente la vente.
   // entrée : cassure du canal haut, EN SAISON seulement, hors annonces
   if(!EnSaison()) { EcrireJournal("refus=hors_saison"); return; }
   if(!newsOK) { EcrireJournal("refus=fenetre_annonce"); return; }
   // ---------- L12 : repli conditionnel ----------
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
   if(declencheur <= hautCanal * (1.0 + TamponCassurePct / 100.0)) return;   // L4.31 tampon anti-faux-signal
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

   if(ComptePositionsEcurie() >= MaxPositionsEcurie) { EcrireJournal("refus=plafond_ecurie"); return; }
   if(FamilleCorreleeOccupee()) { EcrireJournal("refus=famille_correlee"); return; }   // plafond de correlation // plafond d'ecurie (I2)

   double prix = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double distanceSL = prix - basCanal;
   if(distanceSL <= 0 || distanceSL > 0.50 * prix) return;
   double lot = LotSelonPlafondNotionnel(CalculerLot(distanceSL));   // L8-R3
   if(lot <= 0) return;
   double spreadCourant = SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID);   // L8
   if(SpreadEntreeMaxPct > 0 && spreadCourant > SpreadEntreeMaxPct / 100.0 * distanceSL)
     {
      Print("L12 : entree reportee, spread ", DoubleToString(spreadCourant, _Digits), " > ", DoubleToString(SpreadEntreeMaxPct, 1), " % de la distance de stop");
      return;
     }


   if(HeatEcurieBloque(RisqueParTradePct * FacteurTurbo())) return;   // S1 : budget d'ecurie
   double sl = NormalizeDouble(basCanal, _Digits);
   trade.Buy(lot, _Symbol, 0.0, sl, 0.0, "USOIL_Breakout saison");
  }

bool VenteArmee()
  {
   if(!VenteActive) return(false);
   if(VenteFiltreEMA <= 0) return(true);            // 0 = toujours armee
   if(hEmaVente == INVALID_HANDLE) return(false);   // filtre illisible -> pas de vente (les achats continuent)
   double b[];
   if(CopyBuffer(hEmaVente, 0, 1, 1, b) < 1) return(false);   // decalage 1 : derniere barre COMPLETE
   double clotureD1 = iClose(_Symbol, PERIOD_D1, 1);          // jamais la barre en cours
   if(clotureD1 <= 0 || b[0] <= 0 || b[0] == EMPTY_VALUE) return(false);   // S2.1 : EMPTY_VALUE est un nombre astronomique, pas zero — sans ce test, un indicateur illisible ARMAIT la vente
   return(clotureD1 < b[0]);
  }

bool PositionPileVendeuse()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != NumeroMagique) continue;
      if(PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_SELL) return(true);
     }
   return(false);
  }

double PrixPremiereUniteVente()   // prix d'ouverture le plus HAUT = premiere unite vendue
  {
   double p = 0.0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != NumeroMagique) continue;
      if(PositionGetInteger(POSITION_TYPE) != POSITION_TYPE_SELL) continue;
      double po = PositionGetDouble(POSITION_PRICE_OPEN);
      if(po > p) p = po;
     }
   return(p);
  }

double PrixDerniereUniteVente()   // prix d'ouverture le plus BAS = derniere unite (pyramide vers le bas)
  {
   double p = 0.0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != NumeroMagique) continue;
      if(PositionGetInteger(POSITION_TYPE) != POSITION_TYPE_SELL) continue;
      double po = PositionGetDouble(POSITION_PRICE_OPEN);
      if(p == 0.0 || po < p) p = po;
     }
   return(p);
  }

double LotUniteVente()            // taille de la 1re unite vendue (prix d'ouverture le plus HAUT)
  {
   double p = 0.0, lot = 0.0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != NumeroMagique) continue;
      if(PositionGetInteger(POSITION_TYPE) != POSITION_TYPE_SELL) continue;
      double po = PositionGetDouble(POSITION_PRICE_OPEN);
      if(po > p) { p = po; lot = PositionGetDouble(POSITION_VOLUME); }
     }
   return(lot);
  }

double AppliquerBreakevenCollectifVente(double niveau, double dernier)
  {
   if(!BreakevenCollectifActif || BreakevenCollectifPct <= 0) return(niveau);
   double premiere = PrixPremiereUniteVente();
   if(premiere <= 0 || dernier <= 0) return(niveau);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);   // prix de rachat d'un court
   if(ask <= 0) return(niveau);
   if((premiere - ask) / premiere < BreakevenCollectifPct / 100.0) return(niveau);
   double moyen = (premiere + dernier) / 2.0;
   return(moyen < niveau ? moyen : niveau);   // miroir : on ne peut qu'ABAISSER le niveau
  }

void AppliquerStopCommunVente(double niveau)
  {
   double distMin = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
   double ask     = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   if(niveau < ask + distMin) niveau = ask + distMin;   // le SL d'une vente est AU-DESSUS du prix
   niveau = NormalizeDouble(niveau, _Digits);
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != NumeroMagique) continue;
      if(PositionGetInteger(POSITION_TYPE) != POSITION_TYPE_SELL) continue;   // S2
      double slActuel = PositionGetDouble(POSITION_SL);
      // Miroir de L8+-R9 : le stop ne fait que DESCENDRE, par pas utiles.
      // slActuel <= 0 (position sans SL) : on pose le stop sans condition —
      // sinon le test « niveau < 0 - pasMin » ne serait jamais vrai et une
      // vente orpheline resterait sans stop pour toujours.
      double pasMin = ask * PasMinStopPct / 100.0;
      if(slActuel <= 0 || niveau < slActuel - pasMin)
         trade.PositionModify(ticket, niveau, PositionGetDouble(POSITION_TP));
     }
  }

//+------------------------------------------------------------------+
//| S2 : gestion d'une pile vendeuse (miroir exact du bloc achat      |
//| d'OnTick : rachat canal haut, pyramide vers le bas, stop commun). |
//+------------------------------------------------------------------+
void GererPositionVente(double declencheur, double hautCanalVente)
  {
   // rachat : cloture au-dessus du canal HAUT (PeriodeSortie jours) —
   // miroir exact de « declencheur < basCanal » cote achat
   if(declencheur > hautCanalVente)
     {
      FermerPositions(false);
      return;
     }
   // --- pyramide symetrique (Turtles, miroir) + stop commun ----------
   double atrPyr[];
   ArraySetAsSeries(atrPyr, true);
   double atrVal = 0.0;
   if(CopyBuffer(hAtr, 0, 1, 1, atrPyr) >= 1) atrVal = atrPyr[0];

   int    unites  = NombreUnites();
   double dernier = PrixDerniereUniteVente();
   double basDecision = iLow(_Symbol, UT_Decision, 1);

   MqlDateTime tvS;
   TimeToStruct(TimeCurrent(), tvS);
   bool ajoutBloqueVendredi = (GardeVendrediActif && tvS.day_of_week == 5);   // L8C : vaut aussi pour la pyramide vendeuse
   // 1) ajout d'une unite quand le prix a PROGRESSE VERS LE BAS de
   //    PasUniteATR depuis la derniere unite (une seule unite par bougie)
   if(PyramidageActif && !ajoutBloqueVendredi && unites > 0 && unites < MaxUnites && atrVal > 0 && dernier > 0 && basDecision > 0)
     {
      double seuilAjout = dernier - PasUniteATR * atrVal;
      if(basDecision <= seuilAjout && ComptePositionsEcurie() < MaxPositionsEcurie)
        {
         double lotAjout = LotSelonPlafondNotionnel(LotSelonMarge(LotUniteVente(), true));
         if(HeatEcurieBloque(RisqueParTradePct * FacteurTurbo())) lotAjout = 0.0;   // S2 : budget d'ecurie
         if(lotAjout <= 0)
            Notifier("S2 : unite de pyramide VENTE refusee (marge, notionnel ou heat)");
         else
           {
            double slProvisoire = NormalizeDouble(hautCanalVente, _Digits);
            if(trade.Sell(lotAjout, _Symbol, 0.0, slProvisoire, 0.0,
                          "S2 vente unite " + (string)(unites + 1) + "/" + (string)MaxUnites))
              {
               Notifier(StringFormat("PYRAMIDE VENTE unite %d/%d : +%.2f lot @ %.2f",
                        unites + 1, MaxUnites, lotAjout,
                        SymbolInfoDouble(_Symbol, SYMBOL_BID)));
               unites  = NombreUnites();
               dernier = PrixDerniereUniteVente();
              }
           }
        }
     }

   // 2) stop commun : le plus BAS entre le canal haut et
   //    (derniere unite + StopSousDerniereUniteATR x ATR)
   double niveauStop = hautCanalVente;
   if(PyramidageActif && unites > 1 && atrVal > 0 && dernier > 0)
     {
      double stopTurtle = dernier + StopSousDerniereUniteATR * atrVal;
      if(stopTurtle < niveauStop) niveauStop = stopTurtle;
     }
   niveauStop = AppliquerBreakevenCollectifVente(niveauStop, dernier);
   AppliquerStopCommunVente(niveauStop);
  }

//+------------------------------------------------------------------+
//| S2 : entree VENTE — miroir du signal d'achat, derriere le filtre  |
//| de regime. Appelee seulement quand aucune position n'existe et    |
//| qu'aucun achat ne vient d'ouvrir (jamais long ET court).          |
//+------------------------------------------------------------------+
void TenterEntreeVente(double declencheur, double basCanalVente, double hautCanalVente)
  {
   if(!VenteActive) return;
   if(declencheur <= 0 || basCanalVente <= 0 || hautCanalVente <= 0) return;
   // signal : cloture sous canal_bas x (1 - tampon) — tampon miroir L4.31
   if(declencheur >= basCanalVente * (1.0 - TamponCassurePct / 100.0)) return;
   // filtre de regime : signal present mais filtre desarme -> journalise
   if(!VenteArmee()) { EcrireJournal("refus=vad_desarmee"); return; }
   if(!EnSaison()) { EcrireJournal("refus=hors_saison"); return; }
   if(BloqueParNouvelles()) { EcrireJournal("refus=fenetre_annonce"); return; }
   if(ComptePositionsEcurie() >= MaxPositionsEcurie) { EcrireJournal("refus=plafond_ecurie"); return; }
   if(FamilleCorreleeOccupee()) { EcrireJournal("refus=famille_correlee"); return; }
   double prixVente  = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double distanceSL = hautCanalVente - prixVente;   // le stop d'une vente est AU-DESSUS du prix
   if(distanceSL <= 0 || distanceSL > 0.50 * prixVente) return;   // meme garde-fou que l'achat
   double lot = LotSelonPlafondNotionnel(CalculerLot(distanceSL, true));
   if(lot <= 0) return;
   double spreadCourant = SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(SpreadEntreeMaxPct > 0 && spreadCourant > SpreadEntreeMaxPct / 100.0 * distanceSL)
     {
      Print("S2 : entree vente reportee, spread ", DoubleToString(spreadCourant, _Digits),
            " > ", DoubleToString(SpreadEntreeMaxPct, 1), " % de la distance de stop");
      return;
     }
   if(HeatEcurieBloque(RisqueParTradePct * FacteurTurbo())) return;   // S2 : budget d'ecurie, cote vendeur aussi
   double sl = NormalizeDouble(hautCanalVente, _Digits);
   trade.Sell(lot, _Symbol, 0.0, sl, 0.0, "S2 vente cassure 20j");
   // S2.1 : une attente de repli ACHAT qui hibernerait pendant la vie
   // de la vente se reveillerait des semaines plus tard avec un niveau
   // et un stop perimes. On la desarme.
   DesarmerRepli("vente ouverte : attente d'achat annulee");
  }
//+------------------------------------------------------------------+
