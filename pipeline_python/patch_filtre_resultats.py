# -*- coding: utf-8 -*-
"""Ajoute le FILTRE RESULTATS US100 a tous les robots Nasdaq des generations.

25 aout 2026. Le robot Nasdaq lit resultats_us100.txt (ecrit par la tache
planifiee « Ecurie resultats US100 quotidien » / export_resultats.py) et :
  - refuse toute NOUVELLE entree dans une fenetre large autour de chaque
    publication de resultats des geants du US100 (defaut 4 h avant -> 18 h
    apres, couvre le gap du lendemain matin) ;
  - serre les stops des positions ouvertes pendant la fenetre (reutilise
    ProtegerPositionsNews, meme mecanique que les annonces macro).

METHODE : substitutions a ANCRES STRICTES, tout-ou-rien PAR FICHIER.
Si une seule ancre manque dans un fichier, ce fichier n'est PAS modifie
et il est liste dans le rapport (les generations anciennes n'ont pas
toutes la meme charpente). Chaque .mq5 modifie est d'abord copie en
<nom>.mq5.avant_resultats_<horodatage> (extension non compilable).

Idempotent : un fichier qui contient deja FiltreResultatsActif est saute.
"""
from __future__ import annotations

import datetime as dt
import glob
import io
import os

HORODATE = dt.datetime.now().strftime("%Y%m%d_%H%M%S")

RACINES = [
    r"C:\NouveauMT5\MQL5\Experts",
    r"C:\MT6\MQL5\Experts",
    os.path.join(os.environ["APPDATA"],
                 r"MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Experts"),
    r"C:\Users\jplou\Downloads\generation-S",
    r"C:\Users\jplou\Downloads\Ecurie_Jimmy_I2plus_partage",
]
EXCLURE = ("_avant_", "sauvegarde", "backup")

NOUVEAUX_INPUTS = """input bool   FiltreResultatsActif    = true;   // 25 aout 2026 : resultats des geants du US100 (NVDA & cie)
input int    ResultatsMinutesAvant   = 240;    // blocage avant la publication (4 h)
input int    ResultatsMinutesApres   = 1080;   // et apres (18 h : couvre le gap du lendemain matin)
"""

FONCTION = """
//+------------------------------------------------------------------+
//| Filtre resultats (25 aout 2026) : les geants du US100 publient    |
//| apres la cloture de New York ; le vrai danger est le gap du       |
//| LENDEMAIN matin, hors de portee de la fenetre macro de 30 min.    |
//| resultats_us100.txt est ecrit par la tache planifiee              |
//| « Ecurie resultats US100 quotidien » (export_resultats.py).       |
//+------------------------------------------------------------------+
bool ResultatsBloquent()
  {
   if(!FiltreResultatsActif)
      return false;
   long modif = (long)FileGetInteger("resultats_us100.txt", FILE_MODIFY_DATE);
   if(modif > 0 && TimeCurrent() - (datetime)modif > 7 * 86400)
      return false;   // fichier perime -> neutre (pas de blocage fantome)
   int fh = FileOpen("resultats_us100.txt", FILE_READ | FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_TXT | FILE_ANSI);
   if(fh == INVALID_HANDLE)
      return false;
   long now = (long)TimeGMT();
   bool blocked = false;
   while(!FileIsEnding(fh))
     {
      string line = FileReadString(fh);
      if(StringFind(line, "RESULTATS=") != 0)
         continue;
      string rest = StringSubstr(line, 10);
      int sep = StringFind(rest, ";");
      long epoch = StringToInteger(sep > 0 ? StringSubstr(rest, 0, sep) : rest);
      if(epoch > 0 &&
         now >= epoch - (long)ResultatsMinutesAvant * 60 &&
         now <= epoch + (long)ResultatsMinutesApres * 60)
        {
         blocked = true;
         break;
        }
     }
   FileClose(fh);
   return blocked;
  }
"""

