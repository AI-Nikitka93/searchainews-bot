import type { Context, MiddlewareFn } from "grammy";
import { log } from "../utils/logger";

type Bucket = { count: number; resetAt: number };
const buckets = new Map<string, Bucket>();
const MAX_BUCKETS = 5000;

function getKey(ctx: Context): string | null {
  const userId = ctx.from?.id;
  if (userId) {
    return `user:${userId}`;
  }
  const chatId = ctx.chat?.id;
  if (chatId) {
    return `chat:${chatId}`;
  }
  return null;
}

function sweepIfNeeded(): void {
  if (buckets.size <= MAX_BUCKETS) {
    return;
  }
  buckets.clear();
}

export function rateLimit(windowMs = 3000, max = 3): MiddlewareFn<Context> {
  return async (ctx, next) => {
    const key = getKey(ctx);
    if (!key) {
      await next();
      return;
    }

    sweepIfNeeded();
    const now = Date.now();
    const existing = buckets.get(key);
    if (!existing || now > existing.resetAt) {
      buckets.set(key, { count: 1, resetAt: now + windowMs });
      await next();
      return;
    }

    existing.count += 1;
    if (existing.count > max) {
      log.warn("rate_limit_hit", { key });
      await ctx.reply("Слишком много запросов. Подождите пару секунд и попробуйте снова.");
      return;
    }

    buckets.set(key, existing);
    await next();
  };
}
