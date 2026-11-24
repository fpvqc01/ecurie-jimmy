# ftmo-payout-scout

Agent quotidien (07:00 UTC) pour l’**Écurie Jimmy** : une idée concrète par jour
pour **réussir plus de challenges FTMO**, **garder des comptes financés**, et
**maximiser le cash légitime** (Rewards + scaling).

Ancré dans la connaissance locale du labo (`knowledge/`) — **pas** un scraper
FAQ FTMO.

## Démarrage

```bash
cd ftmo-payout-scout
npx @grok/agent-sdk login
npx @grok/agent-sdk validate --dir .
npx @grok/agent-sdk dev --dir .
```

Déclencher le cron en dev :

```bash
curl -X POST http://127.0.0.1:3000/ftmo-payout-scout/v1/dev/schedules/daily-payout-scout
```

## Outils

- `list_knowledge` / `search_knowledge` / `list_rejected_ideas`
- `list_prior_ideas` / `get_latest_idea` / `save_daily_idea`
