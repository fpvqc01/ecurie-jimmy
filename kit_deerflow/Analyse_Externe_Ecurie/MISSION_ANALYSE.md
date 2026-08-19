# Mission d'analyse independante — systeme de trading « Ecurie Jimmy »

Tu es un reviseur quantitatif independant. Analyse ce systeme de trading
algorithmique et propose des ameliorations. NE PROPOSE PAS de reecrire le
systeme : cherche les failles, les risques oublies et les pistes testables.

## Contexte
- Objectif : passer un challenge FTMO (compte 100k, limites -5 %/jour, -10 % total)
- 2 ecuries de 5 robots (MQL5 en production ; MQL4 = banc d'essai avec pyramidage)
- ~85 backtests deja faits, cimetiere des idees rejetees dans README.md
- Standards de validation (a respecter dans tes suggestions) :
  1. principe economique externe, 2. net des frais reels,
  3. stable sur les 2 moities de periode ET parametres voisins,
  4. ameliore le PORTEFEUILLE sous plafond de 2 positions.

## Questions precises
1. Quels risques le systeme sous-estime-t-il ? (on connait deja : exposition
   notionnelle 2,13x en cas de gap, echantillon reel minuscule)
2. Vois-tu des bogues ou incoherences dans les sources MQL4/MQL5 ?
3. Le pyramidage L3 (3 unites, +0,5 ATR, stop 2 ATR sous la derniere,
   gardien -2,5 %/jour) a-t-il des failles connues dans la litterature ?
4. Quelles idees TESTABLES (pas de la theorie) meriteraient un backtest,
   en evitant celles deja au cimetiere du README ?
5. La detection de TP par historique en MQL4 (VerifierTpEncaisse) est-elle robuste ?

## Contenu du dossier
- README.md : le systeme complet + cimetiere des idees rejetees
- robots_mql5_I2plus/ : les 5 robots en production (MQL5)
- robots_mql4_L3/ : les 5 robots du banc d'essai (MQL4, pyramidage)
- backtests_cles/ : moteur de simulation + 5 tests representatifs
