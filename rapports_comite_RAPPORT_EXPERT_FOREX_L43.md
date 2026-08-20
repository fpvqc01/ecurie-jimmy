# CONTRE-EXPERTISE FOREX/CFD — ÉCURIE L4.3

**Date : 20 août 2026 · 11e expert du comité (lunette forex/CFD) · Lecture seule, aucun fichier modifié**

**Trois mots de vocabulaire d'abord :**
- **Pip/point** : la plus petite variation cotée d'un prix (sur l'or, 1 point = 0,01 $ l'once).
- **Swap (financement)** : les intérêts que le courtier te charge (ou te paie) pour chaque nuit où tu gardes une position ouverte. Sur un CFD acheté, presque toujours négatif quand les taux sont hauts.
- **Rollover** : 17 h New York (= minuit serveur EET), l'instant où le swap est débité et où le marché des CFD or/indices/pétrole fait une pause d'environ 1 h. Spread énorme, presque pas de ticks. Le **mercredi**, le swap compte triple.

---

## VOLET 1 — CONTRE-AVIS SUR LE RAPPORT DU COMITÉ

| # | Conclusion du comité | Avis de l'expert forex |
|---|---|---|
| 1 | HALT fige 3 robots sans fermer | **CONFIRMÉ, et aggravé** : si le HALT se lève pendant la pause quotidienne (rollover) ou le week-end, l'unique tentative de fermeture échoue précisément au pire moment (marché fermé). « Retenter à chaque tick » est le bon correctif — un tick reviendra à la réouverture. |
| 2 | Les 2 robots BTC peuvent occuper les 2 sièges | **CONFIRMÉ** (`FamilleCorreleeOccupee()` exclut explicitement BTC). |
| 3 | `LireFacteurVol()` jamais appelée dans BTC EMA | **CONFIRMÉ** ligne par ligne. Bogue réel. |
| 4 | Facteur vol ×1,5 sans péremption | **CONFIRMÉ.** Plafond à 1,0 en challenge = bonne pratique prop firm. |
| 5 | « Jamais −5 %/jour » faux | **CONFIRMÉ**, et même le −5,61 % du backtest est optimiste : le moteur exécute les stops au prix exact — zéro glissement, zéro gap à travers le stop. |
| 6 | Or/Nasdaq réels ≠ backtest (ATR H4 vs journalier) | **CONFIRMÉ, et plus grave que présenté** : stop réel 2-2,5× plus serré → **notionnel réel 2-2,5× plus gros** que simulé → tous les coûts proportionnels (swap, spread, gap, slippage) sont 2-2,5× plus lourds en réel. |
| 7 | ~29 % de barres bidon | **CONFIRMÉ, nuance à double tranchant** : sur or/Nasdaq le swap est double-compté (~+40 %) = conservateur, tant mieux; sur le pétrole (swap modélisé positif) le même double comptage gonfle un *bonus* = anti-conservateur. |
| 8 | Surajustement, bas de fourchette | **CONFIRMÉ**; la lecture des coûts réels tire même plus bas (voir verdict). |
| 9 | Monte Carlo ~1 challenge sur 5 | **CONFIRMÉ** (ordre de grandeur standard pour une stratégie tendance sous contrainte −5 %/jour). |
| 10 | FTMO Swing oui, FundingPips Master hostile | **CONFIRMÉ et appuyé** : le mode « SERRER » des stops avant les annonces augmente la probabilité qu'un SL s'exécute dans la fenêtre interdite ±2 min du financé Standard. Et de toute façon, SERRER est contre-productif sur une stratégie tendance H4/D1 : le whipsaw de pré-annonce chasse ces stops serrés et éjecte de tendances valides. Bloquer les entrées (déjà fait) suffit. |
| Infra | Périodes de graphiques | **Non-problème confirmé** : tout est codé en dur (`PERIOD_H4`/`PERIOD_D1`), le graphique d'attache n'a aucune importance. |

---

## VOLET 2 — CE QUE LE COMITÉ A MANQUÉ (du plus grave au moins grave)

### A. 🔴 Le swap réel sera ~2-2,5× plus lourd que simulé sur or et Nasdaq
Les taux de swap du backtest sont **réalistes** (or ≈ −14 %/an du notionnel, Nasdaq ≈ −11 %, BTC ≈ −30 % débité 7 j/7, conversion H1 correcte) — bon travail. Le problème : l'EA réel dimensionne sur l'ATR H4 → notionnel or ~2× l'équité au lieu de ~0,7× simulé. Une position or gardée 2 semaines ≈ **−0,9 % d'équité en swap** (la moitié du risque du trade !). Sur une année : **−5 à −7 %/an d'équité en swap réel contre ~−2,5 % simulé → 3 à 4 points de rendement annuel manquants au backtest**, rien que sur l'or. Nasdaq : ~1,5-2 points de plus.

### B. 🔴 Le swap « positif » du pétrole est un instantané, pas une propriété
Le code et le moteur supposent un bonus (+1,9 %/an) codé en dur. Or le swap d'un CFD pétrole suit la **forme de la courbe des futures** : en contango (typique des marchés bien approvisionnés), le swap long devient franchement négatif (2020 : −20 à −40 %/an). La fenêtre déc-mai traverse des bascules de courbe. **À faire : relire le swap USOIL réel dans MT5 chaque début de saison, et retester la manche pétrole avec swap −0,03 %/jour pour voir si elle survit.**

