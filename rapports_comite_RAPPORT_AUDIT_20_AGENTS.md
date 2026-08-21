# RAPPORT À CONTRE-VÉRIFIER — Banc des écuries L6 (21 août 2026)

## Ce qui est affirmé (à confirmer ou infirmer)

Simulateur FTMO exact (phase 1 +10 %, phase 2 +5 %, −5 %/jour sur
l'équité de début de jour, −10 % total, minimum 4 jours par phase,
départs glissants tous les 3 jours de bourse ≈ 1 200 départs jugés).
Données propres (barres de week-end purgées). Moteur H4.

### MODE CHALLENGE ON (frein d'équité : mises à 75 % sous la moyenne 20 j)

| Écurie | 10 ans CAGR/réussite/durée | 2021-2026 | DD |
|---|---|---|---|
| L6 (base) | +38,1 % / 94 % / 157 j | +27,5 % / 88 % / 149 j | −16,7 % |
| L6+ turbo-coussin | +38,1 % / 78 % / 109 j | +27,5 % / 65 % / 102 j | −16,7 % |
| L6++ breakeven 5 % | +38,2 % / 97 % / 156 j | +31,1 % / 93 % / 154 j | −14,4 % |
| L6++ breakeven 6 % | +38,6 % / 92 % / 144 j | +30,0 % / 93 % / 150 j | −14,8 % |
| L6++ 5 % + turbo | +38,2 % / 82 % / 115 j | +31,1 % / 83 % / 116 j | −14,4 % |

### MODE CHALLENGE OFF (sans frein)

| Écurie | 10 ans | 2021-2026 | DD |
|---|---|---|---|
| L6 | +45,0 % / 66 % / 106 j | +31,5 % / 67 % / 130 j | −19,4 % |
| L6+ turbo | +45,0 % / 64 % / 78 j | +31,5 % / 56 % / 86 j | −19,4 % |
| L6++ breakeven 5 % | +45,9 % / 79 % / 117 j | +34,9 % / 88 % / 136 j | −16,9 % |
| L6++ breakeven 6 % | +47,4 % / 72 % / 109 j | +33,6 % / 71 % / 131 j | −17,6 % |
| L6++ 5 % + turbo | +45,9 % / 74 % / 92 j | +34,9 % / 80 % / 107 j | −16,9 % |

## Les mécanismes

- **L6** (EN SERVICE sur MT6) : allocation a×0,75 (Or 0,75 / Nasdaq 0,75
  / Pétrole 1,69 / BTC Cassure 1,69 / BTC EMA 1,13 %), garde vendredi
  pétrole, EMA décidée à 08:00, plafond facteurVol inconditionnel,
  péremption 7 j des fichiers, garde de spread 2 %.
- **L6+** (EN SERVICE sur le MT5 original) : L6 + turbo-coussin — risque
  ×1,33 tant que l'équité de la phase n'a pas +4 %, puis ×1,0.
- **L6++** (construite, NON déployée) : L6 + breakeven collectif — dès
  que le profit du trade dépasse le seuil (5 ou 6 %), le stop commun ne
  peut plus descendre sous le prix d'entrée MOYEN des unités
  ((première + dernière)/2). Appliqué aux 2 manches qui pyramident.

## Les conclusions tirées (à challenger)

1. L6++ breakeven 5 % domine L6 sur les 4 colonnes : rendement ≥,
   réussite +3 pts (10 ans) et +5 pts (récent), DD −2,3 pts, durée égale.
   « Aucun compromis ».
2. Le breakeven serait le meilleur amortisseur connu : en mode OFF il
   récupère 66 → 79 % (10 ans) et 67 → 88 % (récent).
3. Le turbo seul serait le pire compromis (56-78 %).
4. Le frein d'équité vaudrait +28 pts de réussite pour −7 pts de CAGR.
5. Un plateau de seuils 5-9 % a été observé (banc_giveback_robustesse).

## Ce qui a été rejeté au banc (give-back)

Verrouillage partiel (fermer 1 unité sur 3) : 198 j au seuil 4 % = PIRE
que la référence. Chandelier ATR K=3/4/5 : neutre (161/162/169 j).
Canal de sortie 7 j : 129 j mais 69 % de réussite sur 2021-2026.

## Où regarder (dépôt Ecurie_Jimmy_I2plus_partage)

- `backtests/banc_ecuries_L6_modes.py` — le banc ON/OFF (source des tableaux)
- `backtests/banc_ecuries_L6.py` — comparatif mode ON
- `backtests/banc_giveback.py` — les 12 mécanismes
- `backtests/banc_giveback_robustesse.py` — plateau des seuils
- `backtests/moteur_h4.py`, `test_l4_macro.py`, `tests_comite_B.py` — le moteur
- Robots : `robots/Jimmy L6/`, `robots/Jimmy L6+/`, `robots/Jimmy L6++/`
- Les mêmes fichiers de données/scripts sont aussi dans le dossier de
  travail temporaire de la session (scratchpad).

## QUESTIONS AU GROUPE

1. Les chiffres se reproduisent-ils ? Y a-t-il une erreur de méthode
   (double comptage, look-ahead, simulateur trop permissif) ?
2. Le breakeven collectif est-il un vrai gain ou un artefact
   d'ajustement ? Le plateau 5-9 % tient-il à un ré-échantillonnage ?
3. La formule (première + dernière)/2 est-elle la bonne définition du
   « point mort collectif » ? Elle diffère du vrai prix moyen pondéré
   (écart mesuré ~215 points sur un cas réel à 73 500).
4. Le simulateur FTMO exact reproduit-il fidèlement les règles 2026
   (calcul du daily loss sur le solde à 00:00 CE(S)T, équité flottante,
   commissions et swaps inclus) ?
5. Danger caché à déployer L6++ sur un compte réel ?
