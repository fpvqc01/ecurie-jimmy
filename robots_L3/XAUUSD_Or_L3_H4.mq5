//+------------------------------------------------------------------+
//| XAUUSD_Or_L3_H4.mq5                                             |
//| Version I2 — config optimisee du 17 aout 2026 :                  |
//|  - OR     : TP 1.5R (~750$) + re-entree sur repli 0.25xATR       |
//|  - NASDAQ : TP 1.0R (~500$) + re-entree sur repli 0.5xATR        |
//|  - re-entree permise tant que le creux du swing d'origine tient  |
//|  - risque 1.5 % par trade (x1.5)                                 |
//|  - plafond d'ecurie : max 2 positions simultanees (tous robots)  |
//| Meme magic que la V1 : reprend les positions existantes.         |
//+------------------------------------------------------------------+
#property copyright "Macro Bot"
#property version   "2.00"

#include <Trade\Trade.mqh>

enum ENUM_PRESET
  {
   PRESET_GOLD,    // Or (XAUUSD)
   PRESET_NASDAQ   // US100 / NAS100
  };

input ENUM_PRESET Preset             = PRESET_GOLD;
input bool   MacroLongAllowed        = true;
input bool   BiasFromFile            = true;
input double RiskPerTradePct         = 3.0;    // L3 or renforce (demi-Kelly conservateur, valide 5-10 ans)
input double DailyStopPct            = 2.5;   // L3 : resserre (valide 19 aout ; FTMO = 5)
input double TotalStopPct            = 8.0;
input double ChallengeInitialBalance = 0;
input long   MagicNumber             = 20260915;
input int    MaxPositionsEcurie      = 2;      // plafond global de l'ecurie (I2)
input bool   NewsFilterOn            = true;
input int    NewsMinutesAvant        = 30;
input int    NewsMinutesApres        = 30;

enum ENUM_NEWS_PROTECT
  {
   NEWS_PROTECT_RIEN   = 0,
   NEWS_PROTECT_SERRER = 1,
   NEWS_PROTECT_FERMER = 2
  };
input ENUM_NEWS_PROTECT NewsProtectMode = NEWS_PROTECT_SERRER;
input bool   PushNotifications       = true;
input bool   BreakevenActif          = true;
input bool   FacteurVolActif         = true;   // moduler le risque selon la volatilite (L3)
input bool   JournalActif            = true;   // journal de reflexion (Files\Ecurie_Journal)

CTrade   trade;
int      hATR = INVALID_HANDLE, hRSI = INVALID_HANDLE;
datetime lastBar = 0;
bool     cacheBiasOK   = true;
bool     cacheNewsBloq = false;
bool     cacheInitFait = false;
datetime derniereLectureVol = 0;
double   facteurVol = 1.0;

double   attenteReentree = 0;   // prix de sortie TP ; 0 = rien en attente (I2)
double   plancherSwing   = 0;   // creux du swing de l'entree d'origine (I2)

// parametres de timing par preset
int    SwingLookback;
double FibLo, FibHi, RsiPull, StopAtrMult, TpR, RetraceReentree;
int    RsiPeriod = 14, AtrPeriod = 14;

string BaseGV()  { return "MACROBOT_BASE_"  + (string)AccountInfoInteger(ACCOUNT_LOGIN); }
string HaltGV()  { return "MACROBOT_HALT_"  + (string)AccountInfoInteger(ACCOUNT_LOGIN); }

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
      if(PositionGetInteger(POSITION_MAGIC) != MagicNumber) continue;
      return(true);
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
      if(m != 20260915 && m != 20260917 && m != 20260918) continue;
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
   if(!PushNotifications) return;
   static bool avertiEchec = false;
   if(!SendNotification(_Symbol + " L3 : " + msg) && !avertiEchec)
     {
      Print("Push non envoye. Configure ton MetaQuotes ID.");
      avertiEchec = true;
     }
  }

//+------------------------------------------------------------------+
//| Notifications + detection des sorties TP (arme la re-entree)     |
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
   long   sens = HistoryDealGetInteger(trans.deal, DEAL_ENTRY);

   if(sens == DEAL_ENTRY_IN)
      Notifier(StringFormat("ENTREE achat %.2f lot @ %s", vol, DoubleToString(prix, _Digits)));
   else if(sens == DEAL_ENTRY_OUT)
     {
      Notifier(StringFormat("SORTIE %.2f lot @ %s | P/L: %.2f $", vol,
                            DoubleToString(prix, _Digits),
                            HistoryDealGetDouble(trans.deal, DEAL_PROFIT)));
      long raison = HistoryDealGetInteger(trans.deal, DEAL_REASON);
      if(raison == DEAL_REASON_TP)
        {
         attenteReentree = prix;
         Print("TP encaisse : re-entree armee sous ", DoubleToString(prix, _Digits),
               " (tant que le plancher ", DoubleToString(plancherSwing, _Digits), " tient)");
        }
      else
        {
         attenteReentree = 0;   // stop touche : la these est invalidee
         plancherSwing = 0;
        }
     }
  }


