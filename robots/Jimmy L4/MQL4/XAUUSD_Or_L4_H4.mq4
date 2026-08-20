//+------------------------------------------------------------------+
//|  XAUUSD Or L3 H4
//|  Ecurie L3 de Jimmy — version MetaTrader 4 (MQL4)
//|  Regles validees par backtest : gardien -2,5 %/jour, plafond
//|  d'ecurie de 2 piles, repli fib 20-80 % + RSI<55, TP 1,5R + re-entree 0,25xATR.
//+------------------------------------------------------------------+
#property strict

input double RisqueParTradePct     = 2.0;   // L4 : or 2,0 (plateau valide 2 moteurs, falaise a 2,5)   // Risque par trade en % du solde
input double LimitePerteJourPct    = 2.5;    // Coupe-circuit perte du jour (FTMO = 5)
input double LimitePerteTotalePct  = 8.0;    // Coupe-circuit perte totale (FTMO = 10)
input int    MaxPositionsEcurie    = 2;      // Plafond global de piles ouvertes
input int    NumeroMagique         = 20261015; // Identifiant du robot
input int    Glissement            = 30;     // Slippage tolere (points)
input int    SwingLookback        = 60;    // bougies du swing analyse
input double FibLo                = 0.20;  // zone de repli basse
input double FibHi                = 0.80;  // zone de repli haute
input double RsiPull              = 55.0;  // RSI sous ce niveau puis qui remonte
input double StopAtrMult          = 3.0;   // stop = N x ATR
input double TpR                  = 1.5;   // TP en multiples de R
input double RetraceReentree      = 0.25;  // repli exige pour la re-entree
input bool   BreakevenActif       = true;  // stop au point mort a +1R
input bool   BiaisMacroDepuisFichier = true; // lire macrobot_bias.txt
input bool   AchatPermisSansFichier  = true; // fichier absent -> achats permis
input bool   FiltreNouvellesActif    = true; // bloquer autour des annonces USD
input int    MinutesBlocageAvantNews = 30;
input int    MinutesBlocageApresNews = 30;
input bool   ProtegerPositionsPendantNews = true; // serrer les stops en fenetre
input bool   FacteurVolActif       = true;   // moduler le risque selon la volatilite
input bool   JournalActif          = true;   // journal de reflexion (Files\Ecurie_Journal)
input bool   PlafondCorrelationActif = true;  // un seul metal/indice a la fois (crises)
input bool   ModeChallengeActif = true;  // L4 : ACTIF par defaut (valide scan 21 aout, 2 moteurs)
input double ThrottleChallenge  = 0.75;  // L3+ : facteur de risque sous la moyenne 20 j
input bool   FiltreDollarActif  = true;  // L4.1 : pas d'entree or quand le dollar est fort (DXY > moy. 200 j)
input bool   RelireFiltreAvantTrade = true; // L4.1 : relecture fraiche du fichier juste avant chaque trade
input bool   NotificationsPush     = true;   // push cellulaire (MetaQuotes ID)

// ---- etat interne ----
double   soldeReference   = 0.0;
double   equiteDebutJour  = 0.0;
int      jourCourant      = -1;
bool     arretDefinitif   = false;
bool     avisJourFait     = false;
datetime derniereBarre    = 0;
double   facteurVol       = 1.0;
datetime derniereLectureVol   = 0;
datetime derniereLectureBiais = 0;
datetime derniereLectureNews  = 0;
bool     biaisMacroOK     = true;
bool     newsBloquaitAvant = false;
datetime prochainesNews[];
int      ticketSuivi      = 0;
double   tpSuivi          = 0.0;
double   attenteReentree  = 0.0;
double   plancherSwing    = 0.0;

string BaseGV() { return("MACROBOT_BASE_" + IntegerToString(AccountNumber())); }
string HaltGV() { return("MACROBOT_HALT_" + IntegerToString(AccountNumber())); }
string DayGV()  { return("MACROBOT_DAY_"  + IntegerToString(AccountNumber())); }

//+------------------------------------------------------------------+
//| Notifications (log + push cellulaire)                            |
//+------------------------------------------------------------------+
void Notifier(string msg)
  {
   Print(msg);
   if(!NotificationsPush) return;
   static bool avertiEchec = false;
   if(!SendNotification("Or L3 : " + msg) && !avertiEchec)
     {
      Print("Push non envoye. Configure ton MetaQuotes ID : Outils > Options > Notifications.");
      avertiEchec = true;
     }
  }

