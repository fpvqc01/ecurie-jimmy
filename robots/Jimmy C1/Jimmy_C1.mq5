//+------------------------------------------------------------------+
//| Jimmy C1 v1.10 — ecurie crypto H4 (BTC/ETH/SOL), challenge FTMO  |
//|                                                                  |
//| UN SEUL fichier, attache 3 fois (un graphique H4 par symbole).   |
//| 3 canaux Donchian (ensemble 10/20/40 j) par graphique, une pile  |
//| d'unites par canal, magics distincts par canal.                  |
//|                                                                  |
//| v1.10 (23 aout 2026) : reecriture apres le comite adversarial.   |
//|  - canaux calcules sur les barres 2..N+1 (la barre de decision   |
//|    est EXCLUE — v1.00 ne pouvait jamais entrer) ;                |
//|  - variables globales prefixees par NUMERO DE COMPTE : la phase 2|
//|    (nouveau login) repart automatiquement propre ;               |
//|  - valeurs par defaut = configuration C1 VALIDEE au banc ;       |
//|  - solde de minuit RECONSTRUIT depuis l'historique des deals     |
//|    au premier chargement du jour (redemarrage sur) ;             |
//|  - verrou d'objectif relache si les frais mangent la marge ;     |
//|  - fermetures avec code de retour + relance espacee (5 s) —      |
//|    jamais de rafale de requetes (limite FTMO ~2000/jour) ;       |
//|  - une pyramide max par barre H4 par canal ;                     |
//|  - replis armes PERSISTES en variables globales ;                |
//|  - barre non marquee « traitee » si l'historique n'est pas pret ;|
//|  - calendrier en cache memoire (relu toutes les 15 min) ;        |
//|  - journal anti-repetition ; deviation proportionnelle au prix ; |
//|  - CPPI desactive par defaut (CppiMax=0), comme au banc.         |
//|                                                                  |
//| Fichiers du cerveau Python (MQL5\Files\CryptoEcurie\) : freins   |
//| OPTIONNELS — fichier absent/perime/tronque => le robot continue  |
//| sans le filtre. Sentinelle fin=1 exigee sur regime.txt.          |
//+------------------------------------------------------------------+
#property copyright "Jimmy - ecurie crypto C1"
#property version   "1.10"
#property strict

#include <Trade\Trade.mqh>

//--- identite (magic = MagicBase + offset marche + canal 1..3)
input long     MagicBase            = 20264000;  // C1 reserve 20264011-20264033
input int      OffsetMarche         = 0;         // 0 = auto (BTC=10, ETH=20, SOL=30)
input double   CapitalInitialFTMO   = 0;         // capital INITIAL du challenge — OBLIGATOIRE

//--- strategie : configuration C1 VALIDEE (banc D/F/R du 23 aout 2026)
input int      Canal1Entree = 60;   input int Canal1Sortie = 30;    // 10/5 jours (barres H4)
input int      Canal2Entree = 120;  input int Canal2Sortie = 60;    // 20/10 jours
input int      Canal3Entree = 240;  input int Canal3Sortie = 120;   // 40/20 jours
input double   StopATR              = 2.0;       // stop = derniere unite - StopATR x ATR journalier
input double   PasPyramideATR       = 0.5;
input int      UnitesMax            = 4;
input int      PilesMax             = 6;         // piles (marche x canal) simultanees, ecurie entiere
input double   RisqueUniteP         = 0.35;      // % de l'equite de minuit par unite
input double   HeatMaxP             = 3.0;       // % : somme des risques au stop, 3 graphiques
input double   LevierMax            = 0.90;      // notionnel total / equite (FTMO Swing crypto 1:1)
input double   NotionnelMarcheMax   = 0.50;      // notionnel de CE symbole / equite
input bool     VentesActives        = false;     // NON valide au banc (66 % vs 91 %) — garder false
input bool     VenteSousEMA200Seul  = true;
input double   RepliKATR            = 0;         // repli conditionnel : REJETE au banc — garder 0
input double   RepliSeuilForce      = 1.0;
input int      RepliBarresMax       = 30;
input int      SortieTempsJours     = 15;        // sortie anti-swap : LE mecanisme gagnant du banc
input double   SortieTempsSeuilR    = 0.0;       // fermer si profit(+swap) < 0 apres 15 jours

//--- protections FTMO
input double   PerteJourFTMOP       = 5.0;
input double   CoussinJourP         = 1.0;       // gardien : plancher FTMO jour + coussin...
input double   GardienJourP         = 2.5;       // ...ou equite_minuit x (1-gardien), le plus haut
input double   PerteTotaleFTMOP     = 10.0;
input double   CoussinTotalP        = 0.25;      // HALT a -9,75 % (couper plus tot = echec certain)
input double   ObjectifPhaseP       = 10.0;      // 10 phase 1, 5 phase 2, 0 = compte finance
input double   MargeObjectifP       = 0.25;
input bool     MicroTradesJoursMin  = true;      // complete les 4 jours de trading FTMO apres verrou
input int      JoursMinFTMO         = 4;
input double   CppiMax              = 0;         // 0 = DESACTIVE (comme au banc) ; >0 = actif
input double   CppiPlancherP        = 10.0;

//--- fichiers du cerveau Python
input bool     LireRegime           = true;
input bool     LireCalendrier       = false;     // fenetres d'evenements : REJETEES au banc — off
input int      EvenementFenetreH    = 2;
input int      RegimePerimeH        = 48;