//+------------------------------------------------------------------+
//| Journal de reflexion : une ligne par bougie dans                 |
//| MQL5\Files\Ecurie_Journal\<robot>.txt (lisible au Bloc-notes)    |
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
   if(Preset == PRESET_GOLD)
     {
      SwingLookback = 60; FibLo = 0.20; FibHi = 0.80;
      RsiPull = 55.0; StopAtrMult = 3.0;
      TpR = 1.5; RetraceReentree = 0.25;    // I2
     }
   else // PRESET_NASDAQ
     {
      SwingLookback = 40; FibLo = 0.10; FibHi = 0.90;
      RsiPull = 60.0; StopAtrMult = 2.0;
      TpR = 1.0; RetraceReentree = 0.5;     // I2
     }

   if(_Period != PERIOD_H4)
      Print("ATTENTION: la strategie a ete calibree en H4, graphique actuel: ",
            EnumToString(_Period));

   hATR = iATR(_Symbol, _Period, AtrPeriod);
   hRSI = iRSI(_Symbol, _Period, RsiPeriod, PRICE_CLOSE);
   if(hATR == INVALID_HANDLE || hRSI == INVALID_HANDLE)
      return INIT_FAILED;

   trade.SetExpertMagicNumber(MagicNumber);

   if(!GlobalVariableCheck(BaseGV()))
     {
      double base = (ChallengeInitialBalance > 0)
                    ? ChallengeInitialBalance
                    : AccountInfoDouble(ACCOUNT_BALANCE);
      GlobalVariableSet(BaseGV(), base);
     }
   Print("MacroBot L3 demarre. Baseline: ", DoubleToString(GlobalVariableGet(BaseGV()), 2),
         " | TP ", DoubleToString(TpR, 1), "R, re-entree ", DoubleToString(RetraceReentree, 2),
         "xATR, plafond ecurie ", MaxPositionsEcurie);

   EventSetTimer(60);
   RafraichirDonneesExternes();
   return INIT_SUCCEEDED;
  }

//+------------------------------------------------------------------+
void OnTimer()
  {
   RafraichirDonneesExternes();
   LireFacteurVol();
   ProtegerPositionsNews();
  }

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
         Notifier(n ? "Annonce USD imminente : entrees bloquees, stops en protection."
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
bool GuardianBlocks()
  {
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double base   = GlobalVariableGet(BaseGV());

   if(GlobalVariableCheck(HaltGV()) && GlobalVariableGet(HaltGV()) > 0.5)
      return true;
   if(equity <= base * (1.0 - TotalStopPct / 100.0))
     {
      Notifier("PERTE TOTALE MAX ATTEINTE - fermeture du compte, arret definitif");
      CloseAllOurs("");
      GlobalVariableSet(HaltGV(), 1.0);
      return true;
     }

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
      CloseAllOurs("");
      return true;
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
      return MacroLongAllowed;
   string line = FileReadString(fh);
   FileClose(fh);
   string tag = (Preset == PRESET_GOLD) ? "GOLD=1" : "NAS=1";
   return (StringFind(line, tag) >= 0);
  }

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
   return blocked;
  }

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
         Print("Annonce imminente : fermeture preventive de ", ticket);
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
            Print("Fenetre d'annonce : stop serre a ", DoubleToString(nouveau, _Digits));
     }
  }

