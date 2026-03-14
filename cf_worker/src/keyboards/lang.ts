import { InlineKeyboard } from "grammy";

export function languageKeyboard(): InlineKeyboard {
  return new InlineKeyboard()
    .text("Русский", "lang:ru")
    .text("English", "lang:en");
}
