# -*- coding: utf-8 -*-
"""SCAN COMPLET de tout le code de Jimmy (19 aout 2026) :
   1. Backtests MT4 : resultats + mecanismes verifies
   2. Coherence des sources MQL4 vs MQL5 (regles validees presentes partout)
   3. Integrite des templates (MT4 ASCII/CRLF, MT5 UTF-16/CRLF, balises)
   4. Etat des robots I2+ en production
   5. Pipeline Python
"""
import re, html, os, glob, io

MT4T = r"C:\Users\jplou\AppData\Local\Temp\claude\C--Users-jplou-Downloads\402ab065-414d-49fe-b7c5-31e3426fcd6c\scratchpad\MT4-Test"
MT4 = r"C:\Users\jplou\AppData\Roaming\MetaQuotes\Terminal\2C68BEE3A904BDCEE3EEF5A5A77EC162"
MT5 = r"C:\Users\jplou\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075"
probs = []


def titre(t):
    print()
    print("=" * 86)
    print(" " + t)
    print("=" * 86)


# ---------- 1. BACKTESTS ----------
titre("1. BACKTESTS MT4 (apres les 2 correctifs)")
TESTS = [("g_or", "XAUUSD Or H4"), ("g_cass", "BTC Cassure H4"), ("g_nas", "US100 Nasdaq H4"),
         ("g_ema", "BTC EMA H1"), ("g_oil", "USOIL Petrole D1")]
print("%-18s | %-9s | %-5s | %-15s | %-6s | %s" %
      ("Robot", "Profit", "PF", "Chute max", "Trades", "Periode"))
print("-" * 86)
logs = {}
for cle, etiq in TESTS:
    p = os.path.join(MT4T, "%s.htm" % cle)
    if not os.path.exists(p):
        print("%-18s | rapport absent" % etiq)
        probs.append("rapport %s absent" % etiq)
        continue
    t = open(p, "rb").read().decode("cp1252", errors="replace")
    cel = [html.unescape(re.sub("<[^>]+>", " ", c)).strip()
           for c in re.findall(r"<td[^>]*>(.*?)</td>", t, re.S)]
    cel = [c for c in cel if c]
    def v(k):
        for i in range(len(cel) - 1):
            if cel[i].startswith(k):
                return cel[i + 1]
        return "?"
    per = ""
    for c in cel:
        m = re.search(r"(\d{4}\.\d{2}\.\d{2}).*?(\d{4}\.\d{2}\.\d{2})", c)
        if m:
            per = "%s->%s" % (m.group(1)[:7], m.group(2)[:7])
            break
    print("%-18s | %-9s | %-5s | %-15s | %-6s | %s" % (
        etiq, v("Profit total net"), v("Facteur de profit"),
        v("Chute maximale"), v("Total des Trades"), per))
    lp = os.path.join(MT4T, "lg_%s.log" % cle)
    if os.path.exists(lp):
        logs[etiq] = open(lp, "rb").read().decode("cp1252", errors="replace").splitlines()

print()
print("%-18s | %-8s | %-10s | %-7s | %-10s | %-9s | %s" %
      ("Robot", "entrees", "re-entrees", "TP vus", "unites pyr", "gardien", "erreurs"))
print("-" * 86)
for etiq, L in logs.items():
    e = sum(1 for l in L if "ENTREE achat" in l)
    r = sum(1 for l in L if "re-entree)" in l)
    tp = sum(1 for l in L if "TP encaisse" in l)
    py = sum(1 for l in L if "PYRAMIDE" in l)
    pa = sum(1 for l in L if "PAUSE" in l)
    ar = sum(1 for l in L if "ARRET" in l)
    ec = sum(1 for l in L if "Echec" in l)
    err = sum(1 for l in L if re.search(r"\berror\b|invalid|failed", l, re.I))
    g = ("%dj" % pa if pa else "") + ("/ARRET" if ar else "")
    etat = "0" if (ec + err) == 0 else "!! %d" % (ec + err)
    if ec + err:
        probs.append("%s : %d erreurs dans le journal" % (etiq, ec + err))
    print("%-18s | %-8d | %-10d | %-7d | %-10d | %-9s | %s" %
          (etiq, e, r, tp, py, g if g else "-", etat))
    # coherence : une re-entree ne doit jamais depasser le nombre de TP
    if r > tp:
        probs.append("%s : %d re-entrees pour %d TP (desarmement ?)" % (etiq, r, tp))

# ---------- 2. COHERENCE DES SOURCES ----------
titre("2. COHERENCE DES SOURCES (regles validees presentes ?)")
REGLES = [
    ("gardien 2.5 %", r"(LimitePerteJourPct|DailyStopPct)\s*=\s*2\.5"),
    ("gardien total 8 %", r"(LimitePerteTotalePct|TotalStopPct)\s*=\s*8"),
    ("plafond ecurie 2", r"MaxPositionsEcurie\s*=\s*2"),
    ("cap par PILES", r"compte les PILES|vues"),
    ("magics 202609xx", r"2026091[578]"),
]
PYR = [("pyramidage 3 unites", r"MaxUnites\s*=\s*3"),
       ("pas 0,5 ATR", r"PasUniteATR\s*=\s*0\.5"),
       ("stop Turtle 2 ATR", r"StopSousDerniereUniteATR\s*=\s*2\.0")]