//+------------------------------------------------------------------+
//| Journal de reflexion : une ligne par bougie                      |
//+------------------------------------------------------------------+
void EcrireJournal(string texte)
  {
   if(!JournalActif) return;
   string fichier = "Ecurie_Journal\\" + WindowExpertName() + ".txt";
   int fh = FileOpen(fichier, FILE_READ | FILE_WRITE | FILE_TXT | FILE_ANSI);
   if(fh == INVALID_HANDLE) return;
   FileSeek(fh, 0, SEEK_END);
   FileWrite(fh, TimeToString(TimeCurrent(), TIME_DATE | TIME_MINUTES) + " | " + texte);
   FileClose(fh);
  }

//+------------------------------------------------------------------+
//| Plafond d'ecurie : on compte les PILES (magic+symbole), pas les   |
//| ordres — un robot qui pyramide occupe UN seul siege.              |
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| PLAFOND DE CORRELATION (valide sur 99 ans de crises)              |
//| Un seul robot de la famille metal/indice (or, Nasdaq) en position |
//| a la fois : evite la double exposition au meme choc de liquidite  |
//| (septembre 2011 : or ET indices en chute simultanee = compte mort)|
//| Test : 2011 de -8,0 % (mort) a -2,2 % ; crises positives 5/7->6/7.|
//+------------------------------------------------------------------+
bool EstMetalOuIndice(string symbole)
  {
   string s = symbole;
   StringToUpper(s);
   if(StringFind(s, "XAU") >= 0) return(true);
   if(StringFind(s, "XAG") >= 0) return(true);
   if(StringFind(s, "US100") >= 0) return(true);
   if(StringFind(s, "NAS") >= 0) return(true);
   if(StringFind(s, "US30") >= 0) return(true);
   if(StringFind(s, "US500") >= 0) return(true);
   if(StringFind(s, "SPX") >= 0) return(true);
   if(StringFind(s, "GER") >= 0 || StringFind(s, "DE30") >= 0) return(true);
   return(false);
  }

//+------------------------------------------------------------------+
//| L4.1 FILTRE DOLLAR : lit Ecurie_DXY.txt ("1 AAAA-MM-JJ" = dollar |
//| fort, or bloque). Signal absent ou vieux de plus de 7 jours ->   |
//| ne bloque JAMAIS (securite fail-open). Valide 21 aout : +1,9 a   |
//| +3,2 pts sur 10 ans, les 2 moteurs, modes ON et OFF.             |
//+------------------------------------------------------------------+
bool DollarFort(bool forcer = false)
  {
   if(!FiltreDollarActif) return(false);
   static datetime dernierLu = 0;                    // relecture du fichier aux
   static bool     cacheFort = false;                // 30 minutes (cache, pas de
   if(!forcer && dernierLu != 0 && TimeCurrent() - dernierLu < 1800)   // disque a chaque tick)
      return(cacheFort);
   dernierLu = TimeCurrent();
   cacheFort = false;
   int fh = FileOpen("Ecurie_DXY.txt", FILE_READ | FILE_TXT | FILE_ANSI);
   if(fh == INVALID_HANDLE) return(false);
   string ligne = FileReadString(fh);
   FileClose(fh);
   if(StringSubstr(ligne, 0, 1) != "1") return(false);
   int esp = StringFind(ligne, " ");
   if(esp > 0)
     {
      datetime d = StringToTime(StringSubstr(ligne, esp + 1));
      if(d > 0 && TimeCurrent() - d > 7 * 86400) return(false);   // signal perime
     }
   cacheFort = true;
   return(true);
  }

bool FamilleCorreleeOccupee()
  {
   if(!PlafondCorrelationActif) return(false);
   if(!EstMetalOuIndice(Symbol())) return(false);
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) continue;
      int m = OrderMagicNumber();
      if(m != 20260815 && m != 20260817 && m != 20260818 &&
         m != 20261015 && m != 20261017 && m != 20261018) continue;
      if(OrderSymbol() == Symbol()) continue;
      if(EstMetalOuIndice(OrderSymbol())) return(true);
     }
   return(false);
  }

