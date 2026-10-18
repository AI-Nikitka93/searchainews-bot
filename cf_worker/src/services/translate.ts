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

async function translateWithChatEndpoint(
  baseUrl: string,
  apiKey: string | null,
  model: string,
  text: string
): Promise<string | null> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (apiKey) {
    headers["Authorization"] = `Bearer ${apiKey}`;
  }
  const response = await fetch(`${baseUrl}/chat/completions`, {
    method: "POST",
    headers,
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
    return null;
  }
  const payload = (await response.json()) as {
    choices?: Array<{ message?: { content?: string } }>;
  };
  const rawText = payload?.choices?.[0]?.message?.content?.trim();
  return rawText ? cleanAiArtifacts(rawText) : null;
}

async function translateText(text: string, env: Env): Promise<{ text: string; success: boolean }> {
  const start = Date.now();

  // Tier 1: Groq API with multi-key rotation (Extreme speed, <0.5s)
  const groqKeys: string[] = [];
  if (env.GROQ_API_KEYS) {
    groqKeys.push(...env.GROQ_API_KEYS.split(",").map((k) => k.trim()).filter(Boolean));
  }
  if (env.GROQ_API_KEY && !groqKeys.includes(env.GROQ_API_KEY)) {
    groqKeys.unshift(env.GROQ_API_KEY);
  }

  const groqBaseUrl = env.GROQ_BASE_URL || "https://api.groq.com/openai/v1";
  const groqModels = [env.GROQ_MODEL || "openai/gpt-oss-120b", "qwen/qwen3.8-27b"];

  for (const key of groqKeys) {
    for (const model of groqModels) {
      try {
        const translated = await translateWithChatEndpoint(groqBaseUrl, key, model, text);
        if (translated) {
          log.info("translate_done", { provider: "groq", model, duration_ms: Date.now() - start });
          return { text: translated, success: true };
        }
      } catch (e) {
        log.warn("translate_groq_key_fail", { keyPrefix: key.slice(0, 8), model, error: String(e) });
      }
    }
  }

  // Tier 2: OpenRouter API
  if (env.OPENROUTER_API_KEY) {
    const baseUrl = env.OPENROUTER_BASE_URL || "https://openrouter.ai/api/v1";
    const model = env.OPENROUTER_MODEL || "openrouter/free";
    try {
      const translated = await translateWithChatEndpoint(baseUrl, env.OPENROUTER_API_KEY, model, text);
      if (translated) {
        log.info("translate_done", { provider: "openrouter", model, duration_ms: Date.now() - start });
        return { text: translated, success: true };
      }
    } catch (e) {
      log.warn("translate_openrouter_fallback", { error: String(e) });
    }
  }

  // Tier 3: Cloudflare Workers AI
  if (env.AI) {
    try {
      const aiResponse = await (env.AI as any).run("@cf/meta/llama-3.1-8b-instruct", {
        messages: [
          {
            role: "system",
            content: "You are a precise translator. Translate to Russian. Return only the translation."
          },
          { role: "user", content: text }
        ],
        temperature: 0.2,
        max_tokens: 600
      });
      const rawText = (typeof aiResponse === "string" ? aiResponse : aiResponse?.response ?? "") as string;
      const cleaned = cleanAiArtifacts(rawText);
      if (cleaned) {
        log.info("translate_done", { provider: "cloudflare_ai", duration_ms: Date.now() - start });
        return { text: cleaned, success: true };
      }
    } catch (e) {
      log.warn("translate_cf_ai_fallback", { error: String(e) });
    }
  }

  // Tier 4: Pollinations.ai (No-key public inference safety net)
  try {
    const translated = await translateWithChatEndpoint(
      "https://text.pollinations.ai/openai",
      null,
      "openai-fast",
      text
    );
    if (translated) {
      log.info("translate_done", { provider: "pollinations", duration_ms: Date.now() - start });
      return { text: translated, success: true };
    }
  } catch (e) {
    log.warn("translate_pollinations_failed", { error: String(e) });
  }

  return { text, success: false };
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
