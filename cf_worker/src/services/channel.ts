import type { Env } from "../types";
import { formatItemMessage } from "../utils/text";
import { getLabels, resolveLang } from "../utils/i18n";
import { translateItemToRussian } from "./translate";
import { log } from "../utils/logger";

interface ChannelItem {
  id: number;
  title: string;
  url: string;
  impact_score: number | null;
  impact_rationale: string | null;
  action_items_json: string | null;
  target_role: string | null;
}

const DEFAULT_GAP_SECONDS = 300;
const MAX_SEND_RETRIES = 3;
const RETRY_BASE_MS = 1200;

function parseGapSeconds(env: Env): number {
  const raw = env.CHANNEL_POST_GAP_SECONDS;
  const value = raw ? Number(raw) : DEFAULT_GAP_SECONDS;
  if (!Number.isFinite(value) || value <= 0) {
    return DEFAULT_GAP_SECONDS;
  }
  return Math.max(60, Math.floor(value));
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

async function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function sendTelegramWithRetry(env: Env, chatId: string, text: string): Promise<void> {
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
      log.warn("channel_rate_limited", { chat_id: chatId, retry_ms: retryAfter, attempt });
      await sleep(retryAfter);
      continue;
    }

    if (response.status >= 500 && response.status < 600 && attempt < MAX_SEND_RETRIES) {
      const backoff = RETRY_BASE_MS * attempt;
      log.warn("channel_retry", { chat_id: chatId, status: response.status, backoff_ms: backoff, attempt });
      await sleep(backoff);
      continue;
    }

    throw new Error(`Telegram ${response.status}: ${body}`);
  }
  throw new Error("Telegram retries exhausted");
}

async function getLastChannelSentAt(env: Env, channelId: string): Promise<string | null> {
  const row = await env.DB.prepare(
    "SELECT sent_at FROM channel_posts WHERE channel_id = ? ORDER BY sent_at DESC LIMIT 1"
  )
    .bind(channelId)
    .first<{ sent_at?: string }>();
  return row?.sent_at ?? null;
}

async function getNextChannelItem(env: Env, channelId: string): Promise<ChannelItem | null> {
  const query = env.DB.prepare(
    "SELECT i.id, i.title, i.url, i.impact_score, i.impact_rationale, i.action_items_json, i.target_role " +
      "FROM items i " +
      "LEFT JOIN channel_posts c ON c.item_id = i.id AND c.channel_id = ? " +
      "WHERE c.item_id IS NULL AND i.impact_score >= 3 " +
      "ORDER BY COALESCE(i.published_at, i.created_at) DESC, i.id DESC LIMIT 1"
  );
  const result = await query.bind(channelId).first<ChannelItem>();
  return result ?? null;
}

async function recordChannelPost(env: Env, channelId: string, itemId: number): Promise<void> {
  await env.DB.prepare("INSERT INTO channel_posts (channel_id, item_id) VALUES (?, ?)")
    .bind(channelId, itemId)
    .run();
}

export async function runChannelBroadcast(env: Env): Promise<{ sent: number; skipped: number }> {
  if (!env.BOT_TOKEN || !env.DB) {
    log.warn("channel_broadcast_skipped", { reason: "missing_bot_or_db" });
    return { sent: 0, skipped: 1 };
  }
  const channelId = env.CHANNEL_CHAT_ID;
  if (!channelId) {
    log.info("channel_broadcast_disabled");
    return { sent: 0, skipped: 1 };
  }

  const gapSeconds = parseGapSeconds(env);
  const lastSent = await getLastChannelSentAt(env, channelId);
  if (lastSent) {
    const lastTs = Date.parse(lastSent);
    if (!Number.isNaN(lastTs)) {
      const deltaSeconds = (Date.now() - lastTs) / 1000;
      if (deltaSeconds < gapSeconds) {
        log.info("channel_rate_limit", { channel_id: channelId, gap_seconds: gapSeconds, delta_seconds: deltaSeconds });
        return { sent: 0, skipped: 1 };
      }
    }
  }

  const item = await getNextChannelItem(env, channelId);
  if (!item) {
    log.info("channel_no_items");
    return { sent: 0, skipped: 1 };
  }

  const lang = resolveLang("ru");
  const labels = getLabels(lang);
  let translated = null;
  try {
    translated = await translateItemToRussian(item, env);
  } catch (error) {
    log.warn("channel_translate_failed", { item_id: item.id, error: String(error) });
  }

  await sendTelegramWithRetry(env, channelId, formatItemMessage(item, labels, translated));
  await recordChannelPost(env, channelId, item.id);
  log.info("channel_sent", { channel_id: channelId, item_id: item.id });
  return { sent: 1, skipped: 0 };
}
