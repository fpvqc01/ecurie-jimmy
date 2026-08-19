# -*- coding: utf-8 -*-
"""ETAPE 2 : insere la logique de pyramidage dans OnTick des 2 robots de cassure.
Remplace la boucle de stop suiveur par : ajout d'unite + stop commun Turtle."""
import os, re, shutil

DST = r"C:\Users\jplou\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Experts\Jimmy L3"
DL = r"C:\Users\jplou\Downloads\Ecurie_L3_sources"

NOUVEAU_BLOC = """      // --- L3 : PYRAMIDAGE (Turtles) + stop commun -------------------
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
     }"""

# la boucle de stop suiveur d'origine (a remplacer), tolerante aux 2 variantes
MOTIF = re.compile(
    r"      // stop suiveur[^\n]*\n"
    r"      for\(int i = PositionsTotal\(\) - 1; i >= 0; i--\)\s*\n"
    r"        \{.*?\n        \}\n"
    r"      return;\n"
    r"     \}", re.S)

for nom in ("BTCUSD_Cassure_L3_H4.mq5", "USOIL_Petrole_L3_D1.mq5"):
    chemin = os.path.join(DST, nom)
    with open(chemin, "r", encoding="utf-8") as f:
        t = f.read()
    t2, n = MOTIF.subn(NOUVEAU_BLOC, t, count=1)
    if n != 1:
        print("  ECHEC : motif du stop suiveur introuvable dans %s" % nom)
        continue
    # journal : afficher le nombre d'unites
    t2 = t2.replace('"OUVERTE (stop suiveur)"',
                    '(StringFormat("OUVERTE %d unite(s)", NombreUnites()))')
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(t2)
    shutil.copy(chemin, os.path.join(DL, nom))
    print("  %-28s pyramidage insere (%d car.)" % (nom, len(t2)))
