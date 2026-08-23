//+------------------------------------------------------------------+
//| US100_Nasdaq_L43_H4.mq5                                             |
//| Base I2 (17 aout) portee en L4.31 le 20 aout 2026 :              |
//|  - OR     : TP 1.5R (~750$) + re-entree sur repli 0.25xATR       |
//|  - NASDAQ : TP 1.0R (~500$) + re-entree sur repli 0.5xATR        |
//|  - re-entree permise tant que le creux du swing d'origine tient  |
//|  - risque : or 2,0 % (L4) / Nasdaq 1,5 % ; filtre dollar sur or  |
//|  - plafond d'ecurie : max 2 positions simultanees (tous robots)  |
//| Magic L4.3 (20261115) : ecurie independante des autres.          |
//+------------------------------------------------------------------+
#property copyright "Macro Bot"
#property version   "2.00"

#include <Trade\Trade.mqh>

enum ENUM_PRESET
  {
   PRESET_GOLD,    // Or (XAUUSD)
   PRESET_NASDAQ   // US100 / NAS100
  };

input ENUM_PRESET Preset             = PRESET_NASDAQ;
input bool   MacroLongAllowed        = true;
input bool   BiasFromFile            = true;
input double RiskPerTradePct         = 1.02;  // L8+ : deconcentration BTC (banc : plateau sous 1,15 %)   // L8 : allocation a x0,75 (etait 1,5)    // L3 : x1.5
input double FacteurRisqueGlobal     = 1.0;   // L8 : multiplicateur global (mettre 1.33 une fois finance, gardien fixe -2,5)
input bool   TurboCoussinActif   = false;   // L12 : risque x TurboMultiplicateur tant que le coussin de phase n'est pas fait   // D : reglage du laboratoire
input double TurboMultiplicateur = 1.15;   // L12 : plateau verifie 1,15-1,33 ; 1,15 est le meilleur point (falaise a 1,50)
input double TurboCoussinPct     = 4.0;    // L12 : coussin, en % au-dessus de la baseline, qui coupe le turbo
input double SpreadEntreeMaxPct      = 2.0;   // L8 : entree reportee si le spread depasse ce % de la distance de stop (0 = off)
input double LimitePerteJourPct            = 1.75;  // L11 : rendu a 2,50 % - la deconcentration du BTC a traite la cause (banc L11 : -41 a -75 jours, reussite inchangee)   // L3 : resserre (valide 19 aout ; FTMO = 5)   // D : reglage du laboratoire
input double LimitePerteTotalePct            = 8.0;
input double ChallengeInitialBalance = 0;
input double ObjectifPhasePct   = 10.0;  // L8-R13 : objectif de la phase en % (10 = phase 1 FTMO, 5 = phase 2, 0 = desactive)   // D : reglage du laboratoire
input double MargeObjectifPct   = 0.25;  // L8-R13 : coussin encaisse au-dessus de l'objectif (spread/commission)
input long   MagicNumber             = 20262063;  // L8-R5 : magic propre (3 robots partageaient 20261115)
input int    MaxPositionsEcurie      = 2;      // plafond global de l'ecurie (I2)
input bool   NewsFilterOn            = true;
input int    NewsMinutesAvant        = 30;
input int    NewsMinutesApres        = 30;

enum ENUM_NEWS_PROTECT
  {
   NEWS_PROTECT_RIEN   = 0,
   NEWS_PROTECT_SERRER = 1,
   NEWS_PROTECT_FERMER = 2
  };
input ENUM_NEWS_PROTECT NewsProtectMode = NEWS_PROTECT_SERRER;
input bool   PushNotifications       = true;
input bool   BreakevenActif          = true;
input bool   FacteurVolActif         = true;   // moduler le risque selon la volatilite (L3)
input bool   JournalActif            = true;   // journal de reflexion (Files\Ecurie_Journal)
input bool   PlafondCorrelationActif = true;  // un seul metal/indice a la fois (crises)
input bool   ModeChallengeActif = true;  // L4 : ACTIF par defaut (valide scan 21 aout, 2 moteurs)
input double ThrottleChallenge  = 0.75;  // L3+ : facteur sous la moyenne 20 j

