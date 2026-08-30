//+------------------------------------------------------------------+
//|                                                   @@FICHIER@@ |
//|  GROKBOT @@VERSION@@ -- @@PAIRE@@, deux sens, decision journaliere.  |
//|                                                                  |
//|  CODE NEUF. Aucune ligne reprise d'un robot de l'ecurie : ni le   |
//|  chassis L13, ni I2+, ni S2. GrokBot est une lignee separee, avec |
//|  sa propre raison d'exister.                                     |
//|                                                                  |
//|  POURQUOI IL EXISTE                                              |
//|  Les 30 generations de l'ecurie partagent le meme angle mort :    |
//|  elles sont 100 %% ACHETEUSES sur des actifs de risque (BTC, or,   |
//|  Nasdaq, petrole). Aucune ne peut gagner quand le risque baisse.  |
//|  GrokBot est bati pour etre ce robot-la : DEUX SENS, sur le FX,   |
//|  mene par les cycles de politique monetaire Fed/BoJ plutot que    |
//|  par l'appetit pour le risque.                                   |
//|                                                                  |
//|  PRINCIPE ECONOMIQUE EXTERNE (standard 1 du README)               |
//|  Momentum de serie temporelle, qui fonctionne DANS LES DEUX SENS  |
//|  (Moskowitz-Ooi-Pedersen 2012 ; un siecle de donnees AQR). Le     |
//|  README avait rejete le TSMOM comme FILTRE plaque sur des robots  |
//|  deja suiveurs de tendance -- ce n'est pas le meme usage : ici    |
//|  c'est la strategie elle-meme, sur un territoire vierge.          |
//|                                                                  |
//|  LA REGLE                                                        |
//|    Entree  : croisement EMA 20/50 sur bougies JOURNALIERES,       |
//|              a la hausse -> ACHAT, a la baisse -> VENTE.          |
//|    Stop    : 2,0 x ATR(14) journalier. C'est 1 R.                 |
//|    Sortie  : TP a 1,5 R. Pas de stop suiveur (teste, inferieur).  |
//|    Risque  : 0,75 %% du solde par trade.                           |
//|@@REGLE_V2@@
//|                                                                  |
@@ROLE@@
//|                                                                  |
//|  CE QUE LE BANC A MESURE (backtests/banc_grokbot.py, 10 ans de    |
//|  barres journalieres, frais reels PESSIMISTES : commission        |
//|  2,5 $/lot/cote + spread 0,3 pip, et swap -0,010 %%/jour DES DEUX  |
//|  COTES -- aucune paire ne recoit de credit de portage)            |
//|                                                                  |
//|    Manche seule sur 10 ans :                                     |
//|      @@SEUL@@
//|    Portefeuille (ecurie + GrokBot, plafond de 2 positions) :      |
@@PORTEFEUILLE@@
//|                                                                  |
@@POURQUOI@@
//|                                                                  |
//|  PROTECTIONS FTMO : partagees avec l'ecurie par les variables     |
//|  globales MACROBOT_BASE / HALT / DAY. Si un robot de l'ecurie     |
//|  declenche le gardien, GrokBot ferme aussi, et l'inverse.         |
//|                                                                  |
//|  RESERVE HONNETE : ~3,2 trades par an. C'est peu. Le robot ne     |
//|  gagne pas par le nombre de coups mais par la diversification --  |
//|  il est le seul de la maison a pouvoir gagner en marche baissier. |
//+------------------------------------------------------------------+
#property copyright   "Jimmy"
#property link        ""
#property version     "@@VERSION@@.00"
#property description "GrokBot @@VERSION@@ -- USDJPY deux sens, EMA 20/50, TP 1,5R. Code neuf, lignee separee."
#property strict

#include <Trade\Trade.mqh>

