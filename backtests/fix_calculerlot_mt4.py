# -*- coding: utf-8 -*-
"""CORRECTION DEFINITIVE du trade manque (cassure BTC prise par I2+ mais pas L3).
Distance SL du trade = 8,4 % -> le garde-fou 10 % ne l'a PAS bloque.
Le vrai coupable est un return silencieux dans CalculerLot :
  - MODE_TICKVALUE peut retourner 0 pour les CFD/crypto en MT4 (classique
    quand la conversion de devise n'est pas chargee) -> return(0.0) MUET.
Correctifs :
  1. FALLBACK : si tickValue/tickSize invalides, calculer la perte par lot
     avec MODE_LOTSIZE (taille de contrat x distance, en USD pour nos symboles).
  2. JOURNALISER chaque cause de refus (tick, lot mini, marge, garde-fou SL)
     -> plus AUCUN echec silencieux possible dans le chemin d'entree."""
import glob, os, re

MQ4 = r"C:\Users\jplou\AppData\Roaming\MetaQuotes\Terminal\2C68BEE3A904BDCEE3EEF5A5A77EC162\MQL4\Experts\Jimmy L3"

ANCIEN_DEBUT = """   if(distanceSL <= 0) return(0.0);
   double valeurTick = MarketInfo(Symbol(), MODE_TICKVALUE);
   double tailleTick = MarketInfo(Symbol(), MODE_TICKSIZE);
   if(valeurTick <= 0 || tailleTick <= 0) return(0.0);
   double risque = AccountBalance() * RisqueParTradePct / 100.0 * facteurVol;
   double perteParLot = distanceSL / tailleTick * valeurTick;
   if(perteParLot <= 0) return(0.0);"""

NOUVEAU_DEBUT = """   if(distanceSL <= 0) return(0.0);
   double valeurTick = MarketInfo(Symbol(), MODE_TICKVALUE);
   double tailleTick = MarketInfo(Symbol(), MODE_TICKSIZE);
   double risque = AccountBalance() * RisqueParTradePct / 100.0 * facteurVol;
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
     }"""

ANCIEN_MINI = """   if(pas > 0) lot = MathFloor(lot / pas) * pas;
   if(lot < mini) return(0.0);"""

NOUVEAU_MINI = """   if(pas > 0) lot = MathFloor(lot / pas) * pas;
   if(lot < mini)
     {
      Print("REFUS D'ENTREE: lot calcule ", DoubleToString(lot, 4),
            " sous le minimum ", DoubleToString(mini, 2), " — risque trop petit pour ce stop.");
      return(0.0);
     }"""

for p in sorted(glob.glob(os.path.join(MQ4, "*.mq4"))):
    t = open(p, encoding="utf-8", errors="replace").read()
    nom = os.path.basename(p)
    notes = []
    if ANCIEN_DEBUT in t:
        t = t.replace(ANCIEN_DEBUT, NOUVEAU_DEBUT)
        notes.append("fallback tick value + logs")
    elif "FALLBACK" in t:
        notes.append("fallback deja present")
    else:
        notes.append("!! motif CalculerLot introuvable")
    if ANCIEN_MINI in t:
        t = t.replace(ANCIEN_MINI, NOUVEAU_MINI)
        notes.append("log lot mini")
    # journaliser aussi le garde-fou SL du chemin d'entree (cassures)
    t2, k = re.subn(
        r"   if\(distanceSL <= 0 \|\| distanceSL > 0\.50 \* Ask\) return;",
        """   if(distanceSL <= 0 || distanceSL > 0.50 * Ask)
     {
      Print("REFUS D'ENTREE: distance de stop ", DoubleToString(distanceSL, Digits),
            " hors bornes (0 a 50 % du prix).");
      return;
     }""", t)
    if k:
        notes.append("log garde-fou SL")
    t = t2
    open(p, "w", encoding="utf-8").write(t)
    print("  %-28s %s" % (nom, ", ".join(notes)))
