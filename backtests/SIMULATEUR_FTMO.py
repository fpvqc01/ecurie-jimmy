# -*- coding: utf-8 -*-
"""SIMULATEUR FTMO DE REFERENCE (21 aout 2026).

Remplace les simulateurs eparpilles dans banc_L8.py, verif_ftmo_l6.py,
banc_ecuries_L6*.py, classement_generations.py. Tous les futurs bancs
doivent importer celui-ci - c'est le point unique de verite.

LES 4 CORRECTIFS PAR RAPPORT AUX ANCIENS
----------------------------------------
C1. OBJECTIF AU SOLDE FERME.
    FTMO ecrit noir sur blanc : « You will meet this objective once your
    account BALANCE exceeds the Initial Simulated Capital by the required
    Profit Target WITH ALL POSITIONS CLOSED. » Les anciens simulateurs
    validaient la phase sur l'EQUITE (profit flottant inclus). Pour une
    strategie a pyramide qui porte beaucoup de flottant, c'est un biais
    massivement optimiste : au moment ou l'equite touche +10 %, le solde
    ferme n'est qu'a +0,1 a +2,3 %.
    Ici : les PERTES sont jugees sur l'equite (correct, FTMO compte le
    flottant pour les pertes), l'OBJECTIF sur le solde ferme.

C2. LES CHALLENGES NON RESOLUS NE SONT PLUS JETES.
    Les anciens faisaient `if v == -1: continue` - ils retiraient du
    denominateur les challenges qui n'avaient pas fini avant la fin des
    donnees, c'est-a-dire exactement les LENTS. Effet mesure : jusqu'a
    23 % des departs jetes, et de facon ASYMETRIQUE entre variantes, au
    point d'inverser des classements.
    Ici : on n'ouvre un challenge que s'il a `piste_min` jours devant lui.
    La censure est nulle PAR CONSTRUCTION, et le nombre de departs
    ecartes faute de piste est affiche.

C3. LES JOURS DE TRADING SONT COMPTES CORRECTEMENT.
    FTMO : « A Trading Day is any day during which at least one position
    is OPENED. » Les anciens comptaient tout jour ou le P&L bougeait -
    donc une position tenue 10 jours valait 10 jours de trading au lieu
    de 1. Ici : compteur d'OUVERTURES fourni par l'appelant.

C4. L'INCERTITUDE EST AFFICHEE.
    Les departs glissants tous les 3 jours se chevauchent d'un facteur
    ~70. « 89 % sur 1 229 departs » n'est pas 1 229 essais : c'est
    l'equivalent de ~16-18 challenges independants, donc un intervalle
    de confiance d'environ +/- 10 points. Le simulateur calcule et
    affiche n_eff et l'intervalle de Wilson.

LIMITE CONNUE, NON CORRIGEE ICI
-------------------------------
La frontiere de journee est celle de la serie fournie (date UTC), alors
que FTMO remet le compteur a zero a minuit CE(S)T (22 h UTC l'ete, 23 h
l'hiver). La barre 20 h-24 h UTC porte 6 a 13 % du mouvement journalier
median selon le marche. Corriger demande de re-agreger depuis les barres
H4 - a faire dans un second temps. Le biais est modere et connu.
De meme, la regle -5 %/jour est testee sur le total du jour et non sur le
minimum intrajournalier : FTMO, lui, surveille « the absolute lowest
point ... even for a split second ». Les taux de reussite sont donc des
BORNES SUPERIEURES.
"""
import math

import numpy as np

# Regles FTMO 2-Step (verifiees sur ftmo.com le 21 aout 2026)
CIBLE_P1 = 0.10
CIBLE_P2 = 0.05
PERTE_JOUR = 0.05
PERTE_TOTALE = 0.10
JOURS_MIN = 4

SUCCES, MORT, NON_RESOLU = 1, 0, -1
MORT_JOUR, MORT_TOTALE = "jour", "totale"