int ComptePositionsEcurie()
  {
   string vues = "";
   int n = 0;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) continue;
      int m = OrderMagicNumber();
      if(m != 20261015 && m != 20261017 && m != 20261018) continue;
      string cle = "|" + IntegerToString(m) + ":" + OrderSymbol() + "|";
      if(StringFind(vues, cle) >= 0) continue;
      vues += cle;
      n++;
     }
   return(n);
  }

//+------------------------------------------------------------------+
//| Positions du robot (symbole + magic)                             |
//+------------------------------------------------------------------+
int NombreUnites()
  {
   int n = 0;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) continue;
      if(OrderSymbol() != Symbol() || OrderMagicNumber() != NumeroMagique) continue;
      if(OrderType() != OP_BUY) continue;
      n++;
     }
   return(n);
  }

bool PositionOuverte() { return(NombreUnites() > 0); }

double PrixDerniereUnite()   // prix d'ouverture le plus HAUT
  {
   double p = 0.0;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) continue;
      if(OrderSymbol() != Symbol() || OrderMagicNumber() != NumeroMagique) continue;
      if(OrderType() != OP_BUY) continue;
      if(OrderOpenPrice() > p) p = OrderOpenPrice();
     }
   return(p);
  }

double LotUnite()            // lot de la 1re unite (prix d'ouverture le plus BAS)
  {
   double p = 0.0, lot = 0.0;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) continue;
      if(OrderSymbol() != Symbol() || OrderMagicNumber() != NumeroMagique) continue;
      if(OrderType() != OP_BUY) continue;
      if(p == 0.0 || OrderOpenPrice() < p) { p = OrderOpenPrice(); lot = OrderLots(); }
     }
   return(lot);
  }

void AppliquerStopCommun(double niveau)
  {
   double distMin = MarketInfo(Symbol(), MODE_STOPLEVEL) * Point;
   if(niveau > Bid - distMin) niveau = Bid - distMin;
   niveau = NormalizeDouble(niveau, Digits);
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) continue;
      if(OrderSymbol() != Symbol() || OrderMagicNumber() != NumeroMagique) continue;
      if(OrderType() != OP_BUY) continue;
      if(MathAbs(niveau - OrderStopLoss()) < Point) continue;   // anti-doublon
      if(niveau > OrderStopLoss() + Point)
         if(!OrderModify(OrderTicket(), OrderOpenPrice(), niveau, OrderTakeProfit(), 0, clrBlue))
            Print("Echec OrderModify ticket ", OrderTicket(), " erreur ", GetLastError());
     }
  }

void FermerPositions(string raison)
  {
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) continue;
      if(OrderSymbol() != Symbol() || OrderMagicNumber() != NumeroMagique) continue;
      if(OrderType() != OP_BUY) continue;
      if(OrderClose(OrderTicket(), OrderLots(), Bid, Glissement, clrRed))
         Notifier("Fermeture (" + raison + ") " + DoubleToString(OrderLots(), 2) + " lot");
     }
   ticketSuivi = 0;
  }

