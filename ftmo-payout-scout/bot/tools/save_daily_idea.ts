import { prompt } from "@grok/agent-sdk";
import { defineTool } from "@grok/agent-sdk/tools";
import * as z from "zod/v4";

type IdeaRecord = {
  date: string;
  headline: string;
  phase: "challenge" | "funded" | "sizing" | "scaling" | "portfolio";
  thesis: string;
  whyNotCemetery: string;
  testPlan: string;
  cashImpact: string;
  ftmoRisk: string;
  savedAt: string;
  sessionId: string;
};

type IdeaIndex = {
  dates: string[];
};

export default defineTool({
  description: prompt`
    Persist today's ONE concrete idea to pass more challenges / keep funded
    accounts alive / extract more legitimate FTMO Reward cash. Call once per
    daily run after checking cemetery + prior ideas.
  `,
  effect: "idempotent",
  inputSchema: z.object({
    date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
    headline: z.string().min(8).max(200),
    phase: z.enum([
      "challenge",
      "funded",
      "sizing",
      "scaling",
      "portfolio",
    ]),
    thesis: z.string().min(40).max(3000),
    whyNotCemetery: z
      .string()
      .min(20)
      .max(800)
      .describe("Why this is not a rejected lab idea"),
    testPlan: z
      .string()
      .min(40)
      .max(2000)
      .describe("Concrete next measurement: backtest / demo / free trial"),
    cashImpact: z
      .string()
      .min(20)
      .max(800)
      .describe("How this raises pass rate, survival, or Reward $/month"),
    ftmoRisk: z
      .string()
      .min(20)
      .max(800)
      .describe("FTMO rule / loss-limit risk if the idea is wrong"),
  }),
  async execute(input, ctx) {
    const record: IdeaRecord = {
      ...input,
      savedAt: new Date().toISOString(),
      sessionId: ctx.session.id,
    };

    const key = `idea:${input.date}`;
    await ctx.host.kv.put(key, record);
    await ctx.host.kv.put("idea:latest", { date: input.date, key });

    const index = ((await ctx.host.kv.get("idea:index")) as IdeaIndex | null) ?? {
      dates: [],
    };
    if (!index.dates.includes(input.date)) {
      index.dates.push(input.date);
      await ctx.host.kv.put("idea:index", index);
    }

    const path = `ideas/${input.date}.json`;
    await ctx.host.files.write(path, JSON.stringify(record, null, 2), {
      scope: "deployment",
    });

    return {
      saved: true,
      key,
      path,
      date: input.date,
      phase: input.phase,
    };
  },
});
