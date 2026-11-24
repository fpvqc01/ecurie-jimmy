import { defineEval } from "@grok/agent-sdk/evals";

export default defineEval({
  tags: ["smoke"],
  description: "Checks cemetery then searches knowledge before proposing.",
  async test(t) {
    await t.send(
      "Donne l'idée du jour pour maximiser le cash FTMO via l'écurie. Vérifie d'abord le cimetière. Ne sauvegarde rien.",
    );
    t.succeeded();
    t.calledTool("list_rejected_ideas");
    t.calledTool("search_knowledge");
    t.notCalledTool("save_daily_idea");
  },
});