### C. 🔴 Gaps du lundi sur décisions OPEP+ — pyramide 4, zéro protection
L'OPEP+ décide souvent le week-end, marché fermé. Le calendrier du bot (annonces USD) ne couvre pas l'OPEP. Un gap de −5 % sur le WTI (vu en 2020, 2022) sur un notionnel pyramidé ~0,6× équité = **−3 % d'équité d'un coup**, avant tout stop. Correctif opérationnel simple : ne pas laisser la pyramide pleine traverser un week-end de réunion OPEP (dates connues d'avance).

### D. 🟠 Une décision H4 sur six tombe au rollover; le robot D1 décide à LA pire heure
La barre de minuit serveur = 17 h New York : pause d'~1 h sur or/Nasdaq/pétrole, exécution au premier tick de réouverture avec spread 3-10× le normal. Le robot **BTC EMA D1 décide chaque jour à cette heure-là** — spread élargi sur 100 % de ses entrées/sorties, absent du backtest (frais fixes jamais horodatés). Correctif peu coûteux : décaler la décision D1 (ex. barre de 08:00) ou filtrer un spread > seuil avant d'entrer.

### E. 🟠 Gardien d'équité aveugle marché fermé
Les gardiens ne tournent que dans OnTick — pas de ticks = pas de contrôle. Pendant la pause quotidienne et le week-end, seuls les robots BTC surveillent l'équité. Le vrai correctif reste « retenter la fermeture à chaque tick » (premier tick de réouverture). Effet de bord bénin : OnTimer peut tenter des modifications marché fermé → erreurs « market closed » dans le journal, sans conséquence.

### F. 🟡 Décalage d'une heure entre le « jour » du robot (EET) et celui de FTMO (CE(S)T)
Bien absorbé en pratique par la marge 2,5 % vs 5 %. À savoir, pas prioritaire.

### G. 🟡 Points positifs que le comité n'avait pas crédités
- **Calcul de lot correct et robuste au compte non-USD** : `SYMBOL_TRADE_TICK_VALUE` est déjà dans la devise du compte — la bonne façon de faire, beaucoup d'EA amateurs se trompent ici.
- **Dividendes du US100 non modélisés — en ta faveur** (~+0,5-1 %/an de notionnel pour l'acheteur).
- **`LotSelonMarge` avant chaque ordre** : évite les rejets silencieux, pertinent avec le levier crypto 1:1 FTMO.
- Garde-fou d'aberration sur la distance de stop : bon réflexe (le commentaire dit 10 %, le code dit 50 % — commentaire à corriger, pas le code).

### H. 🟡 Divers plus fins
- Données pétrole = futures continus vs CFD spot du compte : les cassures ne tomberont pas exactement aux mêmes prix (tolérable avec le tampon 0,25 %).
- Liquidité du pétrole autour des échéances mensuelles : éviter d'entrer le jour de roll serait un raffinement gratuit.
- `attenteReentree` en mémoire seulement : un redémarrage efface une ré-entrée armée (perte d'opportunité, pas de risque).
- Régime de taux : les swaps simulés figent les taux 2026 sur 10 ans d'historique — les années taux-zéro étaient en réalité plus douces, donc le passé simulé est *trop* pénalisé. Coïncidence conservatrice.

---

## ANALYSE COMPLÈTE — ROBOT PAR ROBOT

| Robot | Verdict | En bref |
|---|---|---|
| **XAUUSD Or H4** | ⚠️ | Mécanique propre (pullback fib+RSI sans look-ahead, stop dans le même ordre que l'achat, breakeven standard, filtre DXY bien pensé) — mais LE robot le plus exposé au swap réel (notionnel ~2× équité) et au spread de rollover. Coûts réels sous-estimés. |
| **US100 Nasdaq H4** | ⚠️ | Copie du robot or (risque 1,5 %, sans DXY — cohérent). Mêmes réserves atténuées; le plafond « un seul métal/indice » est une vraie bonne protection de crise. |
| **BTCUSD Cassure H1** | ⚠️ | La plus solide mécaniquement : Donchian sans look-ahead, pyramide Turtles relue depuis le courtier (survit aux redémarrages — excellent), swap bien simulé. Réserves : le doublon BTC possible, la fermeture d'urgence one-shot, et la pyramide 4 qui traverse le week-end. |
| **BTCUSD EMA D1** | ❌ tant que non corrigé | Deux bogues avérés (LireFacteurVol jamais appelée; HALT qui fige sans fermer) + décision quotidienne à la pire heure de spread + magic partagé fragile. Bonne stratégie, exécution à réparer. |
| **USOIL Pétrole H4** | ⚠️→❌ | Squelette Donchian solide, saisonnalité bien codée, mais la thèse de coûts la plus fragile : swap « bonus » qui peut s'inverser en contango, gaps OPEP+ sans garde-fou, données futures vs CFD. |

**Mécaniques transverses : ✅ pour l'essentiel** — gardiens à double étage avec baseline persistante, filtre d'annonces sur TimeGMT (insensible au fuseau), journaux de réflexion précieux pour le duel démo-vs-backtest.

---

## VERDICT GLOBAL

Le rapport du comité est solide — aucune conclusion majeure contestée. Mais il a audité l'écurie comme du *code* et pas assez comme des *CFD* : une fois ajoutés le swap réel sur des notionnels 2× plus gros que simulés (~3-5 points/an sur or/Nasdaq), un « bonus » pétrole qui peut s'inverser, et des décisions prises à l'heure du rollover, **l'attente honnête glisse de +15-20 % vers +10-15 %/an** — ce qui reste une écurie sérieuse pour un compte démo, et rien de tout cela ne se règle en payant un challenge plus vite.
