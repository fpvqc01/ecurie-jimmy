//+------------------------------------------------------------------+
//|                                           USOIL_Petrole_L3_D1.mq5 |
//|  Cassure Donchian 20/10 JOURNALIER sur le pétrole WTI,           |
//|  achat seulement, ACTIVE SEULEMENT EN SAISON (déc -> mai :       |
//|  accumulation des raffineries avant la "driving season" US).     |
//|                                                                  |
//|  Backtest 10 ans frais FTMO réels : +11.9%/an, Sharpe 0.65,      |
//|  robuste sur 5 fenêtres saisonnières et les 2 moitiés.           |
//|  Le swap long du pétrole est POSITIF sur ce compte (bonus).      |
//|                                                                  |
//|  Utilise les données JOURNALIÈRES peu importe le graphique       |
//|  (impossible de se tromper de cadre de temps en l'attachant).    |
//|  Protections FTMO partagées avec les autres robots (MACROBOT_*). |
//+------------------------------------------------------------------+
#property copyright "Jimmy"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

input double RisqueParTradePct    = 0.75;   // Risque par trade en % du solde (I2 : x1.5)
input double LimitePerteJourPct   = 2.5;    // L3 : resserre (valide 19 aout ; FTMO = 5)
input double LimitePerteTotalePct = 8.0;    // Coupe-circuit perte totale (FTMO = 10)
input int    PeriodeEntree        = 20;     // Cassure du plus haut des N jours
input int    PeriodeSortie        = 10;     // Stop suiveur sous le plus bas des M jours
input int    MoisDebutSaison      = 12;     // Saison favorable : début (mois)
input int    JourDebutSaison      = 1;      //   ... jour
input int    MoisFinSaison        = 5;      // Saison favorable : fin (mois)
input int    JourFinSaison        = 31;     //   ... jour
input int    PeriodeATR           = 14;     // ATR journalier (protection annonces)
input long   NumeroMagique        = 20260918; // Identifiant distinct
input int    MaxPositionsEcurie   = 2;      // Plafond global de positions de l'ecurie (I2)
input bool   FiltreNouvellesActif    = true; // bloquer les entrées autour des annonces USD fort impact
input int    MinutesBlocageAvantNews = 30;
input int    MinutesBlocageApresNews = 30;

enum ENUM_PROTECTION_NEWS
  {
   PROTECTION_AUCUNE = 0,   // ne rien faire sur les positions ouvertes
   PROTECTION_SERRER = 1,   // serrer les stops pendant la fenêtre d'annonce (recommandé)
   PROTECTION_FERMER = 2    // fermer les positions avant l'annonce
  };
input ENUM_PROTECTION_NEWS ProtectionPositionsNews = PROTECTION_SERRER;
input bool   FacteurVolActif       = true; // moduler le risque selon la volatilite des marches (L3)
input bool   PyramidageActif    = true;  // L3 : ajouter des unites sur un trade gagnant (Turtles)
input int    MaxUnites          = 3;     // L3 : nombre maximum d'unites empilees
input double PasUniteATR        = 0.5;   // L3 : ajouter une unite chaque +N x ATR
input double StopSousDerniereUniteATR = 2.0; // L3 : stop commun a N x ATR sous la derniere unite
input bool   JournalActif          = true; // journal de reflexion (Files\Ecurie_Journal)
input bool   NotificationsPush       = true; // push cellulaire (MetaQuotes ID)

CTrade   trade;
int      hAtr = INVALID_HANDLE;
datetime dernierJour = 0;
datetime derniereLectureNews = 0;
long     newsEpochs[];
bool     newsBloquaitAvant = false;
datetime derniereLectureVol = 0;
double   facteurVol = 1.0;


string BaseGV() { return "MACROBOT_BASE_" + (string)AccountInfoInteger(ACCOUNT_LOGIN); }
string HaltGV() { return "MACROBOT_HALT_" + (string)AccountInfoInteger(ACCOUNT_LOGIN); }
string DayGV()
  {
   MqlDateTime now;
   TimeToStruct(TimeCurrent(), now);
   return StringFormat("MACROBOT_DAY_%04d%02d%02d_%s",
                       now.year, now.mon, now.day,
                       (string)AccountInfoInteger(ACCOUNT_LOGIN));
  }

//+------------------------------------------------------------------+
//| Plafond d'ecurie : positions de tous nos robots (I2)             |
//+------------------------------------------------------------------+
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
   if(!NotificationsPush) return;
   static bool avertiEchec = false;
   if(!SendNotification("Pétrole L3 : " + msg) && !avertiEchec)
     {
      Print("Push non envoyé. Configure ton MetaQuotes ID : Outils > Options > Notifications.");
      avertiEchec = true;
     }
  }

