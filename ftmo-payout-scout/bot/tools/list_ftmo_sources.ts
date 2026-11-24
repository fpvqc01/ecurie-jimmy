import { prompt } from "@grok/agent-sdk";
import { defineTool } from "@grok/agent-sdk/tools";
import { FTMO_OFFICIAL_SOURCES } from "../lib/sources.js";

export default defineTool({
  description: prompt`
    List the curated official FTMO URLs this agent may fetch for payout,
    scaling, and challenge-rule research. Call this before fetch_ftmo_page
    when you need the day's starting set of sources.
  `,
  effect: "read",
  async execute() {
    return {
      sources: FTMO_OFFICIAL_SOURCES.map((s) => ({
        id: s.id,
        url: s.url,
        topic: s.topic,
      })),
      note: "Only https URLs on ftmo.com (and help/support subdomains) are allowed.",
    };
  },
});
