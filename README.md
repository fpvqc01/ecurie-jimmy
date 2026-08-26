# Écurie Jimmy I2+ — Système de trading algorithmique pour challenges FTMO

Paquet de partage pour revue de code / optimisation. Généré le 17 août 2026.
Environnement : MetaTrader 5 (MQL5) sur compte FTMO-Demo 100k, hedging.

## Vue d'ensemble

5 robots (Expert Advisors) sur 4 marchés, coordonnés par des protections partagées.
Performance simulée (5 ans, frais réels du compte relevés dans MT5) :
**~+21 %/an, Sharpe 1,39, pire journée -4,0 %, pire creux vs départ -6,1 %**
— toujours à l'intérieur des règles FTMO (perte journalière max 5 %, totale max 10 %).

| Robot | Marché/TF | Stratégie | Risque/trade |
|---|---|---|---|
| BTCUSD_EMA_I2+_H1 | BTCUSD H1 | Croisement EMA 20/50, achat seul, TP 2R + ré-entrée sur repli 0,25×ATR | 0,75 % |
| BTCUSD_Cassure_I2+_H4 | BTCUSD H4 | Cassure Donchian 55/20, achat seul, stop suiveur (jamais de TP) | 0,75 % |
| XAUUSD_Or_I2+_H4 | XAUUSD H4 | Repli fibonacci (20-80 % du swing 60 barres) + RSI<55 qui remonte, TP 1,5R + ré-entrée 0,25×ATR, breakeven à +1R | 3,0 % |
| US100_Nasdaq_I2+_H4 | US100 H4 | Même famille, fib 10-90 % du swing 40 barres, RSI<60, TP 1R + ré-entrée 0,5×ATR | 1,5 % |
| USOIL_Petrole_I2+_D1 | USOIL (données D1, TF du graphique indifférent) | Cassure Donchian 20/10 journalière, ACTIVE SEULEMENT déc→mai (saisonnalité raffineries pré-driving-season) | 0,75 % |

## Mécanismes transversaux (dans chaque EA)

1. **Coupe-circuits partagés** via GlobalVariables MT5 (`MACROBOT_BASE/HALT/DAY_<login>`) :
   -3,5 % de perte journalière (équité du compte) → chaque robot ferme ses positions, pause
   jusqu'au lendemain ; -8 % vs solde initial → fermeture générale + arrêt définitif (drapeau partagé).
2. **Plafond d'écurie** : max 2 positions simultanées tous robots confondus
   (`ComptePositionsEcurie()` compte les magics 20260815/17/18). Validé en backtest :
   améliore le Sharpe de 0,73→1,39 en filtrant les signaux excédentaires.
3. **Ré-entrée après take-profit** (robots EMA/or/Nasdaq) : détection `DEAL_REASON_TP` dans
   OnTradeTransaction → arme une ré-entrée si le prix retrace de N×ATR sous le prix de sortie,
   tant que le régime tient (EMA haussières / plancher du swing intact). Un stop touché annule.
4. **Filtre macro** (BTC seulement) : lit `MQL5\Files\macrobot_bias.txt` (écrit par le pipeline
   Python depuis les données BIS — posture Fed). Or/Nasdaq : même mécanisme via l'input BiasFromFile.
5. **Filtre d'annonces** : `macrobot_news.txt` (calendrier ForexFactory, annonces USD à fort
   impact, epochs UTC) → aucune nouvelle entrée ±30 min, et serrage des stops des positions
   ouvertes (breakeven si profit, sinon 0,5×ATR) pendant la fenêtre.
6. **Volatility targeting** (Moreira & Muir 2017) : `macrobot_vol.txt` (facteur 0,5-1,5 calculé
   chaque matin = 1 / vol relative moyenne des 4 marchés) multiplie le risque par trade.
7. **Notifications push** (SendNotification) sur chaque entrée/sortie/coupe-circuit.

## Pipeline Python (dossier pipeline_python/)

- `export_bias.py` : biais macro BIS (taux directeurs + CPI US) → GOLD/NAS/BTC=0|1.
  Règles dans `assets.py` (or: taux réels US qui ne montent pas ; nasdaq/btc: Fed pas en serrage).
- `export_news.py` : calendrier ForexFactory (XML, heures GMT!) + Fear&Greed crypto.
- `export_vol.py` : facteur de volatilité quotidien.
- Orchestré par `bot.cmd ftmo-bias`, tâches planifiées Windows (7h30 quotidien + horaire).