//+------------------------------------------------------------------+
//| Taille de position selon le risque et la distance au stop        |
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| L3+ MODE CHALLENGE (throttle d'equite, Seykota) : quand l'equite  |
//| du compte passe sous sa moyenne des 20 derniers jours, les        |
//| nouvelles entrees prennent un risque reduit. Valide en backtest : |
//| challenges morts 13 % -> 6 % pour -1,9 pt de rendement annuel.    |
//+------------------------------------------------------------------+
double HistoEquite[20];
int    HistoIndex = 0;
bool   HistoPlein = false;
datetime dernierReleve = 0;

void ReleverEquite()
  {
   datetime jour = iTime(Symbol(), PERIOD_D1, 0);
   if(jour == dernierReleve) return;
   dernierReleve = jour;
   HistoEquite[HistoIndex] = AccountEquity();
   HistoIndex = (HistoIndex + 1) % 20;
   if(HistoIndex == 0) HistoPlein = true;
  }

double FacteurChallenge()
  {
   if(!ModeChallengeActif) return(1.0);
   if(!HistoPlein) return(1.0);
   double somme = 0;
   for(int i = 0; i < 20; i++) somme += HistoEquite[i];
   double moyenne = somme / 20.0;
   if(moyenne > 0 && AccountEquity() < moyenne) return(ThrottleChallenge);
   return(1.0);
  }

double CalculerLot(double distanceSL)
  {
   if(distanceSL <= 0) return(0.0);
   double valeurTick = MarketInfo(Symbol(), MODE_TICKVALUE);
   double tailleTick = MarketInfo(Symbol(), MODE_TICKSIZE);
   double risque = AccountBalance() * RisqueParTradePct / 100.0 * facteurVol * FacteurChallenge();
   double perteParLot = 0.0;
   if(valeurTick > 0 && tailleTick > 0)
      perteParLot = distanceSL / tailleTick * valeurTick;
   if(perteParLot <= 0)
     {
      // FALLBACK : MODE_TICKVALUE peut etre 0 sur les CFD/crypto en MT4.
      // Nos symboles cotent en USD : perte par lot = distance x taille de contrat.
      double tailleContrat = MarketInfo(Symbol(), MODE_LOTSIZE);
      if(tailleContrat > 0)
        {
         perteParLot = distanceSL * tailleContrat;
         Print("AVERTISSEMENT: tick value invalide (", DoubleToString(valeurTick, 5),
               ") — fallback contrat=", DoubleToString(tailleContrat, 2));
        }
     }
   if(perteParLot <= 0)
     {
      Print("REFUS D'ENTREE: impossible de calculer la perte par lot (tickValue=",
            DoubleToString(valeurTick, 5), " tickSize=", DoubleToString(tailleTick, 5), ")");
      return(0.0);
     }
   double lot = risque / perteParLot;
   double pas = MarketInfo(Symbol(), MODE_LOTSTEP);
   double mini = MarketInfo(Symbol(), MODE_MINLOT);
   double maxi = MarketInfo(Symbol(), MODE_MAXLOT);
   if(pas > 0) lot = MathFloor(lot / pas) * pas;
   if(lot < mini)
     {
      Print("REFUS D'ENTREE: lot calcule ", DoubleToString(lot, 4),
            " sous le minimum ", DoubleToString(mini, 2), " — risque trop petit pour ce stop.");
      return(0.0);
     }
   if(lot > maxi) lot = maxi;
   lot = NormalizeDouble(lot, 2);

   // L3 : verification de la MARGE (sinon erreur 134, ordre perdu en silence)
   int essais = 0;
   while(lot >= mini && essais < 12)
     {
      ResetLastError();
      double libre = AccountFreeMarginCheck(Symbol(), OP_BUY, lot);
      if(libre > 0 && GetLastError() != 134) return(lot);
      lot = NormalizeDouble(lot - MathMax(pas, lot * 0.2), 2);   // on reduit
      essais++;
     }
   Print("Marge insuffisante pour ouvrir : ordre annule (lot demande trop gros).");
   return(0.0);
  }

//+------------------------------------------------------------------+
//| COUPE-CIRCUITS partages (variables globales du terminal)         |
//+------------------------------------------------------------------+
bool VerifierProtections()
  {
   if(GlobalVariableCheck(HaltGV()) && GlobalVariableGet(HaltGV()) > 0)
     {
      if(PositionOuverte()) FermerPositions("arret definitif");
      return(false);
     }
   if(!GlobalVariableCheck(BaseGV()))
      GlobalVariableSet(BaseGV(), AccountBalance());
   soldeReference = GlobalVariableGet(BaseGV());

   int jour = TimeDay(TimeCurrent()) + 100 * TimeMonth(TimeCurrent());
   if(jour != jourCourant)
     {
      jourCourant = jour;
      equiteDebutJour = AccountEquity();
      GlobalVariableSet(DayGV(), equiteDebutJour);
      avisJourFait = false;
     }
   else if(GlobalVariableCheck(DayGV()))
      equiteDebutJour = GlobalVariableGet(DayGV());

   double equite = AccountEquity();
   if(soldeReference > 0 && equite <= soldeReference * (1.0 - LimitePerteTotalePct / 100.0))
     {
      GlobalVariableSet(HaltGV(), 1);
      if(PositionOuverte()) FermerPositions("perte totale");
      Notifier("ARRET DEFINITIF : perte totale de " + DoubleToString(LimitePerteTotalePct, 1) + " % atteinte.");
      return(false);
     }
   if(equiteDebutJour > 0 && equite <= equiteDebutJour * (1.0 - LimitePerteJourPct / 100.0))
     {
      if(PositionOuverte()) FermerPositions("perte du jour");
      if(!avisJourFait)
        {
         Notifier("PAUSE : perte de " + DoubleToString(LimitePerteJourPct, 1) + " % du jour atteinte.");
         avisJourFait = true;
        }
      return(false);
     }
   return(true);
  }

//+------------------------------------------------------------------+
//| Lectures des fichiers du pipeline (Files\macrobot_*.txt)         |
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
      double f = StrToDouble(StringSubstr(ligne, 8));
      if(f >= 0.5 && f <= 1.5)
        {
         if(MathAbs(f - facteurVol) > 0.01)
            Print("Facteur de volatilite mis a jour : " + DoubleToString(f, 2));
         facteurVol = f;
        }
     }
  }

