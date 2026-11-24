import { prompt } from "@grok/agent-sdk";
import { defineTool } from "@grok/agent-sdk/tools";
import * as z from "zod/v4";

export default defineTool({
  description: prompt`
    Read a previously saved daily brief from host memory.
    Use before writing a new brief to highlight what changed since yesterday.
  `,
  effect: "read",
  inputSchema: z.object({
    date: z
      .string()
      .regex(/^\d{4}-\d{2}-\d{2}$/)
      .optional()
      .describe("UTC date YYYY-MM-DD; omit to load the latest brief"),
  }),
  async execute({ date }, ctx) {
    let key: string;
    if (date) {
      key = `brief:${date}`;
    } else {
      const latest = (await ctx.host.kv.get("brief:latest")) as
        | { date?: string; key?: string }
        | null;
      if (!latest?.key) {
        return { found: false as const, hint: "No brief saved yet." };
      }
      key = latest.key;
    }

    const brief = await ctx.host.kv.get(key);
    if (!brief) {
      return { found: false as const, key, hint: "No brief for that date." };
    }
    return { found: true as const, key, brief };
  },
});