//===================== REGLAGES ====================================
input group "--- Strategie (valeurs validees au banc : NE PAS optimiser) ---"
input int    EmaRapide        = 20;     // EMA rapide, en jours. Plateau verifie 10/40 a 30/60
input int    EmaLente         = 50;     // EMA lente, en jours
input int    PeriodeATR       = 14;     // ATR journalier, pour la taille du stop
input double StopEnATR        = 2.0;    // stop = N x ATR. Plateau 1,5 - 3,0. C'est 1 R
input double TakeProfitEnR    = 1.5;    // TP en multiples de R. Plateau 1,0 - 2,0 (3,0 echoue)
input bool   AutoriserVente   = true;   // la raison d'etre du robot : NE PAS desactiver sans raison
input bool   AutoriserAchat   = true;
@@INPUTS_V2@@
input group "--- Risque ---"
input double RisqueParTradePct = 0.75;  // % du solde risque par trade (banc : 0,75)
input double LotMaximum        = 5.0;   // garde-fou dur, en lots
input double NotionnelMaxEquite = 2.0;  // notionnel max de ce robot, en multiples de l'equite

input group "--- Protections FTMO, partagees avec l'ecurie ---"
input double LimitePerteJourPct   = 2.50;  // gardien quotidien (FTMO tolere 5 %)
input double LimitePerteTotalePct = 8.00;  // gardien total (FTMO tolere 10 %)
input double CapitalInitial       = 0;     // 0 = solde au premier chargement
input int    MaxPositionsEcurie   = 2;     // plafond de positions, TOUS robots confondus
input string MagicsEcurie         = "@@MAGICS@@"; // magics comptes par le plafond partage (le sien est ajoute tout seul)
input long   NumeroMagique        = 20268001; // GrokBot : bloc de magics a lui

input group "--- Filtre d'annonces (fichier partage avec l'ecurie) ---"
input bool   FiltreNouvellesActif  = true;  // lit MQL5\Files\macrobot_news.txt
input int    MinutesAvantNews      = 30;
input int    MinutesApresNews      = 30;

input group "--- Affichage ---"
input bool   AffichageActif   = true;
input ENUM_BASE_CORNER AffichageCoin = CORNER_LEFT_UPPER;
input int    AffichageTaille  = 9;
input color  AffichageFond    = C'18,22,30';
input color  AffichageTexte   = clrGainsboro;
input bool   AffichageLignes  = true;   // EMA, stop et TP traces sur les prix
input bool   NotificationsPush = true;

//===================== ETAT ========================================
CTrade   trade;
int      hEmaRapide = INVALID_HANDLE;
int      hEmaLente  = INVALID_HANDLE;
int      hAtr       = INVALID_HANDLE;
datetime derniereBarre  = 0;
datetime derniereLectureNews = 0;
long     newsEpochs[];
bool     fenetreNews    = false;
bool     alerteEnvoyee  = false;
string   PANNEAU = "GROKBOT_";
long     magics[];
@@ETAT_V2@@

//===================== VARIABLES PARTAGEES =========================
// Memes noms que l'ecurie : les gardiens sont communs a toute la maison.
string CleBase()  { return("MACROBOT_BASE_" + (string)AccountInfoInteger(ACCOUNT_LOGIN)); }
string CleHalte() { return("MACROBOT_HALT_" + (string)AccountInfoInteger(ACCOUNT_LOGIN)); }
string CleJour()
  {
   MqlDateTime t;
   TimeToStruct(TimeCurrent(), t);
   return(StringFormat("MACROBOT_DAY_%04d%02d%02d_%d", t.year, t.mon, t.day,
                       AccountInfoInteger(ACCOUNT_LOGIN)));
  }
string CleAncre() { return("GROKBOT_ANCRE_" + (string)NumeroMagique + "_" + _Symbol); }

double CapitalDepart()
  {
   if(!GlobalVariableCheck(CleBase()))
      GlobalVariableSet(CleBase(), (CapitalInitial > 0) ? CapitalInitial
                                                        : AccountInfoDouble(ACCOUNT_BALANCE));
   return(GlobalVariableGet(CleBase()));
  }