void LireBiaisMacro()
  {
   if(!BiaisMacroDepuisFichier) { biaisMacroOK = true; return; }
   if(TimeCurrent() - derniereLectureBiais < 60) return;
   derniereLectureBiais = TimeCurrent();
   int fh = FileOpen("macrobot_bias.txt", FILE_READ | FILE_TXT | FILE_ANSI);
   if(fh == INVALID_HANDLE) { biaisMacroOK = AchatPermisSansFichier; return; }
   string contenu = "";
   while(!FileIsEnding(fh)) contenu += FileReadString(fh) + ";";
   FileClose(fh);
   int p = StringFind(contenu, "GOLD=");
   if(p < 0) { biaisMacroOK = AchatPermisSansFichier; return; }
   string v = StringSubstr(contenu, p + 5, 1);
   biaisMacroOK = (v == "1");
  }

void LireNouvelles()
  {
   if(!FiltreNouvellesActif) return;
   if(TimeCurrent() - derniereLectureNews < 60) return;
   derniereLectureNews = TimeCurrent();
   int fh = FileOpen("macrobot_news.txt", FILE_READ | FILE_TXT | FILE_ANSI);
   if(fh == INVALID_HANDLE) return;
   ArrayResize(prochainesNews, 0);
   while(!FileIsEnding(fh))
     {
      string ligne = FileReadString(fh);
      if(StringFind(ligne, "EVENT=") == 0)
        {
         datetime t = (datetime)StrToInteger(StringSubstr(ligne, 6));
         int n = ArraySize(prochainesNews);
         ArrayResize(prochainesNews, n + 1);
         prochainesNews[n] = t;
        }
     }
   FileClose(fh);
  }

bool BloqueParNouvelles()
  {
   if(!FiltreNouvellesActif) return(false);
   datetime maintenant = TimeGMT();
   for(int i = 0; i < ArraySize(prochainesNews); i++)
     {
      if(maintenant >= prochainesNews[i] - MinutesBlocageAvantNews * 60 &&
         maintenant <= prochainesNews[i] + MinutesBlocageApresNews * 60)
         return(true);
     }
   return(false);
  }

void ProtegerPositionsNews()
  {
   if(!ProtegerPositionsPendantNews || !newsBloquaitAvant) return;
   double atr = iATR(Symbol(), 0, 14, 1);
   if(atr <= 0) return;
   double distMin = MarketInfo(Symbol(), MODE_STOPLEVEL) * Point;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) continue;
      if(OrderSymbol() != Symbol() || OrderMagicNumber() != NumeroMagique) continue;
      if(OrderType() != OP_BUY) continue;
      double cible = (Bid > OrderOpenPrice()) ? OrderOpenPrice() : Bid - 0.5 * atr;
      if(cible > Bid - distMin) cible = Bid - distMin;
      cible = NormalizeDouble(cible, Digits);
      if(cible > OrderStopLoss() + Point)
         if(!OrderModify(OrderTicket(), OrderOpenPrice(), cible, OrderTakeProfit(), 0, clrOrange))
            Print("Echec OrderModify ticket ", OrderTicket(), " erreur ", GetLastError());
     }
  }

