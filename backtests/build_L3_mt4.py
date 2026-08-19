# -*- coding: utf-8 -*-
"""Genere l'ECURIE L3 en MQL4 (MetaTrader 4) — portage complet depuis MQL5.
5 robots : BTC EMA H1, BTC Cassure H4 (pyramidage), Or H4, Nasdaq H4,
Petrole D1 (pyramidage). Memes regles validees : gardien -2,5 %/jour,
plafond d'ecurie par piles, TP + re-entree, pyramidage Turtle 3 unites.
Differences MQL4 gerees : OrderSend/OrderSelect au lieu de positions,
indicateurs directs (pas de handles), detection du TP par l'historique
(OnTradeTransaction n'existe pas en MQL4)."""
import os

DST = r"C:\Users\jplou\AppData\Roaming\MetaQuotes\Terminal\2C68BEE3A904BDCEE3EEF5A5A77EC162\MQL4\Experts\Jimmy L3"
DL = r"C:\Users\jplou\Downloads\Ecurie_L3_MT4"
os.makedirs(DST, exist_ok=True)
os.makedirs(DL, exist_ok=True)

# ================= EN-TETE COMMUN =================
ENTETE = """//+------------------------------------------------------------------+
//|  {titre}
//|  Ecurie L3 de Jimmy — version MetaTrader 4 (MQL4)
//|  Regles validees par backtest : gardien -2,5 %/jour, plafond
//|  d'ecurie de 2 piles, {specif}
//+------------------------------------------------------------------+
#property strict

input double RisqueParTradePct     = {risque};   // Risque par trade en % du solde
input double LimitePerteJourPct    = 2.5;    // Coupe-circuit perte du jour (FTMO = 5)
input double LimitePerteTotalePct  = 8.0;    // Coupe-circuit perte totale (FTMO = 10)
input int    MaxPositionsEcurie    = 2;      // Plafond global de piles ouvertes
input int    NumeroMagique         = {magic}; // Identifiant du robot
input int    Glissement            = 30;     // Slippage tolere (points)
{inputs_specifiques}input bool   BiaisMacroDepuisFichier = true; // lire macrobot_bias.txt
input bool   AchatPermisSansFichier  = true; // fichier absent -> achats permis
input bool   FiltreNouvellesActif    = true; // bloquer autour des annonces USD
input int    MinutesBlocageAvantNews = 30;
input int    MinutesBlocageApresNews = 30;
input bool   ProtegerPositionsPendantNews = true; // serrer les stops en fenetre
input bool   FacteurVolActif       = true;   // moduler le risque selon la volatilite
input bool   JournalActif          = true;   // journal de reflexion (Files\\Ecurie_Journal)
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

string BaseGV() {{ return("MACROBOT_BASE_" + IntegerToString(AccountNumber())); }}
string HaltGV() {{ return("MACROBOT_HALT_" + IntegerToString(AccountNumber())); }}
string DayGV()  {{ return("MACROBOT_DAY_"  + IntegerToString(AccountNumber())); }}

//+------------------------------------------------------------------+
//| Notifications (log + push cellulaire)                            |
//+------------------------------------------------------------------+
void Notifier(string msg)
  {{
   Print(msg);
   if(!NotificationsPush) return;
   static bool avertiEchec = false;
   if(!SendNotification("{prefixe_push} : " + msg) && !avertiEchec)
     {{
      Print("Push non envoye. Configure ton MetaQuotes ID : Outils > Options > Notifications.");
      avertiEchec = true;
     }}
  }}

//+------------------------------------------------------------------+
//| Journal de reflexion : une ligne par bougie                      |
//+------------------------------------------------------------------+
void EcrireJournal(string texte)
  {{
   if(!JournalActif) return;
   string fichier = "Ecurie_Journal\\\\" + WindowExpertName() + ".txt";
   int fh = FileOpen(fichier, FILE_READ | FILE_WRITE | FILE_TXT | FILE_ANSI);
   if(fh == INVALID_HANDLE) return;
   FileSeek(fh, 0, SEEK_END);
   FileWrite(fh, TimeToString(TimeCurrent(), TIME_DATE | TIME_MINUTES) + " | " + texte);
   FileClose(fh);
  }}

//+------------------------------------------------------------------+
//| Plafond d'ecurie : on compte les PILES (magic+symbole), pas les   |
//| ordres — un robot qui pyramide occupe UN seul siege.              |
//+------------------------------------------------------------------+
int ComptePositionsEcurie()
  {{
   string vues = "";
   int n = 0;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {{
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) continue;
      int m = OrderMagicNumber();
      if(m != 20260915 && m != 20260917 && m != 20260918) continue;
      string cle = "|" + IntegerToString(m) + ":" + OrderSymbol() + "|";
      if(StringFind(vues, cle) >= 0) continue;
      vues += cle;
      n++;
     }}
   return(n);
  }}

//+------------------------------------------------------------------+
//| Positions du robot (symbole + magic)                             |
//+------------------------------------------------------------------+
int NombreUnites()
  {{
   int n = 0;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {{
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) continue;
      if(OrderSymbol() != Symbol() || OrderMagicNumber() != NumeroMagique) continue;
      if(OrderType() != OP_BUY) continue;
      n++;
     }}
   return(n);
  }}

bool PositionOuverte() {{ return(NombreUnites() > 0); }}

double PrixDerniereUnite()   // prix d'ouverture le plus HAUT
  {{
   double p = 0.0;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {{
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) continue;
      if(OrderSymbol() != Symbol() || OrderMagicNumber() != NumeroMagique) continue;
      if(OrderType() != OP_BUY) continue;
      if(OrderOpenPrice() > p) p = OrderOpenPrice();
     }}
   return(p);
  }}

double LotUnite()            // lot de la 1re unite (prix d'ouverture le plus BAS)
  {{
   double p = 0.0, lot = 0.0;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {{
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) continue;
      if(OrderSymbol() != Symbol() || OrderMagicNumber() != NumeroMagique) continue;
      if(OrderType() != OP_BUY) continue;
      if(p == 0.0 || OrderOpenPrice() < p) {{ p = OrderOpenPrice(); lot = OrderLots(); }}
     }}
   return(lot);
  }}

void AppliquerStopCommun(double niveau)
  {{
   double distMin = MarketInfo(Symbol(), MODE_STOPLEVEL) * Point;
   if(niveau > Bid - distMin) niveau = Bid - distMin;
   niveau = NormalizeDouble(niveau, Digits);
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {{
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) continue;
      if(OrderSymbol() != Symbol() || OrderMagicNumber() != NumeroMagique) continue;
      if(OrderType() != OP_BUY) continue;
      if(niveau > OrderStopLoss() + Point)
         OrderModify(OrderTicket(), OrderOpenPrice(), niveau, OrderTakeProfit(), 0, clrBlue);
     }}
  }}

void FermerPositions(string raison)
  {{
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {{
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) continue;
      if(OrderSymbol() != Symbol() || OrderMagicNumber() != NumeroMagique) continue;
      if(OrderType() != OP_BUY) continue;
      if(OrderClose(OrderTicket(), OrderLots(), Bid, Glissement, clrRed))
         Notifier("Fermeture (" + raison + ") " + DoubleToString(OrderLots(), 2) + " lot");
     }}
   ticketSuivi = 0;
  }}

//+------------------------------------------------------------------+
//| Taille de position selon le risque et la distance au stop        |
//+------------------------------------------------------------------+
double CalculerLot(double distanceSL)
  {{
   if(distanceSL <= 0) return(0.0);
   double valeurTick = MarketInfo(Symbol(), MODE_TICKVALUE);
   double tailleTick = MarketInfo(Symbol(), MODE_TICKSIZE);
   if(valeurTick <= 0 || tailleTick <= 0) return(0.0);
   double risque = AccountBalance() * RisqueParTradePct / 100.0 * facteurVol;
   double perteParLot = distanceSL / tailleTick * valeurTick;
   if(perteParLot <= 0) return(0.0);
   double lot = risque / perteParLot;
   double pas = MarketInfo(Symbol(), MODE_LOTSTEP);
   double mini = MarketInfo(Symbol(), MODE_MINLOT);
   double maxi = MarketInfo(Symbol(), MODE_MAXLOT);
   if(pas > 0) lot = MathFloor(lot / pas) * pas;
   if(lot < mini) return(0.0);
   if(lot > maxi) lot = maxi;
   return(NormalizeDouble(lot, 2));
  }}

//+------------------------------------------------------------------+
//| COUPE-CIRCUITS partages (variables globales du terminal)         |
//+------------------------------------------------------------------+
bool VerifierProtections()
  {{
   if(GlobalVariableCheck(HaltGV()) && GlobalVariableGet(HaltGV()) > 0)
     {{
      if(PositionOuverte()) FermerPositions("arret definitif");
      return(false);
     }}
   if(!GlobalVariableCheck(BaseGV()))
      GlobalVariableSet(BaseGV(), AccountBalance());
   soldeReference = GlobalVariableGet(BaseGV());

   int jour = TimeDay(TimeCurrent()) + 100 * TimeMonth(TimeCurrent());
   if(jour != jourCourant)
     {{
      jourCourant = jour;
      equiteDebutJour = AccountEquity();
      GlobalVariableSet(DayGV(), equiteDebutJour);
      avisJourFait = false;
     }}
   else if(GlobalVariableCheck(DayGV()))
      equiteDebutJour = GlobalVariableGet(DayGV());

   double equite = AccountEquity();
   if(soldeReference > 0 && equite <= soldeReference * (1.0 - LimitePerteTotalePct / 100.0))
     {{
      GlobalVariableSet(HaltGV(), 1);
      if(PositionOuverte()) FermerPositions("perte totale");
      Notifier("ARRET DEFINITIF : perte totale de " + DoubleToString(LimitePerteTotalePct, 1) + " % atteinte.");
      return(false);
     }}
   if(equiteDebutJour > 0 && equite <= equiteDebutJour * (1.0 - LimitePerteJourPct / 100.0))
     {{
      if(PositionOuverte()) FermerPositions("perte du jour");
      if(!avisJourFait)
        {{
         Notifier("PAUSE : perte de " + DoubleToString(LimitePerteJourPct, 1) + " % du jour atteinte.");
         avisJourFait = true;
        }}
      return(false);
     }}
   return(true);
  }}

//+------------------------------------------------------------------+
//| Lectures des fichiers du pipeline (Files\\macrobot_*.txt)         |
//+------------------------------------------------------------------+
void LireFacteurVol()
  {{
   if(!FacteurVolActif) {{ facteurVol = 1.0; return; }}
   if(TimeCurrent() - derniereLectureVol < 60) return;
   derniereLectureVol = TimeCurrent();
   int fh = FileOpen("macrobot_vol.txt", FILE_READ | FILE_TXT | FILE_ANSI);
   if(fh == INVALID_HANDLE) {{ facteurVol = 1.0; return; }}
   string ligne = FileReadString(fh);
   FileClose(fh);
   if(StringFind(ligne, "FACTEUR=") == 0)
     {{
      double f = StrToDouble(StringSubstr(ligne, 8));
      if(f >= 0.5 && f <= 1.5)
        {{
         if(MathAbs(f - facteurVol) > 0.01)
            Print("Facteur de volatilite mis a jour : " + DoubleToString(f, 2));
         facteurVol = f;
        }}
     }}
  }}

void LireBiaisMacro()
  {{
   if(!BiaisMacroDepuisFichier) {{ biaisMacroOK = true; return; }}
   if(TimeCurrent() - derniereLectureBiais < 60) return;
   derniereLectureBiais = TimeCurrent();
   int fh = FileOpen("macrobot_bias.txt", FILE_READ | FILE_TXT | FILE_ANSI);
   if(fh == INVALID_HANDLE) {{ biaisMacroOK = AchatPermisSansFichier; return; }}
   string contenu = "";
   while(!FileIsEnding(fh)) contenu += FileReadString(fh) + ";";
   FileClose(fh);
   int p = StringFind(contenu, "{cle_biais}=");
   if(p < 0) {{ biaisMacroOK = AchatPermisSansFichier; return; }}
   string v = StringSubstr(contenu, p + {len_cle}, 1);
   biaisMacroOK = (v == "1");
  }}

void LireNouvelles()
  {{
   if(!FiltreNouvellesActif) return;
   if(TimeCurrent() - derniereLectureNews < 60) return;
   derniereLectureNews = TimeCurrent();
   int fh = FileOpen("macrobot_news.txt", FILE_READ | FILE_TXT | FILE_ANSI);
   if(fh == INVALID_HANDLE) return;
   ArrayResize(prochainesNews, 0);
   while(!FileIsEnding(fh))
     {{
      string ligne = FileReadString(fh);
      if(StringFind(ligne, "EVENT=") == 0)
        {{
         datetime t = (datetime)StrToInteger(StringSubstr(ligne, 6));
         int n = ArraySize(prochainesNews);
         ArrayResize(prochainesNews, n + 1);
         prochainesNews[n] = t;
        }}
     }}
   FileClose(fh);
  }}

bool BloqueParNouvelles()
  {{
   if(!FiltreNouvellesActif) return(false);
   datetime maintenant = TimeGMT();
   for(int i = 0; i < ArraySize(prochainesNews); i++)
     {{
      if(maintenant >= prochainesNews[i] - MinutesBlocageAvantNews * 60 &&
         maintenant <= prochainesNews[i] + MinutesBlocageApresNews * 60)
         return(true);
     }}
   return(false);
  }}

void ProtegerPositionsNews()
  {{
   if(!ProtegerPositionsPendantNews || !newsBloquaitAvant) return;
   double atr = iATR(Symbol(), 0, 14, 1);
   if(atr <= 0) return;
   double distMin = MarketInfo(Symbol(), MODE_STOPLEVEL) * Point;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {{
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) continue;
      if(OrderSymbol() != Symbol() || OrderMagicNumber() != NumeroMagique) continue;
      if(OrderType() != OP_BUY) continue;
      double cible = (Bid > OrderOpenPrice()) ? OrderOpenPrice() : Bid - 0.5 * atr;
      if(cible > Bid - distMin) cible = Bid - distMin;
      cible = NormalizeDouble(cible, Digits);
      if(cible > OrderStopLoss() + Point)
         OrderModify(OrderTicket(), OrderOpenPrice(), cible, OrderTakeProfit(), 0, clrOrange);
     }}
  }}

//+------------------------------------------------------------------+
//| Detection d'un TP encaisse (MQL4 n'a pas OnTradeTransaction) :    |
//| on suit le ticket et on interroge l'historique quand il disparait |
//+------------------------------------------------------------------+
void VerifierTpEncaisse()
  {{
   if(ticketSuivi == 0) return;
   if(OrderSelect(ticketSuivi, SELECT_BY_TICKET, MODE_TRADES))
      if(OrderCloseTime() == 0) return;          // toujours ouvert
   if(!OrderSelect(ticketSuivi, SELECT_BY_TICKET, MODE_HISTORY)) return;
   if(OrderCloseTime() == 0) return;
   double tp = OrderTakeProfit();
   double clot = OrderClosePrice();
   if(tp > 0 && MathAbs(clot - tp) <= 3 * Point * MathPow(10, Digits - 4 > 0 ? 1 : 0))
     {{
      attenteReentree = tp;                       // TP touche -> re-entree armee
      Notifier("TP encaisse a " + DoubleToString(tp, Digits) + " : re-entree armee.");
     }}
   else
     {{
      attenteReentree = 0.0;
      plancherSwing = 0.0;
     }}
   ticketSuivi = 0;
  }}

//+------------------------------------------------------------------+
int OnInit()
  {{
   EventSetTimer(60);
   if(!GlobalVariableCheck(BaseGV())) GlobalVariableSet(BaseGV(), AccountBalance());
   soldeReference = GlobalVariableGet(BaseGV());
   Notifier("{titre} demarre. Base: " + DoubleToString(soldeReference, 2) +
            " | gardien jour " + DoubleToString(LimitePerteJourPct, 1) + " %{suffixe_demarrage}");
   return(INIT_SUCCEEDED);
  }}

void OnDeinit(const int reason) {{ EventKillTimer(); }}

void OnTimer()
  {{
   LireFacteurVol();
   LireBiaisMacro();
   LireNouvelles();
   newsBloquaitAvant = BloqueParNouvelles();
   VerifierTpEncaisse();
  }}
"""

