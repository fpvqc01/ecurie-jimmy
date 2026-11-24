import { defineAgent } from "@grok/agent-sdk";

export default defineAgent({
  name: "ftmo-payout-scout",
  description:
    "Daily Écurie Jimmy lab: one idea to pass more FTMO challenges and maximize legitimate funded Reward cash.",
  model: {
    id: "grok-4.7",
    params: [
      { id: "reasoning_effort", value: "high" },
      { id: "fast", value: "true" },
    ],
  },
});
