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

const DEFAULT_NEWS_MAX_AGE_HOURS = 36;
const DEFAULT_NEWS_MAX_RESEARCH = 1;
const STOPWORDS = new Set([
  "the",
  "and",
  "for",
  "with",
  "from",
  "that",
  "this",
  "into",
  "over",
  "under",
  "about",
  "using",
  "news",
  "update",
  "report",
  "shows",
  "show",
  "new",
  "how",
  "why",
  "what",
  "to",
  "of",
  "in",
  "on",
  "a",
  "an",
  "и",
  "в",
  "на",
  "о",
  "об",
  "как",
  "что",
  "это",
  "эта",
  "этот",
  "для",
  "из",
  "по",
  "при",
  "про",
  "над",
  "под",
  "его",
  "ее",
  "их",
  "мы",
  "они",
  "вы",
  "наш",
  "ваш",
  "новый",
  "новая",
  "новые",
  "обзор",
  "исследование"
]);

function parseNewsMaxAgeHours(env: Env): number {
  const raw = env.NEWS_MAX_AGE_HOURS;
  const value = raw ? Number(raw) : DEFAULT_NEWS_MAX_AGE_HOURS;
  if (!Number.isFinite(value) || value <= 0) {
    return DEFAULT_NEWS_MAX_AGE_HOURS;
  }
  return Math.min(168, Math.max(6, Math.floor(value)));
}

function parseNewsResearchDomains(env: Env): Set<string> {
  const raw = env.NEWS_RESEARCH_DOMAINS;
  if (!raw) {
    return new Set();
  }
  return new Set(
    raw
      .split(",")
      .map((part) => part.trim().toLowerCase())
      .filter(Boolean)
  );
}

function parseNewsMaxResearch(env: Env): number {
  const raw = env.NEWS_MAX_RESEARCH_PER_BATCH;
  const value = raw ? Number(raw) : DEFAULT_NEWS_MAX_RESEARCH;
  if (!Number.isFinite(value) || value < 0) {
    return DEFAULT_NEWS_MAX_RESEARCH;
  }
  return Math.min(5, Math.max(0, Math.floor(value)));
}

