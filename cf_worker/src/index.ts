import { webhookCallback } from "grammy/web";
import { createBot } from "./bot";
import { runBroadcast } from "./services/broadcast";
import { upsertItems } from "./services/ingest";
import { log } from "./utils/logger";
import type { Env } from "./types";

function verifyWebhookSecret(request: Request, env: Env, pathSecret?: string | null): boolean {
  const allowInsecure = env.ALLOW_WEBHOOK_WITHOUT_SECRET === "true";
  if (allowInsecure) {
    return true;
  }
  if (!env.WEBHOOK_SECRET) {
    return allowInsecure;
  }
  const secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token");
  if (pathSecret && pathSecret === env.WEBHOOK_SECRET) {
    return true;
  }
  if (secret === env.WEBHOOK_SECRET) {
    return true;
  }
  return allowInsecure;
}

function verifyIngestSecret(request: Request, env: Env): boolean {
  const expected = env.INGEST_SECRET || env.WEBHOOK_SECRET;
  if (!expected) {
    return false;
  }
  const token = request.headers.get("X-Ingest-Token");
  return token === expected;
}

export default {
  async fetch(request: Request, env: Env, _ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);
    const reqId = crypto.randomUUID();
    const start = Date.now();
    const ip =
      request.headers.get("CF-Connecting-IP") ||
      request.headers.get("X-Forwarded-For") ||
      "unknown";

    log.info("request_start", {
      req_id: reqId,
      method: request.method,
      path: url.pathname,
      ip
    });

    const respond = (response: Response): Response => {
      log.info("request_end", {
        req_id: reqId,
        method: request.method,
        path: url.pathname,
        status: response.status,
        duration_ms: Date.now() - start
      });
      return response;
    };

    if (url.pathname === "/health") {
      return respond(new Response("ok", { status: 200 }));
    }

    if (url.pathname === "/ingest") {
      if (request.method !== "POST") {
        return respond(new Response("Method not allowed", { status: 405 }));
      }
      if (!verifyIngestSecret(request, env)) {
        log.warn("ingest_unauthorized", { req_id: reqId });
        return respond(new Response("Unauthorized", { status: 401 }));
      }
      try {
        const payload = await request.json();
        const items = Array.isArray(payload?.items)
          ? payload.items
          : payload?.item
            ? [payload.item]
            : [];
        if (!items.length) {
          return respond(new Response("No items", { status: 400 }));
        }
        const saved = await upsertItems(env, items);
        log.info("ingest_saved", { req_id: reqId, count: saved });
        return respond(Response.json({ ok: true, saved }));
      } catch (error) {
        log.warn("ingest_failed", { req_id: reqId, error: String(error) });
        return respond(new Response("Bad request", { status: 400 }));
      }
    }

    const isWebhookRoot = url.pathname === "/webhook";
    const isWebhookWithSecret = url.pathname.startsWith("/webhook/");
    if (!isWebhookRoot && !isWebhookWithSecret) {
      return respond(new Response("Not found", { status: 404 }));
    }

    if (request.method !== "POST") {
      return respond(new Response("Method not allowed", { status: 405 }));
    }

    const debugToken = request.headers.get("X-Debug-Token");
    const expectedDebug = env.INGEST_SECRET || env.WEBHOOK_SECRET;
    if (debugToken && expectedDebug && debugToken === expectedDebug) {
      const received = request.headers.get("X-Telegram-Bot-Api-Secret-Token");
      return respond(
        Response.json({
          ok: true,
          secret_present: Boolean(env.WEBHOOK_SECRET),
          secret_len: env.WEBHOOK_SECRET ? env.WEBHOOK_SECRET.length : 0,
          header_present: Boolean(received),
          header_len: received ? received.length : 0,
          header_matches: Boolean(received && env.WEBHOOK_SECRET && received === env.WEBHOOK_SECRET),
          allow_insecure: env.ALLOW_WEBHOOK_WITHOUT_SECRET ?? null,
          path_secret_present: isWebhookWithSecret,
          path_secret_len: isWebhookWithSecret ? url.pathname.split("/")[2]?.length ?? 0 : 0
        })
      );
    }

    const pathSecret = isWebhookWithSecret ? url.pathname.split("/")[2] : null;
    if (!verifyWebhookSecret(request, env, pathSecret)) {
      const received = request.headers.get("X-Telegram-Bot-Api-Secret-Token");
      log.warn("webhook_unauthorized", {
        req_id: reqId,
        secret_present: Boolean(env.WEBHOOK_SECRET),
        header_present: Boolean(received),
        header_len: received ? received.length : 0,
        path_secret_present: Boolean(pathSecret),
        path_secret_len: pathSecret ? pathSecret.length : 0
      });
      return respond(new Response("Unauthorized", { status: 401 }));
    }

    if (!env.BOT_TOKEN) {
      log.error("bot_token_missing", { req_id: reqId });
      return respond(new Response("BOT_TOKEN is not set", { status: 500 }));
    }

    const bot = createBot(env);
    const handle = webhookCallback(bot, "cloudflare-mod");
    try {
      const response = await handle(request);
      return respond(response);
    } catch (error) {
      log.error("webhook_error", { req_id: reqId, error: String(error) });
      return respond(new Response("Webhook error", { status: 500 }));
    }
  },

  async scheduled(_event: ScheduledEvent, env: Env, ctx: ExecutionContext): Promise<void> {
    log.info("broadcast_scheduled");
    ctx.waitUntil(runBroadcast(env));
  }
};
