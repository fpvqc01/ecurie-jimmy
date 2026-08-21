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

input double RisqueParTradePct    = 1.13;  // L6+ : allocation a x0,75 (etait 1,5)   // parite de risque validee 10 ans (etait 0.75)   // Risque par trade en % du solde (I2 : x1.5)
input double FacteurRisqueGlobal     = 1.0;   // L6+ : multiplicateur global (mettre 1.33 une fois finance, gardien fixe -2,5)
input double SpreadEntreeMaxPct      = 2.0;   // L6+ : entree reportee si le spread depasse ce % de la distance de stop (0 = off)
input bool   TurboCoussinActif     = true;   // L6+ : x TurboMultiplicateur tant que le coussin n'est pas fait, puis x1,0
input double TurboMultiplicateur   = 1.33;   // L6+ : multiplicateur de risque avant le coussin (banc : 78 % / 109 j)
input double TurboCoussinPct       = 4.0;    // L6+ : coussin (en % au-dessus de la baseline) qui coupe le turbo
input ENUM_TIMEFRAMES UT_Decision    = PERIOD_D1; // L4.3 : une decision par jour (valide walk-forward)
input ENUM_TIMEFRAMES UT_Indicateurs = PERIOD_D1; // L4.3 : EMA/ATR journaliers
input int             HeureDecision  = 8;         // L6+F : heure serveur de la decision D1 (evite le spread du rollover de minuit)
input double LimitePerteJourPct   = 2.5;    // L3 : resserre (valide 19 aout ; FTMO = 5)
input double LimitePerteTotalePct = 8.0;    // Coupe-circuit perte totale en %
input int    EMARapide            = 20;
input int    EMALente             = 50;
input int    PeriodeATR           = 14;
input double MultiplicateurSL     = 2.0;    // Stop = 2 x ATR (= 1R)
input double MultiplicateurTP     = 4.0;    // TP = 4 x ATR (= 2R, ~1000 $) (I2)
input double RetraceReentreeATR   = 0.25;   // Ré-entrée après repli de N x ATR sous le prix de sortie TP (I2)
input int    MaxPositionsEcurie   = 2;      // Plafond global de positions de l'écurie (I2)
input long   NumeroMagique        = 20261115;
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
input bool   ModeChallengeActif = false; // SANS mode challenge (variante MT6)
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

double   attenteReentree = 0;   // prix de sortie TP ; 0 = pas de ré-entrée en attente

string BaseGV() { return "MACROBOT_BASE_" + (string)AccountInfoInteger(ACCOUNT_LOGIN); }

//+------------------------------------------------------------------+
//| L6+ : turbo-coussin — x1,33 tant que l'equite n'a pas +4 % au-   |
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
   if(!SendNotification("[L6+SC] BTC bot : " + msg) && !avertiEchec)
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
//| MQL6+\Files\Ecurie_Journal\<robot>.txt (lisible au Bloc-notes)    |
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
   Print("L6+ turbo-coussin | actif=", TurboCoussinActif, " mult=", TurboMultiplicateur, " coussin=+", TurboCoussinPct, "%");
   Print("L6+ charge | decision=", EnumToString(UT_Decision), " indicateurs=", EnumToString(UT_Indicateurs), " heureDecision=", HeureDecision, "h");
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
      GlobalVariableSet(BaseGV(), AccountInfoDouble(ACCOUNT_BALANCE));

   Print("BTCUSD_EMA_L43_D1 démarré. Baseline = ", DoubleToString(GlobalVariableGet(BaseGV()), 2),
         " | TP 2R, ré-entrée ", DoubleToString(RetraceReentreeATR, 2),
         "xATR, plafond écurie ", MaxPositionsEcurie);
   EventSetTimer(60);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnTimer()
  {
   ReleverEquite();
   LireFacteurVol();
   if(facteurVol > 1.0) facteurVol = 1.0;   // L6+ : jamais amplifier, challenge ou pas

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

   long modifBias = (long)FileGetInteger("macrobot_bias.txt", FILE_MODIFY_DATE);   // L6+
   if(modifBias > 0 && TimeCurrent() - (datetime)modifBias > 7 * 86400)
     { biaisMacroOK = AchatPermisSansFichier; return(biaisMacroOK); }   // L6+ : perime -> neutre
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

   long modifNews = (long)FileGetInteger("macrobot_news.txt", FILE_MODIFY_DATE);   // L6+
   if(modifNews > 0 && TimeCurrent() - (datetime)modifNews > 7 * 86400)
     { ArrayResize(newsEpochs, 0); return; }   // L6+ : fichier perime -> neutre
   int fh = FileOpen("macrobot_news.txt", FILE_READ | FILE_TXT | FILE_ANSI);
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
   if(valeurTick <= 0 || tailleTick <= 0 || distanceSL <= 0) return(0);

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
   double distanceSL = atrVal * MultiplicateurSL;
   double distanceTP = atrVal * MultiplicateurTP;
   if(distanceSL <= 0) return;
   double lot = CalculerLot(distanceSL);
   if(lot <= 0) return;
   double spreadCourant = SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID);   // L6+
   if(SpreadEntreeMaxPct > 0 && spreadCourant > SpreadEntreeMaxPct / 100.0 * distanceSL)
     {
      Print("L6+ : entree reportee, spread ", DoubleToString(spreadCourant, _Digits), " > ", DoubleToString(SpreadEntreeMaxPct, 1), " % de la distance de stop");
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
   if(UT_Decision == PERIOD_D1 && tvF.hour < HeureDecision) return;   // L6+F : on decide a 08:00, pas au rollover
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
      (newsBloquaitAvant ? "FENETRE ANNONCE" : "libre"), facteurVol, (attenteReentree > 0 ? "OUI" : "non")));

   // régime baissier : fermeture éventuelle + annulation de la ré-entrée
   if(!haussier)
     {
      attenteReentree = 0;
      if(croisementBaissier && PositionActuelle() == 1)
         FermerPositions(false);
      return;
     }

   if(PositionActuelle() != 0) return;
   if(!macroPermis) return;
   if(ComptePositionsEcurie() >= MaxPositionsEcurie) return;
   if(FamilleCorreleeOccupee()) return;   // plafond de correlation   // plafond d'écurie (I2)

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
