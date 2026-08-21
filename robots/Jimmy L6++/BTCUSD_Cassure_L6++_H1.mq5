//+------------------------------------------------------------------+
//|                                             BTCUSD_Cassure_L43_H1.mq5 |
//|  Cassure Donchian 20/10 JOURS sur BTC, achat seulement (L4.31).  |
//|  Graphique SANS importance (canaux journaliers, decision H1).    |
//|                                                                  |
//|  Entree  : barre H1 fermee > plus haut 20 JOURS + tampon 0,25 %  |
//|  Sortie  : stop suiveur sous le plus bas 10 JOURS (+ pyramide 4) |
//|  Valide avec les frais reels FTMO (commission 0.065% A/R +       |
//|  swap -30%/an). Config L4.31 validee walk-forward 2021-2026.     |
//|                                                                  |
//|                                                                  |
//|  Partage les protections FTMO (variables MACROBOT_*), le biais   |
//|  macro BIS et le filtre d'annonces avec les autres robots.       |
//|  Magic distinct : ne touche jamais aux trades du bot EMA H1.     |
//+------------------------------------------------------------------+
#property copyright "Jimmy"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

input double RisqueParTradePct    = 1.69;  // L6++ : allocation a x0,75 (etait 1,5)   // parite de risque validee 10 ans (etait 0.75)   // Risque par trade en % du solde (I2 : x1.5)
input double FacteurRisqueGlobal     = 1.0;   // L6++ : multiplicateur global (mettre 1.33 une fois finance, gardien fixe -2,5)
input double SpreadEntreeMaxPct      = 2.0;   // L6++ : entree reportee si le spread depasse ce % de la distance de stop (0 = off)
input bool   TurboCoussinActif     = false;  // L6++ : turbo OFF par defaut (la combinaison turbo + breakeven n'est PAS backtestee)   // L6++ : x TurboMultiplicateur tant que le coussin n'est pas fait, puis x1,0
input double TurboMultiplicateur   = 1.33;   // L6++ : multiplicateur de risque avant le coussin (banc : 78 % / 109 j)
input double TurboCoussinPct       = 4.0;    // L6++ : coussin (en % au-dessus de la baseline) qui coupe le turbo
input double LimitePerteJourPct   = 2.5;    // L3 : resserre (valide 19 aout ; FTMO = 5)
input double LimitePerteTotalePct = 8.0;    // Coupe-circuit perte totale en % (FTMO = 10)
input int    PeriodeEntree        = 20;     // L4.3 corrige : canal 20 JOURS (config validee walk-forward ; etait 55 bougies H4)
input int    PeriodeSortie        = 10;     // L4.3 corrige : sortie 10 JOURS (etait 20 bougies H4)
input int    PeriodeATR           = 14;     // ATR (protection annonces)
input long   NumeroMagique        = 20261117; // Identifiant distinct du bot EMA
input int    MaxPositionsEcurie   = 2;      // Plafond global de positions de l'ecurie (I2)
input bool   BiaisMacroDepuisFichier = true; // biais BIS (macrobot_bias.txt, relu chaque minute)
input bool   AchatPermisSansFichier  = true; // fichier absent -> achats permis quand meme ?
input bool   FiltreNouvellesActif    = true; // bloquer les entrees autour des annonces USD
input int    MinutesBlocageAvantNews = 30;
input int    MinutesBlocageApresNews = 30;

enum ENUM_PROTECTION_NEWS
  {
   PROTECTION_AUCUNE = 0,   // ne rien faire sur les positions ouvertes
   PROTECTION_SERRER = 1,   // serrer les stops pendant la fenetre d'annonce (recommande)
   PROTECTION_FERMER = 2    // fermer les positions avant l'annonce
  };
input ENUM_PROTECTION_NEWS ProtectionPositionsNews = PROTECTION_SERRER;
input bool   FacteurVolActif       = true; // moduler le risque selon la volatilite des marches (L3)
input bool   PyramidageActif    = true;  // L3 : ajouter des unites sur un trade gagnant (Turtles)
input int    MaxUnites          = 4;     // L4.2 : pyramide 4 (valide 21 aout, +2 pts H4 10 ans)
input ENUM_TIMEFRAMES UT_Decision    = PERIOD_H1; // L4.3 : cadence de decision (valide walk-forward)
input double TamponCassurePct = 0.25; // L4.31 : entree seulement si cassure > canal + X % (plateau 0,15-0,30 valide)
input double PasUniteATR        = 0.5;   // L3 : ajouter une unite chaque +N x ATR
input double StopSousDerniereUniteATR = 2.0; // L3 : stop commun a N x ATR sous la derniere unite
input bool   BreakevenCollectifActif = true;  // L6++ : proteger le point mort quand la pyramide est pleine
input double BreakevenCollectifPct   = 5.0;   // L6++ : seuil de profit du trade qui arme la protection (plateau 5-9 ; 6.0 = 13 jours de moins)
input bool   JournalActif          = true; // journal de reflexion (Files\Ecurie_Journal)
input bool   PlafondCorrelationActif = true;  // un seul metal/indice a la fois (crises)
input bool   ModeChallengeActif = true;  // L4 : ACTIF par defaut (valide scan 21 aout, 2 moteurs)
input double ThrottleChallenge  = 0.75;  // L3+ : facteur sous la moyenne 20 j
input bool   NotificationsPush       = true; // push cellulaire (MetaQuotes ID)

