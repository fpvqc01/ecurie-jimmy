> # ⚠️ REJOUÉ LE 21 AOÛT AU SOIR — deux résultats sur trois ont changé
>
> Ce rapport a été écrit avant la réparation des données, et il déclarait
> lui-même que `d10h1_btc.csv` était introuvable (BTC tournait en H4).
> Le fichier existe maintenant et il est réparé. Reprise :
> `backtests/reprise_rapport_crises.py`.
>
> **CE QUI TIENT** — la concentration : BTC Cassure fait **74,9 %** du
> rendement (annoncé 75,2 %) et **9 des 10 pires journées**, souvent 100 %
> de la perte du jour. Or + Nasdaq + BTC EMA = 10 % du rendement.
>
> **CE QUI S'AMÉLIORE** — les journées mortelles étaient exagérées, comme le
> rapport le soupçonnait : pire journée **−5,42 %** (et non −8,63 %),
> **1 journée** sous −5 % (et non 3), **7** sous −3 % (et non 27). Effet du
> gardien resserré à −1,75 %, des données réparées et de la cadence H1.
>
> **CE QUI NE TIENT PLUS** — le filtre marché baissier n'est pas le repas
> gratuit annoncé. Mesuré sur L8 + R13, données réparées :
>
> | seuil | 10 ans | 2021-2026 |
> |---|---|---|
> | aucun | +28,4 % / 89 % / 205 j | +19,1 % / 84 % / **228 j** |
> | −12,5 % | +23,8 % / 92 % / 222 j | +14,5 % / 82 % / **336 j** |
> | −20 % | +26,6 % / **95 %** / 223 j | +15,0 % / **89 %** / **337 j** |
>
> Le rapport annonçait « CAGR quasi inchangé (−0,7 à −2,0 pt) ». C'est en
> réalité **−1,8 à −6,3 pts sur 10 ans et −4,1 à −9,2 pts sur le récent**,
> et la durée sur la fenêtre récente **explose de +74 à +109 jours**.
> Le seuil −20 % reste le meilleur taux de réussite jamais mesuré
> (95 % / 89 %) — mais c'est un choix « lent et sûr », pas un gain gratuit.

# L'ÉCURIE EN CRISE ET HORS CRISE — 21 août 2026

Question posée : si on retire du backtest les pires journées des crises économiques, que vaut l'écurie
le reste du temps ?

Réponse courte : **hors crise elle est bien meilleure — et c'est précisément hors crise que se trouvent
toutes ses journées mortelles.** Les crises économiques ne sont pas le danger de cette écurie.

