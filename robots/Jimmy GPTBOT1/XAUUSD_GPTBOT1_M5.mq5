//+------------------------------------------------------------------+
//| XAUUSD_GPTBOT1_M5.mq5                                             |
//| GENERATION GPTBOT1 — V1.1 or seulement.                           |
//|                                                                   |
//| Construit le 25 aout 2026 a la demande de Jimmy, d'apres les      |
//| recommandations de la conversation ChatGPT « Hausse des cryptos   |
//| expliquee » : survivre au challenge d'abord ; risque 0,25-0,50 %  |
//| par trade ; stop obligatoire ; AUCUNE martingale ; AUCUN grid ;   |
//| controleur FTMO SEPARE de la strategie (il peut dire NON) ;       |
//| arret quotidien AVANT la limite ; series de pertes ; filtres      |
//| spread/heures/annonces ; journalisation ; or : tendance H1 ->     |
//| impulsion -> repli 38-62 % -> confirmation M5/M15, stop           |
//| structurel ajuste ATR, objectif 1,5-2R ; viser 20-40 jours.       |
//|                                                                   |
//| V1.1 (25 aout, audit de risque maison) :                          |
//|  - l'etat du controleur (solde de minuit, gel, pause, arret       |
//|    definitif) est PERSISTE dans les variables globales du         |
//|    terminal : un redemarrage ne l'efface plus ;                   |
//|  - les fermetures d'urgence sont REESSAYEES a chaque tick tant    |
//|    qu'il reste des positions, et leurs echecs journalises ;       |
//|  - le plancher total declenche un ARRET DEFINITIF qui ne se leve  |
//|    jamais tout seul (seul Jimmy peut le lever, voir plus bas) ;   |
//|  - ChallengeInitialBalance et les fenetres d'annonces sont        |
//|    VALIDES au demarrage (refus de demarrer sinon) ;               |
//|  - plafond de lot absolu, distance de stop minimale, marge de     |
//|    glissement dans le calcul du risque ;                          |
//|  - la serie de pertes se lit sur 48 h glissantes, plus            |
//|    seulement depuis minuit.                                       |
//|                                                                   |
//| LIMITES ASSUMEES (documentees, pas des oublis) :                  |
//|  - concu pour tourner SEUL sur son compte : son gel ne ferme que  |
//|    SES positions ; d'autres robots sur le meme compte partagent   |
//|    la limite FTMO sans coordination ;                             |
//|  - le filtre d'annonces ne bloque que les ENTREES : une position  |
//|    deja ouverte traverse l'annonce avec son stop (tampon          |
//|    2,5 % -> 5 % en garde) ; fenetres a l'HEURE SERVEUR, a         |
//|    ajuster selon le fuseau reel du courtier ;                     |
//|  - le jour du robot commence a minuit SERVEUR (~1 h d'ecart avec  |
//|    le minuit CE(S)T de FTMO ; effet borne par le tampon).         |
//| Pour lever un ARRET DEFINITIF : supprimer la variable globale     |
//| GPTBOT1_<magic>_arret_definitif dans MT5 (F3), en connaissance    |
//| de cause. RIEN N'EST DEPLOYE ; validation = testeur MT5 + demo.   |
//+------------------------------------------------------------------+
#property copyright "Jimmy - generation GPTBOT1"
#property version   "1.10"
#property strict

#include <Trade\Trade.mqh>

//--- identite ------------------------------------------------------
input long   MagicNumber            = 20267001; // bloc GPTBOT1 : 20267001+
input string NomRobot               = "GPTBOT1 Or";

//--- risque (recommandations ChatGPT) ------------------------------
input double RisqueParTradePct      = 0.50;   // 0,25-0,50 % recommande
input double RatioTP                = 1.75;   // objectif 1,5R a 2R
input double MaxLotAbsolu           = 3.0;    // plafond dur, peu importe le stop
input double MargeGlissementPct     = 20.0;   // reserve pour glissement/commission
input int    MaxTradesSimultanes    = 2;      // 2-3 max, tous robots confondus
input int    SerieDePertesMax       = 3;      // pause apres N pertes de suite (48 h glissantes)
input int    PauseApresSerieHeures  = 24;

