# -*- coding: utf-8 -*-
"""Fabrique les deux robots GrokBot1 a partir du chassis L13 (cassures).

GrokBot1 n'est pas ecrit a la main : il est DERIVE de Jimmy L13 par ce script,
pour que chaque correctif futur du chassis se reporte d'une commande et qu'on
puisse toujours diff-er GrokBot1 contre son parent. Meme esprit que build_L3.py
et build_generations_plus.py.

Ce qui est greffe (voir RAPPORT_GROKBOT1.md pour les chiffres du banc) :
  1. coupe-temps conditionnel 12 j / 1,00 ATR   -- ACTIF, valide au banc
  2. reengagement apres sortie gagnante (Grok)  -- present, DESACTIVE (neutre)
  3. affichage graphique                        -- ACTIF

Lancer :  python3 build_grokbot1.py
"""
import os, io, sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CIBLE  = os.path.join(RACINE, "robots", "GrokBot1")

SOURCES = [
    ("robots/Jimmy L13/BTCUSD_Cassure_L13_H1.mq5",
     "GrokBot1_Cassure_BTCUSD_H1.mq5", "BTCUSD", "20261132"),
    ("robots/Jimmy L13/USOIL_Petrole_L13_H4.mq5",
     "GrokBot1_Cassure_USOIL_H4.mq5", "USOIL", "20261133"),
]

# ------------------------------------------------------------------ 1. entete
ENTETE = '''//+------------------------------------------------------------------+
//|                                       %(fichier)s |
//|  GROKBOT1 -- la generation nee du comite IA externe (Grok).      |
//|                                                                  |
//|  Chassis : Jimmy L13 (cassure Donchian 20/10 JOURS, achat seul,  |
//|  pyramide Turtle 4 unites, repli conditionnel L12, gardien       |
//|  quotidien -2,50 %%, fermeture a l'objectif R13). Rien du chassis |
//|  n'a ete change : GrokBot1 AJOUTE trois choses.                  |
//|                                                                  |
//|  1. COUPE-TEMPS CONDITIONNEL  (actif -- VALIDE au banc)          |
//|     Point 6 du plan de banc du comite du 21 aout, propose par    |
//|     les trois IA. Si apres CoupeTempsJours jours le meilleur     |
//|     profit atteint n'a jamais depasse CoupeTempsSeuilATR x ATR   |
//|     journalier d'entree, la position est fermee. Ce n'est pas    |
//|     l'age qui coupe, c'est l'ABSENCE DE PROGRES : le capital     |
//|     immobilise repart ailleurs.                                  |
//|     Banc (backtests/banc_grokbot1.py, portefeuille sous plafond  |
//|     de 2, frais reels, 10 ans de barres journalieres) :          |
//|        10 ans   CAGR +8,63 %% (ref +7,67) | duree 573 j (600)     |
//|                 reussite 96,9 %% (95,3)   | give-back 42,1 (43,7) |
//|        2016-21  CAGR +11,00 %% (ref +8,89)| duree 517 j (687)     |
//|        2021-26  CAGR +6,89 %% (ref +6,82) | duree 557 j (557)     |
//|     Les 4 standards du README sont passes. DEUX RESERVES        |
//|     HONNETES : (a) le mecanisme ne s'est declenche que 6 fois    |
//|     en 10 ans -- petit echantillon, comme le pyramidage a son    |
//|     epoque ; (b) le creux maximal sur 10 ans se CREUSE, de       |
//|     -10,7 %% a -12,2 %%. Il s'agit du creux de la serie complete, |
//|     pas d'un creux intra-challenge : la reussite FTMO, elle,     |
//|     MONTE (95,3 -> 96,9 %%). A surveiller quand meme sur compte  |
//|     finance, ou le creux total compte pour de vrai.              |
//|                                                                  |
//|  2. REENGAGEMENT APRES SORTIE GAGNANTE  (present, DESACTIVE)     |
//|     Point 4 du plan, propose par Grok (no 5). Apres une sortie   |
//|     en profit, rentrer de nouveau quand le prix depasse le       |
//|     sommet du trade + K x ATR. Le banc le mesure NEUTRE :        |
//|     +0,04 pt de CAGR, -3 jours, et K = 0,25 / 0,50 / 1,00 / 1,50 |
//|     donnent tous le meme resultat -- signature d'un mecanisme    |
//|     inerte. Il est arme 32 fois en 10 ans mais la cassure 20 j   |
//|     tirait deja le meme jour 17 fois sur 19. Laisse dans le code |
//|     et desactive : a rouvrir si un jour on teste un chassis dont |
//|     l'entree n'est PAS un plus-haut de canal.                    |
//|                                                                  |
//|  3. AFFICHAGE GRAPHIQUE  (actif)                                 |
//|     Un panneau sur le graphique : etat du gardien, avancement    |
//|     de la phase, position et unites, canaux, compte a rebours du |
//|     coupe-temps, filtres macro/annonces/volatilite. Plus les     |
//|     lignes du canal et du stop directement sur les prix.         |
//|                                                                  |
//|  CE QUI A ETE REJETE AU MEME BANC (ne pas reessayer) :           |
//|   - canal de sortie 7 j ou 5 j, seul ou "repare" par le          |
//|     reengagement : CAGR +4,9 / +5,4 contre +7,7 en reference,    |
//|     duree 896 j / 818 j contre 600 j. L'hypothese de Gemini      |
//|     (le reengagement repare le canal rapide) est INFIRMEE.       |
//|   - coupe-temps 8 j / 0,75 ATR, 8 j / 1,50, 12 j / 2,00 :        |
//|     nettement gagnants sur 10 ans (+8,1 a +8,9 %%) et sur la 1re  |
//|     moitie (+10,9 a +11,9 %%), mais perdants de 0,1 a 0,3 pt sur  |
//|     la 2e -- ils echouent au standard 3. Le 20 j / 3,00 ATR fait |
//|     en plus baisser la reussite (94,7 contre 95,3 %%).            |
//|     Le reglage du comite (12 j / 1,00 ATR) est le seul a passer  |
//|     les deux moities. Il est au BORD du plateau, pas au centre : |
//|     le SIGNE du mecanisme est robuste (5 voisins sur 5 gagnent   |
//|     sur 10 ans), son REGLAGE ne l'est pas.                       |
//|                                                                  |
//|  Partage les protections FTMO (variables MACROBOT_*), le biais   |
//|  macro BIS et le filtre d'annonces avec les autres robots.       |
//|  Magic distinct : ne touche jamais aux trades des autres.        |
//+------------------------------------------------------------------+
'''