//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result)
  {
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD) return;
   if(!HistoryDealSelect(trans.deal)) return;
   if(HistoryDealGetInteger(trans.deal, DEAL_MAGIC) != NumeroMagique) return;
   if(HistoryDealGetString(trans.deal, DEAL_SYMBOL) != _Symbol) return;

   double vol  = HistoryDealGetDouble(trans.deal, DEAL_VOLUME);
   double prix = HistoryDealGetDouble(trans.deal, DEAL_PRICE);
   long   sens = HistoryDealGetInteger(trans.deal, DEAL_ENTRY);

   if(sens == DEAL_ENTRY_IN)
      Notifier(StringFormat("ENTRÉE cassure saisonnière %.2f lot @ %s", vol, DoubleToString(prix, _Digits)));
   else if(sens == DEAL_ENTRY_OUT)
      Notifier(StringFormat("SORTIE %.2f lot @ %s | P/L: %.2f $", vol,
                            DoubleToString(prix, _Digits),
                            HistoryDealGetDouble(trans.deal, DEAL_PROFIT)));
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
   trade.SetExpertMagicNumber(NumeroMagique);
   trade.SetDeviationInPoints(50);

   hAtr = iATR(_Symbol, PERIOD_D1, PeriodeATR);
   if(hAtr == INVALID_HANDLE)
     {
      Print("Erreur : impossible de créer l'ATR.");
      return(INIT_FAILED);
     }

   if(!GlobalVariableCheck(BaseGV()))
      GlobalVariableSet(BaseGV(), AccountInfoDouble(ACCOUNT_BALANCE));

   Print("USOIL_Petrole_L3_D1 démarré. Baseline challenge = ",
         DoubleToString(GlobalVariableGet(BaseGV()), 2),
         " | Saison favorable : ", MoisDebutSaison, "/", JourDebutSaison,
         " au ", MoisFinSaison, "/", JourFinSaison);

   EventSetTimer(60);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnTimer()
  {
   LireNouvelles();
   LireFacteurVol();
   BloqueParNouvelles();
   ProtegerPositionsNews();
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   if(hAtr != INVALID_HANDLE) IndicatorRelease(hAtr);
  }

//+------------------------------------------------------------------+
//| Sommes-nous dans la fenêtre saisonnière favorable ?              |
//| Gère les fenêtres qui chevauchent le Nouvel An (déc -> mai).     |
//+------------------------------------------------------------------+
bool EnSaison()
  {
   MqlDateTime now;
   TimeToStruct(TimeCurrent(), now);
   int md  = now.mon * 100 + now.day;
   int deb = MoisDebutSaison * 100 + JourDebutSaison;
   int fin = MoisFinSaison * 100 + JourFinSaison;
   if(deb <= fin) return(md >= deb && md <= fin);
   return(md >= deb || md <= fin);   // fenêtre à cheval sur l'année
  }

//+------------------------------------------------------------------+
void FermerPositions(bool toutLeCompte)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) != NumeroMagique) continue;
      if(!toutLeCompte && PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      trade.PositionClose(ticket);
     }
  }

//+------------------------------------------------------------------+
bool VerifierProtections()
  {
   double equite = AccountInfoDouble(ACCOUNT_EQUITY);
   double base   = GlobalVariableGet(BaseGV());
   if(base <= 0) return(false);

   if(GlobalVariableCheck(HaltGV()) && GlobalVariableGet(HaltGV()) > 0.5)
     {
      static bool dejaFerme = false;
      if(!dejaFerme) { FermerPositions(true); dejaFerme = true; }
      return(false);
     }

   if(equite <= base * (1.0 - LimitePerteTotalePct / 100.0))
     {
      Notifier("🚨 LIMITE DE PERTE TOTALE ATTEINTE. Fermeture, arrêt définitif.");
      FermerPositions(true);
      GlobalVariableSet(HaltGV(), 1.0);
      return(false);
     }

   string cle = DayGV();
   if(!GlobalVariableCheck(cle))
      GlobalVariableSet(cle, equite);
   double debutJour = GlobalVariableGet(cle);
   static bool avisJourFait = false;
   if(equite <= debutJour * (1.0 - LimitePerteJourPct / 100.0))
     {
      if(!avisJourFait)
        {
         Notifier("⚠️ Limite de perte journalière atteinte. Fermeture, pause jusqu'à demain.");
         avisJourFait = true;
        }
      FermerPositions(true);
      return(false);
     }
   avisJourFait = false;
   return(true);
  }