//===================== OUTILS ======================================
void Avertir(string msg)
  {
   Print("GrokBot@@VERSION@@ : ", msg);
   if(!NotificationsPush) return;
   if(!SendNotification("[GrokBot@@VERSION@@ " + _Symbol + "] " + msg) && !alerteEnvoyee)
     {
      alerteEnvoyee = true;
      Print("Push non envoye. Configure ton MetaQuotes ID : Outils > Options > Notifications.");
     }
  }

double Valeur(int handle, int decalage)
  {
   if(handle == INVALID_HANDLE) return(0.0);
   double b[];
   if(CopyBuffer(handle, 0, decalage, 1, b) < 1) return(0.0);
   return(b[0]);
  }

void DecouperMagics()
  {
   string morceaux[];
   int n = StringSplit(MagicsEcurie, ',', morceaux);
   ArrayResize(magics, 0);
   for(int i = 0; i < n; i++)
     {
      string m = morceaux[i];
      StringTrimLeft(m); StringTrimRight(m);
      if(StringLen(m) == 0) continue;
      long v = StringToInteger(m);
      if(v <= 0) continue;
      int k = ArraySize(magics);
      ArrayResize(magics, k + 1);
      magics[k] = v;
     }
   int k = ArraySize(magics);              // GrokBot se compte lui-meme
   ArrayResize(magics, k + 1);
   magics[k] = NumeroMagique;
  }

bool MagicDeLEcurie(long m)
  {
   for(int i = ArraySize(magics) - 1; i >= 0; i--)
      if(magics[i] == m) return(true);
   return(false);
  }

// Plafond partage : une position par symbole compte pour une, tous robots
// confondus. Meme regle que l'ecurie, mais code ecrit ici.
int PositionsEcurie()
  {
   string vus = "";
   int n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t == 0) continue;
      if(!MagicDeLEcurie(PositionGetInteger(POSITION_MAGIC))) continue;
      string cle = "|" + PositionGetString(POSITION_SYMBOL) + ":"
                       + (string)PositionGetInteger(POSITION_MAGIC) + "|";
      if(StringFind(vus, cle) >= 0) continue;
      vus += cle;
      n++;
     }
   return(n);
  }

bool PositionActive()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) != NumeroMagique) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      return(true);
     }
   return(false);
  }

int SensPosition()      // +1 achat, -1 vente, 0 aucune
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) != NumeroMagique) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      return(PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? +1 : -1);
     }
   return(0);
  }

void FermerTout(bool toutLeCompte)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t == 0) continue;
      if(!toutLeCompte)
        {
         if(PositionGetInteger(POSITION_MAGIC) != NumeroMagique) continue;
         if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
        }
      else if(!MagicDeLEcurie(PositionGetInteger(POSITION_MAGIC))) continue;
      trade.PositionClose(t);
     }
  }

//===================== GARDIENS ====================================
// Trois niveaux, dans l'ordre : halte generale (definitive), pause du
// jour (jusqu'a demain), perte totale. Les trois s'ecrivent dans les
// variables partagees, donc l'ecurie entiere les voit.
bool ProtectionsOK()
  {
   double base   = CapitalDepart();
   double equite = AccountInfoDouble(ACCOUNT_EQUITY);
   if(base <= 0) return(true);

   if(GlobalVariableCheck(CleHalte()) && GlobalVariableGet(CleHalte()) > 0)
     {
      if(PositionActive()) FermerTout(false);
      return(false);
     }

   double perteTotale = (equite / base - 1.0) * 100.0;
   if(perteTotale <= -LimitePerteTotalePct)
     {
      GlobalVariableSet(CleHalte(), 1);
      FermerTout(true);
      Avertir(StringFormat("HALTE GENERALE : perte totale %.2f %% (limite %.2f)",
                           perteTotale, LimitePerteTotalePct));
      return(false);
     }

   if(GlobalVariableCheck(CleJour()) && GlobalVariableGet(CleJour()) > 0)
     {
      if(PositionActive()) FermerTout(false);
      return(false);
     }

   // reference du jour : equite au premier tick de la journee
   string cleRef = "GROKBOT_EQJOUR_" + (string)AccountInfoInteger(ACCOUNT_LOGIN);
   MqlDateTime t; TimeToStruct(TimeCurrent(), t);
   string cleDate = StringFormat("%04d%02d%02d", t.year, t.mon, t.day);
   string cleRefD = cleRef + "_" + cleDate;
   if(!GlobalVariableCheck(cleRefD)) GlobalVariableSet(cleRefD, equite);
   double refJour = GlobalVariableGet(cleRefD);
   if(refJour > 0)
     {
      double perteJour = (equite / refJour - 1.0) * 100.0;
      if(perteJour <= -LimitePerteJourPct)
        {
         GlobalVariableSet(CleJour(), 1);
         FermerTout(true);
         Avertir(StringFormat("PAUSE DU JOUR : %.2f %% (limite %.2f). Reprise demain.",
                              perteJour, LimitePerteJourPct));
         return(false);
        }
     }
   return(true);
  }