//--- controleur FTMO (SEPARE de la strategie) ----------------------
input double ArretQuotidienPct      = 2.50;   // gel du jour AVANT la limite de 5 %
input double PlancherTotalPct       = 9.00;   // arret DEFINITIF avant le -10 % FTMO
input double ChallengeInitialBalance= 200000.0;
input double ToleranceBalancePct    = 15.0;   // ecart max input/compte reel au demarrage

//--- filtres -------------------------------------------------------
input double SpreadMaxPrix          = 0.35;   // en $ sur l'or ; au-dela : pas d'entree
input int    HeureDebut             = 8;      // heure serveur
input int    HeureFin               = 21;
input bool   GardeVendredi          = true;   // pas d'entree vendredi apres 18 h
input bool   FermerVendrediSoir     = true;   // tout fermer avant le week-end
// Fenetres d'annonces, HEURE SERVEUR. Defauts pour un serveur GMT+2/+3 cale
// sur l'heure d'ete americaine (FTMO) : 15:30 serveur = 8 h 30 New York
// (NFP, IPC...) ; 21:00 serveur = 14 h FOMC. A ajuster si le fuseau differe.
input string FenetresBloquees       = "15:25-15:50;20:45-21:20";

//--- strategie or : tendance + repli + confirmation ----------------
input int    EmaTendanceH1          = 50;     // direction H1
input int    EmaConfirmationM5      = 20;     // retour du momentum M5
input int    PeriodeATR             = 14;
input double ImpulsionMinATR        = 1.5;    // impulsion H1 >= k x ATR(H1)
input int    FenetreImpulsionH1     = 12;     // barres H1 pour chercher l'impulsion
input double RepliMinPct            = 38.0;   // zone de repli : 38-62 % de l'impulsion
input double RepliMaxPct            = 62.0;
input double MargeStopATR           = 0.25;   // stop = structure - k x ATR(H1)
input double DistanceStopMinATR     = 0.50;   // distance minimale du stop (anti-lot geant)

//--- divers --------------------------------------------------------
input bool   PushNotifications      = true;
input bool   JournalActif           = true;

CTrade trade;
int    hEmaH1 = INVALID_HANDLE, hEmaM5 = INVALID_HANDLE;
int    hAtrH1 = INVALID_HANDLE;
datetime derniereBarreM5 = 0;
datetime jourCourant     = 0;
double soldeMinuit       = 0.0;
bool   jourGele          = false;
bool   arretDefinitif    = false;
datetime finPauseSerie   = 0;
bool   notifGelEnvoyee   = false;
int    fenetresMin[20][2];
int    nbFenetres        = 0;

//+------------------------------------------------------------------+
//| Persistance : l'etat du controleur survit aux redemarrages.       |
//| Variables globales du terminal (conservees 4 semaines sur disque).|
//+------------------------------------------------------------------+
string GV(const string suffixe) { return("GPTBOT1_" + (string)MagicNumber + "_" + suffixe); }

void SauverEtat()
  {
   GlobalVariableSet(GV("jour"), (double)(long)jourCourant);
   GlobalVariableSet(GV("solde_minuit"), soldeMinuit);
   GlobalVariableSet(GV("jour_gele"), jourGele ? 1.0 : 0.0);
   GlobalVariableSet(GV("fin_pause"), (double)(long)finPauseSerie);
   GlobalVariableSet(GV("arret_definitif"), arretDefinitif ? 1.0 : 0.0);
  }

void RestaurerEtat()
  {
   // L'arret definitif et la pause se restaurent TOUJOURS (ils ne dependent
   // pas du jour). Le solde de minuit ne se restaure que si on est encore
   // le meme jour : sinon c'est un vrai nouveau jour, on repart du solde.
   if(GlobalVariableCheck(GV("arret_definitif")))
      arretDefinitif = (GlobalVariableGet(GV("arret_definitif")) > 0.5);
   if(GlobalVariableCheck(GV("fin_pause")))
      finPauseSerie = (datetime)(long)GlobalVariableGet(GV("fin_pause"));
   if(GlobalVariableCheck(GV("jour")) && GlobalVariableCheck(GV("solde_minuit")))
     {
      datetime jourSauve = (datetime)(long)GlobalVariableGet(GV("jour"));
      if(jourSauve == DebutDuJour(TimeCurrent()))
        {
         jourCourant = jourSauve;
         soldeMinuit = GlobalVariableGet(GV("solde_minuit"));
         if(GlobalVariableCheck(GV("jour_gele")))
            jourGele = (GlobalVariableGet(GV("jour_gele")) > 0.5);
         Journaliser("etat restaure | solde_minuit=" + DoubleToString(soldeMinuit, 2)
                     + " gel=" + (jourGele ? "OUI" : "non")
                     + " arret_definitif=" + (arretDefinitif ? "OUI" : "non"));
         return;
        }
     }
   jourCourant = DebutDuJour(TimeCurrent());
   soldeMinuit = AccountInfoDouble(ACCOUNT_BALANCE);
   SauverEtat();
  }