# ------------------------------------------------------------------ 2. inputs
INPUTS = '''input bool   CoupeTempsActif      = true;   // GrokBot1 : fermer une position qui ne progresse pas (point 6 du comite, VALIDE au banc)
input int    CoupeTempsJours      = 12;     // GrokBot1 : jours (barres D1) avant de juger l'absence de progres -- 12 est le reglage du comite ET le seul a passer les deux moities
input double CoupeTempsSeuilATR   = 1.00;   // GrokBot1 : meilleur profit minimal exige, en ATR journalier d'ENTREE ; en dessous, on ferme
input bool   CoupeTempsIgnoreSiPyramide = true; // GrokBot1 : ne jamais couper un trade qui a deja ajoute une unite (le banc journalier ne pyramide pas : interaction NON testee, on reste prudent)
input bool   ReengagementActif    = false;  // GrokBot1 : DESACTIVE - mesure neutre au banc (+0,04 pt de CAGR, -3 j) et insensible a K : la cassure 20 j tire deja avant lui
input double ReengagementATR      = 0.50;   // GrokBot1 : depassement du sommet precedent exige, en ATR journalier (valeur Grok)
input int    ReengagementJours    = 0;      // GrokBot1 : validite de l'armement en jours (0 = illimite)
input bool   AffichageActif       = true;   // GrokBot1 : panneau d'etat sur le graphique
input ENUM_BASE_CORNER AffichageCoin = CORNER_LEFT_UPPER; // GrokBot1 : coin d'ancrage du panneau
input int    AffichageTaille      = 9;      // GrokBot1 : taille du texte du panneau
input color  AffichageFond        = C'20,24,32';  // GrokBot1 : fond du panneau
input color  AffichageTexte       = clrGainsboro; // GrokBot1 : couleur du texte
input bool   AffichageLignes      = true;   // GrokBot1 : tracer canal haut / canal bas / stop sur les prix
'''

