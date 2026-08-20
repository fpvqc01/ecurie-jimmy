# RAPPORT DU COMITÉ DE VÉRIFICATION — Écurie L4.3

**Date : 20 août 2026 · Cible : les 5 robots L4.3 + variante SansChallenge (déployés sur C:\MT6) · 10 experts IA indépendants**

---

## VERDICT GLOBAL EN 5 LIGNES

L'écurie est **bien construite pour un projet amateur** — plusieurs experts l'ont souligné spontanément : pas de look-ahead dans les canaux, frais réels soignés, stop serveur sur chaque trade, protections globales du compte, déploiement identique bit pour bit aux sources. **MAIS** le comité a trouvé **2 vrais bogues de code**, **1 trou de portefeuille sérieux**, et **3 raisons de croire que le rendement réel sera plus bas que le backtest**. Rien n'exige d'arrêter la démo; tout exige d'être réglé **avant de payer un challenge**.

**Attente réaliste selon le comité : plutôt +15 à +20 %/an que +27-47 %, avec ~1 chance sur 5 de rater un challenge par pure malchance même si tout est correct.**

---

## 🔴 À CORRIGER AVANT TOUT CHALLENGE PAYANT

### 1. Le coupe-circuit global laisse 3 robots figés avec leurs positions ouvertes
*Trouvé indépendamment par 3 experts (code, risque, red team).*
Quand la perte totale atteint −8 %, le robot qui la détecte ferme SES positions et lève le drapeau HALT. Mais les robots **or, Nasdaq et BTC EMA**, en voyant le drapeau, se figent **sans fermer** (`XAUUSD_Or_L43_H4.mq5:337-338`, `US100_Nasdaq_L43_H4.mq5:~304`, `BTCUSD_EMA_L43_D1.mq5:292-293`). Et la fermeture d'urgence des 2 autres n'est tentée **qu'une seule fois** (`BTCUSD_Cassure_L43_H1.mq5:270-271` — si elle échoue, jamais de 2e essai). Dans un krach, le −8 % du gardien peut glisser jusqu'au −10 % fatal FTMO.
**Correctif : retenter la fermeture à chaque tick dans la branche HALT, dans les 5 robots.**
*Nuance : si c'est or/Nasdaq/BTC-EMA qui déclenche (magic partagé 20261115), la fermeture emporte les trois — le trou existe quand BTC-Cassure ou pétrole déclenche en premier.*

### 2. Rien n'empêche les DEUX robots BTC d'occuper les 2 places de l'écurie en même temps
*Analyste de portefeuille.* Le plafond de corrélation couvre or/indices mais **exempte le BTC**. Deux piles sur le même marché (corrélation 1,00) : pire cas mesuré sur tes propres données = **−5,5 % en un jour** (jusqu'à −8,25 % avec le facteur volatilité ×1,5) contre une limite FTMO de −5 %. Et le scénario réaliste qui déclenche ça — **gap BTC de fin de semaine** (12 mars 2020 : −39,5 % en un jour, c'est dans tes données) — est précisément celui où le gardien ne peut pas agir.
**Correctif : règle « un seul robot BTC en position à la fois » (même mécanique que or/Nasdaq).**

### 3. Bogue : le facteur de volatilité est mort dans le robot BTC EMA
*Vérificateur de code.* `LireFacteurVol()` est définie (`BTCUSD_EMA_L43_D1.mq5:447`) mais **jamais appelée**. Quand le pipeline dit « réduis les mises de moitié », les 4 autres obéissent, le BTC EMA reste à plein risque. L'input `FacteurVolActif` est un placebo.
**Correctif : ajouter l'appel dans OnTimer, comme les 4 autres robots.**

### 4. Le facteur volatilité peut AMPLIFIER le risque ×1,5 sans limite de fraîcheur
*Red team + portefeuille.* Un `macrobot_vol.txt` gelé à FACTEUR=1.5 (écrit un matin calme, pipeline mort ensuite) **multiplie le risque de chaque trade par 1,5 pendant la crise suivante**, en silence — aucun test d'âge du fichier (contrairement au filtre DXY qui a sa péremption de 7 jours).
**Correctif : plafonner le facteur à 1,0 sur un compte challenge + péremption 7 jours sur vol/news/bias comme sur le DXY.**

---

## 🟠 IMPORTANT — à savoir et à planifier

### 5. Les chiffres annoncés sont exacts… mais deux affirmations d'emballage sont fausses
*Contre-vérificateur de chiffres — il a tout recalculé depuis zéro.* Les +47 %/an (10 ans) et +37,5 %/an (2021-2026), et les taux de réussite 87 %/83 %, **se reproduisent à la décimale**. Par contre : « jamais −5 %/jour » est **faux** (3 journées ≤ −5 % dans le backtest même, pire : −5,61 % — une seule tue un challenge) et « jamais −10 % total » est **faux** (creux réel −19,9 % sur la courbe continue). La formulation honnête : **« ~87 % de chances de réussir un challenge, ~13 % de le perdre »**. Note : le gardien est à −2,5 %, pas −3 % comme dans certains résumés.

