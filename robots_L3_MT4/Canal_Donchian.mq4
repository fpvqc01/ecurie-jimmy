//+------------------------------------------------------------------+
//|  Canal_Donchian.mq4                                              |
//|  Ecurie L3 de Jimmy — visualise les canaux des robots de cassure |
//|  Ligne bleue  = plus haut des N bougies (niveau d'entree)        |
//|  Ligne rouge  = plus bas des M bougies (stop suiveur)            |
//|  BTC Cassure H4 : 55 / 20     Petrole D1 : 20 / 10               |
//+------------------------------------------------------------------+
#property strict
#property indicator_chart_window
#property indicator_buffers 2
#property indicator_color1 DodgerBlue
#property indicator_color2 OrangeRed
#property indicator_style1 STYLE_DOT
#property indicator_style2 STYLE_DOT
#property indicator_width1 1
#property indicator_width2 1

input int PeriodeHaut = 55;   // bougies pour le plus haut (entree)
input int PeriodeBas  = 20;   // bougies pour le plus bas (stop suiveur)

double BufHaut[];
double BufBas[];

//+------------------------------------------------------------------+
int OnInit()
  {
   SetIndexBuffer(0, BufHaut);
   SetIndexBuffer(1, BufBas);
   SetIndexStyle(0, DRAW_LINE, STYLE_DOT, 1, DodgerBlue);
   SetIndexStyle(1, DRAW_LINE, STYLE_DOT, 1, OrangeRed);
   SetIndexLabel(0, "Canal haut (" + IntegerToString(PeriodeHaut) + ")");
   SetIndexLabel(1, "Canal bas (" + IntegerToString(PeriodeBas) + ")");
   IndicatorShortName("Canal Donchian " + IntegerToString(PeriodeHaut) + "/" + IntegerToString(PeriodeBas));
   IndicatorDigits(Digits);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
int OnCalculate(const int rates_total,
                const int prev_calculated,
                const datetime &time[],
                const double &open[],
                const double &high[],
                const double &low[],
                const double &close[],
                const long &tick_volume[],
                const long &volume[],
                const int &spread[])
  {
   int depart = MathMax(PeriodeHaut, PeriodeBas) + 1;
   if(rates_total < depart) return(0);

   int limite = rates_total - prev_calculated;
   if(prev_calculated > 0) limite++;
   if(limite > rates_total - depart) limite = rates_total - depart;

   for(int i = 0; i < limite; i++)
     {
      // canaux calcules sur les bougies PRECEDENTES (comme les robots)
      int idxH = iHighest(NULL, 0, MODE_HIGH, PeriodeHaut, i + 1);
      int idxB = iLowest(NULL, 0, MODE_LOW, PeriodeBas, i + 1);
      if(idxH < 0 || idxB < 0) continue;
      BufHaut[i] = High[idxH];
      BufBas[i]  = Low[idxB];
     }
   return(rates_total);
  }
//+------------------------------------------------------------------+