CTrade   trade;
int      hATR = INVALID_HANDLE, hRSI = INVALID_HANDLE;
datetime lastBar = 0;
bool     cacheBiasOK   = true;
bool     cacheNewsBloq = false;
bool     cacheInitFait = false;
datetime derniereLectureVol = 0;
double   facteurVol = 1.0;
bool     volLectureEchouee = false;   // L13

double   attenteReentree = 0;   // prix de sortie TP ; 0 = rien en attente (I2)
double   plancherSwing   = 0;   // creux du swing de l'entree d'origine (I2)

// parametres de timing par preset
int    SwingLookback;
double FibLo, FibHi, RsiPull, StopAtrMult, TpR, RetraceReentree;
int    RsiPeriod = 14, AtrPeriod = 14;

string BaseGV()  { return "MACROBOT_BASE_"  + (string)AccountInfoInteger(ACCOUNT_LOGIN); }
string HaltGV()  { return "MACROBOT_HALT_"  + (string)AccountInfoInteger(ACCOUNT_LOGIN); }
string LastEqGV() { return "MACROBOT_LASTEQ_" + (string)AccountInfoInteger(ACCOUNT_LOGIN); }   // L4.32 : equite d'avant le gap

//+------------------------------------------------------------------+
//| L12 : turbo-coussin. Rejete dix fois quand il etait seul (il fait |
//| entrer plus gros au pire moment). Viable une fois combine au      |
//| repli conditionnel, qui corrige exactement ce defaut : 75 % de    |
//| reussite seul, 95 % avec le repli.                                |
//+------------------------------------------------------------------+
double FacteurTurbo()
  {
   if(!TurboCoussinActif) return(1.0);
   if(!GlobalVariableCheck(BaseGV())) return(1.0);
   double basePhase = GlobalVariableGet(BaseGV());
   if(basePhase <= 0) return(1.0);
   if(AccountInfoDouble(ACCOUNT_EQUITY) >= basePhase * (1.0 + TurboCoussinPct / 100.0))
      return(1.0);
   return(TurboMultiplicateur);
  }

//+------------------------------------------------------------------+

//+------------------------------------------------------------------+
//| L3 : test de position robuste (PositionSelect n'est pas fiable    |
//| sur un compte hedging) -> boucle explicite symbole + magic.       |
//+------------------------------------------------------------------+
bool PositionOuverte()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != MagicNumber) continue;
      return(true);
     }
   return(false);
  }

//+------------------------------------------------------------------+
//| PLAFOND DE CORRELATION (valide sur 99 ans de crises)              |
//| L'or et les indices semblent independants... jusqu'a une crise de |
//| liquidite qui les fait chuter ENSEMBLE (septembre 2011 : l'or de  |
//| 1920 a 1530 pendant que les indices plongeaient). Un seul robot   |
//| de la famille metal/indice peut donc etre en position a la fois.  |
//| Test : 2011 passe de -8,0 % (compte mort) a -2,2 % ; crises       |
//| positives 5/7 -> 6/7 ; cout 1,1 point de rendement annuel.        |
//+------------------------------------------------------------------+
bool EstMetalOuIndice(string symbole)
  {
   string s = symbole;
   StringToUpper(s);
   if(StringFind(s, "XAU") >= 0) return(true);   // or
   if(StringFind(s, "XAG") >= 0) return(true);   // argent
   if(StringFind(s, "US100") >= 0) return(true); // Nasdaq
   if(StringFind(s, "NAS") >= 0) return(true);
   if(StringFind(s, "US30") >= 0) return(true);
   if(StringFind(s, "US500") >= 0) return(true);
   if(StringFind(s, "SPX") >= 0) return(true);
   if(StringFind(s, "GER") >= 0 || StringFind(s, "DE30") >= 0) return(true);
   return(false);
  }