# (ancre exacte, remplacement, nombre d'occurrences attendu)
def edits():
    return [
        # E1 : les trois nouveaux inputs, apres le mode de protection news
        ("input ENUM_NEWS_PROTECT NewsProtectMode = NEWS_PROTECT_SERRER;\n",
         "input ENUM_NEWS_PROTECT NewsProtectMode = NEWS_PROTECT_SERRER;\n"
         + NOUVEAUX_INPUTS, 1),
        # E2 : la variable de cache, a cote de celle des news
        ("bool     cacheNewsBloq = false;\n",
         "bool     cacheNewsBloq = false;\n"
         "bool     cacheResultatsBloq = false;   // filtre resultats US100\n", 1),
        # E3a : lecture dans RafraichirDonneesExternes
        ("   bool n = NewsBlocks();\n",
         "   bool n = NewsBlocks();\n"
         "   bool r = ResultatsBloquent();\n", 1),
        # E3b : notification sur changement d'etat (regle : dire QUI et QUOI --
        # Notifier() prefixe deja l'identite du robot)
        ('      if(n != cacheNewsBloq)\n'
         '         Notifier(n ? "Annonce USD imminente : entrees bloquees, stops en protection."\n'
         '                    : "Fenetre d\'annonce terminee : retour a la normale.");\n',
         '      if(n != cacheNewsBloq)\n'
         '         Notifier(n ? "Annonce USD imminente : entrees bloquees, stops en protection."\n'
         '                    : "Fenetre d\'annonce terminee : retour a la normale.");\n'
         '      if(r != cacheResultatsBloq)\n'
         '         Notifier(r ? "Resultats d\'un geant du US100 ce soir : entrees bloquees, stops en protection."\n'
         '                    : "Fenetre de resultats terminee : retour a la normale.");\n', 1),
        # E3c : memorisation du cache
        ("   cacheNewsBloq = n;\n",
         "   cacheNewsBloq = n;\n"
         "   cacheResultatsBloq = r;\n", 1),
        # E4 : la fonction, juste avant ProtegerPositionsNews
        ("//+------------------------------------------------------------------+\nvoid ProtegerPositionsNews()\n",
         FONCTION
         + "//+------------------------------------------------------------------+\nvoid ProtegerPositionsNews()\n", 1),
        # E5 : le serrage de stops s'applique aussi pendant la fenetre resultats
        ("   if(NewsProtectMode == NEWS_PROTECT_RIEN || !cacheNewsBloq)\n",
         "   if(NewsProtectMode == NEWS_PROTECT_RIEN || (!cacheNewsBloq && !cacheResultatsBloq))\n", 1),
        # E6 : refus d'entree, journalise comme les autres refus
        ('   if(cacheNewsBloq)\n      { EcrireJournal("refus=fenetre_annonce"); return; }\n',
         '   if(cacheNewsBloq)\n      { EcrireJournal("refus=fenetre_annonce"); return; }\n'
         '   if(cacheResultatsBloq)\n      { EcrireJournal("refus=resultats_geants_US100"); return; }\n', 1),
    ]


def candidats():
    vus = set()
    for racine in RACINES:
        for chemin in glob.glob(os.path.join(racine, "**", "*.mq5"),
                                recursive=True):
            nom = os.path.basename(chemin)
            if "US100" not in nom and "Nasdaq" not in nom:
                continue
            bas = chemin.lower()
            if any(x in bas for x in EXCLURE):
                continue
            reel = os.path.normcase(os.path.abspath(chemin))
            if reel in vus:
                continue
            vus.add(reel)
            yield chemin


def patcher(chemin):
    src = io.open(chemin, encoding="utf-8", errors="replace").read()
    if "FiltreResultatsActif" in src:
        return "deja fait"
    manquantes = []
    for ancre, _, n in edits():
        if src.count(ancre) != n:
            manquantes.append("%r x%d attendu, x%d trouve"
                              % (ancre.strip()[:48], n, src.count(ancre)))
    if manquantes:
        return "ANCRES MANQUANTES : " + " | ".join(manquantes)
    copie = chemin + ".avant_resultats_" + HORODATE
    io.open(copie, "w", encoding="utf-8").write(src)
    for ancre, rempl, _ in edits():
        src = src.replace(ancre, rempl)
    io.open(chemin, "w", encoding="utf-8").write(src)
    return "PATCHE"


def main():
    bilans = {}
    for chemin in sorted(candidats()):
        bilans[chemin] = patcher(chemin)
    ok = sum(1 for v in bilans.values() if v == "PATCHE")
    deja = sum(1 for v in bilans.values() if v == "deja fait")
    rate = len(bilans) - ok - deja
    print("=" * 78)
    print("PATCH FILTRE RESULTATS US100 - %s" % HORODATE)
    print("%d fichiers patches, %d deja faits, %d refuses (ancres)" % (ok, deja, rate))
    print("=" * 78)
    for chemin, v in sorted(bilans.items()):
        print("%-9s %s" % (v if v in ("PATCHE", "deja fait") else "REFUSE", chemin))
        if v not in ("PATCHE", "deja fait"):
            print("          " + v)


if __name__ == "__main__":
    main()
