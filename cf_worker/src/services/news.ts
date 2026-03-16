import type { Env, Role } from "../types";

export interface NewsItem {
  id: number;
  title: string;
  url: string;
  impact_score: number | null;
  impact_rationale: string | null;
  action_items_json: string | null;
  target_role: string | null;
}

function normalizeTitle(title?: string | null): string {
  if (!title) {
    return "";
  }
  return title
    .toLowerCase()
    .replace(/['"`’]/g, "")
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function normalizeHost(url?: string | null): string {
  if (!url) {
    return "";
  }
  try {
    const parsed = new URL(url);
    let host = parsed.hostname.toLowerCase();
    if (host.startsWith("www.")) {
      host = host.slice(4);
    }
    return host;
  } catch {
    return "";
  }
}

function buildDedupeKey(item: NewsItem): string {
  const host = normalizeHost(item.url);
  const title = normalizeTitle(item.title);
  if (title) {
    return `${host}:${title}`;
  }
  return item.url ?? `${host}:${item.id}`;
}

function dedupeItems(items: NewsItem[], limit: number): NewsItem[] {
  const seen = new Set<string>();
  const output: NewsItem[] = [];
  for (const item of items) {
    const key = buildDedupeKey(item);
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    output.push(item);
    if (output.length >= limit) {
      break;
    }
  }
  return output;
}

export async function getLatestForRole(
  env: Env,
  role: Role,
  limit = 3,
  userId?: number
): Promise<NewsItem[]> {
  const roleAliases: Record<Role, string[]> = {
    ai_specialist: ["ai_specialist", "pm", "founder"],
    ai_developer: ["ai_developer", "developer"],
    ai_enthusiast: ["ai_enthusiast"],
    ai_beginner: ["ai_beginner"],
    developer: ["developer", "ai_developer"],
    pm: ["pm", "ai_specialist"],
    founder: ["founder", "ai_specialist"]
  };
  const roleValues = roleAliases[role] ?? [role];
  const roleLike = `%${role}%`;
  const rolePlaceholders = roleValues.map(() => "?").join(", ");
  const fetchLimit = Math.max(limit * 4, 12);
  const query = userId
    ? env.DB.prepare(
        "SELECT i.id, i.title, i.url, i.impact_score, i.impact_rationale, i.action_items_json, i.target_role " +
          "FROM items i " +
          "LEFT JOIN deliveries d ON d.item_id = i.id AND d.user_id = ? " +
          "WHERE d.item_id IS NULL AND i.impact_score >= 3 " +
          `AND (i.target_role IN (${rolePlaceholders}) OR i.target_role LIKE ? OR i.target_role IN ('', 'other') OR i.target_role IS NULL) ` +
          "ORDER BY COALESCE(i.published_at, i.created_at) DESC, i.id DESC LIMIT ?"
      )
    : env.DB.prepare(
        "SELECT id, title, url, impact_score, impact_rationale, action_items_json, target_role " +
          "FROM items " +
          `WHERE impact_score >= 3 AND (target_role IN (${rolePlaceholders}) OR target_role LIKE ? OR target_role IN ('', 'other') OR target_role IS NULL) ` +
          "ORDER BY COALESCE(published_at, created_at) DESC, id DESC LIMIT ?"
      );
  const result = userId
    ? await query.bind(userId, ...roleValues, roleLike, fetchLimit).all<NewsItem>()
    : await query.bind(...roleValues, roleLike, fetchLimit).all<NewsItem>();
  const primary = dedupeItems(result.results ?? [], limit);
  if (primary.length > 0) {
    return primary;
  }
  const fallbackQuery = userId
    ? env.DB.prepare(
        "SELECT i.id, i.title, i.url, i.impact_score, i.impact_rationale, i.action_items_json, i.target_role " +
          "FROM items i " +
          "LEFT JOIN deliveries d ON d.item_id = i.id AND d.user_id = ? " +
          "WHERE d.item_id IS NULL AND i.impact_score >= 3 " +
          "ORDER BY COALESCE(i.published_at, i.created_at) DESC, i.id DESC LIMIT ?"
      )
    : env.DB.prepare(
        "SELECT id, title, url, impact_score, impact_rationale, action_items_json, target_role " +
          "FROM items " +
          "WHERE impact_score >= 3 " +
          "ORDER BY COALESCE(published_at, created_at) DESC, id DESC LIMIT ?"
      );
  const fallback = userId
    ? await fallbackQuery.bind(userId, fetchLimit).all<NewsItem>()
    : await fallbackQuery.bind(fetchLimit).all<NewsItem>();
  return dedupeItems(fallback.results ?? [], limit);
}

export async function markItemsDelivered(
  env: Env,
  userId: number,
  itemIds: number[],
  status = "manual"
): Promise<void> {
  if (!itemIds.length) {
    return;
  }
  const stmt = env.DB.prepare(
    "INSERT INTO deliveries (user_id, item_id, status, error, sent_at) VALUES (?, ?, ?, NULL, datetime('now')) " +
      "ON CONFLICT(user_id, item_id) DO UPDATE SET status = excluded.status, sent_at = datetime('now')"
  );
  for (const itemId of itemIds) {
    await stmt.bind(userId, itemId, status).run();
  }
}
