# -*- coding: utf-8 -*-
"""D9 tel que code vs D10. Challenge FTMO et compte finance.

Le moteur (banc_L13 / tests_comite_B) ne lit pas les .mq5. Il rejoue le
meme chassis, et on lui dit si les garde-fous voient les positions :

  D9 tel que code  — plafonds morts. ComptePositionsEcurie et
                     FamilleCorreleeOccupee cherchent 20261131-35 (L13)
                     alors que les robots D9 portent 20262091-95.
                     Le turbo x1,15 sous +6 % ne regarde pas la phase :
                     il reste actif en compte finance.
  D10              — plafonds actifs (plage derivee du magic de base).
                     Turbo x1,15 sous +6 % en challenge (phases 1 et 2).
                     Compte finance : facteur 1.

En challenge les deux versions ont le turbo : l'ecart ne vient que des
plafonds. En compte finance, les deux ecarts jouent en meme temps ; le
script ajoute la decomposition (chaque levier seul).

Le turbo du simulateur est une BORNE, pas une mesure : les rendements
journaliers sont multiplies apres coup. Les stops ne sont pas rejoues,
et le gardien journalier du moteur (1,25 %) ne bouge pas. Meme reserve
que SIM_FTMO_V2.
"""
import os
import sys
import time
import json

import numpy as np
import pandas as pd

D = os.path.dirname(os.path.abspath(__file__))
if D not in sys.path:
    sys.path.insert(0, D)

import banc_D9_analyse as A          # charge le chassis (banc_L13 patche)
L = A.L

ROBOTS = os.path.join(os.path.dirname(D), "robots")
TURBO = (1.15, 0.06)                  # x1,15 tant que l'equite de phase < +6 %
GARDIEN_FTMO = 0.010                  # coussin du simulateur, comme le banc D9
FTMO = dict(perte_jour=0.05, perte_totale=0.10, regle="ftmo",
            gardien=GARDIEN_FTMO)

# Chiffres deja mesures le 24 nov (resultats_banc_D9.json) pour controler
# que ce banc rejoue bien le meme chassis. On ne les publie pas a la place
# des chiffres de CETTE execution.
ATTENDU_D9_CODE = {
    "10 ans ": dict(cagr=20.103321813375263, dd=-12.475087181073407,
                    trades=432, reussite=84.28571428571429,
                    duree_med=284.5, morts_totale=44),
    "2021-26": dict(cagr=13.424007386426705, dd=-12.236916931215436,
                    trades=207, reussite=71.09375,
                    duree_med=412.0, morts_totale=37),
}
ATTENDU_D9_VOULU = {
    "10 ans ": dict(cagr=22.280241678102676, dd=-11.951666807923377,
                    trades=273, reussite=90.68825910931174,
                    duree_med=251.5, morts_totale=23),
    "2021-26": dict(cagr=17.984581906760155, dd=-10.586400947738117,
                    trades=150, reussite=88.9908256880734,
                    duree_med=297.0, morts_totale=12),
}


# --------------------------------------------------------------- sources .mq5
def _lire(dossier, nom):
    return open(os.path.join(ROBOTS, dossier, nom), encoding="utf-8").read()


def _fonction(src, nom):
    i = src.find(nom + "()")
    if i < 0:
        raise SystemExit("fonction absente : " + nom)
    j = src.find("\n  }\n", i)
    return src[i:j]


