import type { Update } from "grammy/types";
import { createBot } from "./bot";
import { analyzePendingItems } from "./services/ai_analyzer";
import { runBroadcast } from "./services/broadcast";
import { checkFreshness } from "./services/freshness";
import { upsertItems } from "./services/ingest";
import { log } from "./utils/logger";
import type { Env } from "./types";

async function recordWebhook(env: Env, reqId: string, authorized: boolean, payload: unknown): Promise<void> {
  if (!env.DB) {
    return;
  }
  try {
    const body = payload as {
      update_id?: number;
      message?: { chat?: { id?: number; username?: string }; from?: { username?: string } };
      edited_message?: { chat?: { id?: number; username?: string } };
      callback_query?: { message?: { chat?: { id?: number; username?: string } }; from?: { username?: string } };
    };
    const updateId = body?.update_id ?? null;
    const message = body?.message ?? body?.edited_message ?? body?.callback_query?.message ?? null;
    const chatId = message?.chat?.id ?? null;
    const chatType = message?.chat?.type ?? null;
    const messageId = message?.message_id ?? null;
    const username =
      message?.chat?.username ?? body?.message?.from?.username ?? body?.callback_query?.from?.username ?? null;
    const kind = body?.callback_query ? "callback" : body?.message ? "message" : body?.edited_message ? "edited" : "other";
    const text = (message?.text ?? body?.callback_query?.data ?? null) as string | null;
    const command = text && text.startsWith("/") ? text.split(" ")[0] : null;

    await env.DB.prepare(
      "INSERT INTO webhook_logs (req_id, authorized, update_id, chat_id, username, kind, chat_type, message_id, command, text) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
    )
      .bind(
        reqId,
        authorized ? 1 : 0,
        updateId,
        chatId ? String(chatId) : null,
        username,
        kind,
        chatType,
        messageId,
        command,
        text ? text.slice(0, 200) : null
      )
      .run();
  } catch (error) {
    log.warn("webhook_log_failed", { req_id: reqId, error: String(error) });
  }
}

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
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
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

    const recordRequest = (status: number, authorized: boolean, error?: string) => {
      if (!env.DB) {
        return;
      }
      const headerPresent = Boolean(request.headers.get("X-Telegram-Bot-Api-Secret-Token"));
      const pathSecretPresent = url.pathname.startsWith("/webhook/");
      ctx.waitUntil(
        env.DB.prepare(
          "INSERT INTO request_logs (req_id, path, method, status, authorized, header_present, path_secret_present, error) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
        )
          .bind(
            reqId,
            url.pathname,
            request.method,
            status,
            authorized ? 1 : 0,
            headerPresent ? 1 : 0,
            pathSecretPresent ? 1 : 0,
            error ?? null
          )
          .run()
      );
    };

    const respond = async (response: Response, authorized = true, error?: string): Promise<Response> => {
      log.info("request_end", {
        req_id: reqId,
        method: request.method,
        path: url.pathname,
        status: response.status,
        duration_ms: Date.now() - start
      });
      let errorText = error;
      if (!errorText && response.status >= 400) {
        try {
          errorText = (await response.clone().text()).slice(0, 500);
        } catch {
          errorText = null;
        }
      }
      recordRequest(response.status, authorized, errorText ?? undefined);
      return response;
    };

    if (url.pathname === "/health") {
      return await respond(new Response("ok", { status: 200 }));
    }

    if (url.pathname === "/ingest") {
      if (request.method !== "POST") {
        return await respond(new Response("Method not allowed", { status: 405 }));
      }
      if (!verifyIngestSecret(request, env)) {
        log.warn("ingest_unauthorized", { req_id: reqId });
        return await respond(new Response("Unauthorized", { status: 401 }), false, "ingest_unauthorized");
      }
      try {
        const payload = await request.json();
        const items = Array.isArray(payload?.items)
          ? payload.items
          : payload?.item
            ? [payload.item]
            : [];
        if (!items.length) {
          return await respond(new Response("No items", { status: 400 }), true, "ingest_no_items");
        }
        const saved = await upsertItems(env, items);
        log.info("ingest_saved", { req_id: reqId, count: saved });
        return await respond(Response.json({ ok: true, saved }));
      } catch (error) {
        log.warn("ingest_failed", { req_id: reqId, error: String(error) });
        return await respond(new Response("Bad request", { status: 400 }), true, "ingest_bad_request");
      }
    }

    const isWebhookRoot = url.pathname === "/webhook";
    const isWebhookWithSecret = url.pathname.startsWith("/webhook/");
    if (!isWebhookRoot && !isWebhookWithSecret) {
      return await respond(new Response("Not found", { status: 404 }));
    }

    if (request.method !== "POST") {
      return await respond(new Response("Method not allowed", { status: 405 }));
    }

    let payload: unknown = null;
    try {
      payload = await request.clone().json();
    } catch (error) {
      payload = null;
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
    const authorized = verifyWebhookSecret(request, env, pathSecret);
    await recordWebhook(env, reqId, authorized, payload);
    if (!authorized) {
      const received = request.headers.get("X-Telegram-Bot-Api-Secret-Token");
      log.warn("webhook_unauthorized", {
        req_id: reqId,
        secret_present: Boolean(env.WEBHOOK_SECRET),
        header_present: Boolean(received),
        header_len: received ? received.length : 0,
        path_secret_present: Boolean(pathSecret),
        path_secret_len: pathSecret ? pathSecret.length : 0
      });
      return await respond(new Response("Unauthorized", { status: 401 }), false, "webhook_unauthorized");
    }

    if (!env.BOT_TOKEN) {
      log.error("bot_token_missing", { req_id: reqId });
      return await respond(new Response("BOT_TOKEN is not set", { status: 500 }), true, "bot_token_missing");
    }

    const bot = createBot(env);
    if (!payload) {
      return await respond(new Response("Bad request", { status: 400 }), true, "webhook_no_payload");
    }
    try {
      await bot.init();
      const update = payload as Update;
      await bot.handleUpdate(update);
      return await respond(new Response("OK", { status: 200 }), true);
    } catch (error) {
      const message = String(error);
      log.error("webhook_error", { req_id: reqId, error: message });
      if (env.DB) {
        ctx.waitUntil(
          env.DB.prepare("INSERT INTO bot_errors (update_id, chat_id, username, error) VALUES (?, ?, ?, ?)")
            .bind(null, null, null, message)
            .run()
        );
      }
      return await respond(new Response("Webhook error", { status: 500 }), true, "webhook_error");
    }
  },

  async scheduled(_event: ScheduledEvent, env: Env, ctx: ExecutionContext): Promise<void> {
    log.info("broadcast_scheduled");
    ctx.waitUntil(
      (async () => {
        await analyzePendingItems(env, 5);
        await runBroadcast(env);
        await checkFreshness(env);
      })()
    );
  }
};