//+------------------------------------------------------------------+
//| Detection d'un TP encaisse (MQL4 n'a pas OnTradeTransaction) :    |
//| on suit le ticket et on interroge l'historique quand il disparait |
//+------------------------------------------------------------------+
void VerifierTpEncaisse()
  {
   if(ticketSuivi == 0) return;
   if(OrderSelect(ticketSuivi, SELECT_BY_TICKET, MODE_TRADES))
      if(OrderCloseTime() == 0) return;          // toujours ouvert
   if(!OrderSelect(ticketSuivi, SELECT_BY_TICKET, MODE_HISTORY)) return;
   if(OrderCloseTime() == 0) return;
   double tp = OrderTakeProfit();
   double clot = OrderClosePrice();
   if(tp > 0 && MathAbs(clot - tp) <= 3 * Point * MathPow(10, Digits - 4 > 0 ? 1 : 0))
     {
      attenteReentree = tp;                       // TP touche -> re-entree armee
      Notifier("TP encaisse a " + DoubleToString(tp, Digits) + " : re-entree armee.");
     }
   else
     {
      attenteReentree = 0.0;
      plancherSwing = 0.0;
     }
   ticketSuivi = 0;
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   EventSetTimer(60);
   // Dans le STRATEGY TESTER : les coupe-circuits doivent repartir a neuf.
   // (en reel ils sont volontairement permanents jusqu a reinitialisation)
   if(IsTesting())
     {
      GlobalVariableDel(BaseGV());
      GlobalVariableDel(HaltGV());
      GlobalVariableDel(DayGV());
     }
   if(!GlobalVariableCheck(BaseGV())) GlobalVariableSet(BaseGV(), AccountBalance());
   soldeReference = GlobalVariableGet(BaseGV());
   Notifier("XAUUSD Or L3 H4 demarre. Base: " + DoubleToString(soldeReference, 2) +
            " | gardien jour " + DoubleToString(LimitePerteJourPct, 1) + " % | TP 1,5R, re-entree 0,25xATR");
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason) { EventKillTimer(); }

void OnTimer()
  {
   ReleverEquite();
   LireFacteurVol();
   LireBiaisMacro();
   LireNouvelles();
   newsBloquaitAvant = BloqueParNouvelles();
   VerifierTpEncaisse();
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   if(!VerifierProtections()) return;
   newsBloquaitAvant = BloqueParNouvelles();
   ProtegerPositionsNews();
   VerifierTpEncaisse();
   GererBreakeven();

   datetime barre = iTime(Symbol(), 0, 0);
   if(barre == derniereBarre) return;
   derniereBarre = barre;

   double atr = iATR(Symbol(), 0, 14, 1);
   double cloture = iClose(Symbol(), 0, 1);

   EcrireJournal(StringConcatenate(
      "cloture=", DoubleToString(cloture, Digits),
      " | position=", (PositionOuverte() ? StringConcatenate("OUVERTE ", NombreUnites(), " unite(s)") : "aucune"),
      " | biais_macro=", (biaisMacroOK ? "OK" : "BLOQUE"),
      " | news=", (newsBloquaitAvant ? "FENETRE ANNONCE" : "libre"),
      " | facteurVol=", DoubleToString(facteurVol, 2),
      " | reentree_armee=", (attenteReentree > 0 ? "OUI" : "non"),
      " | plancher_swing=", DoubleToString(plancherSwing, Digits)));

   if(PositionOuverte()) return;
   if(!biaisMacroOK) return;
   if(newsBloquaitAvant) return;
   if(atr <= 0) return;

   double stopDist = StopAtrMult * atr;
   if(stopDist <= 0) return;

   // swing sur les bougies fermees
   int hiIdx = iHighest(Symbol(), 0, MODE_HIGH, SwingLookback, 1);
   int loIdx = iLowest(Symbol(), 0, MODE_LOW, SwingLookback, 1);
   if(hiIdx < 0 || loIdx < 0) return;
   double hi = iHigh(Symbol(), 0, hiIdx);
   double lo = iLow(Symbol(), 0, loIdx);
   double span = hi - lo;
   bool swingOK = (loIdx > hiIdx);        // le creux est ANTERIEUR au sommet

   // invalidation de la re-entree : plancher du swing casse
   if(attenteReentree > 0 && plancherSwing > 0 && cloture < plancherSwing)
     {
      attenteReentree = 0; plancherSwing = 0;
      Print("Plancher du swing casse : re-entree annulee.");
     }

   // --- Entree 1 : repli fibonacci + RSI qui se retourne ---
   bool setup = false;
   if(swingOK && span > 0)
     {
      double retrace = (hi - cloture) / span;
      if(retrace >= FibLo && retrace <= FibHi)
        {
         double rsi1 = iRSI(Symbol(), 0, 14, PRICE_CLOSE, 1);
         double rsi2 = iRSI(Symbol(), 0, 14, PRICE_CLOSE, 2);
         setup = (rsi2 < RsiPull && rsi1 > rsi2);
        }
     }
   if(setup)
     {
      if(ComptePositionsEcurie() >= MaxPositionsEcurie) return;
   if(FamilleCorreleeOccupee()) return;   // plafond de correlation
   if(DollarFort(RelireFiltreAvantTrade)) return;   // L4.1 filtre dollar (relecture avant trade)
      plancherSwing = lo;
      attenteReentree = 0;
      OuvrirAchat(stopDist, "Ecurie_L3 fib+RSI");
      return;
     }

   // --- Entree 2 : re-entree sur repli apres un TP encaisse ---
   if(attenteReentree > 0 && plancherSwing > 0 &&
      iLow(Symbol(), 0, 1) <= attenteReentree - RetraceReentree * atr &&
      cloture > plancherSwing)
     {
      if(ComptePositionsEcurie() >= MaxPositionsEcurie) return;
   if(FamilleCorreleeOccupee()) return;   // plafond de correlation
   if(DollarFort(RelireFiltreAvantTrade)) return;   // L4.1 filtre dollar (relecture avant trade)
      Print("Repli atteint apres TP : re-entree.");
      OuvrirAchat(stopDist, "Ecurie_L3 re-entree");
      attenteReentree = 0;          // desarme : une seule re-entree par TP
     }
  }

