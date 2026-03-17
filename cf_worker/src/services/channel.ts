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
const SUMMARY_MAX_CHARS = 240;
const HEADLINE_MAX_CHARS = 120;
const AI_MODEL = "@cf/meta/llama-3.1-8b-instruct";
const CANDIDATE_LIMIT = 30;
const RECENT_DOMAIN_LOOKBACK = 4;
const DEFAULT_DEDUPE_HOURS = 72;
const DEFAULT_POST_MIN_ITEMS = 2;
const DEFAULT_POST_MAX_ITEMS = 5;
const DEFAULT_MAX_AGE_HOURS = 24;
const DEFAULT_MIN_SUMMARY_CHARS = 60;
const DEFAULT_MAX_RESEARCH_PER_POST = 1;
const DEFAULT_TZ_OFFSET_MINUTES = 0;
const DEFAULT_DAILY_REPORT_HOUR = 21;
const DEFAULT_BREAKING_MIN_IMPACT = 5;
const MAX_SEND_RETRIES = 3;
const RETRY_BASE_MS = 1200;
const MAX_EXTRA_SOURCES = 2;
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
const DEFAULT_BREAKING_KEYWORDS = [
  "new model",
  "model release",
  "launches model",
  "released model",
  "introducing",
  "gpt-5",
  "gpt-4.5",
  "claude",
  "gemini",
  "llama",
  "qwen",
  "mistral",
  "deepseek",
  "pixtral",
  "magistral",
  "devstral",
  "reasoning model",
  "foundation model",
  "open model",
  "api release",
  "flagship model",
  "weights released",
  "выпустила модель",
  "новая модель",
  "релиз модели",
  "представила модель"
];

interface ChannelBlock {
  main: ChannelItem;
  related: ChannelItem[];
  topicTokens: Set<string>;
  domain: string;
  isResearch: boolean;
}

interface HourWindow {
  start: number;
  end: number;
}

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

function parseDedupeHours(env: Env): number {
  const raw = env.CHANNEL_DEDUPE_HOURS;
  const value = raw ? Number(raw) : DEFAULT_DEDUPE_HOURS;
  if (!Number.isFinite(value) || value <= 0) {
    return DEFAULT_DEDUPE_HOURS;
  }
  return Math.min(240, Math.max(24, Math.floor(value)));
}

function parsePostMinItems(env: Env): number {
  const raw = env.CHANNEL_POST_MIN_ITEMS;
  const value = raw ? Number(raw) : DEFAULT_POST_MIN_ITEMS;
  if (!Number.isFinite(value) || value < 1) {
    return DEFAULT_POST_MIN_ITEMS;
  }
  return Math.min(10, Math.max(1, Math.floor(value)));
}

function parsePostMaxItems(env: Env): number {
  const raw = env.CHANNEL_POST_MAX_ITEMS;
  const value = raw ? Number(raw) : DEFAULT_POST_MAX_ITEMS;
  if (!Number.isFinite(value) || value < 1) {
    return DEFAULT_POST_MAX_ITEMS;
  }
  return Math.min(10, Math.max(1, Math.floor(value)));
}

function parseMaxAgeHours(env: Env): number {
  const raw = env.CHANNEL_MAX_AGE_HOURS;
  const value = raw ? Number(raw) : DEFAULT_MAX_AGE_HOURS;
  if (!Number.isFinite(value) || value <= 0) {
    return DEFAULT_MAX_AGE_HOURS;
  }
  return Math.min(168, Math.max(6, Math.floor(value)));
}

function parseMinSummaryChars(env: Env): number {
  const raw = env.CHANNEL_MIN_SUMMARY_CHARS;
  const value = raw ? Number(raw) : DEFAULT_MIN_SUMMARY_CHARS;
  if (!Number.isFinite(value) || value <= 0) {
    return DEFAULT_MIN_SUMMARY_CHARS;
  }
  return Math.min(200, Math.max(20, Math.floor(value)));
}

function parseResearchDomains(env: Env): string[] {
  const raw = env.CHANNEL_RESEARCH_DOMAINS;
  if (!raw) {
    return [];
  }
  return raw
    .split(",")
    .map((part) => part.trim().toLowerCase())
    .filter(Boolean);
}