function normalizeTitle(title?: string | null): string {
  if (!title) {
    return "";
  }
  return title
    .toLowerCase()
    .replace(/['"`’]/g, "")
    .replace(/[^a-z0-9а-яё]+/gi, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function tokenizeTitle(title?: string | null): string[] {
  if (!title) {
    return [];
  }
  return normalizeTitle(title)
    .split(" ")
    .map((token) => token.trim())
    .filter((token) => token.length >= 3 && !STOPWORDS.has(token));
}

function jaccard(a: Set<string>, b: Set<string>): number {
  if (!a.size || !b.size) {
    return 0;
  }
  let intersection = 0;
  for (const token of a) {
    if (b.has(token)) {
      intersection += 1;
    }
  }
  const union = a.size + b.size - intersection;
  return union > 0 ? intersection / union : 0;
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

function dedupeItems(env: Env, items: NewsItem[], limit: number): NewsItem[] {
  const seen = new Set<string>();
  const seenDomains = new Set<string>();
  const seenTopics: Set<string>[] = [];
  const output: NewsItem[] = [];
  const researchDomains = parseNewsResearchDomains(env);
  const maxResearch = parseNewsMaxResearch(env);
  let researchCount = 0;

  for (const item of items) {
    const key = buildDedupeKey(item);
    if (seen.has(key)) {
      continue;
    }
    const host = normalizeHost(item.url);
    const tokens = new Set(tokenizeTitle(item.title));
    if (!tokens.size) {
      continue;
    }
    const isResearch = host ? researchDomains.has(host) : false;
    if (isResearch && researchCount >= maxResearch) {
      continue;
    }
    if (host && seenDomains.has(host)) {
      continue;
    }
    if (seenTopics.some((topic) => jaccard(topic, tokens) >= 0.65)) {
      continue;
    }
    seen.add(key);
    output.push(item);
    seenTopics.push(tokens);
    if (host) {
      seenDomains.add(host);
    }
    if (isResearch) {
      researchCount += 1;
    }
    if (output.length >= limit) {
      break;
    }
  }

  if (output.length >= limit) {
    return output;
  }

  for (const item of items) {
    const key = buildDedupeKey(item);
    if (seen.has(key)) {
      continue;
    }
    const tokens = new Set(tokenizeTitle(item.title));
    if (!tokens.size) {
      continue;
    }
    if (seenTopics.some((topic) => jaccard(topic, tokens) >= 0.65)) {
      continue;
    }
    output.push(item);
    seen.add(key);
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
  const maxAgeHours = parseNewsMaxAgeHours(env);
  const fetchLimit = Math.max(limit * 4, 12);
  const query = userId
    ? env.DB.prepare(
        "SELECT i.id, i.title, i.url, i.impact_score, i.impact_rationale, i.action_items_json, i.target_role " +
          "FROM items i " +
          "LEFT JOIN deliveries d ON d.item_id = i.id AND d.user_id = ? " +
          "WHERE d.item_id IS NULL AND i.impact_score >= 3 " +
          `AND (i.target_role IN (${rolePlaceholders}) OR i.target_role LIKE ? OR i.target_role IN ('', 'other') OR i.target_role IS NULL) ` +
          "AND COALESCE(i.published_at, i.created_at) >= datetime('now', ?) " +
          "ORDER BY COALESCE(i.published_at, i.created_at) DESC, i.id DESC LIMIT ?"
      )
    : env.DB.prepare(
        "SELECT id, title, url, impact_score, impact_rationale, action_items_json, target_role " +
          "FROM items " +
          `WHERE impact_score >= 3 AND (target_role IN (${rolePlaceholders}) OR target_role LIKE ? OR target_role IN ('', 'other') OR target_role IS NULL) ` +
          "AND COALESCE(published_at, created_at) >= datetime('now', ?) " +
          "ORDER BY COALESCE(published_at, created_at) DESC, id DESC LIMIT ?"
      );
  const result = userId
    ? await query.bind(userId, ...roleValues, roleLike, `-${maxAgeHours} hours`, fetchLimit).all<NewsItem>()
    : await query.bind(...roleValues, roleLike, `-${maxAgeHours} hours`, fetchLimit).all<NewsItem>();
  const primary = dedupeItems(env, result.results ?? [], limit);
  if (primary.length > 0) {
    return primary;
  }
  const fallbackQuery = userId
    ? env.DB.prepare(
        "SELECT i.id, i.title, i.url, i.impact_score, i.impact_rationale, i.action_items_json, i.target_role " +
          "FROM items i " +
          "LEFT JOIN deliveries d ON d.item_id = i.id AND d.user_id = ? " +
          "WHERE d.item_id IS NULL AND i.impact_score >= 3 " +
          "AND COALESCE(i.published_at, i.created_at) >= datetime('now', ?) " +
          "ORDER BY COALESCE(i.published_at, i.created_at) DESC, i.id DESC LIMIT ?"
      )
    : env.DB.prepare(
        "SELECT id, title, url, impact_score, impact_rationale, action_items_json, target_role " +
          "FROM items " +
          "WHERE impact_score >= 3 " +
          "AND COALESCE(published_at, created_at) >= datetime('now', ?) " +
          "ORDER BY COALESCE(published_at, created_at) DESC, id DESC LIMIT ?"
      );
  const fallback = userId
    ? await fallbackQuery.bind(userId, `-${maxAgeHours} hours`, fetchLimit).all<NewsItem>()
    : await fallbackQuery.bind(`-${maxAgeHours} hours`, fetchLimit).all<NewsItem>();
  return dedupeItems(env, fallback.results ?? [], limit);
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