//--- divers
input int      ATRJours             = 20;
input double   EcartMaxSpreadP      = 0.30;      // % : pas de nouvelle exposition si spread plus large
input double   DeviationP           = 0.05;      // % du prix tolere en glissement d'ordre

CTrade  trade;
string  PREF = "";                               // "C1_<login>_" — par compte (phase 2 propre)
int     hATR = INVALID_HANDLE, hEMA50 = INVALID_HANDLE, hEMA200 = INVALID_HANDLE;
datetime derniereBarre = 0;
int     offsetM = 0;
int     canaux_e[3], canaux_s[3];
datetime dernierAjout[3] = {0, 0, 0};            // une pyramide max par barre H4 par canal
datetime dernierEssaiFerme = 0;                  // espacement des rafales de fermeture (5 s)
datetime dernierMicroTrade = 0;
long    jourAncre = -1;
// cache du calendrier (relu au plus toutes les 15 min)
datetime calCache[64];
int      calN = 0;
datetime calLu = 0;
// regime (dernieres valeurs valides)
double   regimeML = 1.0;
bool     regimePorteAchat = true;
datetime regimeMaj = 0, regimeLu = 0;
// journal anti-repetition
string   dernierRefus = "";
datetime dernierRefusT = 0;

//+------------------------------------------------------------------+
long MagicCanal(int c) { return MagicBase + offsetM + c + 1; }
bool EstNotreMagic(long m) { return m > MagicBase && m <= MagicBase + 39; }
bool EstMagicLocal(long m) { return m > MagicBase + offsetM && m <= MagicBase + offsetM + 3; }
string GV(string nom) { return PREF + nom; }
string GVHeat() { return PREF + "HEAT_" + IntegerToString(MagicBase + offsetM); }

//+------------------------------------------------------------------+
int OnInit()
  {
   if(AccountInfoInteger(ACCOUNT_MARGIN_MODE) != ACCOUNT_MARGIN_MODE_RETAIL_HEDGING)
     { Print("C1 REFUSE : compte NETTING (il faut un compte hedging)."); return(INIT_FAILED); }
   if(CapitalInitialFTMO <= 0)
     { Print("C1 REFUSE : CapitalInitialFTMO doit etre regle au capital exact du challenge."); return(INIT_FAILED); }
   // offset auto par symbole — evite la collision de magics par erreur humaine
   offsetM = OffsetMarche;
   if(offsetM == 0)
     {
      if(StringFind(_Symbol, "BTC") >= 0) offsetM = 10;
      else if(StringFind(_Symbol, "ETH") >= 0) offsetM = 20;
      else if(StringFind(_Symbol, "SOL") >= 0) offsetM = 30;
      else { Print("C1 REFUSE : symbole inconnu (", _Symbol, ") — regler OffsetMarche a la main."); return(INIT_FAILED); }
     }
   PREF = "C1_" + IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN)) + "_";
   canaux_e[0] = Canal1Entree; canaux_s[0] = Canal1Sortie;
   canaux_e[1] = Canal2Entree; canaux_s[1] = Canal2Sortie;
   canaux_e[2] = Canal3Entree; canaux_s[2] = Canal3Sortie;
   hATR    = iATR(_Symbol, PERIOD_D1, ATRJours);
   hEMA50  = iMA(_Symbol, PERIOD_D1, 50, 0, MODE_EMA, PRICE_CLOSE);
   hEMA200 = iMA(_Symbol, PERIOD_D1, 200, 0, MODE_EMA, PRICE_CLOSE);
   if(hATR == INVALID_HANDLE || hEMA50 == INVALID_HANDLE || hEMA200 == INVALID_HANDLE)
      return(INIT_FAILED);
   // ne pas rejouer la derniere barre fermee au redemarrage
   derniereBarre = iTime(_Symbol, PERIOD_H4, 0);
   RestaurerRepli();
   EventSetTimer(30);
   string etat = "";
   if(GlobalVariableCheck(GV("HALT")))   etat += " *** HALT ACTIF (plancher total touche) ***";
   if(GlobalVariableCheck(GV("VERROU"))) etat += " *** VERROU D'OBJECTIF ACTIF ***";
   Journal("C1 v1.10 charge. compte " + IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN))
           + " magic " + IntegerToString(MagicBase + offsetM)
           + " capital " + DoubleToString(CapitalInitialFTMO, 0)
           + " objectif " + DoubleToString(ObjectifPhaseP, 1) + " %" + etat);
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int raison)
  {
   EventKillTimer();
   if(hATR != INVALID_HANDLE) IndicatorRelease(hATR);
   if(hEMA50 != INVALID_HANDLE) IndicatorRelease(hEMA50);
   if(hEMA200 != INVALID_HANDLE) IndicatorRelease(hEMA200);
   // purge du heat SEULEMENT si le robot est retire sans positions (sinon les
   // autres graphiques sous-compteraient le risque encore ouvert)
   if((raison == REASON_REMOVE || raison == REASON_CHARTCLOSE) && !aDesPositionsLocales())
      GlobalVariableDel(GVHeat());
  }

//+------------------------------------------------------------------+
//| Journal (anti-repetition : un meme refus au plus 1 fois / 5 min) |
//+------------------------------------------------------------------+
void Journal(string txt)
  {
   int f = FileOpen("CryptoEcurie\\journal_" + _Symbol + ".txt",
                    FILE_WRITE | FILE_READ | FILE_TXT | FILE_ANSI);
   if(f != INVALID_HANDLE)
     {
      FileSeek(f, 0, SEEK_END);
      FileWrite(f, TimeToString(TimeTradeServer(), TIME_DATE | TIME_MINUTES) + " | " + txt);
      FileClose(f);
     }
   Print(txt);
  }