//===================== FILTRE D'ANNONCES ===========================
// Lit le meme macrobot_news.txt que l'ecurie (epochs UTC, une par ligne).
// Fichier absent = on ne bloque rien : le robot ne doit jamais dependre
// d'un fichier pour fonctionner.
void LireNouvelles()
  {
   if(!FiltreNouvellesActif) { fenetreNews = false; return; }
   if(TimeCurrent() - derniereLectureNews < 300) return;
   derniereLectureNews = TimeCurrent();
   int h = FileOpen("macrobot_news.txt", FILE_READ | FILE_TXT | FILE_ANSI | FILE_COMMON);
   if(h == INVALID_HANDLE) h = FileOpen("macrobot_news.txt", FILE_READ | FILE_TXT | FILE_ANSI);
   if(h == INVALID_HANDLE) { ArrayResize(newsEpochs, 0); return; }
   ArrayResize(newsEpochs, 0);
   while(!FileIsEnding(h))
     {
      string ligne = FileReadString(h);
      StringTrimLeft(ligne); StringTrimRight(ligne);
      if(StringLen(ligne) == 0) continue;
      long e = StringToInteger(ligne);
      if(e <= 0) continue;
      int k = ArraySize(newsEpochs);
      ArrayResize(newsEpochs, k + 1);
      newsEpochs[k] = e;
     }
   FileClose(h);
  }

bool DansFenetreNews()
  {
   if(!FiltreNouvellesActif) return(false);
   long maintenant = (long)TimeGMT();
   for(int i = ArraySize(newsEpochs) - 1; i >= 0; i--)
     {
      long d = newsEpochs[i] - maintenant;
      if(d <= MinutesAvantNews * 60 && -d <= MinutesApresNews * 60) return(true);
     }
   return(false);
  }

//===================== TAILLE DE POSITION ==========================
// Risque fixe en % du solde, converti en lots par la valeur du tick.
// Trois garde-fous : lot max, notionnel max, et marge disponible.
double CalculerLot(double distanceStop)
  {
   if(distanceStop <= 0) return(0.0);
   double solde   = AccountInfoDouble(ACCOUNT_BALANCE);
   double risque$ = solde * RisqueParTradePct / 100.0;
   double tickV   = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickS   = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickV <= 0 || tickS <= 0) return(0.0);
   double perteParLot = (distanceStop / tickS) * tickV;
   if(perteParLot <= 0) return(0.0);
   double lot = risque$ / perteParLot;

   double pas = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double mini = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxi = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   if(pas > 0) lot = MathFloor(lot / pas) * pas;
   if(lot > LotMaximum) lot = LotMaximum;
   if(maxi > 0 && lot > maxi) lot = maxi;

   // notionnel : ce robot ne prend jamais plus de N x l'equite
   if(NotionnelMaxEquite > 0)
     {
      double contrat = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE);
      double prix    = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double equite  = AccountInfoDouble(ACCOUNT_EQUITY);
      if(contrat > 0 && prix > 0 && equite > 0)
        {
         double lotMax = NotionnelMaxEquite * equite / (contrat * prix);
         if(pas > 0) lotMax = MathFloor(lotMax / pas) * pas;
         if(lot > lotMax) lot = lotMax;
        }
     }
   if(mini > 0 && lot < mini) return(0.0);   // trop petit pour etre pris : on s'abstient
   return(lot);
  }

