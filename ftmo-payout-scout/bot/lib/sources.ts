/** Official FTMO pages to scan for payout / scaling / rules updates. */
export const FTMO_OFFICIAL_SOURCES = [
  {
    id: "withdraw-profits",
    url: "https://ftmo.com/en/faq/how-do-i-withdraw-my-profits/",
    topic: "How to withdraw profits / request Rewards",
  },
  {
    id: "crypto-withdrawals",
    url: "https://ftmo.com/en/crypto-withdrawals/",
    topic: "Crypto withdrawal options",
  },
  {
    id: "scaling",
    url: "https://ftmo.com/en/reward-growth-and-scaling-plan/",
    topic: "Reward growth and scaling plan (up to 90% split)",
  },
  {
    id: "trading-objectives",
    url: "https://ftmo.com/en/trading-objectives/",
    topic: "Trading objectives and loss limits",
  },
  {
    id: "consistency-rule",
    url: "https://ftmo.com/en/faq/how-does-your-consistency-rule-work/",
    topic: "Consistency rule (affects Challenge / Instant)",
  },
  {
    id: "premium-scaling",
    url: "https://ftmo.com/en/faq/is-the-premium-programme-compatible-with-the-scaling-plan/",
    topic: "Premium programme vs Scaling Plan",
  },
] as const;

export const ALLOWED_HOST_SUFFIXES = [
  "ftmo.com",
  "help.ftmo.com",
  "support.ftmo.com",
] as const;

export function isAllowedFtmoUrl(raw: string): boolean {
  let parsed: URL;
  try {
    parsed = new URL(raw);
  } catch {
    return false;
  }
  if (parsed.protocol !== "https:") return false;
  const host = parsed.hostname.toLowerCase();
  return ALLOWED_HOST_SUFFIXES.some(
    (suffix) => host === suffix || host.endsWith(`.${suffix}`),
  );
}
