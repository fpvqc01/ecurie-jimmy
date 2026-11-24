import { prompt } from "@grok/agent-sdk";
import { defineTool } from "@grok/agent-sdk/tools";
import * as z from "zod/v4";

type BriefRecord = {
  date: string;
  headline: string;
  summary: string;
  ideas: string[];
  sources: string[];
  complianceNote: string;
  savedAt: string;
  sessionId: string;
};

export default defineTool({
  description: prompt`
    Persist today's FTMO payout-maximization brief (legitimate rules only)
    into host memory so later sessions can compare day-over-day changes.
    Call this once per daily run after you have evidence from fetch_ftmo_page.
  `,
  effect: "idempotent",
  inputSchema: z.object({
    date: z
      .string()
      .regex(/^\d{4}-\d{2}-\d{2}$/)
      .describe("UTC calendar date YYYY-MM-DD"),
    headline: z.string().min(8).max(200),
    summary: z.string().min(40).max(4000),
    ideas: z
      .array(z.string().min(8).max(500))
      .min(1)
      .max(8)
      .describe("Concrete legitimate tactics grounded in FTMO rules"),
    sources: z.array(z.string().url()).min(1).max(12),
    complianceNote: z
      .string()
      .min(20)
      .max(500)
      .describe("Explicit reminder that advice stays inside FTMO ToS"),
  }),
  async execute(input, ctx) {
    const record: BriefRecord = {
      ...input,
      savedAt: new Date().toISOString(),
      sessionId: ctx.session.id,
    };

    const key = `brief:${input.date}`;
    await ctx.host.kv.put(key, record);
    await ctx.host.kv.put("brief:latest", { date: input.date, key });

    const path = `briefs/${input.date}.json`;
    await ctx.host.files.write(path, JSON.stringify(record, null, 2), {
      scope: "deployment",
    });

    return {
      saved: true,
      key,
      path,
      date: input.date,
      ideaCount: input.ideas.length,
    };
  },
});