bool MargeSuffisante(int sens, double lot)
  {
   double marge = 0.0;
   ENUM_ORDER_TYPE type = (sens > 0) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   double prix = (sens > 0) ? SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                            : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(!OrderCalcMargin(type, _Symbol, lot, prix, marge)) return(true);   // doute : on laisse passer
   return(marge < AccountInfoDouble(ACCOUNT_MARGIN_FREE) * 0.5);
  }

//===================== ENTREE ======================================
void Entrer(int sens, double atr, string raison)
  {
   if(sens > 0 && !AutoriserAchat) return;
   if(sens < 0 && !AutoriserVente) return;
   if(atr <= 0) return;
   if(PositionsEcurie() >= MaxPositionsEcurie)
     { Print("GrokBot : entree refusee, plafond d'ecurie atteint"); return; }
   if(DansFenetreNews())
     { Print("GrokBot : entree refusee, fenetre d'annonce"); return; }

   double R    = StopEnATR * atr;
   double prix = (sens > 0) ? SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                            : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(prix <= 0) return;
   double sl = (sens > 0) ? prix - R : prix + R;
   double tp = 0.0;
   if(TakeProfitEnR > 0) tp = (sens > 0) ? prix + TakeProfitEnR * R : prix - TakeProfitEnR * R;

   // le courtier impose une distance minimale entre le prix et les niveaux
   double distMin = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
   if(MathAbs(prix - sl) <= distMin) { Print("GrokBot : stop trop proche du prix, entree annulee"); return; }

   double lot = CalculerLot(R);
   if(lot <= 0) { Print("GrokBot : lot nul (risque, notionnel ou volume minimal)"); return; }
   if(!MargeSuffisante(sens, lot)) { Print("GrokBot : marge insuffisante"); return; }

   sl = NormalizeDouble(sl, _Digits);
   tp = (tp > 0) ? NormalizeDouble(tp, _Digits) : 0.0;
   bool ok = (sens > 0) ? trade.Buy(lot, _Symbol, 0.0, sl, tp, "GrokBot@@VERSION@@ " + raison)
                        : trade.Sell(lot, _Symbol, 0.0, sl, tp, "GrokBot@@VERSION@@ " + raison);
   if(!ok)
     { Print("GrokBot : ordre refuse, code ", trade.ResultRetcode(), " ", trade.ResultRetcodeDescription()); return; }
   GlobalVariableSet(CleAncre(), atr);   // ATR d'entree, garde pour l'affichage et la v2
   Avertir(StringFormat("%s %.2f lot @ %s | stop %s | TP %s (%s)",
                        (sens > 0 ? "ACHAT" : "VENTE"), lot,
                        DoubleToString(prix, _Digits), DoubleToString(sl, _Digits),
                        (tp > 0 ? DoubleToString(tp, _Digits) : "aucun"), raison));
  }
@@FONCTIONS_V2@@
//===================== AFFICHAGE ===================================
string txtPanneau[];
color  couleurPanneau[];

void Empiler(int ligne, string texte, color teinte)
  {
   if(ArraySize(txtPanneau) <= ligne)
     { ArrayResize(txtPanneau, ligne + 1); ArrayResize(couleurPanneau, ligne + 1); }
   txtPanneau[ligne] = texte;
   couleurPanneau[ligne] = teinte;
  }

void Etiquette(int ligne, string texte, color teinte)
  {
   string nom = PANNEAU + "L" + (string)ligne;
   if(ObjectFind(0, nom) < 0)
     {
      ObjectCreate(0, nom, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, nom, OBJPROP_CORNER, AffichageCoin);
      ObjectSetInteger(0, nom, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, nom, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, nom, OBJPROP_ZORDER, 10);
      ObjectSetString(0, nom, OBJPROP_FONT, "Consolas");
     }
   ObjectSetInteger(0, nom, OBJPROP_XDISTANCE, 18);
   ObjectSetInteger(0, nom, OBJPROP_YDISTANCE, 20 + ligne * (AffichageTaille + 6));
   ObjectSetInteger(0, nom, OBJPROP_FONTSIZE, AffichageTaille);
   ObjectSetInteger(0, nom, OBJPROP_COLOR, teinte);
   ObjectSetString(0, nom, OBJPROP_TEXT, texte);
  }