//+------------------------------------------------------------------+
void GererBreakeven()
  {
   if(!BreakevenActif) return;
   if(!PositionOuverte()) return;
   if(PositionGetInteger(POSITION_MAGIC) != MagicNumber) return;
   if(PositionGetInteger(POSITION_TYPE) != POSITION_TYPE_BUY) return;

   double entree = PositionGetDouble(POSITION_PRICE_OPEN);
   double sl     = PositionGetDouble(POSITION_SL);
   double tp     = PositionGetDouble(POSITION_TP);
   if(sl <= 0 || sl >= entree) return;

   double R   = entree - sl;
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(bid < entree + R) return;

   double distMin = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
   double nouveau = entree;
   if(nouveau > bid - distMin) nouveau = bid - distMin;
   nouveau = NormalizeDouble(nouveau, _Digits);
   if(nouveau <= sl) return;
   if(trade.PositionModify(PositionGetInteger(POSITION_TICKET), nouveau, tp))
      Notifier("Breakeven +1R : stop remonte au prix d'entree.");
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
double LotsForRisk(double stopDist)
  {
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   if(tickSize <= 0 || tickValue <= 0)
      return 0;
   double lossPerLot = stopDist / tickSize * tickValue;
   if(lossPerLot <= 0)
      return 0;
   double riskMoney = AccountInfoDouble(ACCOUNT_EQUITY) * RiskPerTradePct / 100.0 * facteurVol;
   double lots = riskMoney / lossPerLot;

   double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   lots = MathFloor(lots / lotStep) * lotStep;
   if(lots < minLot)
      return 0;
   return MathMin(lots, maxLot);
  }

//+------------------------------------------------------------------+
//| Ouvre un achat au prix du marche avec SL/TP calcules             |
//+------------------------------------------------------------------+
void OuvrirAchat(double stopDist, string commentaire)
  {
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double sl  = NormalizeDouble(ask - stopDist, _Digits);
   double tp  = NormalizeDouble(ask + stopDist * TpR, _Digits);
   double lots = LotsForRisk(stopDist);
   if(lots <= 0) return;
   if(trade.Buy(lots, _Symbol, 0.0, sl, tp, commentaire))
      Print("ENTREE LONG ", _Symbol, " lots=", DoubleToString(lots, 2),
            " SL=", sl, " TP=", tp, " (", commentaire, ")");
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   if(GuardianBlocks())
      return;

   ProtegerPositionsNews();
   GererBreakeven();

   datetime barTime = iTime(_Symbol, _Period, 0);
   if(barTime == lastBar)
      return;
   lastBar = barTime;

   EcrireJournal(StringFormat("cloture=%.2f | position=%s | biais_macro=%s | news=%s | facteurVol=%.2f | reentree_armee=%s | plancher_swing=%.2f",
      iClose(_Symbol, _Period, 1), (PositionOuverte() ? "OUVERTE" : "aucune"),
      (cacheBiasOK ? "OK" : "BLOQUE"), (cacheNewsBloq ? "FENETRE ANNONCE" : "libre"),
      facteurVol, (attenteReentree > 0 ? "OUI" : "non"), plancherSwing));

   if(PositionOuverte())
      return;
   if(!cacheBiasOK)
      return;
   if(cacheNewsBloq)
      return;

   int need = SwingLookback + 5;
   MqlRates rates[];
   if(CopyRates(_Symbol, _Period, 0, need, rates) < need)
      return;
   ArraySetAsSeries(rates, true);

   double atrBuf[];
   if(CopyBuffer(hATR, 0, 1, 1, atrBuf) < 1)
      return;
   double stopDist = StopAtrMult * atrBuf[0];
   if(stopDist <= 0)
      return;

   // swing haussier sur les bougies fermees
   int hiIdx = 1, loIdx = 1;
   for(int i = 1; i <= SwingLookback; i++)
     {
      if(rates[i].high > rates[hiIdx].high) hiIdx = i;
      if(rates[i].low  < rates[loIdx].low)  loIdx = i;
     }
   bool swingOK = (loIdx > hiIdx);
   double hi = rates[hiIdx].high, lo = rates[loIdx].low;
   double span = hi - lo;

   // invalidation de la re-entree : le plancher du swing d'origine a casse
   if(attenteReentree > 0 && plancherSwing > 0 && rates[1].close < plancherSwing)
     {
      attenteReentree = 0;
      plancherSwing = 0;
      Print("Plancher du swing casse : re-entree annulee.");
     }

   // --- Entree 1 : setup fib+RSI complet (comme V1) ---
   bool setup = false;
   if(swingOK && span > 0)
     {
      double retrace = (hi - rates[1].close) / span;
      if(retrace >= FibLo && retrace <= FibHi)
        {
         double rsi[];
         if(CopyBuffer(hRSI, 0, 1, 2, rsi) >= 2)
           {
            ArraySetAsSeries(rsi, true);
            setup = (rsi[1] < RsiPull && rsi[0] > rsi[1]);
           }
        }
     }
   if(setup)
     {
      if(ComptePositionsEcurie() >= MaxPositionsEcurie) return;   // plafond (I2)
      plancherSwing = lo;
      attenteReentree = 0;
      OuvrirAchat(stopDist, "Ecurie_L3 fib+RSI");
      return;
     }

   // --- Entree 2 (I2) : re-entree sur repli apres un TP encaisse ---
   if(attenteReentree > 0 && plancherSwing > 0 &&
      rates[1].low <= attenteReentree - RetraceReentree * atrBuf[0] &&
      rates[1].close > plancherSwing)
     {
      if(ComptePositionsEcurie() >= MaxPositionsEcurie) return;   // plafond (I2)
      Print("Repli atteint apres TP : re-entree.");
      OuvrirAchat(stopDist, "Ecurie_L3 re-entree");
      attenteReentree = 0;
     }
  }
//+------------------------------------------------------------------+
