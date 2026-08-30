# GrokBot — une lignée neuve, bâtie à partir de rien (26 août 2026)

> ⚠️ **Provenance.** La conversation Grok (`grok.com/share/bGVnYWN5LWNvcHk_9f05acfc…`,
> « MT5 Trading Robot for FTMO Challenges ») reste **illisible depuis le labo** :
> 403 en accès direct, page derrière connexion, API de partage fermée. Le labo
> tourne dans un conteneur isolé — il n'a aucun accès à un navigateur sur ton
> poste. **GrokBot n'est donc pas une transcription de ce que Grok a écrit** :
> c'est une lignée conçue et validée ici, sous le nom que tu lui as donné.
> Si tu colles le contenu réel, le banc est prêt à le mesurer.

**Consigne suivie** : aucune reprise d'un robot existant. Ni le châssis L13, ni
I2+, ni S2. `robots/GrokBot*/` est du code neuf, avec son propre banc
(`backtests/banc_grokbot.py`) et son propre simulateur **deux sens** — l'écurie
n'en avait pas.

---

## 1. Pourquoi cette lignée existe

Les 30 générations de l'écurie partagent un angle mort, nommé dans le README :
**elles sont 100 % acheteuses** sur des actifs de risque (BTC, or, Nasdaq,
pétrole). Aucune ne peut gagner quand le risque baisse.

GrokBot est bâti pour être ce robot-là : **deux sens**, sur le **FX** — la classe
d'actifs menée par les cycles de politique monétaire plutôt que par l'appétit
pour le risque.

**Principe économique externe (standard 1)** : le momentum de série temporelle
fonctionne dans les deux sens (Moskowitz-Ooi-Pedersen 2012 ; un siècle de données
AQR). Le README avait rejeté le TSMOM comme *filtre* plaqué sur des robots déjà
suiveurs de tendance — ce n'est pas le même usage : ici c'est la stratégie
elle-même, sur un territoire vierge.