//| true si une AUTRE position metal/indice de l'ecurie est ouverte
bool FamilleCorreleeOccupee()
  {
   if(!PlafondCorrelationActif) return(false);
   if(!EstMetalOuIndice(_Symbol)) return(false);   // ne concerne pas BTC/petrole
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      long m = PositionGetInteger(POSITION_MAGIC);
      if(m != 20261131 && m != 20261132 && m != 20261133 && m != 20261134 && m != 20261135) continue;
      string sym = PositionGetString(POSITION_SYMBOL);
      if(sym == _Symbol) continue;                 // c'est nous
      if(EstMetalOuIndice(sym)) return(true);      // un cousin est deja expose
     }
   return(false);
  }

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
      if(m != 20261131 && m != 20261132 && m != 20261133 && m != 20261134 && m != 20261135) continue;
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
   if(!PushNotifications) return;
   static bool avertiEchec = false;
   if(!SendNotification("[L8] " + _Symbol + " : " + msg) && !avertiEchec)
     {
      Print("Push non envoye. Configure ton MetaQuotes ID.");
      avertiEchec = true;
     }
  }

//+------------------------------------------------------------------+
//| Notifications + detection des sorties TP (arme la re-entree)     |
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result)
  {
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD) return;
   if(!HistoryDealSelect(trans.deal)) return;
   if(HistoryDealGetInteger(trans.deal, DEAL_MAGIC) != MagicNumber) return;
   if(HistoryDealGetString(trans.deal, DEAL_SYMBOL) != _Symbol) return;

   double vol  = HistoryDealGetDouble(trans.deal, DEAL_VOLUME);
   double prix = HistoryDealGetDouble(trans.deal, DEAL_PRICE);
   long   sens = HistoryDealGetInteger(trans.deal, DEAL_ENTRY);

   if(sens == DEAL_ENTRY_IN)
      Notifier(StringFormat("ENTREE achat %.2f lot @ %s", vol, DoubleToString(prix, _Digits)));
   else if(sens == DEAL_ENTRY_OUT)
     {
      Notifier(StringFormat("SORTIE %.2f lot @ %s | P/L: %.2f $", vol,
                            DoubleToString(prix, _Digits),
                            HistoryDealGetDouble(trans.deal, DEAL_PROFIT)));
      long raison = HistoryDealGetInteger(trans.deal, DEAL_REASON);
      if(raison == DEAL_REASON_TP)
        {
         attenteReentree = prix;
         Print("TP encaisse : re-entree armee sous ", DoubleToString(prix, _Digits),
               " (tant que le plancher ", DoubleToString(plancherSwing, _Digits), " tient)");
        }
      else
        {
         attenteReentree = 0;   // stop touche : la these est invalidee
         plancherSwing = 0;
        }
     }
  }


//+------------------------------------------------------------------+
//| Journal de reflexion : une ligne par bougie dans                 |
//| MQL8\Files\Ecurie_Journal\<robot>.txt (lisible au Bloc-notes)    |
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| L13 : combien d'annonces le flux contient-il ENCORE A VENIR ?     |
//|                                                                   |
//| Le 22 aout 2026, macrobot_news.txt ne contenait qu'un evenement,  |
//| vieux de trois jours. La fenetre de blocage etant de +/- 30 min,  |
//| le filtre ne pouvait mathematiquement plus rien bloquer — et il   |
//| ecrivait quand meme « libre » dans le bloc-notes. « Libre » et    |
//| « aveugle » devenaient indiscernables. Ils ne le sont plus.       |
//+------------------------------------------------------------------+
int NewsEvenementsAVenir()
  {
   int fh = FileOpen("macrobot_news.txt",
                     FILE_READ | FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_TXT | FILE_ANSI);
   if(fh == INVALID_HANDLE) return(-1);            // -1 = flux illisible
   long maintenant = (long)TimeGMT();
   int n = 0;
   while(!FileIsEnding(fh))
     {
      string ligne = FileReadString(fh);
      if(StringFind(ligne, "EVENT=") != 0) continue;
      string reste = StringSubstr(ligne, 6);
      int sep = StringFind(reste, ";");
      long epoch = StringToInteger(sep > 0 ? StringSubstr(reste, 0, sep) : reste);
      if(epoch > maintenant) n++;
     }
   FileClose(fh);
   return(n);
  }