# ================= ONTICK PAR ROBOT =================

ONTICK_CASSURE = """
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
      " | facteurVol=", DoubleToString(facteurVol, 2), SAISON_JOURNAL));

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
   CONDITIONS_ENTREE
   if(cloture <= hautCanal) return;
   if(ComptePositionsEcurie() >= MaxPositionsEcurie) return;

   double distanceSL = Ask - basCanal;
   if(distanceSL <= 0 || distanceSL > LIMITE_SL * Ask) return;
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
  }
"""

ONTICK_FIB = """
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
      OuvrirAchat(stopDist, "Ecurie_L3 re-entree");
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
         OrderModify(OrderTicket(), OrderOpenPrice(), NormalizeDouble(cible, Digits),
                     OrderTakeProfit(), 0, clrBlue);
        }
     }
  }
"""

ONTICK_EMA = """
//+------------------------------------------------------------------+
void OnTick()
  {
   if(!VerifierProtections()) return;
   newsBloquaitAvant = BloqueParNouvelles();
   ProtegerPositionsNews();
   VerifierTpEncaisse();

   datetime barre = iTime(Symbol(), 0, 0);
   if(barre == derniereBarre) return;
   derniereBarre = barre;

   double ema20 = iMA(Symbol(), 0, PeriodeRapide, 0, MODE_EMA, PRICE_CLOSE, 1);
   double ema50 = iMA(Symbol(), 0, PeriodeLente, 0, MODE_EMA, PRICE_CLOSE, 1);
   double ema20p = iMA(Symbol(), 0, PeriodeRapide, 0, MODE_EMA, PRICE_CLOSE, 2);
   double ema50p = iMA(Symbol(), 0, PeriodeLente, 0, MODE_EMA, PRICE_CLOSE, 2);
   double atr = iATR(Symbol(), 0, PeriodeATR, 1);
   double cloture = iClose(Symbol(), 0, 1);
   bool haussier = (ema20 > ema50);

   EcrireJournal(StringConcatenate(
      "prix=", DoubleToString(cloture, Digits),
      " | EMA", PeriodeRapide, "=", DoubleToString(ema20, Digits),
      (haussier ? " > " : " < "), "EMA", PeriodeLente, "=", DoubleToString(ema50, Digits),
      " | position=", (PositionOuverte() ? "OUVERTE" : "aucune"),
      " | macro=", (biaisMacroOK ? "OK" : "BLOQUE"),
      " | news=", (newsBloquaitAvant ? "FENETRE ANNONCE" : "libre"),
      " | facteurVol=", DoubleToString(facteurVol, 2),
      " | reentree_armee=", (attenteReentree > 0 ? "OUI" : "non")));

   if(PositionOuverte())
     {
      if(!haussier) { FermerPositions("croisement baissier"); attenteReentree = 0; }
      return;
     }
   if(!haussier) { attenteReentree = 0; return; }
   if(!biaisMacroOK) return;
   if(newsBloquaitAvant) return;
   if(atr <= 0) return;

   double stopDist = MultiplicateurSL * atr;
   bool croisement = (ema20p <= ema50p);          // croisement frais
   bool reentree = (attenteReentree > 0 &&
                    iLow(Symbol(), 0, 1) <= attenteReentree - RetraceReentreeATR * atr);

   if(!croisement && !reentree) return;
   if(ComptePositionsEcurie() >= MaxPositionsEcurie) return;

   double lot = CalculerLot(stopDist);
   if(lot <= 0) return;
   double sl = NormalizeDouble(Ask - stopDist, Digits);
   double tp = NormalizeDouble(Ask + MultiplicateurTP * atr, Digits);
   double distMin = MarketInfo(Symbol(), MODE_STOPLEVEL) * Point;
   if(Ask - sl < distMin || tp - Ask < distMin) return;
   int ticket = OrderSend(Symbol(), OP_BUY, lot, Ask, Glissement, sl, tp,
                          (croisement ? "Ecurie_L3 croisement" : "Ecurie_L3 re-entree"),
                          NumeroMagique, 0, clrGreen);
   if(ticket > 0)
     {
      ticketSuivi = ticket;
      attenteReentree = 0;
      Notifier(StringConcatenate("ENTREE achat ", DoubleToString(lot, 2), " lot @ ",
               DoubleToString(Ask, Digits), " | SL ", DoubleToString(sl, Digits),
               " | TP ", DoubleToString(tp, Digits)));
     }
  }
"""

