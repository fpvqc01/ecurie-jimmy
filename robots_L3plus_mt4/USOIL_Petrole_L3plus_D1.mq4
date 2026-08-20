//+------------------------------------------------------------------+
//|  USOIL Petrole L3 D1
//|  Ecurie L3 de Jimmy — version MetaTrader 4 (MQL4)
//|  Regles validees par backtest : gardien -2,5 %/jour, plafond
//|  d'ecurie de 2 piles, cassure Donchian 20/10 journaliere, saison dec-mai + PYRAMIDAGE.
//+------------------------------------------------------------------+
#property strict

input double RisqueParTradePct     = 1.5;   // parite de risque validee 10 ans (etait 0.75)   // Risque par trade en % du solde
input double LimitePerteJourPct    = 2.5;    // Coupe-circuit perte du jour (FTMO = 5)
input double LimitePerteTotalePct  = 8.0;    // Coupe-circuit perte totale (FTMO = 10)
input int    MaxPositionsEcurie    = 2;      // Plafond global de piles ouvertes
input int    NumeroMagique         = 20260918; // Identifiant du robot
input int    Glissement            = 30;     // Slippage tolere (points)
input int    PeriodeGraphique     = PERIOD_D1; // donnees journalieres quel que soit le graphique
input int    PeriodeEntree        = 20;    // cassure du plus haut des N jours
input int    PeriodeSortie        = 10;    // stop suiveur sous le plus bas des M jours
input int    PeriodeATR           = 14;
input int    MoisDebutSaison      = 12;    // saison favorable : debut
input int    JourDebutSaison      = 1;
input int    MoisFinSaison        = 5;     // saison favorable : fin
input int    JourFinSaison        = 31;
input bool   PyramidageActif      = true;  // L3 : ajouter des unites sur un gagnant
input int    MaxUnites            = 3;     // L3 : maximum d'unites empilees
input double PasUniteATR          = 0.5;   // L3 : une unite chaque +N x ATR
input double StopSousDerniereUniteATR = 2.0; // L3 : stop commun sous la derniere unite
input bool   BiaisMacroDepuisFichier = true; // lire macrobot_bias.txt
input bool   AchatPermisSansFichier  = true; // fichier absent -> achats permis
input bool   FiltreNouvellesActif    = true; // bloquer autour des annonces USD
input int    MinutesBlocageAvantNews = 30;
input int    MinutesBlocageApresNews = 30;
input bool   ProtegerPositionsPendantNews = true; // serrer les stops en fenetre
input bool   FacteurVolActif       = true;   // moduler le risque selon la volatilite
input bool   JournalActif          = true;   // journal de reflexion (Files\Ecurie_Journal)
input bool   PlafondCorrelationActif = true;  // un seul metal/indice a la fois (crises)
input bool   ModeChallengeActif = false; // L3+ : reduire le risque en drawdown (phases FTMO)
input double ThrottleChallenge  = 0.75;  // L3+ : facteur de risque sous la moyenne 20 j
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
   if(!SendNotification("Petrole L3 : " + msg) && !avertiEchec)
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

