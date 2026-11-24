import { prompt } from "@grok/agent-sdk";
import { defineTool } from "@grok/agent-sdk/tools";
import { listKnowledgeDocs } from "../lib/knowledge.js";

export default defineTool({
  description: prompt`
    List the local Écurie Jimmy knowledge docs (system, cemetery of rejected
    ideas, FTMO cash constraints). Call this before search_knowledge.
  `,
  effect: "read",
  async execute() {
    const docs = await listKnowledgeDocs();
    return {
      docs: docs.map((d) => ({ id: d.id, path: d.path, title: d.title })),
    };
  },
});
