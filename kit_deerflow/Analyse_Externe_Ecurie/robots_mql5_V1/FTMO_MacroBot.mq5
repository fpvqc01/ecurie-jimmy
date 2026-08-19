//+------------------------------------------------------------------+
//| FTMO_MacroBot.mq5                                                |
//| Strategie macro or / US100 avec gardien de risque FTMO.          |
//|                                                                  |
//| - A attacher sur un graphique H4 (XAUUSD ou US100/NAS100).       |
//| - Long-only : le biais macro (taux reels US pour l'or, posture   |
//|   Fed pour le Nasdaq) se met a jour ~1x/mois via l'input         |
//|   MacroLongAllowed (ou le fichier bias si BiasFromFile=true).    |
//| - Entree : pullback fib du dernier swing haussier + RSI qui      |
//|   redemarre. Stop ATR, objectif en multiples de R.               |
//| - GARDIEN FTMO : coupe tout a -DailyStopPct% dans la journee     |
//|   (marge sous la limite officielle de 5%) et arrete              |
//|   definitivement a -TotalStopPct% (limite officielle 10%).       |
//+------------------------------------------------------------------+
#property copyright "Macro Bot"
#property version   "1.00"

#include <Trade\Trade.mqh>

enum ENUM_PRESET
  {
   PRESET_GOLD,    // Or (XAUUSD)
   PRESET_NASDAQ   // US100 / NAS100
  };

input ENUM_PRESET Preset             = PRESET_GOLD;
input bool   MacroLongAllowed        = true;   // biais macro long (maj ~1x/mois)
input bool   BiasFromFile            = false;  // lire le biais dans MQL5\Files\macrobot_bias.txt
input double RiskPerTradePct         = 1.0;    // % d'equity risque par trade
input double DailyStopPct            = 3.5;    // coupure quotidienne (FTMO: 5%)
input double TotalStopPct            = 8.0;    // coupure definitive (FTMO: 10%)
input double ChallengeInitialBalance = 0;      // 0 = balance au 1er lancement
input long   MagicNumber             = 20260815;
input bool   NewsFilterOn            = true;   // bloquer les entrees autour des annonces USD fort impact
input int    NewsMinutesAvant        = 30;     // minutes de blocage avant l'annonce
input int    NewsMinutesApres        = 30;     // minutes de blocage apres l'annonce

enum ENUM_NEWS_PROTECT
  {
   NEWS_PROTECT_RIEN   = 0,  // ne rien faire sur les positions ouvertes
   NEWS_PROTECT_SERRER = 1,  // serrer les stops pendant la fenetre d'annonce (recommande)
   NEWS_PROTECT_FERMER = 2   // fermer les positions avant l'annonce (le plus prudent)
  };
input ENUM_NEWS_PROTECT NewsProtectMode = NEWS_PROTECT_SERRER; // gestion des positions autour des annonces
input bool   PushNotifications       = true;   // notifications push sur le cellulaire (app MT5 mobile + MetaQuotes ID)
input bool   BreakevenActif          = true;   // stop remonte au prix d'entree des que le trade atteint +1R

CTrade   trade;
int      hATR = INVALID_HANDLE, hRSI = INVALID_HANDLE;
datetime lastBar = 0;
// cache des donnees externes, rafraichi chaque minute par OnTimer
bool     cacheBiasOK   = true;
bool     cacheNewsBloq = false;
bool     cacheInitFait = false;

// parametres de timing fixes par preset
int    SwingLookback;
double FibLo, FibHi, RsiPull, StopAtrMult, TpR;
int    RsiPeriod = 14, AtrPeriod = 14;

string BaseGV()  { return "MACROBOT_BASE_"  + (string)AccountInfoInteger(ACCOUNT_LOGIN); }
string HaltGV()  { return "MACROBOT_HALT_"  + (string)AccountInfoInteger(ACCOUNT_LOGIN); }