# ------------------------------------------------------------------ 3. globaux
GLOBAUX = '''
// ---------------- GrokBot1 : etat des mecanismes du comite ----------------
double   reengSommet   = 0.0;      // sommet du dernier trade GAGNANT (0 = desarme)
datetime reengQuand    = 0;        // moment de l'armement, pour la fenetre de validite
double   sortieProfitCumul = 0.0;  // profit accumule des sorties du trade en cours de fermeture
int      coupeTempsFaits = 0;      // compteur de sessions, pour le panneau
string   PANNEAU = "GROKBOT1_";    // prefixe de TOUS les objets graphiques

string AtrEntreeGV()
  {
   return("GROKBOT1_ATR0_" + (string)NumeroMagique + "_" + _Symbol);
  }

string SommetGV()
  {
   return("GROKBOT1_SOMMET_" + (string)NumeroMagique + "_" + _Symbol);
  }
'''

# ------------------------------------------------------------------ 4. fonctions
FONCTIONS = r'''
//+------------------------------------------------------------------+
//| GROKBOT1 -- suivi du trade : premiere unite, ATR d'entree, MFE.  |
//| Tout est relu depuis les positions et les barres D1, jamais      |
//| garde en memoire vive seule : le robot survit a un redemarrage   |
//| de MT5 en pleine position (regle du chassis).                    |
//+------------------------------------------------------------------+
double PrixPremiereUnite()
  {
   double p = 0.0;
   datetime t = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != NumeroMagique) continue;
      datetime to = (datetime)PositionGetInteger(POSITION_TIME);
      if(t == 0 || to < t) { t = to; p = PositionGetDouble(POSITION_PRICE_OPEN); }
     }
   return(p);
  }

datetime TempsPremiereUnite()
  {
   datetime t = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != NumeroMagique) continue;
      datetime to = (datetime)PositionGetInteger(POSITION_TIME);
      if(t == 0 || to < t) t = to;
     }
   return(t);
  }

//| L'ATR du jour d'ENTREE, comme au banc (et non l'ATR courant).    |
//| Memorise en variable globale du terminal pour survivre a un      |
//| redemarrage ; a defaut on retombe sur l'ATR courant.             |
void MemoriserAtrEntree()
  {
   double a = ValeurAtrJour();
   if(a > 0) GlobalVariableSet(AtrEntreeGV(), a);
  }

void OublierAtrEntree()
  {
   if(GlobalVariableCheck(AtrEntreeGV())) GlobalVariableDel(AtrEntreeGV());
   if(GlobalVariableCheck(SommetGV()))    GlobalVariableDel(SommetGV());
  }

//| Le sommet atteint depuis l'entree, tenu a jour tant que la       |
//| position vit. Grok ancre son reengagement dessus : il faut donc  |
//| le connaitre APRES la fermeture, quand la position n'existe      |
//| plus -- d'ou la variable globale du terminal.                    |
void MajSommetTrade()
  {
   int i0 = JoursDepuisEntree();
   if(i0 < 0) return;
   double h = 0.0;
   int idx = iHighest(_Symbol, PERIOD_D1, MODE_HIGH, i0 + 1, 0);
   if(idx >= 0) h = iHigh(_Symbol, PERIOD_D1, idx);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(bid > h) h = bid;
   if(h <= 0) return;
   double connu = GlobalVariableCheck(SommetGV()) ? GlobalVariableGet(SommetGV()) : 0.0;
   if(h > connu) GlobalVariableSet(SommetGV(), h);
  }

double SommetTrade()
  {
   return(GlobalVariableCheck(SommetGV()) ? GlobalVariableGet(SommetGV()) : 0.0);
  }

double AtrEntree()
  {
   if(GlobalVariableCheck(AtrEntreeGV()))
     {
      double a = GlobalVariableGet(AtrEntreeGV());
      if(a > 0) return(a);
     }
   return(ValeurAtrJour());
  }

//| Jours (barres D1) ecoules depuis la premiere unite. -1 = inconnu.|
int JoursDepuisEntree()
  {
   datetime t0 = TempsPremiereUnite();
   if(t0 == 0) return(-1);
   int i0 = iBarShift(_Symbol, PERIOD_D1, t0, false);
   return(i0);
  }

//| Meilleur profit atteint depuis l'entree, en ATR d'entree.        |
//| Relu sur les plus-hauts D1, exactement comme le banc.            |
//| -1 = mesure indisponible (on ne coupe jamais dans le doute).     |
double MeilleurProfitEnAtr()
  {
   double e = PrixPremiereUnite();
   int    i0 = JoursDepuisEntree();
   if(e <= 0 || i0 < 0) return(-1.0);
   int idx = iHighest(_Symbol, PERIOD_D1, MODE_HIGH, i0 + 1, 0);
   if(idx < 0) return(-1.0);
   double h = iHigh(_Symbol, PERIOD_D1, idx);
   double a = AtrEntree();
   if(a <= 0 || h <= 0) return(-1.0);
   return((h - e) / a);
  }

//+------------------------------------------------------------------+
//| GROKBOT1 no 1 -- COUPE-TEMPS CONDITIONNEL (point 6 du comite).   |
//| Ferme la position si, apres CoupeTempsJours jours, le meilleur   |
//| profit atteint n'a jamais franchi CoupeTempsSeuilATR x ATR.      |
//| Retourne true si la position vient d'etre fermee.                |
//+------------------------------------------------------------------+
bool CoupeTempsDeclenche()
  {
   if(!CoupeTempsActif) return(false);
   if(!PositionOuverte()) return(false);
   if(CoupeTempsIgnoreSiPyramide && NombreUnites() > 1) return(false);
   int jours = JoursDepuisEntree();
   if(jours < CoupeTempsJours) return(false);
   double mfe = MeilleurProfitEnAtr();
   if(mfe < 0.0) return(false);                 // mesure indisponible : on ne coupe pas
   if(mfe >= CoupeTempsSeuilATR) return(false); // le trade a progresse : on le laisse courir
   Notifier(StringFormat("COUPE-TEMPS : %d jours sans progres (meilleur %.2f ATR < %.2f) -> fermeture",
                         jours, mfe, CoupeTempsSeuilATR));
   EcrireJournal(StringFormat("coupe_temps=OUI jours=%d mfe_atr=%.2f seuil=%.2f",
                              jours, mfe, CoupeTempsSeuilATR));
   coupeTempsFaits++;
   FermerPositions(false);
   return(true);
  }

//+------------------------------------------------------------------+
//| GROKBOT1 no 2 -- REENGAGEMENT APRES SORTIE GAGNANTE (Grok no 5). |
//| Desactive par defaut : mesure neutre au banc. Le code reste pour |
//| pouvoir le rouvrir sur un chassis a entree non-canal.            |
//+------------------------------------------------------------------+
void ArmerReengagement(double sommet)
  {
   if(!ReengagementActif) return;
   if(sommet <= 0) return;
   reengSommet = sommet;
   reengQuand  = TimeCurrent();
   Print("GrokBot1 : reengagement arme au-dessus de ",
         DoubleToString(sommet, _Digits), " + ",
         DoubleToString(ReengagementATR, 2), " ATR");
  }

void DesarmerReengagement()
  {
   reengSommet = 0.0;
   reengQuand  = 0;
  }

double NiveauReengagement()
  {
   if(reengSommet <= 0) return(0.0);
   double a = ValeurAtrJour();
   if(a <= 0) return(0.0);
   return(reengSommet + ReengagementATR * a);
  }

bool ReengagementDeclenche(double prixDecision)
  {
   if(!ReengagementActif || reengSommet <= 0) return(false);
   if(ReengagementJours > 0 && reengQuand > 0)
     {
      int jours = (int)((TimeCurrent() - reengQuand) / 86400);
      if(jours > ReengagementJours) { DesarmerReengagement(); return(false); }
     }
   double niveau = NiveauReengagement();
   if(niveau <= 0) return(false);
   return(prixDecision > niveau);
  }

//+------------------------------------------------------------------+
//| GROKBOT1 no 3 -- AFFICHAGE GRAPHIQUE                             |
//+------------------------------------------------------------------+
string txtPanneau[];
color  couleurPanneau[];

void Empiler(int ligne, string texte, color teinte)
  {
   if(ArraySize(txtPanneau) <= ligne)
     {
      ArrayResize(txtPanneau, ligne + 1);
      ArrayResize(couleurPanneau, ligne + 1);
     }
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

void LignePrix(string cle, double prix, color teinte, ENUM_LINE_STYLE style)
  {
   string nom = PANNEAU + "P_" + cle;
   if(prix <= 0)
     {
      if(ObjectFind(0, nom) >= 0) ObjectDelete(0, nom);
      return;
     }
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

void EffacerPanneau()
  {
   ObjectsDeleteAll(0, PANNEAU);
   ChartRedraw();
  }

//| Le fond du panneau, cree une seule fois.                         |
void FondPanneau(int lignes)
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
   ObjectSetInteger(0, nom, OBJPROP_XSIZE, 27 * AffichageTaille);
   ObjectSetInteger(0, nom, OBJPROP_YSIZE, 20 + lignes * (AffichageTaille + 6));
   ObjectSetInteger(0, nom, OBJPROP_BGCOLOR, AffichageFond);
   ObjectSetInteger(0, nom, OBJPROP_COLOR, AffichageFond);
  }

//| Rafraichit tout le panneau. Appele a chaque tick et au timer :   |
//| l'affichage ne prend AUCUNE decision, il ne fait que montrer.    |
void RafraichirAffichage()
  {
   static bool dejaEfface = false;
   if(!AffichageActif)
     {
      if(!dejaEfface) { EffacerPanneau(); dejaEfface = true; }
      return;
     }
   dejaEfface = false;
   // hors mode visuel, le testeur n'a pas d'ecran : on ne dessine rien.
   if(MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_VISUAL_MODE)) return;
   static uint dernierDessin = 0;
   uint maintenant = GetTickCount();
   if(dernierDessin != 0 && (maintenant - dernierDessin) < 250) return;
   dernierDessin = maintenant;

   double equite  = AccountInfoDouble(ACCOUNT_EQUITY);
   double base    = GlobalVariableCheck(BaseGV()) ? GlobalVariableGet(BaseGV()) : 0.0;
   double avance  = (base > 0) ? (equite / base - 1.0) * 100.0 : 0.0;
   double objectif = ObjectifPhasePctCourant();
   bool   halte   = GlobalVariableCheck(HaltGV()) && GlobalVariableGet(HaltGV()) > 0;
   bool   pauseJ  = GlobalVariableCheck(DayGV()) && GlobalVariableGet(DayGV()) > 0;

   int    unites  = NombreUnites();
   double entree  = PrixPremiereUnite();
   double bid     = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double stop    = 0.0, lots = 0.0, pnl = 0.0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != NumeroMagique) continue;
      lots += PositionGetDouble(POSITION_VOLUME);
      pnl  += PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
      double sl = PositionGetDouble(POSITION_SL);
      if(sl > stop) stop = sl;
     }

   int    besoin = MathMax(PeriodeEntree, PeriodeSortie) + 2;
   double hautCanal = 0.0, basCanal = 0.0;
   MqlRates r[];
   ArraySetAsSeries(r, true);
   if(CopyRates(_Symbol, PERIOD_D1, 0, besoin, r) >= besoin)
     {
      hautCanal = r[1].high;
      for(int i = 2; i <= PeriodeEntree; i++) if(r[i].high > hautCanal) hautCanal = r[i].high;
      basCanal = r[1].low;
      for(int i = 2; i <= PeriodeSortie; i++) if(r[i].low < basCanal) basCanal = r[i].low;
     }
   double seuilEntree = (hautCanal > 0) ? hautCanal * (1.0 + TamponCassurePct / 100.0) : 0.0;

   color vert = clrLimeGreen, rouge = clrTomato, jaune = clrGold, gris = AffichageTexte;
   ArrayResize(txtPanneau, 0);
   ArrayResize(couleurPanneau, 0);
   int L = 0;
   Empiler(L++, "GROKBOT1  " + _Symbol + "  " + EnumToString(UT_Decision)
                  + "  (chassis L13)", clrDeepSkyBlue);
   Empiler(L++, StringFormat("phase %s  %+.2f %% / %.2f %%   %s",
                  (PhaseActuelle == PHASE_1 ? "1" : (PhaseActuelle == PHASE_2 ? "2" : "finance")),
                  avance, objectif,
                  (objectif > 0 && avance >= objectif ? "OBJECTIF ATTEINT" : "")),
             (objectif > 0 && avance >= objectif) ? vert : gris);
   Empiler(L++, StringFormat("gardien jour -%.2f %%   total -%.1f %%   %s",
                  LimitePerteJourPct, LimitePerteTotalePct,
                  halte ? "HALTE GENERALE" : (pauseJ ? "PAUSE DU JOUR" : "actif")),
             (halte || pauseJ) ? rouge : vert);
   Empiler(L++, "----------------------------------------", gris);

   if(unites > 0)
     {
      Empiler(L++, StringFormat("position  %d/%d unite(s)  %.2f lot  %+.2f $",
                     unites, MaxUnites, lots, pnl), (pnl >= 0) ? vert : rouge);
      Empiler(L++, StringFormat("entree %s   stop %s",
                     DoubleToString(entree, _Digits), DoubleToString(stop, _Digits)), gris);
      int    jours = JoursDepuisEntree();
      double mfe   = MeilleurProfitEnAtr();
      if(CoupeTempsActif)
        {
         string etat;
         color  teinte = gris;
         if(CoupeTempsIgnoreSiPyramide && unites > 1)
            etat = "immunise (pyramide)";
         else if(jours < 0 || mfe < 0.0)
            etat = "mesure indisponible";
         else if(mfe >= CoupeTempsSeuilATR)
           { etat = StringFormat("sauf : %.2f ATR >= %.2f", mfe, CoupeTempsSeuilATR); teinte = vert; }
         else
           {
            etat = StringFormat("%.2f ATR < %.2f -> coupe dans %d j",
                                mfe, CoupeTempsSeuilATR, (int)MathMax(CoupeTempsJours - jours, 0));
            teinte = (CoupeTempsJours - jours <= 2) ? rouge : jaune;
           }
         Empiler(L++, StringFormat("coupe-temps j%d/%d  %s", (int)MathMax(jours, 0),
                        CoupeTempsJours, etat), teinte);
        }
      else
         Empiler(L++, "coupe-temps  desactive", gris);
     }
   else
     {
      Empiler(L++, "position  aucune", gris);
      Empiler(L++, StringFormat("entree si cloture > %s  (canal %s)",
                     DoubleToString(seuilEntree, _Digits),
                     DoubleToString(hautCanal, _Digits)), gris);
      if(replArme)
         Empiler(L++, StringFormat("repli L12 arme : %s  (%d barre(s))",
                        DoubleToString(replNiveau, _Digits), replReste), jaune);
      else if(ReengagementActif && reengSommet > 0)
         Empiler(L++, StringFormat("reengagement arme : > %s",
                        DoubleToString(NiveauReengagement(), _Digits)), jaune);
      else
         Empiler(L++, "aucune attente armee", gris);
     }
   Empiler(L++, StringFormat("canal bas (sortie) %s   prix %s",
                  DoubleToString(basCanal, _Digits), DoubleToString(bid, _Digits)), gris);
   Empiler(L++, "----------------------------------------", gris);
   Empiler(L++, StringFormat("macro %s   annonces %s",
                  biaisMacroOK ? "OK" : "BLOQUE",
                  newsBloquaitAvant ? "FENETRE" : "libre"),
             (biaisMacroOK && !newsBloquaitAvant) ? vert : jaune);
   Empiler(L++, StringFormat("vol x%.2f   ecurie %d/%d   coupes %d",
                  facteurVol, ComptePositionsEcurie(), MaxPositionsEcurie, coupeTempsFaits), gris);
   // le fond d'abord (il porte le ZORDER le plus bas), le texte ensuite
   FondPanneau(L);
   for(int i = 0; i < L; i++) Etiquette(i, txtPanneau[i], couleurPanneau[i]);

   if(AffichageLignes)
     {
      LignePrix("canal_haut", seuilEntree, clrDodgerBlue, STYLE_DOT);
      LignePrix("canal_bas",  basCanal,    clrSlateGray,  STYLE_DOT);
      LignePrix("stop",       stop,        clrTomato,     STYLE_SOLID);
      LignePrix("reeng",      (unites == 0 ? NiveauReengagement() : 0.0), clrGold, STYLE_DASH);
     }
   ChartRedraw();
  }
'''

