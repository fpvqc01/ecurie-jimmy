//+------------------------------------------------------------------+
//| Nova_ORB_XAUUSD_M5.mq5 — Opening Range Breakout (sprint ~30j)   |
//| + filtre "IA légère" : score range/vol + biais fichier optionnel|
//| Config labo orb_fast : risk 1.8%, TP 1.8R — HAUTE MORTALITÉ     |
//+------------------------------------------------------------------+
#property copyright "Nova FTMO"
#property version   "1.10"

input double RisquePct        = 1.8;
input int    RangeBars        = 3;      // barres M5 pour construire le range
input double SlBufferAtr      = 0.2;
input double TpR              = 1.8;
input int    AtrPeriod        = 14;
input double HaltJourPct      = 3.2;
input double HaltTotalPct     = 8.0;
input double ObjectifPhasePct = 10.0;   // 10 p1 / 5 p2 / 0 financé
input int    LondonOpenHour   = 7;      // UTC terminal — ajuster fuseau MT5
input int    NyOpenHour       = 13;
input int    SessionEndHour   = 20;
input int    MaxTradesDay     = 2;
input bool   AllowShort       = true;
input long   Magic            = 202611243;

// --- Filtre intelligent (pas un LLM dans la boucle) ---
input bool   UseSmartFilter   = true;   // refuse les ranges pourris
input double MinRangeAtr      = 0.35;   // range trop petit = bruit
input double MaxRangeAtr      = 2.20;   // range trop large = chaos
input double MinBreakBodyAtr  = 0.15;   // bougie de break trop molle = skip
input bool   UseBiasFile      = false;  // lit MQL5\Files\nova_ai_bias.txt
input string BiasFileName     = "nova_ai_bias.txt"; // BOTH|LONG|SHORT|OFF

int hAtr;
datetime g_day0=0;
double g_dayStartEquity=0;
bool g_halted=false;
int g_dayTrades=0;

// ORB state
bool g_building=false;
bool g_armed=false;
bool g_takenSession=false;
int g_rangeBars=0;
double g_rangeHi=0, g_rangeLo=0;

int OnInit()
{
   hAtr=iATR(_Symbol, PERIOD_M5, AtrPeriod);
   if(hAtr==INVALID_HANDLE) return INIT_FAILED;
   string key="NOVA_INIT_"+IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN));
   if(!GlobalVariableCheck(key))
      GlobalVariableSet(key, AccountInfoDouble(ACCOUNT_BALANCE));
   g_dayStartEquity=AccountInfoDouble(ACCOUNT_EQUITY);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(hAtr!=INVALID_HANDLE) IndicatorRelease(hAtr);
}

double InitCap()
{
   return GlobalVariableGet("NOVA_INIT_"+IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN)));
}

bool Buf(int handle,int shift,double &v)
{
   double b[];
   if(CopyBuffer(handle,0,shift,1,b)!=1) return false;
   v=b[0]; return true;
}

int CountMine()
{
   int n=0;
   for(int i=PositionsTotal()-1;i>=0;--i)
   {
      ulong t=PositionGetTicket(i);
      if(!PositionSelectByTicket(t)) continue;
      if(PositionGetString(POSITION_SYMBOL)==_Symbol && PositionGetInteger(POSITION_MAGIC)==Magic) n++;
   }
   return n;
}

void CloseAllMine()
{
   for(int i=PositionsTotal()-1;i>=0;--i)
   {
      ulong ticket=PositionGetTicket(i);
      if(!PositionSelectByTicket(ticket)) continue;
      if(PositionGetString(POSITION_SYMBOL)!=_Symbol || PositionGetInteger(POSITION_MAGIC)!=Magic) continue;
      MqlTradeRequest req; MqlTradeResult res; ZeroMemory(req); ZeroMemory(res);
      req.action=TRADE_ACTION_DEAL;
      req.position=ticket;
      req.symbol=_Symbol;
      req.volume=PositionGetDouble(POSITION_VOLUME);
      bool isBuy=(PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY);
      req.type=isBuy?ORDER_TYPE_SELL:ORDER_TYPE_BUY;
      req.price=isBuy?SymbolInfoDouble(_Symbol,SYMBOL_BID):SymbolInfoDouble(_Symbol,SYMBOL_ASK);
      req.deviation=40; req.magic=Magic;
      OrderSend(req,res);
   }
}

void NewDayReset(datetime day0,double equity)
{
   g_day0=day0;
   g_dayStartEquity=equity;
   g_halted=false;
   g_dayTrades=0;
   g_building=false;
   g_armed=false;
   g_takenSession=false;
   g_rangeBars=0;
}

void ManageRisk()
{
   MqlDateTime dt; TimeToStruct(TimeCurrent(),dt);
   datetime day0=StringToTime(StringFormat("%04d.%02d.%02d",dt.year,dt.mon,dt.day));
   double equity=AccountInfoDouble(ACCOUNT_EQUITY);
   double balance=AccountInfoDouble(ACCOUNT_BALANCE);
   double initCap=InitCap();
   if(day0!=g_day0) NewDayReset(day0,equity);

   if(equity<=initCap*(1.0-HaltTotalPct/100.0) || equity<=initCap*0.90)
   { CloseAllMine(); g_halted=true; return; }
   if(equity<=g_dayStartEquity-(HaltJourPct/100.0)*initCap)
   { CloseAllMine(); g_halted=true; }
   if(ObjectifPhasePct>0.0 && balance>=initCap*(1.0+ObjectifPhasePct/100.0) && CountMine()>0)
      CloseAllMine();
}

