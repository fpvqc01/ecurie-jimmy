//+------------------------------------------------------------------+
//| Nova_US100_H4.mq5 — NOUVEAU système (config banc D)              |
//| Signal: close croise au-dessus EMA20, régime EMA20>EMA100         |
//+------------------------------------------------------------------+
#property copyright "Nova FTMO"
#property version   "1.00"

input double RisquePct        = 0.8;
input int    EmaRapide        = 20;
input int    EmaLente         = 100;
input int    AtrPeriod        = 14;
input double SlAtr            = 1.7;
input double TpR              = 2.5;
input double HaltJourPct      = 2.4;
input double HaltTotalPct     = 8.0;
input double ObjectifPhasePct = 10.0; // 10=p1, 5=p2, 0=financé
input int    CooldownBars     = 3;
input long   Magic            = 202611242;

datetime g_day0 = 0;
double   g_dayStartEquity = 0;
bool     g_haltedToday = false;
int      g_lastExitBar = -100000;
int      hEmaF, hEmaS, hAtr;

int OnInit()
{
   hEmaF = iMA(_Symbol, PERIOD_H4, EmaRapide, 0, MODE_EMA, PRICE_CLOSE);
   hEmaS = iMA(_Symbol, PERIOD_H4, EmaLente, 0, MODE_EMA, PRICE_CLOSE);
   hAtr  = iATR(_Symbol, PERIOD_H4, AtrPeriod);
   if(hEmaF==INVALID_HANDLE || hEmaS==INVALID_HANDLE || hAtr==INVALID_HANDLE)
      return INIT_FAILED;
   g_dayStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   string key = "NOVA_INIT_"+IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN));
   if(!GlobalVariableCheck(key))
      GlobalVariableSet(key, AccountInfoDouble(ACCOUNT_BALANCE));
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(hEmaF!=INVALID_HANDLE) IndicatorRelease(hEmaF);
   if(hEmaS!=INVALID_HANDLE) IndicatorRelease(hEmaS);
   if(hAtr!=INVALID_HANDLE)  IndicatorRelease(hAtr);
}

bool Buf(int h, int shift, double &v)
{
   double b[];
   if(CopyBuffer(h, 0, shift, 1, b)!=1) return false;
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
      req.deviation=30; req.magic=Magic;
      OrderSend(req,res);
   }
   g_lastExitBar=Bars(_Symbol,PERIOD_H4);
}

double InitCap()
{
   return GlobalVariableGet("NOVA_INIT_"+IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN)));
}

void ManageRisk()
{
   MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
   datetime day0=StringToTime(StringFormat("%04d.%02d.%02d",dt.year,dt.mon,dt.day));
   double equity=AccountInfoDouble(ACCOUNT_EQUITY);
   double balance=AccountInfoDouble(ACCOUNT_BALANCE);
   double initCap=InitCap();
   if(day0!=g_day0){ g_day0=day0; g_dayStartEquity=equity; g_haltedToday=false; }

   if(equity<=initCap*(1.0-HaltTotalPct/100.0) || equity<=initCap*0.90)
   { CloseAllMine(); g_haltedToday=true; return; }
   if(equity<=g_dayStartEquity-(HaltJourPct/100.0)*initCap)
   { CloseAllMine(); g_haltedToday=true; }

   if(ObjectifPhasePct>0.0 && balance>=initCap*(1.0+ObjectifPhasePct/100.0) && CountMine()>0)
      CloseAllMine();
}

void OnTick()
{
   ManageRisk();
   if(g_haltedToday) return;

   static datetime lastBar=0;
   datetime t=iTime(_Symbol,PERIOD_H4,0);
   if(t==lastBar) return;
   lastBar=t;
   if(CountMine()>0) return;
   if(Bars(_Symbol,PERIOD_H4)-g_lastExitBar < CooldownBars) return;

   double emaF1,emaF2,emaS1,atr1;
   if(!Buf(hEmaF,1,emaF1) || !Buf(hEmaF,2,emaF2) || !Buf(hEmaS,1,emaS1) || !Buf(hAtr,1,atr1)) return;
   double c1=iClose(_Symbol,PERIOD_H4,1);
   double c2=iClose(_Symbol,PERIOD_H4,2);
   if(atr1<=0) return;

   bool cross=(c2<=emaF2 && c1>emaF1);
   bool regime=(c1>emaS1 && emaF1>emaS1);
   if(!(cross && regime)) return;

   double equity=AccountInfoDouble(ACCOUNT_EQUITY);
   double risk=RisquePct/100.0;
   double slDist=SlAtr*atr1;
   double ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK);
   double tickVal=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE);
   double tickSize=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   if(tickVal<=0 || tickSize<=0 || slDist<=0) return;
   double lots=(equity*risk)/((slDist/tickSize)*tickVal);
   double step=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   double vmin=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   double vmax=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   lots=MathFloor(lots/step)*step;
   if(lots<vmin) return;
   if(lots>vmax) lots=vmax;

   MqlTradeRequest req; MqlTradeResult res; ZeroMemory(req); ZeroMemory(res);
   req.action=TRADE_ACTION_DEAL;
   req.symbol=_Symbol;
   req.volume=lots;
   req.type=ORDER_TYPE_BUY;
   req.price=ask;
   req.sl=ask-slDist;
   req.tp=ask+TpR*slDist;
   req.deviation=30;
   req.magic=Magic;
   req.comment="NovaUS100";
   if(!OrderSend(req,res)) Print("Nova XAU fail ",res.retcode);
}

void OnTradeTransaction(const MqlTradeTransaction& trans,
                        const MqlTradeRequest& request,
                        const MqlTradeResult& result)
{
   if(trans.type==TRADE_TRANSACTION_DEAL_ADD)
      g_lastExitBar=Bars(_Symbol,PERIOD_H4);
}
