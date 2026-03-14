import type { Context, MiddlewareFn } from "grammy";
import { log } from "../utils/logger";

const buckets = new Map<number, { count: number; resetAt: number }>();

export function rateLimit(windowMs = 3000, max = 3): MiddlewareFn<Context> {
  return async (ctx, next) => {
    const userId = ctx.from?.id;
    if (!userId) {
      await next();
      return;
    }

    const now = Date.now();
    const existing = buckets.get(userId);
    if (!existing || now > existing.resetAt) {
      buckets.set(userId, { count: 1, resetAt: now + windowMs });
      await next();
      return;
    }

    existing.count += 1;
    if (existing.count > max) {
      log.warn("rate_limit_hit", { user_id: userId });
      await ctx.reply("Слишком много запросов. Подождите пару секунд и попробуйте снова.");
      return;
    }

    buckets.set(userId, existing);
    await next();
  };
}