void JournalRefus(string raison)
  {
   if(raison == dernierRefus && TimeTradeServer() - dernierRefusT < 300) return;
   dernierRefus = raison;
   dernierRefusT = TimeTradeServer();
   Journal("refus=" + raison);
  }

//+------------------------------------------------------------------+
//| Etat reconstruit des positions (redemarrage sur)                 |
//+------------------------------------------------------------------+
int UnitesDuCanal(int c, double &dernierPx, double &qtyTot, double &moy, int &sens)
  {
   long magic = MagicCanal(c);
   int n = 0; dernierPx = 0; qtyTot = 0; sens = 0;
   double somme = 0;
   datetime tmax = 0;
   ulong tkmax = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || !PositionSelectByTicket(tk)) continue;
      if(PositionGetInteger(POSITION_MAGIC) != magic) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      double vol = PositionGetDouble(POSITION_VOLUME);
      double px  = PositionGetDouble(POSITION_PRICE_OPEN);
      datetime t = (datetime)PositionGetInteger(POSITION_TIME);
      sens = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? 1 : -1;
      n++; qtyTot += vol; somme += vol * px;
      // derniere unite = temps le plus recent ; egalite tranchee par le ticket
      if(t > tmax || (t == tmax && tk > tkmax)) { tmax = t; tkmax = tk; dernierPx = px; }
     }
   moy = (qtyTot > 0) ? somme / qtyTot : 0;
   return n;
  }

datetime PremiereEntreeDuCanal(int c)
  {
   long magic = MagicCanal(c);
   datetime t0 = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || !PositionSelectByTicket(tk)) continue;
      if(PositionGetInteger(POSITION_MAGIC) != magic) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      datetime t = (datetime)PositionGetInteger(POSITION_TIME);
      if(t0 == 0 || t < t0) t0 = t;
     }
   return t0;
  }

double ProfitDuCanal(int c)
  {
   // profit latent NET : P&L + swap deja paye (le swap accumule compte, banc R)
   long magic = MagicCanal(c);
   double p = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || !PositionSelectByTicket(tk)) continue;
      if(PositionGetInteger(POSITION_MAGIC) != magic) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      p += PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
     }
   return p;
  }

double ValeurPerte(double distancePrix, double vol)
  {
   double tv = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE_LOSS);
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tv <= 0) tv = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   if(tv <= 0 || ts <= 0) return 0;
   return distancePrix / ts * tv * vol;
  }

double RisqueAuStop(int c)
  {
   long magic = MagicCanal(c);
   double r = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || !PositionSelectByTicket(tk)) continue;
      if(PositionGetInteger(POSITION_MAGIC) != magic) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      double sl = PositionGetDouble(POSITION_SL);
      if(sl <= 0) continue;
      int sens = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? 1 : -1;
      double perte = (PositionGetDouble(POSITION_PRICE_OPEN) - sl) * sens;
      if(perte > 0) r += ValeurPerte(perte, PositionGetDouble(POSITION_VOLUME));
     }
   return r;
  }

double NotionnelLocal()
  {
   double n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || !PositionSelectByTicket(tk)) continue;
      if(!EstMagicLocal(PositionGetInteger(POSITION_MAGIC))) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      n += PositionGetDouble(POSITION_VOLUME)
           * SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE)
           * PositionGetDouble(POSITION_PRICE_CURRENT);
     }
   return n;
  }

double NotionnelEcurie()
  {
   double n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || !PositionSelectByTicket(tk)) continue;
      if(!EstNotreMagic(PositionGetInteger(POSITION_MAGIC))) continue;
      string s = PositionGetString(POSITION_SYMBOL);
      SymbolSelect(s, true);      // hors Market Watch, contrat/prix vaudraient 0
      double contrat = SymbolInfoDouble(s, SYMBOL_TRADE_CONTRACT_SIZE);
      if(contrat <= 0) contrat = 1;
      n += PositionGetDouble(POSITION_VOLUME) * contrat
           * PositionGetDouble(POSITION_PRICE_CURRENT);
     }
   return n;
  }

int PilesOuvertesEcurie()
  {
   long vus[40];
   int nv = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || !PositionSelectByTicket(tk)) continue;
      long m = PositionGetInteger(POSITION_MAGIC);
      if(!EstNotreMagic(m)) continue;
      bool deja = false;
      for(int j = 0; j < nv; j++) if(vus[j] == m) { deja = true; break; }
      if(!deja && nv < 40) vus[nv++] = m;
     }
   return nv;
  }

double HeatEcurie()
  {
   double local = 0;
   for(int c = 0; c < 3; c++) local += RisqueAuStop(c);
   GlobalVariableSet(GVHeat(), local);
   double total = 0;
   for(int i = GlobalVariablesTotal() - 1; i >= 0; i--)
     {
      string nom = GlobalVariableName(i);
      if(StringFind(nom, PREF + "HEAT_") == 0) total += GlobalVariableGet(nom);
     }
   return total;
  }

bool aDesPositionsLocales()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || !PositionSelectByTicket(tk)) continue;
      if(EstMagicLocal(PositionGetInteger(POSITION_MAGIC))
         && PositionGetString(POSITION_SYMBOL) == _Symbol) return true;
     }
   return false;
  }