def phase(vm, vr, vo, i0, cible, r13=False, marge=0.0025, turbo=None, cppi=None):
    """Joue une phase. Retourne (issue, duree_en_jours, cause_de_mort).

    vm : rendements quotidiens MARQUES AU MARCHE  -> pertes (C1)
    vr : rendements quotidiens REALISES           -> objectif (C1)
    vo : 1 si au moins une position a ete OUVERTE ce jour-la (C3)
    turbo : (multiplicateur, seuil) - le risque est multiplie tant que
            l equite de la phase n a pas atteint 1 + seuil.
    cppi  : (maxi, plancher_pct, mini) - exposition PROPORTIONNELLE au
            coussin au-dessus du plancher, formule exacte du robot S3 :
                m = (equite - (1 - plancher)) / plancher, borne [mini, maxi]
            C est l INVERSE du turbo : petit pres du gouffre, plein quand
            le coussin est fait. Grossman-Zhou (1993). Meme approximation
            de mesure que le turbo (applique a la serie, pas aux stops).

    ATTENTION - APPROXIMATION CONNUE SUR LE TURBO
    Multiplier la serie de rendements APRES COUP n est pas une mesure :
    changer la taille des positions change quels stops sont touches, donc
    la serie elle-meme. Les chiffres turbo sont une BORNE OPTIMISTE. Le
    projet avait deja identifie ce defaut pour le mecanisme M3 ; il vaut
    exactement pareil ici. Pour une vraie mesure il faudrait rejouer le
    moteur, ce qui suppose que le moteur connaisse l etat du challenge.
    """
    eq = 1.0
    bal = 1.0
    jt = 0
    for j in range(i0, len(vm)):
        m = 1.0
        if cppi is not None:
            maxi_c, planch_c, mini_c = cppi
            m = (eq - (1.0 - planch_c)) / planch_c
            if m < mini_c:
                m = mini_c
            if m > maxi_c:
                m = maxi_c
        elif turbo is not None:
            mult_t, seuil_t = turbo
            if eq < 1.0 + seuil_t:
                m = mult_t
        rm = vm[j] * m
        if vo is not None:
            jt += int(vo[j])
        elif rm != 0.0:
            jt += 1                      # repli si l'appelant n'a pas vo
        if rm <= -PERTE_JOUR:
            return MORT, j - i0 + 1, MORT_JOUR
        eq *= (1.0 + rm)
        bal *= (1.0 + vr[j] * m)
        if eq <= 1.0 - PERTE_TOTALE:
            return MORT, j - i0 + 1, MORT_TOTALE
        if jt >= JOURS_MIN:
            if r13:
                # R13 : le robot FERME TOUT des que l equite depasse
                # l objectif + un coussin (spread/commission a l encaissement).
                # Fermer realise le flottant, donc le solde rejoint l equite :
                # la phase est validee. C est la modelisation fidele du robot.
                if eq >= 1.0 + cible + marge:
                    return SUCCES, j - i0 + 1, None
            elif bal >= 1.0 + cible:
                return SUCCES, j - i0 + 1, None
    return NON_RESOLU, len(vm) - i0, None


def challenge(vm, vr, vo, i0, r13=False, turbo=None, cppi=None):
    """Phase 1 puis phase 2. Retourne (issue, duree_totale, cause)."""
    v1, d1, c1 = phase(vm, vr, vo, i0, CIBLE_P1, r13, turbo=turbo, cppi=cppi)
    if v1 != SUCCES:
        return v1, d1, c1
    v2, d2, c2 = phase(vm, vr, vo, i0 + d1, CIBLE_P2, r13, turbo=turbo, cppi=cppi)
    if v2 != SUCCES:
        return v2, d1 + d2, c2
    return SUCCES, d1 + d2, None


def wilson(succes, n, z=1.96):
    """Intervalle de confiance de Wilson (fiable sur petits echantillons)."""
    if n <= 0:
        return (0.0, 100.0)
    p = succes / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    demi = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (100 * max(0.0, centre - demi), 100 * min(1.0, centre + demi))