//+------------------------------------------------------------------+
//| Journal : une ligne par decision, style Ecurie_Journal            |
//+------------------------------------------------------------------+
void Journaliser(const string texte)
  {
   if(!JournalActif) return;
   string ligne = TimeToString(TimeCurrent(), TIME_DATE|TIME_MINUTES)
                  + " | " + NomRobot + " | " + texte;
   Print(ligne);
   int f = FileOpen("Ecurie_Journal\\GPTBOT1_XAUUSD.txt",
                    FILE_READ|FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_SHARE_READ);
   if(f != INVALID_HANDLE)
     {
      FileSeek(f, 0, SEEK_END);
      FileWriteString(f, ligne + "\r\n");
      FileClose(f);
     }
  }

void Notifier(const string texte)
  {
   // Regle de Jimmy : toute notification dit QUI l'envoie et CE QU'IL FAIT.
   if(PushNotifications) SendNotification(NomRobot + " : " + texte);
   Journaliser("notification | " + texte);
  }

//+------------------------------------------------------------------+
//| Outils temps                                                      |
//+------------------------------------------------------------------+
datetime DebutDuJour(datetime t)
  {
   MqlDateTime s;
   TimeToStruct(t, s);
   s.hour = 0; s.min = 0; s.sec = 0;
   return(StructToTime(s));
  }

bool AnalyserFenetres()
  {
   // "HH:MM-HH:MM;HH:MM-HH:MM" -> tableau de minutes. Un format invalide
   // rendrait le filtre silencieusement mort : on refuse de demarrer.
   nbFenetres = 0;
   string brut = FenetresBloquees;
   StringTrimLeft(brut); StringTrimRight(brut);
   if(brut == "") return(true);          // filtre volontairement vide : permis
   string parts[];
   int n = StringSplit(brut, ';', parts);
   for(int i = 0; i < n && nbFenetres < 20; i++)
     {
      string bornes[], hd[], hf[];
      if(StringSplit(parts[i], '-', bornes) != 2) return(false);
      if(StringSplit(bornes[0], ':', hd) != 2) return(false);
      if(StringSplit(bornes[1], ':', hf) != 2) return(false);
      int debut = (int)StringToInteger(hd[0]) * 60 + (int)StringToInteger(hd[1]);
      int fin   = (int)StringToInteger(hf[0]) * 60 + (int)StringToInteger(hf[1]);
      if(debut < 0 || fin > 1439 || debut >= fin) return(false);
      fenetresMin[nbFenetres][0] = debut;
      fenetresMin[nbFenetres][1] = fin;
      nbFenetres++;
     }
   return(nbFenetres > 0);
  }

