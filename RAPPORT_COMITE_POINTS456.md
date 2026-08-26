# GrokBot1 — la génération née du comité IA externe (26 août 2026)

**Ce que le labo a reçu** : un lien de conversation Grok
(`grok.com/share/bGVnYWN5LWNvcHk_9f05acfc…`, titre *« MT5 Trading Robot for FTMO
Challenges »*, dernier message *« Ajouter l'affichage graphique »*).

> ⚠️ **Limite honnête, à lire avant tout le reste.** Le contenu de cette
> conversation est **inaccessible depuis le labo** : la page Grok exige une
> session connectée (403 en accès direct, rendu client-side, API de partage
> fermée). Seules les métadonnées publiques ont pu être lues. **GrokBot1 n'a
> donc PAS été reconstruit à partir du texte de Grok** — il a été bâti à partir
> de ce que le labo possède *déjà* et *par écrit* des propositions de Grok :
> le `RAPPORT_COMITE_L8_VITESSE.md` du 21 août. Le seul élément repris
> directement de la conversation est **l'affichage graphique**, qui en était la
> dernière demande. Si le contenu réel de la conversation diffère, colle-le et
> le labo refait le banc — l'outillage est en place et rejouable en une commande.

---

## 1. Pourquoi ces mécanismes-là

Le comité du 21 août (ChatGPT / Grok / Gemini) avait laissé un **plan de banc en
6 points**. Un seul avait été exécuté : l'ancre roulante (Grok nº 1), **rejetée**
— on la retrouve désactivée dans `Jimmy R2` avec sa raison : *« le banc du quant
rejette la forme K = 2,0 : +18 j et −5 pts de CAGR »*.

Trois points dormaient depuis, tous touchés par Grok :

| Point | Idée | Auteur | État avant aujourd'hui |
|---|---|---|---|
| 4 | Réengagement après une sortie gagnante | Grok nº 5 | jamais testé |
| 5 | Canal de sortie rapide « réparé » par le réengagement | Gemini nº 3 + Grok | jamais testé |
| 6 | Coupe-temps conditionnel (absence de progrès) | les 3 IA | jamais testé |

C'est ce que GrokBot1 met au banc. Nouveau script : **`backtests/banc_comite_points456.py`**
(portefeuille complet, plafond de 2, frais réels, 10 ans de barres journalières
Yahoo, trois fenêtres). Le critère avait été **fixé d'avance par le comité** :
*réussite qui ne baisse pas ET durée médiane en baisse* — appliqué ici sur les
trois fenêtres, comme l'exige le standard 3 du README.

---

## 2. Résultats — fenêtre 10 ans

| Variante | CAGR | Sharpe | Creux | Réussite | Durée méd. | Give-back |
|---|---|---|---|---|---|---|
| **Référence (config H)** | +7,67 % | 1,23 | −10,7 % | 95,3 % | 600 j | 43,7 % |
| P4 réengagement +0,50 ATR *(Grok)* | +7,71 % | 1,24 | −10,7 % | 95,3 % | 597 j | 43,8 % |
| P5 canal 7 j seul | +4,88 % | 0,97 | −9,9 % | 100,0 % | 896 j | 45,9 % |
| P5 canal 7 j + réengagement | +4,95 % | 0,92 | −9,9 % | 95,2 % | 852 j | 48,1 % |
| P6 coupe-temps 8 j / 0,75 ATR | +8,85 % | 1,29 | −11,5 % | 97,6 % | 574 j | 41,1 % |
| **P6 coupe-temps 12 j / 1,00 ATR** ✅ | **+8,63 %** | **1,31** | −12,2 % | **96,9 %** | **573 j** | **42,1 %** |
| P6 coupe-temps 12 j / 2,00 ATR | +8,08 % | 1,23 | −12,0 % | 97,4 % | 618 j | 42,8 % |
| P6 coupe-temps 20 j / 3,00 ATR | +7,69 % | 1,25 | −10,7 % | 94,7 % | 611 j | 42,7 % |
| P4+5+6 combinés | +5,51 % | 0,98 | −11,6 % | 99,8 % | 816 j | 49,0 % |

### Les deux moitiés (standard 3)

| Variante | 2016-2021 CAGR / durée | 2021-2026 CAGR / durée |
|---|---|---|
| Référence | +8,89 % / 687 j | +6,82 % / 557 j |
| **Coupe-temps 12 j / 1,00 ATR** | **+11,00 % / 517 j** | **+6,89 % / 557 j** |
| Coupe-temps 8 j / 0,75 ATR | +11,85 % / 402 j | +6,64 % / 579 j ❌ |
| Coupe-temps 8 j / 1,50 ATR | +11,61 % / 414 j | +6,69 % / 574 j ❌ |
| Coupe-temps 12 j / 2,00 ATR | +10,89 % / 535 j | +6,57 % / 576 j ❌ |
| Canal 7 j + réengagement | +6,18 % / 804 j ❌ | +4,21 % / 798 j ❌ |

---

## 3. Les trois verdicts

### ✅ RETENU — coupe-temps conditionnel, 12 jours / 1,00 ATR (point 6)

> *Si après 12 jours le meilleur profit atteint n'a jamais dépassé 1 ATR
> journalier d'entrée, on ferme. Ce n'est pas l'âge qui coupe, c'est l'absence
> de progrès.*

Passe les 4 standards :

1. **Principe économique externe** — coût d'opportunité du capital immobilisé,
   pas une idée née de l'optimisation : le réglage 12 j / 1,00 ATR est celui que
   le comité a écrit, avant tout backtest.
2. **Frais réels** — portés par le moteur (swap BTC −30 %/an compris).
3. **Stabilité** — les deux moitiés s'améliorent (+2,11 pts et +0,07 pt),
   et les 5 voisins testés gagnent tous sur 10 ans : le **signe** du mécanisme
   est robuste.
4. **Portefeuille sous plafond de 2** — c'est le niveau auquel tout a été mesuré.

**Deux réserves, écrites noir sur blanc :**

- Il ne s'est déclenché que **6 fois en 10 ans**. Petit échantillon — la même
  réserve que le pyramidage à son époque, et elle avait tenu.
- Le **creux maximal se creuse** : −10,7 % → −12,2 % sur la série complète.
  Ce n'est pas un creux intra-challenge (la réussite FTMO *monte*, 95,3 → 96,9 %),
  mais sur compte financé le creux total compte pour de vrai. **À surveiller.**
- Le réglage voisin le plus rentable (8 j / 0,75 ATR : +8,85 % sur 10 ans,
  402 j sur la 1re moitié) **échoue sur la 2e moitié**. 12 j / 1,00 ATR est au
  **bord** du plateau, pas au centre.

### ⚪ NEUTRE, laissé désactivé — réengagement après sortie gagnante (Grok nº 5, point 4)

Le mécanisme fonctionne, se déclenche (armé 32 fois en 10 ans, 19 à 25 entrées
prises), et **ne change presque rien** : +0,04 pt de CAGR, −3 jours.

La raison est structurelle, et c'est l'apport de connaissance le plus solide de
ce banc :

> **Sur un châssis dont l'entrée est un plus-haut de canal, le réengagement de
> Grok est dominé par l'entrée elle-même.** Le déclencheur (« sommet du trade
> précédent + K × ATR ») est *au-dessus* du plus-haut 20 jours dès que le trade
> vient de se terminer — donc la cassure tire toujours la première. Les
> compteurs le montrent : sur 19 déclenchements à K = 1,00, **17 tombent le jour
> même que la cassure**. Et K = 0,25 / 0,50 / 1,00 / 1,50 donnent des résultats
> identiques : signature d'un mécanisme inerte, pas d'un plateau.

