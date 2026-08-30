"""Exporte vers MetaTrader 5 les donnees "temps reel" utiles aux robots :

1. Calendrier economique Forex Factory (flux XML gratuit) : les annonces
   USD a fort impact (CPI, Fed, emploi...) de la semaine. Les robots
   bloquent les nouvelles entrees autour de ces heures.
2. Crypto Fear & Greed Index (api.alternative.me, gratuit, sans cle) :
   sentiment du marche crypto, informatif (affiche dans le journal MT5).

Ecrit MQL5\\Files\\macrobot_news.txt :
    FNG=34
    EVENT=1755266400;Retail Sales m/m
    EVENT=...
(epoch UTC de chaque annonce ; la fenetre de blocage est reglee dans l'EA)

ATTENTION : le flux Forex Factory retourne une erreur 429 si on l'appelle
trop souvent. 1x/jour via la tache planifiee, c'est le bon rythme.
En cas d'echec reseau, le fichier existant est conserve tel quel.
"""
from __future__ import annotations

import glob
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

FF_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.xml"
FNG_URL = "https://api.alternative.me/fng/?limit=1"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# Fuseau du flux Forex Factory : GMT/UTC.
# Verifie le 2026-08-15 : le CPI (toujours publie a 8:30 heure de New York,
# soit 12:30 GMT en ete) apparait a "12:30pm" dans le flux -> le flux est GMT.
FEED_TZ = ZoneInfo("UTC")


def fetch_ff_events() -> list[tuple[int, str]]:
    """[(epoch_utc, titre)] des annonces USD a fort impact de la semaine."""
    r = requests.get(FF_URL, headers=UA, timeout=30)
    r.raise_for_status()
    root = ET.fromstring(r.text)
    out = []
    for ev in root.iter("event"):
        try:
            def txt(tag: str) -> str:
                node = ev.find(tag)
                return (node.text or "").strip() if node is not None else ""
            if txt("country") != "USD" or txt("impact") != "High":
                continue
            date_s, time_s = txt("date"), txt("time").lower()
            # heures non precises ("All Day", "Tentative", vide) : injouable -> ignore
            m = re.match(r"^(\d{1,2}):(\d{2})(am|pm)$", time_s)
            if not m or not date_s:
                continue
            h, mn = int(m.group(1)) % 12, int(m.group(2))
            if m.group(3) == "pm":
                h += 12
            mois, jour, annee = (int(x) for x in date_s.split("-"))
            local = datetime(annee, mois, jour, h, mn, tzinfo=FEED_TZ)
            titre = re.sub(r"[^A-Za-z0-9 .%/-]", "", txt("title"))[:60]
            out.append((int(local.timestamp()), titre))
        except Exception as e:
            print(f"AVERTISSEMENT annonce ignoree (illisible): {e}")
    return sorted(out)


def fetch_fng() -> int:
    """Fear & Greed crypto 0-100, ou -1 si indisponible."""
    r = requests.get(FNG_URL, headers=UA, timeout=30)
    r.raise_for_status()
    return int(r.json()["data"][0]["value"])


def main() -> None:
    try:
        events = fetch_ff_events()
    except Exception as e:
        print(f"AVERTISSEMENT calendrier Forex Factory indisponible ({e}) — "
              "fichier existant conserve.")
        events = None
    try:
        fng = fetch_fng()
    except Exception as e:
        print(f"AVERTISSEMENT Fear & Greed indisponible ({e})")
        fng = -1

    if events is None and fng < 0:
        return  # rien de neuf a ecrire

    base = os.path.join(os.environ["APPDATA"], "MetaQuotes", "Terminal")
    dossiers = glob.glob(os.path.join(base, "*", "MQL5", "Files"))
    dossiers += glob.glob(os.path.join(base, "*", "MQL4", "Files"))  # MT4 : ecurie L3
    for t in dossiers:
        path = os.path.join(t, "macrobot_news.txt")
        anciens = []
        if events is None and os.path.exists(path):
            with open(path, "r", encoding="ascii", errors="ignore") as f:
                anciens = [l.rstrip("\n") for l in f if l.startswith("EVENT=")]
        with open(path, "w", encoding="ascii", errors="ignore") as f:
            f.write(f"FNG={fng}\n")
            if events is not None:
                for epoch, titre in events:
                    f.write(f"EVENT={epoch};{titre}\n")
            else:
                f.write("\n".join(anciens) + ("\n" if anciens else ""))
        print(f"FNG={fng}, {len(events or anciens)} annonces USD fort impact -> {path}")


if __name__ == "__main__":
    main()
