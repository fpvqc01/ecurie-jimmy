import { defineEval } from "@grok/agent-sdk/evals";

export default defineEval({
  tags: ["smoke"],
  description: "Lists official FTMO sources then fetches the FAQ page.",
  async test(t) {
    await t.send(
      "Liste les sources FTMO officielles, puis fetch la page FAQ. Ne sauvegarde rien.",
    );
    t.succeeded();
    t.calledTool("list_ftmo_sources");
    t.calledTool("fetch_ftmo_page");
    t.notCalledTool("save_daily_brief");
  },
});