CTrade   trade;
int      hAtr = INVALID_HANDLE;
datetime derniereBarre = 0;
datetime derniereLectureBiais = 0;
bool     biaisMacroOK = true;
datetime derniereLectureNews = 0;
long     newsEpochs[];
bool     newsBloquaitAvant = false;
datetime derniereLectureVol = 0;
double   facteurVol = 1.0;


string BaseGV() { return "MACROBOT_BASE_" + (string)AccountInfoInteger(ACCOUNT_LOGIN); }

//+------------------------------------------------------------------+
//| L6++ : turbo-coussin — x1,33 tant que l'equite n'a pas +4 % au-   |
//| dessus de la baseline de la phase, puis retour au risque normal. |
//+------------------------------------------------------------------+
double FacteurTurbo()
  {
   if(!TurboCoussinActif) return 1.0;
   if(!GlobalVariableCheck(BaseGV())) return 1.0;
   double basePhase = GlobalVariableGet(BaseGV());
   if(basePhase <= 0) return 1.0;
   if(AccountInfoDouble(ACCOUNT_EQUITY) >= basePhase * (1.0 + TurboCoussinPct / 100.0))
      return 1.0;   // coussin fait : on finit au risque normal
   return TurboMultiplicateur;
  }
string HaltGV() { return "MACROBOT_HALT_" + (string)AccountInfoInteger(ACCOUNT_LOGIN); }
string LastEqGV() { return "MACROBOT_LASTEQ_" + (string)AccountInfoInteger(ACCOUNT_LOGIN); }   // L4.32 : equite d'avant le gap
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
   if(!SendNotification("[L6++] BTC breakout : " + msg) && !avertiEchec)
     {
      Print("Push non envoye. Configure ton MetaQuotes ID : Outils > Options > Notifications.");
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
      Notifier(StringFormat("ENTRÉE cassure %.2f lot @ %s", vol, DoubleToString(prix, _Digits)));
   else if(sens == DEAL_ENTRY_OUT)
      Notifier(StringFormat("SORTIE %.2f lot @ %s | P/L: %.2f $", vol,
                            DoubleToString(prix, _Digits),
                            HistoryDealGetDouble(trans.deal, DEAL_PROFIT)));
  }


//+------------------------------------------------------------------+
//| Journal de reflexion : une ligne par bougie dans                 |
//| MQL6++\Files\Ecurie_Journal\<robot>.txt (lisible au Bloc-notes)    |
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
   Print("L6++ turbo-coussin | actif=", TurboCoussinActif, " mult=", TurboMultiplicateur, " coussin=+", TurboCoussinPct, "%");
   Print("L6++ charge | decision=", EnumToString(UT_Decision), " canaux=D1 tampon=", TamponCassurePct, "%");
   Print("L6++ breakeven collectif | actif=", BreakevenCollectifActif, " seuil=+", BreakevenCollectifPct, "%");
   Print("L6++ charge | PyramideMax=", MaxUnites, " ModeChallenge=", ModeChallengeActif);
   trade.SetExpertMagicNumber(NumeroMagique);
   trade.SetDeviationInPoints(50);

   hAtr = iATR(_Symbol, PERIOD_D1, PeriodeATR);   // L4.3 : ATR journalier
   if(hAtr == INVALID_HANDLE)
     {
      Print("Erreur : impossible de creer l'ATR.");
      return(INIT_FAILED);
     }

   if(false)   // L4.3 : le graphique n'a plus d'importance
      Print("ATTENTION : strategie calibree en H4, graphique actuel : ", EnumToString(_Period));

   if(!GlobalVariableCheck(BaseGV()))
      GlobalVariableSet(BaseGV(), AccountInfoDouble(ACCOUNT_BALANCE));

   Print("BTCUSD_Cassure_L43_H1 démarré. Baseline challenge = ",
         DoubleToString(GlobalVariableGet(BaseGV()), 2));

   EventSetTimer(60);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnTimer()
  {
   ReleverEquite();
   LireNouvelles();
   LireFacteurVol();
   if(facteurVol > 1.0) facteurVol = 1.0;   // L6++ : jamais amplifier, challenge ou pas
   BiaisMacroPermis();
   BloqueParNouvelles();
   ProtegerPositionsNews();
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   if(hAtr != INVALID_HANDLE) IndicatorRelease(hAtr);
  }