bool DansFenetreBloquee()
  {
   MqlDateTime s;
   TimeToStruct(TimeCurrent(), s);
   int minuteJour = s.hour * 60 + s.min;
   for(int i = 0; i < nbFenetres; i++)
      if(minuteJour >= fenetresMin[i][0] && minuteJour <= fenetresMin[i][1])
         return(true);
   return(false);
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   trade.SetExpertMagicNumber(MagicNumber);

   // Validation du capital de reference : un input laisse a 200 000 sur un
   // compte 100 000 rendrait le plancher absurde (trop haut ou trop bas).
   double solde = AccountInfoDouble(ACCOUNT_BALANCE);
   if(solde > 0.0 && MathAbs(solde - ChallengeInitialBalance) / ChallengeInitialBalance * 100.0 > ToleranceBalancePct)
     {
      Print(NomRobot, " REFUSE DE DEMARRER : ChallengeInitialBalance=",
            DoubleToString(ChallengeInitialBalance, 0), " mais solde reel=",
            DoubleToString(solde, 0), " (ecart > ", DoubleToString(ToleranceBalancePct, 0),
            " %). Corrige l'input.");
      return(INIT_FAILED);
     }

   if(!AnalyserFenetres())
     {
      Print(NomRobot, " REFUSE DE DEMARRER : FenetresBloquees illisible (« ",
            FenetresBloquees, " »). Format attendu : HH:MM-HH:MM;HH:MM-HH:MM");
      return(INIT_FAILED);
     }

   hEmaH1 = iMA(_Symbol, PERIOD_H1, EmaTendanceH1, 0, MODE_EMA, PRICE_CLOSE);
   hEmaM5 = iMA(_Symbol, PERIOD_M5, EmaConfirmationM5, 0, MODE_EMA, PRICE_CLOSE);
   hAtrH1 = iATR(_Symbol, PERIOD_H1, PeriodeATR);
   if(hEmaH1 == INVALID_HANDLE || hEmaM5 == INVALID_HANDLE || hAtrH1 == INVALID_HANDLE)
     {
      Print(NomRobot, " : echec de creation des indicateurs");
      return(INIT_FAILED);
     }

   RestaurerEtat();

   Print(NomRobot, " charge | tendance H1 EMA", EmaTendanceH1,
         " -> repli 38-62 % -> confirmation M5 EMA", EmaConfirmationM5,
         " | risque ", DoubleToString(RisqueParTradePct, 2),
         " % | TP ", DoubleToString(RatioTP, 2), "R | magic ", (string)MagicNumber);
   Print(NomRobot, " controleur FTMO | arret jour ", DoubleToString(ArretQuotidienPct, 2),
         " % | plancher total ", DoubleToString(PlancherTotalPct, 2),
         " % (DEFINITIF) | serie max ", (string)SerieDePertesMax,
         " | lot max ", DoubleToString(MaxLotAbsolu, 2));
   if(arretDefinitif)
      Notifier("ATTENTION : arret definitif toujours actif au demarrage — je ne traderai pas");
   Journaliser("charge V1.1 | risque=" + DoubleToString(RisqueParTradePct, 2)
               + "% TP=" + DoubleToString(RatioTP, 2) + "R magic=" + (string)MagicNumber);
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int raison)
  {
   SauverEtat();
   Journaliser("arrete | raison=" + (string)raison);
  }

//+------------------------------------------------------------------+
//| CONTROLEUR FTMO — separe de la strategie. Il peut dire NON.       |
//+------------------------------------------------------------------+
void MettreAJourJour()
  {
   datetime debut = DebutDuJour(TimeCurrent());
   if(debut != jourCourant)
     {
      jourCourant = debut;
      soldeMinuit = AccountInfoDouble(ACCOUNT_BALANCE);
      if(jourGele) Journaliser("nouveau jour | gel quotidien leve");
      jourGele = false;
      notifGelEnvoyee = false;
      SauverEtat();
     }
  }

int NosPositions()
  {
   int n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) == MagicNumber) n++;
     }
   return(n);
  }

int PertesConsecutives()
  {
   // 48 h glissantes : une serie a cheval sur minuit reste une serie.
   int pertes = 0;
   if(!HistorySelect(TimeCurrent() - 48 * 3600, TimeCurrent())) return(0);
   int total = HistoryDealsTotal();
   for(int i = total - 1; i >= 0; i--)
     {
      ulong ticket = HistoryDealGetTicket(i);
      if(HistoryDealGetInteger(ticket, DEAL_MAGIC) != MagicNumber) continue;
      if(HistoryDealGetInteger(ticket, DEAL_ENTRY) != DEAL_ENTRY_OUT) continue;
      double profit = HistoryDealGetDouble(ticket, DEAL_PROFIT)
                    + HistoryDealGetDouble(ticket, DEAL_SWAP)
                    + HistoryDealGetDouble(ticket, DEAL_COMMISSION);
      if(profit < 0.0) pertes++;
      else break;                       // la serie s'arrete au premier gain
     }
   return(pertes);
  }

