//+------------------------------------------------------------------+
//|                                                 BTC_FTMO_Bot.mq5 |
//|  Bot BTC pour MT5 avec coupe-circuits adaptés aux règles FTMO    |
//|                                                                  |
//|  Stratégie : croisement EMA 20/50 + stops basés sur l'ATR        |
//|  Protection PARTAGÉE avec FTMO_MacroBot : les 3 robots lisent    |
//|  la même baseline, la même référence journalière et le même     |
//|  interrupteur d'arrêt (variables globales MACROBOT_*). Si UN    |
//|  robot détecte un dépassement, il ferme les positions de TOUS.  |
//|                                                                  |
//|  IMPORTANT : à tester en DÉMO / Free Trial FTMO d'abord.         |
//|  Aucun bot ne garantit de passer le challenge.                   |
//+------------------------------------------------------------------+
#property copyright "Jimmy"
#property version   "1.10"
#property strict

#include <Trade\Trade.mqh>

//--- Paramètres modifiables (onglet "Inputs" quand tu attaches le bot)
input double RisqueParTradePct    = 0.5;    // Risque par trade en % du solde
input double LimitePerteJourPct   = 3.5;    // Coupe-circuit perte du jour en % (FTMO = 5, on garde une marge)
input double LimitePerteTotalePct = 8.0;    // Coupe-circuit perte totale en % (FTMO = 10, on garde une marge)
input int    EMARapide            = 20;     // Période EMA rapide
input int    EMALente             = 50;     // Période EMA lente
input int    PeriodeATR           = 14;     // Période ATR
input double MultiplicateurSL     = 2.0;    // Stop loss = 2 x ATR
input double MultiplicateurTP     = 3.0;    // Take profit = 3 x ATR
input long   NumeroMagique        = 20260815; // Identifiant des trades (commun aux 3 robots)
input bool   ModeAchatSeulement   = true;   // true = jamais de vente à découvert (recommandé sur BTC)
input bool   BiaisMacroDepuisFichier = true; // lire le biais macro BIS dans macrobot_bias.txt (relu chaque minute)
input bool   AchatPermisSansFichier  = true; // si le fichier est absent : permettre les achats quand même ?
input bool   FiltreNouvellesActif    = true; // bloquer les entrées autour des annonces USD à fort impact
input int    MinutesBlocageAvantNews = 30;   // minutes de blocage AVANT chaque annonce
input int    MinutesBlocageApresNews = 30;   // minutes de blocage APRÈS chaque annonce

enum ENUM_PROTECTION_NEWS
  {
   PROTECTION_AUCUNE = 0,   // ne rien faire sur les positions ouvertes
   PROTECTION_SERRER = 1,   // serrer les stops pendant la fenêtre d'annonce (recommandé)
   PROTECTION_FERMER = 2    // fermer les positions avant l'annonce (le plus prudent)
  };
input ENUM_PROTECTION_NEWS ProtectionPositionsNews = PROTECTION_SERRER; // gestion des positions autour des annonces
input bool   NotificationsPush       = true; // notifications push sur le cellulaire (app MT5 mobile + MetaQuotes ID)

//--- Variables internes
CTrade   trade;
int      hEmaRapide = INVALID_HANDLE;
int      hEmaLente  = INVALID_HANDLE;
int      hAtr       = INVALID_HANDLE;
datetime derniereBarre = 0;
datetime derniereLectureBiais = 0;
bool     biaisMacroOK = true;
datetime derniereLectureNews = 0;
long     newsEpochs[];          // annonces USD fort impact (epoch UTC)
int      fngValeur = -1;        // Fear & Greed crypto (0-100, -1 = inconnu)
bool     newsBloquaitAvant = false;

//+------------------------------------------------------------------+
//| Journal + notification push sur le cellulaire (si configurée)    |
//+------------------------------------------------------------------+
void Notifier(string msg)
  {
   Print(msg);
   if(!NotificationsPush) return;
   static bool avertiEchec = false;
   if(!SendNotification("BTC bot : " + msg) && !avertiEchec)
     {
      Print("Push non envoyé. Configure ton MetaQuotes ID : Outils > Options > Notifications.");
      avertiEchec = true;
     }
  }

