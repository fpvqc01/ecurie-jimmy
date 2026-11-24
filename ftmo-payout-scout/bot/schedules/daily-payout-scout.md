---
cron: "0 7 * * *"
---

Fais le briefing FTMO du jour (UTC).

1. Appelle `list_ftmo_sources`, puis `fetch_ftmo_page` sur chaque source pertinente
   (payouts / FAQ, scaling, trading objectives, challenge).
2. Appelle `get_latest_brief` pour comparer avec le dernier brief sauvegardé.
3. Rédige le briefing au format des instructions (changements, leviers payout
   légitimes, pièges règlement, sources).
4. Appelle `save_daily_brief` avec la date UTC du jour, un headline, le résumé,
   3 à 5 idées concrètes et conformes, les URLs utilisées, et une note de conformité.
5. Reste strictement dans le règlement FTMO — aucun contournement.