//+------------------------------------------------------------------+
//| Ancre de minuit — reconstruite depuis l'historique au besoin     |
//+------------------------------------------------------------------+
double SoldeMinuitDepuisHistorique(datetime minuit)
  {
   // solde de minuit = solde actuel - (profits realises depuis minuit)
   double depuis = 0;
   if(HistorySelect(minuit, TimeTradeServer() + 60))
      for(int i = HistoryDealsTotal() - 1; i >= 0; i--)
        {
         ulong tk = HistoryDealGetTicket(i);
         if(tk == 0) continue;
         depuis += HistoryDealGetDouble(tk, DEAL_PROFIT)
                   + HistoryDealGetDouble(tk, DEAL_SWAP)
                   + HistoryDealGetDouble(tk, DEAL_COMMISSION);
        }
   return AccountInfoDouble(ACCOUNT_BALANCE) - depuis;
  }

void MettreAJourAncre()
  {
   MqlDateTime dt;
   TimeToStruct(TimeTradeServer(), dt);
   long jour = (long)dt.year * 10000 + dt.mon * 100 + dt.day;
   if(jourAncre == jour) return;
   string gvJour = GV("JOUR");
   if(GlobalVariableCheck(gvJour) && (long)GlobalVariableGet(gvJour) == jour)
     { jourAncre = jour; return; }
   // nouveau jour (ou premier chargement) : ancre reconstruite depuis les deals
   dt.hour = 0; dt.min = 0; dt.sec = 0;
   datetime minuit = StructToTime(dt);
   double soldeMinuit = SoldeMinuitDepuisHistorique(minuit);
   GlobalVariableSet(gvJour, (double)jour);
   GlobalVariableSet(GV("SOLDE_MINUIT"), soldeMinuit);
   GlobalVariableSet(GV("EQ_MINUIT"), AccountInfoDouble(ACCOUNT_EQUITY));
   jourAncre = jour;
   // menage des gels des jours passes
   for(int i = GlobalVariablesTotal() - 1; i >= 0; i--)
     {
      string nom = GlobalVariableName(i);
      if(StringFind(nom, GV("GELE_")) == 0 && nom != GV("GELE_" + IntegerToString(jour)))
         GlobalVariableDel(nom);
     }
   Journal("ancre du jour : solde minuit " + DoubleToString(soldeMinuit, 2)
           + " (reconstruit) equite " + DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY), 2));
  }

bool JourGele() { return GlobalVariableCheck(GV("GELE_" + IntegerToString(jourAncre))); }
void GelerJour() { GlobalVariableSet(GV("GELE_" + IntegerToString(jourAncre)), 1); }
bool HaltTotal() { return GlobalVariableCheck(GV("HALT")); }
bool Verrouille() { return GlobalVariableCheck(GV("VERROU")); }

double PlancherJour()
  {
   double soldeMinuit = GlobalVariableCheck(GV("SOLDE_MINUIT"))
                        ? GlobalVariableGet(GV("SOLDE_MINUIT"))
                        : AccountInfoDouble(ACCOUNT_BALANCE);
   return soldeMinuit - CapitalInitialFTMO * PerteJourFTMOP / 100.0;
  }

double NiveauGardienJour()
  {
   double eqMinuit = GlobalVariableCheck(GV("EQ_MINUIT"))
                     ? GlobalVariableGet(GV("EQ_MINUIT"))
                     : AccountInfoDouble(ACCOUNT_EQUITY);
   double a = PlancherJour() + CapitalInitialFTMO * CoussinJourP / 100.0;
   double b = eqMinuit * (1.0 - GardienJourP / 100.0);
   return MathMax(a, b);
  }

double NiveauGardienTotal()
  { return CapitalInitialFTMO * (1.0 - (PerteTotaleFTMOP - CoussinTotalP) / 100.0); }

//+------------------------------------------------------------------+
//| Fichiers du cerveau (frein OPTIONNEL, jamais un organe)          |
//+------------------------------------------------------------------+
void LireFichierRegime()
  {
   if(!LireRegime || TimeTradeServer() - regimeLu < 300) return;    // au plus 1x / 5 min
   regimeLu = TimeTradeServer();
   int f = FileOpen("CryptoEcurie\\regime.txt", FILE_READ | FILE_TXT | FILE_ANSI);
   if(f == INVALID_HANDLE) return;
   double ml = 1.0;
   bool porte = true, complet = false;
   datetime maj = 0;
   while(!FileIsEnding(f))
     {
      string ligne = FileReadString(f);
      int p = StringFind(ligne, "=");
      if(p <= 0) continue;
      string cle = StringSubstr(ligne, 0, p), val = StringSubstr(ligne, p + 1);
      if(cle == "maj") maj = StringToTime(val);
      else if(cle == "porte_achat") porte = (StringToInteger(val) != 0);
      else if(cle == "ml_" + _Symbol) ml = StringToDouble(val);
      else if(cle == "fin") complet = (StringToInteger(val) == 1);
     }
   FileClose(f);
   if(!complet) return;                       // fichier a moitie ecrit : on garde l'ancien etat
   // horodatage en GMT (contrat avec cerveau.py) ; perime => filtres neutres
   if(maj == 0 || TimeGMT() - maj > RegimePerimeH * 3600) { porte = true; ml = 1.0; }
   regimeMaj = maj;
   regimePorteAchat = porte;
   regimeML = MathMin(1.3, MathMax(0.5, ml));
  }