Mesuré sur L6 (l'écurie en service), données assainies, moteur corrigé, 2015-2026.

---

## 1. Crise contre calme

Le régime de crise est défini sur les données, pas sur les souvenirs : Nasdaq à plus de 10 % sous son
plus haut glissant. Aucune journée n'est supprimée — les robots ont bel et bien traversé les crises, on
regarde seulement où le P&L est né.

| régime | jours | % du temps | annualisé | Sharpe | pire creux |
|---|---|---|---|---|---|
| tout (référence) | 4 018 | 100 % | +25,6 % | 1,31 | −19,7 % |
| **crise** (NQ < −10 %) | 826 | 20,6 % | **+6,1 %** | **0,48** | −21,2 % |
| **calme** (le reste) | 3 192 | 79,4 % | **+31,2 %** | **1,47** | −16,1 % |

*« annualisé » = le rendement si toute l'année ressemblait à ce régime.*

**Le résultat tient avec quatre définitions différentes de la crise :**

| définition | % du temps | crise : annualisé / Sharpe | calme : annualisé / Sharpe |
|---|---|---|---|
| Nasdaq < −10 % du sommet | 20,6 % | +6,1 % / 0,48 | +31,2 % / 1,47 |
| Nasdaq < −15 % du sommet | 12,9 % | +6,0 % / 0,43 | +28,8 % / 1,42 |
| volatilité : décile haut | 10,0 % | +9,5 % / 0,95 | +27,5 % / 1,34 |
| volatilité : quintile haut | 19,9 % | +1,8 % / 0,21 | +32,3 % / 1,50 |

Quelle que soit la définition : **en régime calme, +28 à +32 %/an avec un Sharpe de 1,34 à 1,50. En
régime de crise, +2 à +9 %/an avec un Sharpe de 0,21 à 0,95.**

### Épisode par épisode

| épisode | durée | creux Nasdaq | écurie |
|---|---|---|---|
| févr. 2016 (pétrole / Chine) | 28 j | −16,5 % | −1,1 % |
| nov. 2018 | 16 j | −15,1 % | −0,2 % |
| déc. 2018 → févr. 2019 | 62 j | −23,4 % | −0,4 % |
| **mars-avr. 2020 (COVID)** | 42 j | **−31,2 %** | **−0,1 %** |
| sept. 2020 | 11 j | −13,3 % | −0,5 % |
| janv. 2022 | 12 j | −15,0 % | +2,5 % |
| févr.-mars 2022 | 46 j | −21,0 % | +2,4 % |
| **avr. 2022 → juin 2023 (marché baissier)** | **435 j** | **−35,7 %** | **+7,0 %** |
| sept.-oct. 2023 | 15 j | −12,2 % | −1,4 % |
| oct.-nov. 2023 | 16 j | −14,5 % | +3,7 % |
| août 2024 (yen) | 11 j | −14,1 % | +0,2 % |
| mars 2025 | 14 j | −13,1 % | +0,6 % |
| mars-mai 2025 | 37 j | −25,2 % | +2,2 % |

**L'écurie ne perd pas dans les crises — elle piétine.** Le COVID : −0,1 % pendant que le Nasdaq perdait
31 %. Le marché baissier de 2022-23 : +7,0 % sur 14 mois. C'est une protection réelle, et c'est ce que
le README revendique. Mais ce n'est pas une source de rendement : sur 20,6 % du temps, l'écurie ne fait
que 1,3 % de son gain total.

**Ce que ça veut dire concrètement : si tu commences un challenge FTMO pendant une crise, tu ne perdras
probablement pas ton compte — mais tu n'atteindras pas +10 % non plus.** Le compteur tourne à vide.

---

## 2. Le retournement : les journées mortelles sont dans le calme

C'est le résultat que je n'attendais pas.

| date | P&L écurie | régime | Nasdaq ce jour-là |
|---|---|---|---|
| **2017-01-05** | **−8,63 %** | calme | au sommet |
| 2016-09-11 | −5,74 % | calme | −3,1 % |
| 2020-05-10 | −5,45 % | calme | −4,9 % |
| 2019-02-24 | −4,57 % | calme | −7,2 % |
| 2015-10-18 | −4,24 % | calme | au sommet |
| 2023-01-18 | −4,10 % | CRISE | −31,2 % |
| 2024-03-05 | −3,99 % | calme | −2,0 % |
| 2019-04-04 | −3,81 % | calme | −1,8 % |
| 2017-12-08 | −3,53 % | calme | −1,2 % |
| 2016-11-03 | −3,51 % | calme | −4,7 % |

**11 des 12 pires journées tombent en régime calme**, alors que le calme représente 79 % du temps — donc
la crise est même *sous*-représentée dans la queue gauche. Et il y a **3 journées sous −5 %**, c'est-à-dire
trois comptes FTMO morts sur la période, plus 27 journées sous −3 %.

### Et le coupable est toujours le même

| date | total | Or | Nasdaq | Pétrole | **BTC Cassure** | BTC EMA |
|---|---|---|---|---|---|---|
| 2017-01-05 | −8,63 % | 0,00 | +0,14 | 0,00 | **−8,77** | 0,00 |
| 2016-09-11 | −5,74 % | 0,00 | 0,00 | 0,00 | **−4,58** | −1,16 |
| 2020-05-10 | −5,45 % | 0,00 | 0,00 | 0,00 | **−5,45** | 0,00 |
| 2019-02-24 | −4,57 % | 0,00 | +0,09 | 0,00 | **−4,67** | 0,00 |
| 2015-10-18 | −4,24 % | +0,01 | 0,00 | 0,00 | **−4,25** | 0,00 |

**Les 10 pires journées de l'écurie sont, à chaque fois, BTC Cassure.** Ce sont des chocs propres au
bitcoin, pas des crises économiques : BTC a fait −9,9 % le 5 janvier 2017, −8,6 % le 10 mai 2020, −9,1 %
le 24 février 2019 — trois journées où le Nasdaq n'avait rien de particulier.

Le gardien quotidien ne peut rien : quand une seule barre porte −8 %, il se déclenche **après**.

---

## 3. L'écurie n'est pas diversifiée — c'est un robot avec quatre passagers

Contribution au P&L total sur 10 ans :

| robot | cumul | part du total |
|---|---|---|
| **BTC Cassure** | **+202,6 %** | **75,2 %** |
| Pétrole | +54,6 % | 20,3 % |
| BTC EMA | +4,7 % | 1,7 % |
| Or | +4,6 % | 1,7 % |
| Nasdaq | +2,9 % | 1,1 % |

**BTC Cassure fait les trois quarts du rendement et la totalité des journées mortelles.** Pétrole fait le
cinquième restant. L'or et le Nasdaq — les deux manches décrites dans le README comme « le meilleur moteur
testé (PF ~2 sur 10 ans) » et « le meilleur terrain d'achat de replis » — pèsent **2,8 % à eux deux**.

En régime de crise, c'est encore plus net : BTC Cassure fait +21,7 % pendant que le Nasdaq perd −3,9 %,
le Pétrole −2,3 % et BTC EMA −1,2 %. **Les trois autres manches sont un coût net en crise.**

Le récit du README — « le champion tourne chaque année (or → BTC → or → pétrole) », « la diversification
est la seule protection contre l'inconnu » — n'est pas ce que montrent ces chiffres. Il faut soit
remonter l'allocation de l'or et du Nasdaq, soit accepter qu'ils ne servent qu'à occuper des sièges sous
le plafond de 2 positions.

*(Réserve importante : l'allocation L6 donne 1,69 % de risque à BTC Cassure contre 0,75 % à l'or et au
Nasdaq. Une partie de l'écart vient de là — mais 75 % contre 1,7 % ne s'explique pas par un facteur 2,3
d'allocation.)*

---

## 4. « Enlever les pires journées » : pourquoi ça ne veut rien dire

| série | annualisé | Sharpe | creux |
|---|---|---|---|
| complète | +25,6 % | 1,31 | −19,7 % |
| sans les 5 pires journées | +29,0 % | 1,48 | −19,7 % |
| sans les 10 pires | +31,4 % | 1,59 | −19,7 % |
| sans les 20 pires | +35,7 % | 1,80 | −19,7 % |
| sans les 50 pires | +47,2 % | 2,33 | −17,4 % |
| sans les 5 **meilleures** | +18,8 % | 1,13 | −19,7 % |
| sans les 10 meilleures | +14,6 % | 0,96 | −20,3 % |
| sans les 20 meilleures | +9,2 % | 0,68 | −20,3 % |
| sans les 50 meilleures | **−1,4 %** | −0,04 | −41,2 % |

Les deux colonnes bougent d'autant. Le rendement et le risque vivent dans **la même poignée de journées**,
et ce sont les mêmes marchés qui les produisent. Retirer 50 journées sur 4 018 fait passer l'écurie de
+25,6 % à +47,2 % ou à −1,4 % selon le côté qu'on choisit — c'est un choix d'après-coup, pas une mesure.

C'est aussi pour ça que la question « et sans les crises ? » ne se traite pas en supprimant des journées :
la segmentation du §1 est la bonne façon de la poser, parce qu'elle garde les 4 018 journées et se contente
de dire où le P&L est né.

---

## 5. Ce qui en sort quand même : un candidat sérieux

Si on n'ouvre **aucune nouvelle position** tant que le Nasdaq est à plus de X % sous son sommet (décidé
avec les données de la veille, donc implémentable dans le robot) :

| seuil | 10 ans : ann. / Sharpe / creux / réussite | 2021-26 : ann. / Sharpe / creux / réussite |
|---|---|---|
| aucun (L6) | +25,6 % / 1,31 / −19,7 % / **70 %** | +16,1 % / 0,94 / −19,7 % / **69 %** |
| −7,5 % | +19,0 % / 1,16 / −15,9 % / 67 % | +7,9 % / 0,64 / −12,6 % / 45 % |
| −10 % | +19,8 % / 1,14 / −17,5 % / 45 % | +6,0 % / 0,50 / −14,3 % / 29 % |
| **−12,5 %** | +24,9 % / 1,29 / −18,4 % / **79 %** | +16,5 % / 1,03 / −13,0 % / **83 %** |
| **−15 %** | +24,6 % / 1,31 / −17,2 % / **80 %** | +14,1 % / 0,93 / −12,9 % / **85 %** |
| **−17,5 %** | +24,9 % / 1,32 / −17,7 % / **81 %** | +14,7 % / 0,97 / −13,0 % / **86 %** |
| **−20 %** | +24,6 % / 1,31 / −17,0 % / **81 %** | +14,1 % / 0,92 / −13,0 % / **86 %** |
| −25 % | +23,4 % / 1,26 / −18,0 % / 73 % | +12,2 % / 0,81 / −15,4 % / 76 % |

**Il y a un vrai plateau entre −12,5 % et −20 %**, sur les deux fenêtres, à CAGR quasi inchangé
(−0,7 à −2,0 pt), avec un creux amélioré de 2 à 7 points et une réussite en hausse de **10 points sur
10 ans et 16 points sur le récent**. Ça passe ton standard n° 3 (les voisins gagnent aussi) et ton
standard n° 4 (amélioration au niveau du portefeuille sous le plafond de 2).

Le principe économique est défendable et externe à l'optimisation : ne pas ouvrir de nouvelle position
quand le complexe risqué est en marché baissier avéré. La falaise en dessous de −12,5 % le confirme plutôt
qu'elle ne l'infirme — à −7,5 % et −10 % on bloque des corrections ordinaires qui se reprennent, c'est-à-dire
exactement le terrain où l'écurie gagne.

**À traiter comme un candidat, pas comme un résultat.** L'erreur-type sur la réussite est de ±8 à ±11 points ;
+10 points sur 10 ans font environ 1,2 écart-type, +16 sur le récent environ 1,5. C'est cohérent sur les
deux fenêtres et sur cinq seuils voisins, ce qui vaut mieux qu'un chiffre isolé — mais ce n'est pas une
preuve. Il faudrait le passer au banc complet, avec BTC Cassure à sa vraie cadence.

---

## Réserves

- **BTC Cassure tourne en H4 et non en H1** (`d10h1_btc.csv` toujours introuvable). Le gardien quotidien
  est donc évalué toutes les 4 heures au lieu de toutes les heures — **les pires journées du §2 sont
  vraisemblablement exagérées** : le robot déployé vérifie à chaque tick. Mais la *concentration* du §3
  ne dépend pas de la cadence, et le fait que les journées mortelles soient des chocs BTC en marché calme
  non plus.
- **Les gaps de week-end restent invisibles** dans ces données. Les creux de crise sont donc optimistes,
  ce qui va dans le sens de « les crises sont moins dangereuses qu'elles n'en ont l'air » — à corriger.
- **Le simulateur FTMO garde ses défauts** (jugement sur clôtures journalières, base = équité courante).
  Les réussites sont des bornes supérieures.
- Le régime de crise est défini sur le Nasdaq. Une crise obligataire ou une crise propre au bitcoin
  n'apparaît pas comme « crise » dans cette découpe — c'est précisément ce qui rend le §2 lisible.

---

## Ce que je retiens

1. **Hors crise : +31,2 %/an, Sharpe 1,47, creux −16,1 %.** C'est là que vit l'avantage de l'écurie.
2. **En crise : +6,1 %/an, Sharpe 0,48.** Elle protège le capital, elle ne le fait pas croître. Un
   challenge démarré en crise s'enlise plutôt qu'il ne meurt.
3. **Le danger n'est pas la crise économique — c'est BTC un mardi ordinaire.** Onze des douze pires
   journées sont en marché calme, et les dix pires sont toutes BTC Cassure.
4. **L'écurie repose à 75 % sur un seul robot.** L'or et le Nasdaq pèsent 2,8 % à eux deux. La question
   à trancher n'est pas « comment se comporte-t-elle hors crise » mais « pourquoi porte-t-elle trois
   robots qui ne rapportent rien et un qui peut tuer le compte en une barre ».

---

*Scripts fournis : `analyse_crises.py` (segmentation, retrait naïf, règle applicable),
`verif_crises.py` (robustesse des définitions), `verif_voisins.py` (plateau du filtre, pires journées),
`verif_pires.py` (attribution par manche). Tous à lancer depuis `backtests/`.*
