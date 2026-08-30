# -*- coding: utf-8 -*-
"""SIMULATEUR FTMO v2 (22 aout 2026) — CORRECTIF A1 : LE PLANCHER DU JOUR.

CE QUI CHANGE PAR RAPPORT A SIMULATEUR_FTMO.py
----------------------------------------------
L'ancien simulateur tuait le challenge sur `rm <= -PERTE_JOUR`, c'est-a-dire
« la journee a fait -5 % ». Ce n'est PAS la regle FTMO. La vraie regle est :

    plancher du jour = SOLDE a 00:00 CE(S)T  -  5 % du capital INITIAL
    mort si l'EQUITE passe sous ce plancher a n'importe quel moment

Deux differences, et elles ne vont pas dans le meme sens :

1. Le plancher est un MONTANT FIXE (5 % du capital de depart), pas un
   pourcentage de l'equite du jour. Quand le compte est monte a +8 %, un
   « -5 % de l'equite » vaut 5,4 % du capital initial : trop permissif.

2. La reference est le SOLDE (positions fermees), pas l'equite. Un suiveur
   de tendance passe minuit avec du flottant :
   - flottant POSITIF a minuit  -> l'equite peut redescendre du flottant EN
     PLUS des 5 % : la vraie regle est PLUS GENEREUSE que l'ancienne.
   - flottant NEGATIF a minuit  -> l'equite a deja mange une partie des 5 % :
     la vraie regle est PLUS SEVERE que l'ancienne. C'est le mode de mort
     no 1 signale par l'auditeur.

L'ancien simulateur se trompait donc dans LES DEUX SENS selon les jours. Il
fallait refaire les mesures, pas seulement corriger les robots.

CE QUI NE CHANGE PAS
--------------------
C1 objectif au SOLDE FERME · C2 aucun challenge jete · C3 jours de trading
comptes sur les OUVERTURES · C4 intervalles de confiance.

LIMITES CONNUES, TOUJOURS PRESENTES
-----------------------------------
Frontiere de journee en UTC et non a minuit CE(S)T ; le plancher est teste
sur l'equite de FIN de journee et non sur le plus bas intrajournalier. Les
taux restent des BORNES SUPERIEURES.

GARDIEN (option)
----------------
`gardien` modelise le coupe-circuit du robot APRES correctif A1 : des que
l'equite menace de passer sous `plancher + coussin`, le robot aplatit tout.
La journee est alors bornee a ce niveau au lieu de tuer le compte. C'est une
BORNE OPTIMISTE (elle suppose une execution parfaite, sans gap ni slippage) :
elle donne le gain MAXIMAL que le correctif A1 peut apporter.
"""
import math

import numpy as np

CIBLE_P1 = 0.10
CIBLE_P2 = 0.05
PERTE_JOUR = 0.05        # du capital INITIAL, montant fixe
PERTE_TOTALE = 0.10      # du capital INITIAL, statique
JOURS_MIN = 4

SUCCES, MORT, NON_RESOLU = 1, 0, -1
MORT_JOUR, MORT_TOTALE = "jour", "totale"


def phase(vm, vf, vo, i0, cible, r13=False, marge=0.0025,
          regle="ftmo", gardien=None, perte_jour=None, perte_totale=None,
          jours_min=None, flot0=0.0, turbo=None):
    """Joue une phase. Retourne (issue, duree_en_jours, cause).

    vm  : rendements quotidiens MARQUES AU MARCHE   -> equite
    vf  : FLOTTANT ouvert a la fin de chaque jour   -> solde = equite - flottant
    vo  : 1 si une position a ete OUVERTE ce jour-la
    regle : "ftmo"     -> plancher = solde_de_minuit - 5 % du capital initial
            "ancienne" -> mort si la journee fait -5 % (l'ancien simulateur)
    gardien : coussin en fraction (ex. 0.01 = 1 %). Le robot aplatit a
              plancher + coussin au lieu de mourir. None = pas de gardien.
    flot0 : flottant reporte au tout premier jour. 0 = le compte demarre a
            plat, ce qui est la seule situation reelle : on n'herite jamais
            d'une position en achetant un challenge.

    LE SOLDE N'EST PLUS COMPOUNDE DEPUIS LA SERIE REALISEE. On le deduit du
    flottant : solde = equite - flottant. C'est ce qui elimine l'artefact des
    departs glissants (un trade ouvert avant le depart versait tout son gain
    d'un coup dans le solde, qui depassait alors l'equite de plus de 5 % et
    tuait le challenge sur une regle jamais enfreinte).
    """
    pj = PERTE_JOUR if perte_jour is None else perte_jour
    pt = PERTE_TOTALE if perte_totale is None else perte_totale
    jmin = JOURS_MIN if jours_min is None else jours_min

    eq = 1.0        # equite (flottant inclus)
    flot = flot0    # profit non encaisse qui dort dans les positions ouvertes
    jt = 0
    for j in range(i0, len(vm)):
        # TURBO (L6+) : le risque est multiplie tant que l'equite de la phase
        # n'a pas atteint le coussin. ATTENTION - CE N'EST PAS UNE MESURE :
        # multiplier la serie apres coup ne dit pas quels stops auraient ete
        # touches, et le gardien quotidien, lui, ne se multiplie PAS (il coupe
        # au meme % du compte, donc plus tot en mouvement de prix). L'erreur va
        # dans les DEUX sens : pessimiste sur les pertes, optimiste sur les
        # journees que le gardien aurait aplaties. Borne, pas mesure.
        m = 1.0
        if turbo is not None and eq < 1.0 + turbo[1]:
            m = turbo[0]

        eq_minuit = eq
        bal_minuit = eq_minuit * (1.0 - flot * m)   # reference FTMO a 00:00
        if vo is not None:
            jt += int(vo[j])
        elif vm[j] != 0.0:
            jt += 1

        eq_fin = eq * (1.0 + vm[j] * m)

        if regle == "ftmo":
            plancher = bal_minuit - pj          # capital initial = 1.0
        else:
            plancher = eq_minuit * (1.0 - pj)   # ancienne regle (fausse)

        if eq_fin <= plancher:
            if gardien is not None:
                # Le robot a coupe avant : tout est ferme au niveau du coussin.
                niveau = plancher + gardien
                if eq_minuit > niveau:          # il avait la place de couper
                    eq, flot = niveau, 0.0
                    if eq <= 1.0 - pt:
                        return MORT, j - i0 + 1, MORT_TOTALE
                    continue
            return MORT, j - i0 + 1, MORT_JOUR

        eq = eq_fin
        flot = vf[j]
        bal = eq * (1.0 - flot * m)
        if eq <= 1.0 - pt:
            return MORT, j - i0 + 1, MORT_TOTALE
        if jt >= jmin:
            if r13:
                if eq >= 1.0 + cible + marge:
                    return SUCCES, j - i0 + 1, None
            elif bal >= 1.0 + cible:
                return SUCCES, j - i0 + 1, None
    return NON_RESOLU, len(vm) - i0, None