# ================= DEFINITION DES 5 ROBOTS =================
ROBOTS = [
    dict(fichier="BTCUSD_EMA_L3_H1.mq4", titre="BTCUSD EMA L3 H1", magic=20260915, risque="0.75",
         specif="TP 2R + re-entree sur repli 0,25xATR.", prefixe_push="BTC EMA L3", cle_biais="BTC",
         corps=ONTICK_EMA, suffixe_demarrage=" | TP 2R, re-entree 0,25xATR",
         inputs="""input int    PeriodeRapide        = 20;    // EMA rapide
input int    PeriodeLente         = 50;    // EMA lente
input int    PeriodeATR           = 14;
input double MultiplicateurSL     = 2.0;   // stop = N x ATR
input double MultiplicateurTP     = 4.0;   // TP = N x ATR (= 2R)
input double RetraceReentreeATR   = 0.25;  // repli exige pour la re-entree
"""),
    dict(fichier="XAUUSD_Or_L3_H4.mq4", titre="XAUUSD Or L3 H4", magic=20260915, risque="3.0",
         specif="repli fib 20-80 % + RSI<55, TP 1,5R + re-entree 0,25xATR.", prefixe_push="Or L3",
         cle_biais="GOLD", corps=ONTICK_FIB, suffixe_demarrage=" | TP 1,5R, re-entree 0,25xATR",
         inputs="""input int    SwingLookback        = 60;    // bougies du swing analyse
input double FibLo                = 0.20;  // zone de repli basse
input double FibHi                = 0.80;  // zone de repli haute
input double RsiPull              = 55.0;  // RSI sous ce niveau puis qui remonte
input double StopAtrMult          = 3.0;   // stop = N x ATR
input double TpR                  = 1.5;   // TP en multiples de R
input double RetraceReentree      = 0.25;  // repli exige pour la re-entree
input bool   BreakevenActif       = true;  // stop au point mort a +1R
"""),
    dict(fichier="US100_Nasdaq_L3_H4.mq4", titre="US100 Nasdaq L3 H4", magic=20260915, risque="1.5",
         specif="repli fib 10-90 % + RSI<60, TP 1R + re-entree 0,5xATR.", prefixe_push="Nasdaq L3",
         cle_biais="NAS", corps=ONTICK_FIB, suffixe_demarrage=" | TP 1R, re-entree 0,5xATR",
         inputs="""input int    SwingLookback        = 40;    // bougies du swing analyse
input double FibLo                = 0.10;  // zone de repli basse
input double FibHi                = 0.90;  // zone de repli haute
input double RsiPull              = 60.0;  // RSI sous ce niveau puis qui remonte
input double StopAtrMult          = 2.0;   // stop = N x ATR
input double TpR                  = 1.0;   // TP en multiples de R
input double RetraceReentree      = 0.50;  // repli exige pour la re-entree
input bool   BreakevenActif       = true;  // stop au point mort a +1R
"""),
    dict(fichier="BTCUSD_Cassure_L3_H4.mq4", titre="BTCUSD Cassure L3 H4", magic=20260917, risque="0.75",
         specif="cassure Donchian 55/20 + PYRAMIDAGE Turtle 3 unites.", prefixe_push="BTC cassure L3",
         cle_biais="BTC", corps=ONTICK_CASSURE, suffixe_demarrage=" | pyramidage 3 unites, stop 2 ATR sous la derniere",
         inputs="""input int    PeriodeGraphique     = PERIOD_H4; // timeframe des donnees
input int    PeriodeEntree        = 55;    // cassure du plus haut des N bougies
input int    PeriodeSortie        = 20;    // stop suiveur sous le plus bas des M
input int    PeriodeATR           = 14;
input bool   PyramidageActif      = true;  // L3 : ajouter des unites sur un gagnant
input int    MaxUnites            = 3;     // L3 : maximum d'unites empilees
input double PasUniteATR          = 0.5;   // L3 : une unite chaque +N x ATR
input double StopSousDerniereUniteATR = 2.0; // L3 : stop commun sous la derniere unite
"""),
    dict(fichier="USOIL_Petrole_L3_D1.mq4", titre="USOIL Petrole L3 D1", magic=20260918, risque="0.75",
         specif="cassure Donchian 20/10 journaliere, saison dec-mai + PYRAMIDAGE.",
         prefixe_push="Petrole L3", cle_biais="OIL", corps=ONTICK_CASSURE,
         suffixe_demarrage=" | saison dec-mai, pyramidage 3 unites",
         inputs="""input int    PeriodeGraphique     = PERIOD_D1; // donnees journalieres quel que soit le graphique
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
"""),
]