function parseMaxResearchPerPost(env: Env): number {
  const raw = env.CHANNEL_MAX_RESEARCH_PER_POST;
  const value = raw ? Number(raw) : DEFAULT_MAX_RESEARCH_PER_POST;
  if (!Number.isFinite(value) || value < 0) {
    return DEFAULT_MAX_RESEARCH_PER_POST;
  }
  return Math.min(5, Math.max(0, Math.floor(value)));
}

function parseActiveHours(env: Env): HourWindow[] {
  const raw = env.CHANNEL_ACTIVE_HOURS;
  if (!raw) {
    return [];
  }
  const windows: HourWindow[] = [];
  for (const part of raw.split(",")) {
    const trimmed = part.trim();
    if (!trimmed) {
      continue;
    }
    const [startRaw, endRaw] = trimmed.split("-");
    const start = Number(startRaw);
    const end = Number(endRaw);
    if (!Number.isFinite(start) || !Number.isFinite(end)) {
      continue;
    }
    const startHour = Math.min(23, Math.max(0, Math.floor(start)));
    const endHour = Math.min(24, Math.max(0, Math.floor(end)));
    if (startHour === endHour) {
      continue;
    }
    windows.push({ start: startHour, end: endHour });
  }
  return windows;
}

function parseTzOffsetMinutes(env: Env): number {
  const raw = env.CHANNEL_TZ_OFFSET_MINUTES;
  const value = raw ? Number(raw) : DEFAULT_TZ_OFFSET_MINUTES;
  if (!Number.isFinite(value)) {
    return DEFAULT_TZ_OFFSET_MINUTES;
  }
  return Math.max(-840, Math.min(840, Math.floor(value)));
}

function parseDailyReportHour(env: Env): number | null {
  const raw = env.CHANNEL_DAILY_REPORT_HOUR;
  if (!raw) {
    return null;
  }
  const value = Number(raw);
  if (!Number.isFinite(value)) {
    return null;
  }
  const hour = Math.floor(value);
  if (hour < 0 || hour > 23) {
    return null;
  }
  return hour;
}

function parseBreakingMinImpact(env: Env): number {
  const raw = env.CHANNEL_BREAKING_MIN_IMPACT;
  const value = raw ? Number(raw) : DEFAULT_BREAKING_MIN_IMPACT;
  if (!Number.isFinite(value) || value < 1) {
    return DEFAULT_BREAKING_MIN_IMPACT;
  }
  return Math.min(5, Math.max(1, Math.floor(value)));
}

