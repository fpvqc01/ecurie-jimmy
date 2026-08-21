# Comité IA externe — comment passer les challenges plus vite (21 août 2026)

Question posée à ChatGPT, Grok et Gemini : **raccourcir la durée médiane du
challenge complet (205 jours) en gardant la réussite ≥ 90 %, par la GESTION
DES TRADES OUVERTS seulement.** Aucun code, aucun magic, aucun numéro de
compte n'a été transmis — description conceptuelle uniquement.

Base envoyée : L8 = +28,4 %/an, 89 % de réussite, 205 jours médians, creux −13,9 %.

---

## LE CONSENSUS : les 3 IA donnent la MÊME idée en no 1

**Dégeler l'ancre du stop une fois la pyramide pleine.**

Aujourd'hui : à 4 unités, l'ancre « dernière unité − 2×ATR » ne bouge plus
jamais. Seul le canal 10 jours peut encore monter le stop, avec 1 à 2 jours
de retard. C'est la cause des 11 % de gains rendus observés en réel.

Règle proposée (formulations quasi identiques) :

| IA | Règle exacte |
|---|---|
| ChatGPT | ancre « virtuelle » qui monte de 0,75 ATR à chaque +0,75 ATR du prix ; stop = max(canal 10 j, ancre virtuelle − 2 ATR). Tester 0,50 / 0,75 / 1,00 |
| Grok | stop = max(canal 10 j, plus-haut depuis la 4e unité − K×ATR), K = 1,8 / 2,0 / 2,2 |
| Gemini | stop = max(canal 10 j, plus-haut depuis la 4e unité − 2,5×ATR) |

**Ce n'est PAS le chandelier que j'ai déjà rejeté.** Mon test appliquait un
plancher « plus-haut depuis l'ENTRÉE − K×ATR » en permanence, avec K = 3/4/5.
Ici : uniquement APRÈS 4/4, ancré sur le plus-haut depuis la 4e unité, avec
K = 1,8 à 2,5. Serré, et seulement dans l'état gelé. Test différent, pas encore fait.

---

## LES IDÉES NEUVES (jamais testées)

**A. Serrage à l'approche de la ligne d'arrivée (Gemini, no 2)**
Si l'équité de la phase atteint +8 % (phase 1) ou +4 % (phase 2), tous les stops
de toutes les manches remontent au plus-bas 2 jours (ou 1,5 ATR sous le prix).
Raison : à +8 %, on n'a plus besoin de +20 % — on a besoin de FRANCHIR +10 %.
Voir l'équité redescendre de +9 % à +4 % rajoute des mois.
C'est le seul mécanisme du lot qui vise directement la durée.

**B. Réengagement après une sortie GAGNANTE (ChatGPT no 2, Grok no 5, Gemini no 3)**
Après une sortie en profit : mémoriser le dernier sommet, et réentrer avec
1 unité seulement si prix > ce sommet + 0,5 (ou 1,0) ATR. Jamais de réentrée
immédiate — machine à faux signaux.
Gemini pousse plus loin : rétablir le canal de sortie 7 jours (le plus rapide
du banc, 129 j, mais qui écroulait la réussite à 69 %) ET lui coller le
réengagement comme filet. Ça répare le mécanisme que j'avais rejeté.

**C. Coupe-temps CONDITIONNEL, pas par l'âge (les 3)**
Jamais « fermer après N jours ». Fermer si ABSENCE DE PROGRÈS :
si après 8 barres depuis la dernière unité le meilleur profit atteint est
< 0,75 ATR → fermer cette unité. Après 12 barres, si le trade entier n'a
jamais dépassé +1 ATR → tout fermer.

**D. Gestion différente phase 1 / phase 2 (ChatGPT no 7)**
Phase 1 (+10 % à faire) : laisser courir. Phase 2 (+5 % seulement) : serrer
le stop à 1,5 ATR au lieu de 2 dès +3,5 %. Changement de gestion, pas de risque.

---

## CE QU'ILS CONFIRMENT DE MES REJETS

Les trois confirment mes rejets : verrouillage partiel, chandelier large,
canal 7 j seul, TP courts, augmentation de taille. Le quant de ChatGPT :
« le rendement du trend following vient de quelques grosses queues ; il faut
raccourcir la durée sans tronquer cette queue. »

Aucun ne recommande de retirer le breakeven collectif malgré ses +30 jours :
c'est le mécanisme de survie, pas l'accélérateur.

---

## ⚠️ UN POINT À VÉRIFIER DANS MON PROPRE SIMULATEUR

ChatGPT soulève que **FTMO exige que le +10 % soit atteint POSITIONS FERMÉES**,
pas en équité flottante. Mon simulateur travaille sur des rendements
quotidiens. Si ces rendements comptent le profit flottant, mes 205 jours et
mon 89 % sont OPTIMISTES. À vérifier avant tout autre test — ça peut changer
tous les chiffres, comme le bogue de données l'a fait.

## Une remarque de ChatGPT à clarifier

Il note l'incohérence 205 j (aujourd'hui) vs 175 j (mon ancien test).
Explication : 175 j = L6 SANS breakeven collectif ; 205 j = L8 AVEC.
Le breakeven coûte +30 jours. Ce n'est pas une erreur, mais il a raison sur
le principe : un seul point de comparaison pour tous les prochains tests.

---

## Plan de banc proposé

1. **Vérifier le simulateur** (profit fermé vs flottant) — bloquant.
2. **Ancre roulante après 4/4** : 3 variantes d'espacement × 3 valeurs de K.
3. **Serrage ligne d'arrivée** : +8 %/+4 %, seuils voisins.
4. **Réengagement après gagnante** : +0,5 / +1,0 ATR au-dessus du sommet.
5. **Canal 7 j + réengagement** (réhabilitation du mécanisme rejeté).
6. **Coupe-temps conditionnel** sur absence de progrès.

Critère fixé D'AVANCE, comme le demandent les trois : on retient une variante
seulement si **réussite ≥ 90 % ET durée médiane en baisse**, vérifié sur les
DEUX fenêtres (10 ans et 2021-2026). Et on mesure le give-back
(meilleur profit atteint − profit réalisé) comme statistique officielle.