//+------------------------------------------------------------------+
//| Journal + notification push sur le cellulaire (si configuree)    |
//+------------------------------------------------------------------+
void Notifier(string msg)
  {
   Print(msg);
   if(!PushNotifications) return;
   static bool avertiEchec = false;
   if(!SendNotification(_Symbol + " : " + msg) && !avertiEchec)
     {
      Print("Push non envoye. Configure ton MetaQuotes ID : Outils > Options > Notifications.");
      avertiEchec = true;
     }
  }

//+------------------------------------------------------------------+
//| Notification a chaque transaction du robot (entree, sortie,      |
//| stop touche, take profit) — capte aussi les sorties serveur.     |
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result)
  {
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD) return;
   if(!HistoryDealSelect(trans.deal)) return;
   if(HistoryDealGetInteger(trans.deal, DEAL_MAGIC) != MagicNumber) return;
   if(HistoryDealGetString(trans.deal, DEAL_SYMBOL) != _Symbol) return;

   double vol  = HistoryDealGetDouble(trans.deal, DEAL_VOLUME);
   double prix = HistoryDealGetDouble(trans.deal, DEAL_PRICE);
   bool   achat = (HistoryDealGetInteger(trans.deal, DEAL_TYPE) == DEAL_TYPE_BUY);
   long   sens = HistoryDealGetInteger(trans.deal, DEAL_ENTRY);

   if(sens == DEAL_ENTRY_IN)
      Notifier(StringFormat("ENTREE %s %.2f lot @ %s", achat ? "achat" : "vente",
                            vol, DoubleToString(prix, _Digits)));
   else if(sens == DEAL_ENTRY_OUT)
      Notifier(StringFormat("SORTIE %.2f lot @ %s | P/L: %.2f $", vol,
                            DoubleToString(prix, _Digits),
                            HistoryDealGetDouble(trans.deal, DEAL_PROFIT)));
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   if(Preset == PRESET_GOLD)
     {
      SwingLookback = 60; FibLo = 0.20; FibHi = 0.80;
      RsiPull = 55.0; StopAtrMult = 3.0; TpR = 2.0;
     }
   else // PRESET_NASDAQ
     {
      SwingLookback = 40; FibLo = 0.10; FibHi = 0.90;
      RsiPull = 60.0; StopAtrMult = 2.0; TpR = 2.0;
     }

   if(_Period != PERIOD_H4)
      Print("ATTENTION: la strategie a ete calibree en H4, graphique actuel: ",
            EnumToString(_Period));

   hATR = iATR(_Symbol, _Period, AtrPeriod);
   hRSI = iRSI(_Symbol, _Period, RsiPeriod, PRICE_CLOSE);
   if(hATR == INVALID_HANDLE || hRSI == INVALID_HANDLE)
      return INIT_FAILED;

   trade.SetExpertMagicNumber(MagicNumber);

   // baseline du challenge (persistee entre les redemarrages)
   if(!GlobalVariableCheck(BaseGV()))
     {
      double base = (ChallengeInitialBalance > 0)
                    ? ChallengeInitialBalance
                    : AccountInfoDouble(ACCOUNT_BALANCE);
      GlobalVariableSet(BaseGV(), base);
     }
   Print("Baseline challenge: ", DoubleToString(GlobalVariableGet(BaseGV()), 2));

   // verification des donnees externes chaque minute, meme sans tick
   EventSetTimer(60);
   RafraichirDonneesExternes();
   return INIT_SUCCEEDED;
  }

//+------------------------------------------------------------------+
void OnTimer()
  {
   RafraichirDonneesExternes();
   ProtegerPositionsNews();   // serre les stops si une annonce approche, meme sans tick
  }