def verifier_sources():
    """Controle statique : le defaut D9 est bien dans les fichiers, et D10 le corrige."""
    d9 = {
        "BTCUSD_Cassure_D9_H1.mq5": "20262091",
        "BTCUSD_EMA_D9_D1.mq5": "20262092",
        "US100_Nasdaq_D9_H4.mq5": "20262093",
        "USOIL_Petrole_D9_H4.mq5": "20262094",
        "XAUUSD_Or_D9_H4.mq5": "20262095",
    }
    liste_l13 = "20261131 && m != 20261132 && m != 20261133 && m != 20261134 && m != 20261135"
    print("VERIFICATION DU CODE (lecture des .mq5, pas du moteur)")
    for nom, magic in d9.items():
        src = _lire("Jimmy D9", nom)
        n = src.count(liste_l13)
        turbo = _fonction(src, "double FacteurTurbo")
        if n != 2 or magic not in src or "PhaseActuelle" in turbo:
            raise SystemExit("portrait D9 inattendu : " + nom)
        print("  D9 %-32s magic %s | garde-fous : liste L13 x%d | turbo sans phase"
              % (nom, magic, n))

    d10 = {
        "BTCUSD_Cassure_D10_H1.mq5": "MAGIC_D10_CASSURE",
        "BTCUSD_EMA_D10_D1.mq5": "MAGIC_D10_EMA",
        "US100_Nasdaq_D10_H4.mq5": "MAGIC_D10_NASDAQ",
        "USOIL_Petrole_D10_H4.mq5": "MAGIC_D10_PETROLE",
        "XAUUSD_Or_D10_H4.mq5": "MAGIC_D10_OR",
    }
    mqh = _lire("Jimmy D10", "EcurieD10.mqh")
    if "MAGIC_ECURIE_D10  20262100" not in mqh or "NB_ROBOTS_ECURIE  5" not in mqh:
        raise SystemExit("base D10 absente")
    if mqh.count("2026113") or any(str(n) in mqh for n in range(20262091, 20262096)):
        raise SystemExit("le mqh D10 contient encore une liste de magics")
    for nom, macro in d10.items():
        src = _lire("Jimmy D10", nom)
        turbo = _fonction(src, "double FacteurTurbo")
        garde = (
            "#include \"EcurieD10.mqh\"" in src
            and src.count("MagicAppartientEcurie(m)") == 2
            and "20261131" not in src
            and macro in src
            and "MagicEcurieAccepte" in src
            and turbo.find("PhaseActuelle != PHASE_1") < turbo.find("TurboMultiplicateur")
            and "COMPTE_FINANCE" not in turbo.split("double FacteurTurbo")[0][-1:]
        )
        if not garde:
            raise SystemExit("portrait D10 inattendu : " + nom)
        # equilibre des accolades, parentheses, crochets (commentaires et chaines retires)
        equilibre(src, nom)
        print("  D10 %-32s %s | plage du mqh | turbo coupe hors phase 1/2" % (nom, macro))
    equilibre(mqh, "EcurieD10.mqh")
    print("  accolades / parentheses equilibrees sur les 5 .mq5 et le .mqh")
    print("  (pas de MetaEditor ici : ce controle ne remplace pas une compilation)")
    print()


def equilibre(src, nom):
    corps = _retirer_commentaires_chaines(src)
    piles = {")": "(", "]": "[", "}": "{"}
    ouvert = {"(": 0, "[": 0, "{": 0}
    ferme = {")": "(", "]": "[", "}": "{"}
    stack = []
    for i, ch in enumerate(corps):
        if ch in "([{":
            stack.append(ch)
        elif ch in ")]}":
            if not stack or stack[-1] != ferme[ch]:
                raise SystemExit("desequilibre %s vers l'octet %d de %s" % (ch, i, nom))
            stack.pop()
    if stack:
        raise SystemExit("accolades non fermees dans " + nom)
    # ouvert est la pour eviter un import inutile ; le stack suffit
    del piles, ouvert


def _retirer_commentaires_chaines(src):
    out = []
    i, n = 0, len(src)
    while i < n:
        if src.startswith("//", i):
            j = src.find("\n", i)
            if j < 0:
                break
            out.append("\n")
            i = j
            continue
        if src.startswith("/*", i):
            j = src.find("*/", i + 2)
            if j < 0:
                raise SystemExit("commentaire bloc non ferme")
            out.append(" ")
            i = j + 2
            continue
        if src[i] == '"':
            i += 1
            while i < n and src[i] != '"':
                if src[i] == "\\":
                    i += 2
                else:
                    i += 1
            i += 1
            out.append('""')
            continue
        if src[i] == "'":
            i += 1
            while i < n and src[i] != "'":
                if src[i] == "\\":
                    i += 2
                else:
                    i += 1
            i += 1
            out.append("''")
            continue
        out.append(src[i])
        i += 1
    return "".join(out)