Conséquence pratique : **cette idée n'est pas morte, elle est mal logée.** Elle
n'a de contenu que sur un châssis dont l'entrée n'est PAS un plus-haut de canal
(fib/repli, EMA). C'est là qu'il faudra la retester si on y revient.

Le code est présent dans GrokBot1, `ReengagementActif = false`, avec sa raison
en commentaire — même convention que l'`AncreRoulanteActive = false` de R2.

### ❌ REJETÉ — canal de sortie rapide, réparé ou non (point 5)

L'hypothèse de Gemini — *« le canal 7 j s'écroulait, le réengagement le
répare »* — est **infirmée**. Le canal 7 j seul fait +4,88 % contre +7,67 %, et
le réengagement le remonte à +4,95 % : il ne répare rien. Le canal 5 j ne fait
pas mieux (+5,43 %). Les durées explosent (896 j, 852 j, 818 j contre 600 j) :
sortir plus tôt d'une tendance ne rend pas le challenge plus rapide, ça le rend
plus long, parce qu'on tronque exactement la queue qui paie.

C'est le **deuxième** rejet de cette famille, et il ferme la question posée le
21 août. À inscrire au cimetière.

---

## 4. Statut : validé, mais aucun robot ne le porte

Le coupe-temps a d'abord été embarqué dans deux robots dérivés du châssis L13.
**Ces fichiers ont été retirés** : la consigne était une lignée neuve, pas une
variante d'un robot existant (voir `RAPPORT_GROKBOT.md`). Le mécanisme reste
**validé et disponible** — il est à reprendre dans une prochaine écurie L14, avec
ses réglages : `CoupeTempsJours = 12`, `CoupeTempsSeuilATR = 1,00`, appliqué aux
seules cassures (BTC, pétrole), et **jamais** à un trade ayant déjà pyramidé
(interaction non testée : le moteur journalier du banc ne pyramide pas).

