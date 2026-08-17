"""Volatility targeting (Moreira & Muir 2017) pour l'ecurie I2.

Calcule chaque matin le facteur de modulation du risque :
  facteur = clip( 1 / vol_relative_moyenne_des_marches , 0.5 .. 1.5 )
ou vol_relative(marche) = vol 20 jours / vol long terme du marche.
> 1 quand les marches sont calmes (mises grossies)
< 1 quand ils s'agitent (mises reduites)

Valide en backtest 5 ans : CAGR +11.8% -> +13.9%, pire journee -3.53% -> -2.65%,
objectif +10% en ~150 jours au lieu de 192. Ecrit dans MQL5\\Files\\macrobot_vol.txt.

Lance par la tache planifiee quotidienne (bot.cmd ftmo-bias).
"""
from __future__ import annotations

import glob
import os

import requests


def vols_relatives() -> list[float]:
    out = []
    for sym in ("BTC-USD", "GC=F", "NQ=F", "CL=F"):
        r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}",
                         params={"range": "5y", "interval": "1d"},
                         headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
        r.raise_for_status()
        closes = [c for c in r.json()["chart"]["result"][0]["indicators"]["quote"][0]["close"]
                  if c is not None]
        rets = [(b - a) / a for a, b in zip(closes[:-1], closes[1:])]
        if len(rets) < 260:
            continue
        moy_lt = sum(rets) / len(rets)
        vol_lt = (sum((x - moy_lt) ** 2 for x in rets) / len(rets)) ** 0.5
        derniers = rets[-20:]
        moy20 = sum(derniers) / 20
        vol20 = (sum((x - moy20) ** 2 for x in derniers) / 20) ** 0.5
        if vol_lt > 0:
            out.append(vol20 / vol_lt)
    return out


def main() -> None:
    try:
        vols = vols_relatives()
        if not vols:
            print("AVERTISSEMENT: aucune donnee de volatilite — fichier inchange.")
            return
        facteur = max(0.5, min(1.5, 1.0 / (sum(vols) / len(vols))))
    except Exception as e:
        print(f"AVERTISSEMENT: calcul impossible ({e}) — fichier inchange.")
        return

    pattern = os.path.join(os.environ["APPDATA"], "MetaQuotes", "Terminal",
                           "*", "MQL5", "Files")
    for t in glob.glob(pattern):
        path = os.path.join(t, "macrobot_vol.txt")
        with open(path, "w", encoding="ascii") as f:
            f.write(f"FACTEUR={facteur:.2f}\n")
        print(f"FACTEUR={facteur:.2f}  ->  {path}")


if __name__ == "__main__":
    main()
