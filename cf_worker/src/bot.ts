import { Bot } from "grammy";
import { rateLimit } from "./middlewares/rate_limit";
import { roleKeyboard } from "./keyboards/role";
import { languageKeyboard } from "./keyboards/lang";
import { getLatestForRole } from "./services/news";
import { getUserLanguage, getUserProfile, upsertUserLanguage, upsertUserRole } from "./services/users";
import { formatItemMessage } from "./utils/text";
import { log } from "./utils/logger";
import { getLabels, resolveLang, t } from "./utils/i18n";
import { translateItemToRussian } from "./services/translate";
import type { BotContext, Env, Role, Lang } from "./types";

function normalizeRole(value: string | undefined): Role | null {
  if (!value) {
    return null;
  }
  if (value === "developer" || value === "pm" || value === "founder") {
    return value;
  }
  return null;
}

export function createBot(env: Env): Bot<BotContext> {
  const bot = new Bot<BotContext>(env.BOT_TOKEN);

  bot.use(async (ctx, next) => {
    ctx.env = env;
    await next();
  });

  bot.use(rateLimit());

  bot.command("start", async (ctx) => {
    log.info("cmd_start", { user_id: ctx.from?.id ?? null, chat_id: ctx.chat?.id ?? null });
    const updateId = ctx.update?.update_id ?? null;
    const chatId = ctx.chat?.id ?? null;
    const username = ctx.from?.username ?? null;
    ctx.env.DB
      ?.prepare("INSERT INTO bot_events (update_id, chat_id, username, event) VALUES (?, ?, ?, ?)")
      .bind(updateId, chatId ? String(chatId) : null, username, "start")
      .run()
      .catch((error) => log.warn("bot_event_log_failed", { error: String(error) }));
    const userId = ctx.from?.id;
    const language = userId ? await getUserLanguage(env, userId) : null;
    const lang = resolveLang(language ?? "ru");
    const appName = env.APP_NAME ?? "SearchAInews";
    const intro = t(lang, "startIntro").replace("SearchAInews", appName);

    if (!language) {
      await ctx.reply(`${intro}\n${t(lang, "chooseLanguage")}`, {
        reply_markup: languageKeyboard()
      });
      return;
    }

    await ctx.reply(`${intro}\n${t(lang, "chooseRole")}\nСоздано @AI_Nikitka93`, {
      reply_markup: roleKeyboard(lang)
    });
  });

  bot.command("language", async (ctx) => {
    const lang = resolveLang(await getUserLanguage(env, ctx.from?.id ?? 0));
    await ctx.reply(t(lang, "chooseLanguage"), { reply_markup: languageKeyboard() });
  });

  bot.callbackQuery(/^lang:(.+)$/, async (ctx) => {
    const value = ctx.match?.[1];
    const lang: Lang = value === "en" ? "en" : "ru";
    const userId = ctx.from?.id;
    if (!userId) {
      await ctx.answerCallbackQuery({ text: "Не удалось определить пользователя" });
      return;
    }
    await upsertUserLanguage(ctx.env, userId, ctx.from?.username ?? null, lang);
    await ctx.answerCallbackQuery({ text: t(lang, "langSaved") });
    await ctx.reply(t(lang, "chooseRole"), {
      reply_markup: roleKeyboard(lang)
    });
    ctx.env.DB
      ?.prepare("INSERT INTO bot_events (update_id, chat_id, username, event) VALUES (?, ?, ?, ?)")
      .bind(ctx.update?.update_id ?? null, ctx.chat?.id ? String(ctx.chat?.id) : null, ctx.from?.username ?? null, "lang")
      .run()
      .catch((error) => log.warn("bot_event_log_failed", { error: String(error) }));
  });

  bot.callbackQuery(/^role:(.+)$/, async (ctx) => {
    const role = normalizeRole(ctx.match?.[1]);
    if (!role) {
      await ctx.answerCallbackQuery({ text: "Неизвестная роль" });
      return;
    }

    const userId = ctx.from?.id;
    if (!userId) {
      await ctx.answerCallbackQuery({ text: "Не удалось определить пользователя" });
      return;
    }

    await upsertUserRole(ctx.env, userId, ctx.from?.username ?? null, role);
    log.info("role_selected", {
      user_id: userId,
      role,
      username: ctx.from?.username ?? null
    });
    await ctx.answerCallbackQuery({ text: "Роль сохранена" });
    const lang = resolveLang(await getUserLanguage(ctx.env, userId) ?? "ru");
    await ctx.reply(t(lang, "roleSaved"));
    ctx.env.DB
      ?.prepare("INSERT INTO bot_events (update_id, chat_id, username, event) VALUES (?, ?, ?, ?)")
      .bind(ctx.update?.update_id ?? null, ctx.chat?.id ? String(ctx.chat?.id) : null, ctx.from?.username ?? null, "role")
      .run()
      .catch((error) => log.warn("bot_event_log_failed", { error: String(error) }));
  });

  bot.command("latest", async (ctx) => {
    const userId = ctx.from?.id;
    if (!userId) {
      await ctx.reply("Не удалось определить пользователя.");
      return;
    }

    const profile = await getUserProfile(ctx.env, userId);
    const lang = resolveLang(profile.language ?? "ru");
    const role = profile.role;
    if (!role) {
      log.info("latest_no_role", { user_id: userId });
      await ctx.reply(t(lang, "noRole"), {
        reply_markup: roleKeyboard(lang)
      });
      return;
    }

    const items = await getLatestForRole(ctx.env, role, 3);
    if (!items.length) {
      log.info("latest_empty", { user_id: userId, role });
      await ctx.reply(t(lang, "noNews"));
      return;
    }

    log.info("latest_items", { user_id: userId, role, count: items.length });
    for (const item of items) {
      const translated = await translateItemToRussian(item, ctx.env);
      await ctx.reply(formatItemMessage(item, getLabels(lang), translated), {
        parse_mode: "HTML",
        disable_web_page_preview: false
      });
    }
  });

  bot.catch((err) => {
    const message = err.error?.message ?? err.message ?? "unknown";
    log.error(`Bot error: ${message}`);
    const updateId = err.ctx?.update?.update_id ?? null;
    const chatId = err.ctx?.chat?.id ?? err.ctx?.update?.message?.chat?.id ?? null;
    const username =
      err.ctx?.chat?.username ?? err.ctx?.from?.username ?? err.ctx?.update?.message?.from?.username ?? null;
    err.ctx?.env?.DB?.prepare(
      "INSERT INTO bot_errors (update_id, chat_id, username, error) VALUES (?, ?, ?, ?)"
    )
      .bind(updateId, chatId ? String(chatId) : null, username, message)
      .run()
      .catch((dbErr) => {
        log.warn("bot_error_log_failed", { error: String(dbErr) });
      });
  });

  return bot;
}
