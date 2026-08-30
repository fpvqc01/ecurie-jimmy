# -*- coding: utf-8 -*-
"""Exporte vers les terminaux MetaTrader le calendrier des RESULTATS
d'entreprises des geants du US100 (Nasdaq 100).

Pourquoi : les 8 plus gros poids de l'indice (environ la moitie du
Nasdaq 100 a eux seuls) publient leurs chiffres 4 fois par an, presque
toujours APRES la cloture de 16 h New York. Le lendemain matin l'indice
gappe souvent de 1 a 2 %. Le robot Nasdaq lit ce fichier et refuse les
nouvelles entrees dans une fenetre autour de chaque publication (la
fenetre est reglee dans l'EA, pas ici).

Ce script est SEPARE de macrobot_news.txt (alimente par le bot OANDA,
tache « MacroBot nouvelles horaire ») : deux fichiers, deux ecrivains,
aucun conflit.

Ecrit dans chaque terminal MQL5\\Files (et MQL4\\Files) :
    resultats_us100.txt
        RESULTATS=1787961600;NVDA
        RESULTATS=...;...
(epoch UTC de chaque publication)

Source automatique : Yahoo Finance via yfinance (gratuit, sans cle).
Verifie le 25 aout 2026 : les dates arrivent avec l'heure et le fuseau
New York (ex. NVDA 2026-08-26 16:00 heure de l'Est = apres cloture).
LIMITE CONNUE : pour les dates lointaines Yahoo publie parfois une date
ESTIMEE non confirmee par la compagnie. D'ou le fichier manuel :

    evenements_manuels.txt (a cote de ce script) — lignes de la forme
        RESULTATS=2026-08-26 20:00;NVDA        (heure UTC)
        RESULTATS=1787961600;LIBELLE           (ou epoch direct)
        # commentaire
    Ces lignes sont FUSIONNEES au calendrier automatique et survivent
    a toutes les mises a jour. C'est ici qu'on ajoute un evenement
    special (Jackson Hole, une compagnie hors liste, etc.).

En cas d'echec reseau : les fichiers existants sont conserves tels quels.
"""
from __future__ import annotations

import datetime as dt
import glob
import os
import time

TICKERS = ["NVDA", "MSFT", "AAPL", "GOOGL", "AMZN", "META", "TSLA", "AVGO"]
NOM_FICHIER = "resultats_us100.txt"
ICI = os.path.dirname(os.path.abspath(__file__))
MANUEL = os.path.join(ICI, "evenements_manuels.txt")
JOURNAL = os.path.join(ICI, "export_resultats.log")

# garder : de 3 jours dans le passe (la fenetre « apres publication »
# doit rester visible le lendemain) a 60 jours devant
PASSE_J, FUTUR_J = 3, 60


def noter(msg: str) -> None:
    ligne = "%s  %s" % (dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(ligne)
    try:
        with open(JOURNAL, "a", encoding="utf-8") as f:
            f.write(ligne + "\n")
    except OSError:
        pass


def fetch_yahoo() -> list[tuple[int, str]] | None:
    """[(epoch_utc, ticker)] ou None si Yahoo est injoignable."""
    try:
        import yfinance as yf
    except ImportError:
        noter("ERREUR yfinance absent (pip install yfinance)")
        return None
    maintenant = dt.datetime.now(dt.timezone.utc)
    lo = maintenant - dt.timedelta(days=PASSE_J)
    hi = maintenant + dt.timedelta(days=FUTUR_J)
    out, echecs = [], []
    for tk in TICKERS:
        df = None
        for essai in (1, 2):
            try:
                df = yf.Ticker(tk).get_earnings_dates(limit=12)
                break
            except Exception as e:
                if essai == 2:
                    echecs.append(tk)
                    noter("AVERTISSEMENT %s illisible (%s)" % (tk, e))
                else:
                    time.sleep(5)
        if df is None or df.empty:
            continue
        for ts in df.index:
            try:
                t = ts.tz_convert("UTC").to_pydatetime()
            except Exception:
                continue
            if lo <= t <= hi:
                out.append((int(t.timestamp()), tk))
        time.sleep(1.5)          # menagement de Yahoo (429)
    if len(echecs) == len(TICKERS):
        return None              # tout a echoue -> ne rien reecrire
    return sorted(set(out))


def lire_manuel() -> list[tuple[int, str]]:
    """Les evenements ajoutes a la main, jamais ecrases par Yahoo."""
    if not os.path.exists(MANUEL):
        return []
    out = []
    with open(MANUEL, "r", encoding="utf-8", errors="ignore") as f:
        for brut in f:
            ligne = brut.strip()
            if not ligne or ligne.startswith("#"):
                continue
            if not ligne.upper().startswith("RESULTATS="):
                noter("AVERTISSEMENT ligne manuelle ignoree : %r" % ligne)
                continue
            corps = ligne[len("RESULTATS="):]
            quand, _, libelle = corps.partition(";")
            quand = quand.strip()
            epoch = None
            if quand.isdigit():
                epoch = int(quand)
            else:
                for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
                    try:
                        t = dt.datetime.strptime(quand, fmt)
                        epoch = int(t.replace(tzinfo=dt.timezone.utc).timestamp())
                        break
                    except ValueError:
                        pass
            if epoch is None:
                noter("AVERTISSEMENT date manuelle illisible : %r" % ligne)
                continue
            out.append((epoch, (libelle.strip() or "MANUEL")[:40]))
    return out


def dossiers_terminaux() -> list[str]:
    base = os.path.join(os.environ["APPDATA"], "MetaQuotes", "Terminal")
    dossiers = glob.glob(os.path.join(base, "*", "MQL5", "Files"))
    dossiers += glob.glob(os.path.join(base, "*", "MQL4", "Files"))
    # installations PORTABLES, invisibles au glob %APPDATA% (meme liste
    # que le correctif P0-1 d'export_news.py)
    for p in (r"C:\MT6\MQL5\Files", r"C:\NouveauMT5\MQL5\Files"):
        if os.path.isdir(p) and p not in dossiers:
            dossiers.append(p)
    return dossiers


def main() -> None:
    auto = fetch_yahoo()
    manuel = lire_manuel()
    if auto is None and not manuel:
        noter("Yahoo injoignable et pas d'evenements manuels : "
              "fichiers existants conserves.")
        return
    evenements = sorted(set((auto or []) + manuel))
    n = 0
    for d in dossiers_terminaux():
        chemin = os.path.join(d, NOM_FICHIER)
        try:
            with open(chemin, "w", encoding="ascii", errors="ignore") as f:
                for epoch, libelle in evenements:
                    f.write("RESULTATS=%d;%s\n" % (epoch, libelle))
            n += 1
        except OSError as e:
            noter("AVERTISSEMENT ecriture impossible %s (%s)" % (chemin, e))
    noter("%d publications (%d auto + %d manuelles) -> %d terminaux"
          % (len(evenements), len(auto or []), len(manuel), n))


if __name__ == "__main__":
    main()
