import { prompt } from "@grok/agent-sdk";
import { defineTool } from "@grok/agent-sdk/tools";
import { listKnowledgeDocs } from "../lib/knowledge.js";

export default defineTool({
  description: prompt`
    Return the cemetery of already-rejected Écurie Jimmy ideas. Always call
    this before proposing a new daily idea so you do not revive dead paths.
  `,
  effect: "read",
  async execute() {
    const docs = await listKnowledgeDocs();
    const cemetery = docs.find((d) => d.id === "cimetiere");
    if (!cemetery) {
      return { found: false as const, hint: "knowledge/cimetiere.md missing" };
    }
    return {
      found: true as const,
      path: cemetery.path,
      text: cemetery.text,
    };
  },
});
