import type { Context } from "grammy";
import type { Ai } from "@cloudflare/ai";

export type Role =
  | "ai_specialist"
  | "ai_developer"
  | "ai_enthusiast"
  | "ai_beginner"
  | "developer"
  | "pm"
  | "founder";
export type Lang = "ru" | "en";

export interface Env {
  BOT_TOKEN: string;
  WEBHOOK_SECRET: string;
  ALLOW_WEBHOOK_WITHOUT_SECRET?: string;
  OPENROUTER_API_KEY?: string;
  OPENROUTER_BASE_URL?: string;
  OPENROUTER_MODEL?: string;
  AI: Ai;
  DB: D1Database;
  APP_NAME?: string;
  DEFAULT_ROLE?: Role;
  ADMIN_CHAT_ID?: string;
  STALE_NEWS_HOURS?: string;
  INGEST_SECRET?: string;
  CHANNEL_CHAT_ID?: string;
  CHANNEL_POST_GAP_SECONDS?: string;
  CHANNEL_HEADER?: string;
  CHANNEL_LANGUAGE?: string;
  CHANNEL_USE_AI_SUMMARY?: string;
  CHANNEL_MIN_IMPACT?: string;
  CHANNEL_EXCLUDE_DOMAINS?: string;
  CHANNEL_DEDUPE_HOURS?: string;
  CHANNEL_POST_MIN_ITEMS?: string;
  CHANNEL_POST_MAX_ITEMS?: string;
  CHANNEL_MAX_AGE_HOURS?: string;
  CHANNEL_MIN_SUMMARY_CHARS?: string;
  CHANNEL_RESEARCH_DOMAINS?: string;
  CHANNEL_MAX_RESEARCH_PER_POST?: string;
  CHANNEL_BREAKING_MIN_IMPACT?: string;
  CHANNEL_BREAKING_KEYWORDS?: string;
  CHANNEL_MODEL_RELEASE_MIN_IMPACT?: string;
  CHANNEL_ACTIVE_HOURS?: string;
  CHANNEL_TZ_OFFSET_MINUTES?: string;
  CHANNEL_DAILY_REPORT_HOUR?: string;
  NEWS_MAX_AGE_HOURS?: string;
  NEWS_RESEARCH_DOMAINS?: string;
  NEWS_MAX_RESEARCH_PER_BATCH?: string;
}

export interface BotContext extends Context {
  env: Env;
}