//+------------------------------------------------------------------+
void LireNouvelles()
  {
   if(TimeCurrent() - derniereLectureNews < 60) return;
   derniereLectureNews = TimeCurrent();

   int fh = FileOpen("macrobot_news.txt", FILE_READ | FILE_TXT | FILE_ANSI);
   if(fh == INVALID_HANDLE) return;

   ArrayResize(newsEpochs, 0);
   while(!FileIsEnding(fh))
     {
      string ligne = FileReadString(fh);
      if(StringFind(ligne, "EVENT=") == 0)
        {
         string reste = StringSubstr(ligne, 6);
         int sep = StringFind(reste, ";");
         long epoch = StringToInteger(sep > 0 ? StringSubstr(reste, 0, sep) : reste);
         if(epoch > 0)
           {
            int n = ArraySize(newsEpochs);
            ArrayResize(newsEpochs, n + 1);
            newsEpochs[n] = epoch;
           }
        }
     }
   FileClose(fh);
  }

//+------------------------------------------------------------------+
bool BloqueParNouvelles()
  {
   if(!FiltreNouvellesActif) return(false);
   long maintenant = (long)TimeGMT();
   bool bloque = false;
   for(int i = 0; i < ArraySize(newsEpochs); i++)
     {
      if(maintenant >= newsEpochs[i] - (long)MinutesBlocageAvantNews * 60 &&
         maintenant <= newsEpochs[i] + (long)MinutesBlocageApresNews * 60)
        {
         bloque = true;
         break;
        }
     }
   if(bloque != newsBloquaitAvant)
      Notifier(bloque ? "Annonce USD imminente : entrées bloquées, stops en protection."
                      : "Fenêtre d'annonce terminée : retour à la normale.");
   newsBloquaitAvant = bloque;
   return(bloque);
  }

//+------------------------------------------------------------------+
void ProtegerPositionsNews()
  {
   if(ProtectionPositionsNews == PROTECTION_AUCUNE || !newsBloquaitAvant) return;

   double atrBuf[];
   ArraySetAsSeries(atrBuf, true);
   if(CopyBuffer(hAtr, 0, 1, 1, atrBuf) < 1) return;
   double serre = atrBuf[0] * 0.25;   // ATR journalier : serrage au quart
   if(serre <= 0) return;
   double distMin = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != NumeroMagique) continue;

      if(ProtectionPositionsNews == PROTECTION_FERMER)
        {
         Print("Annonce imminente : fermeture préventive de la position ", ticket);
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
            Print("Fenêtre d'annonce : stop serré à ", DoubleToString(nouveau, _Digits));
     }
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
double CalculerLot(double distanceSL)
  {
   double valeurTick = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tailleTick = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(valeurTick <= 0 || tailleTick <= 0 || distanceSL <= 0)
     {
      Print("Impossible de calculer le lot (tick=", tailleTick, ", valeur=", valeurTick, ").");
      return(0);
     }

   double risqueArgent = AccountInfoDouble(ACCOUNT_BALANCE) * RisqueParTradePct / 100.0 * facteurVol;
   double perteParLot  = distanceSL / tailleTick * valeurTick;
   if(perteParLot <= 0) return(0);

   double lot = risqueArgent / perteParLot;
   double pas    = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double lotMin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double lotMax = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   if(pas > 0) lot = MathFloor(lot / pas) * pas;
   if(lot > lotMax) lot = lotMax;
   if(lot < lotMin)
     {
      Print("Lot calculé trop petit (", DoubleToString(lot, 4), "). Trade annulé.");
      return(0);
     }
   return(lot);
  }

//+------------------------------------------------------------------+
bool PositionOuverte()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != NumeroMagique) continue;
      return(true);
     }
   return(false);
  }


//+------------------------------------------------------------------+
//| PYRAMIDAGE (L3, regle des Turtles) : l'etat est lu directement    |
//| dans les positions ouvertes -> survit a un redemarrage de MT5.    |
//+------------------------------------------------------------------+
int NombreUnites()
  {
   int n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != NumeroMagique) continue;
      n++;
     }
   return(n);
  }

double PrixDerniereUnite()   // prix d'ouverture le plus HAUT = derniere unite ajoutee
  {
   double p = 0.0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != NumeroMagique) continue;
      double po = PositionGetDouble(POSITION_PRICE_OPEN);
      if(po > p) p = po;
     }
   return(p);
  }

double LotUnite()            // taille de la 1re unite (prix d'ouverture le plus BAS)
  {
   double p = 0.0, lot = 0.0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != NumeroMagique) continue;
      double po = PositionGetDouble(POSITION_PRICE_OPEN);
      if(p == 0.0 || po < p) { p = po; lot = PositionGetDouble(POSITION_VOLUME); }
     }
   return(lot);
  }

