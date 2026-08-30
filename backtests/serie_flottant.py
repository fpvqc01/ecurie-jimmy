# -*- coding: utf-8 -*-
"""Produit la serie quotidienne AVEC LE FLOTTANT OUVERT — indispensable pour
appliquer la vraie regle FTMO du plancher quotidien.

POURQUOI CE FICHIER EXISTE
--------------------------
On ne peut PAS reconstruire le solde en compoundant la serie realisee (tjr) :
un trade ouvert AVANT le depart d'un challenge et ferme APRES verse tout son
gain d'un coup dans le solde, alors que l'equite n'a suivi que la partie
posterieure au depart. Mesure : la plus grosse journee realisee vaut +27,6 %
quand la plus grosse journee en mark-to-market vaut +9,2 %. Le solde depasse
alors l'equite de plus de 5 % et le challenge « meurt » d'une regle qui n'a
jamais ete enfreinte. C'est un artefact de la methode des departs glissants,
pas un fait de marche.

La solution : demander au moteur, chaque jour, combien de profit NON ENCAISSE
dort dans les positions ouvertes. Le solde de minuit se deduit alors sans
ambiguite, quel que soit le jour ou le challenge commence :

    solde_de_minuit = equite_de_minuit - flottant_de_minuit
"""
import io
import os
import sys

import pandas as pd

BT = r"C:\Users\jplou\Downloads\Ecurie_Jimmy_I2plus_partage\backtests"
if BT not in sys.path:
    sys.path.insert(0, BT)

_o = sys.stdout
sys.stdout = io.StringIO()
import CLASSEMENT_DEFINITIF as CD      # noqa: E402
import banc_L8 as B                    # noqa: E402
sys.stdout = _o


def instrumenter2(s):
    """Comme CD.instrumenter, plus : le flottant ouvert a la fin de chaque jour.

    Le cumul est tenu a jour de facon incrementale (O(1) par barre) : refaire
    la somme du dictionnaire pnl a chaque barre coutait ~750 millions
    d'operations sur la fenetre complete.
    """
    s.pnl_r = {}
    s.ouvertures = {}
    s.flot = {}
    s._run = 0.0
    s._cum0 = 0.0
    gerer0, ouvrir0, clore0 = s.gerer, s.ouvrir, s._clore

    def _maj(t):
        """flottant courant = cumul depuis l'ouverture, 0 si aucune position."""
        s.flot[t.date()] = (s._run - s._cum0) if s.pos is not None else 0.0

    def gerer(t):
        av = s.pnl.get(t, 0.0)
        gerer0(t)
        s._run += s.pnl.get(t, 0.0) - av
        _maj(t)

    def ouvrir(t, *a, **k):
        av = s.pnl.get(t, 0.0)
        r = ouvrir0(t, *a, **k)
        s._run += s.pnl.get(t, 0.0) - av
        if r and s.pos is not None:
            s._cum0 = s._run
            s.ouvertures[t.date()] = 1
        _maj(t)
        return r

    def _clore(t, prix):
        av = s.pnl.get(t, 0.0)
        clore0(t, prix)
        s._run += s.pnl.get(t, 0.0) - av
        s.pnl_r[t] = s.pnl_r.get(t, 0.0) + (s._run - s._cum0)
        _maj(t)

    s.gerer, s.ouvrir, s._clore = gerer, ouvrir, _clore
    return s


def series_flot(ns0, garde_be, debut, fin, alloc=None):
    """Retourne (cagr, dd, tj, tjr, tjo, tjf).

    tj  : rendements quotidiens marques au marche
    tjr : rendements quotidiens realises
    tjo : 1 si une position a ete OUVERTE ce jour-la
    tjf : FLOTTANT ouvert a la fin de la journee (fraction du compte)
    """
    ns, f_or, fab = ns0["ns"], ns0["f_or"], ns0["fab_l431"]
    boite = []

    def f():
        sl = fab()()
        a = B.ALLOC if alloc is None else alloc
        for s in sl:
            if s.nom in a:
                s.risque = a[s.nom]
        if garde_be:
            for s in sl:
                if s.nom in B.PYR:
                    B.breakeven(s, garde_be)
        for s in sl:
            instrumenter2(s)
        boite[:] = sl
        return sl

    ns["DEBUT"], ns["FIN"] = debut, fin
    ns["sleeves_l4"] = f
    r = ns["sim_h4"](interdit=f_or)

    tj = r[6].sort_index()
    realise, ouverts, flot = {}, {}, {}
    for s in boite:
        for tt, vv in s.pnl_r.items():
            j = tt.date()
            realise[j] = realise.get(j, 0.0) + vv
        for j in s.ouvertures:
            ouverts[j] = 1
        for j, vv in s.flot.items():
            flot[j] = flot.get(j, 0.0) + vv

    idx = tj.index
    tjr = pd.Series([realise.get(j.date(), 0.0) for j in idx], index=idx)
    tjo = pd.Series([ouverts.get(j.date(), 0) for j in idx], index=idx)
    tjf = pd.Series([flot.get(j.date(), 0.0) for j in idx], index=idx)
    return r[0], r[2], tj, tjr, tjo, tjf