//+------------------------------------------------------------------+
//| Notification à chaque transaction du robot (entrée, sortie,      |
//| stop touché, take profit...) — capte aussi les sorties exécutées |
//| par le serveur du courtier.                                      |
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
   bool   achat = (HistoryDealGetInteger(trans.deal, DEAL_TYPE) == DEAL_TYPE_BUY);
   long   sens = HistoryDealGetInteger(trans.deal, DEAL_ENTRY);

   if(sens == DEAL_ENTRY_IN)
      Notifier(StringFormat("ENTRÉE %s %.2f lot @ %s", achat ? "achat" : "vente",
                            vol, DoubleToString(prix, _Digits)));
   else if(sens == DEAL_ENTRY_OUT)
      Notifier(StringFormat("SORTIE %.2f lot @ %s | P/L: %.2f $", vol,
                            DoubleToString(prix, _Digits),
                            HistoryDealGetDouble(trans.deal, DEAL_PROFIT)));
  }

//--- Mêmes clés que FTMO_MacroBot : protections partagées entre les 3 robots
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
int OnInit()
  {
   trade.SetExpertMagicNumber(NumeroMagique);
   trade.SetDeviationInPoints(50);

   hEmaRapide = iMA(_Symbol, _Period, EMARapide, 0, MODE_EMA, PRICE_CLOSE);
   hEmaLente  = iMA(_Symbol, _Period, EMALente,  0, MODE_EMA, PRICE_CLOSE);
   hAtr       = iATR(_Symbol, _Period, PeriodeATR);

   if(hEmaRapide == INVALID_HANDLE || hEmaLente == INVALID_HANDLE || hAtr == INVALID_HANDLE)
     {
      Print("Erreur : impossible de créer les indicateurs.");
      return(INIT_FAILED);
     }

   // Baseline du challenge : persistée entre les redémarrages, partagée
   // avec FTMO_MacroBot (première valeur écrite = solde de départ)
   if(!GlobalVariableCheck(BaseGV()))
      GlobalVariableSet(BaseGV(), AccountInfoDouble(ACCOUNT_BALANCE));

   Print("BTC_FTMO_Bot démarré. Baseline challenge = ",
         DoubleToString(GlobalVariableGet(BaseGV()), 2));

   // vérification des données externes chaque minute, même sans tick
   EventSetTimer(60);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnTimer()
  {
   LireNouvelles();          // relit le fichier de nouvelles (throttle interne 60 s)
   BiaisMacroPermis();       // relit le biais macro (throttle interne 60 s)
   BloqueParNouvelles();     // met à jour l'état + log si changement
   ProtegerPositionsNews();  // serre les stops si une annonce approche
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   if(hEmaRapide != INVALID_HANDLE) IndicatorRelease(hEmaRapide);
   if(hEmaLente  != INVALID_HANDLE) IndicatorRelease(hEmaLente);
   if(hAtr       != INVALID_HANDLE) IndicatorRelease(hAtr);
  }

//+------------------------------------------------------------------+
//| Ferme les positions du magic number.                             |
//| toutLeCompte=true : tous les symboles (urgence gardien)          |
//| toutLeCompte=false : seulement ce symbole (sortie de stratégie)  |
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
//| Coupe-circuits FTMO partagés. Retourne true si on peut trader.   |
//+------------------------------------------------------------------+
bool VerifierProtections()
  {
   double equite = AccountInfoDouble(ACCOUNT_EQUITY);
   double base   = GlobalVariableGet(BaseGV());
   if(base <= 0) return(false);

   // 1) Arrêt définitif déjà déclenché par n'importe quel robot du compte
   if(GlobalVariableCheck(HaltGV()) && GlobalVariableGet(HaltGV()) > 0.5)
      return(false);

   // 2) Perte totale : on coupe TOUT le compte et on lève le drapeau partagé
   if(equite <= base * (1.0 - LimitePerteTotalePct / 100.0))
     {
      Notifier("🚨 LIMITE DE PERTE TOTALE ATTEINTE. Fermeture de tout le compte, arrêt définitif.");
      FermerPositions(true);
      GlobalVariableSet(HaltGV(), 1.0);
      return(false);
     }

   // 3) Perte du jour : référence partagée, créée par le premier robot du jour
   string cle = DayGV();
   if(!GlobalVariableCheck(cle))
      GlobalVariableSet(cle, equite);
   double debutJour = GlobalVariableGet(cle);
   static bool avisJourFait = false;
   if(equite <= debutJour * (1.0 - LimitePerteJourPct / 100.0))
     {
      if(!avisJourFait)
        {
         Notifier("⚠️ Limite de perte journalière atteinte. Fermeture de tout le compte, pause jusqu'à demain.");
         avisJourFait = true;
        }
      FermerPositions(true);   // sans effet si déjà tout fermé
      return(false);
     }
   avisJourFait = false;
   return(true);
  }

//+------------------------------------------------------------------+
//| Biais macro : relit MQL5\Files\macrobot_bias.txt au plus 1x/min. |
//| Le fichier est écrit par export_bias.py (données BIS : posture   |
//| Fed). "BTC=1" = achats permis, "BTC=0" = environnement hostile.  |
//+------------------------------------------------------------------+
bool BiaisMacroPermis()
  {
   if(!BiaisMacroDepuisFichier) return(true);
   if(TimeCurrent() - derniereLectureBiais < 60) return(biaisMacroOK);
   derniereLectureBiais = TimeCurrent();

   int fh = FileOpen("macrobot_bias.txt", FILE_READ | FILE_TXT | FILE_ANSI);
   if(fh == INVALID_HANDLE)
     {
      biaisMacroOK = AchatPermisSansFichier;
      return(biaisMacroOK);
     }
   string ligne = FileReadString(fh);
   FileClose(fh);

   bool nouveau = (StringFind(ligne, "BTC=1") >= 0);
   if(nouveau != biaisMacroOK)
      Print("Biais macro BTC : ", nouveau ? "ACHATS PERMIS" : "ACHATS BLOQUÉS", " (", ligne, ")");
   biaisMacroOK = nouveau;
   return(biaisMacroOK);
  }

//+------------------------------------------------------------------+
//| Relit MQL5\Files\macrobot_news.txt au plus 1x/min : annonces USD |
//| à fort impact (Forex Factory) + Fear & Greed crypto.             |
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
      if(StringFind(ligne, "FNG=") == 0)
        {
         int v = (int)StringToInteger(StringSubstr(ligne, 4));
         if(v != fngValeur && v >= 0)
            Print("Fear & Greed crypto : ", v, "/100 (0=peur extrême, 100=avidité extrême)");
         fngValeur = v;
        }
      else if(StringFind(ligne, "EVENT=") == 0)
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
//| true si on est dans la fenêtre de blocage d'une annonce USD      |
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
      Notifier(bloque ? "Annonce économique USD imminente : entrées bloquées, stops en mode protection."
                      : "Fenêtre d'annonce terminée : retour à la normale.");
   newsBloquaitAvant = bloque;
   return(bloque);
  }