void Fond(int lignes)
  {
   string nom = PANNEAU + "FOND";
   if(ObjectFind(0, nom) < 0)
     {
      ObjectCreate(0, nom, OBJ_RECTANGLE_LABEL, 0, 0, 0);
      ObjectSetInteger(0, nom, OBJPROP_CORNER, AffichageCoin);
      ObjectSetInteger(0, nom, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, nom, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, nom, OBJPROP_BACK, false);
      ObjectSetInteger(0, nom, OBJPROP_ZORDER, 0);
      ObjectSetInteger(0, nom, OBJPROP_BORDER_TYPE, BORDER_FLAT);
     }
   ObjectSetInteger(0, nom, OBJPROP_XDISTANCE, 10);
   ObjectSetInteger(0, nom, OBJPROP_YDISTANCE, 12);
   ObjectSetInteger(0, nom, OBJPROP_XSIZE, 28 * AffichageTaille);
   ObjectSetInteger(0, nom, OBJPROP_YSIZE, 20 + lignes * (AffichageTaille + 6));
   ObjectSetInteger(0, nom, OBJPROP_BGCOLOR, AffichageFond);
   ObjectSetInteger(0, nom, OBJPROP_COLOR, AffichageFond);
  }

void Ligne(string cle, double prix, color teinte, ENUM_LINE_STYLE style)
  {
   string nom = PANNEAU + "P_" + cle;
   if(prix <= 0)
     { if(ObjectFind(0, nom) >= 0) ObjectDelete(0, nom); return; }
   if(ObjectFind(0, nom) < 0)
     {
      ObjectCreate(0, nom, OBJ_HLINE, 0, 0, prix);
      ObjectSetInteger(0, nom, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, nom, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, nom, OBJPROP_BACK, true);
      ObjectSetInteger(0, nom, OBJPROP_WIDTH, 1);
     }
   ObjectSetDouble(0, nom, OBJPROP_PRICE, prix);
   ObjectSetInteger(0, nom, OBJPROP_COLOR, teinte);
   ObjectSetInteger(0, nom, OBJPROP_STYLE, style);
   ObjectSetString(0, nom, OBJPROP_TOOLTIP, cle + " " + DoubleToString(prix, _Digits));
  }

void EffacerAffichage() { ObjectsDeleteAll(0, PANNEAU); ChartRedraw(); }