void LireFichierCalendrier()
  {
   if(!LireCalendrier || TimeTradeServer() - calLu < 900) return;   // au plus 1x / 15 min
   calLu = TimeTradeServer();
   calN = 0;
   int f = FileOpen("CryptoEcurie\\calendrier.txt", FILE_READ | FILE_TXT | FILE_ANSI);
   if(f == INVALID_HANDLE) return;
   while(!FileIsEnding(f) && calN < 64)
     {
      string ligne = FileReadString(f);
      if(StringLen(ligne) < 10) continue;
      datetime ev = StringToTime(StringSubstr(ligne, 0, 16));
      if(ev > 0) calCache[calN++] = ev;
     }
   FileClose(f);
  }

bool DansFenetreEvenement()
  {
   if(!LireCalendrier || EvenementFenetreH <= 0 || calN == 0) return false;
   datetime mnt = TimeGMT();
   for(int i = 0; i < calN; i++)
      if(MathAbs((long)(mnt - calCache[i])) <= (long)EvenementFenetreH * 3600) return true;
   return false;
  }

//+------------------------------------------------------------------+
//| Replis armes — persistes en variables globales                   |
//+------------------------------------------------------------------+
double replNiveau[3] = {0, 0, 0};
int    replSens[3] = {0, 0, 0};
int    replReste[3] = {0, 0, 0};

void SauverRepli(int c)
  {
   string base = GV("REPL_" + IntegerToString(MagicCanal(c)));
   if(replSens[c] == 0)
     { GlobalVariableDel(base + "_S"); GlobalVariableDel(base + "_N"); GlobalVariableDel(base + "_R"); }
   else
     {
      GlobalVariableSet(base + "_S", replSens[c]);
      GlobalVariableSet(base + "_N", replNiveau[c]);
      GlobalVariableSet(base + "_R", replReste[c]);
     }
  }

void RestaurerRepli()
  {
   for(int c = 0; c < 3; c++)
     {
      string base = GV("REPL_" + IntegerToString(MagicCanal(c)));
      if(GlobalVariableCheck(base + "_S"))
        {
         replSens[c] = (int)GlobalVariableGet(base + "_S");
         replNiveau[c] = GlobalVariableGet(base + "_N");
         replReste[c] = (int)GlobalVariableGet(base + "_R");
        }
     }
  }

//+------------------------------------------------------------------+
//| Indicateurs journaliers (barre COMPLETE d'hier : decalage 1)     |
//+------------------------------------------------------------------+
bool LireJournalier(double &atr, double &ema50, double &ema200)
  {
   double a[1], e5[1], e2[1];
   if(CopyBuffer(hATR, 0, 1, 1, a) != 1) return false;
   if(CopyBuffer(hEMA50, 0, 1, 1, e5) != 1) return false;
   if(CopyBuffer(hEMA200, 0, 1, 1, e2) != 1) return false;
   atr = a[0]; ema50 = e5[0]; ema200 = e2[0];
   if(atr == EMPTY_VALUE || ema50 == EMPTY_VALUE || ema200 == EMPTY_VALUE) return false;
   return (atr > 0);
  }

// plus haut / plus bas des nb barres PRECEDANT la barre de decision.
// La barre de decision (index 1) est EXCLUE : on copie a partir de l'index 2.
// v1.00 copiait depuis 1 : une cloture ne depasse jamais le plus haut de sa
// propre barre -> le robot ne pouvait JAMAIS entrer (verdict du comite).
double PlusHaut(int nb)
  {
   double h[];
   ArraySetAsSeries(h, true);
   if(CopyHigh(_Symbol, PERIOD_H4, 2, nb, h) != nb) return EMPTY_VALUE;
   return h[ArrayMaximum(h)];
  }
double PlusBas(int nb)
  {
   double l[];
   ArraySetAsSeries(l, true);
   if(CopyLow(_Symbol, PERIOD_H4, 2, nb, l) != nb) return EMPTY_VALUE;
   return l[ArrayMinimum(l)];
  }

//+------------------------------------------------------------------+
//| Taille d'une unite (reduction aux plafonds, comme le moteur)     |
//+------------------------------------------------------------------+
double TailleUnite(double px, double atr, string &refus)
  {
   double eqMinuit = GlobalVariableCheck(GV("EQ_MINUIT"))
                     ? GlobalVariableGet(GV("EQ_MINUIT"))
                     : AccountInfoDouble(ACCOUNT_EQUITY);
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   double f = 1.0;
   if(CppiMax > 0 && CppiPlancherP > 0)
     {
      double plancher = CapitalInitialFTMO * (1.0 - CppiPlancherP / 100.0);
      double coussin = (eqMinuit - plancher) / MathMax(eqMinuit, 1);
      f = MathMax(0.0, MathMin(CppiMax, CppiMax * coussin / (CppiPlancherP / 100.0)));
     }
   f *= regimeML;
   if(f <= 0.05) { refus = "facteur0"; return 0; }

   double dist = StopATR * atr;
   double risque = RisqueUniteP / 100.0 * eqMinuit * f;
   double perteParLot = ValeurPerte(dist, 1.0);
   if(perteParLot <= 0) { refus = "symbole"; return 0; }
   double vol = risque / perteParLot;

   if(HeatEcurie() + risque > HeatMaxP / 100.0 * eq) { refus = "heat"; return 0; }
   if(PilesOuvertesEcurie() >= PilesMax && !aPileLocale()) { refus = "piles_max"; return 0; }

   double contrat = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   double notion = vol * contrat * px;
   // plafond par marche : REDUIRE pour tenir dans le reste (comme le moteur)
   double resteM = NotionnelMarcheMax * eq - NotionnelLocal();
   if(notion > resteM)
     {
      if(resteM <= 0.05 * notion) { refus = "notionnel_marche"; return 0; }
      vol = resteM / (contrat * px);
      notion = resteM;
     }
   double resteL = LevierMax * eq - NotionnelEcurie();
   if(notion > resteL)
     {
      if(resteL <= 0.05 * notion) { refus = "levier"; return 0; }
      vol = resteL / (contrat * px);
     }
   double volMin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double volPas = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double volMax = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   if(volPas <= 0) volPas = volMin > 0 ? volMin : 0.01;
   vol = NormalizeDouble(MathFloor(vol / volPas + 1e-9) * volPas, 8);
   if(vol < volMin) { refus = "trop_petit"; return 0; }
   if(vol > volMax) vol = volMax;
   return vol;
  }