### 6. Le backtest ne simule pas fidèlement 2 des 5 robots déployés
*Sceptique de backtest.* Les robots or et Nasdaq réels calculent RSI/ATR/swing **sur des bougies H4**; le moteur Python les simule **sur des bougies journalières** (ATR ~2 à 2,5× plus grand → stops et lots très différents). Ce sont deux stratégies cousines, pas la même. Les 2 robots BTC, eux, sont fidèles.
**Test juge de paix : lancer chaque robot dans le Strategy Tester de MT5 (C:\MT6) sur 2023-2026 et comparer trade par trade avec le moteur Python.**

### 7. Les données or/pétrole/Nasdaq du backtest contiennent ~29 % de barres bidon
*Vérificateur de données + sceptique (trouvé indépendamment par les deux).* Les CSV Dukascopy gardent des barres plates de fin de semaine que le moteur ne filtre pas : **l'ATR du backtest est sous-estimé de ~24 %** et le « canal 20 jours » ne couvre que ~14 vrais jours de bourse. S'ajoutent : la grille H4 du backtest est en UTC alors que le serveur FTMO est en EET (décalage 2-3 h → d'autres cassures), et le fichier `d10h1_btc.csv` (nécessaire pour reproduire les chiffres L4.3) **manque dans le dossier partagé**.
**Correctifs : filtrer les barres week-end avant le resample et relancer le 10 ans; régénérer d10h1_btc.csv; rafraîchir les 3 CSV Dukascopy (19 jours de retard).**

### 8. Surajustement : ~10 générations sélectionnées sur la même décennie
*Sceptique.* 145 scripts de backtest, lignée I2→L4.31 presque toute choisie sur 2015-2026. Chaque choix individuel a été discipliné, mais l'empilement gonfle mécaniquement le chiffre final. Indices concrets : la moitié récente de la simulation fait **+17 %/an** (vs +39 % pour 2015-2020), et le seul chiffre L4.3 validé hors échantillon est **+19,7 %** (version sans BTC). **Le bas de la fourchette est l'attente honnête.** Le meilleur test qui reste : laisser la démo MT6 tourner 2-3 mois et comparer.

### 9. Monte Carlo : ~1 challenge sur 5 meurt par pure malchance
*Statisticien (5 000 tirages sur 383 trades).* Même si la stratégie vaut exactement son backtest : ~4 % d'échec en 1 mois, 7-9 % en 2 mois, **~19 % en courant jusqu'au +10 %** (durée typique 2-3 mois). Le tueur n° 1 : un gap nocturne/week-end BTC qui transperce le gardien — pas l'érosion lente. Une année donnée peut rendre de −5 % à +90 % par simple variance. **Budgéter 1-2 challenges ratés d'avance.**

### 10. Règles prop firm à jour : FTMO Swing = oui, FundingPips Master = non
*Vérificateur de conformité (sites officiels consultés le 20 août 2026).*
- **FTMO Challenge/Vérification 2-Step : conforme** telle quelle.
- **FTMO financé Standard : incompatible** — fermeture week-end obligatoire (aucun code du vendredi dans les robots) + interdiction que même un SL s'exécute à ±2 min des annonces (le serrage de stops du bot augmente justement ce risque). **Le compte Swing enlève les deux restrictions → c'est l'option naturelle.**
- **FundingPips évaluation : conforme. Master : hostile** — depuis janvier 2026, fermeture forcée de tout chaque vendredi (stratégie de tendance cassée) et « Striking System » sur Master >25 K$ : avertissement dès 1,2 % de perte flottante par idée alors que tes robots risquent 1,5-2 % → 4 trades perdants normaux = compte fermé.
- Divers : levier crypto 1:1 chez FTMO (les lots BTC seront réduits par la marge — risque réel plus petit que le backtest, à mesurer en démo); le pipeline de nouvelles ne couvre que l'USD (FTMO restreint aussi les stocks de pétrole); ne jamais copier les trades d'un terminal vers le compte prop (interdit).

---

## 🟡 INFRASTRUCTURE — gestes manuels rapides

*Vérificateur d'infrastructure.* L'écurie roule pour vrai (5 EA chargés, trade réel exécuté à 17 h 05, filtre DXY frais et planifié aux 30 min ✅). Mais :
1. **⚠️ À vérifier CE SOIR : des EA semblent attachés sur des graphiques de la mauvaise période** (le journal montre le robot D1 sur un graphique H1, le H1 sur H4, le H4 sur Daily). Si un robot lit la période du graphique, ses signaux sont faussés. → Ouvre MT6 et remets chaque robot sur un graphique de SA période. *(Bonne nouvelle du vérificateur de code : les robots utilisent des périodes codées en dur — mais confirme visuellement.)*
2. **Windows Update peut redémarrer la nuit** (heures actives 8 h-17 h) et rien ne repart avant ta connexion → élargir les heures actives + coup d'œil chaque matin.
3. **Couvercle et batterie** : vérifier « fermeture du couvercle = ne rien faire » sur secteur; la tâche DXY ne roule pas sur batterie → laptop branché, couvercle ouvert.
4. Ménage : une cible morte dans `dxy_filtre.py` (dossier disparu) = échec silencieux permanent à retirer; jeter un œil 1×/semaine à `dxy_journal.log`.

---

## ✅ CE QUE LE COMITÉ CONFIRME SOLIDE

- **Chiffres reproduits à la décimale** depuis les données brutes (deux experts indépendants).
- **Aucun look-ahead** dans les canaux/EMA/RSI : décisions sur barres fermées partout, pas de repaint.
- **Frais réels soignés** (commission FTMO exacte, swaps par barre, stress ×2/×3) — « au-dessus du standard amateur ».
- **SL serveur posé dans le même ordre que chaque achat** : jamais de position nue, même si tout plante après.
- **Reprise après redémarrage propre** : positions relues chez le courtier par magic+symbole, pas de doublon possible; le HALT survit au redémarrage.
- **Déploiement MT6 : identique bit pour bit** aux sources (MD5), .ex5 compilés à jour.
- **Variante SansChallenge : saine** — une seule différence (throttle 0,75 désactivé), tous les gardiens FTMO restent actifs.
- **Filtre DXY : bien placé et seulement là où les données le justifient** (corrélation or↔DXY −0,42; ~0 pour pétrole/Nasdaq — inutile de l'étendre).

---

## PLAN D'ACTION RECOMMANDÉ (dans l'ordre)

| # | Action | Type |
|---|---|---|
| 1 | Vérifier les périodes des graphiques dans MT6 | Manuel, 5 min, ce soir |
| 2 | Corriger le HALT (retenter la fermeture à chaque tick, 5 robots) | Code (sur ta demande) |
| 3 | Règle « un seul robot BTC en position à la fois » | Code (sur ta demande) |
| 4 | Réparer LireFacteurVol dans BTC EMA + plafond 1,0 + péremption des fichiers vol/news/bias | Code (sur ta demande) |
| 5 | Heures actives Windows Update + alimentation | Manuel, 10 min |
| 6 | Purger les barres week-end des CSV et relancer le backtest 10 ans | Backtest |
| 7 | Duel Strategy Tester MT5 vs moteur Python (or/Nasdaq surtout) | Backtest, juge de paix |
| 8 | Laisser la démo MT6 rouler 2-3 mois, comparer trade par trade | Patience |
| 9 | Le jour venu : FTMO **Swing** (pas Standard); questions écrites au support FundingPips avant d'acheter | Décision |
| 10 | Budget : prévoir 1-2 challenges ratés (~20 % de malchance incompressible) | Décision |

---

---

## ADDENDUM — CONTRE-EXPERTISE DE L'EXPERT FOREX (11e expert)

*Rapport complet : `RAPPORT_EXPERT_FOREX_L43.md`.* Il **confirme les 10 conclusions du comité** (aucune contestée) et en aggrave deux : le HALT one-shot échoue justement quand le marché est fermé, et le décalage ATR H4 vs journalier signifie des positions réelles 2-2,5× plus grosses que simulées. Ses ajouts principaux :

- 🔴 **Swap réel ~2× plus lourd que simulé sur or/Nasdaq** (3-5 points de rendement annuel manquants au backtest) — pas parce que les taux sont faux (ils sont bons), mais parce que les positions réelles sont plus grosses.
- 🔴 **Le swap « bonus » du pétrole peut s'inverser en contango** (−20 à −40 %/an vu en 2020) — retester la manche pétrole avec un swap négatif.
- 🔴 **Gaps OPEP+ du week-end** sur la pyramide pétrole ×4 : −3 % d'équité possible d'un coup, aucun garde-fou (le calendrier ne couvre que l'USD).
- 🟠 **Le robot BTC EMA D1 décide chaque jour à 17 h New York** — la pire heure de spread; une décision H4 sur six tombe au rollover.
- 🟠 Le mode « SERRER » des stops avant les annonces est contre-productif sur une stratégie tendance (whipsaw) en plus d'être risqué sur compte financé Standard.
- ✅ Bonnes nouvelles : calcul de lot robuste même sur compte non-USD, dividendes US100 en ta faveur, le non-problème des périodes de graphiques est confirmé (tout est codé en dur).

**Attente réaliste révisée : +10 à +15 %/an** (vs +15-20 % pour le comité initial). Verdict robot par robot : Or ⚠️, Nasdaq ⚠️, BTC Cassure ⚠️, **BTC EMA ❌ tant que non corrigé**, Pétrole ⚠️→❌.

---

*Rapport compilé à partir de 11 analyses indépendantes (code, risque, backtest, chiffres, portefeuille, scénarios extrêmes, conformité prop firm, Monte Carlo, données, infrastructure, forex/CFD). Aucun fichier des robots n'a été modifié pendant la vérification.*