def simuler(tj, tjr, tjo=None, pas=3, piste_min=730, r13=False, turbo=None, cppi=None):
    """Simule tous les challenges a departs glissants.

    piste_min : jours garantis devant chaque depart. Aucun challenge
                n'est jete faute de donnees (C2). Mettre 0 pour revenir
                a l'ancien comportement (deconseille).

    Retourne un dictionnaire de resultats.
    """
    vm = np.asarray(tj.values if hasattr(tj, "values") else tj, dtype=float)
    vr = np.asarray(tjr.values if hasattr(tjr, "values") else tjr, dtype=float)
    vo = None
    if tjo is not None:
        vo = np.asarray(tjo.values if hasattr(tjo, "values") else tjo, dtype=float)

    n = len(vm)
    dernier_depart = n - piste_min
    ecartes = max(0, (n - 1) // pas + 1 - (max(0, dernier_depart - 1) // pas + 1))

    ok = 0
    morts = {MORT_JOUR: 0, MORT_TOTALE: 0}
    non_resolus = 0
    durees = []
    durees_echec = []

    for i0 in range(0, max(0, dernier_depart), pas):
        issue, duree, cause = challenge(vm, vr, vo, i0, r13, turbo, cppi)
        if issue == SUCCES:
            ok += 1
            durees.append(duree)
        elif issue == MORT:
            morts[cause] = morts.get(cause, 0) + 1
            durees_echec.append(duree)
        else:
            non_resolus += 1          # ne devrait pas arriver si piste_min suffit
            durees_echec.append(duree)

    total = ok + morts[MORT_JOUR] + morts[MORT_TOTALE] + non_resolus
    taux = 100.0 * ok / max(total, 1)

    # C4 : combien de challenges VRAIMENT independants ?
    duree_moy = float(np.mean(durees)) if durees else float(piste_min)
    n_eff = max(1, int(n / max(duree_moy, 1)))
    bas, haut = wilson(ok / max(total, 1) * n_eff, n_eff)

    d = np.array(durees) if durees else np.array([0])
    return {
        "reussite": taux,
        "ic95": (bas, haut),
        "n_departs": total,
        "n_independants": n_eff,
        "ok": ok,
        "morts_jour": morts[MORT_JOUR],
        "morts_totale": morts[MORT_TOTALE],
        "non_resolus": non_resolus,
        "ecartes_piste": ecartes,
        "duree_med": float(np.median(d)),
        "duree_p10": float(np.percentile(d, 10)),
        "duree_p25": float(np.percentile(d, 25)),
        "duree_p75": float(np.percentile(d, 75)),
        "duree_p90": float(np.percentile(d, 90)),
        "duree_echec_med": float(np.median(durees_echec)) if durees_echec else 0.0,
    }


def esperance_jours(res):
    """Delai espere jusqu'au compte finance, rachats compris.

    E = T_succes + (1-p)/p * T_echec
    C'est le seul chiffre qui compte pour la tresorerie : un challenge
    rate se repaye et se recommence.
    """
    p = res["reussite"] / 100.0
    if p <= 0:
        return float("inf")
    return res["duree_med"] + (1 - p) / p * res["duree_echec_med"]


def formater(nom, res):
    e = esperance_jours(res)
    return ("%-28s %5.1f %% [%4.1f-%5.1f]  med %4.0f j  "
            "p90 %4.0f j  esp %4.0f j  morts %d/%d  n_ind %d"
            % (nom, res["reussite"], res["ic95"][0], res["ic95"][1],
               res["duree_med"], res["duree_p90"], e,
               res["morts_jour"], res["morts_totale"], res["n_independants"]))


EN_TETE = ("%-28s %-20s %-11s %-11s %-11s %-12s %s"
           % ("configuration", "reussite [IC95]", "mediane", "p90",
              "esperance", "morts j/tot", "n_ind"))
