# -*- coding: utf-8 -*-
"""Fabrique les versions de GrokBot a partir du modele commun.

GrokBot est une LIGNEE : GrokBot1, GrokBot2, GrokBot3... Chaque version
ajoute UN mecanisme, et seulement s'il a passe le banc (banc_grokbot.py).
Le modele est unique pour que les versions ne divergent jamais par
accident -- meme esprit que build_L3.py et build_generations_plus.py,
mais sur du code GrokBot, jamais sur un robot de l'ecurie.

  GrokBot1 : la base. EMA 20/50 deux sens, stop 2 ATR, TP 1,5 R.
  GrokBot2 : GrokBot1 + reentree sur repli de 0,50 ATR apres un TP.

Pour ajouter GrokBot3 : passer le mecanisme au banc, puis ajouter une
entree dans VERSIONS avec ses fragments. Rien d'autre a toucher.

Lancer :  python3 build_grokbot.py
"""
import io, os, re

D = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.dirname(D)
MODELE = os.path.join(D, "grokbot_modele.mq5")

# ------------------------------------------------------------------
# Les chiffres du banc, ecrits une seule fois et injectes dans l'entete
# des robots : impossible qu'un fichier annonce autre chose que ce que
# le banc a mesure. TOUS sont en EXECUTION REELLE (entree a l'ouverture
# de la bougie suivante), jamais a la cloture du signal.
# ------------------------------------------------------------------
POURQUOI_USDJPY = """//|  POURQUOI L'USDJPY                                               |
//|  Six paires criblees, neuf regles chacune. L'AUDUSD affiche mieux |
//|  (+23,5 R) mais c'est un PIC : son voisin EMA 30/60 tombe a 0,0 R |
//|  et son stop a 3,0 ATR devient negatif. L'USDJPY est celui dont   |
//|  le voisinage tient le mieux : 12 voisins sur 13 positifs sur     |
//|  10 ans ET sur les deux moities. Le labo choisit les plateaux,    |
//|  pas les pics -- c'est ecrit dans les 7 idees du README.          |"""

POURQUOI_USDCHF = """//|  POURQUOI L'USDCHF EN DEUXIEME PAIRE                             |
//|  Seule paire, apres l'USDJPY, positive sur 10 ans ET sur les deux |
//|  moities avec la meme regle, sans reglage particulier : +18,0 R,  |
//|  PF 2,50, moities +7,0 et +12,0. Son plateau est plus mince que   |
//|  celui de l'USDJPY (le voisin EMA 10/40 echoue sur la 2e moitie), |
//|  c'est dit franchement -- mais son apport n'est pas le rendement  |
//|  brut : c'est le CREUX du portefeuille, ramene sous la barre      |
//|  FTMO. Voir l'entete GrokBot2 pour le detail du compromis.        |"""

PORTE_V1 = """//|      10 ans    CAGR +10,07 % (ecurie seule +7,67)  Sharpe 1,46 (1,23)|
//|                creux -11,2 % (-10,7)  reussite 95,2 % (95,3)     |
//|                duree mediane du challenge 533 j (600)            |
//|      2016-21   CAGR +11,72 % (+7,86)  duree 367 j (603)          |
//|      2021-26   CAGR +8,44 %  (+7,40)  duree 520 j (536)          |
//|                                                                  |
//|      LE DEFAUT, dit franchement : seul, GrokBot1 pousse le creux  |
//|      de l'ecurie de -10,7 a -11,2 %, donc AU-DELA de la limite    |
//|      FTMO de -10 %. Il rapporte le plus, il protege le moins.     |
//|      C'est exactement ce que GrokBot2 corrige.                   |"""

PORTE_V2 = """//|      10 ans    CAGR +9,47 %  (ecurie seule +7,67 ; v1 +10,07)     |
//|                creux -8,9 % (-10,7 ; v1 -11,2)                   |
//|                reussite 98,1 % (95,3 ; v1 95,2)                  |
//|                duree mediane 516 j (600 ; v1 533)                |
//|      2016-21   CAGR +11,57 % (+7,86)  creux -8,9 %  reussite 95,4 %|
//|      2021-26   CAGR +7,39 %  (+7,40)  creux -6,7 %  reussite 100 %|
//|                                                                  |
//|      LE COMPROMIS : la v2 rend 0,60 pt de CAGR a la v1. Elle      |
//|      achete avec le creux ramene SOUS la barre FTMO (-8,9 contre  |
//|      -11,2 %) et +2,9 pts de reussite. Dans un challenge, passer  |
//|      vaut mieux que rapporter : c'est la v2 qu'il faut utiliser.  |"""

ROLE_V1 = """//|  CETTE VERSION : GrokBot1, la base. UNE paire, l'USDJPY.         |"""