for etiquette, dossier, ext in (("MQL5 (Jimmy L3)", os.path.join(MT5, "MQL5", "Experts", "Jimmy L3"), "*.mq5"),
                                ("MQL4 (Jimmy L3)", os.path.join(MT4, "MQL4", "Experts", "Jimmy L3"), "*.mq4")):
    print("\n  --- %s ---" % etiquette)
    for f in sorted(glob.glob(os.path.join(dossier, ext))):
        t = open(f, encoding="utf-8", errors="replace").read()
        nom = os.path.basename(f)
        manques = [n for n, rx in REGLES if not re.search(rx, t)]
        cassure = "Cassure" in nom or "Petrole" in nom
        if cassure:
            manques += [n for n, rx in PYR if not re.search(rx, t)]
        # verifications specifiques
        if "Or_" in nom or "Nasdaq" in nom:
            if "attenteReentree = 0" not in t:
                manques.append("desarmement re-entree")
        if "LotSelonMarge" not in t and "AccountFreeMarginCheck" not in t:
            manques.append("verification de marge")
        if ext == "*.mq4" and "IsTesting()" not in t:
            manques.append("reset gardiens testeur")
        etat = "OK" if not manques else "MANQUE: " + ", ".join(manques)
        if manques:
            probs.append("%s : %s" % (nom, etat))
        print("    %-28s %s" % (nom, etat))

# ---------- 3. TEMPLATES ----------
titre("3. INTEGRITE DES TEMPLATES")
for etiquette, dossier, enc in (
        ("MT5 Jimmy L3", os.path.join(MT5, "MQL5", "Profiles", "Templates", "Jimmy L3"), "utf-16-le"),
        ("MT5 Jimmy I2+ (production)", os.path.join(MT5, "MQL5", "Profiles", "Templates", "Jimmy I2+"), "utf-16-le"),
        ("MT4 templates L3", MT4 + r"\templates", "cp1252")):
    print("\n  --- %s ---" % etiquette)
    motif = "*L3*.tpl" if "L3" in etiquette and "MT4" in etiquette else "*.tpl"
    for f in sorted(glob.glob(os.path.join(dossier, motif))):
        b = open(f, "rb").read()
        if enc == "utf-16-le":
            crlf = b.count("\r\n".encode(enc))
            lf = b.count("\n".encode(enc))
            t = b.decode(enc, errors="replace")
        else:
            crlf, lf = b.count(b"\r\n"), b.count(b"\n")
            t = b.decode(enc, errors="replace")
        colles = len(re.findall(r"></?\w+>", t))
        ea = re.search(r"name=([A-Za-z0-9_+]+)", t)
        souci = []
        if crlf != lf:
            souci.append("LF seuls")
        if colles:
            souci.append("%d balises collees" % colles)
        if not ea:
            souci.append("pas d'expert")
        etat = "OK" if not souci else "!! " + ", ".join(souci)
        if souci:
            probs.append("%s : %s" % (os.path.basename(f), etat))
        print("    %-32s %-26s %s" % (os.path.basename(f)[:32], ea.group(1)[:26] if ea else "-", etat))

# ---------- 4. PRODUCTION I2+ ----------
titre("4. ECURIE I2+ EN PRODUCTION (intacte et vivante ?)")
import datetime
for f in sorted(glob.glob(os.path.join(MT5, "MQL5", "Files", "Ecurie_Journal", "*I2+*.txt"))):
    lignes = open(f, encoding="ansi", errors="replace").read().splitlines()
    derniere = lignes[-1] if lignes else "(vide)"
    print("    %-28s %s" % (os.path.basename(f)[:28], derniere[:88]))

# ---------- 5. PIPELINE ----------
titre("5. PIPELINE DE DONNEES (les 2 terminaux servis ?)")
for term, sub in ((MT5, "MQL5"), (MT4, "MQL4")):
    for nom in ("macrobot_bias.txt", "macrobot_news.txt", "macrobot_vol.txt"):
        p = os.path.join(term, sub, "Files", nom)
        if os.path.exists(p):
            age = (datetime.datetime.now() - datetime.datetime.fromtimestamp(os.path.getmtime(p)))
            contenu = open(p, encoding="ascii", errors="replace").read().strip().splitlines()[0][:40]
            print("    %-6s %-22s %-42s (il y a %d min)" % (sub, nom, contenu, age.total_seconds() // 60))
        else:
            print("    %-6s %-22s ABSENT" % (sub, nom))
            probs.append("%s/%s absent" % (sub, nom))

# ---------- BILAN ----------
titre("BILAN DU SCAN")
if probs:
    print("  %d point(s) a regarder :" % len(probs))
    for p in probs:
        print("    - " + p)
else:
    print("  AUCUNE ERREUR DETECTEE sur l'ensemble du code et des configurations.")
