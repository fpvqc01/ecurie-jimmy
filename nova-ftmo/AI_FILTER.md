# “IA” sur Nova ORB — ce qui a été ajouté

## Ce qu’on N’a PAS mis
Un LLM (Grok/ChatGPT) qui décide **chaque trade M5** : trop lent, cher, instable, et risqué vs règles FTMO (outils ultra-rapides / non rejouables).

## Ce qu’on a mis (IA légère, utile)
1. **Filtre intelligent** dans l’EA (`UseSmartFilter=true`)  
   - refuse range trop petit / trop grand vs ATR  
   - refuse breakout avec bougie trop molle  
2. **Biais optionnel** via fichier `nova_ai_bias.txt`  
   - `BOTH` / `LONG` / `SHORT` / `OFF`  
   - généré par `python3 write_bias.py` (règle EMA H1) ou à la main

## Activer sur MT5
1. Recompile `Nova_ORB_XAUUSD_M5.mq5`  
2. Inputs : `UseSmartFilter=true`  
3. (Option) `UseBiasFile=true` + copie `nova_ai_bias.txt` dans `MQL5\Files\`