# -------------------------------------------------------------------- series
def serie_complete(ns0, debut, fin, vus):
    """Meme serie que banc_L13, plus l'index de dates (pour les fenetres finance)."""
    dates = {}
    ns = ns0["ns"]
    reel = ns["sim_h4"]

    def enveloppe(*a, **k):
        r = reel(*a, **k)
        dates["idx"] = r[6].sort_index().index
        return r

    L.BE = 0.0
    orig = L.B.breakeven
    L.B.breakeven = lambda s, seuil: s          # D9 : breakeven collectif coupe
    ns["sim_h4"] = enveloppe
    try:
        res = L.serie(ns0, debut, fin, "entree", vus)
    finally:
        ns["sim_h4"] = reel
        L.B.breakeven = orig
    return res, pd.DatetimeIndex(dates["idx"])


def proche(obtenu, attendu, tol=1e-6):
    for k, v in attendu.items():
        if abs(float(obtenu[k]) - float(v)) > tol * max(1.0, abs(float(v))):
            return False
    return True


# ------------------------------------------------------------- compte finance
def jouer_finance(vm, vf, vo, turbo):
    """Une vie de compte finance : pas d'objectif de profit.

    jours_min enorme pour que SIM_FTMO_V2.phase ne declare jamais un succes
    de challenge. NON_RESOLU = le compte est encore la a la fin de la fenetre.
    Le turbo, s'il est fourni, suit la regle du code : x tant que l'equite
    est sous la baseline du chargement + coussin. Baseline = 1 au depart.
    """
    issue, duree, cause = L.V2.phase(
        vm, vf, vo, 0, cible=1e9, r13=True, marge=0.0,
        jours_min=10 ** 9, flot0=0.0, turbo=turbo, **FTMO)
    return int(issue), int(duree), cause


def simuler_finance(vm, vf, vo, idx, jours, turbo, pas=3):
    """Departs a plat, tous les `pas` jours, chacun joue `jours` calendaires."""
    vm = np.asarray(vm, dtype=float)
    vf = np.asarray(vf, dtype=float)
    vo = np.asarray(vo, dtype=float)
    n = len(vm)
    surv, mj, mt = 0, 0, 0
    i0 = 0
    while i0 < n:
        limite = idx[i0] + pd.Timedelta(days=jours)
        if idx[-1] < limite:
            break
        if i0 > 0 and abs(vf[i0 - 1]) > 1e-12:
            i0 += pas
            continue
        fin = int(np.searchsorted(idx, limite, side="right"))
        issue, _, cause = jouer_finance(vm[i0:fin], vf[i0:fin], vo[i0:fin], turbo)
        if issue == L.V2.MORT:
            if cause == L.V2.MORT_JOUR:
                mj += 1
            else:
                mt += 1
        else:
            surv += 1
        i0 += pas
    total = surv + mj + mt
    span = max(int((idx[-1] - idx[0]).days), 1)
    # Departs tous les 3 jours : ils se recouvrent. L'IC est calcule sur
    # n_eff = duree de la fenetre / horizon, pas sur n_departs.
    n_eff = max(1, int(span / jours))
    p = surv / max(total, 1)
    bas, haut = L.V2.wilson(p * n_eff, n_eff) if total else (0.0, 100.0)
    return dict(survie=100.0 * surv / max(total, 1), ic95=(bas, haut),
                n_departs=total, n_eff=n_eff,
                survies=surv, morts_jour=mj, morts_totale=mt, jours=jours)


def borne_turbo(vm, idx, turbo):
    """Multiple final et creux si on multiplie les rendements apres coup."""
    eq, pic, creux = 1.0, 1.0, 0.0
    for r in np.asarray(vm, dtype=float):
        m = 1.0
        if turbo is not None and eq < 1.0 + turbo[1]:
            m = turbo[0]
        eq *= (1.0 + r * m)
        pic = max(pic, eq)
        creux = min(creux, eq / pic - 1.0)
    jours = max(int((idx[-1] - idx[0]).days), 1)
    cagr = eq ** (365.25 / jours) - 1.0
    return dict(multiple=eq, cagr=100.0 * cagr, creux=100.0 * creux)


