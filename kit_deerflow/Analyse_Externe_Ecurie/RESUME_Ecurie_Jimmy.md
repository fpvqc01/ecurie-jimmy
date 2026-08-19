# Écurie Jimmy — Résumé complet du projet
### 4 jours de laboratoire, ~60 backtests, 5 robots — 14-17 août 2026

---

## 🏆 Le système final (Écurie I2+)

**Performance simulée (5 ans, frais réels du compte FTMO) : ~+21 %/an, Sharpe 1,39,
pire journée -4,0 %, pire creux -6,1 % — toujours dans les règles FTMO.
Objectif de challenge (+10 %) : ~108 jours médians. Compte financé : ~5,5 mois.**

| Robot | Stratégie | Risque | Pourquoi elle gagne |
|---|---|---|---|
| **XAUUSD Or H4** | Repli fib (20-80 % du swing) + RSI<55 qui remonte, TP 1,5R + ré-entrée 0,25×ATR, breakeven +1R | 3 % | Le meilleur moteur testé (PF ~2 sur 10 ans) — l'or respecte ses retracements |
| **US100 Nasdaq H4** | Même famille, fib 10-90 %, RSI<60, TP 1R + ré-entrée 0,5×ATR | 1,5 % | L'indice le plus nerveux = meilleur terrain d'achat de replis |
| **BTCUSD EMA H1** | Croisement EMA 20/50 achat seul, TP 2R + ré-entrée 0,25×ATR | 0,75 % | Facture les vagues du BTC par versements |
| **BTCUSD Cassure H4** | Donchian 55/20, stop suiveur, JAMAIS de take-profit | 0,75 % | Chevauche les monstres (PF 6,96) — toute cible ampute la queue grasse |
| **USOIL Pétrole D1** | Donchian 20/10 journalier, actif SEULEMENT déc→mai | 0,75 % | Cassure + saisonnalité des raffineries (+ swap positif unique) |

**Les 4 couches systémiques :**
1. **Plafond d'écurie** : max 2 positions simultanées (Sharpe 0,73 → 1,39 — filtre naturel des signaux faibles)
2. **Volatility targeting** (Moreira & Muir 2017) : risque ×0,5-1,5 selon la vol des marchés (+2 pts/an ET pire journée réduite)
3. **Coupe-circuits partagés** : -3,5 %/jour et -8 % total (sous les limites FTMO de 5/10 %), chaque robot protège tout le compte
4. **Pipeline de données automatique** : biais macro BIS (quotidien), calendrier économique + Fear&Greed (horaire),
   blocage des entrées ±30 min des annonces USD + serrage des stops

---

## ⚰️ Le cimetière — tout ce qui a été testé et rejeté (ne pas refaire!)

| Famille | Idées testées | Verdict |
|---|---|---|
| **Vitesse** | Scalping M1 (3 stratégies), scalping M5, S/R H4 entrée M5 | Frais jusqu'à 12× l'avantage brut ; -17 à -42 % en 7 jours |
| **Nouvelles** | Momentum et fade des annonces EIA, inflation comme signal pétrole | L'info publique est dans les prix avant qu'on réagisse ; le pétrole cause le CPI, pas l'inverse |
| **Marchés** | Argent (9 stratégies), US30 (7), US500 (7) | Toujours inférieurs aux titulaires ; corrélés sans rien apporter |
| **Mécanismes** | Runners 75/25, TP sur cassures (1R→6R), fib profond 618/886, EMA200 global, fib+RSI sur cassures | Redondance, amputation des gros gains, ou zéro trade |
| **Taille/risque** | 8 stratégies cumulées, risque ×2+, or seul, plafond 1, sans plafond | Corrélation, rupture des règles FTMO, ou concentration dangereuse |
| **Recrues** | IBS+RSI21 Nasdaq (mean reversion documenté) | Brillant au 1er test, avantage mourant sur 10 ans (PF 3,40 → 1,22 entre moitiés) |
| **Saisonnalité seule** | Long pétrole déc-mai sans filtre | Le krach 2020 tombe en pleine « saison favorable » (DD -158 %) |

---

## 💎 Les 7 idées fondamentales (la méthode)

1. **Les frais sont la première stratégie.** Swap, spread, commission déterminent ce qui peut exister :
   BTC à -30 %/an de swap n'autorise que les mouvements amples ; pétrole à swap positif récompense la patience.
   Toujours backtester avec les frais réels de SON compte (relevés dans les spécifications MT5).
2. **Stratégie et marché doivent partager le même tempérament.** Les replis se récoltent (TP + ré-entrée),
   les cassures se chevauchent (stop suiveur). Le Nasdaq nerveux nourrit les replis, le Dow lourd les affame.
3. **Un plateau, pas un pic.** Un réglage n'est fiable que si ses voisins gagnent aussi ET que les deux
   moitiés de la décennie confirment. Le meilleur chiffre d'un tableau d'optimisation est du bruit mémorisé.
4. **Une amélioration doit apporter un métier absent.** Recrues corrélées = sièges volés ;
   mécanismes redondants = deux salaires pour une job. 5 robots choisis > 8 robots empilés.
5. **La diversification est la seule protection contre l'inconnu.** Le champion tourne chaque année
   (or → BTC → or → pétrole). Résultat : +0,7 % en 2022 quand tout brûlait, jamais d'année perdante.
6. **La frontière du risque est un mur, pas une pente.** Cartographiée au cran près : la config actuelle
   est le maximum qui respecte les règles FTMO. Au-delà : rupture, peu importe la taille du compte
   (les limites sont en %).
7. **Le passé se teste, l'avenir se vit.** Après ~60 backtests, tout test de plus mémorise l'histoire
   au lieu de préparer demain. Le vrai juge : le walk-forward vivant (démo), puis Free Trial, puis challenge.

---

## 📅 Le plan

1. **Maintenant** : 3-4 semaines de démo sans rien toucher (en cours — 1er trade réel : +734 $ le 17 août)
2. **Ensuite** : analyse des trades réels vs simulation → décision
3. **Puis** : Free Trial FTMO (gratuit, ~2 semaines) → challenge 100k ou 200k, compte **Swing**
   (indispensable : permet fin de semaine + annonces au stade financé)
4. **Cible** : compte financé printemps 2027 (médiane), payouts 80 % (90 % après scaling)

*Résumé généré le 17 août 2026 — Jimmy & Claude*