FONCTION_SAISON = """
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
"""

for r in ROBOTS:
    entete = ENTETE.format(titre=r["titre"], specif=r["specif"], risque=r["risque"],
                           magic=r["magic"], inputs_specifiques=r["inputs"],
                           prefixe_push=r["prefixe_push"], cle_biais=r["cle_biais"],
                           len_cle=len(r["cle_biais"]) + 1, suffixe_demarrage=r["suffixe_demarrage"])
    corps = r["corps"]
    if "Cassure" in r["fichier"]:
        corps = corps.replace("SAISON_JOURNAL", '""')
        corps = corps.replace("CONDITIONS_ENTREE", "if(!biaisMacroOK) return;\n   if(newsBloquaitAvant) return;")
        corps = corps.replace("LIMITE_SL", "0.10")
    elif "Petrole" in r["fichier"]:
        entete += FONCTION_SAISON
        corps = corps.replace("SAISON_JOURNAL", 'StringConcatenate(" | saison=", (EnSaison() ? "FAVORABLE" : "hors saison"))')
        corps = corps.replace("CONDITIONS_ENTREE", "if(!EnSaison()) return;\n   if(newsBloquaitAvant) return;")
        corps = corps.replace("LIMITE_SL", "0.15")
    texte = entete + corps + "//+------------------------------------------------------------------+\n"
    for dossier in (DST, DL):
        with open(os.path.join(dossier, r["fichier"]), "w", encoding="utf-8") as f:
            f.write(texte)
    print("  %-28s ecrit (%d car.)" % (r["fichier"], len(texte)))

print("\n5 robots MQL4 generes. Compilation a suivre.")