## Frais réels du compte (relevés dans les spécifications MT5, essentiels aux backtests)

| Marché | Swap long | Commission | Spread approx. |
|---|---|---|---|
| BTCUSD | **-30 %/an** (7j/7) | 0,0325 %/côté | ~0,015 % |
| XAUUSD | ~-7,8 %/an (triple mercredi) | ~0 | ~0,01 % |
| US100 | ~-7,8 %/an (triple vendredi) | 0 | ~0,006 % |
| USOIL | **+1,8 %/an (crédit!)** | 0 | ~0,09 % |

Le swap BTC est le frais dominant — toute stratégie qui tient longtemps ses positions BTC le paie cher.

## 🏆 CANDIDAT VALIDÉ EN ATTENTE D'IMPLÉMENTATION : pyramidage Turtle (19 août)

Seule idée en 70+ backtests à passer les 4 standards ET le test de survie ET le contrôle
d'exécution. Source : règles originales des Turtles (Dennis/Eckhardt) — ajouter des unités
à chaque +0,5 ATR en faveur du trade, stop suiveur commun, max 3-4 unités.
**Appliqué aux DEUX robots de cassure seulement** (BTC Cassure, Pétrole — ceux qui ont un
stop suiveur et aucun TP) :

| Config (portefeuille, gardien -3,5 % actif) | CAGR | Sharpe | Creux | Morts/challenge | Durée médiane |
|---|---|---|---|---|---|
| Référence actuelle | +17,6 % | 1,37 | -6,1 % | 14 % | 111 j |
| + pyramidage 2 unités | +24,3 % | 1,62 | -3,7 % | 14 % | 91 j |
| **+ pyramidage 3 unités** | **+29,2 %** | **1,74** | **-3,2 %** | **15 %** | **81 j** |
| + pyramidage 4 unités | +36,2 % | 1,90 | -2,8 % | 16 % | 80 j |

Validations : les 12 combinaisons de voisins (2/3/4 unités × 0,25/0,5/0,75/1 ATR) battent
toutes la référence ; les DEUX moitiés de période s'améliorent (+19,1/+40,0 vs +5,3/+31,4) ;
l'avantage survit à l'exécution réaliste (unités remplies au pire de niveau/ouverture +
glissement 0,15 % → +29,0 %). Pourquoi ce n'est pas le mirage du risque ×2 (rejeté, 42 % de
morts) : le pyramidage n'ajoute du risque QUE sur les trades déjà gagnants, financés par le
profit ouvert et couverts par le stop suiveur — les perdants gardent leur taille d'origine.
**Réserve honnête** : le gain vient d'un petit nombre de trades (les cassures font ~15-20
trades en 5 ans, le pétrole seulement 7) — c'est la littérature (un siècle de données AQR)
qui sert d'échantillon externe. **NE PAS appliquer aux robots fib/TP** (or, Nasdaq) : +64,6 %
apparent mais 18 déclenchements du gardien en 5 ans = artefact de moteur, pas une stratégie.

### ⚠️ Condition obligatoire découverte au stress du gardien (test_gardien_stress.py)

Le pyramidage **détruit le coussin de sécurité naturel** de l'écurie. Pire journée AVANT
intervention du gardien : **-4,02 % en config actuelle** (sous la limite FTMO -5 % même si
le gardien tombait en panne) contre **-5,62 % avec 3 unités**. Le pyramidage devient donc
dépendant d'une coupure parfaite — et un écart de prix (weekend BTC) qui la déborde de 50 %
donne -5,25 % = challenge mort.

**Correctif validé** : resserrer le gardien quotidien de -3,5 % à **-2,5 %** quand on
pyramide. Il rétablit 1,25 point de marge sous la limite FTMO même avec 50 % de débordement,
et — contre-intuitivement — **améliore aussi le rendement** (coupe les mauvaises journées
plus tôt) :

| Config | CAGR | Sharpe | Pire jour si gardien déborde 50 % | Marge sous -5 % |
|---|---|---|---|---|
| 3 unités, gardien -3,5 % | +29,2 % | 1,75 | -5,25 % | **-0,25 (brèche)** |
| 3 unités, gardien -3,0 % | +29,7 % | 1,82 | -4,50 % | +0,50 |
| **3 unités, gardien -2,5 %** | **+30,1 %** | **1,87** | **-3,75 %** | **+1,25** |
| 3 unités, gardien -2,0 % | +22,7 % | 1,63 | -3,00 % | +2,00 (trop serré) |