def fmt_challenge(r):
    return ("reussite %5.1f%% IC[%4.1f-%5.1f] med %4.0fj mortsJ %d mortsT %d ind %d"
            % (r["reussite"], r["ic95"][0], r["ic95"][1], r["duree_med"],
               r["morts_jour"], r["morts_totale"], r["n_independants"]))


def main():
    verifier_sources()
    print(L.CD.rediriger_vers_donnees())
    print("chassis D9 : gardien moteur 1,25 % | ancre roulante | breakeven collectif coupe")
    print("turbo challenge x1,15 sous +6 % | simulateur FTMO v2 | R13 | departs a plat")
    print()

    chassis = {}
    series = {}
    for morts, cle in ((True, "D9code"), (False, "D10")):
        t0 = time.time()
        chassis[cle] = A.charger(0.0125, morts)
        print("  chassis %s charge en %.1f s" % (cle, time.time() - t0), flush=True)

    for cle, morts in (("D9code", True), ("D10", False)):
        vus = set() if morts else set(L.ALLOC)
        for lib, deb, fin, piste in L.FENETRES:
            t0 = time.time()
            res, idx = serie_complete(chassis[cle], deb, fin, vus)
            series[(cle, lib)] = (res, idx, piste)
            print("  serie %-8s %s en %.1f s  (%d seances)"
                  % (cle, lib, time.time() - t0, len(idx)), flush=True)

    out = {"moteur": {}, "challenge": {}, "finance": {}, "compte_entier": {},
           "borne": {}, "controle": {}}

    print()
    print("MOTEUR (sans turbo : le turbo est applique ensuite par le simulateur)")
    for cle, etq in (("D9code", "D9 tel que code"), ("D10", "D10")):
        for lib, _, _, _ in L.FENETRES:
            (cagr, dd, vm, vo, vf, tr, gb), idx, piste = series[(cle, lib)]
            print("  %-18s %s CAGR %+6.1f%% creux %6.1f%% trades %4d giveback %.0f%%"
                  % (etq, lib, cagr, dd, tr, gb["part"]))
            out["moteur"]["%s | %s" % (etq, lib.strip())] = dict(
                cagr=cagr, dd=dd, trades=tr, giveback_part=gb["part"], seances=int(len(vm)))

    print()
    print("CHALLENGE 2-Step (10 % + 5 %). Turbo x1,15 / +6 % pour les DEUX :")
    print("D10 le garde en phase 1 et 2, donc l'ecart challenge = les plafonds seuls.")
    for cle, etq in (("D9code", "D9 tel que code"), ("D10", "D10")):
        for lib, _, _, _ in L.FENETRES:
            (cagr, dd, vm, vo, vf, tr, gb), idx, piste = series[(cle, lib)]
            t0 = time.time()
            r = L.V2.simuler(vm, vf, vo, piste_min=piste, r13=True,
                             turbo=TURBO, **L.FTMO, gardien=GARDIEN_FTMO)
            print("  %-18s %s %s (%.0fs)" % (etq, lib, fmt_challenge(r), time.time() - t0))
            ligne = dict(cagr=cagr, dd=dd, trades=tr, reussite=r["reussite"],
                         ic95=r["ic95"], duree_med=r["duree_med"], p60=r["p60"],
                         esperance=r["esperance"], morts_jour=r["morts_jour"],
                         morts_totale=r["morts_totale"], non_resolus=r["non_resolus"],
                         ind=r["n_independants"], n_departs=r["n_departs"])
            out["challenge"]["%s | %s" % (etq, lib.strip())] = ligne
            attendu = ATTENDU_D9_CODE if cle == "D9code" else ATTENDU_D9_VOULU
            ok = proche(dict(cagr=cagr, dd=dd, trades=tr, reussite=r["reussite"],
                             duree_med=r["duree_med"], morts_totale=r["morts_totale"]),
                        attendu[lib])
            ref = "analyse du 24 nov, D9 tel que code" if cle == "D9code" else \
                  "analyse du 24 nov, D9 voulu (plafonds actifs, meme turbo)"
            print("    controle vs %s : %s" % (ref, "identique" if ok else "ECART"))
            out["controle"]["%s | %s" % (etq, lib.strip())] = ok

    # Finance : 2 leviers x 2 etats. Seules deux cases sont des robots livres.
    cas_finance = (
        ("D9code", TURBO, "D9 tel que code (plafonds morts, turbo finance)"),
        ("D10", None, "D10 (plafonds actifs, turbo finance coupe)"),
        ("D9code", None, "decomposition : plafonds morts, turbo coupe"),
        ("D10", TURBO, "decomposition : plafonds actifs, turbo finance laisse"),
    )
    print()
    print("COMPTE FINANCE (pas d'objectif ; mort a -5 % du jour ou -10 % du capital initial,")
    print("gardien simulateur 1 %% au-dessus du plancher). Departs a plat tous les 3 jours.")
    print("IC95 sur n_eff = duree de la fenetre / horizon (departs qui se chevauchent).")
    for jours in (365, 1095):
        print()
        print("-- horizon %d jours calendaires --" % jours)
        for cle, turbo, etq in cas_finance:
            for lib, _, _, _ in L.FENETRES:
                (cagr, dd, vm, vo, vf, tr, gb), idx, piste = series[(cle, lib)]
                t0 = time.time()
                f = simuler_finance(vm, vf, vo, idx, jours, turbo)
                print("  %-52s %s survie %5.1f%% IC[%4.1f-%5.1f] departs %4d eff %2d mortsJ %d mortsT %d (%.0fs)"
                      % (etq, lib, f["survie"], f["ic95"][0], f["ic95"][1],
                         f["n_departs"], f["n_eff"], f["morts_jour"], f["morts_totale"],
                         time.time() - t0))
                clef = "%s | %dj | %s" % (etq, jours, lib.strip())
                out["finance"][clef] = f

    print()
    print("UN SEUL COMPTE, du premier jour de la fenetre jusqu'au bout.")
    print("Limite : la perte journaliere FTMO est 5 % du capital INITIAL, en montant fixe.")
    print("Une fois l'equite au-dela de ~4x, une journee de -1,25 % (le gardien moteur)")
    print("depasse ce montant. Le compte qui monte le plus vite meurt donc plus tot,")
    print("sans que ce soit un surcroit de risque. Les fenetres 365/1095 j, remises a 1,")
    print("sont la comparaison finance utilisable.")
    for cle, turbo, etq in cas_finance[:2]:
        for lib, _, _, _ in L.FENETRES:
            (cagr, dd, vm, vo, vf, tr, gb), idx, piste = series[(cle, lib)]
            issue, duree, cause = jouer_finance(vm, vf, vo, turbo)
            if issue == L.V2.MORT:
                issue_txt = "mort %s au jour %d" % (cause, duree)
            else:
                issue_txt = "survivant jusqu'au bout (%d seances)" % duree
            b = borne_turbo(vm, idx, turbo)
            b0 = borne_turbo(vm, idx, None)
            print("  %-52s %s %s | borne multiple x%.2f CAGR %+.1f%% creux %.1f%% (sans turbo x%.2f)"
                  % (etq, lib, issue_txt, b["multiple"], b["cagr"], b["creux"], b0["multiple"]))
            out["compte_entier"]["%s | %s" % (etq, lib.strip())] = dict(
                issue=issue_txt, duree=duree, cause=cause,
                borne=b, borne_sans_turbo=b0)
            out["borne"]["%s | %s" % (etq, lib.strip())] = b

    chemin = os.path.join(D, "resultats_banc_D10.json")
    json.dump(out, open(chemin, "w"), indent=1, default=float)
    print()
    print("json :", chemin)
    if not all(out["controle"].values()):
        print("ATTENTION : le controle vs l'analyse du 24 nov ne passe pas.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