// BOTH / LONG / SHORT / OFF
string ReadBias()
{
   if(!UseBiasFile) return "BOTH";
   int h=FileOpen(BiasFileName,FILE_READ|FILE_TXT|FILE_ANSI);
   if(h==INVALID_HANDLE) return "BOTH";
   string line=FileReadString(h);
   FileClose(h);
   StringTrimLeft(line); StringTrimRight(line);
   StringToUpper(line);
   if(line=="LONG" || line=="SHORT" || line=="OFF" || line=="BOTH") return line;
   return "BOTH";
}

bool SmartFilterOk(const double atr,const double rangeW,const double body,const int side)
{
   if(!UseSmartFilter) return true;
   if(atr<=0) return false;
   double rangeAtr=rangeW/atr;
   double bodyAtr=body/atr;
   // Trop étroit = faux breakouts ; trop large = déjà explosé
   if(rangeAtr < MinRangeAtr || rangeAtr > MaxRangeAtr) {
      Print("Nova AI-filter SKIP range/ATR=",DoubleToString(rangeAtr,2));
      return false;
   }
   if(bodyAtr < MinBreakBodyAtr) {
      Print("Nova AI-filter SKIP weak break body/ATR=",DoubleToString(bodyAtr,2));
      return false;
   }
   string bias=ReadBias();
   if(bias=="OFF") return false;
   if(bias=="LONG" && side<0) return false;
   if(bias=="SHORT" && side>0) return false;
   return true;
}

void OnTick()
{
   ManageRisk();
   if(g_halted) return;

   static datetime lastBar=0;
   datetime t=iTime(_Symbol,PERIOD_M5,0);
   if(t==lastBar) return;
   lastBar=t;

   MqlDateTime dt; TimeToStruct(iTime(_Symbol,PERIOD_M5,1), dt);
   int hh=dt.hour;

   double hi1=iHigh(_Symbol,PERIOD_M5,1);
   double lo1=iLow(_Symbol,PERIOD_M5,1);
   double c1=iClose(_Symbol,PERIOD_M5,1);
   double o1=iOpen(_Symbol,PERIOD_M5,1);

   if(hh==LondonOpenHour || hh==NyOpenHour)
   {
      if(!g_building && !g_armed && !g_takenSession)
      {
         g_building=true;
         g_rangeBars=0;
         g_rangeHi=hi1;
         g_rangeLo=lo1;
      }
   }

   if(g_building)
   {
      if(hi1>g_rangeHi) g_rangeHi=hi1;
      if(lo1<g_rangeLo) g_rangeLo=lo1;
      g_rangeBars++;
      if(g_rangeBars>=RangeBars)
      {
         g_building=false;
         g_armed=true;
      }
   }

   if(hh>=SessionEndHour)
   {
      g_armed=false;
      if(CountMine()>0) CloseAllMine();
   }

   if(CountMine()>0 || !g_armed || g_takenSession || g_dayTrades>=MaxTradesDay)
      return;

   double atr; if(!Buf(hAtr,1,atr) || atr<=0) return;

   int side=0;
   if(c1>g_rangeHi) side=1;
   else if(AllowShort && c1<g_rangeLo) side=-1;
   if(side==0) return;

   double rangeW=g_rangeHi-g_rangeLo;
   double body=MathAbs(c1-o1);
   if(!SmartFilterOk(atr,rangeW,body,side))
   {
      // consomme la session pour ne pas spammer après un range pourri
      g_takenSession=true;
      g_armed=false;
      return;
   }

   double ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK);
   double bid=SymbolInfoDouble(_Symbol,SYMBOL_BID);
   double entry=(side>0)?ask:bid;
   double stop=(side>0)?(g_rangeLo-SlBufferAtr*atr):(g_rangeHi+SlBufferAtr*atr);
   double slDist=MathAbs(entry-stop);
   if(slDist<=0) return;

   double equity=AccountInfoDouble(ACCOUNT_EQUITY);
   double tickVal=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE);
   double tickSize=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   if(tickVal<=0 || tickSize<=0) return;
   double lots=(equity*(RisquePct/100.0))/((slDist/tickSize)*tickVal);
   double step=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   double vmin=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   double vmax=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   lots=MathFloor(lots/step)*step;
   if(lots<vmin) return;
   if(lots>vmax) lots=vmax;

   double tp=entry+side*TpR*slDist;
   MqlTradeRequest req; MqlTradeResult res; ZeroMemory(req); ZeroMemory(res);
   req.action=TRADE_ACTION_DEAL;
   req.symbol=_Symbol;
   req.volume=lots;
   req.type=(side>0)?ORDER_TYPE_BUY:ORDER_TYPE_SELL;
   req.price=entry;
   req.sl=stop;
   req.tp=tp;
   req.deviation=40;
   req.magic=Magic;
   req.comment="NovaORB+AI";
   if(OrderSend(req,res))
   {
      g_dayTrades++;
      g_takenSession=true;
      g_armed=false;
      Print("Nova AI-filter TAKE side=",side," range/ATR=",DoubleToString(rangeW/atr,2));
   }
   else Print("Nova ORB fail ",res.retcode);
}