//+------------------------------------------------------------------+
//| Relit biais macro + calendrier chaque minute, log les changements|
//+------------------------------------------------------------------+
void RafraichirDonneesExternes()
  {
   bool b = MacroBias();
   bool n = NewsBlocks();
   if(cacheInitFait)
     {
      if(b != cacheBiasOK)
         Notifier(b ? "Biais macro : ACHATS PERMIS" : "Biais macro : ACHATS BLOQUES");
      if(n != cacheNewsBloq)
         Notifier(n ? "Annonce USD fort impact imminente : entrees bloquees, stops en mode protection."
                    : "Fenetre d'annonce terminee : retour a la normale.");
     }
   cacheBiasOK   = b;
   cacheNewsBloq = n;
   cacheInitFait = true;
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   if(hATR != INVALID_HANDLE) IndicatorRelease(hATR);
   if(hRSI != INVALID_HANDLE) IndicatorRelease(hRSI);
  }

//+------------------------------------------------------------------+
//| Gardien FTMO : renvoie true si le trading est interdit           |
//+------------------------------------------------------------------+
bool GuardianBlocks()
  {
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double base   = GlobalVariableGet(BaseGV());

   // 1) coupure definitive (perte totale)
   if(GlobalVariableCheck(HaltGV()) && GlobalVariableGet(HaltGV()) > 0.5)
      return true;
   if(equity <= base * (1.0 - TotalStopPct / 100.0))
     {
      Notifier("PERTE TOTALE MAX ATTEINTE - fermeture du compte, arret definitif");
      CloseAllOurs("");
      GlobalVariableSet(HaltGV(), 1.0);
      return true;
     }

   // 2) coupure quotidienne : equity de reference a minuit serveur
   MqlDateTime now;
   TimeToStruct(TimeCurrent(), now);
   string dayKey = StringFormat("MACROBOT_DAY_%04d%02d%02d_%s",
                                now.year, now.mon, now.day,
                                (string)AccountInfoInteger(ACCOUNT_LOGIN));
   if(!GlobalVariableCheck(dayKey))
      GlobalVariableSet(dayKey, equity);
   double dayStart = GlobalVariableGet(dayKey);
   static bool avisJourFait = false;
   if(equity <= dayStart * (1.0 - DailyStopPct / 100.0))
     {
      if(!avisJourFait)
        {
         Notifier("Stop quotidien touche - fermeture du compte, pause jusqu'a demain");
         avisJourFait = true;
        }
      CloseAllOurs("");            // sans effet si deja tout ferme
      return true;   // demain, une nouvelle cle journaliere sera creee
     }
   avisJourFait = false;
   return false;
  }

//+------------------------------------------------------------------+
void CloseAllOurs(string reason)
  {
   if(reason != "") Print("GARDIEN: ", reason);
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0 && PositionGetInteger(POSITION_MAGIC) == MagicNumber)
         trade.PositionClose(ticket);
     }
  }

//+------------------------------------------------------------------+
bool MacroBias()
  {
   if(!BiasFromFile)
      return MacroLongAllowed;
   int fh = FileOpen("macrobot_bias.txt", FILE_READ | FILE_TXT | FILE_ANSI);
   if(fh == INVALID_HANDLE)
      return MacroLongAllowed; // pas de fichier -> input manuel
   string line = FileReadString(fh);
   FileClose(fh);
   string tag = (Preset == PRESET_GOLD) ? "GOLD=1" : "NAS=1";
   return (StringFind(line, tag) >= 0);
  }

//+------------------------------------------------------------------+
//| true si une annonce USD fort impact est proche (macrobot_news.txt|
//| ecrit par export_news.py ; epochs UTC, compares a TimeGMT).      |
//+------------------------------------------------------------------+
bool NewsBlocks()
  {
   if(!NewsFilterOn)
      return false;
   int fh = FileOpen("macrobot_news.txt", FILE_READ | FILE_TXT | FILE_ANSI);
   if(fh == INVALID_HANDLE)
      return false;
   long now = (long)TimeGMT();
   bool blocked = false;
   while(!FileIsEnding(fh))
     {
      string line = FileReadString(fh);
      if(StringFind(line, "EVENT=") != 0)
         continue;
      string rest = StringSubstr(line, 6);
      int sep = StringFind(rest, ";");
      long epoch = StringToInteger(sep > 0 ? StringSubstr(rest, 0, sep) : rest);
      if(epoch > 0 &&
         now >= epoch - (long)NewsMinutesAvant * 60 &&
         now <= epoch + (long)NewsMinutesApres * 60)
        {
         blocked = true;
         break;
        }
     }
   FileClose(fh);
   return blocked;   // le log des changements d'etat se fait dans RafraichirDonneesExternes
  }