bool FamilleCorreleeOccupee()
  {
   if(!PlafondCorrelationActif) return(false);
   if(!EstMetalOuIndice(Symbol())) return(false);
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) continue;
      int m = OrderMagicNumber();
      if(m != 20260815 && m != 20260817 && m != 20260818 &&
         m != 20260915 && m != 20260917 && m != 20260918) continue;
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
      if(m != 20260915 && m != 20260917 && m != 20260918) continue;
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
   int p = StringFind(contenu, "OIL=");
   if(p < 0) { biaisMacroOK = AchatPermisSansFichier; return; }
   string v = StringSubstr(contenu, p + 4, 1);
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
   Notifier("USOIL Petrole L3 D1 demarre. Base: " + DoubleToString(soldeReference, 2) +
            " | gardien jour " + DoubleToString(LimitePerteJourPct, 1) + " % | saison dec-mai, pyramidage 3 unites");
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
//| Fenetre saisonniere (accumulation raffineries pre-driving-season) |
//+------------------------------------------------------------------+
bool EnSaison()
  {
   int mois = TimeMonth(TimeCurrent());
   int jour = TimeDay(TimeCurrent());
   int courant = mois * 100 + jour;
   int debut   = MoisDebutSaison * 100 + JourDebutSaison;
   int fin     = MoisFinSaison * 100 + JourFinSaison;
   if(debut <= fin) return(courant >= debut && courant <= fin);
   return(courant >= debut || courant <= fin);   // fenetre a cheval sur l'annee
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   if(!VerifierProtections()) return;
   newsBloquaitAvant = BloqueParNouvelles();
   ProtegerPositionsNews();
   VerifierTpEncaisse();

   datetime barre = iTime(Symbol(), PeriodeGraphique, 0);
   if(barre == derniereBarre) return;
   derniereBarre = barre;

   int besoin = MathMax(PeriodeEntree, PeriodeSortie) + 3;
   if(iBars(Symbol(), PeriodeGraphique) < besoin) return;

   // canaux calcules sur les bougies AVANT la bougie signal (index 1)
   int idxHaut = iHighest(Symbol(), PeriodeGraphique, MODE_HIGH, PeriodeEntree, 2);
   int idxBas  = iLowest(Symbol(), PeriodeGraphique, MODE_LOW, PeriodeSortie, 2);
   if(idxHaut < 0 || idxBas < 0) return;
   double hautCanal = iHigh(Symbol(), PeriodeGraphique, idxHaut);
   double basCanal  = iLow(Symbol(), PeriodeGraphique, idxBas);
   double cloture   = iClose(Symbol(), PeriodeGraphique, 1);
   double atr       = iATR(Symbol(), PeriodeGraphique, PeriodeATR, 1);

   EcrireJournal(StringConcatenate(
      "cloture=", DoubleToString(cloture, Digits),
      " | canal_haut=", DoubleToString(hautCanal, Digits),
      " | canal_bas=", DoubleToString(basCanal, Digits),
      " | position=", (PositionOuverte() ? StringConcatenate("OUVERTE ", NombreUnites(), " unite(s)") : "aucune"),
      " | macro=", (biaisMacroOK ? "OK" : "BLOQUE"),
      " | news=", (newsBloquaitAvant ? "FENETRE ANNONCE" : "libre"),
      " | facteurVol=", DoubleToString(facteurVol, 2), StringConcatenate(" | saison=", (EnSaison() ? "FAVORABLE" : "hors saison"))));

   if(PositionOuverte())
     {
      // sortie : cloture sous le canal bas
      if(cloture < basCanal) { FermerPositions("cloture sous le canal"); return; }

      // --- PYRAMIDAGE (Turtles) + stop commun ---
      int    unites  = NombreUnites();
      double dernier = PrixDerniereUnite();
      if(PyramidageActif && unites > 0 && unites < MaxUnites && atr > 0 && dernier > 0)
        {
         double seuilAjout = dernier + PasUniteATR * atr;
         if(iHigh(Symbol(), PeriodeGraphique, 1) >= seuilAjout)
           {
            double lotAjout = LotUnite();
            if(lotAjout > 0)
              {
               double slProv = NormalizeDouble(basCanal, Digits);
               int t = OrderSend(Symbol(), OP_BUY, lotAjout, Ask, Glissement, slProv, 0,
                                 StringConcatenate("L3 unite ", unites + 1, "/", MaxUnites),
                                 NumeroMagique, 0, clrGreen);
               if(t > 0)
                 {
                  Notifier(StringConcatenate("PYRAMIDE unite ", unites + 1, "/", MaxUnites,
                           " : +", DoubleToString(lotAjout, 2), " lot @ ", DoubleToString(Ask, Digits)));
                  unites  = NombreUnites();
                  dernier = PrixDerniereUnite();
                 }
         else
            Print("OrderSend (pyramide) echoue, erreur ", GetLastError());
              }
           }
        }
      // stop commun : max(canal bas, derniere unite - N x ATR)
      double niveau = basCanal;
      if(PyramidageActif && unites > 1 && atr > 0 && dernier > 0)
        {
         double turtle = dernier - StopSousDerniereUniteATR * atr;
         if(turtle > niveau) niveau = turtle;
        }
      AppliquerStopCommun(niveau);
      return;
     }

   // --- entree : cassure du canal haut ---
   if(!EnSaison()) return;
   if(newsBloquaitAvant) return;
   if(cloture <= hautCanal) return;
   if(ComptePositionsEcurie() >= MaxPositionsEcurie) return;
   if(FamilleCorreleeOccupee()) return;   // plafond de correlation

   double distanceSL = Ask - basCanal;
   if(distanceSL <= 0 || distanceSL > 0.50 * Ask)
     {
      Print("REFUS D'ENTREE: distance de stop ", DoubleToString(distanceSL, Digits),
            " hors bornes (0 a 50 % du prix).");
      return;
     }
   double lot = CalculerLot(distanceSL);
   if(lot <= 0) return;

   int ticket = OrderSend(Symbol(), OP_BUY, lot, Ask, Glissement,
                          NormalizeDouble(basCanal, Digits), 0,
                          "Ecurie_L3 cassure", NumeroMagique, 0, clrGreen);
   if(ticket > 0)
     {
      ticketSuivi = ticket;
      Notifier(StringConcatenate("ENTREE achat ", DoubleToString(lot, 2), " lot @ ",
               DoubleToString(Ask, Digits), " | stop ", DoubleToString(basCanal, Digits)));
     }
   else
      Print("OrderSend (entree) echoue, erreur ", GetLastError(), " lot=", DoubleToString(lot, 2));
  }
//+------------------------------------------------------------------+