Le gardien à -2,0 % coupe trop de journées récupérables. **Configuration recommandée pour
l'implémentation : pyramidage 3 unités à +0,5 ATR sur les 2 cassures + gardien quotidien
à -2,5 %** (morts en challenge 15 %, durée médiane 82 j contre 111 j aujourd'hui).

## 🤖 GROKBOT — une lignée NEUVE, deux sens, sur le FX (26 août)

Les 30 générations de l'écurie partagent un angle mort : **elles sont 100 %
acheteuses** sur des actifs de risque. Aucune ne peut gagner quand le risque
baisse. GrokBot est bâti pour être ce robot-là — **code neuf, aucune reprise du
châssis L13 ou I2+**, son propre simulateur deux sens
(`backtests/banc_grokbot.py`). Rapport complet : **`RAPPORT_GROKBOT.md`**.

**La règle** : USDJPY, croisement **EMA 20/50** journalier dans les DEUX sens,
stop **2,0 × ATR** (= 1 R), TP **1,5 R**, risque **0,75 %**. C'est exactement le
candidat que ce README décrivait déjà comme « valide en réserve » sans jamais
l'implémenter — et un moteur écrit indépendamment le **réplique** :
**+14,5 R / PF 2,04** contre les +14,4 R / PF 1,91 documentés.

| Fenêtre | | CAGR | Creux | Sharpe | Réussite | Durée |
|---|---|---|---|---|---|---|
| 10 ans | écurie seule | +7,67 % | −10,7 % | 1,23 | 95,3 % | 600 j |
| 10 ans | + GrokBot1 (USDJPY) | **+10,07 %** | −11,2 % | 1,46 | 95,2 % | 533 j |
| 10 ans | **+ GrokBot2 (USDJPY+USDCHF)** | +9,47 % | **−8,9 %** | 1,40 | **98,1 %** | **516 j** |
| 2016-21 | + GrokBot2 | +11,57 % | −8,9 % | 1,44 | 95,4 % | 435 j |
| 2021-26 | + GrokBot2 | +7,39 % | −6,7 % | 1,38 | 100 % | 495 j |

**GrokBot1** rapporte le plus (+2,40 pts de CAGR) mais pousse le creux de
l'écurie à −11,2 %, **au-delà de la limite FTMO de −10 %**. **GrokBot2** — mêmes
règles, deuxième paire — rend 0,60 pt de CAGR et achète avec le creux ramené
**sous** la barre (−8,9 %) et +2,9 pts de réussite. **C'est la v2 qu'il faut
utiliser.** Fichiers : `robots/GrokBot1/` (magic 20268001) et `robots/GrokBot2/`
(20268002 / 20268003). Chaque robot est autonome mais partage les gardiens
`MACROBOT_*` et le plafond de positions avec l'écurie, et porte un **affichage
graphique** (panneau d'état + EMA/stop/TP sur les prix) inerte hors mode visuel.

### 🔬 La découverte de la manche : le contrôle d'exécution est un CRITÈRE

Le banc entre à la **clôture** de la bougie de signal ; un robot réel entre à
l'**ouverture suivante**. Rejoué sous cette contrainte :

| | R à la clôture | R à l'ouverture +1 |
|---|---|---|
| GrokBot1 | +14,5 | **+15,5** (survit) |
| Réentrée sur repli 0,50 ATR | +21,5 | **+9,0** (s'effondre) |

La réentrée sur repli était **le meilleur ajout du banc (+48 %) et un pur
artefact de moteur** — même piège que le « +64,6 % apparent » déjà au cimetière.
**Règle nouvelle du labo : tout mécanisme qui déclenche sur un niveau touché
intrabar doit être mesuré à l'ouverture suivante AVANT d'être retenu.**

## ⚠️ IMPORTANT pour l'optimisation : le cimetière des idées déjà testées

~60 backtests réalisés (Python, données Yahoo 5-10 ans, frais réels, validation par moitiés
de période et paramètres voisins). **Idées testées et REJETÉES — ne pas refaire :**

- Scalping M1/M5 (toutes variantes) : frais 12× l'avantage brut
- Support/résistance H4 avec entrée M5 : stops serrés = frais énormes en R
- Trading des nouvelles EIA pétrole (momentum et fade) : surprise absorbée avant réaction
- Inflation comme signal pétrole : le pétrole cause le CPI, pas l'inverse
- Saisonnalité pétrole SEULE (sans cassure) : krach 2020 en pleine "saison favorable"
- Argent/XAG (9 stratégies) : rien de robuste ; corrélé or avec 2× les frais
- US30 et US500 (7 stratégies chacun) : toujours inférieurs au Nasdaq
- IBS+RSI21 mean-reversion Nasdaq : PF 3,40→1,22 entre les moitiés de décennie (avantage mourant)
- Fib profond 0,618/0,886 : meilleurs trades mais 2× moins de gains (1 trade/an)
- EMA200 comme filtre global : ampute les totaux partout
- fib+RSI sur les cassures : zéro trade (conditions incompatibles)
- TP fixe + ré-entrée SUR LES CASSURES (testé 1R→6R) : ampute la queue grasse, le stop
  suiveur domine mathématiquement
- Runners 75/25 : redondants avec la ré-entrée (même métier, moins bien payé)
- 8 stratégies cumulées : corrélation intra-marché, vole les sièges du plafond
- Risque global ×2+ : brise les limites FTMO (validé par simulation)
- Plafond de 1 position : trop restrictif ; sans plafond : Sharpe s'effondre
- Filtre time-series momentum 12 mois / 6 mois (Moskowitz-Ooi-Pedersen) comme régime global
  (test_litterature.py) : CAGR 17,6→9,3 %, 1re moitié négative — même famille d'échec que
  l'EMA200 : ces filtres arrivent trop tard sur des robots qui suivent déjà la tendance
- Plafond par sous-jacent corrélé (interdire 2 positions BTC simultanées, règle Turtle) :
  17,6→16,6 %, Sharpe 1,37→1,30 — le plafond de 2 gère déjà la corrélation dans les faits
- Stat-arb « style Renaissance » (test_simons.py : z-score 1 j, renversement 5 j, paire
  or/argent) : tout négatif aux frais retail (-14 à -40 % sur 10 ans) — l'avantage par
  trade est plus petit que les frais ; ne marche qu'avec l'infrastructure d'un fonds
- Écurie en mode « news seulement » (test_ecurie_news.py : entrées limitées aux 0-2 j
  après NFP/CPI/FOMC) : CAGR 17,9→6,9 %, 1re moitié négative ; l'avantage vient des
  tendances/replis, pas des annonces — les news restent un garde-fou, pas un signal
- Runner 3R/24 h après TP (test_runner_3r.py, variante plafonnée du runner 75/25) :
  -1 à -2 pts de CAGR — la ré-entrée pleine grandeur sur repli domine toujours le bout
  de position au stop serré (3e rejet de la famille runner)
- Fermeture partielle 1/3 à +500 $ (test_partiel_500.py, voisins 1/2 et 250/1000 $) :
  CAGR 17,9→12,1 % contre pire journée -4,02→-2,83 % — assurance beaucoup trop chère ;
  leçon : un seuil en dollars vaut 0,17R pour l'or et 0,67R pour le BTC, les règles
  doivent rester en R/ATR
- Entrée immédiate à la sortie des annonces (test_entree_news.py, H1 2 ans, ~75 annonces) :
  MOMENTUM -41 R (la réaction est déjà dans le prix) ; FADE +27 R et le contrôle sur
  fausses dates (-27 R) prouve un vrai signal de sur-réaction — MAIS rejeté quand même :
  décroissance brutale (+23,3 R an 1 → +3,7 R an 2, signature IBS), historique testable
  limité à 2 ans, et spreads d'annonce réels 5-10× non modélisables. Le seul rejet avec
  un signal authentique — à retester si des données H1 de 10 ans deviennent disponibles
- **Robot GBPUSD (18 août, 3 scripts test_gbpusd*.py, frais réels des specs MT5 :
  swap -4,47 pts/j, commission 2,5 $/lot/côté, spread ~0,3 pip)** : criblage 10 ans →
  seule l'EMA 20/50 achat seul survit (+9,4 R, PF 2,17, moitiés +4,3/+5,1) mais 2,3 trades/an
  et paramètres voisins deux fois plus faibles ; la couche macro BIS par devise (scores
  carry/momentum taux/inflation, décalés de 2 mois) DÉTRUIT l'avantage partout (filtre
  EMA : tout négatif ; macro seul : -62,7 R/10 ans) ; en portefeuille sous plafond de 2 :
  CAGR 18,1→15,1 %, Sharpe 1,38→1,19, 1re moitié 5,3→1,4 % — le robot vole les sièges
  de l'or pour +1,2 point en 5 ans. REJETÉ (standards 1 et 4).

- **Canal de sortie rapide 7 j / 5 j, seul OU « réparé » par le réengagement
  (26 août, `backtests/banc_comite_points456.py`, point 5 du plan du comité)** : le canal
  7 j fait +4,88 %/an contre +7,67 % en référence, et le réengagement de Grok le
  remonte à peine (+4,95 %) — il ne répare rien. Le canal 5 j ne fait pas mieux
  (+5,43 %). Les durées médianes EXPLOSENT (896 j / 852 j / 818 j contre 600 j) :
  sortir plus tôt d'une tendance ne raccourcit pas le challenge, ça l'allonge,
  parce qu'on tronque la queue qui paie. L'hypothèse de Gemini (« le
  réengagement répare le canal rapide ») est INFIRMÉE. 2e rejet de la famille,
  question fermée.
- **Réengagement après une sortie gagnante sur les CASSURES (Grok nº 5, point 4
  du plan)** : NEUTRE, +0,04 pt de CAGR et −3 jours. Cause structurelle, et
  c'est la leçon : sur un châssis dont l'entrée est un plus-haut de canal, le
  déclencheur « sommet du trade précédent + K × ATR » est *au-dessus* du
  plus-haut 20 jours — la cassure tire donc toujours la première (17 fois sur 19
  le jour même). K = 0,25 / 0,50 / 1,00 / 1,50 donnent des résultats identiques :
  signature d'un mécanisme inerte, pas d'un plateau. **L'idée n'est pas morte,
  elle est mal logée** — à retester sur un châssis fib/repli ou EMA, jamais sur
  une cassure. Aucun robot ne la porte : le banc du 26 août l'a rejetée une
  seconde fois, sur un châssis deux sens et cette fois au contrôle d'exécution.
- **Coupe-temps conditionnel aux réglages 8 j/0,75 ATR, 8 j/1,50, 12 j/2,00,
  20 j/3,00** : nettement gagnants sur 10 ans (+8,1 à +8,9 %) et sur la 1re
  moitié (+10,9 à +11,9 %), mais perdants de 0,1 à 0,3 pt sur la 2e — standard 3
  non passé. Seul le réglage écrit par le comité AVANT tout backtest
  (12 j / 1,00 ATR) passe les deux moitiés : voir la section GrokBot1.

- **Réentrée sur repli après un TP, sur un châssis FX deux sens (26 août,
  `backtests/banc_grokbot.py`)** : +21,5 R contre +14,5 pour la base... à la
  clôture. En exécution réelle (entrée à l'ouverture suivante) : **+9,0 R, soit
  MOINS que la base**. Artefact de moteur pur. Le mécanisme déclenchait sur un
  niveau touché *intrabar* et le simulateur entrait au même instant — un robot ne
  peut pas. Toute la famille (0,25 / 0,50 / 1,00 ATR) tombe pareil.
- **Point mort (breakeven) à +0,75 / +1,00 / +1,25 R sur GrokBot** : −3 à −12 R.
  Il coupe la queue qui paie. 4e confirmation de cette famille.
- **Stop à 3,0 ATR sur GrokBot** — *le rejet le plus instructif du banc* : en
  solo il a le meilleur PF mesuré (3,21) et les moitiés les mieux équilibrées
  (+9,0 / +7,5 contre +4,5 / +10,5). En portefeuille sous le plafond de 2 :
  **+7,81 % contre +10,07 %** — il prend trop peu de trades (22 en 10 ans) pour
  mériter un siège. Rappel que le standard 4 n'est pas une formalité.
- **Plafond interne d'UNE position pour GrokBot** (anti-concentration USD, ses
  deux paires étant des jambes dollar) : −0,68 pt de CAGR et **rien** en échange
  — creux et réussite rigoureusement inchangés. Le plafond de 2 de l'écurie gère
  déjà la corrélation : **même conclusion que le plafond par sous-jacent testé le
  21 août**, atteinte par un chemin indépendant.
- **AUDUSD, AUDJPY, EURUSD, GBPUSD en EMA 20/50 deux sens** : l'AUDUSD affiche le
  meilleur chiffre brut du criblage (+23,5 R) mais c'est un **pic** — voisin
  EMA 30/60 à 0,0 R, stop 3,0 ATR négatif. Les trois autres échouent sur une
  moitié. Seuls l'USDJPY (12 voisins sur 13) et l'USDCHF tiennent.
- **TSMOM (momentum 126 / 252 jours) comme stratégie deux sens sur le FX** :
  +0,6 à +3,5 R sur 10 ans, 1,6 à 2,4 trades/an. Trop lent et trop faible pour un
  siège. Le TSMOM reste utile comme *littérature*, pas comme signal d'entrée.

**Standards de validation utilisés** (à conserver pour toute proposition) :
1. principe économique externe (pas d'idée née de l'optimisation elle-même),
2. amélioration nette avec les frais réels,
3. stabilité sur les DEUX moitiés de période ET sur les paramètres voisins,
4. amélioration au niveau du PORTEFEUILLE sous le plafond de 2 (pas juste en solo).

## Territoire forex : exploré (18 août) — GBPUSD fermé, USDJPY sur le banc d'essai

**GBPUSD : rejeté** (voir cimetière et backtests/test_gbpusd*.py) : les scores macro BIS,
même correctement décalés du retard de publication, n'ont aucun pouvoir directionnel au
quotidien, et le meilleur candidat technique est trop lent (2,3 trades/an) pour justifier
un siège sous le plafond de 2 positions. Même conclusion attendue pour l'EUR/USD.

**USDJPY : candidat VALIDE en réserve** (backtests/test_usdjpy*.py) — la paire des cycles
de politique monétaire Fed/BoJ. EMA 20/50 dans les DEUX sens (premier candidat vendeur du
système), TP 1,5R, stop 2×ATR, risque 0,75 % : +14,4 R/10 ans, PF 1,91, moitiés +5,4/+9,0,
plateau robuste (voisins 10/40→30/60 tous positifs, TP 1R→3R tous positifs, ~4 trades/an).
Le filtre macro BIS n'ajoute rien ici non plus (qualité par trade meilleure, total amputé).
En portefeuille sous plafond de 2 : CAGR identique (+18,1 %), Sharpe 1,38→1,39, les deux
moitiés ET les 12 derniers mois légèrement meilleurs — il ne vole pas de sièges. Verdict :
n'augmente pas le rendement, mais diversifie (seul robot capable de gagner quand les actifs
risqués baissent). Décision d'implémentation laissée ouverte ; il faudrait d'abord confirmer
les swaps réels FTMO (specs MT5 USDJPY : swap achat probablement positif — carry — mais
la majoration du courtier peut l'annuler ; hypothèses du test : +0,005 %/j achat, -0,010 %/j vente).

Bonne revue! — Jimmy (et Claude, son partenaire de laboratoire)

## Structure du depot (mise a jour)

- `robots/` — les 5 EA MQL5 + l'indicateur Canal_Donchian
- `templates/` — les modeles de graphiques MT5 (robot + indicateurs integres, un par marche)
- `pipeline_python/` — scripts de donnees (bias/news/vol) + package bot/ + config.yaml.
  Lancer avec Python 3.12 (pandas, requests). `bot.cmd ftmo-bias` orchestre le tout.
- `backtests/` — TOUT L'OUTILLAGE DE VALIDATION. Point d'entree : `optimisation_finale.py`
  (moteur de simulation du portefeuille : classes Sleeve/Fib/Donch/EmaBTC, frais reels,
  plafond de positions, TP/reentree). Les autres scripts l'importent via exec() et testent
  chaque question (concentration, vol targeting, temps de challenge, etc.).
  Donnees : Yahoo Finance (gratuit, aucune cle requise).
- `robots/GrokBot1/`, `robots/GrokBot2/` — la lignee GrokBot : code NEUF, deux
  sens, FX. Voir `RAPPORT_GROKBOT.md`.
- `backtests/banc_grokbot.py` — son banc (criblage 6 paires x 9 regles, plateau,
  controle d'execution, portefeuille sous plafond de 2) ;
  `backtests/build_grokbot.py` + `grokbot_modele.mq5` generent les versions.
- `backtests/banc_comite_points456.py` — le banc des points 4/5/6 du plan du
  comite externe. Voir `RAPPORT_COMITE_POINTS456.md`.
- `CONVERSATION_Ecurie_Jimmy.md` — l'historique complet du raisonnement (4 jours).

Pour evaluer une nouvelle idee : l'implementer comme variante dans le moteur, la faire
passer par les 4 standards (voir plus haut), et comparer a la config actuelle.
