import { InlineKeyboard } from "grammy";
import type { Lang } from "../types";

const roleLabels: Record<
  Lang,
  { ai_specialist: string; ai_developer: string; ai_enthusiast: string; ai_beginner: string }
> = {
  ru: {
    ai_specialist: "Специалист по ИИ",
    ai_developer: "Разработчик ИИ",
    ai_enthusiast: "Любитель ИИ",
    ai_beginner: "Новичок в ИИ"
  },
  en: {
    ai_specialist: "AI Specialist",
    ai_developer: "AI Developer",
    ai_enthusiast: "AI Enthusiast",
    ai_beginner: "AI Newbie"
  }
};

export function roleKeyboard(lang: Lang): InlineKeyboard {
  const labels = roleLabels[lang] ?? roleLabels.ru;
  return new InlineKeyboard()
    .text(labels.ai_specialist, "role:ai_specialist")
    .text(labels.ai_developer, "role:ai_developer")
    .row()
    .text(labels.ai_enthusiast, "role:ai_enthusiast")
    .text(labels.ai_beginner, "role:ai_beginner");
}
