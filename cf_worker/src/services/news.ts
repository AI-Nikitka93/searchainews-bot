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

export async function getLatestForRole(
  env: Env,
  role: Role,
  limit = 3
): Promise<NewsItem[]> {
  const roleLike = `%${role}%`;
  const query = env.DB.prepare(
    "SELECT id, title, url, impact_score, impact_rationale, action_items_json, target_role " +
      "FROM items " +
      "WHERE impact_score >= 3 AND (target_role = ? OR target_role LIKE ? OR target_role IS NULL OR target_role = '') " +
      "ORDER BY id DESC LIMIT ?"
  );
  const result = await query.bind(role, roleLike, limit).all<NewsItem>();
  const primary = result.results ?? [];
  if (primary.length > 0) {
    return primary;
  }
  const fallbackQuery = env.DB.prepare(
    "SELECT id, title, url, impact_score, impact_rationale, action_items_json, target_role " +
      "FROM items " +
      "WHERE impact_score >= 3 " +
      "ORDER BY id DESC LIMIT ?"
  );
  const fallback = await fallbackQuery.bind(limit).all<NewsItem>();
  return fallback.results ?? [];
}
