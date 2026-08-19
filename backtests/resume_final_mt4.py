# -*- coding: utf-8 -*-
"""Resume final des backtests MT4 apres les 2 corrections."""
import re, html, os

B = r"C:\Users\jplou\AppData\Local\Temp\claude\C--Users-jplou-Downloads\402ab065-414d-49fe-b7c5-31e3426fcd6c\scratchpad\MT4-Test"

TESTS = [("or3", "XAUUSD Or H4"), ("cass3", "BTC Cassure H4"),
         ("nas3", "US100 Nasdaq H4"), ("ema3", "BTC EMA H1")]

def val(cel, cle):
    for i in range(len(cel) - 1):
        if cel[i].startswith(cle):
            return cel[i + 1]
    return "?"

print("%-17s | %-9s | %-5s | %-15s | %-7s | %-9s" %
      ("Robot", "Profit", "PF", "Chute max", "Trades", "Periode"))
print("-" * 92)
details = []
for cle, etiq in TESTS:
    p = os.path.join(B, "rap_%s.htm" % cle)
    if not os.path.exists(p):
        print("%-17s | rapport absent" % etiq); continue
    t = open(p, "rb").read().decode("cp1252", errors="replace")
    cel = [html.unescape(re.sub("<[^>]+>", " ", c)).strip()
           for c in re.findall(r"<td[^>]*>(.*?)</td>", t, re.S)]
    cel = [c for c in cel if c]
    per = ""
    for c in cel:
        m = re.search(r"(\d{4}\.\d{2}\.\d{2}).*?(\d{4}\.\d{2}\.\d{2})", c)
        if m:
            per = "%s->%s" % (m.group(1)[:7], m.group(2)[:7]); break
    print("%-17s | %-9s | %-5s | %-15s | %-7s | %-9s" % (
        etiq, val(cel, "Profit total net"), val(cel, "Facteur de profit"),
        val(cel, "Chute maximale"), val(cel, "Total des Trades"), per))
    # mecanismes depuis le log
    lp = os.path.join(B, "lg_%s.log" % cle)
    if os.path.exists(lp):
        L = open(lp, "rb").read().decode("cp1252", errors="replace").splitlines()
        details.append((etiq, dict(
            entrees=sum(1 for l in L if "ENTREE achat" in l),
            reentrees=sum(1 for l in L if "re-entree)" in l),
            tp=sum(1 for l in L if "TP encaisse" in l),
            pyr=sum(1 for l in L if "PYRAMIDE" in l),
            pause=sum(1 for l in L if "PAUSE" in l),
            arret=sum(1 for l in L if "ARRET" in l),
            echecs=sum(1 for l in L if "Echec" in l))))

print()
print("MECANISMES VERIFIES DANS LES JOURNAUX")
print("%-17s | %-8s | %-10s | %-8s | %-9s | %-7s | %-6s" %
      ("Robot", "entrees", "re-entrees", "TP vus", "unites pyr", "gardien", "echecs"))
print("-" * 92)
for etiq, d in details:
    gard = []
    if d["pause"]: gard.append("%dj" % d["pause"])
    if d["arret"]: gard.append("ARRET")
    print("%-17s | %-8d | %-10d | %-8d | %-9d | %-7s | %-6d" % (
        etiq, d["entrees"], d["reentrees"], d["tp"], d["pyr"],
        "/".join(gard) if gard else "-", d["echecs"]))
