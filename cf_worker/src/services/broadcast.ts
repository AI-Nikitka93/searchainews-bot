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

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function sendTelegram(env: Env, chatId: number, text: string): Promise<void> {
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

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Telegram ${response.status}: ${body}`);
  }
}

async function getUnsentItemsForUser(
  env: Env,
  userId: number,
  role: Role
): Promise<BroadcastItem[]> {
  const roleLike = `%${role}%`;
  const query = env.DB.prepare(
    "SELECT i.id, i.title, i.url, i.impact_score, i.impact_rationale, i.action_items_json, i.target_role " +
      "FROM items i " +
      "LEFT JOIN deliveries d ON d.item_id = i.id AND d.user_id = ? " +
      "WHERE d.item_id IS NULL AND i.impact_score >= 3 " +
      "AND (i.target_role = ? OR i.target_role LIKE ? OR i.target_role IS NULL OR i.target_role = '') " +
      "ORDER BY i.id DESC LIMIT ?"
  );
  const result = await query.bind(userId, role, roleLike, ITEMS_PER_USER).all<BroadcastItem>();
  return result.results ?? [];
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

  const users = await getSubscribedUsers(env);
  log.info(`Broadcast users: ${users.length}`);

  for (const user of users) {
    if (!user.role) {
      continue;
    }

    const lang = resolveLang(user.language ?? "ru");
    const labels = getLabels(lang);
    const items = await getUnsentItemsForUser(env, user.user_id, user.role);
    if (!items.length) {
      continue;
    }

    for (const item of items) {
      try {
        const translated = await translateItemToRussian(item, env);
        await sendTelegram(env, user.user_id, formatItemMessage(item, labels, translated));
        await markDelivery(env, user.user_id, item.id, "sent");
      } catch (error) {
        await markDelivery(env, user.user_id, item.id, "error", String(error));
        log.warn(`Broadcast failed for user ${user.user_id}`, error);
      }
      await sleep(SEND_DELAY_MS);
    }
  }
}
