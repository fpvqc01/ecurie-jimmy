# ftmo-payout-scout

Agent Agent SDK qui, chaque jour (07:00 UTC), lit les pages officielles FTMO
et produit un briefing sur les leviers **légitimes** pour maximiser les
retraits / payouts (règles, scaling, objectifs, fréquence).

Ce n’est **pas** un outil de fraude ni de contournement des ToS FTMO.

## Démarrage local

```bash
cd ftmo-payout-scout
npx @grok/agent-sdk login          # une fois
npx @grok/agent-sdk validate --dir .
npx @grok/agent-sdk dev --dir .    # playground
```

Déclencher le cron à la main en mode dev :

```bash
curl -X POST http://127.0.0.1:3000/ftmo-payout-scout/v1/dev/schedules/daily-payout-scout
```

## Outils

- `list_ftmo_sources` — URLs officielles curatées
- `fetch_ftmo_page` — fetch allowlisté `ftmo.com`
- `get_latest_brief` / `save_daily_brief` — mémoire jour après jour
