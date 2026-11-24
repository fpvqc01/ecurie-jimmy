import { prompt } from "@grok/agent-sdk";
import { defineTool } from "@grok/agent-sdk/tools";
import * as z from "zod/v4";

type IdeaIndex = {
  dates: string[];
};

export default defineTool({
  description: prompt`
    List dates/headlines of previously saved daily ideas so today's proposal
    does not repeat the same lever.
  `,
  effect: "read",
  inputSchema: z.object({
    limit: z.number().int().min(1).max(30).optional(),
  }),
  async execute({ limit }, ctx) {
    const index = ((await ctx.host.kv.get("idea:index")) as IdeaIndex | null) ?? {
      dates: [],
    };
    const dates = [...index.dates].sort().reverse().slice(0, limit ?? 14);
    const items = [];
    for (const date of dates) {
      const idea = (await ctx.host.kv.get(`idea:${date}`)) as {
        headline?: string;
        phase?: string;
      } | null;
      items.push({
        date,
        headline: idea?.headline ?? "(missing)",
        phase: idea?.phase ?? "unknown",
      });
    }
    return { count: items.length, items };
  },
});