//+------------------------------------------------------------------+
//| Ferme les positions de CE robot (magic 20261117).                |
//| toutLeCompte=true : tous les symboles (urgence gardien)          |
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
//| Coupe-circuits FTMO partages (chaque robot surveille l'equite    |
//| du compte entier et ferme ses propres positions en cas d'alerte) |
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
bool BiaisMacroPermis()
  {
   if(!BiaisMacroDepuisFichier) return(true);
   if(TimeCurrent() - derniereLectureBiais < 60) return(biaisMacroOK);
   derniereLectureBiais = TimeCurrent();

   long modifBias = (long)FileGetInteger("macrobot_bias.txt", FILE_MODIFY_DATE);   // L6++
   if(modifBias > 0 && TimeCurrent() - (datetime)modifBias > 7 * 86400)
     { biaisMacroOK = AchatPermisSansFichier; return(biaisMacroOK); }   // L6++ : perime -> neutre
   int fh = FileOpen("macrobot_bias.txt", FILE_READ | FILE_TXT | FILE_ANSI);
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

   long modifNews = (long)FileGetInteger("macrobot_news.txt", FILE_MODIFY_DATE);   // L6++
   if(modifNews > 0 && TimeCurrent() - (datetime)modifNews > 7 * 86400)
     { ArrayResize(newsEpochs, 0); return; }   // L6++ : fichier perime -> neutre
   int fh = FileOpen("macrobot_news.txt", FILE_READ | FILE_TXT | FILE_ANSI);
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
   int fh = FileOpen("macrobot_vol.txt", FILE_READ | FILE_TXT | FILE_ANSI);
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

void ReleverEquite()
  {
   datetime jour = iTime(_Symbol, PERIOD_D1, 0);
   if(jour == dernierReleve) return;
   dernierReleve = jour;
   HistoEquite[HistoIndex] = AccountInfoDouble(ACCOUNT_EQUITY);
   HistoIndex = HistoIndex + 1;
   if(HistoIndex >= 20) { HistoIndex = 0; HistoPlein = true; }
  }

double FacteurChallenge()
  {
   if(!ModeChallengeActif || !HistoPlein) return(1.0);
   double somme = 0;
   for(int i = 0; i < 20; i++) somme += HistoEquite[i];
   double moyenne = somme / 20.0;
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

   double risqueArgent = AccountInfoDouble(ACCOUNT_BALANCE) * RisqueParTradePct / 100.0 * facteurVol * FacteurRisqueGlobal * FacteurTurbo() * FacteurChallenge();
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
      Print("Lot calculé trop petit (", DoubleToString(lot, 4), " < ",
            DoubleToString(lotMin, 4), "). Trade annulé pour respecter le risque.");
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
//| L6++ : prix d'entree MOYEN des unites = (premiere + derniere)/2, |
//| exactement la formule validee au banc give-back du 21 aout.      |
//+------------------------------------------------------------------+
double PrixPremiereUnite()   // prix d'ouverture le plus BAS = 1re unite
  {
   double p = 0.0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != NumeroMagique) continue;
      double po = PositionGetDouble(POSITION_PRICE_OPEN);
      if(p == 0.0 || po < p) p = po;
     }
   return(p);
  }

