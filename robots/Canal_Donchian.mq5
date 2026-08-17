//+------------------------------------------------------------------+
//|                                               Canal_Donchian.mq5 |
//|  Canal de Donchian : le plus haut des N dernières bougies (ligne |
//|  d'entrée des robots de cassure) et le plus bas des M dernières  |
//|  (ligne de sortie / stop suiveur). Purement visuel — les robots  |
//|  font leurs propres calculs identiques.                          |
//|  BTC Breakout : 55/20 en H4.  Pétrole : 20/10 en D1.             |
//+------------------------------------------------------------------+
#property copyright "Jimmy"
#property version   "1.00"
#property indicator_chart_window
#property indicator_buffers 2
#property indicator_plots   2
#property indicator_label1  "Canal haut (entrée)"
#property indicator_type1   DRAW_LINE
#property indicator_color1  clrDodgerBlue
#property indicator_style1  STYLE_DOT
#property indicator_width1  1
#property indicator_label2  "Canal bas (stop suiveur)"
#property indicator_type2   DRAW_LINE
#property indicator_color2  clrOrangeRed
#property indicator_style2  STYLE_DOT
#property indicator_width2  1

input int PeriodeHaut = 55;   // Cassure : plus haut des N bougies
input int PeriodeBas  = 20;   // Sortie : plus bas des M bougies

double tamponHaut[], tamponBas[];

int OnInit()
  {
   SetIndexBuffer(0, tamponHaut, INDICATOR_DATA);
   SetIndexBuffer(1, tamponBas,  INDICATOR_DATA);
   PlotIndexSetInteger(0, PLOT_DRAW_BEGIN, PeriodeHaut + 1);
   PlotIndexSetInteger(1, PLOT_DRAW_BEGIN, PeriodeBas + 1);
   return(INIT_SUCCEEDED);
  }

int OnCalculate(const int total, const int prev,
                const datetime &temps[], const double &ouverture[],
                const double &haut[], const double &bas[], const double &cloture[],
                const long &vol_tick[], const long &vol_reel[], const int &spread[])
  {
   int debut = MathMax(prev - 1, MathMax(PeriodeHaut, PeriodeBas) + 1);
   for(int i = debut; i < total; i++)
     {
      double hh = haut[i-1];
      for(int k = 2; k <= PeriodeHaut && i - k >= 0; k++)
         if(haut[i-k] > hh) hh = haut[i-k];
      tamponHaut[i] = hh;

      double bb = bas[i-1];
      for(int k = 2; k <= PeriodeBas && i - k >= 0; k++)
         if(bas[i-k] < bb) bb = bas[i-k];
      tamponBas[i] = bb;
     }
   return(total);
  }
//+------------------------------------------------------------------+