bool aPileLocale()
  {
   // la pyramide d'une pile deja ouverte n'est pas une nouvelle pile
   return aDesPositionsLocales();
  }

bool SpreadTropLarge()
  {
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(ask <= 0 || bid <= 0) return true;
   return (ask - bid) / ask * 100.0 > EcartMaxSpreadP;
  }

void PreparerTrade()
  {
   double px = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double pt = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   int dev = 50;
   if(px > 0 && pt > 0) dev = (int)MathMax(50.0, px * DeviationP / 100.0 / pt);
   trade.SetDeviationInPoints(dev);
   trade.SetTypeFillingBySymbol(_Symbol);
  }

double AjusterStop(double stop)
  {
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(ts > 0) stop = MathRound(stop / ts) * ts;
   return NormalizeDouble(stop, _Digits);
  }

//+------------------------------------------------------------------+
//| Fermetures avec code de retour (jamais de rafale)                |
//+------------------------------------------------------------------+
bool FermerCanal(int c, string raison)
  {
   long magic = MagicCanal(c);
   bool tout = true;
   PreparerTrade();
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || !PositionSelectByTicket(tk)) continue;
      if(PositionGetInteger(POSITION_MAGIC) != magic) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(!trade.PositionClose(tk))
        {
         uint code = trade.ResultRetcode();
         if(code != TRADE_RETCODE_DONE && code != TRADE_RETCODE_DONE_PARTIAL)
           {
            tout = false;
            JournalRefus("fermeture_echouee_" + IntegerToString(code));
           }
        }
     }
   if(tout) Journal("FERME canal " + IntegerToString(c + 1) + " raison=" + raison);
   return tout;
  }

bool ToutFermerLocal(string raison)
  {
   // espacement 5 s entre les tentatives completes : la limite FTMO est
   // ~2000 requetes serveur/jour, une rafale au tick la creve en minutes
   if(TimeTradeServer() - dernierEssaiFerme < 5) return false;
   dernierEssaiFerme = TimeTradeServer();
   bool tout = true;
   for(int c = 0; c < 3; c++)
      if(!FermerCanal(c, raison)) tout = false;
   return tout;
  }

//+------------------------------------------------------------------+
//| GARDIENS                                                         |
//+------------------------------------------------------------------+
void VerifierGardiens()
  {
   MettreAJourAncre();
   HeatEcurie();                                    // rafraichit notre GV de heat
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   if(eq <= NiveauGardienTotal() && !HaltTotal())
     {
      GlobalVariableSet(GV("HALT"), 1);
      Journal("*** GARDIEN TOTAL : equite " + DoubleToString(eq, 2)
              + " <= " + DoubleToString(NiveauGardienTotal(), 2) + " -> HALT ecurie ***");
     }
   if(HaltTotal())
     {
      if(aDesPositionsLocales()) ToutFermerLocal("halt_total");
      return;
     }
   if(aDesPositionsLocales() && eq <= NiveauGardienJour())
     {
      if(ToutFermerLocal("gardien_jour"))
        {
         GelerJour();
         Journal("*** GARDIEN DU JOUR : equite " + DoubleToString(eq, 2)
                 + " <= " + DoubleToString(NiveauGardienJour(), 2) + " -> aplat + gel ***");
        }
     }
   // verrou d'objectif (R13)
   if(ObjectifPhaseP > 0)
     {
      double cible = CapitalInitialFTMO * (1.0 + ObjectifPhaseP / 100.0);
      double declenche = CapitalInitialFTMO * (1.0 + (ObjectifPhaseP + MargeObjectifP) / 100.0);
      if(eq >= declenche && !Verrouille())
        {
         GlobalVariableSet(GV("VERROU"), 1);
         Journal("*** OBJECTIF ATTEINT : equite " + DoubleToString(eq, 2) + " -> verrou ***");
        }
      if(Verrouille())
        {
         if(aDesPositionsLocales()) ToutFermerLocal("objectif");
         // les frais ont mange la marge ? on relache le verrou et on retrade
         else if(AccountInfoDouble(ACCOUNT_BALANCE) < cible)
           {
            GlobalVariableDel(GV("VERROU"));
            Journal("verrou RELACHE : solde " + DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2)
                    + " sous la cible " + DoubleToString(cible, 2));
           }
         else
            MicroTradeJourMin();
        }
     }
  }