# ------------------------------------------------------------------ 5. patchs
def patcher(src, fichier, marche, magic_l13):
    t = io.open(src, encoding="utf-8").read()

    # -- entete : on remplace le bloc de commentaires initial
    fin = t.index("#property copyright")
    t = ENTETE % {"fichier": fichier} + t[fin:]

    # -- inputs
    ancre = "input bool   JournalActif"
    assert ancre in t, "ancre inputs"
    t = t.replace(ancre, INPUTS + ancre, 1)

    # -- globaux
    ancre = 'string BaseGV() { return "MACROBOT_BASE_"'
    assert ancre in t, "ancre globaux"
    t = t.replace(ancre, GLOBAUX + "\n" + ancre, 1)

    # -- fonctions, juste avant OnTick
    ancre = "void OnTick()"
    assert ancre in t, "ancre OnTick"
    t = t.replace(ancre, FONCTIONS + "\n//+------------------------------------------------------------------+\n" + ancre, 1)

    # -- OnInit : trace de la configuration + premier dessin
    ancre = "   EventSetTimer(60);\n   return(INIT_SUCCEEDED);"
    assert ancre in t, "ancre OnInit"
    t = t.replace(ancre,
        '   Print("GrokBot1 charge | coupe-temps=", CoupeTempsActif, " ", CoupeTempsJours,\n'
        '         " j / ", CoupeTempsSeuilATR, " ATR | reengagement=", ReengagementActif,\n'
        '         " | affichage=", AffichageActif);\n'
        '   if(!PositionOuverte()) OublierAtrEntree();   // repart propre si on est a plat\n'
        '   RafraichirAffichage();\n\n' + ancre, 1)

    # -- OnDeinit : nettoyage des objets
    ancre = "void OnDeinit(const int reason)\n  {\n   EventKillTimer();"
    assert ancre in t, "ancre OnDeinit"
    t = t.replace(ancre, ancre + "\n   EffacerPanneau();   // GrokBot1", 1)

    # -- OnTimer : le panneau vit meme sans nouvelle barre.
    #    Les deux chassis n'ont pas le meme corps de OnTimer (le petrole
    #    surveille le swap en plus) : on vise l'accolade fermante du bloc.
    d = t.index("void OnTimer()")
    f = t.index("\n  }", d) + 1
    t = t[:f] + "   RafraichirAffichage();   // GrokBot1\n" + t[f:]

    # -- OnTick : afficher a chaque tick, avant meme la barre fermee
    ancre = "void OnTick()\n  {\n   if(!VerifierProtections()) return;"
    assert ancre in t, "ancre debut OnTick"
    t = t.replace(ancre,
        "void OnTick()\n  {\n   RafraichirAffichage();   // GrokBot1 : l'affichage ne decide rien\n"
        "   if(!VerifierProtections()) return;", 1)

    # -- coupe-temps : juste apres la sortie par le canal, avant le pyramidage
    ancre = "      // --- L3 : PYRAMIDAGE (Turtles) + stop commun -------------------"
    assert ancre in t, "ancre pyramidage"
    t = t.replace(ancre,
        "      // --- GROKBOT1 : suivi du sommet + coupe-temps (point 6 du comite) ---\n"
        "      MajSommetTrade();\n"
        "      if(CoupeTempsDeclenche()) return;\n\n" + ancre, 1)

    # -- entree : la cassure OU le reengagement
    ancre = ("   if(!entreeParRepli)\n     {\n"
             "   if(declencheur <= hautCanal * (1.0 + TamponCassurePct / 100.0)) return;"
             "   // L4.31 tampon anti-faux-signal")
    assert ancre in t, "ancre entree"
    t = t.replace(ancre,
        "   if(!entreeParRepli)\n     {\n"
        "      // L4.31 tampon anti-faux-signal ; GrokBot1 ajoute une 2e porte d'entree\n"
        "      bool cassure  = (declencheur > hautCanal * (1.0 + TamponCassurePct / 100.0));\n"
        "      bool reengage = (!cassure && ReengagementDeclenche(declencheur));\n"
        "      if(!cassure && !reengage) return;\n"
        "      if(reengage)\n"
        "         Print(\"GrokBot1 : reengagement declenche a \",\n"
        "               DoubleToString(declencheur, _Digits), \" (sommet \",\n"
        "               DoubleToString(reengSommet, _Digits), \")\");", 1)

    # -- l'entree prise desarme le reengagement et memorise l'ATR
    remplaces = 0
    for vieux, etiquette in (('trade.Buy(lot, _Symbol, 0.0, sl, 0.0, "L8 cassure 20j");',
                              "GrokBot1 cassure 20j"),
                             ('trade.Buy(lot, _Symbol, 0.0, sl, 0.0, "USOIL_Breakout saison");',
                              "GrokBot1 saison")):
        if vieux not in t:
            continue
        neuf = ('if(trade.Buy(lot, _Symbol, 0.0, sl, 0.0, "%s"))\n'
                "     {\n"
                "      DesarmerReengagement();   // GrokBot1 : une entree prise desarme l'attente\n"
                "      MemoriserAtrEntree();     // GrokBot1 : l'ATR du jour d'entree sert au coupe-temps\n"
                "     }") % etiquette
        t = t.replace(vieux, neuf, 1)
        remplaces += 1
    assert remplaces == 1, "ancre trade.Buy (%d trouvee(s))" % remplaces

    # -- OnTradeTransaction : armer le reengagement quand le trade se ferme en profit
    ancre = ("      Notifier(StringFormat(\"SORTIE %.2f lot @ %s | P/L: %.2f $\", vol,\n"
             "                            DoubleToString(prix, _Digits),\n"
             "                            HistoryDealGetDouble(trans.deal, DEAL_PROFIT)));")
    assert ancre in t, "ancre sortie"
    t = t.replace(ancre, ancre +
        "\n      // --- GROKBOT1 : fin de trade -> armer le reengagement si gagnant ---\n"
        "      sortieProfitCumul += HistoryDealGetDouble(trans.deal, DEAL_PROFIT)\n"
        "                         + HistoryDealGetDouble(trans.deal, DEAL_SWAP)\n"
        "                         + HistoryDealGetDouble(trans.deal, DEAL_COMMISSION);\n"
        "      if(NombreUnites() == 0)\n"
        "        {\n"
        "         if(sortieProfitCumul > 0) ArmerReengagement(SommetTrade());\n"
        "         else DesarmerReengagement();\n"
        "         sortieProfitCumul = 0.0;\n"
        "         OublierAtrEntree();\n"
        "        }", 1)

    # -- identite : magic, notifications, marche
    # -- GrokBot1 GARDE les magics du chassis L13 (20261132 BTC / 20261133 petrole) :
    #    il remplace les deux cassures d'une ecurie L13, et le plafond partage
    #    (ComptePositionsEcurie) des trois autres robots continue de le compter.
    assert ("= " + magic_l13 + ";") in t, "magic L13 attendu : " + magic_l13

    t = t.replace('SendNotification("[L8] BTC breakout : "', 'SendNotification("[GrokBot1] BTC cassure : "')
    t = t.replace('SendNotification("[L8] Pétrole : "', 'SendNotification("[GrokBot1] Pétrole : "')
    t = t.replace('#property version   "1.00"', '#property version   "1.00"\n#property description "GrokBot1 -- chassis L13 + coupe-temps conditionnel + affichage graphique"')

    return t

os.makedirs(CIBLE, exist_ok=True)
for rel, nom, marche, magic in SOURCES:
    src = os.path.join(RACINE, rel)
    out = patcher(src, nom, marche, magic)
    with io.open(os.path.join(CIBLE, nom), "w", encoding="utf-8") as f:
        f.write(out)
    print("ecrit %-38s %6d octets" % (nom, len(out.encode("utf-8"))))