ROLE_V2 = """//|  CETTE VERSION : GrokBot2. Memes regles EXACTEMENT que GrokBot1, |
//|  mais deployees sur DEUX paires -- USDJPY et USDCHF -- chacune    |
//|  avec son magic. Aucun mecanisme ajoute : le banc les a tous      |
//|  rejetes (voir plus bas). Le seul changement qui a passe le       |
//|  standard 4 est la deuxieme paire.                               |
//|                                                                  |
//|  CE QUE LE BANC A REJETE POUR CETTE v2 (ne pas reessayer) :       |
//|   - reentree sur repli apres un TP (0,25 / 0,50 / 1,00 ATR) :     |
//|     +21,5 R en apparence, mais +9,0 R seulement en execution      |
//|     reelle, soit MOINS que la base (+15,5). C'etait un artefact   |
//|     du moteur, qui entrait a la cloture de la bougie touchant le  |
//|     repli -- un robot ne peut pas faire ca. Rejet net.            |
//|   - point mort a +0,75 / +1,00 / +1,25 R : coupe la queue qui     |
//|     paie ; -3 a -12 R selon le seuil.                            |
//|   - TP a 1,0 R ou 2,0 R, stop a 1,5 ou 3,0 ATR : chacun echoue    |
//|     sur au moins une moitie. Le stop a 3,0 ATR est le plus        |
//|     trompeur : PF 3,21 et moities equilibrees en solo, mais       |
//|     +7,81 % seulement en portefeuille (contre +10,07) -- il prend |
//|     trop peu de trades pour meriter un siege sous le plafond.     |
//|   - plafond interne d'UNE position pour GrokBot (anti-            |
//|     concentration USD) : -0,68 pt de CAGR et rigoureusement rien  |
//|     en echange (creux et reussite inchanges). Le plafond de 2 de  |
//|     l'ecurie gere deja la correlation -- meme conclusion que le   |
//|     README avait tiree pour le plafond par sous-jacent.           |"""

VERSIONS = {
    # magics : bloc de l'ecurie L13 + les magics de la version elle-meme,
    # pour que le plafond de 2 positions compte TOUT le monde.
    "1": dict(dossier="GrokBot1", role=ROLE_V1, porte=PORTE_V1,
              magics="20261131,20261132,20261133,20261134,20261135",
              seul="""+15,5 R | PF 2,19 | 32 trades (3,1/an) | 59 % gagnants   |
//|      moities +4,5 R et +10,5 R                                  |""",
              fichiers=[("GrokBot1_USDJPY_D1.mq5", "USDJPY", "20268001", POURQUOI_USDJPY)]),
    "2": dict(dossier="GrokBot2", role=ROLE_V2, porte=PORTE_V2,
              magics="20261131,20261132,20261133,20261134,20261135,20268002,20268003",
              seul="""USDJPY +15,5 R (PF 2,19) | USDCHF +18,0 R (PF 2,50)      |
//|      moities USDJPY +4,5 / +10,5 ; USDCHF +7,0 / +12,0          |""",
              fichiers=[("GrokBot2_USDJPY_D1.mq5", "USDJPY", "20268002", POURQUOI_USDJPY),
                        ("GrokBot2_USDCHF_D1.mq5", "USDCHF", "20268003", POURQUOI_USDCHF)]),
}

# Les fragments de mecanisme sont vides : le banc n'a valide AUCUN ajout.
# Ils restent en place pour qu'une future GrokBot3 n'ait qu'a les remplir.
VIDE = dict(regle_v2="", inputs_v2="", etat_v2="", fonctions_v2="",
            affichage_v2="", lignes_v2="", init_v2="", tick_v2="", sortie_v2="")

def fabriquer(v, cfg, fichier, paire, magic, pourquoi):
    t = io.open(MODELE, encoding="utf-8").read()
    jetons = dict(VIDE)
    jetons.update({"@@VERSION@@": v, "@@FICHIER@@": fichier, "@@PAIRE@@": paire,
                   "@@SEUL@@": cfg["seul"], "@@PORTEFEUILLE@@": cfg["porte"],
                   "@@POURQUOI@@": pourquoi, "@@ROLE@@": cfg["role"],
                   "@@MAGICS@@": cfg["magics"]})
    for cle, val in jetons.items():
        if not cle.startswith("@@"):
            cle = "@@" + cle.upper() + "@@"
        t = t.replace(cle, val)
    t = t.replace("input long   NumeroMagique        = 20268001;",
                  "input long   NumeroMagique        = %s;" % magic)
    coupe = t.index("#property copyright")
    t = t[:coupe].replace("%%", "%") + t[coupe:]
    assert "@@" not in t, "fragment non remplace : %s" % fichier
    d = os.path.join(RACINE, "robots", cfg["dossier"])
    os.makedirs(d, exist_ok=True)
    chemin = os.path.join(d, fichier)
    io.open(chemin, "w", encoding="utf-8").write(t)
    return chemin, len(t.encode("utf-8"))

if __name__ == "__main__":
    for v in sorted(VERSIONS):
        cfg = VERSIONS[v]
        for fichier, paire, magic, pourquoi in cfg["fichiers"]:
            chemin, taille = fabriquer(v, cfg, fichier, paire, magic, pourquoi)
            print("ecrit %-42s %6d octets" % (os.path.relpath(chemin, RACINE), taille))