void AppliquerStopCommun(double niveau)
  {
   double distMin = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
   double bid     = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(niveau > bid - distMin) niveau = bid - distMin;
   niveau = NormalizeDouble(niveau, _Digits);
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != NumeroMagique) continue;
      double slActuel = PositionGetDouble(POSITION_SL);
      if(niveau > slActuel + _Point)      // le stop ne fait que monter
         trade.PositionModify(ticket, niveau, PositionGetDouble(POSITION_TP));
     }
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   if(!VerifierProtections()) return;

   LireNouvelles();
   LireFacteurVol();
   bool newsOK = !BloqueParNouvelles();
   ProtegerPositionsNews();

   // une décision par JOUR (données journalières, peu importe le graphique)
   datetime jourActuel = iTime(_Symbol, PERIOD_D1, 0);
   if(jourActuel == dernierJour) return;
   dernierJour = jourActuel;

   int besoin = MathMax(PeriodeEntree, PeriodeSortie) + 2;
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, PERIOD_D1, 0, besoin, rates) < besoin) return;

   double hautCanal = rates[2].high;
   for(int i = 3; i <= PeriodeEntree + 1; i++)
      if(rates[i].high > hautCanal) hautCanal = rates[i].high;
   double basCanal = rates[2].low;
   for(int i = 3; i <= PeriodeSortie + 1; i++)
      if(rates[i].low < basCanal) basCanal = rates[i].low;

   EcrireJournal(StringFormat("cloture=%.2f | canal_haut=%.2f (dist %.2f%%) | canal_bas=%.2f | saison=%s | position=%s | news=%s | facteurVol=%.2f",
      rates[1].close, hautCanal, (hautCanal - rates[1].close) / rates[1].close * 100.0, basCanal,
      (EnSaison() ? "FAVORABLE" : "hors saison"), (PositionOuverte() ? (StringFormat("OUVERTE %d unite(s)", NombreUnites())) : "aucune"),
      (newsBloquaitAvant ? "FENETRE ANNONCE" : "libre"), facteurVol));
   if(PositionOuverte())
     {
      // sortie : clôture journalière sous le canal bas (toujours active,
      // même hors saison — on ne garde jamais une position sans gestion)
      if(rates[1].close < basCanal)
        {
         FermerPositions(false);
         return;
        }
      // --- L3 : PYRAMIDAGE (Turtles) + stop commun -------------------
      double atrPyr[];
      ArraySetAsSeries(atrPyr, true);
      double atrVal = 0.0;
      if(CopyBuffer(hAtr, 0, 1, 1, atrPyr) >= 1) atrVal = atrPyr[0];

      int    unites  = NombreUnites();
      double dernier = PrixDerniereUnite();

      // 1) ajout d'une unite quand le prix a avance de PasUniteATR
      //    depuis la derniere unite (une seule unite par bougie : prudent)
      if(PyramidageActif && unites > 0 && unites < MaxUnites && atrVal > 0 && dernier > 0)
        {
         double seuilAjout = dernier + PasUniteATR * atrVal;
         if(rates[1].high >= seuilAjout && ComptePositionsEcurie() <= MaxPositionsEcurie)
           {
            double lotAjout = LotUnite();
            if(lotAjout > 0)
              {
               double slProvisoire = NormalizeDouble(basCanal, _Digits);
               if(trade.Buy(lotAjout, _Symbol, 0.0, slProvisoire, 0.0,
                            "L3 unite " + (string)(unites + 1) + "/" + (string)MaxUnites))
                 {
                  Notifier(StringFormat("PYRAMIDE unite %d/%d : +%.2f lot @ %.2f",
                           unites + 1, MaxUnites, lotAjout,
                           SymbolInfoDouble(_Symbol, SYMBOL_ASK)));
                  unites  = NombreUnites();
                  dernier = PrixDerniereUnite();
                 }
              }
           }
        }

      // 2) stop commun : le plus HAUT entre le canal bas et
      //    (derniere unite - StopSousDerniereUniteATR x ATR)
      double niveauStop = basCanal;
      if(PyramidageActif && unites > 1 && atrVal > 0 && dernier > 0)
        {
         double stopTurtle = dernier - StopSousDerniereUniteATR * atrVal;
         if(stopTurtle > niveauStop) niveauStop = stopTurtle;
        }
      AppliquerStopCommun(niveauStop);
      return;
     }

   // entrée : cassure du canal haut, EN SAISON seulement, hors annonces
   if(!EnSaison()) return;
   if(!newsOK) return;
   if(rates[1].close <= hautCanal) return;
   if(ComptePositionsEcurie() >= MaxPositionsEcurie) return; // plafond d'ecurie (I2)

   double prix = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double distanceSL = prix - basCanal;
   if(distanceSL <= 0 || distanceSL > 0.15 * prix) return;
   double lot = CalculerLot(distanceSL);
   if(lot <= 0) return;

   double sl = NormalizeDouble(basCanal, _Digits);
   trade.Buy(lot, _Symbol, 0.0, sl, 0.0, "USOIL_Breakout saison");
  }
//+------------------------------------------------------------------+