// L'affichage MONTRE, il ne decide rien. Inerte hors mode visuel, et
// limite a un rafraichissement par quart de seconde.
void Afficher()
  {
   static bool efface = false;
   if(!AffichageActif) { if(!efface) { EffacerAffichage(); efface = true; } return; }
   efface = false;
   if(MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_VISUAL_MODE)) return;
   static uint dernier = 0;
   uint tick = GetTickCount();
   if(dernier != 0 && (tick - dernier) < 250) return;
   dernier = tick;

   double base   = CapitalDepart();
   double equite = AccountInfoDouble(ACCOUNT_EQUITY);
   double avance = (base > 0) ? (equite / base - 1.0) * 100.0 : 0.0;
   bool   halte  = GlobalVariableCheck(CleHalte()) && GlobalVariableGet(CleHalte()) > 0;
   bool   pause  = GlobalVariableCheck(CleJour())  && GlobalVariableGet(CleJour())  > 0;

   double er = Valeur(hEmaRapide, 1), el = Valeur(hEmaLente, 1), atr = Valeur(hAtr, 1);
   int    sens = SensPosition();
   double lots = 0.0, pnl = 0.0, entree = 0.0, sl = 0.0, tp = 0.0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) != NumeroMagique) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      lots  += PositionGetDouble(POSITION_VOLUME);
      pnl   += PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
      entree = PositionGetDouble(POSITION_PRICE_OPEN);
      sl     = PositionGetDouble(POSITION_SL);
      tp     = PositionGetDouble(POSITION_TP);
     }

   color vert = clrLimeGreen, rouge = clrTomato, jaune = clrGold, gris = AffichageTexte;
   ArrayResize(txtPanneau, 0); ArrayResize(couleurPanneau, 0);
   int L = 0;
   Empiler(L++, "GROKBOT @@VERSION@@   " + _Symbol + "   deux sens   (D1)", clrDeepSkyBlue);
   Empiler(L++, StringFormat("compte %+.2f %%   gardiens jour -%.2f / total -%.1f   %s",
                avance, LimitePerteJourPct, LimitePerteTotalePct,
                halte ? "HALTE" : (pause ? "PAUSE DU JOUR" : "actifs")),
           (halte || pause) ? rouge : vert);
   Empiler(L++, "----------------------------------------", gris);
   if(sens != 0)
     {
      Empiler(L++, StringFormat("%s  %.2f lot  %+.2f $",
                   (sens > 0 ? "ACHAT" : "VENTE"), lots, pnl), (pnl >= 0) ? vert : rouge);
      Empiler(L++, StringFormat("entree %s  stop %s  TP %s",
                   DoubleToString(entree, _Digits), DoubleToString(sl, _Digits),
                   (tp > 0 ? DoubleToString(tp, _Digits) : "aucun")), gris);
     }
   else
     {
      Empiler(L++, "aucune position", gris);
      string att = (er > 0 && el > 0)
                 ? StringFormat("EMA%d %s EMA%d : %s", EmaRapide,
                                (er > el ? ">" : "<"), EmaLente,
                                (er > el ? "biais ACHAT" : "biais VENTE"))
                 : "EMA indisponibles";
      Empiler(L++, att, gris);
@@AFFICHAGE_V2@@     }
   Empiler(L++, StringFormat("EMA%d %s   EMA%d %s   ATR %s", EmaRapide,
                DoubleToString(er, _Digits), EmaLente, DoubleToString(el, _Digits),
                DoubleToString(atr, _Digits)), gris);
   Empiler(L++, "----------------------------------------", gris);
   Empiler(L++, StringFormat("ecurie %d/%d   annonces %s   risque %.2f %%",
                PositionsEcurie(), MaxPositionsEcurie,
                DansFenetreNews() ? "FENETRE" : "libre", RisqueParTradePct),
           DansFenetreNews() ? jaune : gris);

   Fond(L);
   for(int i = 0; i < L; i++) Etiquette(i, txtPanneau[i], couleurPanneau[i]);
   if(AffichageLignes)
     {
      Ligne("ema_rapide", er, clrDodgerBlue, STYLE_SOLID);
      Ligne("ema_lente",  el, clrSlateGray,  STYLE_SOLID);
      Ligne("stop",       sl, clrTomato,     STYLE_SOLID);
      Ligne("tp",         tp, clrLimeGreen,  STYLE_DASH);
@@LIGNES_V2@@     }
   ChartRedraw();
  }

