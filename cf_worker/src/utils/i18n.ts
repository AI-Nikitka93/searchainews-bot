import type { Lang } from "../types";

export interface Labels {
  impact: string;
  why: string;
  actions: string;
  source: string;
  noTitle: string;
  noRationale: string;
  noActions: string;
}

const labels: Record<Lang, Labels> = {
  ru: {
    impact: "Impact",
    why: "Почему важно",
    actions: "Что делать",
    source: "Источник",
    noTitle: "Без заголовка",
    noRationale: "Нет объяснения",
    noActions: "Нет конкретных шагов"
  },
  en: {
    impact: "Impact",
    why: "Why it matters",
    actions: "Action items",
    source: "Source",
    noTitle: "Untitled",
    noRationale: "No rationale provided",
    noActions: "No action items"
  }
};

const texts: Record<Lang, Record<string, string>> = {
  ru: {
    chooseLanguage: "Выберите язык бота:",
    chooseRole: "Выбери роль, чтобы получать релевантные апдейты:",
    roleSaved: "Роль сохранена. Используй /latest, чтобы получить последние новости.",
    langSaved: "Язык сохранён. Теперь выберите роль.",
    startIntro: "Привет! Это SearchAInews — бот с AI‑инсайтами по новостям.",
    noRole: "Сначала выбери роль через /start.",
    noNews: "Пока нет свежих новостей с impact_score >= 3 для вашей роли.",
    menuTitle: "Меню",
    menuLatest: "📰 10 новостей",
    menuLatest10: "🗞 20 новостей",
    menuSettings: "⚙️ Настройки",
    menuRole: "👤 Роль",
    menuLanguage: "🌐 Язык",
    menuSubscribe: "✅ Подписаться",
    menuUnsubscribe: "🔕 Отключить рассылку",
    menuAbout: "ℹ️ О боте",
    menuHelp: "❓ Помощь",
    menuHint: "Выберите действие:",
    subscribedOn: "Рассылка включена.",
    subscribedOff: "Рассылка отключена.",
    aboutText: "SearchAInews — AI‑дайджест с практическими выводами по новостям. Создано @AI_Nikitka93.",
    helpText: "Команды: /start /latest /latest10 /menu /settings /role /language /subscribe /unsubscribe /about"
  },
  en: {
    chooseLanguage: "Choose bot language:",
    chooseRole: "Pick a role to get relevant updates:",
    roleSaved: "Role saved. Use /latest to get the newest updates.",
    langSaved: "Language saved. Now pick a role.",
    startIntro: "Hi! This is SearchAInews — a bot with AI insights on news.",
    noRole: "Please choose a role via /start first.",
    noNews: "No fresh items with impact_score >= 3 for your role yet.",
    menuTitle: "Menu",
    menuLatest: "📰 10 items",
    menuLatest10: "🗞 20 items",
    menuSettings: "⚙️ Settings",
    menuRole: "👤 Role",
    menuLanguage: "🌐 Language",
    menuSubscribe: "✅ Subscribe",
    menuUnsubscribe: "🔕 Unsubscribe",
    menuAbout: "ℹ️ About",
    menuHelp: "❓ Help",
    menuHint: "Choose an action:",
    subscribedOn: "Subscription enabled.",
    subscribedOff: "Subscription disabled.",
    aboutText: "SearchAInews is an AI news digest with actionable insights. Created by @AI_Nikitka93.",
    helpText: "Commands: /start /latest /latest10 /menu /settings /role /language /subscribe /unsubscribe /about"
  }
};

export function getLabels(lang: Lang): Labels {
  return labels[lang] ?? labels.ru;
}

export function t(lang: Lang, key: keyof typeof texts.ru): string {
  const pack = texts[lang] ?? texts.ru;
  return pack[key] ?? texts.ru[key];
}

export function resolveLang(value: string | null | undefined): Lang {
  if (value === "en") {
    return "en";
  }
  return "ru";
}