// Fermeture de toutes NOS positions. Renvoie true si tout est ferme.
// Les echecs sont journalises : ils arrivent precisement dans les tempetes
// (requotes, off-quotes) — l'appelant DOIT reessayer tant que ca echoue.
bool FermerToutesNosPositions(const string raison)
  {
   bool tout_ferme = true;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) != MagicNumber) continue;
      if(!trade.PositionClose(ticket))
        {
         tout_ferme = false;
         Journaliser("ECHEC de fermeture #" + (string)ticket
                     + " retcode=" + (string)trade.ResultRetcode()
                     + " | " + raison + " | je reessaie au prochain tick");
        }
     }
   return(tout_ferme);
  }

// Verdict du controleur : true = la strategie a le droit d'AGIR (entrer).
// La SURVEILLANCE (gel, plancher, reessais de fermeture) est faite ici,
// a CHAQUE passage, meme quand le verdict est deja non.
bool ControleurFTMO_Permission()
  {
   MettreAJourJour();
   double equite = AccountInfoDouble(ACCOUNT_EQUITY);

   // 1. plancher total : ARRET DEFINITIF. Ne se leve jamais tout seul.
   if(!arretDefinitif
      && equite <= ChallengeInitialBalance * (1.0 - PlancherTotalPct / 100.0))
     {
      arretDefinitif = true;
      SauverEtat();
      Notifier("ARRET DEFINITIF | plancher total " + DoubleToString(PlancherTotalPct, 1)
               + " % touche. Je ne traderai plus. Intervention de Jimmy requise "
               + "(variable globale " + GV("arret_definitif") + ").");
     }
   if(arretDefinitif)
     {
      if(NosPositions() > 0) FermerToutesNosPositions("arret definitif");
      return(false);
     }

   // 2. arret quotidien AVANT la limite FTMO de 5 %.
   if(!jourGele && equite <= soldeMinuit * (1.0 - ArretQuotidienPct / 100.0))
     {
      jourGele = true;
      SauverEtat();
     }
   if(jourGele)
     {
      // Reessai de fermeture a CHAQUE tick tant qu'il reste des positions.
      if(NosPositions() > 0)
        {
         bool ok = FermerToutesNosPositions("arret quotidien "
                     + DoubleToString(ArretQuotidienPct, 1) + " % atteint");
         if(ok && !notifGelEnvoyee)
           {
            notifGelEnvoyee = true;
            Notifier("journee gelee | perte du jour "
                     + DoubleToString(ArretQuotidienPct, 1) + " % atteinte, tout est ferme");
           }
        }
      else if(!notifGelEnvoyee)
        {
         notifGelEnvoyee = true;
         Notifier("journee gelee | perte du jour "
                  + DoubleToString(ArretQuotidienPct, 1) + " % atteinte");
        }
      return(false);
     }

   // 3. protection contre les series de pertes (48 h glissantes, persistee).
   if(TimeCurrent() < finPauseSerie) return(false);
   if(PertesConsecutives() >= SerieDePertesMax)
     {
      finPauseSerie = TimeCurrent() + PauseApresSerieHeures * 3600;
      SauverEtat();
      Notifier("pause de " + (string)PauseApresSerieHeures + " h | "
               + (string)SerieDePertesMax + " pertes consecutives");
      return(false);
     }

   // 4. plafond de positions simultanees (tous les robots du compte).
   if(PositionsTotal() >= MaxTradesSimultanes) return(false);

   // 5. deja une position a nous : V1 = une seule a la fois.
   if(NosPositions() > 0) return(false);
   return(true);
  }

//+------------------------------------------------------------------+
//| Filtres d'entree (spread, heures, annonces)                       |
//+------------------------------------------------------------------+
bool FiltresPassent(string &refus)
  {
   MqlDateTime s;
   TimeToStruct(TimeCurrent(), s);
   if(s.hour < HeureDebut || s.hour >= HeureFin) { refus = "hors des heures de trading"; return(false); }
   if(GardeVendredi && s.day_of_week == 5 && s.hour >= 18) { refus = "vendredi soir"; return(false); }
   double spread = SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(spread > SpreadMaxPrix) { refus = "spread trop eleve (" + DoubleToString(spread, 2) + " $)"; return(false); }
   if(DansFenetreBloquee()) { refus = "fenetre d'annonces"; return(false); }
   refus = "";
   return(true);
  }