//+------------------------------------------------------------------+
//| Micro-trade symbolique : complete les 4 jours de trading FTMO    |
//| quand l'objectif est atteint trop vite (interblocage du banc A). |
//| Seul le graphique BTC (offset 10) le fait, 1 fois par jour max.  |
//+------------------------------------------------------------------+
void MicroTradeJourMin()
  {
   if(!MicroTradesJoursMin || offsetM != 10) return;
   MqlDateTime dt;
   TimeToStruct(TimeTradeServer(), dt);
   long jour = (long)dt.year * 10000 + dt.mon * 100 + dt.day;
   string gvFait = GV("MICRO_" + IntegerToString(jour));
   string gvNb = GV("MICRO_NB");
   double nb = GlobalVariableCheck(gvNb) ? GlobalVariableGet(gvNb) : 0;
   if(GlobalVariableCheck(gvFait) || nb >= JoursMinFTMO) return;
   if(SpreadTropLarge()) return;
   if(TimeTradeServer() - dernierMicroTrade < 3600) return;
   dernierMicroTrade = TimeTradeServer();
   double volMin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   PreparerTrade();
   trade.SetExpertMagicNumber(MagicBase + 39);      // magic a part, hors des canaux
   if(trade.Buy(volMin, _Symbol, 0, 0, 0, "C1 jour min"))
     {
      ulong tk = trade.ResultOrder();
      Sleep(500);
      // fermer aussitot (cout : spread sur le volume minimal)
      for(int i = PositionsTotal() - 1; i >= 0; i--)
        {
         ulong ptk = PositionGetTicket(i);
         if(ptk == 0 || !PositionSelectByTicket(ptk)) continue;
         if(PositionGetInteger(POSITION_MAGIC) == MagicBase + 39
            && PositionGetString(POSITION_SYMBOL) == _Symbol)
            trade.PositionClose(ptk);
        }
      GlobalVariableSet(gvFait, 1);
      GlobalVariableSet(gvNb, nb + 1);
      Journal("micro-trade du jour minimum FTMO (" + DoubleToString(nb + 1, 0)
              + "/" + IntegerToString(JoursMinFTMO) + ")");
     }
  }

//+------------------------------------------------------------------+
void OnTimer()
  {
   VerifierGardiens();
   LireFichierRegime();
   LireFichierCalendrier();
   Comment("C1 ", _Symbol, " | heat ", DoubleToString(100 * HeatEcurie() / MathMax(AccountInfoDouble(ACCOUNT_EQUITY), 1), 2),
           " % | plancher jour ", DoubleToString(PlancherJour(), 0),
           " | gardien ", DoubleToString(NiveauGardienJour(), 0),
           HaltTotal() ? " | *** HALT ***" : "", Verrouille() ? " | VERROU" : "",
           JourGele() ? " | jour gele" : "");
  }

void OnTick()
  {
   VerifierGardiens();
   if(HaltTotal() || Verrouille()) return;

   datetime tBarre = iTime(_Symbol, PERIOD_H4, 0);
   if(tBarre == 0) return;
   if(tBarre == derniereBarre) { GererIntrabarre(); return; }
   // la barre n'est marquee traitee QUE si sa logique a pu s'executer
   if(GererBarreFermee())
      derniereBarre = tBarre;
  }

//+------------------------------------------------------------------+
//| Intrabarre : replis armes et pyramides (1 max par barre/canal)   |
//+------------------------------------------------------------------+
void GererIntrabarre()
  {
   double atr, ema50, ema200;
   if(!LireJournalier(atr, ema50, ema200)) return;
   if(JourGele()) return;
   bool evenement = DansFenetreEvenement();

   for(int c = 0; c < 3; c++)
     {
      double dernier, qty, moy;
      int sens;
      int unites = UnitesDuCanal(c, dernier, qty, moy, sens);

      if(unites == 0 && replSens[c] != 0 && !evenement && !SpreadTropLarge())
        {
         double px = (replSens[c] > 0) ? SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                                       : SymbolInfoDouble(_Symbol, SYMBOL_BID);
         bool touche = (replSens[c] > 0) ? (px <= replNiveau[c]) : (px >= replNiveau[c]);
         if(touche)
           {
            OuvrirUnite(c, replSens[c], atr, "repli");
            replSens[c] = 0;
            SauverRepli(c);
           }
        }
      if(unites > 0 && unites < UnitesMax && !evenement && !SpreadTropLarge()
         && dernierAjout[c] != iTime(_Symbol, PERIOD_H4, 0))
        {
         double niveau = dernier + sens * PasPyramideATR * atr;
         double px = (sens > 0) ? SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                                : SymbolInfoDouble(_Symbol, SYMBOL_BID);
         if((sens > 0 && px >= niveau) || (sens < 0 && px <= niveau))
           {
            if(OuvrirUnite(c, sens, atr, "pyramide"))
               dernierAjout[c] = iTime(_Symbol, PERIOD_H4, 0);
           }
        }
     }
  }

