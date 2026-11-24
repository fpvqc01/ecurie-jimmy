# Recherche — scalping haute fréquence pour FTMO (~30 jours)

Date : 2026-11-24. Sources : FTMO Forbidden Practices, FAQ stratégies, analyses prop 2025–2026.

## Verdict en une ligne

Le **vrai HFT** (latence / tick arb / spam ordres) est **interdit ou suicidaire**.  
Le **scalping session M5–M15** sur Or/Nasdaq est **autorisé** chez FTMO et c’est le seul levier HF réaliste pour viser un challenge ~30 j — **si** l’edge bat spread+slippage.

## Ce que FTMO autorise / interdit

| Pratique | Statut |
|---|---|
| Scalping / tick scalping “normal” | Autorisé (pas de min hold time publié) |
| EA / algo | Autorisé |
| > **2000 requêtes serveur / jour** (open/mod/close) | **Interdit** (compte “hyperactif”) |
| Latency arb / feed retardé / erreurs prix | **Interdit** |
| Gap trading news / 2h avant fermeture marché | **Interdit** (règles gap) |
| Hedge multi-comptes | **Interdit** |
| Copy / même EA commercial massivement partagé | Risque de refus funded |

Sources : [Forbidden Trading Practices](https://ftmo.com/en/forbidden-trading-practices/), FAQ stratégies FTMO.

**Plafond pratique** : rester largement sous ~500–800 round-trips/jour (loin de 2000 requêtes).

## Familles de stratégies HF (classées pour FTMO + objectif 30 j)

### 1) Session momentum scalp — M5 / M15 (priorité #1 à tester)
- **Idée** : Londres / overlap NY seulement ; biais H1 ; entrée pullback EMA20/50 + RSI ; TP 1.2–1.5R ; stop serré ATR.
- **Marché** : XAUUSD d’abord (range journalier large) ; US100 en second (éviter les 15–30 first minutes cash open).
- **Risque** : 0.4–0.8 % / trade ; stop jour perso ~2.5–3 % (sous 5 % FTMO).
- **Pourquoi pour 30 j** : beaucoup de tentatives → possible +0.3–0.7 %/jour **si** winrate après frais tient.
- **Piège** : spread Or = 20–30 % d’un petit scalp M5 typique.

### 2) Liquidity grab / stop-run fade — M5
- **Idée** : sweep d’un high/low puis reclaim ; TP structure proche.
- **Pros** : R:R souvent >1.5 sur spikes.
- **Cons** : fragile en backtest, dépend de la qualité des ticks ; facile à overfitter.

### 3) Breakout ouverture session — M15
- **Idée** : range Asie → break Londres/NY avec filtre volume/ATR.
- **Pros** : 1–3 trades/jour, plus clean pour consistency.
- **Cons** : moins “HF” ; jours plats = challenge lent.

### 4) Micro mean-reversion M1 (Bollinger/RSI)
- **Idée** : fade extrêmes, TP mean.
- **Verdict FTMO** : souvent **mort par frais** (déjà vu dans le cimetière labo : scalping M1/M5 −17 à −42 %/semaine).
- **Ne pas prioriser** sans données M1 + coûts FTMO exacts.

### 5) Latency / tick arb / quote stuffing
- **Verdict** : **OUT**. Interdit + non rejouable en live réel.

## Maths challenge ~30 jours

Objectif 2-Step ≈ **+10 % puis +5 %** (ou trajectoire équivalente).  
Sur ~22–30 jours de trading : il faut de l’ordre de **+0.4 à +0.7 % / jour** en moyenne, avec rares jours morts.

| Style | Trades/jour | Edge net/trade besoin (ordre) | Faisable ? |
|---|---|---|---|
| H4 swing (Nova D) | 0–2 | grand | Oui mais **lents** (~300 j) |
| M15 session | 3–8 | ~0.1–0.2 R net | **Cible #1** |
| M5 agressif | 15–40 | doit battre spread | Difficile Or |
| M1 HF | 50–200 | presque impossible CFD | Non (frais + 2000 req) |

## Coûts — le vrai boss du scalping

Sur CFD FTMO (ordre de grandeur historique labo) :
- Or : spread non négligeable + swap si overnight
- Nasdaq : meilleur spread relatif, mais open US très bruyant
- Chaque aller-retour mange l’avantage : un scalp qui gagne 8–10 “points” Or peut en rendre 2–3 en coûts (**25–30 %**).

**Règle labo** : tout banc scalping doit soustraire **spread + slippage + commission** dès la v1, sinon c’est du mensonge.

## Recommandation Nova (pour viser 30 j)

1. **Construire `Nova_Scalp_M15`** (pas M1) : XAUUSD, sessions Londres+NY only.  
2. Entrée : H1 tendance + M15 pullback EMA + trigger close.  
3. Sortie : TP 1.4R / SL 1.0×ATR(M15) ; max 6 trades/jour ; halt −2.8 %.  
4. Banc : réussites challenge **et** médiane jours — cible médiane ≤45 j d’abord, puis serrer vers 30.  
5. Si pass <40 % à médiane ≤45 j → abandonner le scalp HF, remonter à M15 breakout session (moins de trades).

## Données manquantes aujourd’hui

Le repo n’a surtout que du **H4** (Or/Nasdaq/BTC) + un peu de **H1 BTC**.  
**Pas de M5/M15 Or** → impossible de valider un scalp HF propre tant qu’on n’importe pas ces séries (export MT5 ou broker).

## Prochaine action concrète

1. Exporter depuis MT5 : `XAUUSD M15` + `US100 M15` (2018→aujourd’hui) vers `nova-ftmo/data/`.  
2. Implémenter `nova-ftmo/scalp_m15.py` + banc challenge 30 j.  
3. Garder sous 2000 req/jour dans l’EA.
