import type { Env } from "../types";
import { log } from "../utils/logger";
import type { NewsItem } from "./news";

const CYRILLIC_RE = /[А-Яа-яЁё]/;
const LATIN_RE = /[A-Za-z]/;

let warnedNoKey = false;

function shouldTranslate(text: string | null | undefined): boolean {
  if (!text) {
    return false;
  }
  if (CYRILLIC_RE.test(text)) {
    return false;
  }
  return LATIN_RE.test(text);
}

async function translateText(text: string, env: Env): Promise<string> {
  if (!env.OPENROUTER_API_KEY) {
    if (!warnedNoKey) {
      log.warn("translate_skipped_no_key");
      warnedNoKey = true;
    }
    return text;
  }

  const baseUrl = env.OPENROUTER_BASE_URL || "https://openrouter.ai/api/v1";
  const model = env.OPENROUTER_MODEL || "openrouter/auto";
  const start = Date.now();

  try {
    const response = await fetch(`${baseUrl}/chat/completions`, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${env.OPENROUTER_API_KEY}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        model,
        temperature: 0.2,
        max_tokens: 800,
        messages: [
          {
            role: "system",
            content:
              "You are a precise translator. Translate to Russian. Keep technical terms, acronyms, and code unchanged. Return only the translation."
          },
          { role: "user", content: text }
        ]
      })
    });

    if (!response.ok) {
      const body = await response.text();
      log.warn("translate_failed", { status: response.status, body: body.slice(0, 200) });
      return text;
    }

    const payload = await response.json<{
      choices?: Array<{ message?: { content?: string } }>;
    }>();

    const translated = payload?.choices?.[0]?.message?.content?.trim();
    log.info("translate_done", { model, duration_ms: Date.now() - start });
    return translated || text;
  } catch (error) {
    log.warn("translate_error", { error: String(error) });
    return text;
  }
}

export async function translateItemToRussian(
  item: NewsItem,
  env: Env
): Promise<{ title?: string; rationale?: string; actions?: string[] }> {
  const result: { title?: string; rationale?: string; actions?: string[] } = {};

  if (shouldTranslate(item.title)) {
    result.title = await translateText(item.title, env);
  }

  if (shouldTranslate(item.impact_rationale)) {
    result.rationale = await translateText(item.impact_rationale ?? "", env);
  }

  if (item.action_items_json) {
    try {
      const parsed = JSON.parse(item.action_items_json);
      if (Array.isArray(parsed)) {
        const translated: string[] = [];
        for (const action of parsed) {
          const text = String(action);
          if (shouldTranslate(text)) {
            translated.push(await translateText(text, env));
          } else {
            translated.push(text);
          }
        }
        result.actions = translated;
      }
    } catch (_) {
      // ignore parsing errors
    }
  }

  return result;
}