**Frais, volontairement pessimistes** : commission 2,5 $/lot/côté et spread
0,3 pip (relevés dans les specs MT5, README section GBPUSD) → 0,0036 % par côté ;
et **swap −0,010 %/jour des DEUX côtés** — aucune paire ne reçoit de crédit de
portage, comme le README le réclame lui-même (« la majoration du courtier peut
l'annuler »).

---

## 2. Le criblage : 6 paires × 9 règles

Trois familles (Donchian deux sens, croisement d'EMA deux sens, TSMOM), leurs
voisins, sur 10 ans de barres journalières.

| Règle | Paire | R 10 ans | PF | 1re moitié | 2e moitié |
|---|---|---|---|---|---|
| **EMA 20/50 TP 1,5R** | **USDJPY** | **+14,5** | **2,04** | +3,5 | +10,5 |
| EMA 20/50 TP 1,5R | AUDUSD | +23,5 | 2,68 | +7,5 | +17,0 |
| EMA 20/50 TP 1,5R | USDCHF | +12,0 | 1,67 | +8,5 | +4,5 |
| EMA 20/50 TP 1,5R | AUDJPY | +8,0 | 1,42 | +5,0 | +1,5 |
| Donchian 20/10 | USDJPY | +9,4 | 1,66 | +1,4 | +8,0 |
| TSMOM 252 j | USDJPY | +0,6 | 1,07 | +0,5 | +0,1 |

**Contrôle de validité qui compte** : le README documentait déjà l'USDJPY EMA
20/50 comme *« candidat valide en réserve »* à **+14,4 R, PF 1,91**. Mon moteur,
écrit indépendamment, trouve **+14,5 R, PF 2,04**. Deux implémentations séparées
qui tombent sur le même chiffre — c'est le meilleur argument que le banc n'est
pas cassé.

**Pourquoi pas l'AUDUSD, qui affiche mieux ?** Parce que c'est un **pic**, pas un
plateau : son voisin EMA 30/60 tombe à 0,0 R et son stop à 3,0 ATR devient
négatif. L'USDJPY tient sur 12 voisins sur 13. Le labo choisit les plateaux.

---

## 3. Le contrôle d'exécution — la découverte de la manche

Le banc entre à la **clôture** de la bougie de signal. **Un robot ne peut pas
faire ça** : il voit la bougie fermée, puis entre à l'**ouverture suivante**.
J'ai donc rejoué toute la sélection sous cette contrainte.

| | R à la clôture | R à l'ouverture +1 | écart |
|---|---|---|---|
| GrokBot1 (EMA 20/50) | +14,5 | **+15,5** | **+1,0** |
| Réentrée sur repli 0,50 ATR | +21,5 | **+9,0** | **−12,5** |

**La réentrée sur repli était un artefact de moteur.** Elle gagnait parce que le
simulateur entrait à la clôture de la bougie qui touchait le niveau de repli —
exactement le piège du « +64,6 % apparent » déjà consigné au README. En
exécution réelle elle tombe *sous* la base. **Rejetée.**

L'avantage de GrokBot1, lui, **survit** — il s'améliore même légèrement. Le
contrôle d'exécution est donc devenu le **critère** du banc, plus une simple
vérification finale.

---

## 4. GrokBot1 — la base

> USDJPY. Croisement **EMA 20/50** sur bougies journalières : à la hausse →
> ACHAT, à la baisse → VENTE. Stop **2,0 × ATR(14)** = 1 R. TP **1,5 R**.
> Risque **0,75 %** du solde.

**Seul, 10 ans, exécution réelle** : +15,5 R, PF 2,19, 32 trades (3,1/an),
59 % gagnants, moitiés +4,5 et +10,5.

**Standard 4 — le portefeuille** (écurie + GrokBot, plafond de 2 positions) :

| Fenêtre | | CAGR | Creux | Sharpe | Réussite | Durée |
|---|---|---|---|---|---|---|
| 10 ans | écurie seule | +7,67 % | −10,7 % | 1,23 | 95,3 % | 600 j |
| 10 ans | **+ GrokBot1** | **+10,07 %** | −11,2 % | **1,46** | 95,2 % | **533 j** |
| 2016-21 | écurie seule | +7,86 % | −10,7 % | 1,15 | 88,4 % | 603 j |
| 2016-21 | **+ GrokBot1** | **+11,72 %** | −11,2 % | **1,45** | 88,6 % | **367 j** |
| 2021-26 | écurie seule | +7,40 % | −5,7 % | 1,34 | 100 % | 536 j |
| 2021-26 | **+ GrokBot1** | **+8,44 %** | −5,7 % | **1,52** | 100 % | **520 j** |

**+2,40 pts de CAGR, +0,23 de Sharpe, −67 jours, sur les deux moitiés.**

**Son défaut, dit franchement** : seul, il pousse le creux de l'écurie de −10,7 %
à **−11,2 %** — donc **au-delà de la limite FTMO de −10 %**. Il rapporte le plus
et protège le moins.

---

## 5. GrokBot2 — la deuxième paire

C'est le **seul** changement qui a passé le standard 4. Mêmes règles exactement,
mais déployées sur **USDJPY + USDCHF**, chacune avec son magic.

USDCHF seul, exécution réelle : **+18,0 R, PF 2,50, moitiés +7,0 et +12,0**.
*Réserve honnête* : son plateau est plus mince que celui de l'USDJPY (le voisin
EMA 10/40 échoue sur la 2e moitié).

| Fenêtre | | CAGR | Creux | Sharpe | Réussite | Durée |
|---|---|---|---|---|---|---|
| 10 ans | écurie seule | +7,67 % | −10,7 % | 1,23 | 95,3 % | 600 j |
| 10 ans | + GrokBot1 | +10,07 % | −11,2 % | 1,46 | 95,2 % | 533 j |
| 10 ans | **+ GrokBot2** | +9,47 % | **−8,9 %** | 1,40 | **98,1 %** | **516 j** |
| 2016-21 | **+ GrokBot2** | +11,57 % | **−8,9 %** | 1,44 | **95,4 %** | 435 j |
| 2021-26 | **+ GrokBot2** | +7,39 % | −6,7 % | 1,38 | 100 % | **495 j** |

**Le compromis, explicite** : la v2 rend **0,60 pt de CAGR** à la v1. Elle achète
avec le creux **ramené sous la barre FTMO** (−8,9 contre −11,2 %) et **+2,9 pts
de réussite**. Dans un challenge, passer vaut mieux que rapporter. **C'est la v2
qu'il faut utiliser.**

### Ce que le banc a rejeté pour cette v2

| Candidat | Verdict |
|---|---|
| Réentrée sur repli 0,25 / 0,50 / 1,00 ATR | +9,0 R en exécution réelle contre +15,5 pour la base — **artefact de moteur** |
| Point mort à +0,75 / +1,00 / +1,25 R | −3 à −12 R : coupe la queue qui paie |
| TP à 1,0 R / 2,0 R | échouent chacun sur une moitié |
| Stop à 1,5 ATR | −6,5 R, et les deux moitiés baissent |
| Stop à 3,0 ATR | **le plus trompeur** : PF 3,21 et moitiés équilibrées en solo, mais **+7,81 % en portefeuille** contre +10,07 — trop peu de trades pour mériter un siège |
| Plafond interne d'UNE position (anti-concentration USD) | −0,68 pt de CAGR, **rien** en échange : creux et réussite inchangés |

Le dernier mérite d'être noté : le plafond de 2 de l'écurie **gère déjà la
corrélation**, exactement la conclusion que le README avait tirée pour le plafond
par sous-jacent. Deux chemins indépendants, même verdict.

---

## 6. Les fichiers

```
robots/GrokBot1/GrokBot1_USDJPY_D1.mq5   magic 20268001
robots/GrokBot2/GrokBot2_USDJPY_D1.mq5   magic 20268002
robots/GrokBot2/GrokBot2_USDCHF_D1.mq5   magic 20268003
```

Chaque robot est **autonome** : sa propre gestion du risque (risque fixe converti
en lots par la valeur du tick, plafonné par le lot max, le notionnel et la marge),
ses propres gardiens, son propre filtre d'annonces, son propre affichage.

**Il partage trois choses avec l'écurie**, par les variables globales du terminal :
`MACROBOT_BASE_` (capital de départ), `MACROBOT_HALT_` (halte générale) et
`MACROBOT_DAY_` (pause du jour). Si un robot de l'écurie déclenche un gardien,
GrokBot ferme aussi — et l'inverse. Le plafond de positions se règle par
`MagicsEcurie` : la liste des magics comptés, à ajuster selon la génération
d'écurie que tu fais tourner.

**L'affichage graphique** (ta demande du tour précédent) : panneau d'état —
avancement du compte, gardiens, position et sens, entrée/stop/TP, biais des EMA,
plafond d'écurie, fenêtre d'annonce — plus les EMA, le stop et le TP tracés sur
les prix. Il **montre et ne décide rien**, il est **inerte hors mode visuel** et
limité à un rafraîchissement par quart de seconde : aucun coût en optimisation.

### Réserves à connaître avant de s'en servir

1. **~3,1 trades par an et par paire.** C'est très peu. GrokBot ne gagne pas par
   le nombre de coups mais par la diversification.
2. **Les fichiers ne sont pas compilés** — il n'y a pas de compilateur MQL5 au
   labo. Ils sont vérifiés statiquement (tokenisation réelle : équilibre des
   accolades/parenthèses/crochets, aucun appel non résolu, aucun caractère
   invisible). **À passer dans MetaEditor avant usage.**
3. **Le swap est une hypothèse**, pas un relevé. Le banc suppose −0,010 %/jour
   des deux côtés. Relève les vrais chiffres dans les specs MT5 de ton compte
   FTMO avant de mettre en réel : si le portage de l'USDJPY est positif à
   l'achat, les résultats s'améliorent ; s'il est plus négatif, ils se dégradent.
4. **La référence écurie de ce banc (+7,67 %/an) n'est pas celle du README
   (+18 %)** : fenêtres et moteurs différents. Seules les comparaisons
   *à l'intérieur* de ce banc ont un sens.

---

## 7. Ce que le labo apprend

1. **Le contrôle d'exécution doit être un critère, pas une vérification finale.**
   Il a retourné un verdict complet dans cette manche : la réentrée sur repli
   passait de « meilleur ajout, +48 % » à « pire que la base ». Tout mécanisme
   qui déclenche sur un niveau *touché intrabar* est suspect par construction.
2. **Un pic solo peut mourir en portefeuille.** Le stop à 3,0 ATR avait le
   meilleur PF du banc (3,21) et les moitiés les mieux équilibrées — et il
   s'effondre sous le plafond de 2, parce qu'il prend trop peu de trades.
   Standard 4 n'est pas une formalité.
3. **Une réplication indépendante vaut cher.** Retrouver +14,5 R / PF 2,04 là où
   le README avait +14,4 R / PF 1,91, avec un moteur écrit séparément, vaut plus
   que n'importe quel test de robustesse interne.
4. **J'ai changé un critère en cours de route et je le consigne** : le banc
   exigeait d'abord un PF en hausse. Ce veto a été retiré parce qu'il ne fait pas
   partie des 4 standards et contredit un précédent du README. Le retrait n'a
   rien sauvé : la variante qu'il bloquait est morte au contrôle d'exécution
   juste après.

## 8. Reproduire

```bash
cd backtests
python3 banc_grokbot.py     # criblage, plateau, v2, contrôle d'exécution, portefeuille
python3 build_grokbot.py    # régénère les 3 EA depuis backtests/grokbot_modele.mq5
```

## 9. La suite — GrokBot3

Le générateur est fait pour ça : ajouter une entrée dans `VERSIONS` et remplir
les fragments de mécanisme (aujourd'hui vides, aucun n'ayant survécu). Pistes
que le banc n'a pas encore ouvertes :

- [ ] Une **troisième paire** ; l'AUDJPY est le candidat suivant (+8,0 R, deux
      moitiés positives) mais son PF de 1,42 est mince.
- [ ] Le **portage réel** (relevé, pas supposé) comme filtre de sens : n'acheter
      la paire que du côté où le swap est payé.
- [ ] Un **dimensionnement par volatilité** (le `macrobot_vol.txt` de l'écurie),
      jamais testé sur un châssis deux sens.
- [ ] Trancher `TP 2,0 R` : +19,0 R contre +15,5, mais la 1re moitié baisse
      (+3,0 contre +4,5). À reprendre si des données plus longues arrivent.