function parseBreakingKeywords(env: Env): string[] {
  const raw = env.CHANNEL_BREAKING_KEYWORDS;
  if (!raw) {
    return DEFAULT_BREAKING_KEYWORDS;
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
    "Сделай 1-2 коротких предложения (до 240 символов).",
    "Первое предложение: что произошло.",
    "Второе предложение: почему это важно для читателя.",
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
    const descriptionMatch = text.match(
      /(короткое описание|описание|summary|short description)\s*[:\-–—]\s*([\s\S]+)/i
    );
    const pick = descriptionMatch ? descriptionMatch[2] : text;
    return sanitizeText(cleanSummary(pick), SUMMARY_MAX_CHARS);
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

function normalizeTitle(text: string): string {
  return text
    .toLowerCase()
    .replace(/['"`’]/g, "")
    .replace(/[^a-z0-9а-яё]+/gi, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function tokenizeTitle(text: string): string[] {
  const normalized = normalizeTitle(text);
  if (!normalized) {
    return [];
  }
  return normalized
    .split(" ")
    .map((token) => token.trim())
    .filter((token) => token.length >= 3 && !STOPWORDS.has(token));
}

function makeTopicTokens(title: string): Set<string> {
  return new Set(tokenizeTitle(title));
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

function normalizeHost(url: string): string {
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

function makeDedupeKey(item: ChannelItem): string {
  const host = normalizeHost(item.url ?? "");
  const title = normalizeTitle(item.title ?? "");
  return title ? `${host}:${title}` : host;
}

function isBreakingCandidate(item: ChannelItem, env: Env, researchDomains: Set<string>): boolean {
  const minImpact = parseBreakingMinImpact(env);
  if ((item.impact_score ?? 0) < minImpact) {
    return false;
  }
  const host = normalizeHost(item.url ?? "");
  if (researchDomains.has(host)) {
    return false;
  }
  const haystack = `${item.title ?? ""} ${item.raw_summary ?? ""} ${item.impact_rationale ?? ""}`.toLowerCase();
  return parseBreakingKeywords(env).some((keyword) => haystack.includes(keyword));
}

function cleanSummary(text: string): string {
  let cleaned = text.trim();
  cleaned = cleaned.replace(/^["«»]+|["«»]+$/g, "").trim();
  cleaned = cleaned.replace(
    /\b(заголовок|короткое описание|описание|summary|short description|title|новость|новости|news|update)\s*[:\-–—]\s*/gi,
    ""
  );
  cleaned = cleaned.replace(
    /^(в этой статье|в этом материале|в этом посте|в этой заметке|в этой новости)\s*[,:\-–—]?\s*/i,
    ""
  );
  cleaned = cleaned.replace(/\s+«/g, " «").replace(/\s+»/g, "»");
  return cleaned;
}

function buildChannelMessage(
  item: ChannelItem,
  lang: "ru" | "en",
  overrides?: { title?: string | null; summary?: string | null }
): string {
  const labels = getLabels(lang);
  const title = escapeHtml(sanitizeText(overrides?.title ?? item.title ?? labels.noTitle, HEADLINE_MAX_CHARS));
  const baseSummary = cleanSummary(overrides?.summary ?? item.impact_rationale ?? item.raw_summary ?? "");
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

async function getRecentChannelDomains(env: Env, channelId: string): Promise<string[]> {
  const rows = await env.DB.prepare(
    "SELECT i.url FROM channel_posts c " +
      "JOIN items i ON i.id = c.item_id " +
      "WHERE c.channel_id = ? " +
      "ORDER BY c.sent_at DESC LIMIT ?"
  )
    .bind(channelId, RECENT_DOMAIN_LOOKBACK)
    .all<{ url: string }>();
  return (rows.results ?? []).map((row) => normalizeHost(row.url)).filter(Boolean);
}

async function getRecentDedupeKeys(env: Env, channelId: string): Promise<Set<string>> {
  const hours = parseDedupeHours(env);
  const rows = await env.DB.prepare(
    "SELECT dedupe_key FROM channel_post_keys " +
      "WHERE channel_id = ? AND sent_at >= datetime('now', ?) " +
      "ORDER BY sent_at DESC LIMIT 200"
  )
    .bind(channelId, `-${hours} hours`)
    .all<{ dedupe_key: string }>();
  const set = new Set<string>();
  for (const row of rows.results ?? []) {
    if (row?.dedupe_key) {
      set.add(row.dedupe_key);
    }
  }
  return set;
}

async function getCandidateItems(env: Env, channelId: string, limit: number): Promise<ChannelItem[]> {
  const minImpact = parseMinImpact(env);
  const excludeDomains = parseExcludedDomains(env);
  const maxAgeHours = parseMaxAgeHours(env);
  const minSummaryChars = parseMinSummaryChars(env);
  const excludeSql = excludeDomains.length
    ? " AND " + excludeDomains.map(() => "LOWER(i.url) NOT LIKE ?").join(" AND ")
    : "";
  const query = env.DB.prepare(
    "SELECT i.id, i.title, i.url, i.raw_summary, i.impact_score, i.impact_rationale, i.action_items_json, i.target_role " +
      "FROM items i " +
      "LEFT JOIN channel_posts c ON c.item_id = i.id AND c.channel_id = ? " +
      "WHERE c.item_id IS NULL AND i.impact_score >= ? " +
      "AND COALESCE(i.published_at, i.created_at) >= datetime('now', ?) " +
      "AND LENGTH(COALESCE(i.impact_rationale, i.raw_summary, '')) >= ? " +
      excludeSql +
      " ORDER BY COALESCE(i.published_at, i.created_at) DESC, i.id DESC LIMIT ?"
  );
  const params = [
    channelId,
    minImpact,
    `-${maxAgeHours} hours`,
    minSummaryChars,
    ...excludeDomains.map((domain) => `%${domain}%`),
    limit
  ];
  const result = await query.bind(...params).all<ChannelItem>();
  return result.results ?? [];
}

function pickBestCandidate(
  items: ChannelItem[],
  recentDomains: string[],
  recentKeys: Set<string>
): ChannelItem | null {
  if (!items.length) {
    return null;
  }
  const seen = new Set<string>();
  let consecutiveDomain = "";
  let consecutiveCount = 0;
  if (recentDomains.length > 0) {
    consecutiveDomain = recentDomains[0];
    for (const domain of recentDomains) {
      if (domain === consecutiveDomain) {
        consecutiveCount += 1;
      } else {
        break;
      }
    }
  }

  for (const item of items) {
    const key = makeDedupeKey(item);
    if (recentKeys.has(key)) {
      continue;
    }
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    const host = normalizeHost(item.url ?? "");
    if (consecutiveDomain && consecutiveCount >= 2 && host === consecutiveDomain) {
      continue;
    }
    return item;
  }
  return items[0] ?? null;
}

function pickMultiCandidates(
  items: ChannelItem[],
  recentDomains: string[],
  recentKeys: Set<string>,
  minItems: number,
  maxItems: number,
  researchDomains: Set<string>,
  maxResearchPerPost: number
): ChannelBlock[] {
  if (!items.length) {
    return [];
  }
  const blocks: ChannelBlock[] = [];
  const seenKeys = new Set<string>();
  const seenDomains = new Set<string>();
  let researchCount = 0;

  for (const item of items) {
    const key = makeDedupeKey(item);
    if (recentKeys.has(key) || seenKeys.has(key)) {
      continue;
    }
    const host = normalizeHost(item.url ?? "");
    const isResearch = researchDomains.has(host);
    const tokens = makeTopicTokens(item.title ?? "");
    if (!tokens.size) {
      continue;
    }

    const similarBlock = blocks.find((block) => jaccard(block.topicTokens, tokens) >= 0.65);
    if (similarBlock) {
      if (
        similarBlock.related.length < MAX_EXTRA_SOURCES &&
        host &&
        host !== similarBlock.domain &&
        !similarBlock.related.some((related) => normalizeHost(related.url ?? "") === host)
      ) {
        if (isResearch && researchCount >= maxResearchPerPost) {
          continue;
        }
        similarBlock.related.push(item);
        seenKeys.add(key);
        if (isResearch) {
          researchCount += 1;
        }
      }
      continue;
    }

    if (blocks.length >= maxItems) {
      continue;
    }
    if (isResearch && researchCount >= maxResearchPerPost) {
      continue;
    }
    if (host && seenDomains.has(host)) {
      continue;
    }
    if (recentDomains.length > 1 && host === recentDomains[0] && recentDomains[0] === recentDomains[1]) {
      continue;
    }

    blocks.push({
      main: item,
      related: [],
      topicTokens: tokens,
      domain: host,
      isResearch
    });
    seenKeys.add(key);
    if (host) {
      seenDomains.add(host);
    }
    if (isResearch) {
      researchCount += 1;
    }
  }

  if (blocks.length >= minItems) {
    return blocks.slice(0, maxItems);
  }

  for (const item of items) {
    const key = makeDedupeKey(item);
    if (recentKeys.has(key) || seenKeys.has(key)) {
      continue;
    }
    const host = normalizeHost(item.url ?? "");
    const isResearch = researchDomains.has(host);
    if (isResearch && researchCount >= maxResearchPerPost) {
      continue;
    }
    const tokens = makeTopicTokens(item.title ?? "");
    if (!tokens.size) {
      continue;
    }
    blocks.push({
      main: item,
      related: [],
      topicTokens: tokens,
      domain: host,
      isResearch
    });
    seenKeys.add(key);
    if (isResearch) {
      researchCount += 1;
    }
    if (blocks.length >= minItems) {
      break;
    }
  }

  return blocks.slice(0, maxItems);
}

function pickBreakingCandidate(
  items: ChannelItem[],
  recentKeys: Set<string>,
  env: Env,
  researchDomains: Set<string>
): ChannelItem | null {
  for (const item of items) {
    const key = makeDedupeKey(item);
    if (recentKeys.has(key)) {
      continue;
    }
    if (isBreakingCandidate(item, env, researchDomains)) {
      return item;
    }
  }
  return null;
}

function getLocalNow(env: Env): Date {
  const offsetMinutes = parseTzOffsetMinutes(env);
  return new Date(Date.now() + offsetMinutes * 60 * 1000);
}

function isWithinActiveWindow(env: Env): boolean {
  const windows = parseActiveHours(env);
  if (!windows.length) {
    return true;
  }
  const localHour = getLocalNow(env).getHours();
  return windows.some((window) => {
    if (window.start < window.end) {
      return localHour >= window.start && localHour < window.end;
    }
    return localHour >= window.start || localHour < window.end;
  });
}

function formatLocalDate(env: Env): string {
  const now = getLocalNow(env);
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

async function recordChannelPost(env: Env, channelId: string, itemId: number): Promise<void> {
  await env.DB.prepare("INSERT INTO channel_posts (channel_id, item_id) VALUES (?, ?)")
    .bind(channelId, itemId)
    .run();
}

async function recordChannelKey(env: Env, channelId: string, key: string): Promise<void> {
  await env.DB.prepare("INSERT INTO channel_post_keys (channel_id, dedupe_key) VALUES (?, ?)")
    .bind(channelId, key)
    .run();
}

async function getLastReportDate(env: Env, channelId: string): Promise<string | null> {
  const row = await env.DB.prepare(
    "SELECT last_report_date FROM channel_report_state WHERE channel_id = ? LIMIT 1"
  )
    .bind(channelId)
    .first<{ last_report_date?: string }>();
  return row?.last_report_date ?? null;
}

async function setLastReportDate(env: Env, channelId: string, date: string): Promise<void> {
  await env.DB.prepare(
    "INSERT INTO channel_report_state (channel_id, last_report_date) VALUES (?, ?) " +
      "ON CONFLICT(channel_id) DO UPDATE SET last_report_date = excluded.last_report_date"
  )
    .bind(channelId, date)
    .run();
}

async function maybeSendDailyReport(
  env: Env,
  channelId: string,
  researchDomains: Set<string>
): Promise<void> {
  if (!env.ADMIN_CHAT_ID) {
    return;
  }
  const reportHour = parseDailyReportHour(env);
  if (reportHour === null) {
    return;
  }
  const now = getLocalNow(env);
  if (now.getHours() !== reportHour) {
    return;
  }
  const today = formatLocalDate(env);
  const lastDate = await getLastReportDate(env, channelId);
  if (lastDate === today) {
    return;
  }

  const rows = await env.DB.prepare(
    "SELECT i.url FROM channel_posts c " +
      "JOIN items i ON i.id = c.item_id " +
      "WHERE c.channel_id = ? AND c.sent_at >= datetime('now', '-24 hours')"
  )
    .bind(channelId)
    .all<{ url: string }>();

  const domainCounts: Record<string, number> = {};
  let researchCount = 0;
  for (const row of rows.results ?? []) {
    const host = normalizeHost(row.url);
    if (!host) {
      continue;
    }
    domainCounts[host] = (domainCounts[host] ?? 0) + 1;
    if (researchDomains.has(host)) {
      researchCount += 1;
    }
  }
  const total = (rows.results ?? []).length;
  const topDomains = Object.entries(domainCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([domain, count]) => `${domain} (${count})`)
    .join(", ");

  const summary = [
    "Daily channel report (last 24h)",
    `Total posts: ${total}`,
    `Research posts: ${researchCount}`,
    `Top domains: ${topDomains || "n/a"}`
  ].join("\n");

  await sendTelegramWithRetry(env, env.ADMIN_CHAT_ID, summary);
  await setLastReportDate(env, channelId, today);
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

  const researchDomains = new Set(parseResearchDomains(env));
  await maybeSendDailyReport(env, channelId, researchDomains);

  if (!isWithinActiveWindow(env)) {
    log.info("channel_outside_window", { channel_id: channelId });
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

  const recentDomains = await getRecentChannelDomains(env, channelId);
  const recentKeys = await getRecentDedupeKeys(env, channelId);
  const minItems = parsePostMinItems(env);
  const maxItems = Math.max(minItems, parsePostMaxItems(env));
  const maxResearchPerPost = parseMaxResearchPerPost(env);
  const candidates = await getCandidateItems(env, channelId, Math.max(CANDIDATE_LIMIT, maxItems * 6));
  const breakingItem = pickBreakingCandidate(candidates, recentKeys, env, researchDomains);
  if (breakingItem) {
    const lang = resolveLang(env.CHANNEL_LANGUAGE ?? "ru");
    let translatedTitle: string | null = null;
    try {
      const translated = await translateItemToRussian(breakingItem, env);
      translatedTitle = translated?.title ?? null;
    } catch (error) {
      log.warn("channel_translate_failed", { item_id: breakingItem.id, error: String(error) });
    }

    let aiSummary = "";
    if (parseUseAi(env)) {
      aiSummary = await summarizeWithAI(env, breakingItem.title ?? "", breakingItem.raw_summary ?? "", lang);
    }

    const message = buildChannelMessage(breakingItem, lang, {
      title: translatedTitle ?? breakingItem.title,
      summary: aiSummary || breakingItem.impact_rationale || breakingItem.raw_summary
    });

    await sendTelegramWithRetry(env, channelId, message);
    await recordChannelPost(env, channelId, breakingItem.id);
    await recordChannelKey(env, channelId, makeDedupeKey(breakingItem));
    log.info("channel_breaking_sent", { channel_id: channelId, item_id: breakingItem.id });
    return { sent: 1, skipped: 0 };
  }

  const pickedBlocks = pickMultiCandidates(
    candidates,
    recentDomains,
    recentKeys,
    minItems,
    maxItems,
    researchDomains,
    maxResearchPerPost
  );
  if (!pickedBlocks.length) {
    log.info("channel_no_items");
    return { sent: 0, skipped: 1 };
  }

  const lang = resolveLang(env.CHANNEL_LANGUAGE ?? "ru");
  const messageBlocks: string[] = [];
  let sentCount = 0;

  for (const block of pickedBlocks) {
    const item = block.main;
    let translatedTitle: string | null = null;
    try {
      const translated = await translateItemToRussian(item, env);
      translatedTitle = translated?.title ?? null;
    } catch (error) {
      log.warn("channel_translate_failed", { item_id: item.id, error: String(error) });
    }

    let aiSummary = "";
    if (parseUseAi(env)) {
      aiSummary = await summarizeWithAI(env, item.title ?? "", item.raw_summary ?? "", lang);
    }

    const mainBlock = buildChannelMessage(item, lang, {
      title: translatedTitle ?? item.title,
      summary: aiSummary || item.impact_rationale || item.raw_summary
    });

    if (block.related.length > 0) {
      const labels = getLabels(lang);
      const extraLinks = block.related.map((related, index) => {
        const linkLabel = index === 0 ? `${labels.source} 2` : `${labels.source} ${index + 2}`;
        return `<a href="${escapeHtml(related.url ?? "")}">${linkLabel}</a>`;
      });
      messageBlocks.push([mainBlock, ...extraLinks].join("\n"));
    } else {
      messageBlocks.push(mainBlock);
    }
    sentCount += 1;
  }

  const message = messageBlocks.join("\n\n");
  await sendTelegramWithRetry(env, channelId, message);
  for (const block of pickedBlocks) {
    await recordChannelPost(env, channelId, block.main.id);
    await recordChannelKey(env, channelId, makeDedupeKey(block.main));
    for (const related of block.related) {
      await recordChannelPost(env, channelId, related.id);
      await recordChannelKey(env, channelId, makeDedupeKey(related));
    }
  }
  log.info("channel_sent", { channel_id: channelId, count: sentCount });
  return { sent: sentCount, skipped: 0 };
}