//+------------------------------------------------------------------+
//| Strategie or : tendance H1 -> impulsion -> repli -> confirmation  |
//| Renvoie +1 (achat), -1 (vente), 0 (rien), et remplit stopPropose. |
//+------------------------------------------------------------------+
int SignalOr(double &stopPropose)
  {
   double emaH1[], atrH1[], emaM5[];
   // CopyBuffer avec debut=1 : emaH1[0] = barre 1 (la plus RECENTE fermee),
   // emaH1[2] = barre 3 (plus ancienne). Idem emaM5 : [0] recent, [1] ancien.
   if(CopyBuffer(hEmaH1, 0, 1, 3, emaH1) < 3) return(0);
   if(CopyBuffer(hAtrH1, 0, 1, 1, atrH1) < 1) return(0);
   if(CopyBuffer(hEmaM5, 0, 1, 2, emaM5) < 2) return(0);
   ArraySetAsSeries(emaH1, true);   // -> [0] = la plus recente, sans ambiguite
   ArraySetAsSeries(emaM5, true);
   double atr = atrH1[0];
   if(atr <= 0.0) return(0);

   // Barres H1 fermees recentes, [0] = la plus recente.
   MqlRates h1[];
   if(CopyRates(_Symbol, PERIOD_H1, 1, FenetreImpulsionH1 + 2, h1) < FenetreImpulsionH1) return(0);
   ArraySetAsSeries(h1, true);
   double cloture = h1[0].close;

   // 1. TENDANCE H1 : prix du bon cote de l'EMA, et EMA qui monte/descend.
   //    emaH1[0] = EMA recente ; emaH1[2] = EMA d'il y a 2 barres.
   int sens = 0;
   if(cloture > emaH1[0] && emaH1[0] > emaH1[2]) sens = +1;
   if(cloture < emaH1[0] && emaH1[0] < emaH1[2]) sens = -1;
   if(sens == 0) return(0);

   // 2. IMPULSION recente dans le sens de la tendance : amplitude >= k x ATR.
   int iHaut = 0, iBas = 0;
   for(int i = 1; i < FenetreImpulsionH1; i++)
     {
      if(h1[i].high > h1[iHaut].high) iHaut = i;
      if(h1[i].low  < h1[iBas].low)  iBas  = i;
     }
   double haut = h1[iHaut].high, bas = h1[iBas].low;
   double amplitude = haut - bas;
   if(amplitude < ImpulsionMinATR * atr) return(0);
   // En series ([0] = recent), une MONTEE = le bas est PLUS ANCIEN que le
   // haut, donc iBas > iHaut. L'inverse pour une descente.
   if(sens > 0 && iBas <= iHaut) return(0);
   if(sens < 0 && iHaut <= iBas) return(0);

   // 3. REPLI : le prix actuel est revenu dans la zone 38-62 % de l'impulsion.
   double prix = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double repli;
   if(sens > 0) repli = (haut - prix) / amplitude * 100.0;
   else         repli = (prix - bas) / amplitude * 100.0;
   if(repli < RepliMinPct || repli > RepliMaxPct) return(0);

   // 4. CONFIRMATION : retour du momentum sur M5 (cloture repasse du bon
   //    cote de l'EMA M5) et la derniere M15 fermee va dans le sens.
   //    emaM5[0] = EMA de la barre 1 (recente) ; emaM5[1] = barre 2.
   double m5c1 = iClose(_Symbol, PERIOD_M5, 1);
   double m5c2 = iClose(_Symbol, PERIOD_M5, 2);
   double m15o = iOpen(_Symbol, PERIOD_M15, 1);
   double m15c = iClose(_Symbol, PERIOD_M15, 1);
   if(sens > 0)
     {
      if(!(m5c2 <= emaM5[1] && m5c1 > emaM5[0])) return(0);
      if(m15c <= m15o) return(0);
      stopPropose = bas;
      double basRepli = iLow(_Symbol, PERIOD_M15, iLowest(_Symbol, PERIOD_M15, MODE_LOW, 8, 1));
      if(basRepli > bas && basRepli < prix) stopPropose = basRepli;
      stopPropose -= MargeStopATR * atr;
      // Distance minimale : un stop trop proche fabrique un lot geant.
      double d = SymbolInfoDouble(_Symbol, SYMBOL_ASK) - stopPropose;
      if(d < DistanceStopMinATR * atr)
         stopPropose = SymbolInfoDouble(_Symbol, SYMBOL_ASK) - DistanceStopMinATR * atr;
     }
   else
     {
      if(!(m5c2 >= emaM5[1] && m5c1 < emaM5[0])) return(0);
      if(m15c >= m15o) return(0);
      stopPropose = haut;
      double hautRepli = iHigh(_Symbol, PERIOD_M15, iHighest(_Symbol, PERIOD_M15, MODE_HIGH, 8, 1));
      if(hautRepli < haut && hautRepli > prix) stopPropose = hautRepli;
      stopPropose += MargeStopATR * atr;
      double d = stopPropose - SymbolInfoDouble(_Symbol, SYMBOL_BID);
      if(d < DistanceStopMinATR * atr)
         stopPropose = SymbolInfoDouble(_Symbol, SYMBOL_BID) + DistanceStopMinATR * atr;
     }
   return(sens);
  }

