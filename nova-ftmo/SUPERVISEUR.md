# Superviseur ML / agent d’autorisation

## Idée
1. L’EA ORB détecte un breakout → écrit `MQL5/Files/nova_pending.json` (features)
2. `supervisor.py` score le signal (LogisticRegression) → écrit `nova_auth.txt` = `YES,proba,id` ou `NO,...`
3. L’EA ne trade **que** si `YES` (sinon timeout → refuse, session consommée)

Sans superviseur (`UseAuthSupervisor=false`) : comportement ORB + filtre intelligent inchangé.

## Setup

```bash
cd nova-ftmo
pip install pandas numpy scikit-learn joblib yfinance
python fetch_data.py
python ml_dataset.py
python train_ml.py
```

Puis, sur le PC Windows où tourne MT5 (chemin à adapter) :

```bash
python supervisor.py --loop --mt5-files "C:\Users\TOI\AppData\Roaming\MetaQuotes\Terminal\XXXX\MQL5\Files"
```

Dans l’EA MetaTrader :
- `UseAuthSupervisor = true`
- `AuthTimeoutBars = 3` (≈15 min sur M5)

## Autorisation manuelle (sans ML)

Tu peux aussi écrire à la main :

```text
YES,1.0000,<id>
```

ou `NO,...` dans `nova_auth.txt` — c’est le même handshake.

## Limites (labo actuel)
- Yahoo M5 ≈ 60 jours → ~50 signaux ; AUC labo ~0.69 (petit échantillon, fragile)
- Ce n’est **pas** un LLM dans la boucle de ticks
- Retrain dès que tu as plus d’historique (export MT5 → CSV)
- Remplace `decide()` dans `supervisor.py` par un appel agent si tu veux une 2ᵉ opinion humaine/LLM **1× par signal**