//+------------------------------------------------------------------+
//| Pendant la fenêtre d'annonce : serre les stops (ou ferme) pour   |
//| limiter la perte maximale si le prix saute violemment.           |
//| Monotone : un stop n'est jamais élargi, seulement rapproché.     |
//+------------------------------------------------------------------+
void ProtegerPositionsNews()
  {
   if(ProtectionPositionsNews == PROTECTION_AUCUNE || !newsBloquaitAvant) return;

   double atrBuf[];
   ArraySetAsSeries(atrBuf, true);
   if(CopyBuffer(hAtr, 0, 1, 1, atrBuf) < 1) return;
   double serre = atrBuf[0] * 0.5;
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

      if(PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY)
        {
         double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         double nouveau = bid - serre;
         if(bid > entree && entree > nouveau) nouveau = entree; // breakeven si en profit
         if(nouveau > bid - distMin) nouveau = bid - distMin;   // distance minimale du courtier
         nouveau = NormalizeDouble(nouveau, _Digits);
         if(nouveau > slActuel + serre * 0.1)
            if(trade.PositionModify(ticket, nouveau, tp))
               Print("Fenêtre d'annonce : stop serré à ", DoubleToString(nouveau, _Digits));
        }
      else
        {
         double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double nouveau = ask + serre;
         if(ask < entree && entree < nouveau) nouveau = entree;
         if(nouveau < ask + distMin) nouveau = ask + distMin;
         nouveau = NormalizeDouble(nouveau, _Digits);
         if(slActuel == 0.0 || nouveau < slActuel - serre * 0.1)
            if(trade.PositionModify(ticket, nouveau, tp))
               Print("Fenêtre d'annonce : stop serré à ", DoubleToString(nouveau, _Digits));
        }
     }
  }

