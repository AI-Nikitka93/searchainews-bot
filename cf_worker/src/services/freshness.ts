import type { Env } from "../types";
import { log } from "../utils/logger";

function parseHours(value?: string | null, fallback = 12): number {
  if (!value) {
    return fallback;
  }
  const parsed = Number(value);
  if (Number.isNaN(parsed) || parsed <= 0) {
    return fallback;
  }
  return parsed;
}

async function sendAdminAlert(env: Env, message: string): Promise<void> {
  if (!env.ADMIN_CHAT_ID || !env.BOT_TOKEN) {
    return;
  }
  await fetch(`https://api.telegram.org/bot${env.BOT_TOKEN}/sendMessage`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ chat_id: env.ADMIN_CHAT_ID, text: message })
  }).catch((error) => {
    log.warn("freshness_alert_failed", { error: String(error) });
  });
}

function hoursBetween(now: Date, ts: string): number | null {
  if (!ts) {
    return null;
  }
  const parsed = new Date(ts);
  if (Number.isNaN(parsed.getTime())) {
    return null;
  }
  const diffMs = now.getTime() - parsed.getTime();
  return diffMs / (1000 * 60 * 60);
}

export async function checkFreshness(env: Env): Promise<void> {
  if (!env.DB) {
    log.warn("freshness_skip", { reason: "db_missing" });
    return;
  }

  const staleHours = parseHours(env.STALE_NEWS_HOURS, 12);
  const result = await env.DB.prepare(
    "SELECT COALESCE(MAX(published_at), MAX(created_at)) AS latest FROM items"
  ).first<{ latest: string | null }>();

  const latest = result?.latest ?? null;
  if (!latest) {
    await sendAdminAlert(env, "Freshness warning: database has no items.");
    return;
  }

  const now = new Date();
  const ageHours = hoursBetween(now, latest);
  if (ageHours === null) {
    log.warn("freshness_parse_failed", { latest });
    return;
  }

  if (ageHours > staleHours) {
    await sendAdminAlert(
      env,
      `Freshness warning: no new items for ${Math.round(ageHours)}h (threshold ${staleHours}h).`
    );
  }
}
