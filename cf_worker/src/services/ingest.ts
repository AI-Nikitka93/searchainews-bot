import type { Env } from "../types";

export interface IngestItem {
  source_id?: string | null;
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

const TRACKING_PARAMS = new Set([
  "utm_source",
  "utm_medium",
  "utm_campaign",
  "utm_term",
  "utm_content",
  "utm_id",
  "utm_name",
  "utm_cid",
  "utm_reader",
  "utm_referrer",
  "ref",
  "source",
  "fbclid",
  "gclid",
  "yclid",
  "mc_cid",
  "mc_eid"
]);

function normalizeUrl(input: string): string {
  try {
    const parsed = new URL(input);
    for (const key of Array.from(parsed.searchParams.keys())) {
      const lower = key.toLowerCase();
      if (lower.startsWith("utm_") || TRACKING_PARAMS.has(lower)) {
        parsed.searchParams.delete(key);
      }
    }
    const path = parsed.pathname && parsed.pathname !== "/" ? parsed.pathname.replace(/\/+$/, "") : "/";
    parsed.pathname = path;
    const query = parsed.searchParams.toString();
    parsed.search = query ? `?${query}` : "";
    return parsed.toString();
  } catch {
    return input;
  }
}

export async function upsertItems(env: Env, items: IngestItem[]): Promise<number> {
  let saved = 0;
  for (const item of items) {
    if (!item.url) {
      continue;
    }
    const normalizedUrl = normalizeUrl(item.url);
    const stmt = env.DB.prepare(
      "INSERT INTO items (source_id, title, url, raw_summary, full_text, impact_score, impact_rationale, action_items_json, target_role, tags_json, published_at) " +
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) " +
        "ON CONFLICT(url) DO UPDATE SET " +
        "source_id=COALESCE(excluded.source_id, items.source_id), " +
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
        item.source_id ?? null,
        item.title ?? null,
        normalizedUrl,
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
