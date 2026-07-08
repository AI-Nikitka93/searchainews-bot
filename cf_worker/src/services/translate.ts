import type { Env } from "../types";
import { log } from "../utils/logger";
import type { NewsItem } from "./news";

const CYRILLIC_RE = /[А-Яа-яЁё]/;
const LATIN_RE = /[A-Za-z]/;

let warnedNoKey = false;

const MODERATION_PATTERN = /^(user safety|safety check|safety evaluation|content filter|moderation check)\s*:\s*(safe|unsafe|passed|ok|approved|filtered|benign)\.?\s*/i;

export function cleanAiArtifacts(text: string): string {
  const cleaned = text.trim();
  
  // Guard: if it parses as an API error JSON object, discard it
  try {
    const parsed = JSON.parse(cleaned);
    if (parsed && (parsed.error || parsed.message)) {
      return "";
    }
  } catch {}

  // Regex-based cleaning for OpenRouter moderation headers
  let content = cleaned.replace(MODERATION_PATTERN, "");
  
  // Clean markdown JSON wrapper artifacts
  content = content
    .replace(/^```json\s*/i, "")
    .replace(/```\s*$/, "")
    .replace(/^(translation|перевод)\s*:\s*/i, "")
    .trim();

  // If translation model returned just safety flags as single words, reject
  const lower = content.toLowerCase();
  if (lower === "safe" || lower === "unsafe" || lower === "passed") {
    return "";
  }
  
  return content;
}

function shouldTranslate(text: string | null | undefined): boolean {
  if (!text) {
    return false;
  }
  if (!LATIN_RE.test(text)) {
    return false;
  }
  const cyrillicCount = (text.match(/[А-Яа-яЁё]/g) || []).length;
  const latinCount = (text.match(/[A-Za-z]/g) || []).length;
  if (cyrillicCount > latinCount * 1.2) {
    return false;
  }
  return true;
}

async function translateText(text: string, env: Env): Promise<{ text: string; success: boolean }> {
  if (!env.OPENROUTER_API_KEY) {
    if (!warnedNoKey) {
      log.warn("translate_skipped_no_key");
      warnedNoKey = true;
    }
    return { text, success: false };
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
      return { text, success: false };
    }

    const payload = (await response.json()) as {
      choices?: Array<{ message?: { content?: string } }>;
    };

    const rawText = payload?.choices?.[0]?.message?.content?.trim();
    log.info("translate_done", { model, duration_ms: Date.now() - start });

    if (!rawText) {
      return { text, success: false };
    }

    const cleaned = cleanAiArtifacts(rawText);
    if (cleaned.length === 0) {
      return { text, success: false };
    }

    return { text: cleaned, success: true };
  } catch (error) {
    log.warn("translate_error", { error: String(error) });
    return { text, success: false };
  }
}

export async function translateItemToRussian(
  item: NewsItem,
  env: Env
): Promise<{
  title?: string;
  rationale?: string;
  actions?: string[];
  titleSuccess?: boolean;
  rationaleSuccess?: boolean;
  actionsSuccess?: boolean;
}> {
  const result: {
    title?: string;
    rationale?: string;
    actions?: string[];
    titleSuccess?: boolean;
    rationaleSuccess?: boolean;
    actionsSuccess?: boolean;
  } = {};

  if (shouldTranslate(item.title)) {
    const res = await translateText(item.title, env);
    result.title = res.text;
    result.titleSuccess = res.success;
  } else if (item.title) {
    result.title = item.title;
    result.titleSuccess = true;
  }

  if (shouldTranslate(item.impact_rationale)) {
    const res = await translateText(item.impact_rationale ?? "", env);
    result.rationale = res.text;
    result.rationaleSuccess = res.success;
  } else if (item.impact_rationale) {
    result.rationale = item.impact_rationale;
    result.rationaleSuccess = true;
  }

  if (item.action_items_json) {
    try {
      const parsed = JSON.parse(item.action_items_json);
      if (Array.isArray(parsed)) {
        const translated: string[] = [];
        let allSuccess = true;
        for (const action of parsed) {
          const text = String(action);
          if (shouldTranslate(text)) {
            const res = await translateText(text, env);
            translated.push(res.text);
            if (!res.success) {
              allSuccess = false;
            }
          } else {
            translated.push(text);
          }
        }
        result.actions = translated;
        result.actionsSuccess = allSuccess;
      }
    } catch (_) {
      result.actionsSuccess = false;
    }
  } else {
    result.actionsSuccess = true;
  }

  return result;
}