//+------------------------------------------------------------------+
//| Pendant la fenetre d'annonce : serre les stops (ou ferme) pour   |
//| limiter la perte si le prix saute. Jamais d'elargissement.       |
//+------------------------------------------------------------------+
void ProtegerPositionsNews()
  {
   if(NewsProtectMode == NEWS_PROTECT_RIEN || !cacheNewsBloq)
      return;

   double atrBuf[];
   ArraySetAsSeries(atrBuf, true);
   if(CopyBuffer(hATR, 0, 1, 1, atrBuf) < 1)
      return;
   double serre = atrBuf[0] * 0.5;
   if(serre <= 0)
      return;
   double distMin = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != MagicNumber) continue;

      if(NewsProtectMode == NEWS_PROTECT_FERMER)
        {
         Print("Annonce imminente : fermeture preventive de la position ", ticket);
         trade.PositionClose(ticket);
         continue;
        }

      double slActuel = PositionGetDouble(POSITION_SL);
      double tp       = PositionGetDouble(POSITION_TP);
      double entree   = PositionGetDouble(POSITION_PRICE_OPEN);

      if(PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY)
        {
         double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         double nouveau = bid - serre;
         if(bid > entree && entree > nouveau) nouveau = entree; // breakeven si en profit
         if(nouveau > bid - distMin) nouveau = bid - distMin;   // distance minimale du courtier
         nouveau = NormalizeDouble(nouveau, _Digits);
         if(nouveau > slActuel + serre * 0.1)
            if(trade.PositionModify(ticket, nouveau, tp))
               Print("Fenetre d'annonce : stop serre a ", DoubleToString(nouveau, _Digits));
        }
      else
        {
         double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double nouveau = ask + serre;
         if(ask < entree && entree < nouveau) nouveau = entree;
         if(nouveau < ask + distMin) nouveau = ask + distMin;
         nouveau = NormalizeDouble(nouveau, _Digits);
         if(slActuel == 0.0 || nouveau < slActuel - serre * 0.1)
            if(trade.PositionModify(ticket, nouveau, tp))
               Print("Fenetre d'annonce : stop serre a ", DoubleToString(nouveau, _Digits));
        }
     }
  }

