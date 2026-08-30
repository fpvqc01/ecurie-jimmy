# -*- coding: utf-8 -*-
"""A5 — LE TEST QUI TRANCHE. Ligne « R1 reference », avec et sans .shift(1)
sur le filtre DXY. Seuil de decision fixe d'avance : 0,5 point de CAGR."""
import io, os, sys
BT = r"C:\Users\jplou\Downloads\Ecurie_Jimmy_I2plus_partage\backtests"
sys.path.insert(0, BT); sys.path.insert(0, os.getcwd())
_o=sys.stdout; sys.stdout=io.StringIO()
import CLASSEMENT_DEFINITIF as CD
sys.stdout=_o
import SIM_FTMO_V2 as V2
from serie_flottant import series_flot
from regle_siege import charger3
CD.rediriger_vers_donnees()
DEB, FIN, PISTE = "2021-01-01", "2026-08-20", 730
ALLOC_R1 = {"Or":0.0075,"Nasdaq":0.0075,"Petrole":0.0169,"BTC Cassure":0.0169,"BTC EMA":0.0113}
ALLOC_DEC= {"Or":0.0102,"Nasdaq":0.0102,"Petrole":0.0169,"BTC Cassure":0.0115,"BTC EMA":0.0113}
FTMO2 = dict(cibles=(0.10,0.05), perte_jour=0.05, perte_totale=0.10, jours_min=4)
FLEX1 = dict(cibles=(0.10,), perte_jour=0.04, perte_totale=0.12, jours_min=0)

def run(alloc, shift, cap=2, libere=False, hm=9.9, mode="total"):
    s=sys.stdout; sys.stdout=io.StringIO()
    c,d,tj,tjr,tjo,tjf = series_flot(charger3(0.025,cap,libere,hm,mode,shift_dxy=shift),
                                     0.05, DEB, FIN, alloc=alloc)
    sys.stdout=s
    return c,d,tj.values.astype(float),tjo.values.astype(float),tjf.values.astype(float)

print("A5 — filtre DXY : avec et sans .shift(1). Fenetre %s -> %s\n" % (DEB, FIN))
print("%-42s %7s %8s | %7s %6s %6s | %7s %6s"
      % ("configuration","CAGR","creux","2-Step","med","<=60j","1 phase","med"))
print("-"*104)
for nom, alloc, cap, lib, hm, mode in (
        ("R1 reference", ALLOC_R1, 2, False, 9.9, "total"),
        ("R1 + regle siege/risque 2,5 %", ALLOC_R1, 99, True, 0.025, "capital"),
        ("R1 + allocation deconcentree", ALLOC_DEC, 2, False, 9.9, "total")):
    res={}
    for shift in (False, True):
        c,d,vm,vo,vf = run(alloc, shift, cap, lib, hm, mode)
        a=V2.simuler(vm,vf,vo,piste_min=PISTE,r13=True,regle="ftmo",gardien=0.010,**FTMO2)
        b=V2.simuler(vm,vf,vo,piste_min=PISTE,r13=True,regle="ftmo",gardien=0.010,**FLEX1)
        res[shift]=(c,d,a,b)
        etq = "%s — %s" % (nom, "AVEC shift (corrige)" if shift else "sans shift (actuel)")
        print("%-42s %+6.1f%% %7.1f%% | %6.1f%% %5.0fj %5.1f%% | %6.1f%% %5.0fj"
              % (etq, c, d, a["reussite"], a["duree_med"], a["p60"],
                 b["reussite"], b["duree_med"]))
    dc = res[True][0]-res[False][0]; dd = res[True][1]-res[False][1]
    print("%-42s ECART CAGR %+.2f pt   creux %+.2f pt   reussite %+.1f pt   mediane %+.0f j"
          % ("  ->", dc, dd, res[True][2]["reussite"]-res[False][2]["reussite"],
             res[True][2]["duree_med"]-res[False][2]["duree_med"]))
    print("%-42s %s" % ("  ->", "DEPASSE LE SEUIL DE 0,5 pt : republier" if abs(dc)>0.5
                        else "sous le seuil de 0,5 pt : on note et on passe"))
    print()
