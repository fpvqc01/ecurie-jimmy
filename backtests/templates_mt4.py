# -*- coding: utf-8 -*-
"""Genere les 5 modeles MT4 de l'ecurie L3 : robot integre + indicateurs
visibles (EMA, RSI, ATR, canal Donchian selon le robot).
Format MT4 : ASCII, CRLF, chaque balise sur sa ligne."""
import os

DST = r"C:\Users\jplou\AppData\Roaming\MetaQuotes\Terminal\2C68BEE3A904BDCEE3EEF5A5A77EC162\templates"
DL = r"C:\Users\jplou\Downloads\Ecurie_L3_MT4\templates"
os.makedirs(DL, exist_ok=True)

CHART = """<chart>
symbol={symbole}
period={periode}
digits={digits}
scale=8
graph=1
fore=0
grid=0
volume=0
scroll=1
shift=1
ohlc=1
askline=0
days=0
descriptions=0
shift_size=20
fixed_pos=0
window_left=0
window_top=0
window_right=800
window_bottom=400
window_type=1
background_color=0
foreground_color=16777215
barup_color=65280
bardown_color=255
bullcandle_color=0
bearcandle_color=255
chartline_color=16777215
volumes_color=32768
grid_color=10061943
askline_color=16777215
stops_color=17919
"""

EXPERT = """<expert>
name={nom_ea}
flags=343
window_num=0
<inputs>
{inputs}</inputs>
</expert>
"""

FENETRE_PRINCIPALE = """<window>
height=100
<indicator>
name=main
</indicator>
{indicateurs}</window>
"""

def ema(periode, couleur):
    return """<indicator>
name=Moving Average
period=%d
shift=0
method=1
apply=0
color=%d
style=0
weight=2
period_flags=0
show_data=1
</indicator>
""" % (periode, couleur)

def canal(haut, bas):
    return """<indicator>
name=Custom Indicator
<expert>
name=Canal_Donchian
flags=0
window_num=0
<inputs>
PeriodeHaut=%d
PeriodeBas=%d
</inputs>
</expert>
period_flags=0
show_data=1
</indicator>
""" % (haut, bas)

def fenetre_rsi(periode=14):
    return """<window>
height=40
<indicator>
name=Relative Strength Index
period=%d
apply=0
color=16748574
style=0
weight=1
levels_color=12632256
levels_style=2
levels_weight=1
level_0=30
level_1=70
period_flags=0
show_data=1
</indicator>
</window>
""" % periode

def fenetre_atr(periode=14):
    return """<window>
height=30
<indicator>
name=Average True Range
period=%d
color=16776960
style=0
weight=1
period_flags=0
show_data=1
</indicator>
</window>
""" % periode

MODELES = [
    dict(fichier="jimmy btc ema L3 H1.tpl", symbole="BTCUSD", periode=60, digits=2,
         nom_ea="BTCUSD_EMA_L3_H1",
         inputs="RisqueParTradePct=0.75\nLimitePerteJourPct=2.5\nPeriodeRapide=20\nPeriodeLente=50\nMultiplicateurSL=2.0\nMultiplicateurTP=4.0\nRetraceReentreeATR=0.25\n",
         indicateurs=ema(20, 65535) + ema(50, 255), sous=fenetre_atr()),
    dict(fichier="jimmy or L3 H4.tpl", symbole="XAUUSD", periode=240, digits=2,
         nom_ea="XAUUSD_Or_L3_H4",
         inputs="RisqueParTradePct=3.0\nLimitePerteJourPct=2.5\nSwingLookback=60\nFibLo=0.20\nFibHi=0.80\nRsiPull=55.0\nStopAtrMult=3.0\nTpR=1.5\nRetraceReentree=0.25\nBreakevenActif=true\n",
         indicateurs="", sous=fenetre_rsi() + fenetre_atr()),
    dict(fichier="jimmy nasdaq L3 H4.tpl", symbole="US100.cash", periode=240, digits=2,
         nom_ea="US100_Nasdaq_L3_H4",
         inputs="RisqueParTradePct=1.5\nLimitePerteJourPct=2.5\nSwingLookback=40\nFibLo=0.10\nFibHi=0.90\nRsiPull=60.0\nStopAtrMult=2.0\nTpR=1.0\nRetraceReentree=0.50\nBreakevenActif=true\n",
         indicateurs="", sous=fenetre_rsi() + fenetre_atr()),
    dict(fichier="jimmy btc cassure L3 H4.tpl", symbole="BTCUSD", periode=240, digits=2,
         nom_ea="BTCUSD_Cassure_L3_H4",
         inputs="RisqueParTradePct=0.75\nLimitePerteJourPct=2.5\nPeriodeEntree=55\nPeriodeSortie=20\nPyramidageActif=true\nMaxUnites=3\nPasUniteATR=0.5\nStopSousDerniereUniteATR=2.0\n",
         indicateurs=canal(55, 20), sous=fenetre_atr()),
    dict(fichier="jimmy petrole L3 D1.tpl", symbole="USOIL.cash", periode=1440, digits=2,
         nom_ea="USOIL_Petrole_L3_D1",
         inputs="RisqueParTradePct=0.75\nLimitePerteJourPct=2.5\nPeriodeEntree=20\nPeriodeSortie=10\nMoisDebutSaison=12\nMoisFinSaison=5\nPyramidageActif=true\nMaxUnites=3\nPasUniteATR=0.5\nStopSousDerniereUniteATR=2.0\n",
         indicateurs=canal(20, 10), sous=fenetre_atr()),
]

for m in MODELES:
    t = (CHART.format(symbole=m["symbole"], periode=m["periode"], digits=m["digits"])
         + EXPERT.format(nom_ea=m["nom_ea"], inputs=m["inputs"])
         + FENETRE_PRINCIPALE.format(indicateurs=m["indicateurs"])
         + m["sous"]
         + "</chart>\n")
    t = t.replace("\r\n", "\n").replace("\n", "\r\n")   # CRLF partout
    for dossier in (DST, DL):
        with open(os.path.join(dossier, m["fichier"]), "w", encoding="ascii", newline="") as f:
            f.write(t)
    # verification
    colles = t.count("><")
    nb_ind = t.count("<indicator>")
    print("  %-30s %s %s | %d indicateurs | balises collees:%d"
          % (m["fichier"], m["symbole"], m["periode"], nb_ind, colles))

print("\nVerification des fichiers ecrits :")
for m in MODELES:
    p = os.path.join(DST, m["fichier"])
    b = open(p, "rb").read()
    crlf = b.count(b"\r\n")
    lf = b.count(b"\n")
    ok = "OK" if crlf == lf else "PROBLEME LF"
    ea = "ea:oui" if m["nom_ea"].encode() in b else "EA MANQUANT"
    print("  %-30s %s | CRLF %d/%d %s" % (m["fichier"], ea, crlf, lf, ok))