//+------------------------------------------------------------------+
//| Taille : risque fixe en % de l'equite. AUCUNE martingale.         |
//| La marge de glissement reduit le risque vise ; plafond de lot dur.|
//+------------------------------------------------------------------+
double CalculerLot(double prixEntree, double stop)
  {
   double distance = MathAbs(prixEntree - stop);
   if(distance <= 0.0) return(0.0);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   if(tickSize <= 0.0 || tickValue <= 0.0) return(0.0);
   double risqueArgent = AccountInfoDouble(ACCOUNT_EQUITY) * RisqueParTradePct / 100.0;
   risqueArgent /= (1.0 + MargeGlissementPct / 100.0);   // reserve glissement
   double perteParLot  = distance / tickSize * tickValue;
   if(perteParLot <= 0.0) return(0.0);
   double lot = risqueArgent / perteParLot;
   double pas = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double mini = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxi = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   if(pas <= 0.0) return(0.0);
   lot = MathFloor(lot / pas) * pas;
   if(lot < mini) return(0.0);          // trop petit pour respecter le risque : on refuse
   if(lot > MaxLotAbsolu) lot = MathFloor(MaxLotAbsolu / pas) * pas;
   if(lot > maxi) lot = maxi;
   return(NormalizeDouble(lot, 2));
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   // Surveillance continue du controleur (gel, plancher, reessais de
   // fermeture) meme sans signal et meme entre les barres M5.
   bool permission = ControleurFTMO_Permission();

   // Fermeture de fin de semaine, reessayee a chaque tick apres 21 h.
   if(FermerVendrediSoir)
     {
      MqlDateTime s;
      TimeToStruct(TimeCurrent(), s);
      if(s.day_of_week == 5 && s.hour >= 21 && NosPositions() > 0)
         if(FermerToutesNosPositions("fermeture avant le week-end"))
            Notifier("fermeture avant le week-end");
     }

   // Decisions UNE fois par barre M5.
   datetime barre = iTime(_Symbol, PERIOD_M5, 0);
   if(barre == derniereBarreM5) return;
   derniereBarreM5 = barre;

   if(!permission) return;

   string refus;
   if(!FiltresPassent(refus))
     {
      if(refus != "") Journaliser("refus | " + refus);
      return;
     }

   double stop = 0.0;
   int sens = SignalOr(stop);
   if(sens == 0) return;

   double prix = (sens > 0) ? SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                            : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double distance = MathAbs(prix - stop);
   if(distance <= 0.0) return;
   double tp = (sens > 0) ? prix + RatioTP * distance : prix - RatioTP * distance;

   double lot = CalculerLot(prix, stop);
   if(lot <= 0.0)
     {
      Journaliser("refus | lot minimal depasserait le risque de "
                  + DoubleToString(RisqueParTradePct, 2) + " %");
      return;
     }

   bool ok;
   if(sens > 0) ok = trade.Buy(lot, _Symbol, 0.0, stop, tp, NomRobot);
   else         ok = trade.Sell(lot, _Symbol, 0.0, stop, tp, NomRobot);
   if(ok)
      Notifier((sens > 0 ? "ACHAT" : "VENTE") + " or " + DoubleToString(lot, 2)
               + " lot | stop " + DoubleToString(stop, 2)
               + " | objectif " + DoubleToString(tp, 2)
               + " | risque " + DoubleToString(RisqueParTradePct, 2) + " %");
   else
      Journaliser("echec d'ordre | retcode=" + (string)trade.ResultRetcode());
  }
//+------------------------------------------------------------------+
