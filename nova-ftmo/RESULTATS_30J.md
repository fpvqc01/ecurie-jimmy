# Objectif ~30 jours — résultats labo Nova (2026-11-24)

## Ce qui a été fait

1. Données Yahoo : Or + Nasdaq en **M5 / M15 / H1** (`data/` + `fetch_data.py`)
2. Banc **EMA scalp session** → échec (0 % pass M15 après frais)
3. Banc **ORB** (breakout range Londres/NY) → **vitesse OK, survie faible**

## Meilleur compromis trouvé

**XAUUSD M5 — `orb_fast`** (risk 1.8 %, TP 1.8R, range 3 barres, halt 3.2 %)

| Métrique | Valeur |
|---|---|
| Réussite challenge | **~12 %** |
| Médiane si réussi | **~14–16 j** (donc ≤30 j) |
| Morts | **~19 %** |
| Timeouts | **~69 %** |

Variante **orb_blitz** : médiane ~10 j mais **~70–83 % de morts** → EV pire.

## Lecture honnête

- **Oui**, un challenge en ~2 semaines est *possible* sur Or en ORB agressif.
- **Non**, ce n’est pas encore un système “imprime de l’argent” : ~1 succès sur 8 sur cet échantillon (~60 j M5).
- L’échantillon M5/M15 Yahoo est **court** (60 j) — chiffres à revalider avec export MT5 plus long.
- Nova H4 (`nova_v3_D`) reste plus survivable (~68 % pass) mais **lent** (~350 j).

## Livrables live

- EA : `robots/Nova_ORB_XAUUSD_M5.mq5` (mode sprint ORB)
- Relancer banc : `python3 banc_orb.py`
- Rafraîchir data : `python3 fetch_data.py`
