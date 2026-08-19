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
- `CONVERSATION_Ecurie_Jimmy.md` — l'historique complet du raisonnement (4 jours).

Pour evaluer une nouvelle idee : l'implementer comme variante dans le moteur, la faire
passer par les 4 standards (voir plus haut), et comparer a la config actuelle.
