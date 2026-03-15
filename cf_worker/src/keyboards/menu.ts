import { InlineKeyboard } from "grammy";
import type { Lang } from "../types";
import { t } from "../utils/i18n";

export function menuKeyboard(lang: Lang, subscribed: boolean): InlineKeyboard {
  return new InlineKeyboard()
    .text(t(lang, "menuLatest"), "menu:latest")
    .text(t(lang, "menuLatest10"), "menu:latest10")
    .text(t(lang, "menuSettings"), "menu:settings")
    .row()
    .text(t(lang, "menuRole"), "menu:role")
    .text(t(lang, "menuLanguage"), "menu:language")
    .row()
    .text(subscribed ? t(lang, "menuUnsubscribe") : t(lang, "menuSubscribe"), subscribed ? "menu:unsubscribe" : "menu:subscribe")
    .row()
    .text(t(lang, "menuAbout"), "menu:about")
    .text(t(lang, "menuHelp"), "menu:help");
}
