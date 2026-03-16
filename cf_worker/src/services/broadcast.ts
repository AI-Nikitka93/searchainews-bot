import type { Env, Role } from "../types";
import { formatItemMessage } from "../utils/text";
import { log } from "../utils/logger";
import { getSubscribedUsers } from "./users";
import { getLabels, resolveLang } from "../utils/i18n";
import { translateItemToRussian } from "./translate";

interface BroadcastItem {
  id: number;
  title: string;
  url: string;
  impact_score: number | null;
  impact_rationale: string | null;
  action_items_json: string | null;
  target_role: string | null;
}

const SEND_DELAY_MS = 1200;
const ITEMS_PER_USER = 3;
const MAX_SEND_RETRIES = 3;
const RETRY_BASE_MS = 1200;
const DEFAULT_NEWS_MAX_AGE_HOURS = 36;
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

function buildDedupeKey(item: BroadcastItem): string {
  const host = normalizeHost(item.url);
  const title = normalizeTitle(item.title);
  if (title) {
    return `${host}:${title}`;
  }
  return item.url ?? `${host}:${item.id}`;
}

function dedupeItems(items: BroadcastItem[], limit: number): BroadcastItem[] {
  const seen = new Set<string>();
  const seenDomains = new Set<string>();
  const seenTopics: Set<string>[] = [];
  const output: BroadcastItem[] = [];
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
    if (output.length >= limit) {
      break;
    }
  }
  return output;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function parseRetryAfter(body: string): number | null {
  try {
    const data = JSON.parse(body);
    const retryAfter = data?.parameters?.retry_after;
    if (typeof retryAfter === "number" && retryAfter > 0) {
      return retryAfter * 1000;
    }
  } catch {
    return null;
  }
  return null;
}

async function sendTelegramWithRetry(env: Env, chatId: number | string, text: string): Promise<void> {
  for (let attempt = 1; attempt <= MAX_SEND_RETRIES; attempt += 1) {
    const response = await fetch(`https://api.telegram.org/bot${env.BOT_TOKEN}/sendMessage`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        chat_id: chatId,
        text,
        parse_mode: "HTML",
        disable_web_page_preview: false
      })
    });

    if (response.ok) {
      return;
    }

    const body = await response.text();
    if (response.status === 429) {
      const retryAfter = parseRetryAfter(body) ?? RETRY_BASE_MS * attempt;
      log.warn("telegram_rate_limited", { chat_id: chatId, retry_ms: retryAfter, attempt });
      await sleep(retryAfter);
      continue;
    }

    if (response.status >= 500 && response.status < 600 && attempt < MAX_SEND_RETRIES) {
      const backoff = RETRY_BASE_MS * attempt;
      log.warn("telegram_retry", { chat_id: chatId, status: response.status, backoff_ms: backoff, attempt });
      await sleep(backoff);
      continue;
    }

    throw new Error(`Telegram ${response.status}: ${body}`);
  }
  throw new Error("Telegram retries exhausted");
}

async function sendAdminAlert(env: Env, message: string): Promise<void> {
  if (!env.ADMIN_CHAT_ID || !env.BOT_TOKEN) {
    return;
  }
  try {
    await sendTelegramWithRetry(env, env.ADMIN_CHAT_ID, message);
  } catch (error) {
    log.warn("admin_alert_failed", { error: String(error) });
  }
}

async function getUnsentItemsForUser(
  env: Env,
  userId: number,
  role: Role
): Promise<BroadcastItem[]> {
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
  const fetchLimit = Math.max(ITEMS_PER_USER * 4, 12);
  const query = env.DB.prepare(
    "SELECT i.id, i.title, i.url, i.impact_score, i.impact_rationale, i.action_items_json, i.target_role " +
      "FROM items i " +
      "LEFT JOIN deliveries d ON d.item_id = i.id AND d.user_id = ? " +
      "WHERE d.item_id IS NULL AND i.impact_score >= 3 " +
      `AND (i.target_role IN (${rolePlaceholders}) OR i.target_role LIKE ? OR i.target_role IN ('', 'other') OR i.target_role IS NULL) ` +
      "AND COALESCE(i.published_at, i.created_at) >= datetime('now', ?) " +
      "ORDER BY COALESCE(i.published_at, i.created_at) DESC, i.id DESC LIMIT ?"
  );
  const result = await query
    .bind(userId, ...roleValues, roleLike, `-${maxAgeHours} hours`, fetchLimit)
    .all<BroadcastItem>();
  return dedupeItems(result.results ?? [], ITEMS_PER_USER);
}

async function markDelivery(
  env: Env,
  userId: number,
  itemId: number,
  status: string,
  error?: string
): Promise<void> {
  const query = env.DB.prepare(
    "INSERT INTO deliveries (user_id, item_id, status, error, sent_at) VALUES (?, ?, ?, ?, datetime('now')) " +
      "ON CONFLICT(user_id, item_id) DO UPDATE SET status = excluded.status, error = excluded.error, sent_at = datetime('now')"
  );
  await query.bind(userId, itemId, status, error ?? null).run();
}

export async function runBroadcast(env: Env): Promise<void> {
  if (!env.BOT_TOKEN) {
    log.warn("BOT_TOKEN is missing; broadcaster skipped");
    return;
  }
  if (!env.DB) {
    log.warn("DB binding missing; broadcaster skipped");
    return;
  }

  const start = Date.now();
  const users = await getSubscribedUsers(env);
  let sentCount = 0;
  let errorCount = 0;
  let emptyCount = 0;
  let skippedNoRole = 0;

  log.info("broadcast_start", { users: users.length });

  for (const user of users) {
    if (!user.role) {
      skippedNoRole += 1;
      continue;
    }

    try {
      const lang = resolveLang(user.language ?? "ru");
      const labels = getLabels(lang);
      const items = await getUnsentItemsForUser(env, user.user_id, user.role);
      if (!items.length) {
        emptyCount += 1;
        continue;
      }

      for (const item of items) {
        try {
          let translated = null;
          try {
            translated = await translateItemToRussian(item, env);
          } catch (error) {
            log.warn("translate_failed", { item_id: item.id, error: String(error) });
          }
          await sendTelegramWithRetry(env, user.user_id, formatItemMessage(item, labels, translated));
          await markDelivery(env, user.user_id, item.id, "sent");
          sentCount += 1;
        } catch (error) {
          errorCount += 1;
          await markDelivery(env, user.user_id, item.id, "error", String(error).slice(0, 400));
          log.warn("broadcast_item_failed", { user_id: user.user_id, item_id: item.id, error: String(error) });
        }
        await sleep(SEND_DELAY_MS);
      }
    } catch (error) {
      errorCount += 1;
      log.warn("broadcast_user_failed", { user_id: user.user_id, error: String(error) });
    }
  }

  const durationMs = Date.now() - start;
  log.info("broadcast_done", {
    users: users.length,
    sent: sentCount,
    errors: errorCount,
    empty_users: emptyCount,
    skipped_no_role: skippedNoRole,
    duration_ms: durationMs
  });

  if (errorCount > 0) {
    await sendAdminAlert(
      env,
      `Broadcast warning: users=${users.length} sent=${sentCount} errors=${errorCount} empty=${emptyCount}`
    );
  }

  if (users.length > 0 && sentCount === 0) {
    await sendAdminAlert(env, "Broadcast empty: no items delivered for subscribed users.");
  }
}
