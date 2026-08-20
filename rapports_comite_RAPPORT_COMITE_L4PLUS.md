# RAPPORT DU COMITÉ — Écurie « Jimmy L4+ » (et bilan L4)

**Date : 20 août 2026, soirée · Version auditée : L4+ du 18 h 37 (patch L4.32), variante SansChallenge EN SERVICE sur C:\MT6 · Comité complet : 13 analyses d'experts**

---

## D'OÙ VIENT L4+ (pour être clair)

L4+ est la sortie du script `patch_l432.py` (18 h 32) : les **4 correctifs demandés par le comité de cet après-midi ont été appliqués** à L4.3, les dossiers renommés « Jimmy L4+ », compilés et déployés à 18 h 34-37. Le déploiement lui-même est propre (fichiers identiques aux sources, compilation à jour, les 2 positions BTC ouvertes pendant le remplacement reconnues par le nouveau code, filtre DXY frais).

---

## VERDICT GLOBAL EN 5 LIGNES

Les 4 correctifs du comité sont **réels et bien faits** — les deux plus gros trous de l'après-midi (coupe-circuit qui ne fermait pas, gardien aveugle aux gaps) sont bouchés, et or/Nasdaq sont enfin alignés sur le moteur de backtest. **MAIS le patch a introduit un bogue critique : or et Nasdaq ne peuvent plus jamais prendre un trade** — l'écurie en service roule en réalité à **3 robots sur 5**, en silence. Et la variante SansChallenge qui tourne est la **config la plus agressive des deux** (plafond de volatilité et frein d'équité désactivés ensemble). L4+ peut rester en démo, mais ce n'est **pas** la version validée par les backtests tant que ce n'est pas réparé et recompilé.

---

## 🔴 LES 3 URGENCES

### 1. Bogue FibLo/FibHi : or et Nasdaq sont éteints en silence
*Trouvé indépendamment par 2 experts (red team + vérificateur git).*
En modifiant la ligne du swing, deux affectations ont été avalées par le commentaire :
`SwingLookback = 10;   // L4.32 : 10 JOURS (= moteur) FibLo = 0.20; FibHi = 0.80;`
`FibLo` et `FibHi` ne sont jamais exécutées → elles valent 0,0 → la condition d'entrée devient impossible. **Aucune erreur, aucun message : les 2 robots chargent normalement et ne tradent juste jamais.** Présent dans les 4 fichiers (or + Nasdaq, challenge + SansChallenge) : `XAUUSD_Or_L43_H4.mq5:259/265`, `US100_Nasdaq_L43_H4.mq5:226/232`.
**Correctif : sortir les 2 affectations du commentaire (2 lignes × 4 fichiers), recompiler avec /portable, redéployer.**

### 2. La variante EN SERVICE roule sans plafond de volatilité NI frein d'équité
*Portefeuille + red team.* Le nouveau plafond « facteurVol max 1,0 » est conditionnel à `ModeChallengeActif` — qui est `false` dans la variante SansChallenge en service. Le throttle 0,75 saute aussi. Résultat : le robot en service peut grossir ses mises jusqu'à **×1,5** les jours « calmes » (or : 3 % de risque au lieu de 2), sans aucun frein. Pire journée simulée en SansChallenge : **−4,9 à −8,7 %** selon le glissement.
**Correctif : plafonner à 1,0 sans condition (`if(facteurVol > 1.0) facteurVol = 1.0;`) — ou assumer par écrit que la démo roule plus agressif que le challenge.**

### 3. Le trou BTC+BTC est toujours ouvert
*Portefeuille + vérificateur git.* `FamilleCorreleeOccupee()` exempte toujours le BTC : les 2 robots BTC peuvent occuper les 2 sièges de l'écurie sur le même marché. Pire journée simulée en challenge : **−4,2 à −6,2 %** (limite FTMO : −5 %); exposition notionnelle BTC jusqu'à **150-209 % du compte**, ouverte la fin de semaine quand le gardien ne peut pas réagir. Note : un commit a chiffré la règle « un seul BTC » à −4,8 pts de CAGR/10 ans et a choisi de ne pas l'implémenter — c'est un choix documenté, mais le comité recommande l'inverse pour un compte à limites fixes.
**Correctif : ajouter une famille « crypto » au plafond de corrélation. Bonus fortement suggéré : plafond de notionnel total (~100 % du compte) avant chaque unité de pyramide, et réduction de la pile BTC le vendredi soir.**

---

## ✅ LES 4 CORRECTIFS CONFIRMÉS (vérifiés ligne par ligne, dans les 10 fichiers)

1. **Coupe-circuit HALT retenté à chaque tick** — le `dejaFerme` a disparu; une fermeture refusée (marché fermé, requote) repart d'elle-même au tick suivant, y compris quand le HALT vient d'un autre robot.
2. **Anti-gap du gardien quotidien** — nouvelle variable `MACROBOT_LASTEQ_` : la référence du jour est l'équité d'AVANT le gap. Un gap du lundi compte maintenant dans la perte du jour, comme chez FTMO. (Prix de cette sécurité : une fermeture peut s'exécuter au spread d'ouverture du dimanche.)
3. **Facteur de volatilité réparé** — enfin appelé dans BTC EMA, péremption 7 jours du fichier, plafond 1,0 en mode challenge (voir urgence n° 2 pour la variante en service).
4. **Or/Nasdaq alignés sur le moteur validé** — ATR/RSI/swing passés en journalier : stops ~2,4× plus larges, lots ~2× plus petits. Ça règle le « notionnel 2× trop gros » et ramène le swap réel au niveau simulé (l'expert forex : « le point le mieux réglé de cette version »).

---

## 📊 LES VRAIS CHIFFRES (contre-vérificateur, fichier BTC H1 régénéré)

| | Données brutes | **Données propres (référence honnête)** |
|---|---|---|
| CAGR 10 ans (mode challenge ON) | +47,0 % | **+34,9 %** |
| CAGR 2021-2026 | +37,5 % | **+26,4 %** |
| Jours ≤ −5 % en 10 ans | 3 | **1** (2017; zéro depuis 2021) |
| Réussite de challenge simulée | 87 % | **~91-96 %** |

- Les +47/+37,5 % étaient gonflés de ~11-12 points par les barres de fin de semaine figées. Reproductibilité des scripts : parfaite.
- **« Validée walk-forward 2021-2026 » survend** : seules les cadences l'ont été; le tampon 0,25 % et la structure ont été optimisés sur la fenêtre complète. L'en-tête du robot pétrole (+11,9 %/an) décrit l'ancien robot D1 — périmé.
- Frais modélisés ≥ frais réels FTMO, robustes ×2/×3 : solide.

**Quant (ingénieur financier)** : statistiquement solide sur 10 ans (t = 3,9; plateau de paramètres, pas un pic; asymétrie positive; ~4-8× sous Kelly = prudent) — mais **~73 % du résultat vient de la seule manche BTC Cassure**, dont l'avantage a fondu des deux tiers depuis 2021 (plus significatif seul sur la période récente). Or et Nasdaq : figuration sur 10 ans.

**Économiste** : le portefeuille est un pari unique sur « liquidité abondante + taux réels bas ». Août 2026 est hostile (taux réels au plus haut depuis 2008, inflation 3,4 %, Fed penchant hausse, BTC en 2e année baissière post-halving). Seuls vents favorables : dollar faible et or au record. **Planifier sur la bande basse (~+17 %/an ou moins), Nasdaq = maillon fragile dans 5 scénarios sur 6.**

---

## 🟠 TOUJOURS OUVERTS (n° 4 à 10 du comité + nouveaux)

- **Aucun test de spread avant d'entrer** (les 10 fichiers) — décisions de minuit exécutées au premier tick de la réouverture, le pire spread de la journée; le robot BTC EMA D1 décide chaque jour à 17 h New York.
- **Résultats des mégacaps invisibles** (boursier) — le calendrier ne couvre que la macro USD; un soir de résultats Nvidia = gap Nasdaq de ±0,7-2 % non couvert. Idem réunions OPEP+ pour le pétrole.
- **macrobot_news.txt et macrobot_bias.txt toujours sans péremption** (le correctif n'a couvert que vol).
- **Mode SERRER par défaut** pendant les annonces (adouci par l'ATR journalier, mais toujours risqué sur financé FTMO Standard et contre-productif en tendance).
- **Swap « bonus » du pétrole cru sur parole** — aucun code ne lit le swap réel; en contango il devient franchement négatif.
- **Throttle 20 jours perdu à chaque redémarrage** du laptop (en mémoire vive seulement).
- Divers : garde lotStep manquante or/Nasdaq, pas de plancher de stop (atténué par l'ATR journalier), ChallengeInitialBalance absent de 3 robots, magic 20261115 partagé par 3 robots.
- **Rappel structurel** (portefeuille) : même parfait, ce portefeuille 100 % long a un drawdown historique de −16 à −21 % — les protections limitent la perte par jour, pas la série de jours perdants. Un compte FTMO démarré au mauvais moment meurt quand même.

---

## BILAN L4 (l'ancienne génération, en réserve dans MT6)

Les 9 problèmes de l'après-midi : **tous présents**, plus aucun des correctifs L4.32, plus un facteur vol qui peut amplifier ×1,5 même en challenge, et des cadences jamais validées. Ses chiffres se reproduisent mais tombent à **+21,9 %/an** sur données propres, avec un pire jour à **−14,8 %** (krach BTC 2017). Le robot Nasdaq L4 n'a jamais été fidèlement backtesté (indicateurs H4 vs moteur journalier). **Verdict : moins sûre que L4+ sur toute la ligne — à supprimer de MT6 (quand aucune position n'est ouverte) pour éviter d'attacher le mauvais robot un jour.**

---

## PLAN D'ACTION (dans l'ordre)

| # | Action | Type |
|---|---|---|
| 1 | **Réparer FibLo/FibHi** (4 fichiers), recompiler /portable, redéployer | Code — 10 min, remet l'écurie à 5/5 robots |
| 2 | Plafond facteurVol inconditionnel (ou assumer l'agressivité de la démo par écrit) | Code |
| 3 | Famille « crypto » dans le plafond de corrélation (un seul BTC à la fois) + plafond de notionnel | Code |
| 4 | Péremption 7 jours sur news/bias; test de spread avant les entrées; lire le swap réel du pétrole (`SYMBOL_SWAP_LONG`) et alerter s'il devient négatif | Code |
| 5 | Corriger les en-têtes (walk-forward survendu, pétrole périmé) et documenter les chiffres « données propres » (+35/+26 %) comme référence | Doc |
| 6 | Supprimer les dossiers L4 de MT6 (quand aucune position ouverte) | Ménage manuel |
| 7 | Laisser la démo rouler 2-3 mois et comparer trade par trade avec le moteur (le vrai test hors échantillon) | Patience |
| 8 | Le jour venu : FTMO **Swing**, budget 1-2 challenges ratés (~10-20 % de malchance incompressible) | Décision |

---

*Comité complet : vérificateur git dédié, red team, analyste de portefeuille, contre-vérificateur de chiffres, sceptique de backtest, ingénieur financier (quant), expert boursier, expert forex, économiste, vérificateur d'infrastructure — plus les rapports de l'après-midi (règles FTMO/FundingPips, Monte Carlo, qualité des données) qui restent valides. Aucun fichier des robots n'a été modifié pendant la vérification.*
