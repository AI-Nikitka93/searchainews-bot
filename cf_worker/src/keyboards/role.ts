import { InlineKeyboard } from "grammy";
import type { Lang } from "../types";

const roleLabels: Record<Lang, { developer: string; pm: string; founder: string }> = {
  ru: {
    developer: "Разработчик",
    pm: "PM",
    founder: "Фаундер"
  },
  en: {
    developer: "Developer",
    pm: "PM",
    founder: "Founder"
  }
};

export function roleKeyboard(lang: Lang): InlineKeyboard {
  const labels = roleLabels[lang] ?? roleLabels.ru;
  return new InlineKeyboard()
    .text(labels.developer, "role:developer")
    .text(labels.pm, "role:pm")
    .row()
    .text(labels.founder, "role:founder");
}
