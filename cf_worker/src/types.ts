import type { Context } from "grammy";
import type { Ai } from "@cloudflare/ai";

export type Role = "developer" | "pm" | "founder";
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
}

export interface BotContext extends Context {
  env: Env;
}
