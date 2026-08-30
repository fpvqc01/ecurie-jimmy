# -*- coding: utf-8 -*-
"""FILTRE DOLLAR L4.1 (21 aout 2026) : calcule si le dollar est fort
(DXY > sa moyenne mobile exponentielle 200 jours, Yahoo) et ecrit
Ecurie_DXY.txt ("1 AAAA-MM-JJ" = fort, "0 AAAA-MM-JJ" = pas fort) dans les
dossiers Files des terminaux. Les robots or L4 lisent ce fichier ; s'il
est absent ou vieux de plus de 7 jours, ils ne bloquent RIEN (fail-open).
A lancer une fois par jour (double-clic sur Filtre_DXY.cmd)."""
import time, datetime, requests

CIBLES = [
    r"C:\MT6\MQL5\Files",
    r"C:\NouveauMT5\MQL5\Files",   # P0-1 (22 aout 2026) : 2e portable, etait absent
    r"C:\Users\jplou\AppData\Roaming\MetaQuotes\Terminal\4091F7F60940A975FCB8650EE9CE5521\MQL5\Files",
    r"C:\Users\jplou\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Files",
    r"C:\Users\jplou\AppData\Roaming\MetaQuotes\Terminal\2C68BEE3A904BDCEE3EEF5A5A77EC162\MQL4\Files",
]

def main():
    fin = int(time.time())
    debut = fin - int(2.0 * 365.25 * 86400)          # 2 ans suffisent pour l'EMA 200
    r = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/DX-Y.NYB",
                     params={"period1": debut, "period2": fin, "interval": "1d"},
                     headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
    r.raise_for_status()
    d = r.json()["chart"]["result"][0]
    clotures = [c for c in d["indicators"]["quote"][0]["close"] if c is not None]
    if len(clotures) < 210:
        raise SystemExit("pas assez de donnees DXY (%d jours)" % len(clotures))
    alpha = 2.0 / 201.0
    ema = clotures[0]
    for c in clotures:
        ema = alpha * c + (1 - alpha) * ema
    dernier = clotures[-1]
    fort = 1 if dernier > ema else 0
    ligne = "%d %s" % (fort, datetime.date.today().strftime("%Y.%m.%d"))
    ecrits = 0
    for dossier in CIBLES:
        try:
            with open(dossier + r"\Ecurie_DXY.txt", "w", encoding="ascii") as f:
                f.write(ligne + "\n")
            ecrits += 1
        except OSError as e:
            print("  impossible d'ecrire dans %s : %s" % (dossier, e))
    etat = "FORT (or bloque)" if fort else "pas fort (or libre)"
    msg = ("DXY %.2f vs EMA200 %.2f -> dollar %s | '%s' ecrit dans %d dossiers"
           % (dernier, ema, etat, ligne, ecrits))
    print(msg)
    return msg

if __name__ == "__main__":
    import os
    journal = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dxy_journal.log")
    try:
        msg = main()
    except Exception as e:
        msg = "ERREUR : %s (fail-open : les robots ne bloquent rien)" % e
    # execution aux 30 min : on ne journalise que les CHANGEMENTS d'etat
    # (et les erreurs), sinon le journal se noierait en lignes identiques
    etat_actuel = msg.split("->")[-1].split("|")[0].strip() if "->" in msg else msg
    dernier_etat = ""
    if os.path.exists(journal):
        with open(journal, encoding="utf-8") as f:
            lignes = f.readlines()
        if lignes:
            d = lignes[-1]
            dernier_etat = d.split("->")[-1].split("|")[0].strip() if "->" in d else ""
    if etat_actuel != dernier_etat or "ERREUR" in msg:
        with open(journal, "a", encoding="utf-8") as f:
            f.write("%s  %s\n" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), msg))