//===================== CYCLE DE VIE ================================
int OnInit()
  {
   if(MQLInfoInteger(MQL_TESTER)) GlobalVariablesDeleteAll("MACROBOT_");
   if(MQLInfoInteger(MQL_TESTER)) GlobalVariablesDeleteAll("GROKBOT_");

   if(StringFind(_Symbol, "@@PAIRE@@") < 0)
      Print("GrokBot : ATTENTION, ce fichier est calibre pour @@PAIRE@@ et tourne sur ", _Symbol);
   if(EmaRapide >= EmaLente)
     { Print("GrokBot : EmaRapide doit etre < EmaLente."); return(INIT_PARAMETERS_INCORRECT); }
   if(StopEnATR <= 0 || RisqueParTradePct <= 0)
     { Print("GrokBot : StopEnATR et RisqueParTradePct doivent etre > 0."); return(INIT_PARAMETERS_INCORRECT); }

   trade.SetExpertMagicNumber(NumeroMagique);
   trade.SetDeviationInPoints(30);
   DecouperMagics();

   hEmaRapide = iMA(_Symbol, PERIOD_D1, EmaRapide, 0, MODE_EMA, PRICE_CLOSE);
   hEmaLente  = iMA(_Symbol, PERIOD_D1, EmaLente,  0, MODE_EMA, PRICE_CLOSE);
   hAtr       = iATR(_Symbol, PERIOD_D1, PeriodeATR);
   if(hEmaRapide == INVALID_HANDLE || hEmaLente == INVALID_HANDLE || hAtr == INVALID_HANDLE)
     { Print("GrokBot : indicateurs indisponibles."); return(INIT_FAILED); }

   CapitalDepart();
   Print("GrokBot@@VERSION@@ charge | ", _Symbol, " | EMA ", EmaRapide, "/", EmaLente,
         " | stop ", StopEnATR, " ATR | TP ", TakeProfitEnR, " R | risque ",
         RisqueParTradePct, " % | capital de depart ",
         DoubleToString(GlobalVariableGet(CleBase()), 2));
@@INIT_V2@@   EventSetTimer(60);
   Afficher();
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
   EffacerAffichage();
   if(hEmaRapide != INVALID_HANDLE) IndicatorRelease(hEmaRapide);
   if(hEmaLente  != INVALID_HANDLE) IndicatorRelease(hEmaLente);
   if(hAtr       != INVALID_HANDLE) IndicatorRelease(hAtr);
  }

void OnTimer()
  {
   LireNouvelles();
   ProtectionsOK();
   Afficher();
  }

void OnTick()
  {
   Afficher();
   if(!ProtectionsOK()) return;
   LireNouvelles();

   // une seule decision par bougie journaliere fermee
   datetime barre = iTime(_Symbol, PERIOD_D1, 0);
   if(barre == derniereBarre) return;
   derniereBarre = barre;

   double atr = Valeur(hAtr, 1);
   if(atr <= 0) return;
@@TICK_V2@@
   if(PositionActive()) return;      // stop et TP sont chez le courtier

   // croisement sur les DEUX dernieres bougies journalieres fermees
   double er1 = Valeur(hEmaRapide, 1), er2 = Valeur(hEmaRapide, 2);
   double el1 = Valeur(hEmaLente,  1), el2 = Valeur(hEmaLente,  2);
   if(er1 <= 0 || er2 <= 0 || el1 <= 0 || el2 <= 0) return;

   if(er1 > el1 && er2 <= el2) Entrer(+1, atr, "croisement haussier");
   if(er1 < el1 && er2 >= el2) Entrer(-1, atr, "croisement baissier");
  }

void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result)
  {
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD) return;
   if(!HistoryDealSelect(trans.deal)) return;
   if(HistoryDealGetInteger(trans.deal, DEAL_MAGIC) != NumeroMagique) return;
   if(HistoryDealGetString(trans.deal, DEAL_SYMBOL) != _Symbol) return;
   if(HistoryDealGetInteger(trans.deal, DEAL_ENTRY) != DEAL_ENTRY_OUT) return;

   double profit = HistoryDealGetDouble(trans.deal, DEAL_PROFIT)
                 + HistoryDealGetDouble(trans.deal, DEAL_SWAP)
                 + HistoryDealGetDouble(trans.deal, DEAL_COMMISSION);
   double prix   = HistoryDealGetDouble(trans.deal, DEAL_PRICE);
   long   type   = HistoryDealGetInteger(trans.deal, DEAL_TYPE);
   int    sens   = (type == DEAL_TYPE_SELL) ? +1 : -1;   // sortie inverse de l'entree
   Avertir(StringFormat("SORTIE %s @ %s | P/L %.2f $", (sens > 0 ? "ACHAT" : "VENTE"),
                        DoubleToString(prix, _Digits), profit));
@@SORTIE_V2@@   if(GlobalVariableCheck(CleAncre())) GlobalVariableDel(CleAncre());
  }
//+------------------------------------------------------------------+