//+------------------------------------------------------------------+
//| Calcule la taille du lot selon le risque et la distance du SL    |
//+------------------------------------------------------------------+
double CalculerLot(double distanceSL)
  {
   double valeurTick = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tailleTick = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(valeurTick <= 0 || tailleTick <= 0 || distanceSL <= 0) return(0);

   double risqueArgent = AccountInfoDouble(ACCOUNT_BALANCE) * RisqueParTradePct / 100.0;
   double perteParLot  = distanceSL / tailleTick * valeurTick;
   if(perteParLot <= 0) return(0);

   double lot = risqueArgent / perteParLot;

   // Ajuster aux contraintes du courtier (lot min, max, pas)
   double pas    = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double lotMin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double lotMax = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   if(pas > 0) lot = MathFloor(lot / pas) * pas;
   if(lot > lotMax) lot = lotMax;

   // Si même le lot minimum dépasse le risque voulu, on ne trade pas
   if(lot < lotMin)
     {
      Print("Lot calculé (", DoubleToString(lot, 4), ") plus petit que le lot minimum (",
            DoubleToString(lotMin, 4), "). Trade annulé pour respecter le risque.");
      return(0);
     }
   return(lot);
  }

//+------------------------------------------------------------------+
//| Y a-t-il déjà une position ouverte par ce bot sur ce symbole ?   |
//| Retourne : 1 = achat, -1 = vente, 0 = aucune                     |
//+------------------------------------------------------------------+
int PositionActuelle()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != NumeroMagique) continue;
      if(PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) return(1);
      return(-1);
     }
   return(0);
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   // Les protections sont vérifiées à CHAQUE tick (pas juste à chaque bougie)
   if(!VerifierProtections()) return;

   // Données externes rafraîchies au plus 1x/minute (log si changement d'état)
   LireNouvelles();
   bool macroPermis = BiaisMacroPermis() && !BloqueParNouvelles();
   ProtegerPositionsNews();  // à chaque tick pendant une fenêtre d'annonce : réaction immédiate

   // Le reste ne s'exécute qu'une fois par nouvelle bougie
   datetime barreActuelle = iTime(_Symbol, _Period, 0);
   if(barreActuelle == derniereBarre) return;
   derniereBarre = barreActuelle;

   // Lire les indicateurs sur les 2 dernières bougies FERMÉES (index 1 et 2)
   // (index 0 = bougie en cours, jamais utilisée pour décider)
   double emaRapide[], emaLente[], atr[];
   ArraySetAsSeries(emaRapide, true);
   ArraySetAsSeries(emaLente,  true);
   ArraySetAsSeries(atr,       true);
   if(CopyBuffer(hEmaRapide, 0, 0, 3, emaRapide) < 3) return;
   if(CopyBuffer(hEmaLente,  0, 0, 3, emaLente)  < 3) return;
   if(CopyBuffer(hAtr,       0, 0, 2, atr)       < 2) return;

   bool croisementHaussier = (emaRapide[2] <= emaLente[2] && emaRapide[1] > emaLente[1]);
   bool croisementBaissier = (emaRapide[2] >= emaLente[2] && emaRapide[1] < emaLente[1]);
   if(!croisementHaussier && !croisementBaissier) return;

   double distanceSL = atr[1] * MultiplicateurSL;
   double distanceTP = atr[1] * MultiplicateurTP;
   if(distanceSL <= 0) return;

   int position = PositionActuelle();

   if(croisementHaussier)
     {
      if(position == -1) FermerPositions(false);
      // Nouvel achat SEULEMENT si l'environnement macro le permet
      if(position != 1 && macroPermis)
        {
         double lot = CalculerLot(distanceSL);
         if(lot > 0)
           {
            double prix = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            double sl   = NormalizeDouble(prix - distanceSL, _Digits);
            double tp   = NormalizeDouble(prix + distanceTP, _Digits);
            trade.Buy(lot, _Symbol, 0.0, sl, tp, "BTC_FTMO_Bot achat");
           }
        }
     }
   else if(croisementBaissier)
     {
      if(position == 1) FermerPositions(false);
      if(ModeAchatSeulement) return; // en mode achat seulement, on ferme mais on ne vend pas à découvert
      if(position != -1)
        {
         double lot = CalculerLot(distanceSL);
         if(lot > 0)
           {
            double prix = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            double sl   = NormalizeDouble(prix + distanceSL, _Digits);
            double tp   = NormalizeDouble(prix - distanceTP, _Digits);
            trade.Sell(lot, _Symbol, 0.0, sl, tp, "BTC_FTMO_Bot vente");
           }
        }
     }
  }
//+------------------------------------------------------------------+