//+------------------------------------------------------------------+
//| Barre H4 fermee                                                  |
//+------------------------------------------------------------------+
bool GererBarreFermee()
  {
   double atr, ema50, ema200;
   if(!LireJournalier(atr, ema50, ema200)) return false;   // on retentera au prochain tick
   LireFichierRegime();
   bool evenement = DansFenetreEvenement();
   double cloture = iClose(_Symbol, PERIOD_H4, 1);
   if(cloture <= 0) return false;

   for(int c = 0; c < 3; c++)
      if(replSens[c] != 0 && --replReste[c] <= 0) { replSens[c] = 0; SauverRepli(c); }

   for(int c = 0; c < 3; c++)
     {
      double dernier, qty, moy;
      int sens;
      int unites = UnitesDuCanal(c, dernier, qty, moy, sens);

      if(unites > 0)
        {
         double borne = (sens > 0) ? PlusBas(canaux_s[c]) : PlusHaut(canaux_s[c]);
         if(borne != EMPTY_VALUE
            && ((sens > 0 && cloture < borne) || (sens < 0 && cloture > borne)))
           { FermerCanal(c, "canal"); continue; }
         if(SortieTempsJours > 0)
           {
            datetime t0 = PremiereEntreeDuCanal(c);
            if(t0 > 0 && (TimeTradeServer() - t0) >= (long)SortieTempsJours * 86400)
              {
               // profit latent NET du swap paye (parite avec le moteur)
               double latent = ProfitDuCanal(c);
               double risque0 = RisqueUniteP / 100.0 * CapitalInitialFTMO * unites;
               if(latent < SortieTempsSeuilR * risque0)
                 { FermerCanal(c, "temps"); continue; }
              }
           }
         continue;
        }

      if(JourGele() || evenement || SpreadTropLarge()) continue;
      double hh = PlusHaut(canaux_e[c]);
      double ll = PlusBas(canaux_e[c]);
      if(hh == EMPTY_VALUE || ll == EMPTY_VALUE) continue;

      bool achatOk = regimePorteAchat;
      if(!achatOk) JournalRefus("porte_macro");
      bool venteOk = VentesActives;
      if(venteOk && VenteSousEMA200Seul && cloture >= ema200) venteOk = false;

      if(achatOk && cloture > hh)
        {
         double force = (cloture - ema50) / atr;
         if(RepliKATR > 0 && force < RepliSeuilForce)
           {
            replSens[c] = 1;
            replNiveau[c] = cloture - RepliKATR * atr;
            replReste[c] = RepliBarresMax;
            SauverRepli(c);
            Journal("canal " + IntegerToString(c + 1) + " : repli ARME achat a "
                    + DoubleToString(replNiveau[c], _Digits));
           }
         else
            OuvrirUnite(c, 1, atr, "cassure");
        }
      else if(venteOk && cloture < ll)
        {
         double force = (ema50 - cloture) / atr;
         if(RepliKATR > 0 && force < RepliSeuilForce)
           {
            replSens[c] = -1;
            replNiveau[c] = cloture + RepliKATR * atr;
            replReste[c] = RepliBarresMax;
            SauverRepli(c);
            Journal("canal " + IntegerToString(c + 1) + " : repli ARME vente a "
                    + DoubleToString(replNiveau[c], _Digits));
           }
         else
            OuvrirUnite(c, -1, atr, "cassure");
        }
     }
   return true;
  }

//+------------------------------------------------------------------+
//| Ouvrir une unite + stop commun du canal (ne s'elargit jamais)    |
//+------------------------------------------------------------------+
bool OuvrirUnite(int c, int sens, double atr, string raison)
  {
   string refus = "";
   double px = (sens > 0) ? SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                          : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double vol = TailleUnite(px, atr, refus);
   if(vol <= 0)
     {
      if(refus != "") JournalRefus(refus + " (" + raison + ")");
      return false;
     }
   double stop = AjusterStop(px - sens * StopATR * atr);
   // distance minimale du courtier
   long stopsNiv = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double pt = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   if(stopsNiv > 0 && MathAbs(px - stop) < stopsNiv * pt)
      stop = AjusterStop(px - sens * stopsNiv * pt * 1.1);
   PreparerTrade();
   trade.SetExpertMagicNumber(MagicCanal(c));
   bool ok = (sens > 0) ? trade.Buy(vol, _Symbol, 0, stop, 0, "C1 c" + IntegerToString(c + 1))
                        : trade.Sell(vol, _Symbol, 0, stop, 0, "C1 c" + IntegerToString(c + 1));
   uint code = trade.ResultRetcode();
   // ne jamais juger sur le mot « failed » du journal : lire le code de retour
   if(!ok && code != TRADE_RETCODE_DONE && code != TRADE_RETCODE_PLACED)
     {
      JournalRefus("entree_code_" + IntegerToString(code));
      return false;
     }
   Journal("ENTREE " + (sens > 0 ? "achat" : "vente") + " canal " + IntegerToString(c + 1)
           + " vol " + DoubleToString(vol, 4) + " stop " + DoubleToString(stop, _Digits)
           + " raison=" + raison + " ml=" + DoubleToString(regimeML, 2));
   // stop commun : suit la derniere unite mais ne s'ELARGIT jamais
   long magic = MagicCanal(c);
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || !PositionSelectByTicket(tk)) continue;
      if(PositionGetInteger(POSITION_MAGIC) != magic) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      double slActuel = PositionGetDouble(POSITION_SL);
      double eps = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE) / 2.0;
      if(slActuel == 0 || (sens > 0 && stop > slActuel + eps) || (sens < 0 && stop < slActuel - eps))
         if(!trade.PositionModify(tk, stop, PositionGetDouble(POSITION_TP)))
            JournalRefus("modif_stop_code_" + IntegerToString(trade.ResultRetcode()));
     }
   return true;
  }
//+------------------------------------------------------------------+
