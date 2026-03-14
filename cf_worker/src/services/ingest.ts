import type { Env } from "../types";

export interface IngestItem {
  title?: string;
  url: string;
  raw_summary?: string | null;
  full_text?: string | null;
  impact_score?: number | null;
  impact_rationale?: string | null;
  action_items_json?: string | null;
  target_role?: string | null;
  tags_json?: string | null;
  published_at?: string | null;
}

export async function upsertItems(env: Env, items: IngestItem[]): Promise<number> {
  let saved = 0;
  for (const item of items) {
    if (!item.url) {
      continue;
    }
    const stmt = env.DB.prepare(
      "INSERT INTO items (title, url, raw_summary, full_text, impact_score, impact_rationale, action_items_json, target_role, tags_json, published_at) " +
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) " +
        "ON CONFLICT(url) DO UPDATE SET " +
        "title=excluded.title, " +
        "raw_summary=excluded.raw_summary, " +
        "full_text=COALESCE(excluded.full_text, items.full_text), " +
        "impact_score=excluded.impact_score, " +
        "impact_rationale=excluded.impact_rationale, " +
        "action_items_json=excluded.action_items_json, " +
        "target_role=excluded.target_role, " +
        "tags_json=excluded.tags_json, " +
        "published_at=excluded.published_at"
    );

    await stmt
      .bind(
        item.title ?? null,
        item.url,
        item.raw_summary ?? null,
        item.full_text ?? null,
        item.impact_score ?? null,
        item.impact_rationale ?? null,
        item.action_items_json ?? null,
        item.target_role ?? null,
        item.tags_json ?? null,
        item.published_at ?? null
      )
      .run();
    saved += 1;
  }
  return saved;
}