string EtatFluxNouvelles()
  {
   int n = NewsEvenementsAVenir();
   if(n < 0)  return("AVEUGLE (flux illisible)");
   if(n == 0) return("AVEUGLE (flux sans evenement futur)");
   return(StringFormat("libre (%d a venir)", n));
  }

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
   if(MQLInfoInteger(MQL_TESTER))
      GlobalVariablesDeleteAll("MACROBOT_");   // testeur : purge des gardiens entre les passes (correctif L3 MT4 porte en L4.3)
   if(Preset == PRESET_GOLD)
     {
      SwingLookback = 10; FibLo = 0.20; FibHi = 0.80;   // L4.32 : 10 JOURS (= moteur)
      RsiPull = 55.0; StopAtrMult = 3.0;
      TpR = 1.5; RetraceReentree = 0.25;    // I2
     }
   else // PRESET_NASDAQ
     {
      SwingLookback = 7;  FibLo = 0.10; FibHi = 0.90;   // L4.32 : 7 JOURS (= moteur)
      RsiPull = 60.0; StopAtrMult = 2.0;
      TpR = 1.0; RetraceReentree = 0.5;     // I2
     }

   if(false)   // L4.3 : periode H4 fixee en dur, l'avertissement n'a plus d'objet
      Print("ATTENTION: la strategie a ete calibree en H4, graphique actuel: ",
            EnumToString(_Period));

   hATR = iATR(_Symbol, PERIOD_D1, AtrPeriod);   // L4.32 : journalier (= moteur valide)   // L4.3 : H4 fixe, graphique sans importance
   hRSI = iRSI(_Symbol, PERIOD_D1, RsiPeriod, PRICE_CLOSE);   // L4.32 : journalier   // L4.3 : H4 fixe
   if(hATR == INVALID_HANDLE || hRSI == INVALID_HANDLE)
      return INIT_FAILED;

   trade.SetExpertMagicNumber(MagicNumber);

   if(!GlobalVariableCheck(BaseGV()))
     {
      double base = (ChallengeInitialBalance > 0)
                    ? ChallengeInitialBalance
                    : AccountInfoDouble(ACCOUNT_BALANCE);
      GlobalVariableSet(BaseGV(), base);
     }
   Print("L12-R13 | objectif de phase=", ObjectifPhasePct, "% (+", MargeObjectifPct, "% de coussin) gardien=", LimitePerteJourPct, "%");
   Print("MacroBot L12 demarre (indicateurs journaliers). Baseline: ", DoubleToString(GlobalVariableGet(BaseGV()), 2),
         " | TP ", DoubleToString(TpR, 1), "R, re-entree ", DoubleToString(RetraceReentree, 2),
         "xATR, plafond ecurie ", MaxPositionsEcurie);

   EventSetTimer(60);
   RafraichirDonneesExternes();
   return INIT_SUCCEEDED;
  }

//+------------------------------------------------------------------+
void OnTimer()
  {
   ReleverEquite();
   RafraichirDonneesExternes();
   LireFacteurVol();
   if(facteurVol > 1.0) facteurVol = 1.0;   // L8 : jamais amplifier, challenge ou pas
   ProtegerPositionsNews();
  }

//+------------------------------------------------------------------+
void RafraichirDonneesExternes()
  {
   bool b = MacroBias();
   bool n = NewsBlocks();
   if(cacheInitFait)
     {
      if(b != cacheBiasOK)
         Notifier(b ? "Biais macro : ACHATS PERMIS" : "Biais macro : ACHATS BLOQUES");
      if(n != cacheNewsBloq)
         Notifier(n ? "Annonce USD imminente : entrees bloquees, stops en protection."
                    : "Fenetre d'annonce terminee : retour a la normale.");
     }
   cacheBiasOK   = b;
   cacheNewsBloq = n;
   cacheInitFait = true;
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   if(hATR != INVALID_HANDLE) IndicatorRelease(hATR);
   if(hRSI != INVALID_HANDLE) IndicatorRelease(hRSI);
  }