Deux détails d'implémentation à ne pas perdre : le compte se fait en **jours
(barres D1)**, pas en barres de décision ; et le seuil est en **ATR du jour
d'entrée**, pas l'ATR courant — donc à mémoriser au moment de l'entrée.

## 5. Ce que le labo apprend de cette manche

1. **Un mécanisme peut passer les 4 standards et rester au bord du plateau.**
   12 j / 1,00 ATR gagne partout sauf que ses voisins immédiats perdent la 2e
   moitié. Le *signe* est robuste (5 voisins sur 5 gagnent sur 10 ans), le
   *réglage* ne l'est pas. Nouveau réflexe à garder : distinguer explicitement
   « le mécanisme marche » de « ce réglage marche ».
2. **Une idée peut être bonne et mal logée.** Le réengagement de Grok est inerte
   ici *par construction*, pas par manque de valeur. Avant de jeter une idée au
   cimetière, vérifier qu'elle a seulement pu **s'exprimer** — les compteurs
   « armé / pris / doublé » du banc sont faits pour ça, et devraient devenir
   systématiques.
3. **Fermer une position qui ne progresse pas rapporte plus que fermer plus tôt
   une position qui progresse.** Le coupe-temps gagne (+0,96 pt) là où le canal
   rapide perd (−2,79 pts). Les deux « accélèrent » — un seul accélère sans
   couper la queue.
4. **Le give-back baisse quand le rendement monte.** 43,7 % → 42,1 % avec le
   coupe-temps. La statistique officielle demandée par le comité tient sa
   promesse : elle bouge dans le bon sens sur la variante retenue et dans le
   mauvais sur toutes les variantes de canal rapide (45,9 à 50,1 %).

---

## 6. Reproduire

```bash
cd backtests
python3 banc_comite_points456.py        # le banc complet, 3 fenêtres, verdict automatique
python3 build_grokbot1.py       # régénère les 2 EA depuis le châssis L13
```

Le banc met en cache les séries Yahoo dans `backtests/.cache_yahoo/`
(10 ans de barres journalières, 4 marchés). Résultats bruts :
`backtests/resultats_comite_points456.json`.

## 7. Ce qu'il reste à faire

- [ ] **Coller le contenu réel de la conversation Grok** — s'il décrit un robot
      différent, le banc est prêt à le mesurer.
- [ ] Compiler les deux `.mq5` dans MetaEditor (pas de compilateur MQL5 au labo :
      les fichiers sont vérifiés statiquement, pas compilés).
- [ ] Passer le coupe-temps au **moteur H4 avec pyramide** pour trancher
      `CoupeTempsIgnoreSiPyramide`.
- [ ] Retester le réengagement sur un châssis **fib/repli** (or, Nasdaq), le seul
      endroit où il peut s'exprimer.
- [ ] Surveiller le creux total (−12,2 %) si GrokBot1 va sur compte financé.
