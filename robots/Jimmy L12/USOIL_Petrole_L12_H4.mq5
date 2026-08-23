//+------------------------------------------------------------------+
//|                                           USOIL_Petrole_L43_H4.mq5 |
//|  Cassure Donchian 20/10 JOURNALIER sur le pétrole WTI,           |
//|  achat seulement, ACTIVE SEULEMENT EN SAISON (déc -> mai :       |
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
input bool   TurboCoussinActif   = true;   // L12 : risque x TurboMultiplicateur tant que le coussin de phase n'est pas fait
input double TurboMultiplicateur = 1.15;   // L12 : plateau verifie 1,15-1,33 ; 1,15 est le meilleur point (falaise a 1,50)
input double TurboCoussinPct     = 4.0;    // L12 : coussin, en % au-dessus de la baseline, qui coupe le turbo
input bool   ReplyActif          = true;   // L12 : ne pas acheter le sommet de la cassure quand la tendance est molle
input double ReplyATR            = 1.25;   // L12 : profondeur du repli attendu, en ATR journalier (plateau 0,75-1,25)
input int    ReplyFenetre        = 5;      // L12 : validite de l'attente, en barres de decision
input double ReplySeuilForce     = 1.00;   // L12 : (prix - EMA50) / ATR au-dela duquel on prend la cassure tout de suite
input double SpreadEntreeMaxPct      = 2.0;   // L8 : entree reportee si le spread depasse ce % de la distance de stop (0 = off)
input double LimitePerteJourPct   = 2.50;  // L11 : rendu a 2,50 % - la deconcentration du BTC a traite la cause (banc L11 : -41 a -75 jours, reussite inchangee)    // L3 : resserre (valide 19 aout ; FTMO = 5)
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
input int    MoisDebutSaison      = 12;     // Saison favorable : début (mois)
input int    JourDebutSaison      = 1;      //   ... jour
input int    MoisFinSaison        = 5;      // Saison favorable : fin (mois)
input int    JourFinSaison        = 31;     //   ... jour
input int    PeriodeATR           = 14;     // ATR journalier (protection annonces)
input long   NumeroMagique        = 20261118; // Identifiant distinct
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
input bool   BreakevenCollectifActif = true;   // L8-R2 : protege le point mort quand le trade est bien en profit
input double BreakevenCollectifPct   = 5.0;    // L8-R2 : seuil de profit qui arme la protection
input double PlafondNotionnelEquite  = 1.25;   // L8-R3 : notionnel max de cette manche, en multiple de l'equite (0 = aucun)
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
   if(!TurboCoussinActif) return(1.0);
   if(!GlobalVariableCheck(BaseGV())) return(1.0);
   double basePhase = GlobalVariableGet(BaseGV());
   if(basePhase <= 0) return(1.0);
   if(AccountInfoDouble(ACCOUNT_EQUITY) >= basePhase * (1.0 + TurboCoussinPct / 100.0))
      return(1.0);
   return(TurboMultiplicateur);
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
      if(m != 20260815 && m != 20260817 && m != 20260818 &&
         m != 20261115 && m != 20261117 && m != 20261118) continue;
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
      if(m != 20261115 && m != 20261117 && m != 20261118) continue;
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
   Print("L12 charge | decision=", EnumToString(UT_Decision), " canaux=D1 tampon=", TamponCassurePct, "%");
   Print("L12 | gardien=", LimitePerteJourPct, "% breakeven=+", BreakevenCollectifPct, "% notionnelMax=", PlafondNotionnelEquite, "x equite");
   Print("L12 charge | PyramideMax=", MaxUnites, " GardeVendredi=", GardeVendrediActif, " ModeChallenge=", ModeChallengeActif);
   trade.SetExpertMagicNumber(NumeroMagique);
   trade.SetDeviationInPoints(50);

   hAtr = iATR(_Symbol, PERIOD_D1, PeriodeATR);
   hEma50 = iMA(_Symbol, PERIOD_D1, 50, 0, MODE_EMA, PRICE_CLOSE);   // L12
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
   if(fh == INVALID_HANDLE) { facteurVol = 1.0; return; }
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
   return(LotSelonMarge(lot));
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

   EcrireJournal(StringFormat("cloture=%.2f | canal_haut=%.2f (dist %.2f%%) | canal_bas=%.2f | saison=%s | position=%s | news=%s | facteurVol=%.2f",
      declencheur, hautCanal, (hautCanal - declencheur) / declencheur * 100.0, basCanal,
      (EnSaison() ? "FAVORABLE" : "hors saison"), (PositionOuverte() ? (StringFormat("OUVERTE %d unite(s)", NombreUnites())) : "aucune"),
      (newsBloquaitAvant ? "FENETRE ANNONCE" : "libre"), facteurVol));
   if(PositionOuverte())
     {
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
            double lotAjout = LotSelonPlafondNotionnel(LotSelonMarge(LotUnite()));   // L8-R3/R11
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

   // entrée : cassure du canal haut, EN SAISON seulement, hors annonces
   if(!EnSaison()) return;
   if(!newsOK) return;
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

   if(ComptePositionsEcurie() >= MaxPositionsEcurie) return;
   if(FamilleCorreleeOccupee()) return;   // plafond de correlation // plafond d'ecurie (I2)

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


   double sl = NormalizeDouble(basCanal, _Digits);
   trade.Buy(lot, _Symbol, 0.0, sl, 0.0, "USOIL_Breakout saison");
  }
//+------------------------------------------------------------------+
