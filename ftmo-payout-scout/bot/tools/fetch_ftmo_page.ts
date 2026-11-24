import { prompt } from "@grok/agent-sdk";
import { defineTool } from "@grok/agent-sdk/tools";
import * as z from "zod/v4";
import { htmlToText } from "../lib/html-text.js";
import { isAllowedFtmoUrl } from "../lib/sources.js";

export default defineTool({
  description: prompt`
    Fetch one official FTMO page (ftmo.com / help.ftmo.com / support.ftmo.com)
    and return cleaned text for payout, scaling, and rules analysis.
    Prefer list_ftmo_sources first. Never invent page content.
  `,
  effect: "read",
  inputSchema: z.object({
    url: z.string().url().describe("Full https URL on an allowed FTMO host"),
  }),
  async execute({ url }) {
    if (!isAllowedFtmoUrl(url)) {
      return {
        ok: false as const,
        error: "url_not_allowed",
        hint: "Only https://ftmo.com (and help/support subdomains) are allowed.",
        url,
      };
    }

    const response = await fetch(url, {
      redirect: "follow",
      headers: {
        "user-agent": "ftmo-payout-scout/0.1 (+legitimate-rules-research)",
        accept: "text/html,application/xhtml+xml",
      },
      signal: AbortSignal.timeout(20_000),
    });

    const finalUrl = response.url;
    if (!isAllowedFtmoUrl(finalUrl)) {
      return {
        ok: false as const,
        error: "redirect_not_allowed",
        hint: "Redirect left the FTMO allowlist.",
        url,
        finalUrl,
      };
    }

    if (!response.ok) {
      return {
        ok: false as const,
        error: "http_error",
        status: response.status,
        url,
        finalUrl,
      };
    }

    const html = await response.text();
    const text = htmlToText(html);

    return {
      ok: true as const,
      url,
      finalUrl,
      fetchedAt: new Date().toISOString(),
      charCount: text.length,
      text,
    };
  },
});
