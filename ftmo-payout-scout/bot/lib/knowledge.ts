import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const knowledgeDir = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../knowledge",
);

export type KnowledgeDoc = {
  id: string;
  path: string;
  title: string;
  text: string;
};

export async function listKnowledgeDocs(): Promise<KnowledgeDoc[]> {
  const names = (await readdir(knowledgeDir))
    .filter((name) => name.endsWith(".md"))
    .sort();
  const docs: KnowledgeDoc[] = [];
  for (const name of names) {
    const full = path.join(knowledgeDir, name);
    const text = await readFile(full, "utf8");
    const title =
      text.match(/^#\s+(.+)$/m)?.[1]?.trim() ?? name.replace(/\.md$/, "");
    docs.push({
      id: name.replace(/\.md$/, ""),
      path: `knowledge/${name}`,
      title,
      text,
    });
  }
  return docs;
}

export function scoreDoc(doc: KnowledgeDoc, query: string): number {
  const q = query.toLowerCase().trim();
  if (!q) return 0;
  const terms = q.split(/\s+/).filter((t) => t.length > 1);
  const hay = `${doc.title}\n${doc.text}`.toLowerCase();
  let score = 0;
  for (const term of terms) {
    if (!hay.includes(term)) continue;
    const hits = hay.split(term).length - 1;
    score += hits;
  }
  return score;
}

export function excerptAround(
  text: string,
  query: string,
  radius = 280,
): string {
  const lower = text.toLowerCase();
  const terms = query
    .toLowerCase()
    .split(/\s+/)
    .filter((t) => t.length > 1);
  let idx = -1;
  for (const term of terms) {
    idx = lower.indexOf(term);
    if (idx >= 0) break;
  }
  if (idx < 0) {
    return text.slice(0, radius * 2).trim();
  }
  const start = Math.max(0, idx - radius);
  const end = Math.min(text.length, idx + radius);
  const slice = text.slice(start, end).trim();
  return `${start > 0 ? "…" : ""}${slice}${end < text.length ? "…" : ""}`;
}