//+------------------------------------------------------------------+
bool GuardianBlocks()
  {
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double base   = GlobalVariableGet(BaseGV());

   if(GlobalVariableCheck(HaltGV()) && GlobalVariableGet(HaltGV()) > 0.5)
     {
      CloseAllOurs("");   // L4.32 : on retente la fermeture a chaque tick
      return true;
     }

   // ---- L8-R13 : OBJECTIF DE PHASE ATTEINT -> on encaisse ----
   // FTMO valide sur le solde POSITIONS FERMEES. Tant que le profit reste
   // flottant il ne compte pas, et il peut repartir. Des que l'equite passe
   // l'objectif (plus un coussin pour le spread), on ferme tout et on arrete.
   if(base > 0 && ObjectifPhasePct > 0
      && equity >= base * (1.0 + (ObjectifPhasePct + MargeObjectifPct) / 100.0))
     {
      Notifier(StringFormat("OBJECTIF DE PHASE ATTEINT (+%.2f %%) - fermeture de tout, arret. Solde a encaisser : %.2f",
                            100.0 * (equity / base - 1.0), equity));
      CloseAllOurs("");
      GlobalVariableSet(HaltGV(), 1.0);
      GlobalVariableSet("MACROBOT_CIBLE_" + (string)AccountInfoInteger(ACCOUNT_LOGIN), equity);
      return true;
     }
   if(equity <= base * (1.0 - LimitePerteTotalePct / 100.0))
     {
      Notifier("PERTE TOTALE MAX ATTEINTE - fermeture du compte, arret definitif");
      CloseAllOurs("");
      GlobalVariableSet(HaltGV(), 1.0);
      return true;
     }

   MqlDateTime now;
   TimeToStruct(TimeCurrent(), now);
   string dayKey = StringFormat("MACROBOT_DAY_%04d%02d%02d_%s",
                                now.year, now.mon, now.day,
                                (string)AccountInfoInteger(ACCOUNT_LOGIN));
   if(!GlobalVariableCheck(dayKey))
      GlobalVariableSet(dayKey, GlobalVariableCheck(LastEqGV()) ? GlobalVariableGet(LastEqGV()) : equity);   // L4.32 : reference d'AVANT le gap
   double dayStart = GlobalVariableGet(dayKey);
   GlobalVariableSet(LastEqGV(), equity);   // L4.32
   static bool avisJourFait = false;
   if(equity <= dayStart * (1.0 - LimitePerteJourPct / 100.0))
     {
      if(!avisJourFait)
        {
         Notifier("Stop quotidien touche - fermeture du compte, pause jusqu'a demain");
         avisJourFait = true;
        }
      CloseAllOurs("");
      return true;
     }
   avisJourFait = false;
   return false;
  }

//+------------------------------------------------------------------+
void CloseAllOurs(string reason)
  {
   if(reason != "") Print("GARDIEN: ", reason);
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0 && PositionGetInteger(POSITION_MAGIC) == MagicNumber)
         trade.PositionClose(ticket);
     }
  }

//+------------------------------------------------------------------+
bool MacroBias()
  {
   if(!BiasFromFile)
      return MacroLongAllowed;
   long modifBias = (long)FileGetInteger("macrobot_bias.txt", FILE_MODIFY_DATE);   // L8
   if(modifBias > 0 && TimeCurrent() - (datetime)modifBias > 7 * 86400)
      return MacroLongAllowed;   // L8 : fichier perime -> neutre
   int fh = FileOpen("macrobot_bias.txt", FILE_READ | FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_TXT | FILE_ANSI);
   if(fh == INVALID_HANDLE)
      return MacroLongAllowed;
   string line = FileReadString(fh);
   FileClose(fh);
   string tag = (Preset == PRESET_GOLD) ? "GOLD=1" : "NAS=1";
   return (StringFind(line, tag) >= 0);
  }

//+------------------------------------------------------------------+
bool NewsBlocks()
  {
   if(!NewsFilterOn)
      return false;
   long modifNews = (long)FileGetInteger("macrobot_news.txt", FILE_MODIFY_DATE);   // L8
   if(modifNews > 0 && TimeCurrent() - (datetime)modifNews > 7 * 86400)
      return false;   // L8 : fichier perime -> neutre (pas de blocage fantome)
   int fh = FileOpen("macrobot_news.txt", FILE_READ | FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_TXT | FILE_ANSI);
   if(fh == INVALID_HANDLE)
      return false;
   long now = (long)TimeGMT();
   bool blocked = false;
   while(!FileIsEnding(fh))
     {
      string line = FileReadString(fh);
      if(StringFind(line, "EVENT=") != 0)
         continue;
      string rest = StringSubstr(line, 6);
      int sep = StringFind(rest, ";");
      long epoch = StringToInteger(sep > 0 ? StringSubstr(rest, 0, sep) : rest);
      if(epoch > 0 &&
         now >= epoch - (long)NewsMinutesAvant * 60 &&
         now <= epoch + (long)NewsMinutesApres * 60)
        {
         blocked = true;
         break;
        }
     }
   FileClose(fh);
   return blocked;
  }

