# RAPPORT DU COMITÉ — L5, challenges plus vite, meilleur rendement

**Date : 20 août 2026 · 5 experts : vérificateur L5, quant (frontière risque/vitesse), règles prop firm (sites officiels), analyste de portefeuille, comptable**

---

## PARTIE 1 — L'ANALYSE DE L5 : PROPRE ✅

L5 = L4+ (FibLo réparé) + option C (aucun ajout de pyramide pétrole le vendredi) + option F (décision BTC EMA à 8 h au lieu de minuit = fini les entrées à la pire heure de spread). Le vérificateur a relu chaque ligne modifiée avec la paranoïa FibLo : **aucun nouveau bogue**, les protections tournent toujours pendant la garde du vendredi et avant 8 h, le déploiement MT6 est conforme (MD5 identiques, compilé 19 h 33, les 5 EA « L5 chargé » avec « GardeVendredi=true » et « heureDecision=8h », positions resynchronisées).

Nuance à savoir : la garde du vendredi bloque seulement les **ajouts** de pyramide — ce n'est pas une fermeture avant le week-end, les positions traversent toujours.

**Les 8 problèmes du comité restent ouverts** (c'était attendu — L5 n'y touchait pas). Le plus concret : le plafond du facteur de volatilité ne s'applique pas à la variante SansChallenge en service. Ménage : les vieux dossiers L4 traînent encore dans MT6.

---

## PARTIE 2 — LA RÉPONSE À TA QUESTION

### La phrase qui résume tout

**« Plus vite » se paie en comptes morts, et « meilleur rendement » ne passe pas par plus de risque — il passe par plus de capital.** Les 5 experts arrivent à la même conclusion par 5 chemins différents. Voici le plan qui domine tout le reste.

### 🥇 LE PLAN RECOMMANDÉ (converge sur les 5 rapports)

**1. Challenge : risque normal (×1,0) — ou ×1,33 avec gardien maintenu à −2,5 % si la vitesse compte vraiment.**
La frontière chiffrée avec ton moteur (10 ans, données propres) :

| Config | Réussite challenge complet | Durée médiane | Coût par compte financé |
|---|---|---|---|
| **×1,0 (référence)** | **89,6 %** | 167 j | **603 €** |
| ×1,33 gardien fixe −2,5 % | 80,6 % | 112 j | 670 € |
| ×1,67 gardien fixe | 70,0 % | 77 j | 771 € |
| ×2,0 gardien fixe | 67,1 % | 67 j | 805 € |
| ×2,0 gardien élargi −5 % | **31,7 %** | 56 j | **1 704 €** |

La règle d'or découverte par le banc : si tu montes le risque, **garde le coupe-jour à −2,5 %** — l'élargir fait exploser les jours fatals (2 → 54 en 10 ans). Et « tout doubler » est une illusion : à peine plus rapide en temps espéré (on recommence sans arrêt), 3× plus cher.

**2. Une fois financé : passer à ×1,33 (gardien fixe).**
Revenu net espéré sur un 100 k$ : **~32 000 $/an au lieu de ~16 000 $**, pour une durée de vie de compte quasi égale. C'est LE réglage rendement le plus payant du banc. (×1,67 et au-delà : le compte meurt trop souvent, le revenu retombe.)

