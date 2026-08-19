"""Pont Python -> MetaTrader 5 : ecrit le biais macro courant (BIS) dans
MQL5\\Files\\macrobot_bias.txt pour que les EA FTMO_MacroBot et BTC_FTMO_Bot
le lisent (input BiasFromFile / BiaisMacroDepuisFichier = true).

Biais calcules a partir des donnees BIS (taux directeurs + inflation US) :
  GOLD : long tant que les taux reels US ne montent pas nettement (3 mois)
  NAS  : long tant que la Fed n'est pas en serrage brutal (6 mois)
  BTC  : meme moteur que le Nasdaq (actif de risque correle, sensible a la
         liquidite Fed) — pas de regle sur-mesure inventee sans backtest

A lancer ~1x/jour (tache planifiee Windows) ou a la main :
    bot.cmd ftmo-bias
"""
from __future__ import annotations

import glob
import os

from bot.assets import asset_bias_series
from bot.config import load_config
from bot.macro import component_panels


def main() -> None:
    cfg = load_config(require_oanda=False)
    rate_df, yoy_df = component_panels(cfg)
    gold = int(asset_bias_series("gold_real_rates", rate_df, yoy_df).iloc[-1])
    nas = int(asset_bias_series("nasdaq_fed", rate_df, yoy_df).iloc[-1])
    btc = nas  # BTC suit la posture Fed, comme le Nasdaq
    line = f"GOLD={gold};NAS={nas};BTC={btc}"

    base = os.path.join(os.environ["APPDATA"], "MetaQuotes", "Terminal")
    targets = glob.glob(os.path.join(base, "*", "MQL5", "Files"))
    targets += glob.glob(os.path.join(base, "*", "MQL4", "Files"))  # MT4 : ecurie L3
    if not targets:
        print("Aucun dossier MQL5\\Files trouve — MetaTrader 5 est-il installe ?")
        return
    for t in targets:
        path = os.path.join(t, "macrobot_bias.txt")
        with open(path, "w", encoding="ascii") as f:
            f.write(line + "\n")
        print(f"{line}  ->  {path}")


if __name__ == "__main__":
    main()