//+------------------------------------------------------------------+
//| Ouverture avec TP en R et suivi du ticket (pour detecter le TP)   |
//+------------------------------------------------------------------+
void OuvrirAchat(double stopDist, string commentaire)
  {
   double lot = CalculerLot(stopDist);
   if(lot <= 0) return;
   double sl = NormalizeDouble(Ask - stopDist, Digits);
   double tp = NormalizeDouble(Ask + TpR * stopDist, Digits);
   double distMin = MarketInfo(Symbol(), MODE_STOPLEVEL) * Point;
   if(Ask - sl < distMin || tp - Ask < distMin) return;
   int ticket = OrderSend(Symbol(), OP_BUY, lot, Ask, Glissement, sl, tp,
                          commentaire, NumeroMagique, 0, clrGreen);
   if(ticket > 0)
     {
      ticketSuivi = ticket;
      tpSuivi = tp;
      Notifier(StringConcatenate("ENTREE achat ", DoubleToString(lot, 2), " lot @ ",
               DoubleToString(Ask, Digits), " | SL ", DoubleToString(sl, Digits),
               " | TP ", DoubleToString(tp, Digits), " (", commentaire, ")"));
     }
   else
      Print("OrderSend (entree) echoue, erreur ", GetLastError(), " lot=", DoubleToString(lot, 2));
  }

//+------------------------------------------------------------------+
//| Breakeven a +1R                                                  |
//+------------------------------------------------------------------+
void GererBreakeven()
  {
   if(!BreakevenActif) return;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) continue;
      if(OrderSymbol() != Symbol() || OrderMagicNumber() != NumeroMagique) continue;
      if(OrderType() != OP_BUY) continue;
      double R = OrderOpenPrice() - OrderStopLoss();
      if(R <= 0) continue;
      if(Bid >= OrderOpenPrice() + R && OrderStopLoss() < OrderOpenPrice())
        {
         double distMin = MarketInfo(Symbol(), MODE_STOPLEVEL) * Point;
         double cible = OrderOpenPrice();
         if(cible > Bid - distMin) continue;
         if(!OrderModify(OrderTicket(), OrderOpenPrice(), NormalizeDouble(cible, Digits),
                     OrderTakeProfit(), 0, clrBlue))
            Print("Echec OrderModify ticket ", OrderTicket(), " erreur ", GetLastError());
        }
     }
  }
//+------------------------------------------------------------------+
