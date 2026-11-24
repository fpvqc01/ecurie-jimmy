import { prompt } from "@grok/agent-sdk";
import { defineTool } from "@grok/agent-sdk/tools";
import * as z from "zod/v4";
import {
  excerptAround,
  listKnowledgeDocs,
  scoreDoc,
} from "../lib/knowledge.js";

export default defineTool({
  description: prompt`
    Search local Écurie Jimmy knowledge for challenge pass rate, funded-account
    survival, risk frontiers, rejected ideas, and cash/scaling tactics.
    Prefer this over inventing history the lab already tested.
  `,
  effect: "read",
  inputSchema: z.object({
    query: z.string().min(2).max(200),
    limit: z.number().int().min(1).max(8).optional(),
  }),
  async execute({ query, limit }) {
    const docs = await listKnowledgeDocs();
    const ranked = docs
      .map((doc) => ({
        id: doc.id,
        path: doc.path,
        title: doc.title,
        score: scoreDoc(doc, query),
        excerpt: excerptAround(doc.text, query),
      }))
      .filter((row) => row.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, limit ?? 4);

    return {
      query,
      matches: ranked,
      hint:
        ranked.length === 0
          ? "No local hit — broaden terms, or admit the lab has no data yet."
          : undefined,
    };
  },
});