**3. La taille avant le risque : FTMO 2-Step Swing 200 k$.**
- Le **Swing** est la seule option du marché vérifiée compatible avec ton système (nuit + week-end + nouvelles permises au stade financé). Même prix que Standard. **Le 1-Step est un piège pour toi** : pas de Swing en 1-Step → fermeture obligatoire du week-end une fois financé, + frais non remboursable.
- 200 k$ = 1 080 €, **remboursé au 1er payout**. Un 200 k$ à risque normal rapporte autant que ×1,33 sur 100 k$, avec 9 points de réussite en plus.
- **Deux challenges 200 k$ en parallèle avec la même écurie : PERMIS** (plafond officiel 400 k$ par trader/stratégie, FAQ FTMO vérifiée le 20 août). Attention : mêmes trades = ils passent ou échouent ensemble — ce n'est pas une assurance, c'est un doubleur de capital (~85-95 % de chances d'avoir 2 comptes financés).
- Promo en cours vérifiée : 100 k$ à 439 € (au lieu de 540). FTMO fait des promos saisonnières — surveille avant d'acheter.

**4. Le scaling plan FTMO : le seul levier qui COMPOSE.**
Conditions vérifiées : +10 % net sur 4 mois + **2 payouts traités dans la fenêtre** (donc demande tes payouts, ne laisse pas dormir les profits — dès le 14e jour) → **+25 % de capital et split 90/10**, plafond 2 M$. Trajectoire par tranche de 100 k$ si les conditions sont tenues : ~195 k$ à 12 mois, ~381 k$ à 24 mois, cumul trader ~100 000 $ sur 2 ans. En partant de 2×200 k$ : ×4. Honnêteté : ta médiane (~10 % en 80 j) ratera le palier certains cycles — il se re-teste au suivant, rien n'est perdu.

**5. L'allocation « a×0,75 » : le petit plus gratuit.**
Or 0,75 % / Nasdaq 0,75 % / Pétrole 1,69 % / BTC Cassure 1,69 % / BTC EMA 1,13 % : +2,9 pts de CAGR sur 10 ans, +1,1 pt sur 2021-2026 (gagne sur les DEUX fenêtres = robuste), drawdown égal, réussite de challenge améliorée (93/89), et budget de risque total **réduit** (6 % vs 8 %). Gain modeste mais dans le bon sens partout. « Ne rien changer » reste défendable.

### 💰 CE QUE ÇA DONNE EN VRAIS DOLLARS (comptable)

| Scénario | 100 k$ financé | 200 k$ | 2×200 k$ + scaling 24 mois |
|---|---|---|---|
| Bas (+15 %/an) | ~900 $ US/mois | ~1 800 $/mois | croissant |
| Central (+25 %) | ~1 600 $/mois | ~3 200 $/mois | vers ~8 000 $+/mois en an 2 |
| Haut (+33 %) | ~2 100 $/mois | ~4 200 $/mois | davantage |

Les frais de challenge sont un détail (remboursables); le vrai coût des échecs est le temps sans compte. Le point mort du projet (~1 500-2 100 $/an) est couvert plusieurs fois dès le scénario bas — à condition d'avoir un compte financé. **Pas de 1 %/jour là-dedans : ce sont tes chiffres de backtest, et c'est déjà un vrai revenu.**

### ❌ CE QUI NE MARCHE PAS (vérifié, pour ne pas y perdre du temps ou de l'argent)

- **Monter le risque brut** : ×2 avec gardien élargi = 31,7 % de réussite, 5× moins de revenu une fois financé. Ton propre test « sans protections » l'avait déjà montré.
- **Le 1-Step FTMO** : piège (pas de Swing au stade financé).
- **FundingPips** : fermeture forcée du week-end sur TOUS les modèles Master depuis janvier 2026 + Striking System 1,2 %/idée vs tes 1,5-2 % — écarté tant que ça dure.
- **FTMO « Aggressive »** (cible 20 %) : plus lent pour toi, sans intérêt.
- **Supprimer l'or** (+41 % sur 10 ans en backtest !) : pur rétroviseur — depuis le filtre DXY, l'or contribue. **Supprimer le Nasdaq** : il lisse les challenges (85 → 75 % sans lui).
- **Monter BTC Cassure au-delà de ~1,7 %** : chaque test au-dessus casse la réussite FTMO.
- **Le mode « coast »** (réduire près de la cible) : effet nul — on ne meurt pas près de la cible, on meurt tôt.
- Déjà rejetés avant : pyramide 5, filtres calendrier, intermarché, corrélation dynamique.

### 📋 SÉQUENCE CONCRÈTE PROPOSÉE

1. Régler les restes du comité sur L5 (plafond vol inconditionnel au minimum) + ménage des dossiers L4 dans MT6.
2. (Optionnel) Appliquer l'allocation a×0,75 et/ou préparer l'input « ×1,33 gardien fixe » pour le mode financé — à backtester en MT5 avant.
3. Laisser la démo L5 rouler quelques semaines/mois — le vrai test hors échantillon — et utiliser le **Free Trial FTMO** (gratuit, répétable) pour valider la plomberie sur leurs serveurs (symboles, spreads, swaps réels).
4. Le jour venu : **FTMO 2-Step Swing**, la plus grosse taille que ton budget tolère (promos surveillées, frais remboursable), éventuellement 2 en parallèle sous le plafond de 400 k$.
5. Financé : ×1,33 gardien fixe, payouts aux ~6 semaines (2 par fenêtre de 4 mois) pour armer le scaling.
6. Budget mental : ~10-20 % de malchance incompressible par challenge — prévoir 1-2 échecs sans paniquer ni tout changer.

---

*Avertissement : tous ces chiffres sont des backtests (marge d'erreur ±5-10 points sur les probabilités) et des règles commerciales vérifiées le 20 août 2026 (elles changent — revérifier avant d'acheter). Rien n'est une promesse de rendement. Aucun fichier des robots n'a été modifié pendant l'analyse.*