def challenge(vm, vf, vo, i0, r13=False, cibles=(CIBLE_P1, CIBLE_P2), **kw):
    """Enchaine les phases. Retourne (issue, duree_totale, cause)."""
    d_tot, pos = 0, i0
    for n, c in enumerate(cibles):
        # phase 1 : compte neuf, donc a plat. Phase 2 : le robot a tout ferme
        # a l'objectif (R13), donc a plat aussi.
        v, d, cause = phase(vm, vf, vo, pos, c, r13=r13, flot0=0.0, **kw)
        d_tot += d
        pos += d
        if v != SUCCES:
            return v, d_tot, cause
    return SUCCES, d_tot, None


def wilson(succes, n, z=1.96):
    if n <= 0:
        return (0.0, 100.0)
    p = succes / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    demi = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (100 * max(0.0, centre - demi), 100 * min(1.0, centre + demi))


def simuler(vm, vf, vo, pas=3, piste_min=730, r13=True,
            cibles=(CIBLE_P1, CIBLE_P2), depart_a_plat=True, **kw):
    """Departs glissants. Retourne un dictionnaire de resultats.

    depart_a_plat : n'ouvrir un challenge que les jours ou l'ecurie n'a AUCUNE
        position ouverte. C'est la seule situation reelle (on n'herite jamais
        d'un trade en achetant un challenge) et ca supprime le biais d'un
        compte qui encaisse le gain d'un trade qu'il n'a pas ouvert.
    """
    vm = np.asarray(vm, dtype=float)
    vf = np.asarray(vf, dtype=float)
    vo = None if vo is None else np.asarray(vo, dtype=float)
    n = len(vm)

    ok, mj, mt, nr = 0, 0, 0, 0
    durees, durees_echec = [], []
    for i0 in range(0, max(0, n - piste_min), pas):
        if depart_a_plat and i0 > 0 and abs(vf[i0 - 1]) > 1e-12:
            continue
        issue, duree, cause = challenge(vm, vf, vo, i0, r13=r13, cibles=cibles, **kw)
        if issue == SUCCES:
            ok += 1
            durees.append(duree)
        else:
            if cause == MORT_JOUR:
                mj += 1
            elif cause == MORT_TOTALE:
                mt += 1
            else:
                nr += 1
            durees_echec.append(duree)

    total = ok + mj + mt + nr
    p = 100.0 * ok / max(total, 1)
    a = np.array(durees) if durees else np.array([0])
    e = np.array(durees_echec) if durees_echec else np.array([0])
    duree_moy = float(np.mean(a)) if durees else float(piste_min)
    n_eff = max(1, int(n / max(duree_moy, 1)))
    bas, haut = wilson(p / 100 * n_eff, n_eff)
    esp = (float(np.median(a)) + (1 - p / 100) / max(p / 100, 1e-9) * float(np.median(e))
           if p > 0 else float("inf"))
    return dict(
        reussite=p, ic95=(bas, haut), n_departs=total, n_independants=n_eff,
        ok=ok, morts_jour=mj, morts_totale=mt, non_resolus=nr,
        duree_med=float(np.median(a)), duree_p10=float(np.percentile(a, 10)),
        duree_p90=float(np.percentile(a, 90)), esperance=min(esp, 9999.0),
        p30=100.0 * sum(1 for d in durees if d <= 30) / max(total, 1),
        p45=100.0 * sum(1 for d in durees if d <= 45) / max(total, 1),
        p60=100.0 * sum(1 for d in durees if d <= 60) / max(total, 1),
        p90j=100.0 * sum(1 for d in durees if d <= 90) / max(total, 1),
    )


EN_TETE = ("%-42s %7s %5s %5s %5s %5s %5s %6s %9s"
           % ("configuration", "reuss", "med", "p10", "<=30", "<=45", "<=60", "esper",
              "morts j/t"))


def ligne(nom, r):
    return ("%-42s %6.1f%% %4.0fj %4.0fj %4.1f%% %4.1f%% %4.1f%% %5.0fj %5d/%-4d"
            % (nom, r["reussite"], r["duree_med"], r["duree_p10"],
               r["p30"], r["p45"], r["p60"], r["esperance"],
               r["morts_jour"], r["morts_totale"]))
