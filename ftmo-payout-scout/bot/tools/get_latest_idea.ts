import { prompt } from "@grok/agent-sdk";
import { defineTool } from "@grok/agent-sdk/tools";
import * as z from "zod/v4";

export default defineTool({
  description: prompt`
    Read a previously saved daily challenge/cash idea from host memory.
    Use before writing today's idea to avoid repeats and to build a sequence.
  `,
  effect: "read",
  inputSchema: z.object({
    date: z
      .string()
      .regex(/^\d{4}-\d{2}-\d{2}$/)
      .optional()
      .describe("UTC date YYYY-MM-DD; omit for latest"),
  }),
  async execute({ date }, ctx) {
    let key: string;
    if (date) {
      key = `idea:${date}`;
    } else {
      const latest = (await ctx.host.kv.get("idea:latest")) as
        | { date?: string; key?: string }
        | null;
      if (!latest?.key) {
        return { found: false as const, hint: "No idea saved yet." };
      }
      key = latest.key;
    }

    const idea = await ctx.host.kv.get(key);
    if (!idea) {
      return { found: false as const, key, hint: "No idea for that date." };
    }
    return { found: true as const, key, idea };
  },
});