//+------------------------------------------------------------------+
//| Breakeven : des que le prix atteint entree + 1R (R = distance    |
//| entree->stop initial), le stop remonte au prix d'entree. Le      |
//| trade ne peut plus finir perdant. Valide en backtest 2 ans H4 :  |
//| PF Nasdaq 1.26->1.33, PF or 2.00->2.11. Long-only (le bot        |
//| n'ouvre que des achats).                                         |
//+------------------------------------------------------------------+
void GererBreakeven()
  {
   if(!BreakevenActif) return;
   if(!PositionSelect(_Symbol)) return;
   if(PositionGetInteger(POSITION_MAGIC) != MagicNumber) return;
   if(PositionGetInteger(POSITION_TYPE) != POSITION_TYPE_BUY) return;

   double entree = PositionGetDouble(POSITION_PRICE_OPEN);
   double sl     = PositionGetDouble(POSITION_SL);
   double tp     = PositionGetDouble(POSITION_TP);
   if(sl <= 0 || sl >= entree) return;          // pas de stop ou deja au breakeven/mieux

   double R   = entree - sl;
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(bid < entree + R) return;                 // pas encore +1R de profit

   double distMin = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
   double nouveau = entree;
   if(nouveau > bid - distMin) nouveau = bid - distMin;
   nouveau = NormalizeDouble(nouveau, _Digits);
   if(nouveau <= sl) return;
   if(trade.PositionModify(PositionGetInteger(POSITION_TICKET), nouveau, tp))
      Notifier("Breakeven +1R atteint : stop remonte au prix d'entree, le trade ne peut plus perdre.");
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   if(GuardianBlocks())
      return;

   ProtegerPositionsNews();   // a chaque tick pendant une fenetre d'annonce
   GererBreakeven();          // a chaque tick : securise les trades a +1R

   // une decision par bougie fermee
   datetime barTime = iTime(_Symbol, _Period, 0);
   if(barTime == lastBar)
      return;
   lastBar = barTime;

   if(PositionSelect(_Symbol))   // une position max par symbole
      return;
   // donnees externes du cache, rafraichi chaque minute par OnTimer
   if(!cacheBiasOK)
      return;
   if(cacheNewsBloq)
      return;

   int need = SwingLookback + 5;
   MqlRates rates[];
   if(CopyRates(_Symbol, _Period, 0, need, rates) < need)
      return;
   ArraySetAsSeries(rates, true);

   // swing sur les bougies fermees 1..SwingLookback
   int hiIdx = 1, loIdx = 1;
   for(int i = 1; i <= SwingLookback; i++)
     {
      if(rates[i].high > rates[hiIdx].high) hiIdx = i;
      if(rates[i].low  < rates[loIdx].low)  loIdx = i;
     }
   // swing haussier requis : le bas est plus ancien que le haut
   if(loIdx <= hiIdx)
      return;
   double hi = rates[hiIdx].high, lo = rates[loIdx].low;
   double span = hi - lo;
   if(span <= 0)
      return;

   double close1 = rates[1].close;
   double retrace = (hi - close1) / span;
   if(retrace < FibLo || retrace > FibHi)
      return;

   double rsi[];
   if(CopyBuffer(hRSI, 0, 1, 2, rsi) < 2)
      return;
   ArraySetAsSeries(rsi, true);
   // rsi[1] = avant-derniere bougie fermee, rsi[0] = derniere fermee
   if(!(rsi[1] < RsiPull && rsi[0] > rsi[1]))
      return;

   double atrBuf[];
   if(CopyBuffer(hATR, 0, 1, 1, atrBuf) < 1)
      return;
   double stopDist = StopAtrMult * atrBuf[0];
   if(stopDist <= 0)
      return;

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double sl  = NormalizeDouble(ask - stopDist, _Digits);
   double tp  = NormalizeDouble(ask + stopDist * TpR, _Digits);

   double lots = LotsForRisk(stopDist);
   if(lots <= 0)
      return;

   if(trade.Buy(lots, _Symbol, 0.0, sl, tp, "MacroBot fib+RSI"))
      Print("ENTREE LONG ", _Symbol, " lots=", DoubleToString(lots, 2),
            " retrace=", DoubleToString(retrace * 100, 1), "% SL=", sl, " TP=", tp);
  }

//+------------------------------------------------------------------+
//| Taille de position pour risquer RiskPerTradePct% de l'equity     |
//+------------------------------------------------------------------+
double LotsForRisk(double stopDist)
  {
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   if(tickSize <= 0 || tickValue <= 0)
      return 0;
   double lossPerLot = stopDist / tickSize * tickValue;
   if(lossPerLot <= 0)
      return 0;
   double riskMoney = AccountInfoDouble(ACCOUNT_EQUITY) * RiskPerTradePct / 100.0;
   double lots = riskMoney / lossPerLot;

   double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   lots = MathFloor(lots / lotStep) * lotStep;
   if(lots < minLot)
      return 0;   // trop petit pour respecter le risque -> pas de trade
   return MathMin(lots, maxLot);
  }
//+------------------------------------------------------------------+
