const JS_NOISE =
  /\b(document\.|window\.|classList|hoveredItem|activeItem|menuOpen|function\s*\(|=>|x-cloak|x-transition|@keydown|@mouse|@blur|@click|getElementById)\b/;

function decodeEntities(text: string): string {
  return text
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&quot;/gi, '"')
    .replace(/&#39;/gi, "'")
    .replace(/&#(\d+);/g, (_, n) => {
      const code = Number(n);
      return Number.isFinite(code) ? String.fromCodePoint(code) : " ";
    })
    .replace(/&#x([0-9a-f]+);/gi, (_, h) => {
      const code = Number.parseInt(h, 16);
      return Number.isFinite(code) ? String.fromCodePoint(code) : " ";
    });
}

function stripToLines(chunk: string): string[] {
  const rough = chunk
    .replace(/<\/(p|div|h[1-6]|li|tr|br|section|article)>/gi, "\n")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<[^>]+>/g, " ");

  return decodeEntities(rough)
    .split(/\n+/)
    .map((line) => line.replace(/[ \t]{2,}/g, " ").trim())
    .filter((line) => line.length >= 25)
    .filter((line) => !JS_NOISE.test(line))
    .filter((line) => !/^[{};()]+$/.test(line));
}

function pickContentRoot(htmlWithoutScripts: string): string {
  const patterns = [
    /<div[^>]*class="[^"]*faq-single-content[^"]*"[^>]*>[\s\S]*?<\/div>/i,
    /<main[\s\S]*?<\/main>/i,
    /<article[\s\S]*?<\/article>/i,
  ];
  for (const pattern of patterns) {
    const match = htmlWithoutScripts.match(pattern)?.[0];
    if (match && match.length > 200) return match;
  }
  return htmlWithoutScripts;
}

function metaDescription(html: string): string | undefined {
  const og = html.match(
    /<meta[^>]+property=["']og:description["'][^>]+content=["']([^"']+)["']/i,
  );
  if (og?.[1]) return decodeEntities(og[1]).trim();
  const name = html.match(
    /<meta[^>]+name=["']description["'][^>]+content=["']([^"']+)["']/i,
  );
  return name?.[1] ? decodeEntities(name[1]).trim() : undefined;
}

function pageTitle(html: string): string | undefined {
  const h1 = html.match(/<h1[^>]*>([\s\S]*?)<\/h1>/i);
  if (!h1?.[1]) return undefined;
  return decodeEntities(h1[1].replace(/<[^>]+>/g, " "))
    .replace(/\s+/g, " ")
    .trim();
}

/** Strip tags / scripts from HTML and keep readable page copy for the model. */
export function htmlToText(html: string, maxChars = 14_000): string {
  const withoutNoise = html
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<noscript[\s\S]*?<\/noscript>/gi, " ")
    .replace(/<!--[\s\S]*?-->/g, " ");

  const parts: string[] = [];
  const title = pageTitle(html);
  if (title) parts.push(`# ${title}`);
  const description = metaDescription(html);
  if (description) parts.push(description);

  const root = pickContentRoot(withoutNoise);
  parts.push(...stripToLines(root));

  // If the focused root was too short, fall back to the whole page body.
  if (parts.join("\n").length < 400) {
    parts.push(...stripToLines(withoutNoise));
  }

  const text = parts.join("\n").trim();
  if (text.length <= maxChars) return text;
  return `${text.slice(0, maxChars)}\n…[truncated]`;
}