//| Remonte le niveau de stop au point mort collectif si le trade a  |
//| depasse le seuil de profit. Ne fait JAMAIS descendre le stop.    |
double AppliquerBreakevenCollectif(double niveau, double dernier)
  {
   if(!BreakevenCollectifActif || BreakevenCollectifPct <= 0) return(niveau);
   double premiere = PrixPremiereUnite();
   if(premiere <= 0 || dernier <= 0) return(niveau);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(bid <= 0) return(niveau);
   double gain = (bid - premiere) / premiere;
   if(gain < BreakevenCollectifPct / 100.0) return(niveau);
   double moyen = (premiere + dernier) / 2.0;
   if(moyen > niveau)
     {
      static datetime dernierAvis = 0;
      if(TimeCurrent() - dernierAvis > 3600)
        {
         dernierAvis = TimeCurrent();
         Print("L6++ breakeven collectif arme : gain ", DoubleToString(gain * 100, 2),
               " % -> stop remonte au point mort ", DoubleToString(moyen, _Digits));
        }
      return(moyen);
     }
   return(niveau);
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
      if(niveau > slActuel + _Point)      // le stop ne fait que monter
         trade.PositionModify(ticket, niveau, PositionGetDouble(POSITION_TP));
     }
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   if(!VerifierProtections()) return;

   LireNouvelles();
   LireFacteurVol();
   if(facteurVol > 1.0) facteurVol = 1.0;   // L6++ : jamais amplifier, challenge ou pas
   bool macroPermis = BiaisMacroPermis() && !BloqueParNouvelles();
   ProtegerPositionsNews();

   // une decision par bougie H4 fermee
   datetime barreActuelle = iTime(_Symbol, UT_Decision, 0);   // L4.3
   if(barreActuelle == derniereBarre) return;
   derniereBarre = barreActuelle;

   int besoin = MathMax(PeriodeEntree, PeriodeSortie) + 2;
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, PERIOD_D1, 0, besoin, rates) < besoin) return;   // L4.3 : canaux journaliers
   double declencheur  = iClose(_Symbol, UT_Decision, 1);   // L4.3 : barre de decision fermee
   double hautDecision = iHigh(_Symbol, UT_Decision, 1);
   if(declencheur <= 0 || hautDecision <= 0) return;

   // canaux calcules sur les bougies AVANT la bougie signal (index 1)
   double hautCanal = rates[1].high;   // L4.3 (corrige 20 aout : la veille fait partie du canal)
   for(int i = 2; i <= PeriodeEntree; i++)
      if(rates[i].high > hautCanal) hautCanal = rates[i].high;
   double basCanal = rates[1].low;   // L4.3
   for(int i = 2; i <= PeriodeSortie; i++)
      if(rates[i].low < basCanal) basCanal = rates[i].low;

   EcrireJournal(StringFormat("cloture=%.2f | canal_haut=%.2f (dist %.2f%%) | canal_bas=%.2f | position=%s | macro=%s | news=%s | facteurVol=%.2f",
      declencheur, hautCanal, (hautCanal - declencheur) / declencheur * 100.0, basCanal,
      (PositionOuverte() ? (StringFormat("OUVERTE %d unite(s)", NombreUnites())) : "aucune"), (biaisMacroOK ? "OK" : "BLOQUE"),
      (newsBloquaitAvant ? "FENETRE ANNONCE" : "libre"), facteurVol));
   if(PositionOuverte())
     {
      // sortie : cloture sous le canal bas, sinon stop suiveur remonte
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
      if(PyramidageActif && unites > 0 && unites < MaxUnites && atrVal > 0 && dernier > 0)
        {
         double seuilAjout = dernier + PasUniteATR * atrVal;
         if(hautDecision >= seuilAjout && ComptePositionsEcurie() <= MaxPositionsEcurie)
           {
            double lotAjout = LotUnite();
            if(lotAjout > 0)
              {
               double slProvisoire = NormalizeDouble(basCanal, _Digits);
               if(trade.Buy(lotAjout, _Symbol, 0.0, slProvisoire, 0.0,
                            "L6++ unite " + (string)(unites + 1) + "/" + (string)MaxUnites))
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
      niveauStop = AppliquerBreakevenCollectif(niveauStop, dernier);   // L6++
      AppliquerStopCommun(niveauStop);
      return;
     }

   // entree : cassure du canal haut, si la macro le permet
   if(!macroPermis) return;
   if(declencheur <= hautCanal * (1.0 + TamponCassurePct / 100.0)) return;   // L4.31 tampon anti-faux-signal
   if(ComptePositionsEcurie() >= MaxPositionsEcurie) return;
   if(FamilleCorreleeOccupee()) return;   // plafond de correlation // plafond d'ecurie (I2)

   double prix = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double distanceSL = prix - basCanal;
   if(distanceSL <= 0 || distanceSL > 0.50 * prix) return; // garde-fou : risque > 50 % du prix = aberrant   // L6++ : commentaire aligne sur le code
   double lot = CalculerLot(distanceSL);
   if(lot <= 0) return;
   double spreadCourant = SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID);   // L6++
   if(SpreadEntreeMaxPct > 0 && spreadCourant > SpreadEntreeMaxPct / 100.0 * distanceSL)
     {
      Print("L6++ : entree reportee, spread ", DoubleToString(spreadCourant, _Digits), " > ", DoubleToString(SpreadEntreeMaxPct, 1), " % de la distance de stop");
      return;
     }


   double sl = NormalizeDouble(basCanal, _Digits);
   trade.Buy(lot, _Symbol, 0.0, sl, 0.0, "L6++ cassure 20j");
  }
//+------------------------------------------------------------------+