//+------------------------------------------------------------------+
void ProtegerPositionsNews()
  {
   if(NewsProtectMode == NEWS_PROTECT_RIEN || !cacheNewsBloq)
      return;

   double atrBuf[];
   ArraySetAsSeries(atrBuf, true);
   if(CopyBuffer(hATR, 0, 1, 1, atrBuf) < 1)
      return;
   double serre = atrBuf[0] * 0.5;
   if(serre <= 0)
      return;
   double distMin = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != MagicNumber) continue;

      if(NewsProtectMode == NEWS_PROTECT_FERMER)
        {
         Print("Annonce imminente : fermeture preventive de ", ticket);
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
            Print("Fenetre d'annonce : stop serre a ", DoubleToString(nouveau, _Digits));
     }
  }

//+------------------------------------------------------------------+
void GererBreakeven()
  {
   if(!BreakevenActif) return;
   if(!PositionOuverte()) return;
   if(PositionGetInteger(POSITION_MAGIC) != MagicNumber) return;
   if(PositionGetInteger(POSITION_TYPE) != POSITION_TYPE_BUY) return;

   double entree = PositionGetDouble(POSITION_PRICE_OPEN);
   double sl     = PositionGetDouble(POSITION_SL);
   double tp     = PositionGetDouble(POSITION_TP);
   if(sl <= 0 || sl >= entree) return;

   double R   = entree - sl;
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(bid < entree + R) return;

   double distMin = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
   double nouveau = entree;
   if(nouveau > bid - distMin) nouveau = bid - distMin;
   nouveau = NormalizeDouble(nouveau, _Digits);
   if(nouveau <= sl) return;
   if(trade.PositionModify(PositionGetInteger(POSITION_TICKET), nouveau, tp))
      Notifier("Breakeven +1R : stop remonte au prix d'entree.");
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
   long modifVol = (long)FileGetInteger("macrobot_vol.txt", FILE_MODIFY_DATE);   // L4.32
   if(modifVol > 0 && TimeCurrent() - (datetime)modifVol > 7 * 86400)
     { facteurVol = 1.0; return; }   // L4.32 : fichier perime -> facteur neutre
   int fh = FileOpen("macrobot_vol.txt", FILE_READ | FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_TXT | FILE_ANSI);
   if(fh == INVALID_HANDLE)
     {
      // L13 : NE PAS remettre le facteur a 1.0 ici. Un echec de lecture est
      // presque toujours transitoire — le fichier est reecrit chaque heure
      // par la tache Windows, et l'EA tombe parfois pendant l'ecriture.
      // Remettre 1.0 faisait remonter le risque de 0,92 a 1,00 en silence,
      // soit 9 % de taille en plus, jusqu'a la lecture suivante. Constate
      // dans le journal du 22 aout 2026 : 13 impressions de la meme valeur
      // pour le seul robot petrole.
      if(!volLectureEchouee)
        {
         volLectureEchouee = true;
         Print("Facteur de volatilite : lecture impossible, on GARDE ",
               DoubleToString(facteurVol, 2));
        }
      return;
     }
   volLectureEchouee = false;
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
//+------------------------------------------------------------------+
//| L3 : verifie que la MARGE suffit, sinon reduit le lot ou annule   |
//| (sans ca l'ordre est rejete et le signal est perdu en silence)    |
//+------------------------------------------------------------------+
double LotSelonMarge(double lot)
  {
   double lotMin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double pas    = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double prix   = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double marge  = 0.0;
   int essais = 0;
   while(lot >= lotMin && essais < 12)
     {
      if(OrderCalcMargin(ORDER_TYPE_BUY, _Symbol, lot, prix, marge))
         if(marge < AccountInfoDouble(ACCOUNT_MARGIN_FREE) * 0.95)
            return(lot);
      lot -= MathMax(pas, lot * 0.2);
      if(pas > 0) lot = MathFloor(lot / pas) * pas;
      essais++;
     }
   Print("Marge insuffisante pour ouvrir : ordre annule.");
   return(0.0);
  }

//+------------------------------------------------------------------+
//| L3+ MODE CHALLENGE (throttle d'equite, Seykota) : sous la moyenne |
//| 20 jours de l'equite, les nouvelles entrees prennent un risque    |
//| reduit. Backtest : challenges morts 13 % -> 6 % pour -1,9 pt/an.  |
//+------------------------------------------------------------------+
double   HistoEquite[20];
int      HistoIndex = 0;
bool     HistoPlein = false;
datetime dernierReleve = 0;


//+------------------------------------------------------------------+
//| L8-R4 : le frein d'equite survit aux redemarrages.                |
//| Avant : tableau en memoire vive -> remis a zero a chaque relance, |
//| donc le mode challenge n'etait JAMAIS actif en production.        |
//+------------------------------------------------------------------+
string CleEqJour(datetime j)
  {
   MqlDateTime d; TimeToStruct(j, d);
   return(StringFormat("MACROBOT_EQJ_%04d%02d%02d_%s", d.year, d.mon, d.day,
                       (string)AccountInfoInteger(ACCOUNT_LOGIN)));
  }
void ReleverEquite()
  {
   datetime jour = iTime(_Symbol, PERIOD_D1, 0);
   if(jour <= 0 || jour == dernierReleve) return;
   dernierReleve = jour;
   string cle = CleEqJour(jour);
   if(!GlobalVariableCheck(cle))
      GlobalVariableSet(cle, AccountInfoDouble(ACCOUNT_EQUITY));   // L8-R4
   for(int k = 41; k <= 60; k++)                                   // menage
      GlobalVariableDel(CleEqJour(jour - k * 86400));
  }


double FacteurChallenge()
  {
   if(!ModeChallengeActif) return(1.0);
   datetime jour = iTime(_Symbol, PERIOD_D1, 0);
   double somme = 0; int n = 0;
   for(int k = 1; k <= 40 && n < 20; k++)          // L8-R4 : lit les GV
     {
      string cle = CleEqJour(jour - k * 86400);
      if(!GlobalVariableCheck(cle)) continue;
      somme += GlobalVariableGet(cle); n++;
     }
   if(n < 20) return(1.0);
   double moyenne = somme / n;
   if(moyenne > 0 && AccountInfoDouble(ACCOUNT_EQUITY) < moyenne) return(ThrottleChallenge);
   return(1.0);
  }


double LotsForRisk(double stopDist)
  {
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   if(tickSize <= 0 || tickValue <= 0)
      return 0;
   double lossPerLot = stopDist / tickSize * tickValue;
   if(lossPerLot <= 0)
      return 0;
   double riskMoney = AccountInfoDouble(ACCOUNT_EQUITY) * RiskPerTradePct / 100.0 * facteurVol * FacteurRisqueGlobal * FacteurTurbo() * FacteurChallenge();   // L12
   double lots = riskMoney / lossPerLot;

   double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   lots = MathFloor(lots / lotStep) * lotStep;
   if(lots < minLot)
      return 0;
   return LotSelonMarge(MathMin(lots, maxLot));
  }

//+------------------------------------------------------------------+
//| Ouvre un achat au prix du marche avec SL/TP calcules             |
//+------------------------------------------------------------------+
void OuvrirAchat(double stopDist, string commentaire)
  {
   double spreadCourant = SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID);   // L8
   if(SpreadEntreeMaxPct > 0 && spreadCourant > SpreadEntreeMaxPct / 100.0 * stopDist)
     {
      Print("L12 : entree reportee, spread ", DoubleToString(spreadCourant, _Digits), " > ", DoubleToString(SpreadEntreeMaxPct, 1), " % de la distance de stop");
      return;
     }
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double sl  = NormalizeDouble(ask - stopDist, _Digits);
   double tp  = NormalizeDouble(ask + stopDist * TpR, _Digits);
   double lots = LotsForRisk(stopDist);
   if(lots <= 0) return;
   if(trade.Buy(lots, _Symbol, 0.0, sl, tp, commentaire))
      Print("ENTREE LONG ", _Symbol, " lots=", DoubleToString(lots, 2),
            " SL=", sl, " TP=", tp, " (", commentaire, ")");
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   if(GuardianBlocks())
      return;

   ProtegerPositionsNews();
   GererBreakeven();

   datetime barTime = iTime(_Symbol, PERIOD_H4, 0);   // L4.3 : decision par barre H4 fixe
   if(barTime == lastBar)
      return;
   lastBar = barTime;

   EcrireJournal(StringFormat("cloture=%.2f | position=%s | biais_macro=%s | news=%s | facteurVol=%.2f | reentree_armee=%s | plancher_swing=%.2f",
      iClose(_Symbol, PERIOD_D1, 1), (PositionOuverte() ? "OUVERTE" : "aucune"),
      (cacheBiasOK ? "OK" : "BLOQUE"), (cacheNewsBloq ? "FENETRE ANNONCE" : EtatFluxNouvelles()),
      facteurVol, (attenteReentree > 0 ? "OUI" : "non"), plancherSwing));

   if(PositionOuverte())
      return;
   if(!cacheBiasOK)
      { EcrireJournal("refus=biais_macro"); return; }
   if(cacheNewsBloq)
      { EcrireJournal("refus=fenetre_annonce"); return; }

   int need = SwingLookback + 5;
   MqlRates rates[];
   if(CopyRates(_Symbol, PERIOD_D1, 0, need, rates) < need)   // L4.32 : swing sur jours
      return;
   ArraySetAsSeries(rates, true);

   double atrBuf[];
   if(CopyBuffer(hATR, 0, 1, 1, atrBuf) < 1)
      return;
   double stopDist = StopAtrMult * atrBuf[0];
   if(stopDist <= 0)
      return;

   // swing haussier sur les bougies fermees
   int hiIdx = 1, loIdx = 1;
   for(int i = 1; i <= SwingLookback; i++)
     {
      if(rates[i].high > rates[hiIdx].high) hiIdx = i;
      if(rates[i].low  < rates[loIdx].low)  loIdx = i;
     }
   bool swingOK = (loIdx > hiIdx);
   double hi = rates[hiIdx].high, lo = rates[loIdx].low;
   double span = hi - lo;

   // invalidation de la re-entree : le plancher du swing d'origine a casse
   if(attenteReentree > 0 && plancherSwing > 0 && rates[1].close < plancherSwing)
     {
      attenteReentree = 0;
      plancherSwing = 0;
      Print("Plancher du swing casse : re-entree annulee.");
     }

   // --- Entree 1 : setup fib+RSI complet (comme V1) ---
   bool setup = false;
   if(swingOK && span > 0)
     {
      double retrace = (hi - rates[1].close) / span;
      if(retrace >= FibLo && retrace <= FibHi)
        {
         double rsi[];
         if(CopyBuffer(hRSI, 0, 1, 2, rsi) >= 2)
           {
            ArraySetAsSeries(rsi, true);
            setup = (rsi[1] < RsiPull && rsi[0] > rsi[1]);
           }
        }
     }
   if(setup)
     {
      if(ComptePositionsEcurie() >= MaxPositionsEcurie) { EcrireJournal("refus=plafond_ecurie"); return; }
   if(FamilleCorreleeOccupee()) { EcrireJournal("refus=famille_correlee"); return; }   // plafond de correlation   // plafond (I2)
      plancherSwing = lo;
      attenteReentree = 0;
      OuvrirAchat(stopDist, "Ecurie_L8 fib+RSI");
      return;
     }

   // --- Entree 2 (I2) : re-entree sur repli apres un TP encaisse ---
   if(attenteReentree > 0 && plancherSwing > 0 &&
      rates[1].low <= attenteReentree - RetraceReentree * atrBuf[0] &&
      rates[1].close > plancherSwing)
     {
      if(ComptePositionsEcurie() >= MaxPositionsEcurie) { EcrireJournal("refus=plafond_ecurie"); return; }
   if(FamilleCorreleeOccupee()) { EcrireJournal("refus=famille_correlee"); return; }   // plafond de correlation   // plafond (I2)
      Print("Repli atteint apres TP : re-entree.");
      OuvrirAchat(stopDist, "Ecurie_L8 re-entree");
      attenteReentree = 0;
     }
  }
//+------------------------------------------------------------------+
