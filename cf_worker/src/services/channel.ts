import type { Env } from "../types";
import { escapeHtml } from "../utils/text";
import { getLabels, resolveLang } from "../utils/i18n";
import { translateItemToRussian } from "./translate";
import { log } from "../utils/logger";

interface ChannelItem {
  id: number;
  title: string;
  url: string;
  raw_summary: string | null;
  impact_score: number | null;
  impact_rationale: string | null;
  action_items_json: string | null;
  target_role: string | null;
}

const DEFAULT_GAP_SECONDS = 300;
const SUMMARY_MAX_CHARS = 520;
const AI_MODEL = "@cf/meta/llama-3.1-8b-instruct";
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

function parseMinImpact(env: Env): number {
  const raw = env.CHANNEL_MIN_IMPACT;
  const value = raw ? Number(raw) : 3;
  if (!Number.isFinite(value) || value < 1) {
    return 3;
  }
  return Math.min(5, Math.max(1, Math.floor(value)));
}

function parseUseAi(env: Env): boolean {
  const raw = env.CHANNEL_USE_AI_SUMMARY;
  if (!raw) {
    return true;
  }
  return ["1", "true", "yes", "y", "on"].includes(raw.toLowerCase());
}

function parseExcludedDomains(env: Env): string[] {
  const raw = env.CHANNEL_EXCLUDE_DOMAINS;
  if (!raw) {
    return [];
  }
  return raw
    .split(",")
    .map((part) => part.trim().toLowerCase())
    .filter(Boolean);
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

function extractText(response: unknown): string {
  if (typeof response === "string") {
    return response;
  }
  const payload = response as { response?: string; result?: string };
  return payload?.response ?? payload?.result ?? JSON.stringify(response ?? "");
}

async function summarizeWithAI(env: Env, title: string, summary: string, lang: "ru" | "en"): Promise<string> {
  if (!env.AI) {
    return "";
  }
  const system = [
    "Ты редактор новостного Telegram-канала.",
    "Сделай 1-2 коротких предложения (до 320 символов).",
    "Только главное: что произошло и почему важно.",
    "Пиши простым языком, без жаргона и сложных терминов.",
    "Без списков, без оценок, без эмодзи.",
    "Язык: русский."
  ].join(" ");
  const prompt = [`Заголовок: ${title}`, `Короткое описание: ${summary}`].join("\n");
  try {
    const response = await env.AI.run(AI_MODEL, {
      messages: [
        { role: "system", content: system },
        { role: "user", content: prompt }
      ],
      temperature: 0.2,
      max_tokens: 200
    });
    const text = extractText(response).trim();
    if (!text) {
      return "";
    }
    return sanitizeText(text, SUMMARY_MAX_CHARS);
  } catch (error) {
    log.warn("channel_ai_summary_failed", { error: String(error) });
    return "";
  }
}

function limitSentences(text: string, maxSentences = 2): string {
  const parts = text.split(/(?<=[.!?])\s+/).filter(Boolean);
  return parts.slice(0, maxSentences).join(" ").trim();
}

function sanitizeText(text: string, maxLen: number): string {
  const cleaned = text.replace(/\s+/g, " ").trim();
  if (cleaned.length <= maxLen) {
    return cleaned;
  }
  const head = cleaned.slice(0, Math.max(1, maxLen - 1));
  const lastSpace = head.lastIndexOf(" ");
  const cutoff = lastSpace > Math.floor(maxLen * 0.6) ? lastSpace : head.length;
  return `${head.slice(0, cutoff).trim()}…`;
}

function buildChannelMessage(
  item: ChannelItem,
  lang: "ru" | "en",
  overrides?: { title?: string | null; summary?: string | null }
): string {
  const labels = getLabels(lang);
  const title = escapeHtml(sanitizeText(overrides?.title ?? item.title ?? labels.noTitle, 140));
  const baseSummary = overrides?.summary ?? item.impact_rationale ?? item.raw_summary ?? "";
  const summary = escapeHtml(
    sanitizeText(limitSentences(baseSummary, 2) || labels.noRationale, SUMMARY_MAX_CHARS)
  );
  return [
    `<b>${title}</b>`,
    summary,
    `<a href="${escapeHtml(item.url ?? "")}">${labels.source}</a>`
  ].join("\n");
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
  const minImpact = parseMinImpact(env);
  const excludeDomains = parseExcludedDomains(env);
  const excludeSql = excludeDomains.length
    ? " AND " + excludeDomains.map(() => "LOWER(i.url) NOT LIKE ?").join(" AND ")
    : "";
  const query = env.DB.prepare(
    "SELECT i.id, i.title, i.url, i.raw_summary, i.impact_score, i.impact_rationale, i.action_items_json, i.target_role " +
      "FROM items i " +
      "LEFT JOIN channel_posts c ON c.item_id = i.id AND c.channel_id = ? " +
      "WHERE c.item_id IS NULL AND i.impact_score >= ? " +
      excludeSql +
      " ORDER BY COALESCE(i.published_at, i.created_at) DESC, i.id DESC LIMIT 1"
  );
  const params = [channelId, minImpact, ...excludeDomains.map((domain) => `%${domain}%`)];
  const result = await query.bind(...params).first<ChannelItem>();
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

  const lang = resolveLang(env.CHANNEL_LANGUAGE ?? "ru");
  let aiSummary = "";
  if (parseUseAi(env)) {
    aiSummary = await summarizeWithAI(env, item.title ?? "", item.raw_summary ?? "", lang);
  }

  let translated = null;
  if (!aiSummary) {
    try {
      translated = await translateItemToRussian(item, env);
    } catch (error) {
      log.warn("channel_translate_failed", { item_id: item.id, error: String(error) });
    }
  }

  const message = buildChannelMessage(item, lang, {
    title: translated?.title ?? item.title,
    summary: aiSummary || translated?.rationale || item.impact_rationale || item.raw_summary
  });
  await sendTelegramWithRetry(env, channelId, message);
  await recordChannelPost(env, channelId, item.id);
  log.info("channel_sent", { channel_id: channelId, item_id: item.id });
  return { sent: 1, skipped: 0 };
}
