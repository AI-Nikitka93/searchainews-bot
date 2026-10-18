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
  discussion_context?: string | null;
  content_profile?: string | null;
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
    const keys: string[] = [];
    parsed.searchParams.forEach((_value, key) => {
      keys.push(key);
    });
    for (const key of keys) {
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
    try {
      const stmt = env.DB.prepare(
        "INSERT INTO items (source_id, title, url, raw_summary, full_text, impact_score, impact_rationale, action_items_json, target_role, tags_json, published_at, discussion_context, content_profile) " +
          "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) " +
          "ON CONFLICT(url) DO UPDATE SET " +
          "source_id=COALESCE(excluded.source_id, items.source_id), " +
          "title=COALESCE(excluded.title, items.title), " +
          "raw_summary=COALESCE(excluded.raw_summary, items.raw_summary), " +
          "full_text=COALESCE(excluded.full_text, items.full_text), " +
          "impact_score=COALESCE(excluded.impact_score, items.impact_score), " +
          "impact_rationale=COALESCE(excluded.impact_rationale, items.impact_rationale), " +
          "action_items_json=COALESCE(excluded.action_items_json, items.action_items_json), " +
          "target_role=COALESCE(excluded.target_role, items.target_role), " +
          "tags_json=COALESCE(excluded.tags_json, items.tags_json), " +
          "published_at=COALESCE(excluded.published_at, items.published_at), " +
          "discussion_context=COALESCE(excluded.discussion_context, items.discussion_context), " +
          "content_profile=COALESCE(excluded.content_profile, items.content_profile)"
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
          item.published_at ?? null,
          item.discussion_context ?? null,
          item.content_profile ?? null
        )
        .run();
    } catch {
      // Graceful fallback for pre-migrated D1 databases
      const fallbackStmt = env.DB.prepare(
        "INSERT INTO items (source_id, title, url, raw_summary, full_text, impact_score, impact_rationale, action_items_json, target_role, tags_json, published_at) " +
          "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) " +
          "ON CONFLICT(url) DO UPDATE SET " +
          "source_id=COALESCE(excluded.source_id, items.source_id), " +
          "title=COALESCE(excluded.title, items.title), " +
          "raw_summary=COALESCE(excluded.raw_summary, items.raw_summary), " +
          "full_text=COALESCE(excluded.full_text, items.full_text), " +
          "impact_score=COALESCE(excluded.impact_score, items.impact_score), " +
          "impact_rationale=COALESCE(excluded.impact_rationale, items.impact_rationale), " +
          "action_items_json=COALESCE(excluded.action_items_json, items.action_items_json), " +
          "target_role=COALESCE(excluded.target_role, items.target_role), " +
          "tags_json=COALESCE(excluded.tags_json, items.tags_json), " +
          "published_at=COALESCE(excluded.published_at, items.published_at)"
      );

      await fallbackStmt
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
    }
    saved += 1;
  }
  return saved;
}
