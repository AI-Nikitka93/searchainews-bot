import { Bot } from "grammy";
import { rateLimit } from "./middlewares/rate_limit";
import { roleKeyboard } from "./keyboards/role";
import { languageKeyboard } from "./keyboards/lang";
import { menuKeyboard } from "./keyboards/menu";
import { getLatestForRole, markItemsDelivered } from "./services/news";
import {
  getUserLanguage,
  getUserProfile,
  getUserSettings,
  setUserSubscription,
  upsertUserLanguage,
  upsertUserRole
} from "./services/users";
import { formatItemMessage } from "./utils/text";
import { log } from "./utils/logger";
import { getLabels, resolveLang, t } from "./utils/i18n";
import { translateItemToRussian } from "./services/translate";
import type { BotContext, Env, Role, Lang } from "./types";

function normalizeRole(value: string | undefined): Role | null {
  if (!value) {
    return null;
  }
  const allowed = new Set<Role>([
    "ai_specialist",
    "ai_developer",
    "ai_enthusiast",
    "ai_beginner",
    "developer",
    "pm",
    "founder"
  ]);
  return allowed.has(value as Role) ? (value as Role) : null;
}

async function sendMenu(ctx: BotContext, lang: Lang, subscribed: boolean): Promise<void> {
  await ctx.reply(`${t(lang, "menuTitle")}\n${t(lang, "menuHint")}`, {
    reply_markup: menuKeyboard(lang, subscribed)
  });
}

async function handleLatest(ctx: BotContext, limit = 3): Promise<void> {
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

  const items = await getLatestForRole(ctx.env, role, limit, userId);
  if (!items.length) {
    log.info("latest_empty", { user_id: userId, role });
    await ctx.reply(t(lang, "noNews"));
    return;
  }

  log.info("latest_items", { user_id: userId, role, count: items.length, limit });
  for (const item of items) {
    const translated = await translateItemToRussian(item, ctx.env);
    await ctx.reply(formatItemMessage(item, getLabels(lang), translated), {
      parse_mode: "HTML",
      disable_web_page_preview: false
    });
    await markItemsDelivered(ctx.env, userId, [item.id], "manual");
  }
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

  bot.command("menu", async (ctx) => {
    const settings = await getUserSettings(ctx.env, ctx.from?.id ?? 0);
    const lang = resolveLang(settings.language ?? "ru");
    await sendMenu(ctx, lang, settings.is_subscribed);
  });

  bot.command("settings", async (ctx) => {
    const settings = await getUserSettings(ctx.env, ctx.from?.id ?? 0);
    const lang = resolveLang(settings.language ?? "ru");
    await sendMenu(ctx, lang, settings.is_subscribed);
  });

  bot.command("role", async (ctx) => {
    const lang = resolveLang(await getUserLanguage(ctx.env, ctx.from?.id ?? 0));
    await ctx.reply(t(lang, "chooseRole"), { reply_markup: roleKeyboard(lang) });
  });

  bot.command("help", async (ctx) => {
    const lang = resolveLang(await getUserLanguage(ctx.env, ctx.from?.id ?? 0));
    await ctx.reply(t(lang, "helpText"));
  });

  bot.command("about", async (ctx) => {
    const lang = resolveLang(await getUserLanguage(ctx.env, ctx.from?.id ?? 0));
    await ctx.reply(t(lang, "aboutText"));
  });

  bot.command("subscribe", async (ctx) => {
    const userId = ctx.from?.id;
    if (!userId) {
      await ctx.reply("Не удалось определить пользователя.");
      return;
    }
    const lang = resolveLang(await getUserLanguage(ctx.env, userId) ?? "ru");
    await setUserSubscription(ctx.env, userId, ctx.from?.username ?? null, true);
    await ctx.reply(t(lang, "subscribedOn"));
    await sendMenu(ctx, lang, true);
  });

  bot.command("unsubscribe", async (ctx) => {
    const userId = ctx.from?.id;
    if (!userId) {
      await ctx.reply("Не удалось определить пользователя.");
      return;
    }
    const lang = resolveLang(await getUserLanguage(ctx.env, userId) ?? "ru");
    await setUserSubscription(ctx.env, userId, ctx.from?.username ?? null, false);
    await ctx.reply(t(lang, "subscribedOff"));
    await sendMenu(ctx, lang, false);
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
    const settings = await getUserSettings(ctx.env, userId);
    await sendMenu(ctx, lang, settings.is_subscribed);
    ctx.env.DB
      ?.prepare("INSERT INTO bot_events (update_id, chat_id, username, event) VALUES (?, ?, ?, ?)")
      .bind(ctx.update?.update_id ?? null, ctx.chat?.id ? String(ctx.chat?.id) : null, ctx.from?.username ?? null, "role")
      .run()
      .catch((error) => log.warn("bot_event_log_failed", { error: String(error) }));
  });

  bot.command("latest", async (ctx) => {
    await handleLatest(ctx, 10);
  });

  bot.command("latest10", async (ctx) => {
    await handleLatest(ctx, 20);
  });

  bot.callbackQuery(/^menu:(.+)$/, async (ctx) => {
    const action = ctx.match?.[1] ?? "";
    const userId = ctx.from?.id;
    if (!userId) {
      await ctx.answerCallbackQuery({ text: "Не удалось определить пользователя" });
      return;
    }
    const settings = await getUserSettings(ctx.env, userId);
    const lang = resolveLang(settings.language ?? "ru");
    switch (action) {
      case "latest":
        await ctx.answerCallbackQuery();
        await handleLatest(ctx, 10);
        return;
      case "latest10":
        await ctx.answerCallbackQuery();
        await handleLatest(ctx, 20);
        return;
      case "settings":
        await ctx.answerCallbackQuery();
        await sendMenu(ctx, lang, settings.is_subscribed);
        return;
      case "role":
        await ctx.answerCallbackQuery();
        await ctx.reply(t(lang, "chooseRole"), { reply_markup: roleKeyboard(lang) });
        return;
      case "language":
        await ctx.answerCallbackQuery();
        await ctx.reply(t(lang, "chooseLanguage"), { reply_markup: languageKeyboard() });
        return;
      case "subscribe":
        await setUserSubscription(ctx.env, userId, ctx.from?.username ?? null, true);
        await ctx.answerCallbackQuery({ text: t(lang, "subscribedOn") });
        await sendMenu(ctx, lang, true);
        return;
      case "unsubscribe":
        await setUserSubscription(ctx.env, userId, ctx.from?.username ?? null, false);
        await ctx.answerCallbackQuery({ text: t(lang, "subscribedOff") });
        await sendMenu(ctx, lang, false);
        return;
      case "about":
        await ctx.answerCallbackQuery();
        await ctx.reply(t(lang, "aboutText"));
        return;
      case "help":
        await ctx.answerCallbackQuery();
        await ctx.reply(t(lang, "helpText"));
        return;
      default:
        await ctx.answerCallbackQuery();
        await sendMenu(ctx, lang, settings.is_subscribed);
        return;
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
